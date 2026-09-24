"""Reference parity: sp.auc / sp.roc_curve AUC vs the Mann-Whitney closed form.

The area under the ROC curve equals the rank-based Mann-Whitney statistic:
``AUC = P(score_pos > score_neg) + 0.5*P(tie)``, computed exactly from the
mid-ranks of the positive scores. This is the identical closed form that
``pROC::auc`` (R) and ``sklearn.metrics.roc_auc_score`` implement; the match is
machine-precision. Closed-form identity (no external fixture needed).
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.stats import rankdata

import statspai as sp


def _mann_whitney_auc(y_true, scores):
    y = np.asarray(y_true)
    s = np.asarray(scores, dtype=float)
    ranks = rankdata(s)  # mid-ranks handle ties
    n_pos = int((y == 1).sum())
    n_neg = int((y == 0).sum())
    sum_ranks_pos = ranks[y == 1].sum()
    return (sum_ranks_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


@pytest.fixture(scope="module")
def data():
    rng = np.random.default_rng(1)
    n = 200
    y = rng.integers(0, 2, n)
    scores = 0.3 * y + rng.normal(0, 1, n)
    return y, scores


def test_auc_matches_mann_whitney(data):
    y, scores = data
    got = sp.auc(y, scores)
    assert got == pytest.approx(_mann_whitney_auc(y, scores), abs=1e-12)


def test_roc_curve_auc_matches_mann_whitney(data):
    y, scores = data
    rc = sp.roc_curve(y, scores)
    auc = rc["auc"] if isinstance(rc, dict) else rc.auc
    assert auc == pytest.approx(_mann_whitney_auc(y, scores), abs=1e-12)
