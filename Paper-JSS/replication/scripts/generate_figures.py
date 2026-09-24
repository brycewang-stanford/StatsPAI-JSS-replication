"""Generate figure assets for the StatsPAI JSS worked examples."""
from __future__ import annotations

import io
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import statspai as sp

HERE = Path(__file__).resolve().parent
PAPER_DIR = HERE.parents[1]

sys.path.insert(0, str(HERE))
from _paths import STATSPAI_ROOT  # noqa: E402

# Shared with the Track C figure so the paper's two figure families use
# one typographic scale; see tests/perf/_figstyle.py for why.
sys.path.insert(0, str(STATSPAI_ROOT / "tests" / "perf"))
from _figstyle import TEXT_WIDTH_IN, apply as _apply_figstyle  # noqa: E402

_apply_figstyle(plt)

FIGURE_DIR = PAPER_DIR / "manuscript" / "figures"
PDF_METADATA = {"CreationDate": None}


def _as_frame(value: object) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value.copy()
    if isinstance(value, str):
        return pd.read_fwf(io.StringIO(value))
    raise TypeError(f"Cannot convert {type(value).__name__} to DataFrame")


def _save(fig: plt.Figure, stem: str) -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        FIGURE_DIR / f"{stem}.pdf",
        bbox_inches="tight",
        metadata=PDF_METADATA,
    )
    fig.savefig(FIGURE_DIR / f"{stem}.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def basque_gap() -> None:
    df = sp.datasets.basque_terrorism()
    fit = sp.synth(
        df,
        outcome="gdppc",
        unit="region",
        time="year",
        treated_unit="Basque Country",
        treatment_time=1970,
        method="classic",
    )
    gap = _as_frame(fit.model_info["gap_table"])
    fig, ax = plt.subplots(figsize=(TEXT_WIDTH_IN, 0.52 * TEXT_WIDTH_IN))
    ax.plot(gap["time"], gap["gap"], color="#1f4e79", linewidth=2.0)
    ax.axhline(0, color="0.25", linewidth=0.8)
    ax.axvline(1970, color="#9b2226", linestyle="--", linewidth=1.2)
    ax.fill_between(
        gap["time"],
        gap["gap"],
        0,
        where=gap["post_treatment"].astype(bool),
        color="#1f4e79",
        alpha=0.16,
    )
    ax.set_title("Basque synthetic-control gap")
    ax.set_xlabel("Year")
    ax.set_ylabel("GDP per capita gap")
    ax.text(1970.5, ax.get_ylim()[0] * 0.92, "Treatment", color="#9b2226")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    _save(fig, "ex02_basque_gap")


def basque_placebo() -> None:
    """In-space permutation placebo for the Basque SCM example.

    Reproduces the Abadie-Diamond-Hainmueller (2010) Figure 4 style:
    grey lines are donor placebos (each donor as the pseudo-treated
    unit), the dark line is the Basque country gap.
    """
    df = sp.datasets.basque_terrorism()
    fit = sp.synth(
        df,
        outcome="gdppc",
        unit="region",
        time="year",
        treated_unit="Basque Country",
        treatment_time=1970,
        method="classic",
    )
    times = fit.model_info["times"]
    treated_gap = _as_frame(fit.model_info["gap_table"])
    placebo_gaps = fit.model_info["placebo_gaps"]
    placebo_units = list(fit.model_info["placebo_units"])
    placebo_pre_mspes = list(fit.model_info["placebo_pre_mspes"])
    treated_pre_mspe = float(fit.model_info["pre_treatment_mspe"])

    fig, ax = plt.subplots(figsize=(TEXT_WIDTH_IN, 0.52 * TEXT_WIDTH_IN))
    ax.axhline(0, color="0.25", linewidth=0.8)
    ax.axvline(1970, color="#9b2226", linestyle="--", linewidth=1.2)
    # Drop placebos with very poor pre-treatment fit (>20x treated MSPE)
    # following Abadie-Diamond-Hainmueller (2010) Figure 5 convention.
    mspe_cutoff = 20.0 * treated_pre_mspe
    for j, unit in enumerate(placebo_units):
        if placebo_pre_mspes[j] > mspe_cutoff:
            continue
        ax.plot(times, placebo_gaps[:, j], color="0.65", linewidth=0.8, alpha=0.7)
    ax.plot(treated_gap["time"], treated_gap["gap"],
            color="#1f4e79", linewidth=2.2, label="Basque Country")
    ax.set_title(
        "In-space permutation placebo "
        "(donors with pre-MSPE $\\leq 20$x treated)"
    )
    ax.set_xlabel("Year")
    ax.set_ylabel("GDP per capita gap")
    ax.text(1970.5, ax.get_ylim()[0] * 0.94, "Treatment", color="#9b2226")
    ax.legend(loc="lower left", frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    _save(fig, "ex02_basque_placebo")


def mpdta_event_study() -> None:
    df = sp.datasets.mpdta()
    fit = sp.callaway_santanna(
        df,
        y="lemp",
        g="first_treat",
        t="year",
        i="countyreal",
        estimator="reg",
    )
    es = fit.model_info["event_study"].copy()
    fig, ax = plt.subplots(figsize=(TEXT_WIDTH_IN, 0.52 * TEXT_WIDTH_IN))
    ax.axhline(0, color="0.25", linewidth=0.8)
    ax.axvline(-0.5, color="#9b2226", linestyle="--", linewidth=1.2)
    ax.errorbar(
        es["relative_time"],
        es["att"],
        yerr=[es["att"] - es["ci_lower"], es["ci_upper"] - es["att"]],
        fmt="o-",
        color="#2a6f62",
        ecolor="#8ab7aa",
        capsize=3,
        linewidth=1.8,
    )
    ax.set_title("Callaway-Sant'Anna event-study estimates")
    ax.set_xlabel("Relative time")
    ax.set_ylabel("ATT")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    _save(fig, "ex03_mpdta_event_study")


def lee_rd_plot() -> None:
    # simulated=True: the dataset default flipped to the real RDsenate
    # extract (columns x, y) in 1.21.0; this figure plots the calibrated
    # replica, matching Section 4.4's replica arm.
    df = sp.datasets.lee_2008_senate(simulated=True)
    rd = sp.rdrobust(df, y="voteshare_next", x="margin", c=0.0)
    fig, ax = sp.rdplot(
        df,
        y="voteshare_next",
        x="margin",
        c=0.0,
        h=float(rd.model_info["bandwidth_h"]),
        show_bw=True,
        title="Lee (2008) RD: incumbency advantage",
        x_label="Democratic margin at t",
        y_label="Democratic vote share at t+1",
    )
    fig.tight_layout()
    _save(fig, "ex04_lee_rd")


def main() -> int:
    basque_gap()
    basque_placebo()
    mpdta_event_study()
    lee_rd_plot()
    print(f"OK -- wrote figures to {FIGURE_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
