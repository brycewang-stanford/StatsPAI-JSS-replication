"""Write ``r2_ts_break.csv`` for the round-2 time-series parity tests.

Run from the repository root::

    python tests/reference_parity/_fixtures/_generate_r2_ts_data.py

Columns (n = 300, seed 20260918):

* ``y3``  -- three mean shifts (after observations 75, 150, 225), N(0, 1) noise
* ``yx``  -- intercept and slope on ``x`` shift after observation 120
* ``yx2`` -- two breaks in the intercept/slope (after 90 and 200)
* ``x``   -- N(0, 1) regressor
* ``wn``  -- white noise (no break)

Values are written with ``%.17g`` so every reader sees the same doubles.
"""

from pathlib import Path

import numpy as np
import pandas as pd

rng = np.random.default_rng(20260918)
n = 300
t = np.arange(1, n + 1)
x = rng.normal(size=n)
mu3 = np.select([t <= 75, t <= 150, t <= 225], [0.0, 1.2, -0.4], 0.9)
y3 = mu3 + rng.normal(size=n)
yx = np.where(t <= 120, 1.0 + 0.5 * x, 1.8 + 1.1 * x) + rng.normal(size=n)
a = np.select([t <= 90, t <= 200], [0.0, 1.0], -0.2)
b = np.select([t <= 90, t <= 200], [0.4, 1.2], 0.3)
yx2 = a + b * x + rng.normal(size=n)
wn = rng.normal(size=n)
df = pd.DataFrame({"t": t, "y3": y3, "yx": yx, "yx2": yx2, "x": x, "wn": wn})
out = Path(__file__).parent / "r2_ts_break.csv"
df.to_csv(out, index=False, float_format="%.17g")
print("wrote", out)
