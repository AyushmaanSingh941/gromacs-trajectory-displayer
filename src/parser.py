"""
parser.py — reads GROMACS .xvg and .log output and figures out what kind of
data it is.

GROMACS analysis tools (gmx rms, gmx gyrate, gmx sasa, gmx energy, ...) all
dump the same basic xvg format: '#' comment lines, '@' xmgrace directives
for titles/axis labels/legends, then whitespace-separated numeric columns.
The actual meaning of those columns depends entirely on which gmx command
produced the file, so on top of the raw parsing this module also takes a
guess at the file type from the filename + header text. That guess drives
a lot of the downstream analysis (e.g. RMSF files aren't time series, so
they need to be treated differently from everything else).

mdrun's .log file is a different beast: it's a big, mostly free-form text
log, but every nstenergy/nstlog steps it prints a fixed-width "Energies
(kJ/mol)" table (Bond, Angle, Potential, Temperature, Pressure, ...) right
after a "Step / Time" pair. parse_log() scans the whole file for those
tables and stacks them into a time series with the same ParsedXvg shape
that parse_xvg() produces, so callers don't need to special-case which
kind of file they got.
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
    """Everything we pulled out of one .xvg (or .log) file."""
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
    """Main entry point for .xvg files — bytes in, a fully-populated
    ParsedXvg out.

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


# ---------------------------------------------------------------------------
# .log parsing
# ---------------------------------------------------------------------------
#
# mdrun's .log file repeats a block like this every nstenergy/nstlog steps,
# buried among a lot of other free-form text (neighbor searching, DD load
# balancing, etc):
#
#            Step           Time
#               0        0.00000
#
#    Energies (kJ/mol)
#            Bond          Angle    Proper Dih.  Improper Dih.          LJ-14
#     4.19267e+02    1.02252e+03    3.15570e+02    1.32399e+01    3.19409e+02
#      Coulomb-14        LJ (SR)   Disper. corr.   Coulomb (SR)   Coul. recip.
#     4.02241e+03   -1.23456e+03   -5.67890e+01   -1.98765e+04    1.23456e+01
#       Potential    Kinetic En.   Total Energy  Conserved En.    Temperature
#    -1.45678e+04    2.34567e+03   -1.22222e+04   -1.22222e+04    3.01234e+02
#  Pres. DC (bar) Pressure (bar)   Constr. rmsd
#    -1.23456e+01    1.23456e+00    1.23456e-05
#
# The tricky part is that labels like "Proper Dih." or "Coul. recip." have
# spaces in them, so a naive .split() on whitespace misaligns labels with
# values. GROMACS prints these as fixed-width, right-justified columns
# though (same width for every column in a given gmx build), so instead we
# figure out the column count from the value line (numbers never contain
# spaces, so split() is safe there) and then slice the label line into that
# many equal-width chunks.

_STEP_TIME_RE = re.compile(
    r"^[ \t]*Step[ \t]+Time[ \t]*\n"
    r"[ \t]*(\d+)[ \t]+([-+0-9.eE]+)[ \t]*$",
    re.MULTILINE,
)
_ENERGY_HEADER_RE = re.compile(r"Energies \(kJ/mol\)[ \t]*")

# how far past a "Step / Time" line we're willing to look for the matching
# "Energies (kJ/mol)" header before giving up (there can be a fair bit of
# other mdrun chatter — DD/PME load balancing, warnings, etc. — in between)
_ENERGY_SEARCH_WINDOW_CHARS = 6000


def _parse_energy_block_lines(block_lines: list[str]) -> dict[str, float]:
    """Parse the alternating label/value line pairs under an
    'Energies (kJ/mol)' header into a {label: value} dict.

    Each pair is handled independently: if one pair's columns don't line
    up cleanly (odd whitespace, a one-off copy/paste artifact, etc.) we
    skip just that pair and keep going, rather than risk mislabeling a
    value OR aborting the whole block and silently losing everything
    after it (e.g. Temperature/Pressure, which show up in later pairs).
    """
    energies: dict[str, float] = {}
    i = 0
    while i + 1 < len(block_lines):
        label_line = block_lines[i]
        value_line = block_lines[i + 1]
        i += 2

        value_tokens = value_line.split()
        if not value_tokens or not label_line.strip():
            continue
        try:
            values = [float(v) for v in value_tokens]
        except ValueError:
            continue

        n = len(values)
        width = len(label_line) // n if n else 0
        if width <= 0 or len(label_line) != width * n:
            # columns didn't line up with the values for this pair —
            # skip just this pair, other pairs in the block are unaffected
            continue

        for col in range(n):
            label = label_line[col * width:(col + 1) * width].strip()
            if label:
                energies[label] = values[col]

    return energies


def _iter_log_energy_frames(raw_text: str):
    """Yield one {'Step': ..., 'Time': ..., <energy terms>...} dict per
    Step/Time + Energies(kJ/mol) pair found anywhere in a .log file."""
    step_matches = list(_STEP_TIME_RE.finditer(raw_text))

    for idx, m in enumerate(step_matches):
        step, time = m.group(1), m.group(2)

        window_end = (
            step_matches[idx + 1].start() if idx + 1 < len(step_matches)
            else min(len(raw_text), m.end() + _ENERGY_SEARCH_WINDOW_CHARS)
        )
        window = raw_text[m.end():window_end]

        header = _ENERGY_HEADER_RE.search(window)
        if not header:
            continue

        # collect lines until the first blank line, skipping the blank
        # line that immediately follows the header itself
        remaining_lines = window[header.end():].splitlines()
        start = 0
        while start < len(remaining_lines) and remaining_lines[start].strip() == "":
            start += 1

        block_lines = []
        for line in remaining_lines[start:]:
            if line.strip() == "":
                break
            block_lines.append(line)

        energies = _parse_energy_block_lines(block_lines)
        if not energies:
            continue

        try:
            frame = {"Time": float(time), "Step": float(step)}
        except ValueError:
            continue
        frame.update(energies)
        yield frame


def parse_log(filename: str, file_bytes: bytes) -> ParsedXvg:
    """Main entry point for .log files — bytes in, a ParsedXvg out.

    Scans the whole file for every 'Step / Time' + 'Energies (kJ/mol)'
    table (there's one roughly every nstenergy/nstlog steps) and stacks
    them into a time series DataFrame shaped just like the ones parse_xvg()
    produces for gmx energy .xvg output: Time as the first column, every
    other numeric quantity (Step, Bond, Angle, ..., Temperature, Pressure,
    ...) as a y-series next to it.

    Returns an object with an empty df if no energy tables could be found;
    callers should check `.df.empty` rather than expecting an exception.
    """
    raw_text = file_bytes.decode("utf-8", errors="replace").replace("\r\n", "\n")

    empty_result = ParsedXvg(
        filename=filename, df=pd.DataFrame(), metadata_lines=[], axis_labels=[],
        title="", x_label="", y_label="", filetype="unknown",
        is_timeseries=True, size_kb=len(file_bytes) / 1024,
    )

    frames = list(_iter_log_energy_frames(raw_text))
    if not frames:
        return empty_result

    # not every frame is guaranteed to report the exact same set of energy
    # terms (e.g. a run that adds free-energy output partway through), so
    # union the columns in first-seen order instead of assuming the first
    # frame has them all
    ordered_cols: list[str] = ["Time", "Step"]
    for frame in frames:
        for key in frame:
            if key not in ordered_cols:
                ordered_cols.append(key)

    df = pd.DataFrame(frames, columns=ordered_cols)
    df = df.sort_values("Time", kind="stable").reset_index(drop=True)

    downcast = False
    if len(df) > LARGE_FILE_ROW_THRESHOLD:
        df = df.astype(np.float32)
        downcast = True

    y_terms = [c for c in df.columns if c not in ("Time",)]

    return ParsedXvg(
        filename=filename,
        df=df,
        metadata_lines=[],
        axis_labels=[],
        title=f"Energies — {filename}",
        x_label="Time (ps)",
        y_label="Value",
        filetype="energy",
        is_timeseries=True,
        size_kb=len(file_bytes) / 1024,
        downcast_to_f32=downcast,
    )
    # (y_terms kept above only for readability/debugging; ParsedXvg.y_cols
    # already derives the same thing from df.columns[1:])


def parse_file(filename: str, file_bytes: bytes) -> ParsedXvg:
    """Convenience dispatcher: routes to parse_log() for .log files and
    parse_xvg() for everything else (.xvg being the expected case)."""
    if filename.lower().endswith(".log"):
        return parse_log(filename, file_bytes)
    return parse_xvg(filename, file_bytes)