"""
Top header banner for the dashboard.
"""
import streamlit as st


def render_header(title: str = "Water Quality Dashboard",
                  subtitle: str = "Visualise water-quality measurements by region and compare against WHO / BIS safety thresholds") -> None:
    st.markdown(
        f"""
        <div class="wq-header">
            <div class="wq-header-icon">💧</div>
            <div>
                <h1>{title}</h1>
                <p>{subtitle}</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

