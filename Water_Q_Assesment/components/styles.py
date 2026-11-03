"""
Global custom CSS injected once into every page via st.markdown.
"""
import streamlit as st


PALETTE = {
    "primary":    "#1a73e8",
    "safe":       "#34a853",
    "warning":    "#fbbc04",
    "danger":     "#ea4335",
    "missing":    "#9e9e9e",
    "bg":         "#f0f4f9",
    "surface":    "#ffffff",
    "border":     "#dadce0",
    "text":       "#202124",
    "text_muted": "#5f6368",
}


def inject_css() -> None:
    st.markdown(
        f"""
        <style>
        /* ── Root & Layout ──────────────────────────────────────────── */
        @import url('https://fonts.googleapis.com/css2?family=Google+Sans:wght@400;500;700&family=Roboto+Mono:wght@400;500&display=swap');

        html, body, [class*="css"] {{
            font-family: 'Google Sans', 'Segoe UI', sans-serif;
            color: {PALETTE['text']};
        }}

        .main .block-container {{
            padding: 1.5rem 2rem 3rem;
            max-width: 1400px;
        }}

        /* ── Sidebar ────────────────────────────────────────────────── */
        section[data-testid="stSidebar"] {{
            background: linear-gradient(180deg, #1a237e 0%, #283593 60%, #1565c0 100%);
        }}
        section[data-testid="stSidebar"] * {{
            color: #e8eaf6 !important;
        }}
        section[data-testid="stSidebar"] .stSelectbox label,
        section[data-testid="stSidebar"] .stMultiSelect label,
        section[data-testid="stSidebar"] .stDateInput label {{
            color: #b3bef8 !important;
            font-size: 0.78rem;
            font-weight: 500;
            letter-spacing: 0.05em;
            text-transform: uppercase;
        }}
        section[data-testid="stSidebar"] hr {{
            border-color: rgba(255,255,255,0.15) !important;
        }}

        /* ── Top header banner ──────────────────────────────────────── */
        .wq-header {{
            background: linear-gradient(135deg, #1a237e 0%, #1565c0 50%, #0288d1 100%);
            border-radius: 16px;
            padding: 1.5rem 2rem;
            margin-bottom: 1.5rem;
            color: #fff;
            display: flex;
            align-items: center;
            gap: 1rem;
        }}
        .wq-header h1 {{
            margin: 0;
            font-size: 1.75rem;
            font-weight: 700;
            color: #fff;
        }}
        .wq-header p {{
            margin: 0.25rem 0 0;
            font-size: 0.9rem;
            opacity: 0.85;
            color: #fff;
        }}
        .wq-header-icon {{
            font-size: 2.5rem;
            line-height: 1;
        }}

        /* ── KPI Cards ──────────────────────────────────────────────── */
        .kpi-row {{
            display: flex;
            gap: 1rem;
            flex-wrap: wrap;
            margin-bottom: 1.5rem;
        }}
        .kpi-card {{
            flex: 1;
            min-width: 150px;
            background: {PALETTE['surface']};
            border: 1px solid {PALETTE['border']};
            border-radius: 12px;
            padding: 1rem 1.25rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
            position: relative;
            overflow: hidden;
        }}
        .kpi-card::before {{
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 4px;
            border-radius: 12px 12px 0 0;
        }}
        .kpi-card.safe::before   {{ background: {PALETTE['safe']}; }}
        .kpi-card.danger::before {{ background: {PALETTE['danger']}; }}
        .kpi-card.warning::before{{ background: {PALETTE['warning']}; }}
        .kpi-card.info::before   {{ background: {PALETTE['primary']}; }}
        .kpi-card.grey::before   {{ background: {PALETTE['missing']}; }}

        .kpi-label {{
            font-size: 0.72rem;
            font-weight: 600;
            color: {PALETTE['text_muted']};
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.4rem;
        }}
        .kpi-value {{
            font-size: 2rem;
            font-weight: 700;
            line-height: 1.1;
        }}
        .kpi-value.safe    {{ color: {PALETTE['safe']}; }}
        .kpi-value.danger  {{ color: {PALETTE['danger']}; }}
        .kpi-value.warning {{ color: {PALETTE['warning']}; }}
        .kpi-value.info    {{ color: {PALETTE['primary']}; }}
        .kpi-value.grey    {{ color: {PALETTE['missing']}; }}
        .kpi-sub {{
            font-size: 0.78rem;
            color: {PALETTE['text_muted']};
            margin-top: 0.2rem;
        }}

        /* ── Section title ──────────────────────────────────────────── */
        .section-title {{
            font-size: 1.05rem;
            font-weight: 700;
            color: {PALETTE['text']};
            margin: 1.5rem 0 0.75rem;
            padding-bottom: 0.4rem;
            border-bottom: 2px solid {PALETTE['primary']};
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        /* ── Status badge ───────────────────────────────────────────── */
        .badge {{
            display: inline-block;
            padding: 0.15rem 0.6rem;
            border-radius: 20px;
            font-size: 0.72rem;
            font-weight: 600;
            letter-spacing: 0.04em;
        }}
        .badge-safe    {{ background: #e6f4ea; color: {PALETTE['safe']}; }}
        .badge-danger  {{ background: #fce8e6; color: {PALETTE['danger']}; }}
        .badge-missing {{ background: #f1f3f4; color: {PALETTE['missing']}; }}

        /* ── Threshold info box ─────────────────────────────────────── */
        .thresh-box {{
            background: #e8f0fe;
            border-left: 4px solid {PALETTE['primary']};
            border-radius: 0 8px 8px 0;
            padding: 0.6rem 1rem;
            font-size: 0.82rem;
            margin-bottom: 1rem;
            color: #1a237e;
        }}

        /* ── Warning callout ────────────────────────────────────────── */
        .disclaimer {{
            background: #fff8e1;
            border-left: 4px solid {PALETTE['warning']};
            border-radius: 0 8px 8px 0;
            padding: 0.6rem 1rem;
            font-size: 0.78rem;
            color: #5f4e00;
            margin-top: 1.5rem;
        }}

        /* ── Chart card wrapper ─────────────────────────────────────── */
        .chart-card {{
            background: {PALETTE['surface']};
            border: 1px solid {PALETTE['border']};
            border-radius: 12px;
            padding: 1rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.06);
            margin-bottom: 1rem;
        }}

        /* ── Streamlit overrides ────────────────────────────────────── */
        div[data-testid="stMetric"] {{
            background: {PALETTE['surface']};
            border: 1px solid {PALETTE['border']};
            border-radius: 12px;
            padding: 0.8rem 1rem;
        }}
        .stTabs [data-baseweb="tab-list"] {{
            gap: 4px;
        }}
        .stTabs [data-baseweb="tab"] {{
            border-radius: 8px 8px 0 0;
            font-weight: 500;
        }}
        /* Hide default streamlit footer */
        footer {{ visibility: hidden; }}
        </style>
        """,
        unsafe_allow_html=True,
    )

