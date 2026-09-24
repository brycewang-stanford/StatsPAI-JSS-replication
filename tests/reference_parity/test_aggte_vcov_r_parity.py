"""``sp.aggte(type='dynamic')`` exposes the covariance R ``did`` computes.

The *joint* covariance of the event-study cells -- not only its diagonal --
is what ``sp.honest_did`` / ``sp.breakdown_m`` feed to the Rambachan-Roth
fixed-length interval and what ``sp.uniform_bands`` turns into a sup-t
critical value. Until 1.30 ``sp.aggte`` did not expose it, so those callers
rebuilt it from the per-cell influence functions with the cohort shares
treated as fixed: the diagonal agreed with the reported standard errors but
the off-diagonal blocks were up to 8 percent away from R's, and the FLCI
built on them was correspondingly wrong (on the ``cs_report`` demo panel the
breakdown M* moved by a factor of three).

Reference values come from R ``did`` on this machine, run against the
**same CSV this test loads** (``statspai/datasets/data/castle_2013.csv``)::

    library(did)
    df <- read.csv("castle_2013.csv")
    df$gvar <- ifelse(is.na(df$effyear), 0, df$effyear)
    a <- att_gt(yname="l_homicide", tname="year", idname="sid", gname="gvar",
                data=df, control_group="nevertreated", bstrap=FALSE,
                cband=FALSE, est_method="dr", base_period="universal")
    d <- aggte(a, type="dynamic", bstrap=FALSE, cband=FALSE)
    IF <- d$inf.function$dynamic.inf.func.e
    S <- t(IF) %*% IF / nrow(IF)^2          # the cells' joint covariance

The reference period (e = -1) is dropped on both sides: R reports its row
and column as exactly zero and StatsPAI omits the cell.
"""

from __future__ import annotations

import numpy as np

import statspai as sp

R_EGT = [-9, -8, -7, -6, -5, -4, -3, -2, 0, 1, 2, 3, 4, 5]

R_VCOV = [
    [
        3.265703189728e-03,
        2.446999887884e-03,
        2.251274415446e-03,
        1.366029390751e-03,
        8.945331756292e-04,
        4.126317446617e-04,
        3.084526181329e-04,
        1.051783798372e-05,
        -8.379291478756e-04,
        -8.390402394222e-04,
        -1.346172915950e-03,
        -8.531199177583e-04,
        -1.034535339158e-03,
        -5.812701115035e-04,
    ],
    [
        2.446999887884e-03,
        1.412714519523e-02,
        -7.852134277315e-04,
        1.770631118640e-03,
        5.499242719398e-04,
        -2.153830856370e-03,
        -3.914949073819e-04,
        -1.965811785875e-03,
        -3.496338335223e-04,
        -2.685163165697e-03,
        -3.192273096951e-04,
        -2.920164672463e-04,
        -2.099067201199e-04,
        5.739825352227e-05,
    ],
    [
        2.251274415446e-03,
        -7.852134277315e-04,
        1.560501730050e-02,
        2.615608786716e-03,
        2.309927001456e-03,
        1.422926581275e-03,
        -2.471942960849e-04,
        2.558593688925e-05,
        -2.394001729729e-03,
        7.550733585360e-04,
        -1.285883649398e-03,
        -1.335047342317e-03,
        -3.199930030618e-04,
        -1.266191720237e-04,
    ],
    [
        1.366029390751e-03,
        1.770631118640e-03,
        2.615608786716e-03,
        4.753414366152e-03,
        3.028652181578e-03,
        1.625751744625e-03,
        2.211480688573e-03,
        8.153951304698e-04,
        -8.760747212937e-04,
        -1.042081351948e-03,
        -1.101683141887e-03,
        -7.729663786250e-04,
        -4.447490772196e-04,
        -1.767221612224e-04,
    ],
    [
        8.945331756292e-04,
        5.499242719398e-04,
        2.309927001456e-03,
        3.028652181578e-03,
        3.719369493273e-03,
        1.744537947813e-03,
        1.889340172418e-03,
        7.972460142477e-05,
        -1.425744466069e-03,
        -4.395282966360e-04,
        -2.200761912160e-03,
        -2.037151676878e-03,
        -9.653011524708e-04,
        -2.066951605894e-04,
    ],
    [
        4.126317446617e-04,
        -2.153830856370e-03,
        1.422926581275e-03,
        1.625751744625e-03,
        1.744537947813e-03,
        2.705911021270e-03,
        1.439160534424e-03,
        1.368004803952e-03,
        -8.904483096848e-05,
        -1.780923835260e-04,
        -5.484487201134e-04,
        -8.724258966185e-04,
        -3.858663983753e-04,
        -7.321227181601e-04,
    ],
    [
        3.084526181329e-04,
        -3.914949073819e-04,
        -2.471942960849e-04,
        2.211480688573e-03,
        1.889340172418e-03,
        1.439160534424e-03,
        2.147571110432e-03,
        1.002717234039e-03,
        -1.274241439346e-04,
        -1.260788537577e-04,
        -8.415515817796e-04,
        -8.583413412742e-04,
        -3.138849560772e-04,
        -7.385325085449e-04,
    ],
    [
        1.051783798372e-05,
        -1.965811785875e-03,
        2.558593688925e-05,
        8.153951304698e-04,
        7.972460142477e-05,
        1.368004803952e-03,
        1.002717234039e-03,
        1.915880779700e-03,
        5.916350809784e-04,
        9.154693914828e-05,
        6.519075950787e-04,
        4.513700375556e-04,
        5.723761144405e-04,
        -6.483745802874e-04,
    ],
    [
        -8.379291478756e-04,
        -3.496338335223e-04,
        -2.394001729729e-03,
        -8.760747212937e-04,
        -1.425744466069e-03,
        -8.904483096848e-05,
        -1.274241439346e-04,
        5.916350809784e-04,
        1.571578232099e-03,
        1.705978931278e-04,
        1.561991358945e-03,
        1.256516886878e-03,
        9.261468451298e-04,
        6.425967290269e-05,
    ],
    [
        -8.390402394222e-04,
        -2.685163165697e-03,
        7.550733585360e-04,
        -1.042081351948e-03,
        -4.395282966360e-04,
        -1.780923835260e-04,
        -1.260788537577e-04,
        9.154693914828e-05,
        1.705978931278e-04,
        2.432578771455e-03,
        4.588786575437e-04,
        6.343536236988e-04,
        9.805811717502e-04,
        2.848670272251e-05,
    ],
    [
        -1.346172915950e-03,
        -3.192273096951e-04,
        -1.285883649398e-03,
        -1.101683141887e-03,
        -2.200761912160e-03,
        -5.484487201134e-04,
        -8.415515817796e-04,
        6.519075950787e-04,
        1.561991358945e-03,
        4.588786575437e-04,
        3.517923179896e-03,
        2.646307250786e-03,
        2.201406485014e-03,
        6.395400497350e-04,
    ],
    [
        -8.531199177583e-04,
        -2.920164672463e-04,
        -1.335047342317e-03,
        -7.729663786250e-04,
        -2.037151676878e-03,
        -8.724258966185e-04,
        -8.583413412742e-04,
        4.513700375556e-04,
        1.256516886878e-03,
        6.343536236988e-04,
        2.646307250786e-03,
        3.276754046551e-03,
        2.143774514756e-03,
        8.180919638973e-04,
    ],
    [
        -1.034535339158e-03,
        -2.099067201199e-04,
        -3.199930030618e-04,
        -4.447490772196e-04,
        -9.653011524708e-04,
        -3.858663983753e-04,
        -3.138849560772e-04,
        5.723761144405e-04,
        9.261468451298e-04,
        9.805811717502e-04,
        2.201406485014e-03,
        2.143774514756e-03,
        2.884272294343e-03,
        1.538907883950e-03,
    ],
    [
        -5.812701115035e-04,
        5.739825352227e-05,
        -1.266191720237e-04,
        -1.767221612224e-04,
        -2.066951605894e-04,
        -7.321227181601e-04,
        -7.385325085449e-04,
        -6.483745802874e-04,
        6.425967290269e-05,
        2.848670272251e-05,
        6.395400497350e-04,
        8.180919638973e-04,
        1.538907883950e-03,
        2.586133729025e-03,
    ],
]


def _fit():
    df = sp.datasets.castle_doctrine()
    df = df.assign(gvar=df["effyear"].fillna(0))
    return sp.callaway_santanna(
        df,
        y="l_homicide",
        g="gvar",
        t="year",
        i="sid",
        estimator="dr",
        control_group="nevertreated",
        base_period="universal",
    )


def test_aggte_dynamic_vcov_matches_r_did():
    """Every entry, diagonal and off-diagonal, at the Track A budget."""
    dyn = sp.aggte(_fit(), type="dynamic", bstrap=False, cband=False)
    times = [int(t) for t in dyn.detail["relative_time"]]
    assert times == R_EGT
    V = np.asarray(dyn.model_info["vcov"], dtype=float)
    R = np.asarray(R_VCOV, dtype=float)
    assert V.shape == R.shape
    # Observed worst relative gap 2.8e-13 (R's transcription is 12 digits).
    np.testing.assert_allclose(V, R, rtol=1e-9, atol=1e-18)


def test_exposed_vcov_is_the_one_behind_the_reported_standard_errors():
    dyn = sp.aggte(_fit(), type="dynamic", bstrap=False, cband=False)
    V = np.asarray(dyn.model_info["vcov"], dtype=float)
    np.testing.assert_allclose(
        np.sqrt(np.diag(V)), dyn.detail["se"].to_numpy(dtype=float), rtol=1e-12
    )


def test_honest_did_reads_that_covariance():
    """The FLCI route uses the exposed matrix, not a fixed-share rebuild."""
    fit = _fit()
    from statspai.did._flci import event_study_moments

    _, sigma, times = event_study_moments(fit)
    assert [int(t) for t in times] == R_EGT
    np.testing.assert_allclose(
        sigma, np.asarray(R_VCOV, dtype=float), rtol=1e-9, atol=1e-18
    )
