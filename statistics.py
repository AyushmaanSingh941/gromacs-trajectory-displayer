"""
parser.py — reads GROMACS .xvg output and figures out what kind of data it is.

GROMACS analysis tools (gmx rms, gmx gyrate, gmx sasa, gmx energy, ...) all
dump the same basic xvg format: '#' comment lines, '@' xmgrace directives
for titles/axis labels/legends, then whitespace-separated numeric columns.
The actual meaning of those columns depends entirely on which gmx command
produced the file, so on top of the raw parsing this module also takes a
guess at the file type from the filename + header text. That guess drives
a lot of the downstream analysis (e.g. RMSF files aren't time series, so
they need to be treated differently from everything else).
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# above this many rows we switch to float32 to keep memory sane — GROMACS
# trajectories logged every step can easily be a few hundred thousand lines
LARGE_FILE_ROW_THRESHOLD = 200_000

# filename hints -> file type. checked as substrings against the lowercased
# filename first since that's usually the most reliable signal (gmx's
# default output names are pretty consistent across labs)
FILENAME_HINTS = {
    "rmsd":        "rmsd",
    "rmsf":        "rmsf",
    "gyrate":      "gyration",
    "sasa":        "sasa",
    "hbnum":       "hbonds",
    "hbond":       "hbonds",
    "energy":      "energy",
    "ener":        "energy",
    "temp":        "temperature",
    "pres":        "pressure",
}

# fallback: keyword hints pulled from the xmgrace title/axis text, for when
# someone renamed the file or it came from a script instead of gmx directly
TEXT_HINTS = [
    (re.compile(r"rmsf|fluctuation", re.I),                 "rmsf"),
    (re.compile(r"rmsd|root.mean.square.deviation", re.I),  "rmsd"),
    (re.compile(r"radius of gyration|gyrate|r_g", re.I),    "gyration"),
    (re.compile(r"sasa|solvent.access", re.I),               "sasa"),
    (re.compile(r"hydrogen bond|h.?bond", re.I),              "hbonds"),
    (re.compile(r"temperature", re.I),                        "temperature"),
    (re.compile(r"pressure", re.I),                           "pressure"),
    (re.compile(r"potential|total energy|kinetic", re.I),     "energy"),
]

# file types where the x-axis is NOT time (RMSF is per-residue/per-atom)
NON_TIMESERIES_TYPES = {"rmsf"}

FRIENDLY_NAMES = {
    "rmsd": "RMSD",
    "rmsf": "RMSF",
    "gyration": "Radius of Gyration",
    "sasa": "SASA",
    "hbonds": "Hydrogen Bonds",
    "energy": "Energy",
    "temperature": "Temperature",
    "pressure": "Pressure",
    "unknown": "Unrecognized",
}


@dataclass
class ParsedXvg:
    """Everything we pulled out of one .xvg file."""
    filename: str
    df: pd.DataFrame
    metadata_lines: list[str]
    axis_labels: list[str]
    title: str
    x_label: str
    y_label: str
    filetype: str                 # one of FRIENDLY_NAMES keys
    is_timeseries: bool
    size_kb: float
    downcast_to_f32: bool = False

    @property
    def friendly_type(self) -> str:
        return FRIENDLY_NAMES.get(self.filetype, "Unrecognized")

    @property
    def x_col(self) -> str:
        return self.df.columns[0]

    @property
    def y_cols(self) -> list[str]:
        return list(self.df.columns[1:])


def _split_header_and_data(raw_text: str) -> tuple[list[str], list[str], list[str]]:
    metadata_lines, axis_labels, data_lines = [], [], []
    for line in raw_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            metadata_lines.append(stripped)
        elif stripped.startswith("@"):
            axis_labels.append(stripped)
        elif stripped:
            data_lines.append(stripped)
    return metadata_lines, axis_labels, data_lines


def _parse_numeric_block(data_lines: list[str]) -> tuple[np.ndarray, bool]:
    """Turn the data lines into a numpy array, fast path first.

    Returns (array, was_downcast). np.genfromtxt does the heavy lifting in
    C and is a lot faster than a Python-level float() loop on big files,
    but it pads short/broken rows with nan instead of erroring — so on
    anything that comes back with nans we fall back to the slow, careful
    line-by-line parser that just skips whatever doesn't convert.
    """
    data_block = "\n".join(data_lines)

    try:
        array = np.genfromtxt(io.StringIO(data_block))
        if array.ndim == 1:
            array = array.reshape(1, -1)
        if array.size == 0 or np.isnan(array).any():
            raise ValueError("ragged or empty block, falling back")
    except Exception:
        clean_rows = []
        for row in data_lines:
            vals = row.split()
            if not vals:
                continue
            try:
                clean_rows.append([float(v) for v in vals])
            except ValueError:
                continue
        if not clean_rows:
            return np.empty((0, 0)), False
        array = np.array(clean_rows, dtype=np.float64)
        if array.ndim == 1:
            array = array.reshape(1, -1)

    downcast = False
    if array.shape[0] > LARGE_FILE_ROW_THRESHOLD:
        array = array.astype(np.float32)
        downcast = True

    return array, downcast


def _extract_legend_names(axis_labels: list[str]) -> dict[int, str]:
    legend_names = {}
    for lbl in axis_labels:
        if "legend" not in lbl.lower():
            continue
        parts = lbl.split('"')
        if len(parts) < 2:
            continue
        legend_text = parts[1]
        tokens = lbl.split()
        for i, tok in enumerate(tokens):
            if tok.lower() == "legend" and i > 0:
                series_token = tokens[i - 1]
                if series_token.startswith("s") and series_token[1:].isdigit():
                    legend_names[int(series_token[1:])] = legend_text
                break
    return legend_names


def _extract_axis_text(axis_labels: list[str]) -> dict:
    info = {"title": "", "xaxis": "", "yaxis": ""}
    for line in axis_labels:
        lower = line.lower()
        parts = line.split('"')
        if len(parts) < 2:
            continue
        text = parts[1]
        if lower.startswith("@ title") or lower.startswith("@title"):
            info["title"] = text
        elif "xaxis" in lower and "label" in lower:
            info["xaxis"] = text
        elif "yaxis" in lower and "label" in lower:
            info["yaxis"] = text
    return info


def detect_filetype(filename: str, title: str, x_label: str, y_label: str) -> str:
    """Guess what kind of gmx output this is. Filename first (most reliable
    in practice), then falls back to scanning the title/axis text."""
    lower_name = filename.lower()
    for hint, ftype in FILENAME_HINTS.items():
        if hint in lower_name:
            return ftype

    combined_text = " ".join([title, x_label, y_label])
    for pattern, ftype in TEXT_HINTS:
        if pattern.search(combined_text):
            return ftype

    return "unknown"


def parse_xvg(filename: str, file_bytes: bytes) -> ParsedXvg:
    """Main entry point — bytes in, a fully-populated ParsedXvg out.

    Returns an object with an empty df if nothing usable could be parsed;
    callers should check `.df.empty` rather than expecting an exception.
    """
    raw_text = file_bytes.decode("utf-8", errors="replace")
    metadata_lines, axis_labels, data_lines = _split_header_and_data(raw_text)

    empty_result = ParsedXvg(
        filename=filename, df=pd.DataFrame(), metadata_lines=metadata_lines,
        axis_labels=axis_labels, title="", x_label="", y_label="",
        filetype="unknown", is_timeseries=True, size_kb=len(file_bytes) / 1024,
    )

    if not data_lines:
        return empty_result

    array, downcast = _parse_numeric_block(data_lines)
    if array.size == 0:
        return empty_result

    n_cols = array.shape[1]
    legend_names = _extract_legend_names(axis_labels)
    axis_text = _extract_axis_text(axis_labels)

    ftype = detect_filetype(filename, axis_text["title"], axis_text["xaxis"], axis_text["yaxis"])
    is_timeseries = ftype not in NON_TIMESERIES_TYPES

    col_names = ["Residue" if ftype == "rmsf" else "Time"]
    for i in range(1, n_cols):
        col_names.append(legend_names.get(i - 1, f"Value_{i}"))
    while len(col_names) < n_cols:
        col_names.append(f"Value_{len(col_names)}")

    df = pd.DataFrame(array, columns=col_names[:n_cols])

    return ParsedXvg(
        filename=filename,
        df=df,
        metadata_lines=metadata_lines,
        axis_labels=axis_labels,
        title=axis_text["title"] or FRIENDLY_NAMES.get(ftype, filename),
        x_label=axis_text["xaxis"] or ("Residue" if ftype == "rmsf" else "Time (ps)"),
        y_label=axis_text["yaxis"] or "Value",
        filetype=ftype,
        is_timeseries=is_timeseries,
        size_kb=len(file_bytes) / 1024,
        downcast_to_f32=downcast,
    )
