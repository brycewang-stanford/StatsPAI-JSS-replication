"""Generalized-random-forest kernels beyond the scalar causal forest.

The core engine (:mod:`._grf_engine`) grows regression, causal and
FE-causal trees.  This module adds the remaining members of the GRF family
as further tree *kinds* that reuse the engine's sampling, honesty, pruning
and little-bag machinery unchanged; only the three kind-specific pieces
live here:

* relabeling + split search at a parent node,
* the per-leaf sufficient statistics,
* the forest-weighted local solve (and its little-bag variance) at
  prediction time.

Every kind reads its per-observation data from one float matrix ``M`` whose
columns depend on the kind:

=====================  ==============================  =====================
kind                   ``M`` columns                   estimand at ``x``
=====================  ==============================  =====================
``KIND_INSTRUMENTAL``  ``Y~, W~, Z~`` (centred)        Cov(Y,Z|x)/Cov(W,Z|x)
``KIND_MULTI_CAUSAL``  ``Y~_1..Y~_q, W~_1..W~_k``      h(x) in Y = c + W'h
``KIND_MULTI_REG``     ``Y_1..Y_q``                    E[Y | x] (vector)
``KIND_QUANTILE``      ``Y``                           conditional quantiles
``KIND_SURVIVAL``      ``time index, event``           S(t | x)
``KIND_CAUSAL_SURV``   ``A, B, W~, event``             sum a A / sum a B
=====================  ==============================  =====================

Splitting follows the GRF recipe (Athey, Tibshirani and Wager 2019,
Sec. 2.3): the parent's local estimating equation is solved, each sample
is relabeled with its gradient pseudo-outcome ``rho_i = xi' A_P^{-1}
psi_i``, and children maximise ``sum_c ||sum_{i in c} rho_i||^2 / n_c``.
The instrumental rule is ATW (2019, Sec. 5); the multi-outcome / multi-
regressor rule is their eq. (20) with the full coefficient vector as
target; the causal-survival rule is Cui, Kosorok, Sverdrup, Wager and Zhu
(2023, eq. 14); class-count ("probability") splitting serves quantile and
probability forests (ATW 2019, Sec. 3.3); survival trees split on the
two-sample log-rank statistic (Ishwaran, Kogalur, Blackstone and Lauer
2008), evaluated exactly with Fenwick trees in O(log T) per candidate.

Where the papers leave choices open the kernels follow the documented
behaviour of the R package ``grf`` (argument semantics of
``instrumental_forest``, ``multi_arm_causal_forest``, ``lm_forest``,
``probability_forest``, ``quantile_forest``, ``survival_forest`` and
``causal_survival_forest``).  No ``grf`` source code is used.

References
----------
[@athey2019generalized], [@cui2023estimating], [@ishwaran2008random]
"""

from __future__ import annotations

import math

import numpy as np

from ._grf_engine import _CACHE, _debias_variance, njit, prange

KIND_INSTRUMENTAL = 3
KIND_MULTI_CAUSAL = 4
KIND_MULTI_REG = 5
KIND_QUANTILE = 6
KIND_SURVIVAL = 7
KIND_CAUSAL_SURV = 8

EXT_KINDS = (
    KIND_INSTRUMENTAL,
    KIND_MULTI_CAUSAL,
    KIND_MULTI_REG,
    KIND_QUANTILE,
    KIND_SURVIVAL,
    KIND_CAUSAL_SURV,
)
# Kinds whose prediction is a forest-weighted local moment solve (with a
# little-bag variance); the other two predict from the forest weights.
MOMENT_KINDS = (KIND_INSTRUMENTAL, KIND_MULTI_CAUSAL, KIND_MULTI_REG, KIND_CAUSAL_SURV)


# --------------------------------------------------------------------------- #
#  Dimensions
# --------------------------------------------------------------------------- #


@njit(cache=_CACHE, nogil=True)
def rho_dim(kind, params):  # type: ignore[no-untyped-def]
    """Width of the pseudo-outcome vector for ``kind``."""
    if kind == KIND_MULTI_CAUSAL:
        return int(params[0]) * int(params[1])
    if kind == KIND_MULTI_REG:
        return int(params[0])
    if kind == KIND_QUANTILE:
        if params[0] > 0.5:  # regression splitting
            return 1
        return params.size  # len(quantiles) + 1 classes
    return 1


@njit(cache=_CACHE, nogil=True)
def n_leaf_stats(kind, params):  # type: ignore[no-untyped-def]
    if kind == KIND_INSTRUMENTAL:
        return 6
    if kind == KIND_MULTI_CAUSAL:
        q = int(params[0])
        k = int(params[1])
        return 1 + q + k + k * q + k * k
    if kind == KIND_MULTI_REG:
        return 1 + int(params[0])
    if kind == KIND_CAUSAL_SURV:
        return 3
    return 1  # quantile / survival: weight only (prediction uses members)


def n_outputs(kind: int, params: np.ndarray) -> int:
    """Number of estimated quantities per prediction row (moment kinds)."""
    if kind == KIND_MULTI_CAUSAL:
        return int(params[0]) * int(params[1])
    if kind == KIND_MULTI_REG:
        return int(params[0])
    return 1


# --------------------------------------------------------------------------- #
#  Relabeling
# --------------------------------------------------------------------------- #


@njit(cache=_CACHE, nogil=True)
def _relabel_instrumental(  # type: ignore[no-untyped-def]
    idx, M, G, rho, reduced_form_weight
):
    """IV gradient pseudo-outcome (ATW 2019, Sec. 5).

    ``rho_i = (Z_i - Z_bar)[(Y_i - Y_bar) - tau_P (W_i - W_bar)] / J_P`` with
    ``tau_P`` the node's local Wald estimate and ``J_P`` the node mean of
    ``(Z - Z_bar)(W - W_bar)``.  With ``reduced_form_weight = r > 0`` the
    label is ``(1 - r) rho_IV + r rho_CF``, where ``rho_CF`` is the causal-
    forest label that treats ``W`` as exogenous (grf's
    ``reduced.form.weight``).  Returns True when the node must stop.
    """
    sw = 0.0
    sy = 0.0
    swt = 0.0
    sz = 0.0
    for t in range(idx.size):
        j = idx[t]
        g = G[j]
        sw += g
        sy += g * M[j, 0]
        swt += g * M[j, 1]
        sz += g * M[j, 2]
    if abs(sw) <= 1e-16:
        return True
    ybar = sy / sw
    wbar = swt / sw
    zbar = sz / sw
    num = 0.0
    den = 0.0
    num_cf = 0.0
    den_cf = 0.0
    for t in range(idx.size):
        j = idx[t]
        g = G[j]
        dz = M[j, 2] - zbar
        dw = M[j, 1] - wbar
        dy = M[j, 0] - ybar
        num += g * dz * dy
        den += g * dz * dw
        num_cf += g * dw * dy
        den_cf += g * dw * dw
    if abs(den) < 1e-10:
        return True
    tau = num / den
    jac = den / sw
    use_cf = reduced_form_weight > 0.0
    if use_cf and abs(den_cf) < 1e-10:
        return True
    beta_cf = num_cf / den_cf if use_cf else 0.0
    jac_cf = den_cf / sw if use_cf else 1.0
    for t in range(idx.size):
        j = idx[t]
        dz = M[j, 2] - zbar
        dw = M[j, 1] - wbar
        dy = M[j, 0] - ybar
        r_iv = dz * (dy - tau * dw) / jac
        if use_cf:
            r_cf = dw * (dy - beta_cf * dw) / jac_cf
            rho[j, 0] = (1.0 - reduced_form_weight) * r_iv + reduced_form_weight * r_cf
        else:
            rho[j, 0] = r_iv
    return False


@njit(cache=_CACHE, nogil=True)
def _relabel_multi_causal(idx, M, G, rho, q, k):  # type: ignore[no-untyped-def]
    """Vector gradient pseudo-outcome for ``Y = c + W'h`` (ATW 2019, eq. 20).

    At the parent the local least-squares fit of the centred ``Y`` (``q``
    outcomes) on the centred ``W`` (``k`` regressors) gives ``h_P`` and the
    Jacobian ``A_P = W~'G W~ / sum G``; each sample's label is the
    flattened ``A_P^{-1} W~_i (Y~_i - W~_i' h_P)'`` (``k x q``).  Stops when
    ``W~'G W~`` is numerically singular.
    """
    sw = 0.0
    ybar = np.zeros(q)
    wbar = np.zeros(k)
    for t in range(idx.size):
        j = idx[t]
        g = G[j]
        sw += g
        for a in range(q):
            ybar[a] += g * M[j, a]
        for b in range(k):
            wbar[b] += g * M[j, q + b]
    if abs(sw) <= 1e-16:
        return True
    for a in range(q):
        ybar[a] /= sw
    for b in range(k):
        wbar[b] /= sw
    WW = np.zeros((k, k))
    WY = np.zeros((k, q))
    for t in range(idx.size):
        j = idx[t]
        g = G[j]
        for b in range(k):
            wb = M[j, q + b] - wbar[b]
            for c in range(k):
                WW[b, c] += g * wb * (M[j, q + c] - wbar[c])
            for a in range(q):
                WY[b, a] += g * wb * (M[j, a] - ybar[a])
    evals = np.linalg.eigvalsh(WW)
    if evals[0] < 1e-10:
        return True
    h = np.linalg.solve(WW, WY)  # k x q
    Ainv = np.linalg.inv(WW / sw)
    wt = np.zeros(k)
    grad = np.zeros(k)
    for t in range(idx.size):
        j = idx[t]
        for b in range(k):
            wt[b] = M[j, q + b] - wbar[b]
        for a in range(q):
            res = M[j, a] - ybar[a]
            for b in range(k):
                res -= wt[b] * h[b, a]
            for b in range(k):
                acc = 0.0
                for c in range(k):
                    acc += Ainv[b, c] * wt[c]
                grad[b] = acc * res
            for b in range(k):
                rho[j, b * q + a] = grad[b]
    return False


@njit(cache=_CACHE, nogil=True)
def _relabel_quantile(idx, M, rho, quantiles):  # type: ignore[no-untyped-def]
    """One-hot class of Y relative to the node's empirical quantiles."""
    m = idx.size
    ys = np.empty(m)
    for t in range(m):
        ys[t] = M[idx[t], 0]
    ys.sort()
    nq = quantiles.size
    cut = np.empty(nq)
    for a in range(nq):
        pos = int(math.ceil(quantiles[a] * m)) - 1
        if pos < 0:
            pos = 0
        if pos > m - 1:
            pos = m - 1
        cut[a] = ys[pos]
    for t in range(m):
        j = idx[t]
        y = M[j, 0]
        cls = 0
        for a in range(nq):
            if y > cut[a]:
                cls += 1
        for a in range(nq + 1):
            rho[j, a] = 0.0
        rho[j, cls] = 1.0
    # A node whose samples all fall in one class carries no split signal.
    first = -1
    for t in range(m):
        j = idx[t]
        cls = 0
        for a in range(nq + 1):
            if rho[j, a] > 0.5:
                cls = a
        if first == -1:
            first = cls
        elif cls != first:
            return False
    return True


@njit(cache=_CACHE, nogil=True)
def _relabel_causal_survival(idx, M, G, rho):  # type: ignore[no-untyped-def]
    """``rho_i = (A_i - tau_P B_i) / mean_P(B)`` (Cui et al. 2023, eq. 14)."""
    sw = 0.0
    sa = 0.0
    sb = 0.0
    for t in range(idx.size):
        j = idx[t]
        g = G[j]
        sw += g
        sa += g * M[j, 0]
        sb += g * M[j, 1]
    if abs(sw) <= 1e-16 or abs(sb) < 1e-10:
        return True
    tau = sa / sb
    jac = sb / sw
    for t in range(idx.size):
        j = idx[t]
        rho[j, 0] = (M[j, 0] - tau * M[j, 1]) / jac
    return False


# --------------------------------------------------------------------------- #
#  Split search
# --------------------------------------------------------------------------- #


@njit(cache=_CACHE, nogil=True)
def _split_vector(  # type: ignore[no-untyped-def]
    X,
    idx,
    rho,
    d,
    G,
    vars_,
    min_node_size,
    alpha,
    imbalance_penalty,
    S,
    s_cols,
    n_s,
    D,
    d_col,
):
    """Best split of a node on the vector response ``rho[:, :d]``.

    Criterion ``sum_c ||sum_{i in c} G_i rho_i||^2 / sum_{i in c} G_i``
    minus ``imbalance_penalty (1/size_L + 1/size_R)``.

    * ``n_s == 0``: unstabilised -- each child keeps at least
      ``max(ceil(alpha m), 1)`` rows (the regression-forest rule).
    * ``n_s > 0``: stabilised on the columns ``S[:, s_cols[0..n_s)]`` --
      for *each* such column, each child holds at least ``min_node_size``
      rows below and above the parent's mean of that column and at least
      ``alpha`` of the parent's weighted sum of squares of it (the causal-
      forest rule applied column by column).
    * ``d_col >= 0``: additionally each child holds at least
      ``max(1, alpha m)`` rows with ``D[:, d_col] == 1`` (failures).
    """
    m = idx.size
    sw = 0.0
    srho = np.zeros(d)
    for t in range(m):
        j = idx[t]
        g = G[j]
        sw += g
        for a in range(d):
            srho[a] += g * rho[j, a]
    # Stabilisation statistics.
    s_sum = np.zeros(max(n_s, 1))
    s_sq = np.zeros(max(n_s, 1))
    s_mean = np.zeros(max(n_s, 1))
    n_small = np.zeros(max(n_s, 1), dtype=np.int64)
    min_size = np.zeros(max(n_s, 1))
    for c in range(n_s):
        col = s_cols[c]
        a = 0.0
        b = 0.0
        for t in range(m):
            j = idx[t]
            a += G[j] * S[j, col]
            b += G[j] * S[j, col] * S[j, col]
        s_sum[c] = a
        s_sq[c] = b
        s_mean[c] = a / sw
        min_size[c] = (b - a * a / sw) * alpha
        cnt = 0
        for t in range(m):
            if S[idx[t], col] < s_mean[c]:
                cnt += 1
        n_small[c] = cnt
    n_fail = 0
    min_fail = 0.0
    if d_col >= 0:
        for t in range(m):
            if D[idx[t], d_col] > 0.5:
                n_fail += 1
        min_fail = max(1.0, alpha * m)
    min_rows = max(int(math.ceil(m * alpha)), 1)

    best_dec = 0.0
    best_var = -1
    best_val = 0.0
    xs = np.empty(m)
    lrho = np.zeros(d)
    l_sum = np.zeros(max(n_s, 1))
    l_sq = np.zeros(max(n_s, 1))
    l_small = np.zeros(max(n_s, 1), dtype=np.int64)
    for v_i in range(vars_.size):
        v = vars_[v_i]
        for t in range(m):
            xs[t] = X[idx[t], v]
        order = np.argsort(xs, kind="mergesort")
        lw = 0.0
        ln = 0
        lfail = 0
        for a in range(d):
            lrho[a] = 0.0
        for c in range(n_s):
            l_sum[c] = 0.0
            l_sq[c] = 0.0
            l_small[c] = 0
        for t in range(m - 1):
            j = idx[order[t]]
            g = G[j]
            lw += g
            ln += 1
            for a in range(d):
                lrho[a] += g * rho[j, a]
            for c in range(n_s):
                val = S[j, s_cols[c]]
                l_sum[c] += g * val
                l_sq[c] += g * val * val
                if val < s_mean[c]:
                    l_small[c] += 1
            if d_col >= 0 and D[j, d_col] > 0.5:
                lfail += 1
            if xs[order[t]] == xs[order[t + 1]]:
                continue  # not a bucket boundary
            rn = m - ln
            rw = sw - lw
            if lw <= 0.0 or rw <= 0.0:
                continue
            ok = True
            pen = 0.0
            if n_s == 0:
                if ln < min_rows:
                    continue
                if rn < min_rows:
                    break
                pen = imbalance_penalty * (1.0 / ln + 1.0 / rn)
            else:
                stop = False
                for c in range(n_s):
                    ls = l_small[c]
                    ll = ln - ls
                    rs = n_small[c] - ls
                    rl = rn - rs
                    if ls < min_node_size or ll < min_node_size:
                        ok = False
                        break
                    if rs < min_node_size or rl < min_node_size:
                        ok = False
                        stop = True
                        break
                    size_l = l_sq[c] - l_sum[c] * l_sum[c] / lw
                    rsum = s_sum[c] - l_sum[c]
                    size_r = (s_sq[c] - l_sq[c]) - rsum * rsum / rw
                    if size_l < min_size[c] or size_r < min_size[c]:
                        ok = False
                        break
                    if imbalance_penalty > 0.0:
                        if size_l == 0.0 or size_r == 0.0:
                            ok = False
                            break
                        pen += imbalance_penalty * (1.0 / size_l + 1.0 / size_r)
                if stop:
                    break
                if not ok:
                    continue
            if d_col >= 0:
                if lfail < min_fail or (n_fail - lfail) < min_fail:
                    continue
            dec = 0.0
            for a in range(d):
                ra = srho[a] - lrho[a]
                dec += lrho[a] * lrho[a] / lw + ra * ra / rw
            dec -= pen
            if dec > best_dec:
                best_dec = dec
                best_var = v
                best_val = xs[order[t]]
    return best_var >= 0, best_var, best_val


@njit(cache=_CACHE, nogil=True)
def _bit_add(tree, pos, val):  # type: ignore[no-untyped-def]
    i = pos + 1
    while i < tree.size:
        tree[i] += val
        i += i & (-i)


@njit(cache=_CACHE, nogil=True)
def _bit_sum(tree, pos):  # type: ignore[no-untyped-def]
    """Sum of entries ``0..pos`` (``pos < 0`` gives 0)."""
    s = 0.0
    i = pos + 1
    while i > 0:
        s += tree[i]
        i -= i & (-i)
    return s


@njit(cache=_CACHE, nogil=True)
def _split_logrank(X, idx, M, vars_, alpha):  # type: ignore[no-untyped-def]
    """Best split by the two-sample log-rank statistic ``U^2 / V``.

    ``M[:, 0]`` holds the (grid) time index and ``M[:, 1]`` the event
    indicator.  Each child must contain at least ``max(1, alpha m)``
    failures.  Sample weights are not used, as documented for grf's
    survival splitting.  The statistic is updated exactly as samples move
    left: with at-risk counts ``Y_k``, failures ``d_k``, hazard increments
    ``d_k / Y_k`` and variance weights ``c_k = d_k (Y_k - d_k) / (Y_k
    (Y_k - 1))``, adding a sample with time rank ``r`` changes ``U`` by
    ``event - H_r`` and ``V = sum c Y_L - sum (c / Y) Y_L^2`` through
    prefix sums kept in two Fenwick trees.
    """
    m = idx.size
    # Compress the node's time indices to ranks 0..T-1.
    times = np.empty(m)
    for t in range(m):
        times[t] = M[idx[t], 0]
    order_t = np.argsort(times, kind="mergesort")
    rank = np.empty(m, dtype=np.int64)
    T = 0
    prev = -1.0
    for t in range(m):
        val = times[order_t[t]]
        if t == 0 or val != prev:
            T += 1
            prev = val
        rank[order_t[t]] = T - 1
    d_k = np.zeros(T)
    n_k = np.zeros(T)
    n_fail = 0
    for t in range(m):
        r = rank[t]
        n_k[r] += 1.0
        if M[idx[t], 1] > 0.5:
            d_k[r] += 1.0
            n_fail += 1
    min_fail = max(1.0, alpha * m)
    if n_fail < 2.0 * min_fail:
        return False, -1, 0.0
    Y_k = np.zeros(T)
    acc = 0.0
    for r in range(T - 1, -1, -1):
        acc += n_k[r]
        Y_k[r] = acc
    H = np.zeros(T)  # prefix sums of d/Y
    C = np.zeros(T)  # prefix sums of c
    Gp = np.zeros(T)  # prefix sums of c / Y
    h_acc = 0.0
    c_acc = 0.0
    g_acc = 0.0
    for r in range(T):
        if Y_k[r] > 0:
            h_acc += d_k[r] / Y_k[r]
        if Y_k[r] > 1:
            c = d_k[r] * (Y_k[r] - d_k[r]) / (Y_k[r] * (Y_k[r] - 1.0))
            c_acc += c
            g_acc += c / Y_k[r]
        H[r] = h_acc
        C[r] = c_acc
        Gp[r] = g_acc

    best_stat = 0.0
    best_var = -1
    best_val = 0.0
    xs = np.empty(m)
    bitG = np.zeros(T + 1)
    bitN = np.zeros(T + 1)
    for v_i in range(vars_.size):
        v = vars_[v_i]
        for t in range(m):
            xs[t] = X[idx[t], v]
        order = np.argsort(xs, kind="mergesort")
        for r in range(T + 1):
            bitG[r] = 0.0
            bitN[r] = 0.0
        U = 0.0
        S1 = 0.0
        S2 = 0.0
        nl = 0.0
        lfail = 0
        for t in range(m - 1):
            o = order[t]
            r = rank[o]
            ev = M[idx[o], 1] > 0.5
            # Q = sum_{k <= r} g_k Y_L,k before the move.
            Q = _bit_sum(bitG, r - 1) + Gp[r] * (nl - _bit_sum(bitN, r - 1))
            U += (1.0 if ev else 0.0) - H[r]
            S1 += C[r]
            S2 += 2.0 * Q + Gp[r]
            _bit_add(bitG, r, Gp[r])
            _bit_add(bitN, r, 1.0)
            nl += 1.0
            if ev:
                lfail += 1
            if xs[o] == xs[order[t + 1]]:
                continue
            if lfail < min_fail:
                continue
            if n_fail - lfail < min_fail:
                break
            V = S1 - S2
            if V <= 1e-12:
                continue
            stat = U * U / V
            if stat > best_stat:
                best_stat = stat
                best_var = v
                best_val = xs[o]
    return best_var >= 0, best_var, best_val


@njit(cache=_CACHE, nogil=True)
def relabel_and_split(  # type: ignore[no-untyped-def]
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
    rho,
):
    """Kind dispatch used by ``_grf_engine._grow_tree``; returns
    ``(found, var, value)`` (``found`` is False when the node must stop).

    Stabilised splits constrain the instrument (``M[:, 2]``) for IV trees,
    every regressor column for multi-causal trees and the centred
    treatment (``M[:, 2]``) plus the failure count (``M[:, 3]``) for
    causal-survival trees.
    """
    empty_cols = np.zeros(0, dtype=np.int64)
    s_cols = np.full(1, 2, dtype=np.int64)
    if kind == KIND_SURVIVAL:
        return _split_logrank(X, idx, M, vars_, alpha)
    if kind == KIND_INSTRUMENTAL:
        if _relabel_instrumental(idx, M, G, rho, params[0]):
            return False, -1, 0.0
        if stabilize_splits:
            return _split_vector(
                X,
                idx,
                rho,
                1,
                G,
                vars_,
                min_node_size,
                alpha,
                imbalance_penalty,
                M,
                s_cols,
                1,
                M,
                -1,
            )
        return _split_vector(
            X,
            idx,
            rho,
            1,
            G,
            vars_,
            min_node_size,
            alpha,
            imbalance_penalty,
            M,
            empty_cols,
            0,
            M,
            -1,
        )
    if kind == KIND_MULTI_CAUSAL:
        q = int(params[0])
        k = int(params[1])
        if _relabel_multi_causal(idx, M, G, rho, q, k):
            return False, -1, 0.0
        n_s = k if stabilize_splits else 0
        w_cols = np.arange(q, q + k).astype(np.int64)
        return _split_vector(
            X,
            idx,
            rho,
            q * k,
            G,
            vars_,
            min_node_size,
            alpha,
            imbalance_penalty,
            M,
            w_cols,
            n_s,
            M,
            -1,
        )
    if kind == KIND_MULTI_REG:
        q = int(params[0])
        for t in range(idx.size):
            j = idx[t]
            for a in range(q):
                rho[j, a] = M[j, a]
        return _split_vector(
            X,
            idx,
            rho,
            q,
            G,
            vars_,
            min_node_size,
            alpha,
            imbalance_penalty,
            M,
            empty_cols,
            0,
            M,
            -1,
        )
    if kind == KIND_QUANTILE:
        if params[0] > 0.5:
            for t in range(idx.size):
                rho[idx[t], 0] = M[idx[t], 0]
            return _split_vector(
                X,
                idx,
                rho,
                1,
                G,
                vars_,
                min_node_size,
                alpha,
                imbalance_penalty,
                M,
                empty_cols,
                0,
                M,
                -1,
            )
        if _relabel_quantile(idx, M, rho, params[1:]):
            return False, -1, 0.0
        return _split_vector(
            X,
            idx,
            rho,
            params.size,
            G,
            vars_,
            min_node_size,
            alpha,
            imbalance_penalty,
            M,
            empty_cols,
            0,
            M,
            -1,
        )
    # KIND_CAUSAL_SURV
    if _relabel_causal_survival(idx, M, G, rho):
        return False, -1, 0.0
    if stabilize_splits:
        return _split_vector(
            X,
            idx,
            rho,
            1,
            G,
            vars_,
            min_node_size,
            alpha,
            imbalance_penalty,
            M,
            s_cols,
            1,
            M,
            3,
        )
    return _split_vector(
        X,
        idx,
        rho,
        1,
        G,
        vars_,
        min_node_size,
        alpha,
        imbalance_penalty,
        M,
        empty_cols,
        0,
        M,
        3,
    )


# --------------------------------------------------------------------------- #
#  Leaf statistics
# --------------------------------------------------------------------------- #


@njit(cache=_CACHE, nogil=True)
def _add_obs_stats(kind, M, j, g, q, kw, out):  # type: ignore[no-untyped-def]
    """Add observation ``j``'s (weight-``g``) moment statistics to ``out``.

    Layout: ``[g, ...]`` with ``IV: gY, gW, gZ, gZY, gZW``; multi-causal:
    ``gY_a, gW_b, gW_bY_a, gW_bW_c``; multi-regression: ``gY_a``;
    causal-survival: ``gA, gB``.  A forest-averaged leaf statistic is the
    forest-weighted sum of these, ``sum_i alpha_i(x) stats_i``.
    """
    out[0] += g
    if kind == KIND_INSTRUMENTAL:
        y = M[j, 0]
        w = M[j, 1]
        z = M[j, 2]
        out[1] += g * y
        out[2] += g * w
        out[3] += g * z
        out[4] += g * z * y
        out[5] += g * z * w
    elif kind == KIND_MULTI_CAUSAL:
        for aa in range(q):
            out[1 + aa] += g * M[j, aa]
        for bb in range(kw):
            wb = M[j, q + bb]
            out[1 + q + bb] += g * wb
            for aa in range(q):
                out[1 + q + kw + bb * q + aa] += g * wb * M[j, aa]
            for cc in range(kw):
                out[1 + q + kw + kw * q + bb * kw + cc] += g * wb * M[j, q + cc]
    elif kind == KIND_MULTI_REG:
        for aa in range(q):
            out[1 + aa] += g * M[j, aa]
    elif kind == KIND_CAUSAL_SURV:
        out[1] += g * M[j, 0]
        out[2] += g * M[j, 1]


@njit(cache=_CACHE, nogil=True)
def _dims(kind, params):  # type: ignore[no-untyped-def]
    q = 1
    kw = 1
    if kind == KIND_MULTI_CAUSAL:
        q = int(params[0])
        kw = int(params[1])
    elif kind == KIND_MULTI_REG:
        q = int(params[0])
    return q, kw


@njit(cache=_CACHE, nogil=True)
def leaf_values_ext(  # type: ignore[no-untyped-def]
    kind, leaf_offsets, leaf_members, M, G, params
):
    """Per-leaf sufficient statistics, each divided by the leaf's sample
    count (the convention of the core engine)."""
    n_nodes = leaf_offsets.size - 1
    k_stats = n_leaf_stats(kind, params)
    vals = np.zeros((n_nodes, k_stats))
    nonempty = np.zeros(n_nodes, dtype=np.bool_)
    q, kw = _dims(kind, params)
    for node in range(n_nodes):
        a = leaf_offsets[node]
        b = leaf_offsets[node + 1]
        c = b - a
        if c == 0:
            continue
        acc = np.zeros(k_stats)
        for t in range(a, b):
            j = leaf_members[t]
            _add_obs_stats(kind, M, j, G[j], q, kw, acc)
        if abs(acc[0]) <= 1e-16:
            continue
        for st in range(k_stats):
            vals[node, st] = acc[st] / c
        nonempty[node] = True
    return vals, nonempty


@njit(cache=_CACHE, nogil=True)
def obs_stats_matrix(kind, M, G, params):  # type: ignore[no-untyped-def]
    """``(n, k_stats)`` per-observation statistics (for weight-based solves)."""
    n = M.shape[0]
    k_stats = n_leaf_stats(kind, params)
    q, kw = _dims(kind, params)
    out = np.zeros((n, k_stats))
    for j in range(n):
        _add_obs_stats(kind, M, j, G[j], q, kw, out[j])
    return out


# --------------------------------------------------------------------------- #
#  Prediction: forest-weighted local moment solves
# --------------------------------------------------------------------------- #


@njit(cache=_CACHE, nogil=True)
def _local_system(kind, s, q, kw):  # type: ignore[no-untyped-def]
    """Moment system ``J theta = r`` from averaged leaf statistics ``s``.

    Returns ``(J, r)`` with ``theta`` = (intercept(s), coefficients)
    stacked as rows; columns index outcomes.
    """
    if kind == KIND_INSTRUMENTAL:
        # E_a[(1, Z)'(Y - c - W tau)] = 0
        J = np.empty((2, 2))
        r = np.empty((2, 1))
        J[0, 0] = s[0]
        J[0, 1] = s[2]
        J[1, 0] = s[3]
        J[1, 1] = s[5]
        r[0, 0] = s[1]
        r[1, 0] = s[4]
        return J, r
    if kind == KIND_MULTI_CAUSAL:
        # E_a[(1, W)'(Y - c - W'h)] = 0
        J = np.empty((kw + 1, kw + 1))
        r = np.empty((kw + 1, q))
        J[0, 0] = s[0]
        for b in range(kw):
            J[0, 1 + b] = s[1 + q + b]
            J[1 + b, 0] = s[1 + q + b]
            for c in range(kw):
                J[1 + b, 1 + c] = s[1 + q + kw + kw * q + b * kw + c]
        for a in range(q):
            r[0, a] = s[1 + a]
            for b in range(kw):
                r[1 + b, a] = s[1 + q + kw + b * q + a]
        return J, r
    if kind == KIND_MULTI_REG:
        J = np.empty((1, 1))
        r = np.empty((1, q))
        J[0, 0] = s[0]
        for a in range(q):
            r[0, a] = s[1 + a]
        return J, r
    # KIND_CAUSAL_SURV: E_a[A - B tau] = 0
    J = np.empty((1, 1))
    r = np.empty((1, 1))
    J[0, 0] = s[2]
    r[0, 0] = s[1]
    return J, r


@njit(cache=_CACHE, nogil=True)
def _n_out_first(kind, q, kw):  # type: ignore[no-untyped-def]
    if kind == KIND_MULTI_CAUSAL:
        return q * kw, 1
    if kind == KIND_MULTI_REG:
        return q, 0
    if kind == KIND_INSTRUMENTAL:
        return 1, 1
    return 1, 0


@njit(cache=_CACHE, nogil=True)
def _pick(kind, mat, o, q, first):  # type: ignore[no-untyped-def]
    """Entry of a stacked (intercepts; coefficients) matrix for output ``o``."""
    if kind == KIND_MULTI_CAUSAL:
        return mat[1 + o // q, o % q]
    if kind == KIND_MULTI_REG:
        return mat[0, o]
    return mat[first, 0]


@njit(cache=_CACHE, nogil=True)
def solve_local(kind, s, q, kw):  # type: ignore[no-untyped-def]
    """Solve ``J theta = r`` built from averaged statistics ``s``.

    Returns ``(ok, Jinv, theta)``; ``ok`` is False for a singular system.
    """
    J, rhs = _local_system(kind, s, q, kw)
    dim = J.shape[0]
    if dim == 1:
        if abs(J[0, 0]) < 1e-14:
            return False, np.zeros((1, 1)), np.zeros(rhs.shape)
    elif abs(np.linalg.det(J)) < 1e-14 * max(1.0, abs(J[0, 0])) ** dim:
        return False, np.zeros((dim, dim)), np.zeros(rhs.shape)
    Jinv = np.linalg.inv(J)
    return True, Jinv, Jinv @ rhs


def weighted_solve(
    kind: int, alpha: np.ndarray, M: np.ndarray, G: np.ndarray, params: np.ndarray
) -> np.ndarray:
    """Estimates at target points from explicit forest weights.

    ``alpha`` is ``(n_targets, n)``; the result is ``(n_targets, n_outputs)``
    -- the same local solve the prediction kernel applies to averaged leaf
    statistics, since those equal ``alpha @ obs_stats``.
    """
    stats = obs_stats_matrix(
        int(kind),
        np.ascontiguousarray(M, dtype=np.float64),
        np.ascontiguousarray(G, dtype=np.float64),
        np.ascontiguousarray(params, dtype=np.float64),
    )
    S = np.asarray(alpha, dtype=float) @ stats
    q, kw = _dims(int(kind), np.asarray(params, dtype=np.float64))
    n_out, first = _n_out_first(int(kind), q, kw)
    out = np.full((S.shape[0], n_out), np.nan)
    for r in range(S.shape[0]):
        ok, _, theta = solve_local(int(kind), np.ascontiguousarray(S[r]), q, kw)
        if ok:
            for o in range(n_out):
                out[r, o] = _pick(int(kind), theta, o, q, first)
    return out


@njit(cache=_CACHE, parallel=True)
def predict_moment_kernel(  # type: ignore[no-untyped-def]
    kind,
    params,
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
):
    """Point estimates and little-bag variances for the moment kinds.

    The estimate solves the forest-averaged moment system ``J theta = r``;
    per tree ``b`` the moment residual ``psi_b = r_b - J_b theta`` is mapped
    through ``J^{-1}`` to the influence of that tree on the target rows of
    ``theta`` (ATW 2019, Sec. 4), whose between-bag and within-bag spread
    gives the debiased variance, as in the core engine.
    """
    n_rows = rows.size
    n_trees = roots.size
    k_stats = leaf_values.shape[1]
    q, kw = _dims(kind, params)
    n_out, first = _n_out_first(kind, q, kw)
    pred = np.full((n_rows, n_out), np.nan)
    var = np.full((n_rows, n_out), np.nan)
    L = ci_group_size
    n_groups = n_trees // L
    for r_i in prange(n_rows):
        row = rows[r_i]
        avg = np.zeros(k_stats)
        per_tree = np.zeros((n_trees, k_stats))
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
                if X[r_i, split_var[base + node]] <= split_val[base + node]:
                    node = left[base + node]
                else:
                    node = right[base + node]
            g = base + node
            if not leaf_nonempty[g]:
                continue
            valid[t] = True
            count += 1
            for s in range(k_stats):
                avg[s] += leaf_values[g, s]
                per_tree[t, s] = leaf_values[g, s]
        if count == 0:
            continue
        for s in range(k_stats):
            avg[s] /= count
        ok, Jinv, theta = solve_local(kind, avg, q, kw)
        if not ok:
            continue
        for o in range(n_out):
            pred[r_i, o] = _pick(kind, theta, o, q, first)
        if not (estimate_variance and L > 1):
            continue
        rho_sq = np.zeros(n_out)
        rho_grouped_sq = np.zeros(n_out)
        group_rho = np.zeros(n_out)
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
            for o in range(n_out):
                group_rho[o] = 0.0
            for j in range(L):
                t = grp * L + j
                Jb, rb = _local_system(kind, per_tree[t], q, kw)
                psi = rb - Jb @ theta
                infl = Jinv @ psi
                for o in range(n_out):
                    val = _pick(kind, infl, o, q, first)
                    rho_sq[o] += val * val
                    group_rho[o] += val
            for o in range(n_out):
                rho_grouped_sq[o] += (group_rho[o] / L) ** 2
        if good > 0:
            for o in range(n_out):
                var_between = rho_grouped_sq[o] / good
                var_total = rho_sq[o] / (good * L)
                group_noise = (var_total - var_between) / (L - 1)
                var[r_i, o] = _debias_variance(var_between, group_noise, good)
    return pred, var


# --------------------------------------------------------------------------- #
#  Prediction from forest weights (survival, quantile)
# --------------------------------------------------------------------------- #


@njit(cache=_CACHE, nogil=True)
def _row_weights(  # type: ignore[no-untyped-def]
    X,
    r_i,
    row,
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
    out,
):
    """Fill ``out`` (length n_train) with the forest weights of one row."""
    for j in range(n_train):
        out[j] = 0.0
    n_trees = roots.size
    count = 0
    for t in range(n_trees):
        if oob:
            byte = drawn_bitmap[t, row >> 3]
            if (byte >> (row & 7)) & 1:
                continue
        base = node_offsets[t]
        node = roots[t]
        while left[base + node] != -1:
            if X[r_i, split_var[base + node]] <= split_val[base + node]:
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
        for s in range(a, b):
            out[leaf_members[s]] += 1.0 / size
    if count > 0:
        for j in range(n_train):
            out[j] /= count
    return count


@njit(cache=_CACHE, nogil=True)
def km_curve_row(  # type: ignore[no-untyped-def]
    alpha, time_index, event, sample_weight, n_times, nelson_aalen, out
):
    """Forest-weighted Kaplan-Meier / Nelson-Aalen curve on grid 1..n_times.

    ``time_index[i]`` in ``0..n_times`` counts grid failure times at or below
    ``Y_i``; ``d_l`` is the weighted failure mass at grid point ``l`` and
    ``Y_l`` the weighted mass with ``time_index >= l``.
    """
    n_train = alpha.size
    d = np.zeros(n_times + 1)
    at = np.zeros(n_times + 2)
    for j in range(n_train):
        a = alpha[j]
        if a == 0.0:
            continue
        w = a * sample_weight[j]
        k = time_index[j]
        at[k] += w
        if event[j] > 0.5:
            d[k] += w
    acc = 0.0
    for k in range(n_times, -1, -1):
        acc += at[k]
        at[k] = acc
    s = 1.0
    cum = 0.0
    for k in range(1, n_times + 1):
        if at[k] > 0.0:
            if nelson_aalen:
                cum += d[k] / at[k]
                s = math.exp(-cum)
            else:
                s *= 1.0 - d[k] / at[k]
        out[k - 1] = s


@njit(cache=_CACHE, nogil=True)
def weighted_quantiles_row(  # type: ignore[no-untyped-def]
    alpha, y_sorted_order, y_train, sample_weight, quantiles, out
):
    """Smallest training ``y`` whose cumulative forest weight reaches ``q``."""
    n_train = alpha.size
    total = 0.0
    for j in range(n_train):
        total += alpha[j] * sample_weight[j]
    if total <= 0.0:
        return
    for a in range(quantiles.size):
        target = quantiles[a] * total
        acc = 0.0
        val = np.nan
        last = np.nan
        for s in range(n_train):
            j = y_sorted_order[s]
            w = alpha[j] * sample_weight[j]
            if w == 0.0:
                continue
            acc += w
            last = y_train[j]
            if acc >= target - 1e-12 * total:
                val = y_train[j]
                break
        out[a] = val if not math.isnan(val) else last


def km_from_weights(
    alpha: np.ndarray,
    time_index: np.ndarray,
    event: np.ndarray,
    sample_weight: np.ndarray,
    n_times: int,
    nelson_aalen: bool = False,
) -> np.ndarray:
    """Survival curves ``(n_targets, n_times)`` from explicit forest weights."""
    A = np.atleast_2d(np.asarray(alpha, dtype=float))
    out = np.full((A.shape[0], int(n_times)), np.nan)
    ti = np.ascontiguousarray(time_index, dtype=np.int64)
    ev = np.ascontiguousarray(event, dtype=np.float64)
    sw = np.ascontiguousarray(sample_weight, dtype=np.float64)
    for r in range(A.shape[0]):
        if A[r].sum() > 0:
            km_curve_row(
                np.ascontiguousarray(A[r]),
                ti,
                ev,
                sw,
                int(n_times),
                bool(nelson_aalen),
                out[r],
            )
    return out


def quantiles_from_weights(
    alpha: np.ndarray,
    y: np.ndarray,
    quantiles: np.ndarray,
    sample_weight: np.ndarray = None,  # type: ignore[assignment]
) -> np.ndarray:
    """Forest-weighted quantiles ``(n_targets, len(quantiles))``."""
    A = np.atleast_2d(np.asarray(alpha, dtype=float))
    y = np.ascontiguousarray(y, dtype=np.float64)
    order = np.argsort(y, kind="mergesort").astype(np.int64)
    sw = np.ones(y.size) if sample_weight is None else np.asarray(sample_weight, float)
    q = np.ascontiguousarray(quantiles, dtype=np.float64)
    out = np.full((A.shape[0], q.size), np.nan)
    for r in range(A.shape[0]):
        weighted_quantiles_row(np.ascontiguousarray(A[r]), order, y, sw, q, out[r])
    return out


@njit(cache=_CACHE, parallel=True)
def predict_survival_kernel(  # type: ignore[no-untyped-def]
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
    time_index,
    event,
    sample_weight,
    n_times,
    nelson_aalen,
):
    """Forest-weighted survival curves for each row (see ``km_curve_row``)."""
    n_rows = rows.size
    out = np.full((n_rows, n_times), np.nan)
    for r_i in prange(n_rows):
        alpha = np.zeros(n_train)
        cnt = _row_weights(
            X,
            r_i,
            rows[r_i],
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
            alpha,
        )
        if cnt == 0:
            continue
        km_curve_row(
            alpha,
            time_index,
            event,
            sample_weight,
            n_times,
            nelson_aalen,
            out[r_i],
        )
    return out


@njit(cache=_CACHE, parallel=True)
def predict_quantile_kernel(  # type: ignore[no-untyped-def]
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
    y_sorted_order,
    y_train,
    sample_weight,
    quantiles,
):
    """Weighted quantiles of the training outcomes under the forest weights
    (Meinshausen 2006); see ``weighted_quantiles_row``."""
    n_rows = rows.size
    out = np.full((n_rows, quantiles.size), np.nan)
    for r_i in prange(n_rows):
        alpha = np.zeros(n_train)
        cnt = _row_weights(
            X,
            r_i,
            rows[r_i],
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
            alpha,
        )
        if cnt == 0:
            continue
        weighted_quantiles_row(
            alpha, y_sorted_order, y_train, sample_weight, quantiles, out[r_i]
        )
    return out
