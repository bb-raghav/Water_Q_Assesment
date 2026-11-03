"""Plotly charts and the Folium map. Each function returns a figure/map or None if there is nothing to draw."""
from __future__ import annotations

import html

import folium
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.analysis import threshold_text
from src.threshold_validation import (ABOVE, BELOW, CANNOT, INSUFFICIENT, MIXED, MISSING, WITHIN,
                                      status_label)

STATUS_COLORS = {WITHIN: "#2e9e6b", ABOVE: "#d64545", BELOW: "#e08a1e", MISSING: "#9aa5b1", CANNOT: "#5f6b7a"}
STATUS_SYMBOLS = {WITHIN: "circle", ABOVE: "triangle-up", BELOW: "triangle-down", MISSING: "x", CANNOT: "diamond"}
# (folium colour, glyphicon) - icon shape + colour, so meaning never depends on colour alone
MARKER_STYLE = {WITHIN: ("green", "ok-sign"), ABOVE: ("red", "arrow-up"), BELOW: ("orange", "arrow-down"),
                MIXED: ("purple", "random"), INSUFFICIENT: ("lightgray", "question-sign")}
TEAL = "#0f766e"


def _with_values(df):
    return df[df["measured_value"].notna()]


def _threshold_lines(fig, info, axis="y"):
    if not info:
        return
    label = info.get("reference_name") or "Reference"
    for key, name in (("min", "Min"), ("max", "Max")):
        if info.get(key) is not None:
            kw = dict(line_dash="dash", line_color=TEAL, annotation_text=f"{name} {info[key]:g} - {label}"[:70])
            fig.add_hline(y=info[key], **kw) if axis == "y" else fig.add_vline(x=info[key], **kw)


def trend_chart(df, parameter, unit, info=None):
    """Lines are broken where a measurement is missing instead of bridging the gap."""
    if _with_values(df).empty:
        return None
    all_dates = sorted(df["sampling_date"].unique())
    fig = go.Figure()
    for name, g in df.groupby("site_name"):
        s = g.groupby("sampling_date")["measured_value"].mean().reindex(all_dates)
        fig.add_trace(go.Scatter(x=all_dates, y=s.values, mode="lines+markers", name=name, connectgaps=False))
    _threshold_lines(fig, info)
    fig.update_layout(title=f"{parameter} over time", xaxis_title="Sampling date",
                      yaxis_title=f"{parameter} ({unit})", legend_title="Site", margin=dict(t=50, b=10))
    return fig


def regional_chart(summary, parameter, unit):
    if summary.empty:
        return None
    fig = px.bar(summary, x="region", y="mean", text=[f"n={n}" for n in summary["n"]],
                 hover_data={"n": True, "sites": True, "median": ":.2f", "min": ":.2f", "max": ":.2f"},
                 color_discrete_sequence=[TEAL])
    fig.update_layout(title=f"Mean {parameter} by region (n = valid observations)",
                      xaxis_title="Region", yaxis_title=f"Mean {parameter} ({unit})", margin=dict(t=50, b=10))
    return fig


def distribution_chart(df, parameter, unit, info=None):
    d = _with_values(df)
    if d.empty:
        return None
    if len(d) < 5:  # too few points for a meaningful histogram
        fig = px.strip(d, x="measured_value", color="region", hover_data=["site_name", "sampling_date"])
    else:
        fig = px.histogram(d, x="measured_value", nbins=min(12, max(4, len(d) // 2)), marginal="box",
                           color_discrete_sequence=[TEAL])
    _threshold_lines(fig, info, axis="x")
    fig.update_layout(title=f"Distribution of {parameter} (n={len(d)})", xaxis_title=f"{parameter} ({unit})",
                      margin=dict(t=50, b=10))
    return fig


def threshold_chart(df, parameter, unit, info=None):
    d = _with_values(df)
    if d.empty:
        return None
    fig = px.scatter(d, x="site_name", y="measured_value", color="status", symbol="status",
                     color_discrete_map=STATUS_COLORS, symbol_map=STATUS_SYMBOLS,
                     hover_data=["sampling_date", "region", "status_reason"])
    fig.update_traces(marker=dict(size=11))
    _threshold_lines(fig, info)
    fig.update_layout(title=f"{parameter}: measurements vs reference limits", xaxis_title="Site",
                      yaxis_title=f"{parameter} ({unit})", legend_title="Status", margin=dict(t=50, b=10))
    return fig


def site_chart(df):
    d = _with_values(df)
    if d.empty:
        return None
    d = d.assign(label=d["parameter"] + " (" + d["unit"].fillna("?") + ")").sort_values("sampling_date")
    fig = px.line(d, x="sampling_date", y="measured_value", facet_row="label", markers=True,
                  color_discrete_sequence=[TEAL])
    fig.update_yaxes(matches=None, title_text="")
    fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1], textangle=0, x=0.0, xanchor="left"))
    fig.update_layout(height=max(280, 190 * d["label"].nunique()), xaxis_title="Sampling date",
                      margin=dict(t=30, b=10))
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
