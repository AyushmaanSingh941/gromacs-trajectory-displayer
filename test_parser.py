import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analysis import (estimate_equilibration, explain_metric,
                           quality_score, top_flexible_residues)


def _synthetic_settling_series(n=1000, settle_at_frac=0.4, seed=0):
    """Builds a series that drifts for the first chunk then settles down —
    a controlled case where we know roughly where equilibration "should"
    land, so the heuristic has something concrete to be checked against."""
    rng = np.random.default_rng(seed)
    settle_idx = int(n * settle_at_frac)
    time = np.arange(n, dtype=float)
    drift = np.linspace(2.0, 0.5, settle_idx)
    flat = 0.5 + rng.normal(0, 0.02, n - settle_idx)
    values = np.concatenate([drift + rng.normal(0, 0.02, settle_idx), flat])
    return time, values, settle_idx


def test_equilibration_detects_roughly_the_right_region():
    time, values, settle_idx = _synthetic_settling_series()
    result = estimate_equilibration(time, values)
    assert result["equilibrated"] is True
    # allow a generous window either side given this is block-based, not exact
    assert abs(result["eq_index"] - settle_idx) < len(values) * 0.15


def test_equilibration_flat_signal_settles_immediately():
    time = np.arange(200, dtype=float)
    values = np.full(200, 3.0)
    result = estimate_equilibration(time, values)
    assert result["equilibrated"] is True
    assert result["eq_index"] <= 20  # should catch on almost right away


def test_equilibration_too_short_series_returns_gracefully():
    result = estimate_equilibration([0, 1, 2], [1, 1, 1])
    assert result["equilibrated"] is False


def test_quality_score_averages_available_components():
    result = quality_score({"RMSD": 90, "Temperature": 80, "Pressure": None})
    assert result["n_components"] == 2
    assert 80 <= result["overall"] <= 90


def test_quality_score_flags_low_components():
    result = quality_score({"RMSD": 30})
    assert any("RMSD" in w for w in result["warnings"])
    assert result["recommendations"]


def test_quality_score_no_components():
    result = quality_score({})
    assert result["overall"] is None


def test_top_flexible_residues_ranks_correctly():
    ids = [1, 2, 3, 4]
    rmsf = [0.1, 0.5, 0.05, 0.3]
    top2 = top_flexible_residues(ids, rmsf, top_n=2)
    assert top2[0][0] == 2  # highest RMSF
    assert top2[1][0] == 4


def test_explain_metric_stays_grounded_in_provided_numbers():
    stats = {"mean": 1.23, "std": 0.05, "n": 100}
    answer = explain_metric("what's the average?", "rmsd", stats, None, None)
    assert "1.23" in answer
