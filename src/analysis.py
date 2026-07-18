"""
analysis.py — the "is this simulation any good" layer.

Two things live here:
  - estimate_equilibration(): a heuristic for where a time series settles down
  - quality_score(): a composite 0-100 score for quick triage across a run

Both are explicitly heuristics, not established statistical methods, and
the docstrings say so. If you need a citation-ready equilibration point,
look at pymbar's detectEquilibration (reverse cumulative averaging +
statistical inefficiency) — this is a lightweight stand-in for "does this
look roughly flat yet", good for a first pass across a folder of files,
not for the methods section of a paper.
"""

from __future__ import annotations

import numpy as np

from .parser import FRIENDLY_NAMES


def estimate_equilibration(time_arr, values, n_blocks: int = 20,
                            tail_fraction: float = 0.25, tolerance: float = 1.0) -> dict:
    """Chop the series into n_blocks blocks, treat the mean/std of the
    last `tail_fraction` of the run as the "equilibrated" reference, then
    walk forward from the start looking for the first block that lands
    within `tolerance` reference-std of that reference AND stays there
    for every block after it (so a single lucky block doesn't count).
    """
    time_arr = np.asarray(time_arr, dtype=float)
    values = np.asarray(values, dtype=float)
    n = values.size

    if n < n_blocks * 2:
        return {
            "equilibrated": False,
            "eq_time": None,
            "message": "Not enough frames to make a meaningful equilibration estimate.",
        }

    block_size = n // n_blocks
    block_means, block_start_idx = [], []
    for b in range(n_blocks):
        start = b * block_size
        end = n if b == n_blocks - 1 else (b + 1) * block_size
        block_means.append(values[start:end].mean())
        block_start_idx.append(start)

    tail_start = int(n * (1 - tail_fraction))
    ref_mean = values[tail_start:].mean()
    ref_std = values[tail_start:].std()
    if ref_std == 0:
        ref_std = 1e-9  # dead flat tail — avoid a divide by zero, not a real signal

    eq_block = None
    for b in range(n_blocks):
        if abs(block_means[b] - ref_mean) <= tolerance * ref_std:
            if all(abs(bm - ref_mean) <= tolerance * ref_std for bm in block_means[b:]):
                eq_block = b
                break

    if eq_block is None:
        return {
            "equilibrated": False,
            "eq_time": None,
            "message": "No clear equilibration point — the signal never settles "
                       "within tolerance of its final segment over the sampled window.",
        }

    eq_idx = block_start_idx[eq_block]
    eq_time = time_arr[eq_idx]

    pre_var = values[:eq_idx].var() if eq_idx > 0 else values.var()
    post_var = values[eq_idx:].var()
    reduction_pct = 0.0 if pre_var == 0 else (1 - post_var / pre_var) * 100

    return {
        "equilibrated": True,
        "eq_time": float(eq_time),
        "eq_index": eq_idx,
        "variance_reduction_pct": float(reduction_pct),
        "message": f"Estimated equilibration around {eq_time:.3g} "
                   f"(variance dropped ~{reduction_pct:.0f}% after this point).",
    }


def _linear_drift_slope(time_arr, values) -> float:
    """Slope of a straight-line fit over the back half of the run — used
    as a stand-in for 'is this still trending' for quantities like
    pressure/energy where raw fluctuation size isn't the useful signal."""
    time_arr = np.asarray(time_arr, dtype=float)
    values = np.asarray(values, dtype=float)
    n = values.size
    if n < 4:
        return 0.0
    half = n // 2
    t, v = time_arr[half:], values[half:]
    if np.allclose(t, t[0]):
        return 0.0
    slope, _ = np.polyfit(t, v, 1)
    return float(slope)


def rmsd_stability_score(time_arr, values) -> dict:
    """Lower post-equilibration coefficient of variation = more stable."""
    eq = estimate_equilibration(time_arr, values)
    tail = values[eq["eq_index"]:] if eq["equilibrated"] else values
    mean = np.mean(tail)
    cv = (np.std(tail) / mean) if mean else float("inf")
    # a CV under ~5% is a reasonably flat RMSD plateau in practice; above
    # ~20% it's still moving around a lot. this scale is a rule of thumb,
    # not a standard
    score = float(np.clip(100 - cv * 500, 0, 100))
    return {"score": score, "cv": cv, "equilibration": eq}


def temperature_stability_score(values, target: float | None = None) -> dict:
    """Temperature has an explicit setpoint (the thermostat), so std
    relative to the mean is actually meaningful here, unlike pressure."""
    values = np.asarray(values, dtype=float)
    mean = values.mean()
    std = values.std()
    cv = std / mean if mean else float("inf")
    score = float(np.clip(100 - cv * 2000, 0, 100))  # thermostats usually keep this well under 1%
    return {"score": score, "cv": cv, "mean": mean, "std": std}


def pressure_stability_score(time_arr, values) -> dict:
    """Pressure is noisy by nature in MD (virial fluctuations are large
    even in a well-behaved NPT run), so scoring it on raw std would
    unfairly punish a healthy simulation. What actually matters is
    whether the running average is drifting — so this scores the slope
    of a linear fit over the back half of the run instead."""
    values = np.asarray(values, dtype=float)
    slope = _linear_drift_slope(time_arr, values)
    scale = (values.std() or 1.0)
    normalized_drift = abs(slope) / scale
    score = float(np.clip(100 - normalized_drift * 5000, 0, 100))
    return {"score": score, "drift_slope": slope}


def energy_stability_score(time_arr, values) -> dict:
    """Same idea as pressure — look for drift, not raw noise."""
    values = np.asarray(values, dtype=float)
    slope = _linear_drift_slope(time_arr, values)
    scale = (values.std() or 1.0)
    normalized_drift = abs(slope) / scale
    score = float(np.clip(100 - normalized_drift * 5000, 0, 100))
    return {"score": score, "drift_slope": slope}


def compute_stability_component(filetype: str, time_arr, values) -> tuple[str, float | None, dict]:
    """Routes to the right scorer for a given detected file type and hands
    back (label, score-or-None, raw details). Kept here instead of in
    app.py so the "which metric gets which treatment" logic lives in one
    place next to the scorers themselves.
    """
    if filetype == "rmsd":
        details = rmsd_stability_score(time_arr, values)
        return "RMSD", details["score"], details
    if filetype in ("gyration", "sasa", "hbonds"):
        # these plateau the same way RMSD does, so the same CV-based
        # scoring logic applies even though the physical quantity differs
        details = rmsd_stability_score(time_arr, values)
        return FRIENDLY_NAMES.get(filetype, filetype), details["score"], details
    if filetype == "temperature":
        details = temperature_stability_score(values)
        return "Temperature", details["score"], details
    if filetype == "pressure":
        details = pressure_stability_score(time_arr, values)
        return "Pressure", details["score"], details
    if filetype == "energy":
        details = energy_stability_score(time_arr, values)
        return "Energy", details["score"], details
    return FRIENDLY_NAMES.get(filetype, filetype), None, {}


def quality_score(component_scores: dict[str, float]) -> dict:
    """Average whatever component sub-scores are available (not every
    upload will have temperature/pressure/energy/RMSD all present) and
    generate a few plain-language warnings off the weak spots.

    This number is a triage aid, nothing more — it doesn't prove a
    trajectory is "correct" or that any downstream biology holds up.
    Always look at the actual plots before trusting a single number.
    """
    available = {k: v for k, v in component_scores.items() if v is not None}

    if not available:
        return {"overall": None, "components": {}, "warnings": [], "recommendations": []}

    overall = float(np.mean(list(available.values())))

    warnings, recommendations = [], []
    for name, score in available.items():
        if score < 50:
            warnings.append(f"{name} stability is low ({score:.0f}/100) — worth a closer look.")
            if name == "RMSD":
                recommendations.append("RMSD hasn't settled — consider a longer run or check for a bad starting structure.")
            elif name == "Temperature":
                recommendations.append("Temperature is fluctuating more than expected — check thermostat coupling.")
            elif name == "Pressure":
                recommendations.append("Pressure shows a persistent drift — check barostat coupling constants and box equilibration.")
            elif name == "Energy":
                recommendations.append("Energy is still trending — the system may not be fully equilibrated yet.")
        elif score < 75:
            warnings.append(f"{name} is borderline ({score:.0f}/100).")

    return {
        "overall": overall,
        "components": available,
        "n_components": len(available),
        "warnings": warnings,
        "recommendations": recommendations,
    }


def explain_metric(question: str, filetype: str, stats: dict, equilibration: dict | None,
                    quality: dict | None) -> str:
    """Template-based explainer, deliberately NOT hooked up to any LLM.

    It only ever reports numbers that were actually computed elsewhere in
    this module — it pattern-matches on a few keywords in the question and
    fills in a canned sentence with real values. That's a hard constraint,
    not a shortcut: an assistant that free-generates explanations of
    simulation quality is exactly the kind of thing that quietly
    hallucinates a plausible-sounding but wrong answer, which is worse
    than no answer for a research tool. Wire up a real LLM here later if
    you want, but keep it grounded to computed values only.
    """
    q = question.lower()
    friendly = FRIENDLY_NAMES.get(filetype, filetype)

    if any(w in q for w in ["trend", "increas", "decreas", "drift"]):
        if equilibration and equilibration.get("equilibrated"):
            return (f"Based on the computed values, {friendly} settles down around "
                     f"{equilibration['eq_time']:.3g}, with variance dropping about "
                     f"{equilibration['variance_reduction_pct']:.0f}% after that point. "
                     f"Before that it's still moving — after it, changes look like noise "
                     f"around a stable mean rather than a real trend.")
        elif equilibration:
            return (f"The equilibration check didn't find a clear settling point for "
                     f"{friendly} in this window — it may still be trending, or the run "
                     f"may just be too short to tell.")
        return f"No equilibration analysis is available for {friendly} yet."

    if any(w in q for w in ["stable", "quality", "good", "ok", "okay"]):
        if quality and quality.get("overall") is not None:
            return (f"The composite quality score for this file is "
                     f"{quality['overall']:.0f}/100 across {quality['n_components']} "
                     f"metric(s). " + (" ".join(quality["warnings"]) if quality["warnings"]
                     else "No components fell below the warning threshold."))
        return "Not enough metrics were available to compute a quality score for this file."

    if any(w in q for w in ["mean", "average"]):
        return f"The mean value for {friendly} is {stats['mean']:.4g} (n={stats['n']}, std={stats['std']:.4g})."

    return (f"I can only report what's actually been computed — mean is "
            f"{stats['mean']:.4g}, std is {stats['std']:.4g}. Try asking about the "
            f"trend, stability, or the average specifically.")


def top_flexible_residues(residue_ids, rmsf_values, top_n: int = 10):
    """Just sorts residues by RMSF descending and hands back the top N —
    the useful part is having this in one place so the app and any
    scripts calling into it agree on what 'top flexible' means."""
    residue_ids = np.asarray(residue_ids)
    rmsf_values = np.asarray(rmsf_values, dtype=float)
    order = np.argsort(rmsf_values)[::-1][:top_n]
    return [(int(residue_ids[i]), float(rmsf_values[i])) for i in order]
