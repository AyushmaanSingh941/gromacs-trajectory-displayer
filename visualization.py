"""
visualization.py — builds the Plotly figures and hands back static image
bytes for the ones the user wants to export. Same dark theme across the
board so the app doesn't look like it was stitched together.
"""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go

DARK_BG = "#0D1117"
GRID_COLOR = "#21262D"
LINE_COLOR = "#30363D"
TEXT_MUTED = "#8B949E"
TEXT_BRIGHT = "#E6EDF3"

COLORS = [
    "#00C8C8",  # teal — primary accent
    "#FF7B54",
    "#9B72CF",
    "#5CE65C",
    "#F0C040",
    "#54AAFF",
]


def _apply_dark_theme(fig, x_title: str, y_title: str, log_y: bool = False) -> go.Figure:
    fig.update_layout(
        paper_bgcolor=DARK_BG,
        plot_bgcolor=DARK_BG,
        title=dict(font=dict(family="Inter, Segoe UI, sans-serif", size=16, color=TEXT_BRIGHT),
                   x=0, xanchor="left"),
        xaxis=dict(title=dict(text=x_title, font=dict(color=TEXT_MUTED, size=12)),
                   tickfont=dict(color=TEXT_MUTED, size=10, family="Roboto Mono, Courier New, monospace"),
                   gridcolor=GRID_COLOR, linecolor=LINE_COLOR, zerolinecolor=LINE_COLOR),
        yaxis=dict(title=dict(text=y_title, font=dict(color=TEXT_MUTED, size=12)),
                   tickfont=dict(color=TEXT_MUTED, size=10, family="Roboto Mono, Courier New, monospace"),
                   gridcolor=GRID_COLOR, linecolor=LINE_COLOR, zerolinecolor=LINE_COLOR,
                   type="log" if log_y else "linear"),
        legend=dict(font=dict(color="#C9D1D9", size=11), bgcolor="#161B22",
                    bordercolor=GRID_COLOR, borderwidth=1),
        hoverlabel=dict(bgcolor="#161B22", bordercolor=LINE_COLOR,
                         font=dict(color=TEXT_BRIGHT, size=12, family="Roboto Mono, Courier New, monospace")),
        autosize=True,
        margin=dict(l=60, r=20, t=60, b=60),
    )
    return fig


def timeseries_figure(df, x_col: str, y_cols: list[str], chart_type: str,
                       title: str, x_title: str, y_title: str,
                       show_markers: bool = False, log_y: bool = False) -> go.Figure:
    kwargs = dict(x=x_col, y=y_cols, title=title, labels={x_col: x_title},
                  color_discrete_sequence=COLORS)

    if chart_type == "Line":
        fig = px.line(df, **kwargs)
        if show_markers:
            fig.update_traces(mode="lines+markers", marker=dict(size=3))
    elif chart_type == "Scatter":
        fig = px.scatter(df, **kwargs)
    else:
        fig = px.area(df, **kwargs)
        if show_markers:
            fig.update_traces(mode="lines+markers", marker=dict(size=3))

    return _apply_dark_theme(fig, x_title, y_title, log_y)


def comparison_figure(long_df, x_col: str, y_col: str, color_col: str,
                       chart_type: str, title: str, x_title: str, y_title: str,
                       log_y: bool = False) -> go.Figure:
    kwargs = dict(x=x_col, y=y_col, color=color_col, title=title,
                  labels={x_col: x_title, y_col: y_title}, color_discrete_sequence=COLORS)
    if chart_type == "Line":
        fig = px.line(long_df, **kwargs)
    elif chart_type == "Scatter":
        fig = px.scatter(long_df, **kwargs)
    else:
        fig = px.area(long_df, **kwargs)

    return _apply_dark_theme(fig, x_title, y_title, log_y)


def add_moving_average_trace(fig: go.Figure, x, y, name: str, color: str) -> go.Figure:
    fig.add_scatter(x=x, y=y, mode="lines", name=f"{name} (avg)",
                     line=dict(color=color, width=2, dash="dot"), opacity=0.9)
    return fig


def rmsf_figure(residue_ids, rmsf_values, highlight_ids=None,
                 title: str = "Per-Residue RMSF") -> go.Figure:
    highlight_ids = set(highlight_ids or [])
    colors = [COLORS[1] if rid in highlight_ids else COLORS[0] for rid in residue_ids]

    fig = go.Figure(go.Bar(x=list(residue_ids), y=list(rmsf_values),
                            marker=dict(color=colors), name="RMSF"))
    fig.update_layout(title=title)
    return _apply_dark_theme(fig, "Residue", "RMSF (nm)")


def export_figure_bytes(fig: go.Figure, fmt: str = "png", scale: int = 2) -> bytes:
    """PNG/SVG/PDF bytes for a figure, via kaleido. Needs
    `pip install kaleido` — it's in requirements.txt but Streamlit doesn't
    pull it in on its own."""
    return fig.to_image(format=fmt, scale=scale)
