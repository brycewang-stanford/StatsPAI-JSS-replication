"""Write the shared data for the round-2 ``misc_sens`` parity family.

Run once; the CSVs are committed so the R generator
(``_generate_misc_sens_R.R``), the Stata generator
(``_generate_misc_sens_stata.do``) and the Python tests
(``test_misc_sens_R_parity.py`` / ``test_misc_sens_stata_parity.py``) all
read identical bytes.

Files (all ``%.17g`` so nothing is lost on the round trip)
---------------------------------------------------------
misc_sens_mi.csv        n = 200 with missing values (MI pooling).
    x1 ~ N(0, 1); x2 = 0.5 x1 + N(0, 1); x3 ~ Bernoulli(0.4)
    y  = 1 + x1 + 0.5 x2 - 0.7 x3 + N(0, 1)
    x2 missing w.p. expit(-1.5 + 0.8 x1)  (MAR on x1);  y missing w.p. 0.1.
    The imputed datasets themselves are written by the R generator
    (``misc_sens_mi_imputed.csv``, mice with a fixed seed): pooling is the
    deterministic step, so every side pools the same m completed datasets.

misc_sens_med.csv       n = 300, mediation (medsens).
    x1, x2 ~ N(0, 1); t ~ Bernoulli(0.5)
    m = 0.5 + 0.6 t + 0.3 x1 + N(0, 1)
    y = 1 + 0.4 t + 0.5 m + 0.2 x2 + 0.3 x1 + N(0, 1)

misc_sens_ovb.csv       n = 400, sensemakr / E-value / subgroup / ANCOVA.
    x1, x2 ~ N(0, 1); x3 ~ Bernoulli(0.5); g3 in {1, 2, 3}
    d  = 0.5 x1 + 0.3 x2 + N(0, 1)       continuous treatment (sensemakr)
    y  = 1 + 0.4 d + 0.6 x1 + 0.3 x2 - 0.2 x3 + 0.3 d x3 + N(0, 1)
    grp ~ Bernoulli(expit(0.5 x1)); pre = 2 + 0.5 x1 + N(0, 1)
    post = 1 + 0.6 grp + 0.7 pre + 0.2 x2 + N(0, 1)
    region in {"a", "b", "c"} (string); cl in 1..40 (cluster id)

misc_sens_attr.csv      n = 500, RCT with differential attrition.
    treat ~ Bernoulli(0.5); age ~ N(40, 10); inc ~ N(50, 15)
    obs ~ Bernoulli(0.85 treat + 0.70 (1 - treat))
    y = 10 + 1.5 treat + 0.05 age + N(0, 2) if obs else missing
    b1 ~ N(0, 1); b2 ~ Bernoulli(0.3); b3 ~ Exp(1)   balance covariates

misc_sens_src.csv / misc_sens_tgt.csv   transport (IOSW).
    source n = 400: x1 ~ N(0, 1), x2 ~ Bernoulli(0.4), a ~ Bernoulli(0.5),
    y = 1 + a + 0.5 x1 + 0.5 a x1 + 0.3 x2 + N(0, 1)
    target n = 600: x1 ~ N(0.5, 1), x2 ~ Bernoulli(0.6)
"""

from __future__ import annotations

import pathlib

import numpy as np
import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent


def _expit(v):
    return 1.0 / (1.0 + np.exp(-v))


def _write(df: pd.DataFrame, name: str) -> None:
    df.to_csv(HERE / name, index=False, float_format="%.17g")


def main() -> None:
    rng = np.random.default_rng(20260918)

    # ---------------- MI ----------------
    n = 200
    x1 = rng.normal(size=n)
    x2 = 0.5 * x1 + rng.normal(size=n)
    x3 = (rng.random(n) < 0.4).astype(int)
    y = 1 + x1 + 0.5 * x2 - 0.7 * x3 + rng.normal(size=n)
    x2m = np.where(rng.random(n) < _expit(-1.5 + 0.8 * x1), np.nan, x2)
    ym = np.where(rng.random(n) < 0.1, np.nan, y)
    _write(pd.DataFrame({"y": ym, "x1": x1, "x2": x2m, "x3": x3}), "misc_sens_mi.csv")

    # ---------------- mediation ----------------
    n = 300
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    t = (rng.random(n) < 0.5).astype(int)
    m = 0.5 + 0.6 * t + 0.3 * x1 + rng.normal(size=n)
    y = 1 + 0.4 * t + 0.5 * m + 0.2 * x2 + 0.3 * x1 + rng.normal(size=n)
    _write(
        pd.DataFrame({"y": y, "t": t, "m": m, "x1": x1, "x2": x2}),
        "misc_sens_med.csv",
    )

    # ---------------- OVB / subgroup / ANCOVA ----------------
    n = 400
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    x3 = (rng.random(n) < 0.5).astype(int)
    g3 = rng.integers(1, 4, size=n)
    d = 0.5 * x1 + 0.3 * x2 + rng.normal(size=n)
    y = 1 + 0.4 * d + 0.6 * x1 + 0.3 * x2 - 0.2 * x3 + 0.3 * d * x3 + rng.normal(size=n)
    grp = (rng.random(n) < _expit(0.5 * x1)).astype(int)
    pre = 2 + 0.5 * x1 + rng.normal(size=n)
    post = 1 + 0.6 * grp + 0.7 * pre + 0.2 * x2 + rng.normal(size=n)
    region = np.array(["a", "b", "c"])[rng.integers(0, 3, size=n)]
    cl = rng.integers(1, 41, size=n)
    _write(
        pd.DataFrame(
            {
                "y": y,
                "d": d,
                "x1": x1,
                "x2": x2,
                "x3": x3,
                "g3": g3,
                "grp": grp,
                "pre": pre,
                "post": post,
                "region": region,
                "cl": cl,
            }
        ),
        "misc_sens_ovb.csv",
    )

    # ---------------- attrition / balance ----------------
    n = 500
    treat = (rng.random(n) < 0.5).astype(int)
    age = rng.normal(40, 10, size=n)
    inc = rng.normal(50, 15, size=n)
    obs = (rng.random(n) < np.where(treat == 1, 0.85, 0.70)).astype(int)
    y = 10 + 1.5 * treat + 0.05 * age + rng.normal(0, 2, size=n)
    y = np.where(obs == 1, y, np.nan)
    b1 = rng.normal(size=n)
    b2 = (rng.random(n) < 0.3).astype(int)
    b3 = rng.exponential(size=n)
    _write(
        pd.DataFrame(
            {
                "y": y,
                "treat": treat,
                "obs": obs,
                "age": age,
                "inc": inc,
                "b1": b1,
                "b2": b2,
                "b3": b3,
            }
        ),
        "misc_sens_attr.csv",
    )

    # ---------------- transport ----------------
    ns, nt = 400, 600
    x1 = rng.normal(size=ns)
    x2 = (rng.random(ns) < 0.4).astype(int)
    a = (rng.random(ns) < 0.5).astype(int)
    y = 1 + a + 0.5 * x1 + 0.5 * a * x1 + 0.3 * x2 + rng.normal(size=ns)
    _write(pd.DataFrame({"x1": x1, "x2": x2, "a": a, "y": y}), "misc_sens_src.csv")
    _write(
        pd.DataFrame(
            {
                "x1": rng.normal(0.5, 1, size=nt),
                "x2": (rng.random(nt) < 0.6).astype(int),
            }
        ),
        "misc_sens_tgt.csv",
    )


if __name__ == "__main__":
    main()
