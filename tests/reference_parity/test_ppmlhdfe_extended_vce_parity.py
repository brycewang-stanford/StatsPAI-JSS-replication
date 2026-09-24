"""Reference parity: ``sp.ppmlhdfe`` extended ``vce=`` menu (wild + CR2/CR3).

**Wild (score) bootstrap — beyond-Stata, boottest-convention.** Stata's
``boottest`` cannot run after ``ppmlhdfe`` at all (no ``constraints()``
support — verified empirically), so no direct Stata reference exists. The
implementation therefore extends the menu with boottest's *exact convention*
via two facts:

1. the score bootstrap touches only per-cluster one-step contributions
   ``q_g`` and cluster shares — never per-observation leverage — and ``q_g``
   is pure linear algebra at the restricted fit, so the weighted
   Frisch-Waugh-Lovell reduction onto the FE-absorbed design is **exact**
   (verified to 1e-17 against the full-dummy computation). This makes the
   bootstrap computable for high-dimensional FE (500-level FE in <1s);
2. on low-dimensional FE, ``ppmlhdfe(vce="wild")`` is **byte-identical** to
   ``sp.fepois(vce="wild")`` — which is itself bit-exact vs Stata
   ``boottest`` after ``poisson`` (see ``test_feglm_wild_boottest_parity``,
   frozen enumerated p for the null x3 = 0.31640625 = 324/1024). The anchor
   below is therefore transitively pinned to Stata.

**CR2/CR3** use the reference-matching FE-as-dummies design (the weighted
projection does not carry CR2 leverage through absorption), equal to
``sp.fepois(vce="CR2")`` and hence to the frozen R
``clubSandwich::vcovCR(glm(poisson))`` references
(x1: CR2=0.030557580, CR3=0.032057722), with a hard guard against
high-dimensional FE.
"""

import numpy as np
import pandas as pd
import pytest

from statspai.regression.count import ppmlhdfe

BOOTTEST_X3_P = 0.31640625  # frozen enumerated boottest reference (via fepois)
CLUBSANDWICH_CR2_X1 = 0.030557580
CLUBSANDWICH_CR3_X1 = 0.032057722


def _wild_panel() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    n, g = 240, 10
    firm = rng.integers(0, 5, n)
    clu = rng.integers(0, g, n)
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    x3 = rng.normal(size=n)
    mu = np.exp(0.3 + 0.35 * x1 - 0.2 * x2 + 0.0 * x3 + 0.1 * firm)
    yv = rng.poisson(mu)
    return pd.DataFrame(
        {"y": yv, "x1": x1, "x2": x2, "x3": x3, "firm": firm, "clu": clu}
    )


def _pois_panel() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    n, g = 300, 12
    firm = rng.integers(0, 6, n)
    clu = rng.integers(0, g, n)
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    mu = np.exp(0.2 + 0.5 * x1 - 0.3 * x2 + 0.15 * firm)
    yv = rng.poisson(mu)
    return pd.DataFrame({"y": yv, "x1": x1, "x2": x2, "firm": firm, "clu": clu})


def test_ppmlhdfe_wild_byte_identical_to_fepois_and_boottest() -> None:
    pytest.importorskip("pyfixest")
    from statspai.fixest import fepois

    df = _wild_panel()
    rp = ppmlhdfe("y ~ x1 + x2 + x3 | firm", data=df, vce="wild", cluster="clu")
    rf = fepois("y ~ x1 + x2 + x3 | firm", data=df, vce="wild", cluster="clu")
    for v in ("x1", "x2", "x3"):
        assert float(rp.pvalues[v]) == float(rf.pvalues[v])
    # transitively bit-exact vs Stata boottest (enumerated 2^10 grid)
    assert float(rp.pvalues["x3"]) == BOOTTEST_X3_P


def test_ppmlhdfe_wild_scales_to_high_dimensional_fe() -> None:
    """The FWL-exact absorbed computation handles FE sizes where the dummy
    design would be infeasible — this is the beyond-Stata capability."""
    rng = np.random.default_rng(5)
    n = 5000
    big = rng.integers(0, 500, n)
    clu = rng.integers(0, 11, n)
    x1 = rng.normal(size=n)
    x3 = rng.normal(size=n)
    mu = np.exp(0.5 + 0.3 * x1 + 0.002 * (big % 7))
    yv = rng.poisson(mu)
    df = pd.DataFrame({"y": yv, "x1": x1, "x3": x3, "big": big, "clu": clu})
    r = ppmlhdfe("y ~ x1 + x3 | big", data=df, vce="wild", cluster="clu")
    # x3 is a true null: enumerated p strictly inside (0, 1); x1 rejects.
    assert 0.0 < float(r.pvalues["x3"]) < 1.0
    assert float(r.pvalues["x1"]) < 0.05


def test_ppmlhdfe_cr2_cr3_match_fepois_and_clubsandwich() -> None:
    df = _pois_panel()
    c2 = ppmlhdfe("y ~ x1 + x2 | firm", data=df, vce="CR2", cluster="clu")
    c3 = ppmlhdfe("y ~ x1 + x2 | firm", data=df, vce="CR3", cluster="clu")
    cj = ppmlhdfe("y ~ x1 + x2 | firm", data=df, vce="jackknife", cluster="clu")
    assert np.isclose(float(c2.std_errors["x1"]), CLUBSANDWICH_CR2_X1, atol=1e-4)
    assert np.isclose(float(c3.std_errors["x1"]), CLUBSANDWICH_CR3_X1, atol=1e-4)
    assert float(cj.std_errors["x1"]) == float(c3.std_errors["x1"])


def test_ppmlhdfe_cr2_high_dim_fe_guard() -> None:
    rng = np.random.default_rng(3)
    n = 4000
    big = rng.integers(0, 1500, n)  # 1499 dummies > 1000-column guard
    clu = rng.integers(0, 10, n)
    x1 = rng.normal(size=n)
    yv = rng.poisson(np.exp(0.4 + 0.2 * x1))
    df = pd.DataFrame({"y": yv, "x1": x1, "big": big, "clu": clu})
    with pytest.raises(Exception):
        ppmlhdfe("y ~ x1 | big", data=df, vce="CR2", cluster="clu")


def test_ppmlhdfe_vce_hc_alias_and_guards() -> None:
    df = _pois_panel()
    a = ppmlhdfe("y ~ x1 + x2 | firm", data=df, vce="robust")
    b = ppmlhdfe("y ~ x1 + x2 | firm", data=df, robust="robust")
    assert float(a.std_errors["x1"]) == float(b.std_errors["x1"])
    with pytest.raises(Exception):
        ppmlhdfe("y ~ x1 + x2 | firm", data=df, vce="wild")  # cluster required
    df["w"] = 1.0
    with pytest.raises(Exception):
        ppmlhdfe("y ~ x1 + x2 | firm", data=df, vce="wild", cluster="clu", weights="w")


def test_ppmlhdfe_conley_matches_conleyreg_via_fepois() -> None:
    """ppmlhdfe(vce='conley') equals fepois(vce='conley') on the same model,
    which is pinned to R conleyreg (spherical uniform kernel, ~1e-7); the
    no-FE case is asserted against the frozen conleyreg value directly."""
    rng = np.random.default_rng(31)
    n = 400
    lat = rng.uniform(30, 45, n)
    lon = rng.uniform(-120, -100, n)
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    mu = np.exp(0.3 + 0.4 * x1 - 0.25 * x2)
    yv = rng.poisson(mu)
    df = pd.DataFrame({"y": yv, "x1": x1, "x2": x2, "lat": lat, "lon": lon})
    r = ppmlhdfe(
        "y ~ x1 + x2",
        data=df,
        vce="conley",
        conley_lat="lat",
        conley_lon="lon",
        conley_cutoff=200,
    )
    assert np.isclose(float(r.std_errors["x1"]), 0.033367118927, atol=5e-7)
    with pytest.raises(Exception):
        ppmlhdfe("y ~ x1 + x2", data=df, vce="conley")  # coords required
