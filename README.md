# =============================================================================
# GROMACS Insight Platform — app.py
#
# Upload GROMACS .xvg output, get it auto-classified (RMSD/RMSF/Rg/SASA/
# H-bonds/energy/temperature/pressure), poke at it in Quick View, then hit
# Analyze for equilibration estimates, a rough quality score, comparisons
# across files, and a downloadable report.
#
# Split across src/ (parser, statistics, analysis, visualization, report) —
# this file is just the UI wiring.
# =============================================================================

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st
import pandas as pd

pd.set_option("styler.render.max_elements", 2000000)

from src import analysis, report, statistics as stats_mod, visualization as viz
from src.parser import FRIENDLY_NAMES, parse_xvg


st.set_page_config(
    page_title="GROMACS Insight Platform",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)


# dark "deep space lab" theme, teal accent to match molecular viz tools
st.markdown("""
<style>
    .stApp {
        background-color: #0D1117;
        color: #C9D1D9;
        font-family: 'Inter', 'Segoe UI', sans-serif;
    }
    [data-testid="stSidebar"] {
        background-color: #161B22;
        border-right: 1px solid #21262D;
    }
    [data-testid="stSidebar"] .stMarkdown p,
    [data-testid="stSidebar"] label {
        color: #8B949E;
        font-size: 0.82rem;
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }
    .hero-title {
        font-size: 2.1rem;
        font-weight: 700;
        color: #E6EDF3;
        letter-spacing: -0.02em;
        line-height: 1.15;
        margin-bottom: 0.15rem;
    }
    .hero-subtitle {
        font-size: 1rem;
        color: #8B949E;
        margin-bottom: 1.8rem;
    }
    .accent { color: #00C8C8; }
    .metric-card {
        background: #161B22;
        border: 1px solid #21262D;
        border-radius: 8px;
        padding: 1rem 1.2rem;
        text-align: center;
    }
    .metric-value {
        font-size: 1.5rem;
        font-weight: 600;
        color: #00C8C8;
        font-family: 'Roboto Mono', 'Courier New', monospace;
    }
    .metric-label {
        font-size: 0.75rem;
        color: #8B949E;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        margin-top: 0.2rem;
    }
    .section-header {
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #8B949E;
        border-bottom: 1px solid #21262D;
        padding-bottom: 0.4rem;
        margin: 1.2rem 0 0.8rem;
    }
    .filetype-badge {
        display: inline-block;
        background: #161B22;
        border: 1px solid #21262D;
        border-radius: 999px;
        padding: 0.2rem 0.7rem;
        font-size: 0.75rem;
        color: #00C8C8;
        font-family: 'Roboto Mono', monospace;
        margin-right: 0.4rem;
    }
    [data-testid="stFileUploadDropzone"] {
        background-color: #0D1117 !important;
        border: 1px dashed #30363D !important;
        border-radius: 8px !important;
    }
    [data-testid="stDataFrame"] {
        border: 1px solid #21262D;
        border-radius: 8px;
        overflow: hidden;
    }
    .block-container { padding-top: 2rem; }
    .stSelectbox div[data-baseweb="select"] > div,
    .stNumberInput input {
        background-color: #161B22 !important;
        border-color: #30363D !important;
        color: #C9D1D9 !important;
    }
    .stAlert { border-radius: 8px; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def _cached_parse(filename: str, file_bytes: bytes):
    # streamlit can't cache a dataclass with a DataFrame inside directly in
    # older versions without some coaxing, but it handles it fine as long
    # as the inputs (filename + bytes) are hashable, which they are
    return parse_xvg(filename, file_bytes)


def parse_uploaded_files(files):
    parsed, failed = {}, []
    for f in files:
        result = _cached_parse(f.name, f.read())
        if result.df.empty:
            failed.append(f.name)
        else:
            parsed[f.name] = result
    return parsed, failed


# ---------------------------------------------------------------------------
# sidebar
# ---------------------------------------------------------------------------

with st.sidebar:

    st.markdown("""
    <div style="padding: 0.5rem 0 1.5rem;">
        <span style="font-size:1.5rem;">🧬</span>
        <span style="font-size:1rem; font-weight:700; color:#E6EDF3;
                     letter-spacing:-0.01em; margin-left:0.5rem;">
            GROMACS<span style="color:#00C8C8;">Insight</span>
        </span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
        <div style="background: #161B22; padding: 0.6rem; border: 1px solid #21262D; border-radius: 6px; text-align: center; margin: 1rem 0;">
            <div style="font-size: 0.7rem; color: #8B949E; text-transform: uppercase; letter-spacing: 0.05em;">Analysis Engine</div>
            <div style="font-size: 1.1rem; font-weight: 600; color: #00C8C8; font-family: monospace;">ACTIVE ● ONLINE</div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="section-header">Input Files</div>', unsafe_allow_html=True)

    uploaded_files = st.file_uploader(
        label="Upload GROMACS .xvg files",
        type=["xvg", "txt"],
        accept_multiple_files=True,
        help="Drop in rmsd.xvg, rmsf.xvg, gyrate.xvg, energy.xvg, whatever you've "
             "got. Upload more than one to compare replicas, mutants, or conditions."
    )

    st.markdown('<div class="section-header">Chart Options</div>', unsafe_allow_html=True)

    chart_type = st.selectbox("Chart type", options=["Line", "Scatter", "Area"], index=0)
    show_markers = st.checkbox("Show data point markers", value=False)
    downsample = st.slider("Display every Nth frame", min_value=1, max_value=100, value=1, step=1,
                           help="Speeds up rendering for long trajectories. Doesn't affect exports.")

    st.markdown('<div class="section-header">Analysis</div>', unsafe_allow_html=True)

    time_unit = st.radio("Time axis unit", options=["ps", "ns"], index=0, horizontal=True,
                        help="GROMACS writes time in ps natively. Exports always keep native ps.")
    show_moving_avg = st.checkbox("Overlay moving average", value=False,
                                  help="Rolling-mean line on top of the raw signal — useful for noisy RMSD/Rg.")
    ma_window = st.slider("Moving average window (frames)", min_value=2, max_value=200, value=10, step=1)
    log_y = st.checkbox("Log scale (Y axis)", value=False)

    st.markdown("---")
    st.markdown("""
    <p style="font-size:0.75rem; color:#484F58; line-height:1.6;">
        Auto-detects RMSD, RMSF, Rg, SASA, H-bonds, energy, temperature,
        and pressure files. Runs equilibration + quality checks and builds
        a downloadable report.<br><br>
        Built with Streamlit · Plotly · SciPy
    </p>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# main content
# ---------------------------------------------------------------------------

st.markdown("""
<p class="hero-title">
    GROMACS Insight <span class="accent">Platform</span>
</p>
<p class="hero-subtitle">
    Upload simulation output, auto-detect what it is, and get equilibration
    checks, a quality score, and a report — without hand-rolling another
    analysis notebook.
</p>
""", unsafe_allow_html=True)


if not uploaded_files:
    _, center_col, _ = st.columns([1, 2, 1])
    with center_col:
        st.markdown("""
        <div style="background:#161B22; border:1px dashed #30363D; border-radius:12px;
                    padding:3rem 2rem; text-align:center; margin-top:2rem;">
            <div style="font-size:3rem; margin-bottom:1rem;">📂</div>
            <p style="color:#E6EDF3; font-size:1rem; font-weight:600; margin-bottom:0.4rem;">
                No files loaded yet
            </p>
            <p style="color:#8B949E; font-size:0.85rem; line-height:1.6;">
                Use the <strong style="color:#C9D1D9;">sidebar</strong> to upload one or more
                GROMACS <code>.xvg</code> files.<br>
                Upload several to compare replicas or WT vs mutant runs side by side.
            </p>
        </div>
        """, unsafe_allow_html=True)
    st.stop()


with st.spinner("Parsing file(s)…"):
    parsed_files, failed_files = parse_uploaded_files(uploaded_files)

if failed_files:
    st.warning("Couldn't extract numeric data from: " + ", ".join(failed_files) + " — skipping those.")

if not parsed_files:
    st.error("None of the uploaded files had usable data. Check they contain numbers after the `@`/`#` headers.")
    st.stop()


# ---- detected file badges --------------------------------------------------

st.markdown('<div class="section-header">Detected Files</div>', unsafe_allow_html=True)
badge_html = ""
for fname, pf in parsed_files.items():
    badge_html += f'<span class="filetype-badge">{fname} → {pf.friendly_type} ({len(pf.df):,} rows)</span>'
st.markdown(badge_html, unsafe_allow_html=True)
st.markdown("")


time_divisor = 1000 if time_unit == "ns" else 1


# ---------------------------------------------------------------------------
# Quick View — exploratory plotting, same idea as the original dashboard
# ---------------------------------------------------------------------------

st.markdown('<div class="section-header">Quick View</div>', unsafe_allow_html=True)

timeseries_files = {k: v for k, v in parsed_files.items() if v.is_timeseries}
rmsf_files = {k: v for k, v in parsed_files.items() if not v.is_timeseries}

if timeseries_files:
    pick_options = list(timeseries_files.keys())
    quick_pick = st.multiselect("Files to plot", options=pick_options, default=pick_options[:1])

    if quick_pick:
        # union of column names across the picked files so a shared legend
        # (e.g. everyone has "RMSD") can be overlaid in one chart
        common_cols = set()
        for fname in quick_pick:
            common_cols.update(timeseries_files[fname].y_cols)
        common_cols = sorted(common_cols)

        quick_col = st.selectbox("Column to plot", options=common_cols)

        frames = []
        for fname in quick_pick:
            pf = timeseries_files[fname]
            if quick_col not in pf.df.columns:
                continue
            sub = pf.df[[pf.x_col, quick_col]].copy()
            sub.columns = ["Time", "Value"]
            if downsample > 1:
                sub = sub.iloc[::downsample].reset_index(drop=True)
            sub["Time"] = sub["Time"] / time_divisor
            sub["Source"] = fname
            frames.append(sub)

        if frames:
            combined = pd.concat(frames, ignore_index=True)
            x_title = f"Time ({time_unit})"

            if len(quick_pick) == 1:
                fig = viz.timeseries_figure(
                    combined.rename(columns={"Value": quick_col}), "Time", [quick_col],
                    chart_type, f"{quick_col}", x_title, quick_col,
                    show_markers=show_markers, log_y=log_y
                )
            else:
                fig = viz.comparison_figure(
                    combined, "Time", "Value", "Source", chart_type,
                    f"{quick_col} comparison", x_title, quick_col, log_y=log_y
                )

            if show_moving_avg:
                for i, src in enumerate(combined["Source"].unique()):
                    sub = combined[combined["Source"] == src]
                    smoothed = stats_mod.moving_average(sub["Value"], ma_window)
                    fig = viz.add_moving_average_trace(fig, sub["Time"], smoothed, src,
                                                       viz.COLORS[i % len(viz.COLORS)])

            st.plotly_chart(fig, use_container_width=True)

            export_cols = st.columns(4)
            for fmt, col in zip(["png", "svg", "pdf"], export_cols[:3]):
                with col:
                    try:
                        img_bytes = viz.export_figure_bytes(fig, fmt)
                        st.download_button(f"⬇ {fmt.upper()}", data=img_bytes,
                                          file_name=f"{quick_col}_chart.{fmt}", key=f"quickview_{fmt}")
                    except Exception:
                        st.caption(f"{fmt.upper()} export needs Chrome installed for kaleido "
                                  f"(`plotly_get_chrome`).")
else:
    st.caption("No time-series files in this upload — see the RMSF section below if applicable.")

if rmsf_files:
    st.markdown('<div class="section-header">Per-Residue RMSF</div>', unsafe_allow_html=True)
    for fname, pf in rmsf_files.items():
        residues = pf.df[pf.x_col]
        rmsf_vals = pf.df[pf.y_cols[0]]
        top_n = st.slider(f"Top N flexible residues — {fname}", 3, 25, 10, key=f"topn_{fname}")
        top_residues = analysis.top_flexible_residues(residues, rmsf_vals, top_n=top_n)
        highlight_ids = [r for r, _ in top_residues]

        fig = viz.rmsf_figure(residues, rmsf_vals, highlight_ids=highlight_ids, title=f"RMSF — {fname}")
        st.plotly_chart(fig, use_container_width=True)

        st.markdown(f"**Top {top_n} flexible residues ({fname})**")
        st.dataframe(pd.DataFrame(top_residues, columns=["Residue", "RMSF (nm)"]),
                    use_container_width=True, height=min(300, 40 + 28 * len(top_residues)))


# ---------------------------------------------------------------------------
# Analyze — equilibration, quality score, comparisons, report
# ---------------------------------------------------------------------------

st.markdown('<div class="section-header">Analysis</div>', unsafe_allow_html=True)

if "analysis_ran" not in st.session_state:
    st.session_state["analysis_ran"] = False

if st.button("▶  Analyze", type="primary"):
    st.session_state["analysis_ran"] = True

if st.session_state["analysis_ran"]:

    files_summary = []
    per_file_scores = {}

    for fname, pf in timeseries_files.items():
        y_col = pf.y_cols[0]
        values = pf.df[y_col]
        time_arr = pf.df[pf.x_col]

        desc = stats_mod.descriptive_stats(values)
        eq = analysis.estimate_equilibration(time_arr, values)
        label, score, details = analysis.compute_stability_component(pf.filetype, time_arr, values)
        q = analysis.quality_score({label: score}) if score is not None else None

        per_file_scores[fname] = score
        files_summary.append({
            "filename": fname, "filetype": pf.filetype, "n_frames": len(pf.df),
            "stats": desc, "equilibration": eq, "quality": q,
        })

    if not files_summary:
        st.info("Nothing to analyze yet — RMSF files get their residue-level view above instead "
                "of an equilibration/quality analysis (there's no time axis to settle over).")

    for f in files_summary:
        with st.expander(f"📊  {f['filename']} — {FRIENDLY_NAMES.get(f['filetype'], f['filetype'])}", expanded=True):
            cols = st.columns(4)
            s = f["stats"]
            with cols[0]:
                st.markdown(f'<div class="metric-card"><div class="metric-value">{s["mean"]:.4g}</div>'
                           f'<div class="metric-label">Mean</div></div>', unsafe_allow_html=True)
            with cols[1]:
                st.markdown(f'<div class="metric-card"><div class="metric-value">{s["std"]:.4g}</div>'
                           f'<div class="metric-label">Std Dev</div></div>', unsafe_allow_html=True)
            with cols[2]:
                st.markdown(f'<div class="metric-card"><div class="metric-value">{s["ci_low"]:.3g} – {s["ci_high"]:.3g}</div>'
                           f'<div class="metric-label">95% CI</div></div>', unsafe_allow_html=True)
            with cols[3]:
                q = f["quality"]
                score_txt = f"{q['overall']:.0f}/100" if q and q["overall"] is not None else "N/A"
                st.markdown(f'<div class="metric-card"><div class="metric-value">{score_txt}</div>'
                           f'<div class="metric-label">Quality Score</div></div>', unsafe_allow_html=True)

            st.caption(f"ℹ️ {f['equilibration']['message']}")

            if f["quality"] and f["quality"]["warnings"]:
                for w in f["quality"]["warnings"]:
                    st.warning(w)
                for r in f["quality"]["recommendations"]:
                    st.info(r)

            question = st.text_input(f"Ask about {f['filename']}", key=f"ask_{f['filename']}",
                                     placeholder="e.g. is this stable? what's the trend?")
            if question:
                answer = analysis.explain_metric(question, f["filetype"], f["stats"],
                                                 f["equilibration"], f["quality"])
                st.markdown(f"> {answer}")
                st.caption("Rule-based explainer — only reports numbers computed above, no LLM involved.")

    # ---- comparisons across files sharing a detected type -----------------
    by_type = {}
    for f in files_summary:
        by_type.setdefault(f["filetype"], []).append(f["filename"])

    comparisons = []
    for ftype, names in by_type.items():
        if len(names) == 2:
            a_series = timeseries_files[names[0]].df[timeseries_files[names[0]].y_cols[0]]
            b_series = timeseries_files[names[1]].df[timeseries_files[names[1]].y_cols[0]]
            comparisons.append(stats_mod.compare_two_samples(a_series, names[0], b_series, names[1]))

    if comparisons:
        st.markdown('<div class="section-header">Comparisons</div>', unsafe_allow_html=True)
        for c in comparisons:
            st.markdown(f"**{c['label_a']} vs {c['label_b']}** — mean diff: `{c['mean_diff']:.4g}`, "
                       f"t = `{c['t_stat']:.3g}`, p = `{c['p_value']:.3g}`")
            st.caption(c["caveat"])

    # ---- report -------------------------------------------------------------
    st.markdown('<div class="section-header">Report</div>', unsafe_allow_html=True)

    if files_summary:
        md_report = report.build_markdown_report(files_summary, comparisons)

        report_col1, report_col2 = st.columns(2)
        with report_col1:
            st.download_button("⬇  Download Markdown Report", data=md_report.encode("utf-8"),
                              file_name="gromacs_insight_report.md", mime="text/markdown")
        with report_col2:
            try:
                pdf_bytes = report.build_pdf_report(md_report, figures=None)
                st.download_button("⬇  Download PDF Report", data=pdf_bytes,
                                  file_name="gromacs_insight_report.pdf", mime="application/pdf")
            except Exception as e:
                st.caption(f"PDF export failed ({e}). Markdown report is still available.")

        with st.expander("Preview report"):
            st.markdown(md_report)
else:
    st.caption("Click **Analyze** above to run equilibration detection, quality scoring, "
              "comparisons, and generate a report.")


# ---------------------------------------------------------------------------
# raw data / export, per file
# ---------------------------------------------------------------------------

st.markdown('<div class="section-header">Raw Data & Export</div>', unsafe_allow_html=True)

export_pick = st.selectbox("File", options=list(parsed_files.keys()), key="export_pick")
pf = parsed_files[export_pick]

table_col, stats_col = st.columns([3, 1])
with table_col:
    st.dataframe(pf.df.style.format("{:.6g}"), use_container_width=True, height=320)
with stats_col:
    st.markdown("**Descriptive Stats**")
    st.dataframe(pf.df[pf.y_cols].describe().style.format("{:.4g}"), use_container_width=True, height=320)

with st.expander("📄  File Metadata"):
    if pf.metadata_lines or pf.axis_labels:
        st.code("\n".join(pf.metadata_lines + pf.axis_labels), language="text")
    else:
        st.info("No header lines found in this file.")
    dtype_note = " (downcast to float32 for memory — large file)" if pf.downcast_to_f32 else ""
    st.caption(f"📁 {pf.filename} · {pf.size_kb:.1f} KB · {len(pf.df):,} rows · "
              f"{len(pf.df.columns)} columns{dtype_note}")

csv_buffer = pf.df.to_csv(index=False).encode("utf-8")
st.download_button("⬇  Download parsed data as CSV", data=csv_buffer,
                  file_name=export_pick.replace(".xvg", "_parsed.csv").replace(".txt", "_parsed.csv"),
                  mime="text/csv")
