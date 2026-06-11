import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.statistics import (compare_two_samples, confidence_interval,
                             descriptive_stats, moving_average, rolling_std)


def test_descriptive_stats_known_values():
    values = [1, 2, 3, 4, 5]
    stats = descriptive_stats(values)
    assert stats["n"] == 5
    assert stats["mean"] == 3.0
    assert stats["median"] == 3.0
    assert abs(stats["std"] - np.std(values, ddof=1)) < 1e-9


def test_descriptive_stats_empty_input():
    stats = descriptive_stats([])
    assert stats["n"] == 0
    assert np.isnan(stats["mean"])


def test_confidence_interval_widens_with_more_variance():
    tight = confidence_interval([10, 10.1, 9.9, 10.05, 9.95])
    wide = confidence_interval([0, 20, 5, 15, 10])
    tight_width = tight[1] - tight[0]
    wide_width = wide[1] - wide[0]
    assert wide_width > tight_width


def test_moving_average_smooths_noise():
    rng = np.random.default_rng(0)
    noisy = 5 + rng.normal(0, 1, 200)
    smoothed = moving_average(noisy, window=20)
    assert np.std(smoothed) < np.std(noisy)
    assert len(smoothed) == len(noisy)


def test_rolling_std_no_nans():
    values = np.arange(50)
    result = rolling_std(values, window=5)
    assert not np.isnan(result).any()


def test_compare_two_samples_detects_obvious_difference():
    a = np.random.default_rng(1).normal(0, 0.1, 100)
    b = np.random.default_rng(2).normal(5, 0.1, 100)
    result = compare_two_samples(a, "A", b, "B")
    assert result["p_value"] < 0.001
    assert result["mean_diff"] < -4  # a is centered near 0, b near 5
    assert "caveat" in result
