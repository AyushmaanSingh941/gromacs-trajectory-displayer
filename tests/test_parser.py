import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.parser import detect_filetype, parse_xvg

SAMPLE_RMSD = b"""\
# This file was created by gmx rms
@ title "RMSD"
@ xaxis label "Time (ps)"
@ yaxis label "RMSD (nm)"
@TYPE xy
    0.0000    0.0512
    1.0000    0.0631
    2.0000    0.0598
    3.0000    0.0602
"""

SAMPLE_RMSF = b"""\
@ title "RMS fluctuation"
@ xaxis label "Residue"
@ yaxis label "RMSF (nm)"
    1    0.08
    2    0.12
    3    0.31
    4    0.09
"""

SAMPLE_MULTI_COL = b"""\
@ title "Energy"
@ s0 legend "Potential"
@ s1 legend "Kinetic"
    0.0   -412345.6   1200.1
    1.0   -412300.1   1198.4
    2.0   -412310.0   1201.9
"""

SAMPLE_GARBAGE_TAIL = b"""\
@ title "RMSD"
    0.0   0.05
    1.0   0.06
    2.0   corrupted_row garbage
    3.0   0.07
"""


def test_detect_filetype_from_filename():
    assert detect_filetype("rmsd.xvg", "", "", "") == "rmsd"
    assert detect_filetype("prot_rmsf_bb.xvg", "", "", "") == "rmsf"
    assert detect_filetype("gyrate.xvg", "", "", "") == "gyration"
    assert detect_filetype("energy_run1.xvg", "", "", "") == "energy"


def test_detect_filetype_from_title_when_filename_unhelpful():
    ftype = detect_filetype("output_final.xvg", "Radius of gyration", "Time (ps)", "Rg (nm)")
    assert ftype == "gyration"


def test_detect_filetype_unknown_when_nothing_matches():
    assert detect_filetype("weird_output.xvg", "", "", "") == "unknown"


def test_parse_rmsd_basic():
    result = parse_xvg("rmsd.xvg", SAMPLE_RMSD)
    assert not result.df.empty
    assert result.filetype == "rmsd"
    assert result.is_timeseries is True
    assert list(result.df.columns) == ["Time", "Value_1"]
    assert result.df.shape == (4, 2)
    assert abs(result.df["Value_1"].iloc[0] - 0.0512) < 1e-9


def test_parse_rmsf_uses_residue_as_x_axis():
    result = parse_xvg("rmsf.xvg", SAMPLE_RMSF)
    assert result.filetype == "rmsf"
    assert result.is_timeseries is False
    assert result.df.columns[0] == "Residue"


def test_parse_picks_up_legend_names():
    result = parse_xvg("energy.xvg", SAMPLE_MULTI_COL)
    assert list(result.df.columns) == ["Time", "Potential", "Kinetic"]
    assert result.df.shape == (3, 3)


def test_parse_skips_corrupted_rows_without_crashing():
    result = parse_xvg("rmsd.xvg", SAMPLE_GARBAGE_TAIL)
    assert not result.df.empty
    # the corrupted row should just be dropped, not crash the parse
    assert result.df.shape[0] == 3


def test_parse_empty_file_returns_empty_df():
    result = parse_xvg("empty.xvg", b"# nothing but comments\n@ title \"Empty\"\n")
    assert result.df.empty
