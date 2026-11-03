"""Plotly charts and the Folium map. Each function returns a figure/map or None if there is nothing to draw."""
from __future__ import annotations

import html

import folium
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.analysis import threshold_text
from src.threshold_validation import (ABOVE, ALL_STATUSES, BELOW, CANNOT, INSUFFICIENT, MIXED, MISSING,
                                      WITHIN, status_label)

STATUS_COLORS  = {WITHIN: "#268464", ABOVE: "#c3524a", BELOW: "#c58a43", MISSING: "#89958c", CANNOT: "#68756c"}
STATUS_SYMBOLS = {WITHIN: "circle", ABOVE: "triangle-up", BELOW: "triangle-down", MISSING: "x", CANNOT: "diamond"}
MARKER_STYLE   = {WITHIN: ("green", "ok-sign"), ABOVE: ("red", "arrow-up"), BELOW: ("orange", "arrow-down"),
                  MIXED: ("purple", "random"), INSUFFICIENT: ("lightgray", "question-sign")}

# ── Water-theme palette & shared Plotly layout ───────────────────────────────
OCEAN = "#2f7475"
AQUA  = "#8bbdb5"
TEAL  = "#4b9290"

_FONT   = "system-ui, -apple-system, Segoe UI, sans-serif"
_LAYOUT = dict(
    paper_bgcolor = "rgba(0,0,0,0)",
    plot_bgcolor  = "rgba(0,0,0,0)",
    font          = dict(family=_FONT, size=12, color="#283a3b"),
    margin        = dict(l=10, r=10, t=48, b=12),
    legend        = dict(
        orientation="h", yanchor="bottom", y=1.02,
        xanchor="right", x=1,
        bgcolor="rgba(255,255,255,0.92)",
        bordercolor="rgba(49,95,78,0.16)",
        borderwidth=1,
    ),
    xaxis = dict(showgrid=True, gridcolor="rgba(49,95,78,0.08)",
                 zeroline=False, linecolor="rgba(0,0,0,0.10)"),
    yaxis = dict(showgrid=True, gridcolor="rgba(49,95,78,0.08)",
                 zeroline=False, linecolor="rgba(0,0,0,0.10)"),
)
_SEQ = [OCEAN, TEAL, AQUA, "#a8bca0", "#c58a43", "#268464", "#c3524a", "#8b6f9f"]


def status_breakdown_chart(df: pd.DataFrame) -> go.Figure | None:
    if df.empty:
        return None
    counts = df["status"].value_counts().reindex(ALL_STATUSES, fill_value=0)
    labels = [status_label(s) for s in counts.index]
    colors = [STATUS_COLORS.get(s, OCEAN) for s in counts.index]
    
    fig = go.Figure(go.Bar(
        x=counts.values,
        y=labels,
        orientation="h",
        marker=dict(
            color=colors,
            line=dict(width=1, color="rgba(255, 255, 255, 0.6)"),
            cornerradius=4,
        ),
        text=[f"  <b>{v:,}</b>" for v in counts.values],
        textposition="outside",
        textfont=dict(size=11, color="#283a3b", family=_FONT),
        cliponaxis=False,
    ))
    fig.update_layout(**{
        **_LAYOUT,
        "height": 250,
        "margin": dict(l=10, r=40, t=15, b=20),
        "xaxis": dict(
            title="Number of Measurements",
            showgrid=True,
            gridcolor="rgba(49, 95, 78, 0.08)",
            zeroline=False,
        ),
        "yaxis": dict(
            autorange="reversed",
            tickfont=dict(size=11.5, family=_FONT, color="#283a3b"),
        ),
        "showlegend": False,
    })
    return fig


def _with_values(df):
    return df[df["measured_value"].notna()]


def _threshold_lines(fig, info, axis="y"):
    if not info:
        return
    label = info.get("reference_name") or "Reference"
    for key, name, dash, color in (
        ("max", "Max", "dash", "#c3524a"),
        ("min", "Min", "dot",  "#c58a43"),
    ):
        if info.get(key) is not None:
            kw = dict(
                line_dash=dash, line_color=color, line_width=1.8,
                annotation_text=f"{name} {info[key]:g} — {label}"[:65],
                annotation_font_size=10, annotation_font_color=color,
            )
            fig.add_hline(y=info[key], **kw) if axis == "y" else fig.add_vline(x=info[key], **kw)


def trend_chart(df, parameter, unit, info=None):
    """Lines are broken where a measurement is missing instead of bridging the gap."""
    if _with_values(df).empty:
        return None
    all_dates = sorted(df["sampling_date"].unique())
    fig = go.Figure()
    for i, (name, g) in enumerate(df.groupby("site_name")):
        s = g.groupby("sampling_date")["measured_value"].mean().reindex(all_dates)
        fig.add_trace(go.Scatter(
            x=all_dates, y=s.values,
            mode="lines+markers", name=name,
            connectgaps=False,
            line=dict(width=2.5, color=_SEQ[i % len(_SEQ)]),
            marker=dict(size=6),
        ))
    _threshold_lines(fig, info)
    fig.update_layout(
        **_LAYOUT,
        title=dict(text=f"<b>{parameter}</b> over time", font=dict(size=14, color="#214f52")),
        xaxis_title="Sampling date",
        yaxis_title=f"{parameter} ({unit})",
        legend_title="Site",
    )
    return fig


def regional_chart(summary, parameter, unit):
    if summary.empty:
        return None
    fig = px.bar(
        summary, x="region", y="mean",
        text=[f"n={n}" for n in summary["n"]],
        hover_data={"n": True, "sites": True, "median": ":.2f", "min": ":.2f", "max": ":.2f"},
        color="mean",
        color_continuous_scale=[[0, "#e7eee3"], [0.5, AQUA], [1, "#214f52"]],
    )
    fig.update_traces(textposition="outside", marker_line_width=0)
    fig.update_coloraxes(showscale=False)
    fig.update_layout(
        **_LAYOUT,
        title=dict(text=f"<b>Mean {parameter}</b> by region", font=dict(size=14, color="#214f52")),
        xaxis_title="Region",
        yaxis_title=f"Mean {parameter} ({unit})",
    )
    return fig


def distribution_chart(df, parameter, unit, info=None):
    d = _with_values(df)
    if d.empty:
        return None
    if len(d) < 5:
        fig = px.strip(d, x="measured_value", color="region",
                       hover_data=["site_name", "sampling_date"],
                       color_discrete_sequence=_SEQ)
    else:
        fig = px.histogram(
            d, x="measured_value",
            nbins=min(12, max(4, len(d) // 2)),
            marginal="box",
            color_discrete_sequence=[OCEAN],
            opacity=0.88,
        )
    _threshold_lines(fig, info, axis="x")
    fig.update_layout(
        **_LAYOUT,
        title=dict(text=f"<b>Distribution</b> of {parameter} (n={len(d)})", font=dict(size=14, color="#214f52")),
        xaxis_title=f"{parameter} ({unit})",
    )
    return fig


def threshold_chart(df, parameter, unit, info=None):
    d = _with_values(df)
    if d.empty:
        return None
    fig = px.scatter(
        d, x="site_name", y="measured_value",
        color="status", symbol="status",
        color_discrete_map=STATUS_COLORS,
        symbol_map=STATUS_SYMBOLS,
        hover_data=["sampling_date", "region", "status_reason"],
    )
    fig.update_traces(marker=dict(size=11, line=dict(width=1, color="white")))
    _threshold_lines(fig, info)
    fig.update_layout(
        **_LAYOUT,
        title=dict(text=f"<b>{parameter}</b>: measurements vs reference limits", font=dict(size=14, color="#214f52")),
        xaxis_title="Site",
        yaxis_title=f"{parameter} ({unit})",
        legend_title="Status",
    )
    return fig


def site_chart(df):
    d = _with_values(df)
    if d.empty:
        return None
    d = d.assign(label=d["parameter"] + " (" + d["unit"].fillna("?") + ")").sort_values("sampling_date")
    fig = px.line(
        d, x="sampling_date", y="measured_value",
        facet_row="label", markers=True,
        color_discrete_sequence=[OCEAN],
    )
    fig.update_traces(line=dict(width=2.5), marker=dict(size=7))
    fig.update_yaxes(matches=None, title_text="")
    fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1], textangle=0, x=0.0, xanchor="left",
                                               font=dict(size=11, color="#547a68")))
    fig.update_layout(
        **_LAYOUT,
        height=max(280, 190 * d["label"].nunique()),
        xaxis_title="Sampling date",
    )
    return fig


def _popup_html(site, detail) -> str:
    latest = detail.sort_values("sampling_date").groupby("parameter").tail(1)
    rows = "".join(
        f"<tr><td>{html.escape(str(r.parameter))}</td><td>{'' if pd.isna(r.measured_value) else f'{r.measured_value:g}'} "
        f"{html.escape(str(r.unit or ''))}</td><td>{html.escape(threshold_text(r.threshold_min, r.threshold_max, r.threshold_unit) if r.threshold_applied else 'n/a')}</td>"
        f"<td>{html.escape(status_label(r.status))}</td><td>{r.sampling_date:%Y-%m-%d}</td></tr>"
        for r in latest.itertuples())
    return (f"<b>{html.escape(str(site.site_name))}</b><br>Region: {html.escape(str(site.region))}<br>"
            f"Site status: {html.escape(status_label(site.status))}"
            "<table style='font-size:12px;margin-top:6px' cellpadding='3'><tr><th>Parameter</th><th>Latest value</th>"
            f"<th>Reference</th><th>Status</th><th>Date</th></tr>{rows}</table>")


def build_map(sites: pd.DataFrame, detail: pd.DataFrame):
    """Markers only for sites with valid coordinates; nothing is placed at made-up locations."""
    valid = sites[sites["has_coordinates"]]
    if valid.empty:
        return None
    m = folium.Map(location=[valid["latitude"].mean(), valid["longitude"].mean()], zoom_start=7,
                   tiles="OpenStreetMap", control_scale=True)
    for s in valid.itertuples():
        color, icon = MARKER_STYLE[s.status]
        folium.Marker([s.latitude, s.longitude], tooltip=f"{s.site_name} ({s.site_id})",
                      popup=folium.Popup(_popup_html(s, detail[detail["site_id"] == s.site_id]), max_width=420),
                      icon=folium.Icon(color=color, icon=icon)).add_to(m)
    if len(valid) > 1:
        m.fit_bounds([[valid["latitude"].min(), valid["longitude"].min()],
                      [valid["latitude"].max(), valid["longitude"].max()]], padding=(30, 30))
    return m
