"""
Sidebar: navigation + filters.
Returns a dict with the user's selections.
"""
import streamlit as st
import pandas as pd
from data.sample_data import REGIONS, THRESHOLDS


def render_sidebar(df: pd.DataFrame) -> dict:
    with st.sidebar:
        st.markdown("## 💧 Water Q")
        st.markdown(
            "<span style='font-size:0.75rem;opacity:0.7;'>Quality Assessment Dashboard</span>",
            unsafe_allow_html=True,
        )
        st.markdown("---")

        # ── Page navigation ──────────────────────────────────────────
        st.markdown(
            "<div style='font-size:0.7rem;font-weight:600;letter-spacing:0.08em;opacity:0.6;margin-bottom:0.5rem;'>NAVIGATION</div>",
            unsafe_allow_html=True,
        )
        page = st.radio(
            label="",
            options=[
                "🏠  Overview",
                "📊  Parameter Analysis",
                "🗺️  Regional Analysis",
                "📈  Trends",
                "✅  Quality Assessment",
                "📋  Data Reports",
            ],
            label_visibility="collapsed",
        )

        st.markdown("---")

        # ── Filters ──────────────────────────────────────────────────
        st.markdown(
            "<div style='font-size:0.7rem;font-weight:600;letter-spacing:0.08em;opacity:0.6;margin-bottom:0.5rem;'>FILTERS</div>",
            unsafe_allow_html=True,
        )

        all_regions = sorted(df["Region"].unique().tolist())
        selected_regions = st.multiselect(
            "Region(s)",
            options=all_regions,
            default=all_regions[:3],
            key="sb_regions",
        )

        all_params = list(THRESHOLDS.keys())
        selected_param = st.selectbox(
            "Parameter",
            options=all_params,
            key="sb_param",
        )

        min_date = df["Date"].min().date()
        max_date = df["Date"].max().date()
        date_range = st.date_input(
            "Date Range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
            key="sb_dates",
        )

        st.markdown("---")

        # ── Disclaimer ───────────────────────────────────────────────
        st.markdown(
            """
            <div style='font-size:0.7rem;opacity:0.65;line-height:1.5;'>
            ⚠️ <b>Disclaimer:</b> Results are based on sample data. 
            Do not declare water safe or unsafe from this tool alone. 
            Always consult official testing for health decisions.
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Unpack date range safely
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date = end_date = date_range

    return {
        "page":             page.split("  ", 1)[-1].strip(),
        "regions":          selected_regions if selected_regions else all_regions,
        "parameter":        selected_param,
        "start_date":       pd.Timestamp(start_date),
        "end_date":         pd.Timestamp(end_date),
    }

