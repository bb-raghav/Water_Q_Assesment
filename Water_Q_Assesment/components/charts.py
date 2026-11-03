"""
Reusable Plotly chart builders.
"""
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from data.sample_data import THRESHOLDS

# ── Colour map ───────────────────────────────────────────────────────────────
STATUS_COLORS = {
    "Safe":         "#34a853",
    "Out of Range": "#ea4335",
    "Missing":      "#9e9e9e",
}

CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Google Sans, Segoe UI, sans-serif", size=12, color="#202124"),
    margin=dict(l=10, r=10, t=40, b=10),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)


# ── 1. Gauge chart – single parameter vs threshold ───────────────────────────
def gauge_chart(param: str, value: float | None) -> go.Figure:
    info   = THRESHOLDS[param]
    lo, hi = info["min"], info["max"]
    unit   = info["unit"]

    if value is None or pd.isna(value):
        display_val = 0
        bar_color   = "#9e9e9e"
        title_text  = f"{param}<br><sub>No data</sub>"
    else:
        display_val = value
        bar_color   = "#34a853" if lo <= value <= hi else "#ea4335"
        title_text  = f"{param}<br><sub>{value:.4g} {unit}</sub>"

    range_max = hi * 1.5 if hi > 0 else 1
    fig = go.Figure(go.Indicator(
        mode  = "gauge+number",
        value = display_val,
        number= dict(suffix=f" {unit}", font=dict(size=14)),
        title = dict(text=title_text, font=dict(size=13)),
        gauge = dict(
            axis       = dict(range=[lo, range_max], tickwidth=1),
            bar        = dict(color=bar_color, thickness=0.25),
            bgcolor    = "#f0f4f9",
            bordercolor= "#dadce0",
            steps      = [
                dict(range=[lo, hi], color="#e6f4ea"),
                dict(range=[hi, range_max], color="#fce8e6"),
            ],
            threshold  = dict(
                line  = dict(color="#ea4335", width=3),
                thickness=0.8,
                value = hi,
            ),
        ),
    ))
    fig.update_layout(**CHART_LAYOUT, height=220)
    return fig


# ── 2. Time-series line chart ─────────────────────────────────────────────────
def timeseries_chart(df: pd.DataFrame, param: str, regions: list[str]) -> go.Figure:
    info     = THRESHOLDS[param]
    hi, unit = info["max"], info["unit"]
    sub      = df[(df["Parameter"] == param) & (df["Region"].isin(regions))].copy()
    sub      = sub.dropna(subset=["Value"])

    fig = go.Figure()

    for region in regions:
        r_df = sub[sub["Region"] == region].sort_values("Date")
        fig.add_trace(go.Scatter(
            x=r_df["Date"], y=r_df["Value"],
            mode="lines+markers",
            name=region,
            marker=dict(size=5),
            line=dict(width=2),
        ))

    # Safe limit band
    fig.add_hline(
        y=hi,
        line_dash="dash",
        line_color="#ea4335",
        line_width=1.5,
        annotation_text=f"Safe max ({hi} {unit})",
        annotation_position="top right",
        annotation_font_size=10,
    )
    if info["min"] > 0:
        fig.add_hline(
            y=info["min"],
            line_dash="dot",
            line_color="#fbbc04",
            line_width=1.5,
            annotation_text=f"Safe min ({info['min']} {unit})",
            annotation_position="bottom right",
            annotation_font_size=10,
        )

    fig.update_layout(
        **CHART_LAYOUT,
        height=360,
        xaxis_title="Date",
        yaxis_title=f"{param} ({unit})",
        title=f"{param} – Trend Over Time",
        title_font_size=14,
    )
    return fig


# ── 3. Box plot – distribution by region ─────────────────────────────────────
def boxplot_chart(df: pd.DataFrame, param: str, regions: list[str]) -> go.Figure:
    info    = THRESHOLDS[param]
    hi, lo  = info["max"], info["min"]
    unit    = info["unit"]
    sub     = df[(df["Parameter"] == param) & (df["Region"].isin(regions))].dropna(subset=["Value"])

    fig = px.box(
        sub, x="Region", y="Value",
        color="Region",
        points="outliers",
        title=f"{param} – Distribution by Region",
        labels={"Value": f"{param} ({unit})"},
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig.add_hline(y=hi, line_dash="dash", line_color="#ea4335", line_width=1.5,
                  annotation_text=f"Max safe ({hi})", annotation_position="top right",
                  annotation_font_size=10)
    if lo > 0:
        fig.add_hline(y=lo, line_dash="dot", line_color="#fbbc04", line_width=1.5)
    fig.update_layout(**CHART_LAYOUT, height=360, showlegend=False,
                      title_font_size=14)
    return fig


# ── 4. Stacked bar – status breakdown by region ───────────────────────────────
def status_bar_chart(df: pd.DataFrame, regions: list[str]) -> go.Figure:
    sub   = df[df["Region"].isin(regions)]
    grp   = (
        sub.groupby(["Region", "Status"])
           .size()
           .reset_index(name="Count")
    )
    fig = px.bar(
        grp, x="Region", y="Count", color="Status",
        color_discrete_map=STATUS_COLORS,
        barmode="stack",
        title="Reading Status by Region",
        labels={"Count": "No. of Readings"},
    )
    fig.update_layout(**CHART_LAYOUT, height=360, title_font_size=14)
    return fig


# ── 5. Heatmap – parameter compliance rate by region ─────────────────────────
def compliance_heatmap(df: pd.DataFrame, regions: list[str]) -> go.Figure:
    sub    = df[df["Region"].isin(regions)]
    pivot  = (
        sub.groupby(["Region", "Parameter"])
           .apply(lambda g: round((g["Status"] == "Safe").sum() / max(len(g), 1) * 100, 1))
           .reset_index(name="SafePct")
    )
    matrix = pivot.pivot(index="Region", columns="Parameter", values="SafePct").fillna(0)

    fig = go.Figure(go.Heatmap(
        z          = matrix.values,
        x          = matrix.columns.tolist(),
        y          = matrix.index.tolist(),
        colorscale = "RdYlGn",
        zmin=0, zmax=100,
        colorbar   = dict(title="Safe %", ticksuffix="%"),
        text       = matrix.values.round(0),
        texttemplate="%{text}%",
        hovertemplate="Region: %{y}<br>Param: %{x}<br>Safe: %{z:.1f}%<extra></extra>",
    ))
    fig.update_layout(
        **CHART_LAYOUT,
        height=max(300, len(matrix) * 55 + 80),
        title="Compliance Rate (%) – Region × Parameter",
        title_font_size=14,
        xaxis=dict(tickangle=-30),
    )
    return fig


# ── 6. Scatter – value vs threshold for a parameter ──────────────────────────
def scatter_vs_threshold(df: pd.DataFrame, param: str, regions: list[str]) -> go.Figure:
    info = THRESHOLDS[param]
    sub  = df[(df["Parameter"] == param) & (df["Region"].isin(regions))].dropna(subset=["Value"])

    fig = px.scatter(
        sub, x="Date", y="Value",
        color="Status",
        color_discrete_map=STATUS_COLORS,
        symbol="Region",
        title=f"{param} – Readings vs Safe Threshold",
        labels={"Value": f"{param} ({info['unit']})"},
        hover_data=["Region", "Unit", "Source"],
    )
    fig.add_hline(y=info["max"], line_dash="dash", line_color="#ea4335",
                  annotation_text=f"Safe max", annotation_font_size=10)
    if info["min"] > 0:
        fig.add_hline(y=info["min"], line_dash="dot", line_color="#fbbc04",
                      annotation_text=f"Safe min", annotation_font_size=10)
    fig.update_layout(**CHART_LAYOUT, height=380, title_font_size=14)
    return fig


# ── 7. Pie chart – overall status split ──────────────────────────────────────
def status_pie(df: pd.DataFrame) -> go.Figure:
    counts = df["Status"].value_counts().reset_index()
    counts.columns = ["Status", "Count"]
    fig = px.pie(
        counts, names="Status", values="Count",
        color="Status",
        color_discrete_map=STATUS_COLORS,
        title="Overall Reading Distribution",
        hole=0.42,
    )
    fig.update_traces(textposition="outside", textinfo="percent+label")
    fig.update_layout(**CHART_LAYOUT, height=340, title_font_size=14,
                      showlegend=False)
    return fig

