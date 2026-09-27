"""Shared inputs for the Track C benchmarks.

A speed ratio compares two implementations only if both run the same task
on the same input. Seeding NumPy and R with the same integer does not give
the same data (the generators differ), so every benchmark input is drawn
once, here, written as CSV with round-trip precision, and read by *both*
sides. Each side records the SHA-256 of the file it read, and
``compare_perf.py`` refuses a row whose two sides read different bytes.

    python tests/perf/_data.py            # write every input + manifest

Files land in ``tests/perf/data/`` (git-ignored; regenerated on demand, the
largest is ~60 MB) with ``manifest.json`` holding their hashes.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"

SIZES = {
    "01_hdfe": [10_000, 100_000, 1_000_000],
    "02_csdid": [1_000, 5_000, 25_000],  # units; five periods each
    "03_scm": [20, 50, 100],  # donors
    "04_dml": [1_000, 5_000, 10_000],
}
CSDID_T = 5
SCM_T = 30
SCM_T0 = 1985  # first treated year; 1970-1984 are pre-treatment


def hdfe(n: int, seed: int = 42) -> pd.DataFrame:
    n_firms = max(50, int(np.sqrt(n) * 2))
    n_years = 20
    rng = np.random.default_rng(seed)
    firm = rng.integers(0, n_firms, size=n)
    year = rng.integers(0, n_years, size=n)
    firm_fe = rng.normal(0, 1.0, size=n_firms)
    year_fe = rng.normal(0, 0.5, size=n_years)
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    y = (
        2.0 * x1
        - 1.5 * x2
        + firm_fe[firm]
        + year_fe[year]
        + rng.normal(scale=0.5, size=n)
    )
    return pd.DataFrame({"y": y, "x1": x1, "x2": x2, "firm": firm, "year": year})


def csdid(n_units: int, seed: int = 42) -> pd.DataFrame:
    """Balanced staggered panel, periods 1..5, cohorts first treated in 2, 3, 4.

    60% never treated; the treated 40% split equally across the three
    cohorts. Cohort g has g - 1 pre-treatment periods on both sides.
    """
    t = CSDID_T
    rng = np.random.default_rng(seed)
    units = np.repeat(np.arange(1, n_units + 1), t)
    years = np.tile(np.arange(1, t + 1), n_units)
    cohort = np.zeros(n_units, dtype=int)
    treated_idx = rng.choice(n_units, size=int(0.4 * n_units), replace=False)
    third = len(treated_idx) // 3
    cohort[treated_idx[:third]] = 2
    cohort[treated_idx[third : 2 * third]] = 3
    cohort[treated_idx[2 * third :]] = 4
    first_treat = cohort[units - 1]
    treat = ((first_treat > 0) & (years >= first_treat)).astype(int)
    unit_fe = rng.normal(0, 0.5, size=n_units)
    year_fe = rng.normal(0, 0.3, size=t)
    eps = rng.normal(0, 0.4, size=n_units * t)
    y = unit_fe[units - 1] + year_fe[years - 1] - 0.05 * treat + eps
    return pd.DataFrame(
        {
            "y": y,
            "unit": units,
            "year": years,
            "first_treat": first_treat,
            "treat": treat,
        }
    )


def scm(n_donors: int, seed: int = 42) -> pd.DataFrame:
    """Two-factor panel; unit 1 is treated from 1985, units 2.. are donors."""
    rng = np.random.default_rng(seed)
    n_units = n_donors + 1
    F = rng.normal(0, 1, size=(SCM_T, 2))
    lam = rng.normal(0, 1, size=(n_units, 2))
    years = np.arange(1970, 1970 + SCM_T)
    rows = []
    for i in range(n_units):
        eps = rng.normal(0, 0.3, size=SCM_T)
        for s, year in enumerate(years):
            rows.append(
                {
                    "unit_id": i + 1,
                    "unit_name": f"unit{i + 1}",
                    "year": int(year),
                    "y": float(lam[i] @ F[s] + eps[s]),
                }
            )
    return pd.DataFrame(rows)


def dml(n: int, p: int = 5, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, p))
    d = ((X[:, 0] + 0.5 * X[:, 1] + rng.normal(size=n)) > 0).astype(int)
    y = 0.5 * d + X.sum(axis=1) * 0.1 + rng.normal(size=n)
    cols = {f"x{i + 1}": X[:, i] for i in range(p)}
    cols["d"] = d
    cols["y"] = y
    return pd.DataFrame(cols)


GENERATORS = {"01_hdfe": hdfe, "02_csdid": csdid, "03_scm": scm, "04_dml": dml}


def path_for(estimator: str, n: int) -> Path:
    return DATA_DIR / f"{estimator}_{n}.csv"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def materialize(estimator: str, n: int) -> tuple[Path, str]:
    """Write (if absent) and hash the input for one benchmark row."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = path_for(estimator, n)
    if not path.exists():
        df = GENERATORS[estimator](n)
        tmp = path.with_suffix(".tmp")
        df.to_csv(tmp, index=False, float_format="%.17g", lineterminator="\n")
        tmp.replace(path)
    return path, sha256(path)


def load(estimator: str, n: int) -> tuple[pd.DataFrame, str]:
    """Read one benchmark input exactly as the R side does, plus its hash."""
    path, digest = materialize(estimator, n)
    return pd.read_csv(path), digest


def main() -> None:
    manifest = {}
    for est, sizes in SIZES.items():
        for n in sizes:
            path, digest = materialize(est, n)
            manifest[path.name] = digest
            print(f"{path.name:28s} {digest[:16]}")
    (DATA_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
