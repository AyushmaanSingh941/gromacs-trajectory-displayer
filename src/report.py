"""
report.py — turns whatever the app has already computed into a downloadable
report. Markdown is the primary format (easy to diff, easy to paste into a
lab notebook); the PDF export is a simple, functional layout built with
reportlab — it's readable and fine for sharing, but it's not attempting to
be a journal-typeset figure, just a portable version of the same content.
"""

from __future__ import annotations

import io
from datetime import datetime


def build_markdown_report(files_summary: list[dict], comparisons: list[dict] | None = None) -> str:
    """
    files_summary: one dict per file, expected keys —
        filename, filetype, n_frames, stats (from statistics.descriptive_stats),
        equilibration (from analysis.estimate_equilibration or None),
        quality (from analysis.quality_score or None)
    comparisons: optional list of dicts from statistics.compare_two_samples
    """
    lines = []
    lines.append("# GROMACS Insight Report")
    lines.append(f"_Generated {datetime.now():%Y-%m-%d %H:%M}_")
    lines.append("")

    lines.append("## Simulation Overview")
    lines.append(f"- Files analyzed: {len(files_summary)}")
    for f in files_summary:
        lines.append(f"  - **{f['filename']}** — detected as *{f['filetype']}*, {f['n_frames']:,} frames")
    lines.append("")

    lines.append("## Stability Analysis")
    for f in files_summary:
        lines.append(f"### {f['filename']}")
        eq = f.get("equilibration")
        if eq:
            lines.append(f"- {eq['message']}")
        q = f.get("quality")
        if q and q.get("overall") is not None:
            lines.append(f"- Quality score: **{q['overall']:.0f}/100** (based on {q['n_components']} metric(s))")
            for w in q.get("warnings", []):
                lines.append(f"  - ⚠️ {w}")
            for r in q.get("recommendations", []):
                lines.append(f"  - → {r}")
        lines.append("")

    lines.append("## Key Statistics")
    for f in files_summary:
        s = f["stats"]
        lines.append(f"**{f['filename']}**: mean={s['mean']:.4g}, median={s['median']:.4g}, "
                     f"std={s['std']:.4g}, 95% CI=({s['ci_low']:.4g}, {s['ci_high']:.4g}), "
                     f"n={s['n']}")
    lines.append("")

    if comparisons:
        lines.append("## Comparisons")
        for c in comparisons:
            lines.append(f"**{c['label_a']} vs {c['label_b']}**: "
                         f"mean diff = {c['mean_diff']:.4g}, t = {c['t_stat']:.3g}, p = {c['p_value']:.3g}")
            lines.append(f"> {c['caveat']}")
        lines.append("")

    lines.append("## Potential Issues")
    any_issues = False
    for f in files_summary:
        q = f.get("quality")
        if q and q.get("warnings"):
            any_issues = True
            for w in q["warnings"]:
                lines.append(f"- **{f['filename']}**: {w}")
    if not any_issues:
        lines.append("- No flags raised by the automated checks — that doesn't replace looking at the plots yourself.")
    lines.append("")

    lines.append("---")
    lines.append("_This report reflects computed measurements and heuristic checks only. "
                 "It does not draw biological or pharmacological conclusions — those require "
                 "domain-level interpretation beyond what this tool calculates._")

    return "\n".join(lines)


def figure_caption(index: int, filetype: str, filenames: list[str]) -> str:
    """Auto-generates a plain, factual figure caption — no interpretation,
    just what's being shown and where it came from."""
    subject = {
        "rmsd": "RMSD", "rmsf": "RMSF", "gyration": "radius of gyration",
        "sasa": "SASA", "hbonds": "hydrogen bond count", "energy": "energy",
        "temperature": "temperature", "pressure": "pressure",
    }.get(filetype, filetype)

    if len(filenames) > 1:
        names = " vs ".join(filenames)
        return f"Figure {index}. {subject} comparison between {names}."
    return f"Figure {index}. {subject} over the course of the simulation ({filenames[0]})."


def build_pdf_report(markdown_text: str, figures: list[tuple[str, bytes]] | None = None) -> bytes:
    """Converts the markdown report into a simple PDF. Headings (#, ##, ###)
    get their own styles, everything else is body text — no fancy markdown
    parsing, just enough to make the PDF readable."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                             leftMargin=0.75 * inch, rightMargin=0.75 * inch,
                             topMargin=0.75 * inch, bottomMargin=0.75 * inch)
    styles = getSampleStyleSheet()
    story = []

    for raw_line in markdown_text.split("\n"):
        line = raw_line.strip()
        if not line:
            story.append(Spacer(1, 6))
        elif line.startswith("# "):
            story.append(Paragraph(line[2:], styles["Title"]))
        elif line.startswith("## "):
            story.append(Paragraph(line[3:], styles["Heading2"]))
        elif line.startswith("### "):
            story.append(Paragraph(line[4:], styles["Heading3"]))
        elif line.startswith("---"):
            story.append(Spacer(1, 10))
        else:
            # strip the light markdown we use (bold/italic/bullets) since
            # reportlab's Paragraph only understands a subset of html-ish tags
            clean = (line.replace("**", "")
                         .replace("_", "")
                         .replace("> ", "")
                         .lstrip("- ")
                         .lstrip("  - "))
            story.append(Paragraph(clean, styles["BodyText"]))

    if figures:
        story.append(Spacer(1, 16))
        story.append(Paragraph("Figures", styles["Heading2"]))
        for caption, png_bytes in figures:
            story.append(Spacer(1, 8))
            story.append(RLImage(io.BytesIO(png_bytes), width=5.5 * inch, height=3.2 * inch))
            story.append(Paragraph(caption, styles["Italic"]))

    doc.build(story)
    return buf.getvalue()
