# GROMACS Insight Platform

A Streamlit app for fast, interactive analysis of GROMACS molecular dynamics simulations without writing a new MDAnalysis script every time. Upload RMSD/RMSF/Rg/SASA/H-bond/energy/temperature/pressure files, auto-classify them, run equilibration + quality checks, compare runs side-by-side, and export a report.

## Features

- **Auto-detection** of GROMACS file types (RMSD, RMSF, Rg, SASA, H-bonds, energy, temperature, pressure) from filename + header text
- **Interactive visualization** with Plotly (line/scatter/area charts, log-scale support, moving-average overlay)
- **Quick View** for exploratory plotting before running formal analysis
- **Equilibration estimation** using block-averaging heuristics (flagged settling point + variance reduction %)
- **Quality scoring** (0–100 composite) built from stability metrics relevant to each file type:
  - RMSD/Rg/SASA/H-bonds: coefficient-of-variation plateau score
  - Temperature: std relative to setpoint
  - Pressure/energy: drift over back-half of run (not raw noise, since both are naturally noisy in MD)
- **Per-residue RMSF ranking** with top-N flexible residues auto-identified
- **Comparison statistics** (Welch's t-test with caveat: frames are autocorrelated, so p-values are rough signals only)
- **Report export** in markdown (easy to diff/share) and PDF (readable, portable)
- **Raw data export** as CSV for downstream analysis
- **Dark theme** optimized for data visualization (GitHub-style palette)

## What it is NOT

- **Not a LLM playground**: the "explain this metric" box is template-based, only reports numbers already computed, never invents values
- **Not a statistical gold standard**: equilibration and quality scores are heuristics for quick triage; for citable work, use `pymbar.timeseries.detect_equilibration`
- **Not adjusted for autocorrelation**: t-tests treat MD frames as independent samples (they're not), so p-values overstate significance — use them as rough signals only
- **Not a trajectory parser**: works with analysis tool output (.xvg files), not the trajectory itself

## Quick Start

### 1. Install Python 3.8+

```bash
python --version
```

### 2. Clone & set up

```bash
git clone https://github.com/AyushmaanSingh941/gromacs-trajectory-displayer.git
cd gromacs-trajectory-displayer
```

### 3. Create virtual environment

```bash
python -m venv venv
source venv/bin/activate        # macOS/Linux
# or
venv\Scripts\activate           # Windows
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

If you want to export figures as PNG/SVG/PDF, install kaleido once:

```bash
plotly_get_chrome
```

(Everything else works fine without it — export buttons just show a friendly error.)

### 5. Run

```bash
streamlit run app.py
```

Open http://localhost:8501 in your browser.

## Usage Workflow

1. **Upload files** in the sidebar — drop in `rmsd.xvg`, `rmsf.xvg`, `energy.xvg`, etc. Upload multiple to compare replicas or WT vs. mutant.
2. **Check badges** to confirm file types were auto-detected correctly.
3. **Quick View** — eyeball one or more runs overlaid before doing anything formal. Adjust chart type, markers, downsampling.
4. **Hit Analyze** — each timeseries gets equilibration estimate + quality score. RMSF files get per-residue ranking. If two files share a type, a comparison appears.
5. **Read warnings** if any metrics fall below threshold. Review recommendations.
6. **Download report** in markdown or PDF to keep with your simulation notes.

## Layout

```
app.py                          Streamlit UI — wiring only, no analysis logic here
src/
  parser.py                     .xvg parsing + file-type auto-detection
  statistics.py                 mean/median/std/CI/moving average/correlation/t-test
  analysis.py                   equilibration heuristic, stability scoring, quality score,
                                rule-based metric explainer, RMSF residue ranking
  visualization.py              Plotly dark-theme figures + PNG/SVG/PDF export
  report.py                     markdown + PDF report builders
tests/
  test_parser.py                tests for file parsing
  test_statistics.py            tests for statistics
  test_analysis.py              tests for equilibration/quality/scoring logic
requirements.txt                Python dependencies
LICENSE                         MIT
```

## File Format

GROMACS `.xvg` output and equivalent `.txt` files. Standard xmgrace format:

```
# Comments (start with #)
@ xaxis label "Time (ps)"
@ yaxis label "RMSD (nm)"
@ s0 legend "Backbone"
@s1 legend "Side chains"

0.0   0.245   0.312
1.0   0.247   0.315
2.0   0.251   0.318
```

The parser handles:
- Comment lines starting with `#` (skipped)
- xmgrace directives starting with `@` (parsed for titles/labels/legends or skipped)
- Whitespace-separated numeric columns

## Auto-Detection Heuristics

File type is guessed from **filename first** (most reliable — GROMACS defaults like `rmsd.xvg` are consistent), **falling back to xmgrace title/axis text** if the filename isn't obvious. If both fail, the file comes back "Unrecognized" but you still get raw stats.

Common hints:
- `rmsd.xvg` → RMSD
- `rmsf.xvg` → RMSF (per-residue, not time-series)
- `gyrate.xvg` → Radius of gyration
- `sasa.xvg` → Solvent-accessible surface area
- `hbnum.xvg` or `hbond.xvg` → Hydrogen bond count
- `energy.xvg` → Potential energy
- `temperature` in filename → Temperature
- `pressure` in filename → Pressure

If you renamed files or generated output with custom scripts, try naming them consistently with GROMACS conventions, or add descriptive text to the title.

## About the Scores

### Equilibration Estimate

Block-averaged signal against mean/std of final 25% of run. It's a first-pass heuristic:
- **Good for**: quick triage across many files, spotting obviously non-equilibrated runs
- **Not good for**: publication-grade equilibration detection (use `pymbar.timeseries.detect_equilibration`)
- **Output**: frame index where signal settles + variance reduction % after that point

### Quality Score (0–100 Composite)

Averaged across whatever metrics are present:

| File type | Metric | How it works |
|-----------|--------|-------------|
| RMSD, Rg, SASA, H-bonds | Coefficient of variation (std/mean) | Lower CV = more stable. Scaled so ~5% CV → high score, ~20% → low. |
| Temperature | CV relative to mean | Thermostats keep this tight. High std = thermostat coupling issue. |
| Pressure | Linear drift (back half of run) | Pressure is naturally noisy, so we score drift, not raw noise. |
| Energy | Linear drift (back half of run) | Same logic as pressure. |

Score is a **triage aid**, not a validated benchmark:
- < 50/100 → worth a closer look (warning + suggestion)
- 50–75/100 → borderline
- > 75/100 → looks reasonable
- **Always look at the plots yourself.** A high score doesn't prove stability or biology.

### Comparison p-values

Computed with Welch's t-test (unequal variance assumed). **Critical caveat**: MD frames are autocorrelated in time, so treating every frame as independent overstates significance. Use these as **rough signals only**, not citable tests. For rigor, decorrelate first (block averaging, etc.).

## Running Tests

```bash
pytest tests/ -v
```

Coverage:
- `test_parser.py` — file parsing, type detection, edge cases (empty files, malformed data)
- `test_statistics.py` — descriptive stats, CI, moving average, t-test
- `test_analysis.py` — equilibration detection, stability scoring, quality score logic

## Known Limitations

- **PDF report** is functional but plain (reportlab) — not journal-typeset. Markdown is more flexible.
- **No LLM involved** — metric explainer is template-based (by design — no hallucination risk).
- **Autocorrelation not corrected** — t-tests assume independence, which MD violates.
- **RMSF assumes per-residue output** — per-atom RMSF or custom numbering still parses but loses axis context.

## Next Steps

If you want to extend this:

1. **Real LLM integration**: swap the rule-based explainer for an actual model call, keeping it strictly grounded to computed values.
2. **Rigorous equilibration**: add `pymbar` for statistical-inefficiency-based detection + proper decorrelation before t-tests.
3. **Batch/CLI mode**: wrap `src/` analysis in a command-line tool for analyzing whole directories without the UI.
4. **Custom parsers**: add support for other analysis tools (gromacs-plus, AMBER, CHARMM formats) alongside xvg.

## Dependencies

| Package | Version | Why |
|---------|---------|-----|
| streamlit | ≥1.38 | Web UI |
| pandas | ≥2.0 | Data tables |
| numpy | ≥1.24 | Numerical ops |
| plotly | ≥5.20 | Interactive charts |
| scipy | ≥1.11 | Statistics (t-test, sem, CI) |
| kaleido | ≥0.2.1 | PNG/SVG/PDF export (optional after `plotly_get_chrome`) |
| reportlab | ≥4.0 | PDF report generation |
| pytest | ≥7.4 | Test runner |

## System Requirements

- **OS**: Windows, macOS, or Linux
- **Python**: 3.8+
- **RAM**: 512 MB minimum (2 GB recommended for large files >100k frames)
- **Disk**: ~500 MB for dependencies + small amount for logs
- **Browser**: Any modern browser (Chrome, Firefox, Safari, Edge)

## Troubleshooting

### "Module not found" errors
Activate venv and reinstall:
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### Slow rendering with large files
Use the "Display every Nth frame" slider to downsample visualization (doesn't affect summary stats or export):
```
Files with >50k frames: try N=5–10
Files with >200k frames: try N=20–50
```

### File upload fails
- Verify the file is valid .xvg or .txt
- Check it contains numeric data (columns of numbers after the `@`/`#` headers)
- Confirm headers start with `#` (comment) or `@` (xmgrace directive)

### "Address already in use" error
Wait 1–2 minutes for the previous Streamlit server to shut down, or use a different port:
```bash
streamlit run app.py --server.port 8502
```

### PNG/SVG/PDF export shows error
You need to install Chrome for kaleido once:
```bash
plotly_get_chrome
```
Everything else (markdown, CSV, on-screen charts) works fine without it.

## Citation

If you use this in a publication, please cite:

```bibtex
@software{singh2026gromacs,
  title={GROMACS Insight Platform},
  author={Singh, Ayushman},
  year={2026},
  url={https://github.com/AyushmaanSingh941/gromacs-trajectory-displayer}
}
```

## License

MIT License. See [LICENSE](LICENSE) for details.

## Support

- **Bug reports**: Open an [issue](https://github.com/AyushmaanSingh941/gromacs-trajectory-displayer/issues)
- **Feature requests**: Open a [discussion](https://github.com/AyushmaanSingh941/gromacs-trajectory-displayer/discussions)
- **Contributing**: See [CONTRIBUTING.md](CONTRIBUTING.md)

---

Built for researchers who want to spend time on biology, not boilerplate. Simple codebase, extensible from the start.
