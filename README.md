GROMACS Insight Platform
A Streamlit app for poking at GROMACS `.xvg` output without writing a new
MDAnalysis script every time. Upload RMSD/RMSF/Rg/SASA/H-bond/energy/
temperature/pressure files, get them auto-classified, run an equilibration
quality check, compare runs against each other, and export a report.
Install
```bash
pip install -r requirements.txt

# figure export (PNG/SVG/PDF) needs a local Chrome install for kaleido —
# run this once, or those specific export buttons will just show a
# friendly error and everything else still works fine
plotly_get_chrome
```
Run
```bash
streamlit run app.py
```
Run the tests
```bash
pytest tests/ -v
```
Layout
```
app.py                 Streamlit UI — wiring only, no analysis logic lives here
src/
  parser.py             .xvg parsing + file-type auto-detection (filename + header text)
  statistics.py          mean/median/std/CI/moving average/correlation/two-sample comparison
  analysis.py             equilibration heuristic, per-filetype stability scoring, quality score,
                           rule-based (non-LLM) metric explainer, RMSF residue ranking
  visualization.py        Plotly figure builders (dark theme) + PNG/SVG/PDF export
  report.py               markdown report builder + a simple reportlab PDF export
tests/                  pytest coverage for parser/statistics/analysis
```
What "auto-detection" actually does
File type is guessed from the filename first (`rmsd.xvg`, `gyrate.xvg`, etc. —
gmx's default output names are pretty consistent), and falls back to
scanning the xmgrace title/axis text if the filename doesn't give it away.
It's a heuristic, not a parser of GROMACS internals — if you've renamed
your files to something unrecognizable with no useful title, it'll come
back "Unrecognized" and you still get raw stats, just no equilibration/
quality scoring on top.
About the equilibration and quality-score numbers
Both are explicitly heuristics, documented as such in the docstrings in
`analysis.py`:
Equilibration estimate: block-averaging against the mean/std of the
final quarter of the run. It's a reasonable first pass, not a
statistical-inefficiency method. If you need a citable equilibration
point, look at `pymbar.timeseries.detect_equilibration`.
Quality score: a 0–100 composite built from whatever stability
metrics are available for a given file (RMSD/Rg/SASA/H-bonds use a
coefficient-of-variation-based plateau score; temperature uses std
relative to its setpoint; pressure and energy use drift over the back
half of the run instead of raw noise, since pressure especially is
expected to be noisy in a healthy NPT simulation). It's a triage aid for
scanning a folder of output quickly — not a validated benchmark, and it
doesn't prove anything about protein stability or biology. Always look
at the actual plot before trusting the number.
Comparison p-values: computed with Welch's t-test, with a caveat
attached every time they're shown — MD frames are autocorrelated in
time, so treating every frame as an independent sample overstates
significance. Treat it as a rough signal.
Example workflow
Run a WT and a mutant simulation in GROMACS, get `rmsd.xvg`,
`rmsf.xvg`, `gyrate.xvg`, and `energy.xvg` out of `gmx rms` / `gmx rmsf`
/ `gmx gyrate` / `gmx energy` for each.
Upload all of them at once — the sidebar badges will show what got
detected as what.
Use Quick View to eyeball a couple of runs overlaid before doing
anything else.
Hit Analyze. Each timeseries file gets an equilibration estimate
and quality score; RMSF files get a per-residue flexibility plot with
the top N flagged automatically.
If two files share a detected type (e.g. two `rmsd.xvg` from WT vs
mutant), a comparison section shows up automatically with the mean
difference and a caveated significance test.
Download the markdown or PDF report to keep with the rest of your run's
notes.
Known limitations / what's simplified
The PDF report is a plain, functional layout (reportlab) — not
journal-typeset. The markdown report is the more flexible format if
you want to fold it into something else.
No literal LLM is wired in. The "explain this metric" box is a
template-based responder that only ever restates numbers already
computed elsewhere in the app — deliberately, so it can't hallucinate
an explanation. Swapping in a real model call is a reasonable follow-up
if you want free-text Q&A, just keep it grounded to computed values.
Statistical comparisons don't correct for autocorrelation — see the
caveat above.
RMSF handling assumes the standard `gmx rmsf` per-residue output
(residue index in column 1). Per-atom RMSF or custom residue
numbering will still parse, but the x-axis label just says "Residue."
If you want to take this further
Swap the rule-based explainer for a real LLM call, keeping the prompt
scoped strictly to the computed stats so it can't invent numbers.
Add `pymbar` for a statistically rigorous equilibration/decorrelation
step before the comparison t-tests.
Batch mode / CLI wrapper around `src/` for analyzing a whole directory
of runs without going through the UI, if this turns into something
worth publishing as a standalone tool.
