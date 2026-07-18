"""
statistics.py — the plain stats layer everything else builds on.

Nothing fancy here on purpose: mean/median/std/CI/moving average/
correlation, plus a two-sample comparison for WT-vs-mutant type
questions. Kept separate from analysis.py because these are generic
enough to be useful outside the equilibration/quality-score stuff.
"""

from __future__ import annotations

import numpy as np
from scipy import stats as sp_stats


def descriptive_stats(values) -> dict:
    """Mean/median/std/var/sem/95% CI/min/max/n for a 1D series."""
    arr = np.asarray(values, dtype=float)
    arr = arr[~np.isnan(arr)]
    n = arr.size

    if n == 0:
        return {k: float("nan") for k in
                ["mean", "median", "std", "var", "sem", "ci_low", "ci_high", "min", "max"]} | {"n": 0}

    result = {
        "n": n,
        "mean": arr.mean(),
        "median": float(np.median(arr)),
        "std": arr.std(ddof=1) if n > 1 else 0.0,
        "var": arr.var(ddof=1) if n > 1 else 0.0,
        "min": arr.min(),
        "max": arr.max(),
    }

    ci_low, ci_high = confidence_interval(arr)
    result["sem"] = sp_stats.sem(arr) if n > 1 else 0.0
    result["ci_low"] = ci_low
    result["ci_high"] = ci_high
    return result


def confidence_interval(values, confidence: float = 0.95) -> tuple[float, float]:
    """95% CI on the mean via a t-distribution. Not adjusted for
    autocorrelation — for time series data (which MD trajectories are)
    the *true* uncertainty is wider than this reports, since consecutive
    frames aren't independent samples. Fine for a quick look."""
    arr = np.asarray(values, dtype=float)
    arr = arr[~np.isnan(arr)]
    n = arr.size
    if n < 2:
        return (float("nan"), float("nan"))

    mean = arr.mean()
    sem = sp_stats.sem(arr)
    margin = sem * sp_stats.t.ppf((1 + confidence) / 2, n - 1)
    return (mean - margin, mean + margin)


def moving_average(values, window: int):
    """Centered rolling mean, pandas under the hood — window edges use
    whatever's available rather than going NaN so the line doesn't get
    chewed off at the start/end of the plot."""
    import pandas as pd
    series = pd.Series(np.asarray(values, dtype=float))
    return series.rolling(window=max(window, 1), min_periods=1, center=True).mean().to_numpy()


def rolling_std(values, window: int):
    import pandas as pd
    series = pd.Series(np.asarray(values, dtype=float))
    return series.rolling(window=max(window, 2), min_periods=1, center=True).std().fillna(0).to_numpy()


def correlation_matrix(df, columns: list[str]):
    """Pearson correlation between the given columns. Just a thin wrapper
    but nice to have in one place instead of every caller writing
    `df[cols].corr()` themselves."""
    return df[columns].corr()


def compare_two_samples(a, label_a: str, b, label_b: str) -> dict:
    """Welch's t-test between two series (unequal variance assumed —
    generally the safer default when comparing two different simulations).

    Important caveat, and it's a real one: frames within an MD trajectory
    are autocorrelated, so treating every frame as an independent sample
    inflates the effective n and makes the p-value look more significant
    than it really is. Report this as a rough signal, not a citable test,
    unless the input has already been decorrelated (e.g. via block
    averaging or a statistical-inefficiency estimate).
    """
    arr_a = np.asarray(a, dtype=float)
    arr_b = np.asarray(b, dtype=float)
    arr_a = arr_a[~np.isnan(arr_a)]
    arr_b = arr_b[~np.isnan(arr_b)]

    if arr_a.size < 2 or arr_b.size < 2:
        return {
            "label_a": label_a, "label_b": label_b,
            "mean_a": arr_a.mean() if arr_a.size else float("nan"),
            "mean_b": arr_b.mean() if arr_b.size else float("nan"),
            "mean_diff": float("nan"), "t_stat": float("nan"), "p_value": float("nan"),
            "caveat": "Not enough data points in one of the series to run a t-test.",
        }

    t_stat, p_value = sp_stats.ttest_ind(arr_a, arr_b, equal_var=False)

    return {
        "label_a": label_a,
        "label_b": label_b,
        "mean_a": arr_a.mean(),
        "mean_b": arr_b.mean(),
        "mean_diff": arr_a.mean() - arr_b.mean(),
        "t_stat": t_stat,
        "p_value": p_value,
        "caveat": (
            "MD frames are autocorrelated in time, so this naive t-test "
            "almost certainly overstates significance — treat the p-value "
            "as a rough signal, not a rigorous test, unless the inputs "
            "have been decorrelated first (block averaging, etc.)."
        ),
    }
