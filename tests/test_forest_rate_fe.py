"""RATE for causal forests with fixed effects, and its split-sample form.

``sp.rate`` used to refuse these forests outright (no propensity, no
doubly-robust score). The imputation scores that already give the ATT give
the curve too, and -- because the rank weights and the imputation weights
are both linear -- an exact standard error rather than one that treats the
scores as data. These tests pin the identities that claim rests on, the
contracts around it, and the reason ``sp.rate_split`` exists.
"""

import warnings

import numpy as np
import pandas as pd
import pytest

import statspai as sp
from statspai.exceptions import (
    AssumptionWarning,
    DataInsufficient,
    MethodIncompatibility,
)
from statspai.forest._fe_imputation import functional_weights, imputation_design
from statspai.forest.forest_inference import rate_from_scores, rate_rank_weights


def panel(seed=0, n_units=90, n_periods=7, het=0.5, sigma=0.6):
    """Staggered adoption selected on the unit effect; tau = 0.3 + het * z."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n_units):
        a, z, w = rng.normal(), rng.normal(), rng.normal()
        never = i % 5 == 0
        g = 10**6 if never else int(np.clip(3 + round(a), 2, n_periods))
        for t in range(1, n_periods + 1):
            d = 1.0 * (t >= g)
            y = a + 0.25 * t + (0.3 + het * z) * d + rng.normal(0, sigma)
            rows.append((i, t, y, d, z, w))
    return pd.DataFrame(rows, columns=["id", "t", "y", "d", "z", "w"])


@pytest.fixture(scope="module")
def fe_forest():
    df = panel()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        cf = sp.causal_forest(
            "y ~ d | z + w",
            data=df,
            fe="twoway",
            unit="id",
            time="t",
            clusters=df["id"].to_numpy(),
            n_estimators=200,
            random_state=0,
        )
    return cf, df


@pytest.fixture(scope="module")
def pooled_forest():
    rng = np.random.default_rng(5)
    n = 600
    X = rng.normal(size=(n, 3))
    T = rng.binomial(1, 1 / (1 + np.exp(-0.4 * X[:, 0])))
    Y = X[:, 1] + (1.0 + X[:, 0]) * T + rng.normal(scale=0.5, size=n)
    df = pd.DataFrame({"y": Y, "d": T, "x0": X[:, 0], "x1": X[:, 1], "x2": X[:, 2]})
    return (
        sp.causal_forest(
            "y ~ d | x0 + x1 + x2", data=df, n_estimators=200, random_state=0
        ),
        df,
    )


# --------------------------------------------------------------------------- #
#  The rank weights are exactly grf's estimator, rewritten as a linear map
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("target", ["AUTOC", "QINI"])
@pytest.mark.parametrize("ties", [False, True])
def test_rank_weights_reproduce_rate_from_scores(target, ties):
    rng = np.random.default_rng(11)
    scores = rng.normal(size=60)
    priorities = rng.normal(size=60)
    if ties:  # collapse to ~10 distinct values, as a discrete rule would
        priorities = np.round(priorities, 1)
    weights = rate_rank_weights(priorities, target)
    assert weights.shape == scores.shape
    np.testing.assert_allclose(
        weights @ scores,
        rate_from_scores(scores, priorities, target)["estimate"],
        rtol=0,
        atol=1e-12,
    )


@pytest.mark.parametrize("target", ["AUTOC", "QINI"])
def test_rank_weights_sum_to_zero(target):
    # RATE is a contrast -- the top-q mean minus the overall mean -- so a
    # constant effect must give exactly 0 whatever the ranking.
    rng = np.random.default_rng(3)
    weights = rate_rank_weights(rng.normal(size=40), target)
    assert abs(weights.sum()) < 1e-12


def test_rank_weights_are_ordered_by_priority():
    # Higher priority must carry more weight, or the curve is upside down.
    priorities = np.array([0.5, -2.0, 1.5, 0.0])
    weights = rate_rank_weights(priorities, "AUTOC")
    assert list(np.argsort(-weights)) == list(np.argsort(-priorities))


# --------------------------------------------------------------------------- #
#  Composed with the imputation weights: exact, and the fixed effects are gone
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("target", ["AUTOC", "QINI"])
def test_fe_rate_equals_the_scores_it_is_built_from(fe_forest, target):
    cf, _ = fe_forest
    design = imputation_design(cf, "test", "none")
    rows = np.flatnonzero(design.target)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", AssumptionWarning)
        got = sp.rate(cf, target=target)
    reference = rate_from_scores(
        design.gamma[rows], np.asarray(cf._oob_tau)[rows], target
    )["estimate"]
    np.testing.assert_allclose(got["estimate"], reference, rtol=0, atol=1e-11)
    np.testing.assert_allclose(got["toc_curve"][:, 0], np.linspace(0.01, 1.0, 100))


@pytest.mark.parametrize("target", ["AUTOC", "QINI"])
def test_fe_rate_weights_annihilate_the_fixed_effects(fe_forest, target):
    # theta = V' y is only an effect if V is orthogonal to the unit and
    # period dummies; and for RATE, unlike the ATT, it must also put zero
    # net weight on the treatment.
    cf, _ = fe_forest
    design = imputation_design(cf, "test", "none")
    rows = np.flatnonzero(design.target)
    W1 = np.zeros(design.n)
    W1[rows] = rate_rank_weights(np.asarray(cf._oob_tau)[rows], target)
    V = np.asarray(functional_weights(design, W1)).ravel()
    assert np.abs(design.Z.T @ V).max() < 1e-10
    assert abs(V @ np.asarray(cf._T_original, dtype=float)) < 1e-10


def test_att_weights_put_unit_weight_on_the_treatment(fe_forest):
    # The contrast above is specific to RATE: the ATT functional must load
    # one, which is what makes it an effect rather than a contrast.
    cf, _ = fe_forest
    design = imputation_design(cf, "test", "none")
    W1 = np.where(design.target, 1.0, 0.0) / design.target.sum()
    V = np.asarray(functional_weights(design, W1)).ravel()
    np.testing.assert_allclose(
        V @ np.asarray(cf._T_original, dtype=float), 1.0, atol=1e-10
    )


# --------------------------------------------------------------------------- #
#  Contracts
# --------------------------------------------------------------------------- #


def test_fe_rate_returns_the_documented_keys(fe_forest):
    cf, _ = fe_forest
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", AssumptionWarning)
        res = sp.rate(cf)
    for key in (
        "estimate",
        "se",
        "ci_low",
        "ci_high",
        "target",
        "toc_curve",
        "n",
        "method",
        "priority_source",
        "n_clusters",
        "estimand",
        "variance",
        "se_method",
        "n_treated_cells",
        "imputation_covariates",
        "cate_source",
    ):
        assert key in res, key
    assert res["variance"] == "bjs"  # conservative for the population RATE
    assert res["se_method"] == "imputation"
    assert res["priority_source"] == "out_of_bag"
    assert res["ci_low"] < res["estimate"] < res["ci_high"]
    assert res["n"] == res["n_treated_cells"]
    assert "treated cells" in res["estimand"]


def test_reusing_the_forests_own_ranking_warns(fe_forest):
    cf, _ = fe_forest
    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter("always")
        sp.rate(cf)
    hits = [w for w in rec if "valid test" in str(w.message)]
    assert len(hits) == 1
    assert issubclass(hits[0].category, AssumptionWarning)
    assert "rate_split" in str(hits[0].message)


def test_supplied_priorities_do_not_warn(fe_forest):
    cf, df = fe_forest
    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter("always")
        res = sp.rate(cf, priorities=df["z"].to_numpy())
    assert not [w for w in rec if "valid test" in str(w.message)]
    assert res["priority_source"] == "supplied"


def test_priorities_accept_both_lengths(fe_forest):
    cf, df = fe_forest
    design = imputation_design(cf, "test", "none")
    rows = np.flatnonzero(design.target)
    per_row = sp.rate(cf, priorities=df["z"].to_numpy())
    per_cell = sp.rate(cf, priorities=df["z"].to_numpy()[rows])
    np.testing.assert_allclose(per_row["estimate"], per_cell["estimate"], atol=1e-12)
    np.testing.assert_allclose(per_row["se"], per_cell["se"], atol=1e-12)


def test_wrong_priority_length_raises(fe_forest):
    cf, _ = fe_forest
    with pytest.raises(MethodIncompatibility, match="one value per row"):
        sp.rate(cf, priorities=np.zeros(3))


def test_non_finite_priorities_raise(fe_forest):
    # Only the treated cells are ranked, so the NaN has to land on one --
    # a NaN on a row the curve never reads is not an error.
    cf, df = fe_forest
    design = imputation_design(cf, "test", "none")
    bad = df["z"].to_numpy().copy()
    bad[np.flatnonzero(design.target)[0]] = np.nan
    with pytest.raises(DataInsufficient, match="non-finite"):
        sp.rate(cf, priorities=bad)
    ok = df["z"].to_numpy().copy()
    ok[np.flatnonzero(~design.target)[0]] = np.nan
    assert np.isfinite(sp.rate(cf, priorities=ok)["estimate"])


def test_half_sample_bootstrap_is_refused_for_fe_forests(fe_forest):
    cf, _ = fe_forest
    with pytest.raises(MethodIncompatibility, match="se_method must be"):
        sp.rate(cf, se_method="half_sample")


def test_imputation_se_is_refused_for_pooled_forests(pooled_forest):
    cf, _ = pooled_forest
    with pytest.raises(MethodIncompatibility, match="only defined for a forest"):
        sp.rate(cf, se_method="imputation")


def test_auto_se_method_is_unchanged_for_pooled_forests(pooled_forest):
    cf, _ = pooled_forest
    auto = sp.rate(cf)
    explicit = sp.rate(cf, se_method="influence")
    np.testing.assert_allclose(auto["se"], explicit["se"], rtol=0, atol=0)


@pytest.mark.parametrize("se_method", ["imputation", "influence"])
def test_both_fe_se_methods_agree_closely(fe_forest, se_method):
    # They estimate different things (one conditions on the ranking) but on
    # a design with real heterogeneity they must not disagree by a factor.
    cf, df = fe_forest
    res = sp.rate(cf, priorities=df["z"].to_numpy(), se_method=se_method)
    reference = sp.rate(cf, priorities=df["z"].to_numpy(), se_method="imputation")
    assert 0.5 < res["se"] / reference["se"] < 2.0


def test_continuous_treatment_fe_forest_is_refused():
    df = panel(seed=2)
    rng = np.random.default_rng(0)
    df["dose"] = df["d"] * rng.uniform(0.5, 1.5, len(df))
    cf = sp.causal_forest(
        "y ~ dose | z + w",
        data=df,
        fe="twoway",
        unit="id",
        time="t",
        discrete_treatment=False,
        n_estimators=60,
        random_state=0,
    )
    with pytest.raises(MethodIncompatibility):
        sp.rate(cf)


@pytest.mark.parametrize("target", ["autoc", "Qini"])
def test_target_is_case_insensitive(fe_forest, target):
    cf, df = fe_forest
    res = sp.rate(cf, target=target, priorities=df["z"].to_numpy())
    assert res["target"] == target.upper()


def test_unknown_target_raises(fe_forest):
    cf, _ = fe_forest
    with pytest.raises(MethodIncompatibility, match="AUTOC"):
        sp.rate(cf, target="qini2")


# --------------------------------------------------------------------------- #
#  rate_split
# --------------------------------------------------------------------------- #


def test_rate_split_splits_units_not_rows(fe_forest):
    cf, df = fe_forest
    res = sp.rate_split(cf, n_splits=3, random_state=0)
    assert res["split_by"] == "units"
    assert res["priority_source"] == "held_out_forest"
    assert res["n_rows_dropped"] == 0
    assert res["n_train_units"] + res["n_eval_units"] == df["id"].nunique()
    assert res["n_train_units"] > 0 and res["n_eval_units"] > 0
    assert "split-sample" in res["method"] and "VEIN over 3 splits" in res["method"]


def test_rate_split_does_not_warn_about_reuse(fe_forest):
    cf, _ = fe_forest
    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter("always")
        sp.rate_split(cf, n_splits=3)
    assert not [w for w in rec if "valid test" in str(w.message)]


def test_rate_split_is_deterministic_given_random_state(fe_forest):
    cf, _ = fe_forest
    a = sp.rate_split(cf, n_splits=3, random_state=7)
    b = sp.rate_split(cf, n_splits=3, random_state=7)
    assert a["estimate"] == b["estimate"] and a["se"] == b["se"]


def test_one_split_moves_with_the_seed_and_aggregating_steadies_it(fe_forest):
    # The reason n_splits defaults to 21. A single split is a draw: it moves
    # with the seed, and with random_state in reach that invites keeping the
    # draw that agrees with you. Medians over splits should be visibly
    # steadier across the same seeds.
    cf, _ = fe_forest
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", AssumptionWarning)
        single = [
            sp.rate_split(cf, n_splits=1, random_state=s)["estimate"] for s in range(4)
        ]
    pooled = [
        sp.rate_split(cf, n_splits=9, random_state=10 * s)["estimate"] for s in range(4)
    ]
    assert len(set(single)) == 4  # every draw is a different evaluation
    assert np.ptp(pooled) < np.ptp(single)


def test_one_split_warns_that_it_is_a_draw(fe_forest):
    cf, _ = fe_forest
    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter("always")
        res = sp.rate_split(cf, n_splits=1)
    hits = [w for w in rec if "one draw" in str(w.message)]
    assert len(hits) == 1 and issubclass(hits[0].category, AssumptionWarning)
    assert res["n_splits"] == 1
    assert "not VEIN" in res["aggregation"]


def test_vein_reports_how_far_the_split_moved_the_answer(fe_forest):
    cf, _ = fe_forest
    res = sp.rate_split(cf, n_splits=9, random_state=0)
    assert res["n_splits"] == 9
    assert res["estimate_min"] <= res["estimate"] <= res["estimate_max"]
    assert res["estimate_iqr"] >= 0
    assert "median over splits" in res["aggregation"]


@pytest.mark.parametrize("bad", [0, -1, 2.5, True])
def test_bad_n_splits_is_refused(fe_forest, bad):
    cf, _ = fe_forest
    with pytest.raises(MethodIncompatibility, match="n_splits"):
        sp.rate_split(cf, n_splits=bad)


def test_rate_split_train_frac_shifts_the_halves(fe_forest):
    cf, df = fe_forest
    small = sp.rate_split(cf, n_splits=3, train_frac=0.3, random_state=1)
    large = sp.rate_split(cf, n_splits=3, train_frac=0.7, random_state=1)
    assert small["n_train_units"] < large["n_train_units"]
    for res in (small, large):
        assert res["n_train_units"] + res["n_eval_units"] == df["id"].nunique()


@pytest.mark.parametrize("train_frac", [0.0, 1.0, -0.5, 1.5])
def test_rate_split_rejects_degenerate_train_frac(fe_forest, train_frac):
    cf, _ = fe_forest
    with pytest.raises(MethodIncompatibility, match="train_frac"):
        sp.rate_split(cf, train_frac=train_frac)


def test_rate_split_leaves_the_original_forest_alone(fe_forest):
    cf, _ = fe_forest
    before = np.asarray(cf._oob_tau).copy()
    sp.rate_split(cf, n_splits=3)
    np.testing.assert_array_equal(np.asarray(cf._oob_tau), before)


def test_rate_split_on_a_pooled_forest(pooled_forest):
    cf, _ = pooled_forest
    res = sp.rate_split(cf, n_splits=3, random_state=0)
    assert res["split_by"] == "rows"
    assert res["priority_source"] == "held_out_forest"
    assert np.isfinite(res["estimate"]) and res["se"] > 0


def test_rate_split_splits_members_for_dyadic_data():
    # A flow between a training and an evaluation country belongs to
    # neither half: it has to be dropped, not silently assigned.
    rng = np.random.default_rng(4)
    n_nodes, n_periods = 14, 6
    pairs = [(i, j) for i in range(n_nodes) for j in range(i + 1, n_nodes)]
    node_a = rng.normal(size=n_nodes)
    rows = []
    for k, (i, j) in enumerate(pairs):
        z = rng.normal()
        g = 10**6 if k % 4 == 0 else int(rng.integers(2, n_periods + 1))
        for t in range(1, n_periods + 1):
            d = 1.0 * (t >= g)
            y = (
                node_a[i]
                + node_a[j]
                + 0.2 * t
                + (0.3 + 0.5 * z) * d
                + rng.normal(0, 0.5)
            )
            rows.append((k, t, y, d, z, i, j))
    df = pd.DataFrame(rows, columns=["pair", "t", "y", "d", "z", "i", "j"])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        cf = sp.causal_forest(
            "y ~ d | z",
            data=df,
            fe="twoway",
            unit="pair",
            time="t",
            clusters=df["pair"].to_numpy(),
            n_estimators=100,
            random_state=0,
        )
        members = df[["i", "j"]].to_numpy()
        res = sp.rate_split(cf, members=members, n_splits=3, random_state=0)
    assert res["split_by"] == "members"
    assert res["n_rows_dropped"] > 0  # the straddling flows
    assert "dyadic" in res["method_detail"]
    # The counts report the thing that was split: countries, not pairs.
    assert res["n_train_units"] + res["n_eval_units"] == n_nodes
    assert res["n_train_units"] < df["pair"].nunique()


def test_rate_split_says_so_when_the_halves_are_too_thin():
    df = panel(seed=1, n_units=8, n_periods=4)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        cf = sp.causal_forest(
            "y ~ d | z + w",
            data=df,
            fe="twoway",
            unit="id",
            time="t",
            clusters=df["id"].to_numpy(),
            n_estimators=50,
            random_state=0,
        )
    with pytest.raises((DataInsufficient, MethodIncompatibility)) as exc:
        sp.rate_split(cf, n_splits=3, train_frac=0.5, random_state=0)
    assert "rate_split()" in str(exc.value)


def test_rate_split_is_registered():
    spec = sp.describe_function("rate_split")
    assert spec is not None
    text = spec if isinstance(spec, str) else str(spec)
    assert "AUTOC" in text or "RATE" in text


def test_rate_split_warns_when_a_half_is_too_thin_to_learn_a_rule():
    # 40 units split in two leaves 20 a side; the Monte Carlo behind the
    # defaults had 75, and the guide's 15-country panel (7 a side) scattered
    # over +-0.08 across splits. Warn rather than let it read as a result.
    df = panel(seed=3, n_units=40)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        cf = sp.causal_forest(
            "y ~ d | z + w",
            data=df,
            fe="twoway",
            unit="id",
            time="t",
            clusters=df["id"].to_numpy(),
            n_estimators=100,
            random_state=0,
        )
    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter("always")
        res = sp.rate_split(cf, n_splits=3, random_state=0)
    hits = [w for w in rec if "close to noise" in str(w.message)]
    assert len(hits) == 1
    assert issubclass(hits[0].category, AssumptionWarning)
    assert max(res["n_train_units"], res["n_eval_units"]) < 30


def test_rate_split_is_quiet_when_both_halves_are_large_enough(fe_forest):
    cf, _ = fe_forest  # 90 units, 45 a side
    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter("always")
        sp.rate_split(cf, n_splits=3, random_state=0)
    assert not [w for w in rec if "close to noise" in str(w.message)]


def test_inadmissible_splits_are_skipped_not_fatal():
    # On a small dyadic panel some partitions leave the evaluation half with
    # nothing to impute. Those are not draws from the estimator, they are
    # inadmissible partitions, and one of them must not destroy the call --
    # which defaulting to many splits would otherwise guarantee.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        df = sp.datasets.currency_union_panel(seed=0)
        cf = sp.causal_forest(
            data=df,
            y="log_trade",
            d="euro",
            x=["pre_trade", "log_gdp_prod", "log_gdppc"],
            id="pair",
            time="year",
            fe="twoway",
            random_state=0,
        )
        members = df[["country_i", "country_j"]].to_numpy()
    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter("always")
        res = sp.rate_split(
            cf, members=members, covariates="auto", n_splits=21, random_state=0
        )
    assert res["n_splits_skipped"] >= 1
    assert res["n_splits"] == 21 - res["n_splits_skipped"]
    assert [w for w in rec if "were skipped" in str(w.message)]
    # A split with a non-positive dyadic variance contributes an estimate but
    # no interval; one of those must not turn the whole interval into NaN.
    assert res["n_splits_without_interval"] > 0
    assert np.isfinite(res["ci_low"]) and np.isfinite(res["ci_high"])
    assert res["ci_low"] <= res["estimate"] <= res["ci_high"]


def test_too_many_inadmissible_splits_is_an_error():
    df = panel(seed=2, n_units=16, n_periods=4)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        cf = sp.causal_forest(
            "y ~ d | z + w",
            data=df,
            fe="twoway",
            unit="id",
            time="t",
            clusters=df["id"].to_numpy(),
            n_estimators=60,
            random_state=0,
        )
        with pytest.raises(DataInsufficient, match="too small to split"):
            sp.rate_split(cf, n_splits=9, train_frac=0.9)
