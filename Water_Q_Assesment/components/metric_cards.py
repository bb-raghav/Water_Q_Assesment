"""
KPI metric cards rendered as HTML for pixel-perfect styling.
"""
import streamlit as st
import pandas as pd


def render_kpi_cards(df_filtered: pd.DataFrame) -> None:
    total   = len(df_filtered)
    safe    = (df_filtered["Status"] == "Safe").sum()
    danger  = (df_filtered["Status"] == "Out of Range").sum()
    missing = (df_filtered["Status"] == "Missing").sum()
    pct_safe = round(safe / total * 100, 1) if total else 0

    cards = [
        {
            "label":    "Total Readings",
            "value":    f"{total:,}",
            "sub":      "across selected filters",
            "cls":      "info",
        },
        {
            "label":    "Safe Readings",
            "value":    f"{safe:,}",
            "sub":      f"{pct_safe}% of total",
            "cls":      "safe",
        },
        {
            "label":    "Out of Range",
            "value":    f"{danger:,}",
            "sub":      f"{round(danger/total*100,1) if total else 0}% of total",
            "cls":      "danger",
        },
        {
            "label":    "Missing Data",
            "value":    f"{missing:,}",
            "sub":      f"{round(missing/total*100,1) if total else 0}% of total",
            "cls":      "grey",
        },
    ]

    html = '<div class="kpi-row">'
    for c in cards:
        html += f"""
        <div class="kpi-card {c['cls']}">
            <div class="kpi-label">{c['label']}</div>
            <div class="kpi-value {c['cls']}">{c['value']}</div>
            <div class="kpi-sub">{c['sub']}</div>
        </div>
        """
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

