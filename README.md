# GROMACS Insight Platform

GROMACS Insight Platform is a Streamlit application for inspecting common GROMACS `.xvg` outputs (for example RMSD, RMSF, radius of gyration, SASA, hydrogen bonds, energy, temperature, and pressure) without writing custom notebooks.

It parses uploaded files, auto-detects metric type using filename/header heuristics, provides interactive plots, computes descriptive statistics, runs heuristic equilibration/stability checks, and exports Markdown/PDF reports.

## Key Features

- Parse `.xvg` files with Grace-style headers and numeric tables
- Heuristic file-type detection from filename and axis/title text
- Interactive Plotly visualizations (line, scatter, area)
- Optional moving-average overlay and Y-axis log scale
- RMSF residue ranking for high-flexibility residues
- Heuristic equilibration estimate for time-series metrics
- Per-metric stability scoring and aggregate quality scoring
- Pairwise Welch t-test comparisons for same metric types
- Export parsed CSV, chart images (PNG/SVG/PDF), Markdown report, and PDF report

## Repository Layout

```text
app.py                  Streamlit UI and orchestration
src/
  __init__.py
  parser.py             XVG parsing and file-type detection
  statistics.py         Descriptive and comparative statistics
  analysis.py           Equilibration/stability heuristics and explainers
  visualization.py      Plotly figure builders and export helpers
  report.py             Markdown/PDF report generation
tests/
  test_parser.py
  test_statistics.py
  test_analysis.py
requirements.txt        Runtime and test dependencies
CONTRIBUTING.md         Contribution workflow
```

## Requirements

- Python 3.10+
- pip

## Installation

```bash
pip install -r requirements.txt
```

### Optional static image export dependency

Plotly static export via Kaleido requires a local Chrome/Chromium installation.

```bash
plotly_get_chrome
```

If Chrome is unavailable, the app still works; only static image export buttons fail gracefully.

## Run the App

```bash
streamlit run app.py
```

## Run Tests

```bash
pytest -q
```

## Supported Input Expectations

- Text files in GROMACS/Grace-like format
- Header lines starting with `#` or `@`
- Whitespace-separated numeric columns
- First column interpreted as time for time-series metrics
- RMSF detected as non-time-series and treated as residue-indexed data

## Scientific Scope and Limitations

This project is intended for exploratory analysis and fast triage, not as a standalone publication-grade statistical workflow.

- Equilibration detection is heuristic (block-based), not a replacement for statistical inefficiency methods (for example `pymbar.timeseries.detect_equilibration`).
- Quality score is a heuristic composite and should not be interpreted as proof of physical validity.
- Welch t-test outputs do **not** correct for MD time autocorrelation; p-values are approximate signals only.
- Interpret biological meaning from domain expertise and raw trajectory context, not from a single score.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

This project is licensed under the [MIT License](LICENSE).
