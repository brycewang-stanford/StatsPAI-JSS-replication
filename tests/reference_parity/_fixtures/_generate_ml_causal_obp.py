"""Reference OPE numbers from Open Bandit Pipeline (Python ``obp``).

Reads ``ml_causal_ope.csv`` (``_generate_ml_causal_data.py``) and writes
``ml_causal_obp.json``. ``obp`` is a Python reference -- there is no R or
Stata implementation of these contextual-bandit estimators that takes the
behaviour/evaluation policies and a reward model as inputs (checked: R
``policytree`` / ``grf`` evaluate binary-treatment policies on AIPW scores,
not K-action logged-bandit data).

``obp`` pins ``torch`` and old ``scikit-learn`` in its metadata; only the
closed-form estimator module is used, so install it without dependencies
into a throwaway directory and put it on ``PYTHONPATH``::

    pip install --no-deps --target /tmp/obp_target obp==0.5.7
    PYTHONPATH=/tmp/obp_target python \
        tests/reference_parity/_fixtures/_generate_ml_causal_obp.py

The evaluation policy, behaviour propensities and the (fixed, deliberately
misspecified) reward-model matrix are columns of the CSV, so the estimators
are deterministic. ``obp`` reports intervals by bootstrap only; the per-round
values (``_estimate_round_rewards``) are stored so that the analytic SE
``sd(round)/sqrt(n)`` can be checked as an identity.
"""

from __future__ import annotations

import json
import pathlib

import numpy as np
import obp
import pandas as pd
from obp.ope import (
    DirectMethod,
    DoublyRobust,
    InverseProbabilityWeighting,
    SelfNormalizedInverseProbabilityWeighting,
)

HERE = pathlib.Path(__file__).parent


def main() -> None:
    df = pd.read_csv(HERE / "ml_causal_ope.csv")
    n = len(df)
    K = 3
    action = df["a"].to_numpy(dtype=int)
    reward = df["r"].to_numpy(dtype=float)
    pb = df[[f"pb{k}" for k in range(K)]].to_numpy()
    pe = df[[f"pe{k}" for k in range(K)]].to_numpy()
    q = df[[f"q{k}" for k in range(K)]].to_numpy()
    pscore = pb[np.arange(n), action]
    action_dist = pe[:, :, None]
    q3 = q[:, :, None]

    out = {"meta": {"obp_version": obp.__version__, "n": n, "n_actions": K}}
    for name, est in (
        ("ipw", InverseProbabilityWeighting()),
        ("ipw_clip2", InverseProbabilityWeighting(lambda_=2.0)),
        ("snipw", SelfNormalizedInverseProbabilityWeighting()),
    ):
        kw = dict(reward=reward, action=action, pscore=pscore, action_dist=action_dist)
        out[name] = {
            "value": float(est.estimate_policy_value(**kw)),
            "round": est._estimate_round_rewards(**kw).tolist(),
        }
    dm = DirectMethod()
    out["dm"] = {
        "value": float(
            dm.estimate_policy_value(action_dist=action_dist, estimated_rewards_by_reg_model=q3)
        ),
        "round": dm._estimate_round_rewards(
            action_dist=action_dist, estimated_rewards_by_reg_model=q3
        ).tolist(),
    }
    for name, est in (("dr", DoublyRobust()), ("dr_clip2", DoublyRobust(lambda_=2.0))):
        kw = dict(
            reward=reward, action=action, pscore=pscore, action_dist=action_dist,
            estimated_rewards_by_reg_model=q3,
        )
        out[name] = {
            "value": float(est.estimate_policy_value(**kw)),
            "round": est._estimate_round_rewards(**kw).tolist(),
        }
    (HERE / "ml_causal_obp.json").write_text(
        json.dumps(out, indent=1, default=float), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
