"""Small-sample statistics for the eval reports (pure Python + NumPy, no SciPy).

Our eval sets have 60-80 items, so every rate is reported with an uncertainty range, and paired comparisons
(the same questions under two configurations) use paired tests rather than comparing two averages.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

Z_95 = 1.959963984540054  # two-sided 95% normal quantile
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20261125  # fixed so reports are reproducible
SIGNIFICANCE_LEVEL = 0.05


def wilson_interval(successes: int, n: int, z: float = Z_95) -> tuple[float, float]:
    """95% Wilson score interval for a proportion; stays inside [0, 1] and behaves at 0% and 100%."""
    if n <= 0:
        return (0.0, 0.0)
    if not 0 <= successes <= n:
        raise ValueError(f"successes={successes} must be between 0 and n={n}")
    p = successes / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    low = 0.0 if successes == 0 else max(0.0, centre - half)  # exact endpoints (avoid 0.9999999 from rounding)
    high = 1.0 if successes == n else min(1.0, centre + half)
    return (low, high)


def mcnemar_exact(only_a: int, only_b: int) -> float:
    """Two-sided exact McNemar p-value from the discordant pairs.

    `only_a` = items config A got right and B got wrong; `only_b` = the reverse. Concordant pairs carry no
    information about which config is better, so only these two counts matter.
    """
    if only_a < 0 or only_b < 0:
        raise ValueError("discordant counts must be non-negative")
    n = only_a + only_b
    if n == 0:
        return 1.0
    k = min(only_a, only_b)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2.0**n
    return min(1.0, 2.0 * tail)


def paired_outcome_test(a: Sequence[bool], b: Sequence[bool]) -> dict[str, float | int | bool]:
    """McNemar comparison of two configs' pass/fail on the same items (a[i] and b[i] are the same item)."""
    if len(a) != len(b):
        raise ValueError("paired outcomes must have equal length")
    only_a = sum(1 for x, y in zip(a, b) if x and not y)
    only_b = sum(1 for x, y in zip(a, b) if y and not x)
    p_value = mcnemar_exact(only_a, only_b)
    return {"n": len(a), "only_a": only_a, "only_b": only_b, "p_value": round(p_value, 4),
            "significant": p_value < SIGNIFICANCE_LEVEL}


def cohen_kappa(labels_a: Sequence[str], labels_b: Sequence[str]) -> float | None:
    """Agreement between two raters beyond chance (1 = perfect, 0 = chance level); None if undefined."""
    if len(labels_a) != len(labels_b):
        raise ValueError("rater label lists must have equal length")
    n = len(labels_a)
    if n == 0:
        return None
    observed = sum(1 for x, y in zip(labels_a, labels_b) if x == y) / n
    categories = set(labels_a) | set(labels_b)
    expected = sum((list(labels_a).count(c) / n) * (list(labels_b).count(c) / n) for c in categories)
    if expected >= 1.0:
        return None  # both raters used one identical label throughout: kappa is undefined
    return (observed - expected) / (1.0 - expected)


def paired_bootstrap_diff(a: Sequence[float], b: Sequence[float], resamples: int = BOOTSTRAP_RESAMPLES,
                          seed: int = BOOTSTRAP_SEED) -> dict[str, float | int | bool]:
    """Mean of (a - b) over paired items with a 95% percentile bootstrap interval."""
    if len(a) != len(b):
        raise ValueError("paired samples must have equal length")
    if not a:
        return {"n": 0, "mean_diff": 0.0, "ci_low": 0.0, "ci_high": 0.0, "significant": False}
    diffs = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    rng = np.random.default_rng(seed)
    means = diffs[rng.integers(0, len(diffs), size=(resamples, len(diffs)))].mean(axis=1)
    low, high = np.percentile(means, [100 * SIGNIFICANCE_LEVEL / 2, 100 * (1 - SIGNIFICANCE_LEVEL / 2)])
    return {"n": len(diffs), "mean_diff": round(float(diffs.mean()), 4), "ci_low": round(float(low), 4),
            "ci_high": round(float(high), 4), "significant": bool(low > 0 or high < 0)}
