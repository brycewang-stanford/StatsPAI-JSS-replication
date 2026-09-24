"""Write the simulated inputs of test_synth_rest_R_parity.py.

Run before ``_generate_synth_rest_R.R``. Deterministic (fixed seeds); the
CSVs are committed so the R and Python sides read identical bytes.

synth_rest_scm.csv
    One treated unit (``unit == 1``) and nine donors, 20 periods, treatment
    from period 15 (T0 = 14 > J = 9, so every simplex least-squares fit in
    the sensitivity tools has a unique solution). Two-factor model plus
    noise; the treated unit's loadings are a convex combination of three
    donors' loadings plus a perturbation, so its pre-fit is good but not
    exact. Effect 3 + 0.2 (t - 15) after treatment. Used by
    ``synth_loo`` / ``synth_time_placebo`` / ``synth_donor_sensitivity`` /
    ``synth_rmspe_filter`` / ``synth_sensitivity`` (vs ``Synth::synth`` +
    ``SCtools::mspe.test``) and ``conformal_synth`` (vs ``scinference``).

synth_rest_donor_subsets.csv
    The donor subsets ``sp.synth_donor_sensitivity(..., k=6, n_samples=5,
    seed=7)`` draws on ``synth_rest_scm.csv``, replayed with the same
    ``np.random.default_rng(7).choice(donors, size=6, replace=False)`` calls
    (the test re-checks the replay), so R can refit the same subsets.

synth_rest_multi.csv
    Three outcomes on very different scales (``gdp`` ~ 100, ``emp`` ~ 5,
    ``inv`` ~ 1000) for one treated unit and 11 donors, 16 periods,
    treatment from period 12 (T0 = 11). Used by ``multi_outcome_synth`` (vs
    ``augsynth::augsynth_multiout``).

synth_rest_stag.csv
    Staggered adoption: 20 units, 14 periods; units 1-3 adopt at period 6,
    units 4-6 at period 9, units 7-8 at period 12, units 9-20 never treated
    (``cohort == 0``). Used by ``sequential_sdid`` (per-cohort blocks vs
    ``synthdid::synthdid_estimate``).

synth_rest_ss_panel.csv / synth_rest_ss_shares.csv / synth_rest_ss_shocks.csv
    Shift-share panel: 40 units, 5 periods, 6 industries; time-invariant
    shares (rows sum to 1), time-varying shocks (``shocks.csv`` is time x
    industry), an endogenous ``x`` driven by the Bartik instrument plus a
    confounder, outcome ``y = 0.5 x + FE + confounder + noise``, and a
    pre-period covariate ``c1``. Used by ``shift_share_political`` (long
    difference first -> last period) and ``shift_share_political_panel``
    (vs ``AER::ivreg`` + ``sandwich``, ``fixest::feols``,
    ``ShiftShareSE::ivreg_ss``, ``bartik.weight::bw``).

synth_rest_ss_panel_unbal.csv
    The same panel with 7 unit-period rows removed, to exercise the
    two-way within transformation on an unbalanced panel (vs
    ``fixest::feols``).
"""

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).parent / "_fixtures"


def _scm() -> pd.DataFrame:
    rng = np.random.default_rng(20260918)
    n_units, n_periods, t0 = 10, 20, 14
    f = np.column_stack(
        [
            np.cumsum(rng.normal(0.4, 1.0, n_periods)),
            2.5 * np.sin(np.arange(n_periods) / 2.5),
        ]
    )
    load = rng.uniform(0.2, 2.0, (n_units, 2))
    level = rng.uniform(5.0, 15.0, n_units)
    # treated = 0.5 * donor2 + 0.3 * donor5 + 0.2 * donor8 (+ perturbation)
    mix = np.zeros(n_units)
    mix[[2, 5, 8]] = [0.5, 0.3, 0.2]
    load[0] = mix @ load + np.array([0.05, -0.04])
    level[0] = mix @ level + 0.3
    rows = []
    for i in range(n_units):
        for t in range(n_periods):
            y = level[i] + load[i] @ f[t] + rng.normal(0.0, 0.4)
            if i == 0 and t >= t0:
                y += 3.0 + 0.2 * (t - t0)
            rows.append({"unit": i + 1, "time": t + 1, "y": y})
    return pd.DataFrame(rows)


def _multi() -> pd.DataFrame:
    rng = np.random.default_rng(20260919)
    n_units, n_periods, t0 = 12, 16, 11
    f = np.column_stack(
        [np.cumsum(rng.normal(0.2, 1.0, n_periods)), np.cos(np.arange(n_periods) / 2.0)]
    )
    load = rng.uniform(0.3, 1.7, (n_units, 2))
    specs = {"gdp": (100.0, 4.0), "emp": (5.0, 0.3), "inv": (1000.0, 60.0)}
    effects = {"gdp": 6.0, "emp": 0.2, "inv": 0.0}
    rows = []
    lev = {k: rng.normal(0.0, 1.0, n_units) for k in specs}
    for i in range(n_units):
        for t in range(n_periods):
            row = {"unit": i + 1, "time": t + 1}
            for k, (mu, sc) in specs.items():
                y = mu + sc * (lev[k][i] + load[i] @ f[t] + rng.normal(0.0, 0.3))
                if i == 0 and t >= t0:
                    y += effects[k]
                row[k] = y
            row["treated"] = int(i == 0 and t >= t0)
            rows.append(row)
    return pd.DataFrame(rows)


def _stag() -> pd.DataFrame:
    rng = np.random.default_rng(20260920)
    n_units, n_periods = 20, 14
    cohort = np.zeros(n_units, dtype=int)
    cohort[0:3] = 6
    cohort[3:6] = 9
    cohort[6:8] = 12
    a = rng.normal(0.0, 1.0, n_units)
    b = rng.normal(0.0, 1.0, n_periods).cumsum()
    load = rng.uniform(0.5, 1.5, n_units)
    rows = []
    for i in range(n_units):
        for t in range(1, n_periods + 1):
            y = a[i] + load[i] * b[t - 1] + rng.normal(0.0, 0.3)
            if cohort[i] and t >= cohort[i]:
                y += 1.5 + 0.1 * (t - cohort[i])
            rows.append({"unit": i + 1, "time": t, "y": y, "cohort": int(cohort[i])})
    return pd.DataFrame(rows)


def _shift_share():
    rng = np.random.default_rng(20260921)
    n, T, K = 40, 5, 6
    inds = [f"k{j + 1}" for j in range(K)]
    shares = rng.dirichlet(np.full(K, 0.8), size=n)
    shocks = rng.normal(0.0, 1.0, (T, K))
    alpha_i = rng.normal(0.0, 1.0, n)
    gamma_t = rng.normal(0.0, 0.5, T)
    conf = rng.normal(0.0, 1.0, (n, T))
    c1 = rng.normal(0.0, 1.0, n) + 0.8 * shares[:, 0]
    rows = []
    for i in range(n):
        for t in range(T):
            z = float(shares[i] @ shocks[t])
            x = 0.7 * z + 0.5 * conf[i, t] + 0.3 * alpha_i[i] + rng.normal(0.0, 0.3)
            y = (
                0.5 * x
                + alpha_i[i]
                + gamma_t[t]
                + 0.6 * conf[i, t]
                + rng.normal(0.0, 0.3)
            )
            rows.append(
                {
                    "unit": i + 1,
                    "time": t + 1,
                    "y": y,
                    "x": x,
                    "c1": c1[i],
                    "w1": rng.normal(0.0, 1.0),
                }
            )
    panel = pd.DataFrame(rows)
    sh = pd.DataFrame(shares, columns=inds)
    sh.insert(0, "unit", np.arange(1, n + 1))
    sk = pd.DataFrame(shocks, columns=inds)
    sk.insert(0, "time", np.arange(1, T + 1))
    drop = rng.choice(len(panel), size=7, replace=False)
    unbal = panel.drop(index=drop).reset_index(drop=True)
    return panel, sh, sk, unbal


def _donor_subsets(scm: pd.DataFrame) -> pd.DataFrame:
    donors = [u for u in scm["unit"].unique() if u != 1]
    rng = np.random.default_rng(7)
    rows = []
    for i in range(5):
        sub = rng.choice(donors, size=6, replace=False)
        rows.append(
            {"iteration": i, "donors": ",".join(str(int(d)) for d in sorted(sub))}
        )
    return pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    fmt = "%.17g"
    scm = _scm()
    scm.to_csv(OUT / "synth_rest_scm.csv", index=False, float_format=fmt)
    _donor_subsets(scm).to_csv(OUT / "synth_rest_donor_subsets.csv", index=False)
    _multi().to_csv(OUT / "synth_rest_multi.csv", index=False, float_format=fmt)
    _stag().to_csv(OUT / "synth_rest_stag.csv", index=False, float_format=fmt)
    panel, sh, sk, unbal = _shift_share()
    panel.to_csv(OUT / "synth_rest_ss_panel.csv", index=False, float_format=fmt)
    sh.to_csv(OUT / "synth_rest_ss_shares.csv", index=False, float_format=fmt)
    sk.to_csv(OUT / "synth_rest_ss_shocks.csv", index=False, float_format=fmt)
    unbal.to_csv(OUT / "synth_rest_ss_panel_unbal.csv", index=False, float_format=fmt)


if __name__ == "__main__":
    main()
