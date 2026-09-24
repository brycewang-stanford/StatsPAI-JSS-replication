"""Generalized-random-forest engine (regression, causal and FE-causal forests).

An independent numba implementation of the generalized random forest
algorithm of Athey, Tibshirani and Wager (2019) and the honest causal
forest of Wager and Athey (2018), written for StatsPAI.  No third-party
forest code is included.  Where the papers leave implementation choices
open (split constraints, leaf pruning, the little-bag variance debiaser),
the engine follows the documented behaviour of the reference R package
``grf`` so that results are statistically comparable with it; that
comparison is made on outputs only (evidence tier T3, see
``tests/reference_parity``).

Algorithm
---------
* Seeding: each little-bag group gets its own seed from
  ``numpy.random.SeedSequence(seed)``, so different seeds give independent
  forests.
* Sampling: trees are grown in little-bag groups of ``ci_group_size``
  trees sharing a half-sample of clusters; each tree draws a subsample of
  that half (``sample_fraction`` of all clusters when ``ci_group_size ==
  1``).  With no clusters every observation is its own cluster.  Honesty
  splits the tree's clusters into a growing part and an estimation part.
* Growth: nodes are processed breadth-first; a node is a leaf when it
  holds at most ``min_node_size`` growing samples, when the causal
  pseudo-outcome cannot be formed, or when no admissible split improves
  the criterion; the number of candidate variables at a node is
  ``Poisson(mtry)`` clipped to ``[1, p]``.
* Causal splitting (ATW 2019, Sec. 2.3): at each parent the gradient
  pseudo-outcome rho_i = (W_i - W_bar)[(Y_i - Y_bar) - beta_P (W_i -
  W_bar)] is computed and children are chosen to maximise the
  between-child variance of rho, subject to each child keeping enough
  treated-like and control-like observations and a share ``alpha`` of the
  parent's treatment variation ("stabilised splits").
* FE splitting: the same criterion with Y and W residualized on unit and
  period effects within the node (Kattenberg, Scheer and Thiel 2023).
* Honest leaves are repopulated with the estimation sample and empty
  leaves are pruned.
* Prediction uses per-leaf sufficient statistics averaged over trees (the
  forest-weighted local regression of ATW 2019, eq. 5), out-of-bag
  prediction excludes every tree whose drawn clusters contain the row, and
  the variance is the bootstrap of little bags (ATW 2019, Sec. 4) with an
  objective-Bayes correction that keeps it non-negative.

Not implemented: missing values in split variables (StatsPAI rejects
non-finite covariates upstream) and automatic parameter tuning.  The
random-number stream is numba's, so forests are reproducible for a given
seed but not bit-identical to any other implementation.

References
----------
[@athey2019generalized], [@wager2018estimation], [@kattenberg2023causal]
"""

from __future__ import annotations

import math
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..exceptions import DataInsufficient, MethodIncompatibility

try:  # numba is a core dependency; the fallback keeps imports safe.
    from numba import njit, prange  # type: ignore[import-untyped]

    HAS_NUMBA = True
except ImportError:  # pragma: no cover
    HAS_NUMBA = False

    def njit(*args: Any, **kwargs: Any) -> Any:  # type: ignore[no-redef]
        if args and callable(args[0]):
            return args[0]
        return lambda fn: fn

    prange = range  # type: ignore[assignment,misc]

_CACHE: bool = HAS_NUMBA and Path(__file__).exists()

KIND_REGRESSION = 0
KIND_CAUSAL = 1
# Causal forest with node-level fixed-effect residualization (CFFE).
KIND_CAUSAL_FE = 2

# Per-leaf sufficient statistics, each divided by the leaf sample count
# (the moments of the forest-weighted local regression; with
# the instrument equal to the treatment, Z == W).
_C_WEIGHT, _C_Y, _C_W, _C_YW, _C_WW = 0, 1, 2, 3, 4
_N_CAUSAL_STATS = 5
# Regression leaves: [sum G / n, sum G Y / n].
_R_WEIGHT, _R_Y = 0, 1
_N_REGRESSION_STATS = 2


# --------------------------------------------------------------------------- #
#  Relabeling and splitting
# --------------------------------------------------------------------------- #


@njit(cache=_CACHE, nogil=True)
def _relabel_causal(idx, Y, W, G, rho):  # type: ignore[no-untyped-def]
    """Causal gradient pseudo-outcome at a parent node (instrument == treatment).

    Writes rho_i = (W_i - W_bar)[(Y_i - Y_bar) - beta (W_i - W_bar)] into
    ``rho`` for the node's samples and returns True when the node must stop
    (zero weight, or an unnormalised treatment sum of squares below 1e-10).
    """
    sw = 0.0
    sy = 0.0
    swt = 0.0
    for t in range(idx.size):
        j = idx[t]
        sw += G[j]
        sy += G[j] * Y[j]
        swt += G[j] * W[j]
    if abs(sw) <= 1e-16:
        return True
    ybar = sy / sw
    wbar = swt / sw
    num = 0.0
    den = 0.0
    for t in range(idx.size):
        j = idx[t]
        dw = W[j] - wbar
        num += G[j] * dw * (Y[j] - ybar)
        den += G[j] * dw * dw
    if abs(den) < 1e-10:
        return True
    beta = num / den
    for t in range(idx.size):
        j = idx[t]
        dw = W[j] - wbar
        rho[j] = dw * ((Y[j] - ybar) - beta * dw)
    return False


@njit(cache=_CACHE, nogil=True)
def _fe_residualize(
    idx, V, G, unit, time, sw_u, s_u, sw_t, s_t, out, max_iter, tol
):  # type: ignore[no-untyped-def]
    """Weighted two-way within transformation of ``V`` over the rows ``idx``.

    Alternating projections (unit demeaning, then period demeaning) until
    the period means of the unit-demeaned values vanish.  One sweep is exact
    in a balanced block; unbalanced blocks iterate to ``tol`` (absolute, on
    the scale of ``V``) or ``max_iter``.  Returns the number of sweeps, or
    ``-1`` when the iteration cap was hit without convergence.  With a
    single period code the time step removes the (already zero) grand mean,
    so the same routine performs one-way unit demeaning.
    """
    scale = 0.0
    for t in range(idx.size):
        j = idx[t]
        out[j] = V[j]
        a = abs(V[j])
        if a > scale:
            scale = a
    threshold = tol * (1.0 + scale)
    for it in range(max_iter):
        for t in range(idx.size):
            j = idx[t]
            sw_u[unit[j]] = 0.0
            s_u[unit[j]] = 0.0
        for t in range(idx.size):
            j = idx[t]
            sw_u[unit[j]] += G[j]
            s_u[unit[j]] += G[j] * out[j]
        for t in range(idx.size):
            j = idx[t]
            if sw_u[unit[j]] > 0.0:
                out[j] -= s_u[unit[j]] / sw_u[unit[j]]
        for t in range(idx.size):
            j = idx[t]
            sw_t[time[j]] = 0.0
            s_t[time[j]] = 0.0
        for t in range(idx.size):
            j = idx[t]
            sw_t[time[j]] += G[j]
            s_t[time[j]] += G[j] * out[j]
        largest = 0.0
        for t in range(idx.size):
            j = idx[t]
            if sw_t[time[j]] > 0.0:
                m = s_t[time[j]] / sw_t[time[j]]
                if abs(m) > largest:
                    largest = abs(m)
        if largest <= threshold:
            return it + 1
        for t in range(idx.size):
            j = idx[t]
            if sw_t[time[j]] > 0.0:
                out[j] -= s_t[time[j]] / sw_t[time[j]]
    return -1


@njit(cache=_CACHE, nogil=True)
def _relabel_causal_fe(
    idx, Y, W, G, unit, time, sw_u, s_u, sw_t, s_t, Yr, Wr, rho, max_iter, tol
):  # type: ignore[no-untyped-def]
    """Node-level FE relabeling (Kattenberg, Scheer and Thiel 2023, Sec. 3).

    Residualizes Y and W on unit and period effects *within the node*, then
    forms the causal gradient pseudo-outcome rho = W~ (Y~ - beta W~) with the
    node's within estimate beta.  ``Wr`` doubles as the instrument for the
    stabilised splitting rule.  Returns True when the node must stop.
    """
    _fe_residualize(idx, Y, G, unit, time, sw_u, s_u, sw_t, s_t, Yr, max_iter, tol)
    _fe_residualize(idx, W, G, unit, time, sw_u, s_u, sw_t, s_t, Wr, max_iter, tol)
    num = 0.0
    den = 0.0
    sw = 0.0
    for t in range(idx.size):
        j = idx[t]
        sw += G[j]
        num += G[j] * Wr[j] * Yr[j]
        den += G[j] * Wr[j] * Wr[j]
    if abs(sw) <= 1e-16 or abs(den) < 1e-10:
        return True
    beta = num / den
    for t in range(idx.size):
        j = idx[t]
        rho[j] = Wr[j] * (Yr[j] - beta * Wr[j])
    return False


@njit(cache=_CACHE, nogil=True)
def _split_instrumental(
    X, idx, rho, Z, G, vars_, min_node_size, alpha, imbalance_penalty
):  # type: ignore[no-untyped-def]
    """Best stabilised causal split of a node.

    Returns (found, var, value).  Left child is ``x <= value``.
    """
    m = idx.size
    sw = 0.0
    sz = 0.0
    szz = 0.0
    srho = 0.0
    for t in range(m):
        j = idx[t]
        g = G[j]
        sw += g
        sz += g * Z[j]
        szz += g * Z[j] * Z[j]
        srho += g * rho[j]
    size_node = szz - sz * sz / sw
    min_child_size = size_node * alpha
    mean_z = sz / sw
    n_small = 0
    for t in range(m):
        if Z[idx[t]] < mean_z:
            n_small += 1

    best_dec = 0.0
    best_var = -1
    best_val = 0.0
    xs = np.empty(m)
    for v_i in range(vars_.size):
        v = vars_[v_i]
        for t in range(m):
            xs[t] = X[idx[t], v]
        order = np.argsort(xs, kind="mergesort")
        lw = 0.0
        lrho = 0.0
        lz = 0.0
        lzz = 0.0
        ln = 0
        lsmall = 0
        for t in range(m - 1):
            j = idx[order[t]]
            g = G[j]
            lw += g
            lrho += g * rho[j]
            lz += g * Z[j]
            lzz += g * Z[j] * Z[j]
            ln += 1
            if Z[j] < mean_z:
                lsmall += 1
            if xs[order[t]] == xs[order[t + 1]]:
                continue  # not a bucket boundary
            llarge = ln - lsmall
            rsmall = n_small - lsmall
            rlarge = (m - ln) - rsmall
            if lsmall < min_node_size or llarge < min_node_size:
                continue
            if rsmall < min_node_size or rlarge < min_node_size:
                break
            size_l = lzz - lz * lz / lw
            if size_l < min_child_size or (imbalance_penalty > 0.0 and size_l == 0):
                continue
            rw = sw - lw
            rz = sz - lz
            size_r = (szz - lzz) - rz * rz / rw
            if size_r < min_child_size or (imbalance_penalty > 0.0 and size_r == 0):
                continue
            rrho = srho - lrho
            dec = lrho * lrho / lw + rrho * rrho / rw
            dec -= imbalance_penalty * (1.0 / size_l + 1.0 / size_r)
            if dec > best_dec:
                best_dec = dec
                best_var = v
                best_val = xs[order[t]]
    return best_var >= 0, best_var, best_val


@njit(cache=_CACHE, nogil=True)
def _split_tau_heterogeneity(
    X, idx, Yr, Wr, G, vars_, min_node_size, alpha, imbalance_penalty
):  # type: ignore[no-untyped-def]
    """Best tau-heterogeneity split (Kattenberg, Scheer and Thiel 2023, eq. 4).

    Scores a candidate split by ``n_L n_R / n^2 (tau_L - tau_R)^2`` with
    ``tau = sum G W~ Y~ / sum G W~^2`` evaluated on the *parent's*
    node-residualized outcome and treatment, which is what the authors'
    implementation searches over.  A child whose residualized treatment has
    no variation carries no ``tau`` and is skipped.  ``alpha`` is applied to
    the child's share of node rows (the grf criterion's size measure does
    not exist here) and ``imbalance_penalty`` is subtracted as in grf.
    """
    m = idx.size
    num_tot = 0.0
    den_tot = 0.0
    for t in range(m):
        j = idx[t]
        num_tot += G[j] * Wr[j] * Yr[j]
        den_tot += G[j] * Wr[j] * Wr[j]
    min_rows = min_node_size
    if alpha > 0.0:
        a_rows = int(alpha * m)
        if a_rows > min_rows:
            min_rows = a_rows
    best_dec = 0.0
    best_var = -1
    best_val = 0.0
    xs = np.empty(m)
    for v_i in range(vars_.size):
        v = vars_[v_i]
        for t in range(m):
            xs[t] = X[idx[t], v]
        order = np.argsort(xs, kind="mergesort")
        num_l = 0.0
        den_l = 0.0
        ln = 0
        for t in range(m - 1):
            j = idx[order[t]]
            num_l += G[j] * Wr[j] * Yr[j]
            den_l += G[j] * Wr[j] * Wr[j]
            ln += 1
            if xs[order[t]] == xs[order[t + 1]]:
                continue  # not a bucket boundary
            rn = m - ln
            if ln < min_rows:
                continue
            if rn < min_rows:
                break
            den_r = den_tot - den_l
            if den_l < 1e-10 or den_r < 1e-10:
                continue
            tau_l = num_l / den_l
            tau_r = (num_tot - num_l) / den_r
            diff = tau_l - tau_r
            dec = (ln * rn) / (m * m) * diff * diff
            if imbalance_penalty > 0.0:
                dec -= imbalance_penalty * (1.0 / ln + 1.0 / rn)
            if dec > best_dec:
                best_dec = dec
                best_var = v
                best_val = xs[order[t]]
    return best_var >= 0, best_var, best_val


@njit(cache=_CACHE, nogil=True)
def _split_regression(
    X, idx, rho, G, vars_, alpha, imbalance_penalty
):  # type: ignore[no-untyped-def]
    """Best CART split of a node on the response ``rho``."""
    m = idx.size
    min_child_size = max(int(math.ceil(m * alpha)), 1)
    sw = 0.0
    srho = 0.0
    for t in range(m):
        j = idx[t]
        sw += G[j]
        srho += G[j] * rho[j]
    best_dec = 0.0
    best_var = -1
    best_val = 0.0
    xs = np.empty(m)
    for v_i in range(vars_.size):
        v = vars_[v_i]
        for t in range(m):
            xs[t] = X[idx[t], v]
        order = np.argsort(xs, kind="mergesort")
        lw = 0.0
        lrho = 0.0
        ln = 0
        for t in range(m - 1):
            j = idx[order[t]]
            lw += G[j]
            lrho += G[j] * rho[j]
            ln += 1
            if xs[order[t]] == xs[order[t + 1]]:
                continue
            rn = m - ln
            if ln < min_child_size:
                continue
            if rn < min_child_size:
                break
            rw = sw - lw
            rrho = srho - lrho
            dec = lrho * lrho / lw + rrho * rrho / rw
            dec -= imbalance_penalty * (1.0 / ln + 1.0 / rn)
            if dec > best_dec:
                best_dec = dec
                best_var = v
                best_val = xs[order[t]]
    return best_var >= 0, best_var, best_val


# --------------------------------------------------------------------------- #
#  Sampling
# --------------------------------------------------------------------------- #


@njit(cache=_CACHE, nogil=True)
def _shuffle_keep(values, keep):  # type: ignore[no-untyped-def]
    perm = values.copy()
    np.random.shuffle(perm)
    return perm[:keep]


@njit(cache=_CACHE, nogil=True)
def _samples_from_clusters(
    cluster_list, cl_offsets, cl_members, samples_per_cluster
):  # type: ignore[no-untyped-def]
    """Observations drawn from each listed cluster (capped per cluster)."""
    total = 0
    for c in cluster_list:
        size = cl_offsets[c + 1] - cl_offsets[c]
        total += min(size, samples_per_cluster)
    out = np.empty(total, dtype=np.int64)
    pos = 0
    for c in cluster_list:
        a = cl_offsets[c]
        b = cl_offsets[c + 1]
        size = b - a
        if size <= samples_per_cluster:
            for t in range(a, b):
                out[pos] = cl_members[t]
                pos += 1
        else:
            chosen = _shuffle_keep(cl_members[a:b], samples_per_cluster)
            for t in range(samples_per_cluster):
                out[pos] = chosen[t]
                pos += 1
    return out


@njit(cache=_CACHE, nogil=True)
def _members_of_clusters(  # type: ignore[no-untyped-def]
    cluster_list, cl_offsets, cl_members
):
    total = 0
    for c in cluster_list:
        total += cl_offsets[c + 1] - cl_offsets[c]
    out = np.empty(total, dtype=np.int64)
    pos = 0
    for c in cluster_list:
        for t in range(cl_offsets[c], cl_offsets[c + 1]):
            out[pos] = cl_members[t]
            pos += 1
    return out


# --------------------------------------------------------------------------- #
#  Tree growth
# --------------------------------------------------------------------------- #


@njit(cache=_CACHE, nogil=True)
def _grow_tree(
    X,
    Y,
    W,
    G,
    kind,
    grow_samples,
    min_node_size,
    mtry,
    alpha,
    imbalance_penalty,
    stabilize_splits,
    max_depth,
    rho,
    unit,
    time,
    fe_scratch,
    Yr,
    Wr,
    fe_max_iter,
    fe_tol,
    tau_split,
    M,
    params,
    rho_mat,
):  # type: ignore[no-untyped-def]
    """Grow one tree on ``grow_samples``.

    Returns node arrays (split_var, split_val, left, right) plus the
    growing samples arranged so that leaf ``k`` owns
    ``work[node_start[k]:node_end[k]]``.
    """
    m = grow_samples.size
    p = X.shape[1]
    max_nodes = 2 * m + 1
    split_var = np.full(max_nodes, -1, dtype=np.int64)
    split_val = np.zeros(max_nodes)
    left = np.full(max_nodes, -1, dtype=np.int64)
    right = np.full(max_nodes, -1, dtype=np.int64)
    node_start = np.zeros(max_nodes, dtype=np.int64)
    node_end = np.zeros(max_nodes, dtype=np.int64)
    depth = np.zeros(max_nodes, dtype=np.int64)
    work = grow_samples.copy()
    all_vars = np.arange(p)

    node_start[0] = 0
    node_end[0] = m
    n_nodes = 1
    i = 0
    while i < n_nodes:
        s = node_start[i]
        e = node_end[i]
        size = e - s
        # Candidate variables are drawn before the stopping checks so the
        # random stream does not depend on which nodes stop.
        k = np.random.poisson(mtry)
        if k < 1:
            k = 1
        if k > p:
            k = p
        vars_ = _shuffle_keep(all_vars, k)
        if size <= min_node_size or (max_depth > 0 and depth[i] >= max_depth):
            i += 1
            continue
        idx = work[s:e]
        if kind >= KIND_INSTRUMENTAL:
            found, var, val = relabel_and_split(
                kind,
                X,
                idx,
                M,
                G,
                vars_,
                min_node_size,
                alpha,
                imbalance_penalty,
                stabilize_splits,
                params,
                rho_mat,
            )
            if not found:
                i += 1
                continue
        elif kind == KIND_CAUSAL:
            if _relabel_causal(idx, Y, W, G, rho):
                i += 1
                continue
        elif kind == KIND_CAUSAL_FE:
            if _relabel_causal_fe(
                idx,
                Y,
                W,
                G,
                unit,
                time,
                fe_scratch[0],
                fe_scratch[1],
                fe_scratch[2],
                fe_scratch[3],
                Yr,
                Wr,
                rho,
                fe_max_iter,
                fe_tol,
            ):
                i += 1
                continue
        else:
            for t in range(size):
                rho[idx[t]] = Y[idx[t]]
        if kind >= KIND_INSTRUMENTAL:
            pass
        elif kind == KIND_CAUSAL and stabilize_splits:
            found, var, val = _split_instrumental(
                X, idx, rho, W, G, vars_, min_node_size, alpha, imbalance_penalty
            )
        elif kind == KIND_CAUSAL_FE and tau_split:
            found, var, val = _split_tau_heterogeneity(
                X, idx, Yr, Wr, G, vars_, min_node_size, alpha, imbalance_penalty
            )
        elif kind == KIND_CAUSAL_FE and stabilize_splits:
            found, var, val = _split_instrumental(
                X, idx, rho, Wr, G, vars_, min_node_size, alpha, imbalance_penalty
            )
        else:
            found, var, val = _split_regression(
                X, idx, rho, G, vars_, alpha, imbalance_penalty
            )
        if not found:
            i += 1
            continue
        # Partition work[s:e] into x <= val (left) and x > val (right).
        lo = s
        hi = e - 1
        while lo <= hi:
            if X[work[lo], var] <= val:
                lo += 1
            else:
                tmp = work[lo]
                work[lo] = work[hi]
                work[hi] = tmp
                hi -= 1
        split_var[i] = var
        split_val[i] = val
        left[i] = n_nodes
        right[i] = n_nodes + 1
        node_start[n_nodes] = s
        node_end[n_nodes] = lo
        node_start[n_nodes + 1] = lo
        node_end[n_nodes + 1] = e
        depth[n_nodes] = depth[i] + 1
        depth[n_nodes + 1] = depth[i] + 1
        n_nodes += 2
        i += 1
    return (
        split_var[:n_nodes],
        split_val[:n_nodes],
        left[:n_nodes],
        right[:n_nodes],
        node_start[:n_nodes],
        node_end[:n_nodes],
        work,
    )


@njit(cache=_CACHE, nogil=True)
def _find_leaf(  # type: ignore[no-untyped-def]
    X, row, root, split_var, split_val, left, right
):
    node = root
    while left[node] != -1:
        if X[row, split_var[node]] <= split_val[node]:
            node = left[node]
        else:
            node = right[node]
    return node


@njit(cache=_CACHE, nogil=True)
def _assign_leaves(  # type: ignore[no-untyped-def]
    X, samples, split_var, split_val, left, right
):
    """CSR of samples per node (only leaves are populated)."""
    n_nodes = left.size
    leaf_of = np.empty(samples.size, dtype=np.int64)
    counts = np.zeros(n_nodes + 1, dtype=np.int64)
    for t in range(samples.size):
        leaf = _find_leaf(X, samples[t], 0, split_var, split_val, left, right)
        leaf_of[t] = leaf
        counts[leaf + 1] += 1
    offsets = np.cumsum(counts)
    pos = offsets[:-1].copy()
    members = np.empty(samples.size, dtype=np.int64)
    for t in range(samples.size):
        leaf = leaf_of[t]
        members[pos[leaf]] = samples[t]
        pos[leaf] += 1
    return offsets, members


@njit(cache=_CACHE, nogil=True)
def _prune_empty_leaves(left, right, leaf_offsets):  # type: ignore[no-untyped-def]
    """Collapse internal nodes with an empty honest child into their
    non-empty child.  Returns the new root and the
    rewritten child pointers (node indices are unchanged)."""
    n_nodes = left.size
    new_left = left.copy()
    new_right = right.copy()
    redirect = np.arange(n_nodes)
    empty = np.zeros(n_nodes, dtype=np.bool_)
    for node in range(n_nodes - 1, -1, -1):
        if left[node] == -1:
            empty[node] = leaf_offsets[node + 1] == leaf_offsets[node]
            continue
        lchild = redirect[left[node]]
        rchild = redirect[right[node]]
        l_empty = new_left[lchild] == -1 and empty[lchild]
        r_empty = new_left[rchild] == -1 and empty[rchild]
        if l_empty and r_empty:
            new_left[node] = -1
            new_right[node] = -1
            empty[node] = True
        elif l_empty:
            redirect[node] = rchild
        elif r_empty:
            redirect[node] = lchild
        else:
            new_left[node] = lchild
            new_right[node] = rchild
    return redirect[0], new_left, new_right


@njit(cache=_CACHE, nogil=True)
def _leaf_values_fe(
    leaf_offsets,
    leaf_members,
    Y,
    W,
    G,
    unit,
    time,
    fe_scratch,
    Yr,
    Wr,
    fe_max_iter,
    fe_tol,
):  # type: ignore[no-untyped-def]
    """Leaf statistics for the FE causal forest.

    Fixed effects are removed again within each (honest) leaf; the leaf
    stores ``[sum G / n, 0, 0, sum G Y~ W~ / n, sum G W~^2 / n]`` so the
    generic causal prediction and little-bag variance kernels apply
    unchanged (the residualized means are zero).  A leaf whose residualized
    treatment has no variation carries no information about the effect and
    is marked empty rather than assigned an arbitrary value.
    """
    n_nodes = leaf_offsets.size - 1
    vals = np.zeros((n_nodes, _N_CAUSAL_STATS))
    nonempty = np.zeros(n_nodes, dtype=np.bool_)
    for node in range(n_nodes):
        a = leaf_offsets[node]
        b = leaf_offsets[node + 1]
        c = b - a
        if c == 0:
            continue
        members = leaf_members[a:b]
        _fe_residualize(
            members,
            Y,
            G,
            unit,
            time,
            fe_scratch[0],
            fe_scratch[1],
            fe_scratch[2],
            fe_scratch[3],
            Yr,
            fe_max_iter,
            fe_tol,
        )
        _fe_residualize(
            members,
            W,
            G,
            unit,
            time,
            fe_scratch[0],
            fe_scratch[1],
            fe_scratch[2],
            fe_scratch[3],
            Wr,
            fe_max_iter,
            fe_tol,
        )
        sw = 0.0
        syw = 0.0
        sww = 0.0
        for t in range(c):
            j = members[t]
            sw += G[j]
            syw += G[j] * Yr[j] * Wr[j]
            sww += G[j] * Wr[j] * Wr[j]
        if abs(sw) <= 1e-16 or sww < 1e-10:
            continue
        vals[node, _C_WEIGHT] = sw / c
        vals[node, _C_YW] = syw / c
        vals[node, _C_WW] = sww / c
        nonempty[node] = True
    return vals, nonempty


@njit(cache=_CACHE, nogil=True)
def _leaf_values(
    kind,
    leaf_offsets,
    leaf_members,
    Y,
    W,
    G,
    unit,
    time,
    fe_scratch,
    Yr,
    Wr,
    fe_max_iter,
    fe_tol,
):  # type: ignore[no-untyped-def]
    n_nodes = leaf_offsets.size - 1
    if kind == KIND_CAUSAL_FE:
        return _leaf_values_fe(
            leaf_offsets,
            leaf_members,
            Y,
            W,
            G,
            unit,
            time,
            fe_scratch,
            Yr,
            Wr,
            fe_max_iter,
            fe_tol,
        )
    k = _N_CAUSAL_STATS if kind == KIND_CAUSAL else _N_REGRESSION_STATS
    vals = np.zeros((n_nodes, k))
    nonempty = np.zeros(n_nodes, dtype=np.bool_)
    for node in range(n_nodes):
        a = leaf_offsets[node]
        b = leaf_offsets[node + 1]
        c = b - a
        if c == 0:
            continue
        sw = 0.0
        for t in range(a, b):
            j = leaf_members[t]
            g = G[j]
            sw += g
            vals[node, 1] += g * Y[j]
            if kind == KIND_CAUSAL:
                vals[node, 2] += g * W[j]
                vals[node, 3] += g * Y[j] * W[j]
                vals[node, 4] += g * W[j] * W[j]
        if abs(sw) <= 1e-16:
            vals[node, :] = 0.0
            continue
        vals[node, 0] = sw
        for q in range(k):
            vals[node, q] /= c
        nonempty[node] = True
    return vals, nonempty


@njit(cache=_CACHE, nogil=True)
def _train_group(
    X,
    Y,
    W,
    G,
    kind,
    cl_offsets,
    cl_members,
    samples_per_cluster,
    sample_fraction,
    mtry,
    min_node_size,
    honesty,
    honesty_fraction,
    prune,
    alpha,
    imbalance_penalty,
    stabilize_splits,
    ci_group_size,
    max_depth,
    seed,
    unit,
    time,
    n_units,
    n_times,
    fe_max_iter,
    fe_tol,
    tau_split,
    M,
    params,
    rho_width,
):  # type: ignore[no-untyped-def]
    """Train one little-bag group of ``ci_group_size`` trees.

    Returns a list of per-tree tuples
    (root, split_var, split_val, left, right, leaf_offsets, leaf_members,
    leaf_values, leaf_nonempty, drawn_samples).
    """
    np.random.seed(seed)
    n = X.shape[0]
    n_clusters = cl_offsets.size - 1
    all_clusters = np.arange(n_clusters)
    rho = np.zeros(n)
    rho_mat = np.zeros((n if kind >= KIND_INSTRUMENTAL else 1, rho_width))
    Yr = np.zeros(n)
    Wr = np.zeros(n)
    fe_scratch = (
        np.zeros(max(n_units, 1)),
        np.zeros(max(n_units, 1)),
        np.zeros(max(n_times, 1)),
        np.zeros(max(n_times, 1)),
    )
    trees = []
    if ci_group_size == 1:
        tree_cluster_sets = [
            _shuffle_keep(all_clusters, int(n_clusters * sample_fraction))
        ]
    else:
        half = _shuffle_keep(all_clusters, int(n_clusters * 0.5))
        tree_cluster_sets = []
        for _ in range(ci_group_size):
            keep = int(math.ceil(half.size * sample_fraction * 2.0))
            tree_cluster_sets.append(_shuffle_keep(half, keep))

    for tree_clusters in tree_cluster_sets:
        if honesty:
            perm = _shuffle_keep(tree_clusters, tree_clusters.size)
            n_grow = int(math.ceil(tree_clusters.size * honesty_fraction))
            grow_clusters = perm[:n_grow]
            est_clusters = perm[n_grow:]
            grow_samples = _samples_from_clusters(
                grow_clusters, cl_offsets, cl_members, samples_per_cluster
            )
            est_samples = _samples_from_clusters(
                est_clusters, cl_offsets, cl_members, samples_per_cluster
            )
        else:
            grow_samples = _samples_from_clusters(
                tree_clusters, cl_offsets, cl_members, samples_per_cluster
            )
            est_samples = np.empty(0, dtype=np.int64)
        drawn = _members_of_clusters(tree_clusters, cl_offsets, cl_members)

        split_var, split_val, left, right, node_start, node_end, work = _grow_tree(
            X,
            Y,
            W,
            G,
            kind,
            grow_samples,
            min_node_size,
            mtry,
            alpha,
            imbalance_penalty,
            stabilize_splits,
            max_depth,
            rho,
            unit,
            time,
            fe_scratch,
            Yr,
            Wr,
            fe_max_iter,
            fe_tol,
            tau_split,
            M,
            params,
            rho_mat,
        )
        root = 0
        if honesty and est_samples.size > 0:
            leaf_offsets, leaf_members = _assign_leaves(
                X, est_samples, split_var, split_val, left, right
            )
            if prune:
                root, left, right = _prune_empty_leaves(left, right, leaf_offsets)
        else:
            # Non-honest: leaves keep their growing samples.
            n_nodes = left.size
            counts = np.zeros(n_nodes + 1, dtype=np.int64)
            for node in range(n_nodes):
                if left[node] == -1:
                    counts[node + 1] = node_end[node] - node_start[node]
            leaf_offsets = np.cumsum(counts)
            leaf_members = np.empty(leaf_offsets[-1], dtype=np.int64)
            for node in range(n_nodes):
                if left[node] == -1:
                    a = leaf_offsets[node]
                    for t in range(node_start[node], node_end[node]):
                        leaf_members[a] = work[t]
                        a += 1
        if kind >= KIND_INSTRUMENTAL:
            vals, nonempty = leaf_values_ext(
                kind, leaf_offsets, leaf_members, M, G, params
            )
        else:
            vals, nonempty = _leaf_values(
                kind,
                leaf_offsets,
                leaf_members,
                Y,
                W,
                G,
                unit,
                time,
                fe_scratch,
                Yr,
                Wr,
                fe_max_iter,
                fe_tol,
            )
        trees.append(
            (
                root,
                split_var,
                split_val,
                left,
                right,
                leaf_offsets,
                leaf_members,
                vals,
                nonempty,
                drawn,
            )
        )
    return trees


# --------------------------------------------------------------------------- #
#  Prediction
# --------------------------------------------------------------------------- #


@njit(cache=_CACHE, nogil=True)
def _debias_variance(  # type: ignore[no-untyped-def]
    var_between, group_noise, num_good_groups
):
    """Objective-Bayes correction of a little-bag variance estimate."""
    initial_estimate = var_between - group_noise
    initial_se = max(var_between, group_noise) * math.sqrt(2.0 / num_good_groups)
    if abs(initial_se) < 1.0e-10:
        return 0.0
    ratio = initial_estimate / initial_se
    numerator = math.exp(-ratio * ratio / 2.0) / math.sqrt(2.0 * math.pi)
    denominator = 0.5 * math.erfc(-ratio / math.sqrt(2.0))
    return initial_estimate + initial_se * numerator / denominator


@njit(cache=_CACHE, parallel=True)
def _predict_kernel(
    kind,
    X,
    rows,
    oob,
    roots,
    node_offsets,
    split_var,
    split_val,
    left,
    right,
    leaf_values,
    leaf_nonempty,
    drawn_bitmap,
    ci_group_size,
    estimate_variance,
):  # type: ignore[no-untyped-def]
    """Point predictions and (optionally) little-bag variances.

    ``rows`` indexes ``X``.  With ``oob=True`` the prediction for row ``i``
    only uses trees whose drawn sample excludes ``i``.
    """
    n_rows = rows.size
    n_trees = roots.size
    k = leaf_values.shape[1]
    pred = np.full(n_rows, np.nan)
    var = np.full(n_rows, np.nan)
    L = ci_group_size
    n_groups = n_trees // L
    for r in prange(n_rows):
        row = rows[r]
        avg = np.zeros(k)
        per_tree = np.zeros((n_trees, k))
        valid = np.zeros(n_trees, dtype=np.bool_)
        count = 0
        for t in range(n_trees):
            if oob:
                byte = drawn_bitmap[t, row >> 3]
                if (byte >> (row & 7)) & 1:
                    continue
            base = node_offsets[t]
            node = roots[t]
            while left[base + node] != -1:
                if X[row, split_var[base + node]] <= split_val[base + node]:
                    node = left[base + node]
                else:
                    node = right[base + node]
            g = base + node
            if not leaf_nonempty[g]:
                continue
            valid[t] = True
            count += 1
            for q in range(k):
                avg[q] += leaf_values[g, q]
                per_tree[t, q] = leaf_values[g, q]
        if count == 0:
            continue
        for q in range(k):
            avg[q] /= count
        if kind == KIND_REGRESSION:
            pred[r] = avg[_R_Y] / avg[_R_WEIGHT]
            if estimate_variance and L > 1:
                mu = pred[r]
                rho_sq = 0.0
                rho_grouped_sq = 0.0
                good = 0
                for grp in range(n_groups):
                    ok = True
                    for j in range(L):
                        if not valid[grp * L + j]:
                            ok = False
                            break
                    if not ok:
                        continue
                    good += 1
                    group_rho = 0.0
                    for j in range(L):
                        t = grp * L + j
                        rr = (per_tree[t, _R_Y] - mu * per_tree[t, _R_WEIGHT]) / avg[
                            _R_WEIGHT
                        ]
                        rho_sq += rr * rr
                        group_rho += rr
                    rho_grouped_sq += (group_rho / L) ** 2
                if good > 0:
                    var_between = rho_grouped_sq / good
                    var_total = rho_sq / (good * L)
                    group_noise = (var_total - var_between) / (L - 1)
                    var[r] = _debias_variance(var_between, group_noise, good)
            continue
        den = avg[_C_WW] * avg[_C_WEIGHT] - avg[_C_W] * avg[_C_W]
        tau = (avg[_C_YW] * avg[_C_WEIGHT] - avg[_C_Y] * avg[_C_W]) / den
        pred[r] = tau
        if estimate_variance and L > 1:
            mu = (avg[_C_Y] - avg[_C_W] * tau) / avg[_C_WEIGHT]
            rho_sq = 0.0
            rho_grouped_sq = 0.0
            good = 0
            for grp in range(n_groups):
                ok = True
                for j in range(L):
                    if not valid[grp * L + j]:
                        ok = False
                        break
                if not ok:
                    continue
                good += 1
                group_rho = 0.0
                for j in range(L):
                    t = grp * L + j
                    psi_1 = (
                        per_tree[t, _C_YW]
                        - per_tree[t, _C_WW] * tau
                        - per_tree[t, _C_W] * mu
                    )
                    psi_2 = (
                        per_tree[t, _C_Y]
                        - per_tree[t, _C_W] * tau
                        - per_tree[t, _C_WEIGHT] * mu
                    )
                    rr = (avg[_C_WEIGHT] * psi_1 - avg[_C_W] * psi_2) / den
                    rho_sq += rr * rr
                    group_rho += rr
                rho_grouped_sq += (group_rho / L) ** 2
            if good > 0:
                var_between = rho_grouped_sq / good
                var_total = rho_sq / (good * L)
                group_noise = (var_total - var_between) / (L - 1)
                var[r] = _debias_variance(var_between, group_noise, good)
    return pred, var


@njit(cache=_CACHE, parallel=True)
def _forest_weights_kernel(
    X,
    rows,
    oob,
    n_train,
    roots,
    node_offsets,
    split_var,
    split_val,
    left,
    right,
    leaf_offsets,
    leaf_offset_base,
    leaf_members,
    member_base,
    leaf_nonempty,
    drawn_bitmap,
):  # type: ignore[no-untyped-def]
    """Dense forest weights alpha_i(x) (ATW 2019, eq. 3)."""
    n_rows = rows.size
    n_trees = roots.size
    out = np.zeros((n_rows, n_train))
    for r in prange(n_rows):
        row = rows[r]
        count = 0
        for t in range(n_trees):
            if oob:
                byte = drawn_bitmap[t, row >> 3]
                if (byte >> (row & 7)) & 1:
                    continue
            base = node_offsets[t]
            node = roots[t]
            while left[base + node] != -1:
                if X[row, split_var[base + node]] <= split_val[base + node]:
                    node = left[base + node]
                else:
                    node = right[base + node]
            g = base + node
            if not leaf_nonempty[g]:
                continue
            lb = leaf_offset_base[t] + node
            a = leaf_offsets[lb] + member_base[t]
            b = leaf_offsets[lb + 1] + member_base[t]
            size = b - a
            if size == 0:
                continue
            count += 1
            for q in range(a, b):
                out[r, leaf_members[q]] += 1.0 / size
        if count > 0:
            for j in range(n_train):
                out[r, j] /= count
    return out


# --------------------------------------------------------------------------- #
#  Python-level forest object
# --------------------------------------------------------------------------- #


@dataclass
class GRFForest:
    """A trained forest stored as concatenated flat arrays."""

    kind: int
    n_train: int
    n_features: int
    ci_group_size: int
    roots: np.ndarray
    node_offsets: np.ndarray
    split_var: np.ndarray
    split_val: np.ndarray
    left: np.ndarray
    right: np.ndarray
    leaf_values: np.ndarray
    leaf_nonempty: np.ndarray
    leaf_offsets: np.ndarray
    leaf_offset_base: np.ndarray
    leaf_members: np.ndarray
    member_base: np.ndarray
    drawn_bitmap: np.ndarray
    options: Dict[str, Any] = field(default_factory=dict)
    params: np.ndarray = field(default_factory=lambda: np.zeros(1))
    aux: Dict[str, np.ndarray] = field(default_factory=dict)

    @property
    def num_trees(self) -> int:
        return int(self.roots.size)

    def predict(
        self,
        X: Optional[np.ndarray] = None,
        estimate_variance: bool = False,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Predictions on new ``X``; out-of-bag predictions when ``X`` is None.

        OOB mode requires the training matrix, which the caller passes via
        :meth:`predict_oob`.
        """
        if X is None:
            raise MethodIncompatibility(
                "use predict_oob(X_train) for out-of-bag predictions"
            )
        X = np.ascontiguousarray(X, dtype=np.float64)
        rows = np.arange(X.shape[0], dtype=np.int64)
        if self.kind >= KIND_INSTRUMENTAL:
            return self._predict_moments(X, rows, False, estimate_variance)
        return _predict_kernel(
            self.kind,
            X,
            rows,
            False,
            self.roots,
            self.node_offsets,
            self.split_var,
            self.split_val,
            self.left,
            self.right,
            self.leaf_values,
            self.leaf_nonempty,
            self.drawn_bitmap,
            self.ci_group_size,
            bool(estimate_variance),
        )

    def predict_oob(
        self, X_train: np.ndarray, estimate_variance: bool = False
    ) -> Tuple[np.ndarray, np.ndarray]:
        X_train = np.ascontiguousarray(X_train, dtype=np.float64)
        if X_train.shape[0] != self.n_train:
            raise MethodIncompatibility("predict_oob needs the training matrix")
        rows = np.arange(self.n_train, dtype=np.int64)
        if self.kind >= KIND_INSTRUMENTAL:
            return self._predict_moments(X_train, rows, True, estimate_variance)
        return _predict_kernel(
            self.kind,
            X_train,
            rows,
            True,
            self.roots,
            self.node_offsets,
            self.split_var,
            self.split_val,
            self.left,
            self.right,
            self.leaf_values,
            self.leaf_nonempty,
            self.drawn_bitmap,
            self.ci_group_size,
            bool(estimate_variance),
        )

    def _predict_moments(
        self, X: np.ndarray, rows: np.ndarray, oob: bool, estimate_variance: bool
    ) -> Tuple[np.ndarray, np.ndarray]:
        """``(pred, var)`` of shape ``(n_rows, n_outputs)`` for the moment
        kinds of :mod:`._grf_ext`."""
        if self.kind not in MOMENT_KINDS:
            raise MethodIncompatibility(
                "This forest predicts through predict_survival() or "
                "predict_quantiles(), not predict()."
            )
        out: Tuple[np.ndarray, np.ndarray] = predict_moment_kernel(
            self.kind,
            self.params,
            X,
            rows,
            bool(oob),
            self.roots,
            self.node_offsets,
            self.split_var,
            self.split_val,
            self.left,
            self.right,
            self.leaf_values,
            self.leaf_nonempty,
            self.drawn_bitmap,
            self.ci_group_size,
            bool(estimate_variance),
        )
        return out

    def _weight_args(self) -> Tuple[Any, ...]:
        return (
            self.n_train,
            self.roots,
            self.node_offsets,
            self.split_var,
            self.split_val,
            self.left,
            self.right,
            self.leaf_offsets,
            self.leaf_offset_base,
            self.leaf_members,
            self.member_base,
            self.leaf_nonempty,
            self.drawn_bitmap,
        )

    def _rows_for(self, X: np.ndarray, oob: bool) -> np.ndarray:
        if oob and X.shape[0] != self.n_train:
            raise MethodIncompatibility(
                "out-of-bag prediction needs one row per training observation"
            )
        return np.arange(X.shape[0], dtype=np.int64)

    def predict_survival(
        self, X: np.ndarray, oob: bool = False, nelson_aalen: bool = False
    ) -> np.ndarray:
        """Survival curves ``(n_rows, n_failure_times)`` (survival kind).

        With ``oob=True`` row ``i`` of ``X`` is predicted from the trees that
        did not draw training observation ``i``; ``X`` may differ from the
        training matrix (e.g. a counterfactual treatment column), which is
        how cross-fitted counterfactual curves are obtained.
        """
        if self.kind != KIND_SURVIVAL:
            raise MethodIncompatibility("predict_survival() needs a survival forest")
        X = np.ascontiguousarray(X, dtype=np.float64)
        rows = self._rows_for(X, oob)
        curves: np.ndarray = predict_survival_kernel(
            X,
            rows,
            bool(oob),
            *self._weight_args(),
            self.aux["time_index"],
            self.aux["event"],
            self.aux["sample_weight"],
            int(self.aux["failure_times"].size),
            bool(nelson_aalen),
        )
        return curves

    def predict_quantiles(
        self, X: np.ndarray, quantiles: np.ndarray, oob: bool = False
    ) -> np.ndarray:
        """Conditional quantiles ``(n_rows, len(quantiles))``."""
        if self.kind != KIND_QUANTILE:
            raise MethodIncompatibility("predict_quantiles() needs a quantile forest")
        X = np.ascontiguousarray(X, dtype=np.float64)
        rows = self._rows_for(X, oob)
        quant: np.ndarray = predict_quantile_kernel(
            X,
            rows,
            bool(oob),
            *self._weight_args(),
            self.aux["y_order"],
            self.aux["y"],
            self.aux["sample_weight"],
            np.ascontiguousarray(quantiles, dtype=np.float64),
        )
        return quant

    def forest_weights(self, X: np.ndarray, oob: bool = False) -> np.ndarray:
        """Dense ``(n_rows, n_train)`` matrix of forest weights alpha_i(x)."""
        X = np.ascontiguousarray(X, dtype=np.float64)
        rows = np.arange(X.shape[0], dtype=np.int64)
        return _forest_weights_kernel(
            X,
            rows,
            bool(oob),
            self.n_train,
            self.roots,
            self.node_offsets,
            self.split_var,
            self.split_val,
            self.left,
            self.right,
            self.leaf_offsets,
            self.leaf_offset_base,
            self.leaf_members,
            self.member_base,
            self.leaf_nonempty,
            self.drawn_bitmap,
        )

    def split_frequencies(self, max_depth: int = 4) -> np.ndarray:
        """Counts of splits by (depth, variable)."""
        out = np.zeros((max_depth, self.n_features), dtype=np.int64)
        for t in range(self.num_trees):
            base = int(self.node_offsets[t])
            stack = [(int(self.roots[t]), 0)]
            while stack:
                node, d = stack.pop()
                g = base + node
                if self.left[g] == -1 or d >= max_depth:
                    continue
                out[d, int(self.split_var[g])] += 1
                stack.append((int(self.left[g]), d + 1))
                stack.append((int(self.right[g]), d + 1))
        return out


def _cluster_csr(
    clusters: Optional[np.ndarray], n: int
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Map arbitrary cluster labels to (codes, offsets, members) CSR arrays."""
    if clusters is None:
        codes = np.arange(n, dtype=np.int64)
        return codes, np.arange(n + 1, dtype=np.int64), np.arange(n, dtype=np.int64)
    _, codes = np.unique(np.asarray(clusters), return_inverse=True)
    codes = codes.astype(np.int64).ravel()
    order = np.argsort(codes, kind="mergesort").astype(np.int64)
    counts = np.bincount(codes)
    offsets = np.concatenate([[0], np.cumsum(counts)]).astype(np.int64)
    return codes, offsets, order


def default_mtry(p: int) -> int:
    """Default ``mtry = min(ceil(sqrt(p) + 20), p)`` (the grf default)."""
    return int(min(math.ceil(math.sqrt(p) + 20), p))


def train_forest(
    X: np.ndarray,
    Y: np.ndarray,
    W: Optional[np.ndarray] = None,
    *,
    kind: int,
    num_trees: int = 2000,
    sample_weight: Optional[np.ndarray] = None,
    clusters: Optional[np.ndarray] = None,
    equalize_cluster_weights: bool = False,
    sample_fraction: float = 0.5,
    mtry: Optional[int] = None,
    min_node_size: int = 5,
    honesty: bool = True,
    honesty_fraction: float = 0.5,
    honesty_prune_leaves: bool = True,
    alpha: float = 0.05,
    imbalance_penalty: float = 0.0,
    stabilize_splits: bool = True,
    ci_group_size: int = 2,
    max_depth: Optional[int] = None,
    seed: int = 0,
    n_jobs: int = 1,
    unit: Optional[np.ndarray] = None,
    time: Optional[np.ndarray] = None,
    fe_max_iter: int = 1000,
    fe_tol: float = 1e-10,
    tau_split: bool = False,
    M: Optional[np.ndarray] = None,
    params: Optional[np.ndarray] = None,
    aux: Optional[Dict[str, np.ndarray]] = None,
) -> GRFForest:
    """Train a regression (``kind=0``) or causal (``kind=1``) forest.

    The GRF family members of :mod:`._grf_ext` (``kind >= 3``) take their
    per-observation data in ``M`` and kind parameters in ``params`` (see
    that module); ``Y`` and ``W`` are then ignored.  ``aux`` stores arrays
    the prediction step needs (survival and quantile forests predict from
    the training outcomes).

    For a causal forest ``Y`` and ``W`` must already be centred by their
    nuisance predictions (``Y - Y.hat`` and ``W - W.hat``), as grf does
    before calling its C++ trainer.  ``kind=KIND_CAUSAL_FE`` additionally
    needs integer ``unit`` codes and (optionally) ``time`` codes; fixed
    effects are then removed within every node and every leaf.
    """
    X = np.ascontiguousarray(X, dtype=np.float64)
    n, p = X.shape
    Y = np.ascontiguousarray(Y, dtype=np.float64).ravel()
    W_arr = (
        np.zeros(n) if W is None else np.ascontiguousarray(W, dtype=np.float64).ravel()
    )
    G = (
        np.ones(n)
        if sample_weight is None
        else np.ascontiguousarray(sample_weight, dtype=np.float64).ravel()
    )
    if ci_group_size > 1 and sample_fraction > 0.5:
        raise MethodIncompatibility(
            "When confidence intervals are enabled (ci_group_size > 1), "
            "sample_fraction must be at most 0.5."
        )
    codes, cl_offsets, cl_members = _cluster_csr(clusters, n)
    if int(kind) == KIND_CAUSAL_FE:
        if unit is None:
            raise MethodIncompatibility("KIND_CAUSAL_FE requires unit codes")
        unit_codes = np.ascontiguousarray(unit, dtype=np.int64).ravel()
        time_codes = (
            np.zeros(n, dtype=np.int64)
            if time is None
            else np.ascontiguousarray(time, dtype=np.int64).ravel()
        )
        n_units = int(unit_codes.max()) + 1
        n_times = int(time_codes.max()) + 1
    else:
        unit_codes = np.zeros(1, dtype=np.int64)
        time_codes = np.zeros(1, dtype=np.int64)
        n_units = 1
        n_times = 1
    cluster_sizes = np.diff(cl_offsets)
    if clusters is None:
        samples_per_cluster = 1
    elif equalize_cluster_weights:
        samples_per_cluster = int(cluster_sizes.min())
    else:
        samples_per_cluster = int(cluster_sizes.max())
    n_clusters = int(cl_offsets.size - 1)
    if int(n_clusters * sample_fraction) < 1:
        raise DataInsufficient(
            "sample_fraction is too small: no clusters would be drawn per tree."
        )
    if honesty and int(math.ceil(n_clusters * sample_fraction * honesty_fraction)) < 1:
        raise DataInsufficient("honesty_fraction leaves no samples to grow trees on.")

    # num_trees is rounded to a multiple of ci_group_size.
    if int(kind) >= KIND_INSTRUMENTAL:
        if M is None or params is None:
            raise MethodIncompatibility(
                "train_forest(): GRF-family kinds need the data matrix M "
                "and the kind parameters."
            )
        M_arr = np.ascontiguousarray(M, dtype=np.float64)
        if M_arr.ndim != 2 or M_arr.shape[0] != n:
            raise MethodIncompatibility("train_forest(): M must be (n, m).")
        if not np.isfinite(M_arr).all():
            raise MethodIncompatibility("train_forest(): M has non-finite values.")
        params_arr = np.ascontiguousarray(params, dtype=np.float64).ravel()
        rho_width = int(rho_dim(int(kind), params_arr))
    else:
        M_arr = np.zeros((1, 1))
        params_arr = np.zeros(1)
        rho_width = 1

    L = int(ci_group_size)
    num_trees = int(num_trees) + (int(num_trees) % L)
    n_groups = num_trees // L
    mtry_value = default_mtry(p) if mtry is None else int(min(max(mtry, 1), p))
    depth_cap = 0 if max_depth is None else int(max_depth)

    # Independent per-group seeds derived from the user's seed.  (Seeding
    # group g with ``seed + g`` made forests for consecutive seeds share all
    # but one group of trees, and forests grown from one seed draw identical
    # subsamples group by group.)
    group_seeds = np.random.SeedSequence(int(seed) % (2**63)).generate_state(
        max(n_groups, 1), dtype=np.uint32
    )

    def _run(group: int) -> List[Tuple[Any, ...]]:
        return list(
            _train_group(
                X,
                Y,
                W_arr,
                G,
                int(kind),
                cl_offsets,
                cl_members,
                int(samples_per_cluster),
                float(sample_fraction),
                float(mtry_value),
                int(min_node_size),
                bool(honesty),
                float(honesty_fraction),
                bool(honesty_prune_leaves),
                float(alpha),
                float(imbalance_penalty),
                bool(stabilize_splits),
                L,
                depth_cap,
                int(group_seeds[group]),
                unit_codes,
                time_codes,
                n_units,
                n_times,
                int(fe_max_iter),
                float(fe_tol),
                bool(tau_split),
                M_arr,
                params_arr,
                rho_width,
            )
        )

    workers = _resolve_n_jobs(n_jobs)
    if workers == 1:
        groups = [_run(g) for g in range(n_groups)]
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            groups = list(pool.map(_run, range(n_groups)))
    trees = [tree for group in groups for tree in group]
    forest = _assemble(trees, int(kind), n, p, L, codes, locals())
    forest.params = params_arr
    forest.aux = dict(aux or {})
    return forest


def _resolve_n_jobs(n_jobs: Optional[int]) -> int:
    if n_jobs is None or n_jobs == 0:
        return 1
    if n_jobs < 0:
        return max(os.cpu_count() or 1, 1)
    return int(n_jobs)


def _assemble(
    trees: List[Tuple[Any, ...]],
    kind: int,
    n: int,
    p: int,
    L: int,
    codes: np.ndarray,
    scope: Dict[str, Any],
) -> GRFForest:
    n_trees = len(trees)
    node_counts = np.array([t[3].size for t in trees], dtype=np.int64)
    node_offsets = np.concatenate([[0], np.cumsum(node_counts)[:-1]]).astype(np.int64)
    member_counts = np.array([t[6].size for t in trees], dtype=np.int64)
    member_base = np.concatenate([[0], np.cumsum(member_counts)[:-1]]).astype(np.int64)
    # leaf_offsets per tree have node_count + 1 entries.
    leaf_offset_base = np.concatenate([[0], np.cumsum(node_counts + 1)[:-1]]).astype(
        np.int64
    )
    drawn_bitmap = np.zeros((n_trees, (n + 7) // 8), dtype=np.uint8)
    for t, tree in enumerate(trees):
        drawn = np.asarray(tree[9], dtype=np.int64)
        np.bitwise_or.at(
            drawn_bitmap[t], drawn >> 3, (1 << (drawn & 7)).astype(np.uint8)
        )
    options = {
        key: scope[key]
        for key in (
            "num_trees",
            "sample_fraction",
            "mtry_value",
            "min_node_size",
            "honesty",
            "honesty_fraction",
            "honesty_prune_leaves",
            "alpha",
            "imbalance_penalty",
            "stabilize_splits",
            "tau_split",
            "equalize_cluster_weights",
            "samples_per_cluster",
            "seed",
        )
        if key in scope
    }
    options["clustered"] = scope.get("clusters") is not None
    options["n_clusters"] = int(codes.max()) + 1 if codes.size else 0
    return GRFForest(
        kind=kind,
        n_train=n,
        n_features=p,
        ci_group_size=L,
        roots=np.array([t[0] for t in trees], dtype=np.int64),
        node_offsets=node_offsets,
        split_var=np.concatenate([t[1] for t in trees]),
        split_val=np.concatenate([t[2] for t in trees]),
        left=np.concatenate([t[3] for t in trees]),
        right=np.concatenate([t[4] for t in trees]),
        leaf_values=np.concatenate([t[7] for t in trees]),
        leaf_nonempty=np.concatenate([t[8] for t in trees]),
        leaf_offsets=np.concatenate([t[5] for t in trees]),
        leaf_offset_base=leaf_offset_base,
        leaf_members=np.concatenate([t[6] for t in trees]),
        member_base=member_base,
        drawn_bitmap=drawn_bitmap,
        options=options,
    )


# The GRF-family kinds (instrumental, multi-causal, multi-regression,
# quantile, survival, causal-survival) live in their own module; it imports
# helpers defined above, so it is bound here, after them.
from ._grf_ext import (  # noqa: E402,F401  (KIND_* are re-exported)
    KIND_CAUSAL_SURV,
    KIND_INSTRUMENTAL,
    KIND_MULTI_CAUSAL,
    KIND_MULTI_REG,
    KIND_QUANTILE,
    KIND_SURVIVAL,
    MOMENT_KINDS,
    leaf_values_ext,
    predict_moment_kernel,
    predict_quantile_kernel,
    predict_survival_kernel,
    relabel_and_split,
    rho_dim,
)
