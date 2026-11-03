"""Water Quality Dashboard - Streamlit entry point. Logic lives in src/; this file is UI only."""
from __future__ import annotations

import json
import os

import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from src import ai_summary as ai
from src import analysis as an
from src import data_loader as dl
from src import visualizations as viz
from src.threshold_validation import (ABOVE, ALL_STATUSES, ASSESSED_STATUSES, BELOW, INSUFFICIENT, MIXED,
                                      MISSING, WITHIN, assess_dataframe, status_label)

# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AquaWatch | Water Quality",
    page_icon="A",
    layout="wide",
    initial_sidebar_state="expanded",
)
dl.load_env_file()

FILTER_KEYS = ["f_region", "f_param", "f_dates", "f_status", "f_sources"]

# ═══════════════════════════════════════════════════════════════════════════════
#  GLOBAL CSS
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* Simple, readable AquaWatch interface */
:root {
  --ocean: #3f6655; --deep: #26372e; --teal: #5e7969;
  --safe: #34765b; --warn: #9a6529; --danger: #b54e47;
  --muted: #778078; --text: #28332c; --surface: #fff;
  --line: #e3e7e2; --canvas: #f7f8f6; --radius: 9px;
}
html, body, [class*="css"] {
  color: var(--text);
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  -webkit-font-smoothing: antialiased;
}
.stApp { background: var(--canvas) !important; min-height: 100vh; }
.main .block-container { max-width: 1440px; padding: 0.4rem 2rem 2.5rem; }

section[data-testid="stSidebar"] {
  min-width: 220px !important; max-width: 220px !important;
  background: #f1f3f0 !important; border-right: 1px solid var(--line) !important;
  box-shadow: none !important; backdrop-filter: none !important;
}
section[data-testid="stSidebar"] > div { background: transparent !important; padding-top: 0 !important; }
section[data-testid="stSidebar"] * { color: #455148 !important; }
section[data-testid="stSidebar"] hr { border-color: #e1e5e0 !important; margin: 0.55rem 0 !important; }
.sb-logo { display: flex; align-items: center; gap: 0.62rem; padding: 1.1rem 0.85rem 0.75rem; text-align: left; }
.brand-mark { display: grid; place-items: center; width: 34px; height: 34px; flex: 0 0 34px; background: #3f6655; border-radius: 9px; }
.brand-mark svg { width: 21px; height: 21px; fill: none; stroke: #fff; stroke-width: 1.65; stroke-linecap: round; stroke-linejoin: round; }
.brand-mark .brand-stream { stroke: #c8d8ae; stroke-width: 1.8; }
.brand-copy { display: flex; flex-direction: column; gap: 0.02rem; }
.sb-logo-title { color: #2b3b31 !important; font-family: inherit; font-size: 1rem; font-weight: 700; letter-spacing: -0.02em; }
.sb-logo-sub { color: #7a837c !important; font-size: 0.7rem; letter-spacing: 0.01em; }
.sb-nav-header { color: #858d86 !important; font-size: 0.66rem; letter-spacing: 0.08em; padding-left: 0.8rem; }
section[data-testid="stSidebar"] .stButton button {
  width: 100% !important; text-align: left !important; color: #536057 !important;
  background: transparent !important; border: 1px solid transparent !important;
  border-radius: 7px !important; padding: 0.48rem 0.72rem !important;
  margin-bottom: 2px !important; font-size: 0.84rem !important; font-weight: 500 !important;
  box-shadow: none !important; transform: none !important;
}
section[data-testid="stSidebar"] .stButton button:hover {
  color: #283b30 !important; background: #e8ece7 !important;
  border-color: transparent !important; box-shadow: none !important; transform: none !important;
}
section[data-testid="stSidebar"] .nav-active .stButton button {
  color: #2e4b3a !important; background: #e5ebe4 !important;
  border-left: 3px solid #5e7969 !important; font-weight: 650 !important; box-shadow: none !important;
}
.sb-footer {
  color: #7b847d !important; background: transparent; border: 0;
  border-top: 1px solid #e0e5df; border-radius: 0;
  padding: 0.75rem 0.25rem; margin: 0.6rem 0.35rem; font-size: 0.69rem;
}
.sb-footer b { color: #59665c; }

/* Page heading without a decorative hero */
.wq-topbar {
  display: flex; align-items: flex-end; justify-content: space-between; gap: 1rem;
  margin: 0.85rem 0 1.15rem; padding: 0.45rem 0 0.9rem;
  color: var(--text); background: transparent; border: 0;
  border-bottom: 1px solid var(--line); border-radius: 0; box-shadow: none; overflow: visible;
}
.wq-heading { display: flex; flex-direction: column; gap: 0.12rem; }
.wq-topbar h1 { margin: 0; color: #28382e; font-family: inherit; font-size: 1.55rem; font-weight: 650; letter-spacing: -0.035em; text-shadow: none; }
.wq-topbar p { margin: 0; color: #79827b; font-size: 0.8rem; }
.wq-pill {
  display: inline-flex; align-items: center; padding: 0.28rem 0.58rem;
  color: #59685d; background: #edf1ec; border: 1px solid #e1e7df;
  border-radius: 6px; box-shadow: none; font-size: 0.7rem; font-weight: 550;
}
.wq-topbar-left, .wq-topbar-right, .wave-container, .wq-topbar-icon-wrap, .liquid-live-dot { display: none !important; }

/* Compact, consistent metrics */
.kpi-grid { display: flex; flex-wrap: wrap; gap: 0.7rem; margin: 0.6rem 0 1.1rem; }
.kpi-card {
  flex: 1 1 145px; min-width: 0; padding: 0.85rem 0.95rem;
  background: #fff; border: 1px solid var(--line); border-radius: 8px;
  box-shadow: none; backdrop-filter: none;
}
.kpi-card::before, .kpi-card::after { display: none; }
.kpi-card:hover { transform: none; box-shadow: 0 2px 7px rgba(30,45,35,0.05); border-color: #d7ded7; }
.kpi-label { color: #737d75; font-size: 0.68rem; font-weight: 600; letter-spacing: 0.035em; text-transform: uppercase; }
.kpi-value { margin-top: 0.25rem; color: #2e4939; font-family: inherit; font-size: 1.65rem; font-weight: 650; letter-spacing: -0.035em; line-height: 1.15; }
.kpi-value.ocean { color: #365f4a; } .kpi-value.safe { color: #34765b; }
.kpi-value.danger { color: #b54e47; } .kpi-value.warn { color: #9a6529; } .kpi-value.muted { color: #68736b; }
.kpi-sub { margin-top: 0.28rem; color: #7e8780; font-size: 0.7rem; font-weight: 400; }

.sec-header {
  --section-color: #577a5c; --section-tint: #eef3eb; --section-rgb: 87,122,92;
  display: flex; align-items: center; gap: 0.55rem;
  margin: 1.25rem 0 0.75rem; padding: 0.34rem 0.55rem;
  color: #334238; background: var(--section-tint);
  border-left: 3px solid var(--section-color); border-radius: 6px;
  font-family: inherit; font-size: 0.96rem; font-weight: 620;
}
.section-overview { --section-color: #577a5c; --section-tint: #eef3eb; --section-rgb: 87,122,92; }
.section-map { --section-color: #397c77; --section-tint: #eaf3f1; --section-rgb: 57,124,119; }
.section-analytics { --section-color: #796596; --section-tint: #f1eef5; --section-rgb: 121,101,150; }
.section-details { --section-color: #a87436; --section-tint: #f7f1e8; --section-rgb: 168,116,54; }
.section-ai { --section-color: #8b6274; --section-tint: #f5eef1; --section-rgb: 139,98,116; }
.section-sources { --section-color: #a45f50; --section-tint: #f6eeec; --section-rgb: 164,95,80; }
.section-mark {
  display: grid; place-items: center; width: 25px; height: 25px; flex: 0 0 25px;
  color: var(--section-color); background: rgba(255,255,255,0.78);
  border: 1px solid rgba(var(--section-rgb),0.18); border-radius: 6px;
}
.section-mark svg { width: 15px; height: 15px; fill: none; stroke: currentColor; stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round; }
.section-title { color: #37443b; }
.chart-wrap, .glass-panel {
  margin-bottom: 0.9rem; padding: 0.9rem 1rem; background: #fff;
  border: 1px solid var(--line); border-radius: 8px; box-shadow: none; backdrop-filter: none;
}
.chart-wrap:hover, .glass-panel:hover { box-shadow: none; }
.banner {
  display: block; margin: 0.5rem 0; padding: 0.58rem 0.78rem;
  border: 1px solid #e4e8e3; border-left: 3px solid #aab6aa;
  border-radius: 5px; box-shadow: none; backdrop-filter: none; font-size: 0.8rem; line-height: 1.5;
}
.banner-info { color: #46584b; background: #f0f3ef; border-color: #e3e8e2; border-left-color: #849886; }
.banner-warn { color: #735729; background: #f8f3e9; border-color: #eee5d3; border-left-color: #ba8a42; }
.banner-danger { color: #793f3a; background: #f8efee; border-color: #eee0de; border-left-color: #b95a52; }
.banner-success { color: #355b45; background: #eff4f0; border-color: #e0e9e1; border-left-color: #558169; }
.thresh-pill {
  display: flex; flex-wrap: wrap; gap: 0.55rem 1.15rem; align-items: center;
  margin-bottom: 0.85rem; padding: 0.6rem 0.8rem; color: #536157;
  background: #f0f3ef; border: 1px solid #e3e8e2; border-radius: 6px; box-shadow: none;
}
.thresh-pill b { margin-right: 0.2rem; color: #394a3d; font-weight: 650; }
.threshold-note { margin-left: 0.35rem; color: #996b30; font-weight: 600; }

div[data-testid="stMetric"] {
  padding: 0.8rem 0.9rem !important; background: #fff !important;
  border: 1px solid var(--line) !important; border-radius: 8px !important; box-shadow: none !important;
}
div[data-testid="stMetricLabel"] p { color: #737d75 !important; font-size: 0.7rem !important; }
div[data-testid="stMetricValue"] { color: #365f4a !important; font-family: inherit !important; font-weight: 650 !important; }
div[data-testid="stDataFrame"] { overflow: hidden !important; background: #fff !important; border: 1px solid var(--line) !important; border-radius: 7px !important; box-shadow: none !important; }
div[data-testid="stExpander"] { background: #fff !important; border: 1px solid var(--line) !important; border-radius: 7px !important; box-shadow: none !important; }
div[data-testid="stExpander"] summary:hover { color: #3f6655 !important; }
div[data-baseweb="select"] > div, div[data-baseweb="input"] > div, div[data-baseweb="textarea"] > div {
  background: #fff !important; border-color: #d9dfd9 !important; border-radius: 6px !important; box-shadow: none !important;
}
div[data-baseweb="select"] > div:focus-within, div[data-baseweb="input"] > div:focus-within, div[data-baseweb="textarea"] > div:focus-within {
  border-color: #718c78 !important; box-shadow: 0 0 0 2px rgba(63,102,85,0.10) !important;
}
.stButton button, .stDownloadButton button { border-radius: 6px !important; font-weight: 550 !important; box-shadow: none !important; }
.stButton button { color: #405046 !important; background: #fff !important; border: 1px solid #dfe4df !important; }
.stButton button:hover { color: #2e4939 !important; background: #f1f4f0 !important; border-color: #cfd8d0 !important; }
button[kind="primary"] { color: #fff !important; background: #3f6655 !important; border: 1px solid #3f6655 !important; }
button[kind="primary"]:hover { color: #fff !important; background: #345746 !important; border-color: #345746 !important; }
.stDownloadButton button { color: #405046 !important; background: #fff !important; border: 1px solid #dfe4df !important; }
.stDownloadButton button:hover { background: #f1f4f0 !important; border-color: #cfd8d0 !important; }
.stSpinner > div { border-top-color: #5e7969 !important; }
div[data-testid="stProgress"] > div > div { background: #5e7969 !important; }
footer { visibility: hidden; }
@media (max-width: 950px) {
  .main .block-container { padding-left: 1rem; padding-right: 1rem; }
  .wq-topbar { align-items: flex-start; }
  .kpi-card { flex-basis: 170px; }
}
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  NAVIGATION CONFIG
# ═══════════════════════════════════════════════════════════════════════════════
NAV_ITEMS = [
    ("overview", "Overview"),
    ("map", "Map"),
    ("analytics", "Analytics"),
    ("details", "Details"),
    ("ai", "AI Insights"),
    ("sources", "Sources"),
]

# ═══════════════════════════════════════════════════════════════════════════════
#  HTML HELPERS  (LIQUID DISPLAY EDITION)
# ═══════════════════════════════════════════════════════════════════════════════
def topbar(page_label: str, data_label: str) -> None:
    st.markdown(f"""
    <div class="wq-topbar">
      <div class="wq-heading">
        <h1>{page_label}</h1>
        <p>Water quality assessment</p>
      </div>
      <span class="wq-pill">{data_label}</span>
    </div>""", unsafe_allow_html=True)


SECTION_MARKS = {
    "overview": '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="3.5" width="7" height="7" rx="1"/><rect x="13.5" y="3.5" width="7" height="7" rx="1"/><rect x="3.5" y="13.5" width="7" height="7" rx="1"/><rect x="13.5" y="13.5" width="7" height="7" rx="1"/></svg>',
    "map": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19.2 10c0 5-7.2 11-7.2 11S4.8 15 4.8 10a7.2 7.2 0 1 1 14.4 0Z"/><circle cx="12" cy="10" r="2.3"/></svg>',
    "analytics": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20V11M10 20V5M16 20v-7M22 20H2"/></svg>',
    "details": '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="3" width="14" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/></svg>',
    "ai": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 5.5h14a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-7l-5 3v-3H5a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2Z"/><path d="M8 10h8M8 13.5h5"/></svg>',
    "sources": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 6.5C9.5 4.5 6 4.5 3.5 5.5v13c2.5-1 6-1 8.5 1 2.5-2 6-2 8.5-1v-13c-2.5-1-6-1-8.5 1Z"/><path d="M12 6.5v13M6.5 8.5h2.8M15 8.5h2.5"/></svg>',
}


def sec(title: str, section: str) -> None:
    mark = SECTION_MARKS.get(section, SECTION_MARKS["overview"])
    st.markdown(
        f'<div class="sec-header section-{section}"><span class="section-mark">{mark}</span>'
        f'<span class="section-title">{title}</span></div>',
        unsafe_allow_html=True)


def kpi_cards(m: dict) -> None:
    safe_count = m["assessed"] - m["outside"] if m["assessed"] else 0
    cards = [
        ("ocean", "Total measurements", m["total"], f"{m['sites']} sites across {m['regions']} regions"),
        ("safe", "Within reference", safe_count, f"of {m['assessed']} assessed"),
        ("danger", "Outside reference", m["outside"], "above or below limit"),
        ("warn", "Cannot assess", m["cannot_assess"], "no verified threshold"),
        ("muted", "Missing values", m["missing"], "never treated as zero"),
    ]
    html = '<div class="kpi-grid">'
    for cls, label, val, sub in cards:
        html += f"""
        <div class="kpi-card {cls}">
          <div class="kpi-label">{label}</div>
          <div class="kpi-value {cls}">{val:,}</div>
          <div class="kpi-sub">{sub}</div>
        </div>"""
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def banner(kind: str, text: str) -> None:
    st.markdown(
        f'<div class="banner banner-{kind}">{text}</div>',
        unsafe_allow_html=True)


def thresh_info(info: dict | None) -> None:
    if not info:
        st.markdown(
            '<div class="thresh-pill">No applicable verified threshold. No limit lines are drawn.</div>',
            unsafe_allow_html=True)
        return
    vstr = "" if info["verified"] else ' <span class="threshold-note">Illustrative / not verified</span>'
    st.markdown(f"""<div class="thresh-pill">
      <span><b>Reference</b> {info.get('reference_name') or 'Unnamed'}</span>
      <span><b>Source</b> {info.get('source_organization') or 'Not stated'}</span>
      <span><b>Limits</b> {an.threshold_text(info['min'], info['max'], info['unit'])}{vstr}</span>
    </div>""", unsafe_allow_html=True)


#  UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════
def get_secret(name: str):
    if os.getenv(name):
        return os.getenv(name)
    try:
        return st.secrets.get(name)
    except Exception:
        return None


@st.cache_data(show_spinner=False)
def cached_sample() -> pd.DataFrame:
    return dl.load_measurements_csv()


@st.cache_data(show_spinner=False)
def cached_default_thresholds() -> pd.DataFrame:
    return dl.load_thresholds_csv()


def reset_filters():
    for k in FILTER_KEYS:
        st.session_state.pop(k, None)


def keep_valid(key, options):
    if key in st.session_state and st.session_state[key] not in options:
        st.session_state.pop(key)


# ═══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR  –  navigation rail only
# ═══════════════════════════════════════════════════════════════════════════════
def build_sidebar() -> str:
    """Render the nav rail. Returns the key of the active page."""
    with st.sidebar:
        st.markdown("""
        <div class="sb-logo">
          <span class="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 28 28">
              <path d="M14 3.5C11.2 7.3 8.7 10.1 8.7 13.6a5.3 5.3 0 0 0 10.6 0c0-3.5-2.5-6.3-5.3-10.1Z"/>
              <path class="brand-stream" d="M10.5 15.5c1.2-.7 2.3-.7 3.5 0s2.1.7 3.2 0"/>
            </svg>
          </span>
          <span class="brand-copy">
            <span class="sb-logo-title">AquaWatch</span>
            <span class="sb-logo-sub">Water quality</span>
          </span>
        </div>""", unsafe_allow_html=True)

        st.markdown("---")

        # Navigation buttons
        st.markdown('<div class="sb-nav-header">Navigation</div>', unsafe_allow_html=True)

        active = st.session_state.get("active_page", "overview")

        for key, label in NAV_ITEMS:
            is_active = key == active
            # Wrap active button in a div to allow CSS targeting
            if is_active:
                st.markdown('<div class="nav-active">', unsafe_allow_html=True)
            if st.button(label, key=f"nav_{key}", use_container_width=True):
                st.session_state["active_page"] = key
                st.rerun()
            if is_active:
                st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("---")

        st.markdown(
            '<div class="sb-footer">Not a certified safety assessment.</div>',
            unsafe_allow_html=True)


    return active


# ═══════════════════════════════════════════════════════════════════════════════
#  INLINE FILTER + DATA BAR  (replaces old sidebar controls)
# ═══════════════════════════════════════════════════════════════════════════════
def inline_controls(df_raw) -> tuple:
    """
    Show data-source selector + threshold toggle + all filters
    in a collapsible panel at the top of the main area.
    Returns (assessed_df, thresholds, allow_unverified, user_thresholds, filters_dict)
    """
    with st.expander("Data source and filters", expanded=False):
        col_ds, col_th = st.columns([1, 1])

        with col_ds:
            st.markdown("**Data Source**")
            modes = ["Synthetic demo data", "Upload CSV"]
            if get_secret("LIVE_DATA_URL"):
                modes.append("Live API")
            mode = st.radio("", modes, key="data_mode", label_visibility="collapsed",
                            horizontal=True)
            if mode == "Upload CSV":
                f = st.file_uploader("Measurements CSV", type="csv", key="meas_upload")
                if f:
                    try:
                        df_raw = dl.load_measurements_csv(f)
                    except dl.DataLoadError as exc:
                        st.error(str(exc))
            elif mode == "Live API":
                if st.button("Fetch live data", key="fetch_live"):
                    with st.spinner("Contacting data provider…"):
                        try:
                            st.session_state["live_df"] = dl.fetch_live_data(
                                get_secret("LIVE_DATA_URL"), get_secret("LIVE_DATA_API_KEY"))
                        except dl.DataLoadError as exc:
                            st.error(str(exc))
                df_raw = st.session_state.get("live_df", df_raw)

        with col_th:
            st.markdown("**Reference Thresholds**")
            up = st.file_uploader("Upload thresholds CSV (optional)", type="csv", key="thresh_upload",
                                  help="Without is_verified column, all rows are treated as verified.")
            allow_unverified = st.checkbox("Use illustrative demo thresholds", value=True,
                                           help="Demo thresholds are NOT regulatory limits.")
            user_thresholds = bool(up)
            try:
                thresholds = dl.load_thresholds_csv(up) if up else cached_default_thresholds()
            except dl.DataLoadError as exc:
                st.error(str(exc))
                thresholds = None

        # ── Validate & assess ──────────────────────────────────────────────
        if df_raw is None or df_raw.empty:
            df_raw = pd.DataFrame(columns=dl.REQUIRED_MEASUREMENT_COLUMNS)
        try:
            clean, issues = dl.validate_measurements(df_raw)
        except dl.DataLoadError as exc:
            st.error(str(exc))
            clean, issues = dl.validate_measurements(pd.DataFrame(columns=dl.REQUIRED_MEASUREMENT_COLUMNS))

        quality  = an.data_quality_summary(len(df_raw), clean, issues)
        assessed = assess_dataframe(clean, thresholds, allow_unverified)

        # ── Filters ────────────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("**Filters**")

        fc1, fc2, fc3, fc4, fc5, fc_btn = st.columns([1.6, 1.6, 1.8, 1.4, 1.4, 0.7])

        if assessed.empty:
            region = an.ALL_REGIONS
            param  = an.ALL_PARAMETERS
            dates  = None
            status = an.ALL_STATUSES_LABEL
            chosen = []
        else:
            regions  = [an.ALL_REGIONS]  + sorted(assessed["region"].dropna().unique())
            params   = [an.ALL_PARAMETERS] + sorted(assessed["parameter"].dropna().unique())
            statuses = [an.ALL_STATUSES_LABEL] + ALL_STATUSES
            sources  = sorted(assessed["data_source"].dropna().unique())

            for k, opts in (("f_region", regions), ("f_param", params), ("f_status", statuses)):
                keep_valid(k, opts)

            region = fc1.selectbox("Region",    regions,  key="f_region",  label_visibility="visible")
            param  = fc2.selectbox("Parameter", params,   key="f_param",   label_visibility="visible")

            dmin, dmax = assessed["sampling_date"].min().date(), assessed["sampling_date"].max().date()
            cur = st.session_state.get("f_dates")
            if isinstance(cur, tuple) and len(cur) == 2 and \
               not (dmin <= cur[0] <= dmax and dmin <= cur[1] <= dmax):
                st.session_state.pop("f_dates")
            dates = fc3.date_input("Date range", value=(dmin, dmax),
                                   min_value=dmin, max_value=dmax, key="f_dates")
            dates = tuple(dates) if isinstance(dates, (tuple, list)) and len(dates) == 2 else (dmin, dmax)

            status = fc4.selectbox("Status", statuses, key="f_status", label_visibility="visible")

            if "f_sources" in st.session_state:
                st.session_state["f_sources"] = [s for s in st.session_state["f_sources"] if s in sources]
            extra  = {} if "f_sources" in st.session_state else {"default": sources}
            chosen = fc5.multiselect("Source", sources, key="f_sources", **extra,
                                     label_visibility="visible")
            fc_btn.markdown("<br>", unsafe_allow_html=True)
            fc_btn.button("Reset filters", on_click=reset_filters, use_container_width=True, key="reset_btn")

        is_synthetic = (mode == "Synthetic demo data")
        filters_dict = {
            "region": region, "parameter": param, "status": status,
            "date_range": [str(d) for d in dates] if dates else None,
            "data_sources": chosen,
        }

        return (assessed, thresholds, allow_unverified, user_thresholds,
                is_synthetic, quality, issues, filters_dict,
                region, param, dates, status, chosen)


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE SECTIONS
# ═══════════════════════════════════════════════════════════════════════════════
def section_overview(df, quality, is_synthetic):
    m = an.overview_metrics(df)
    kpi_cards(m)

    if m["total"]:
        fig_status = viz.status_breakdown_chart(df)
        if fig_status:
            sec("Measurement Status Breakdown", "overview")
            st.markdown('<div class="chart-wrap">', unsafe_allow_html=True)
            st.plotly_chart(fig_status, use_container_width=True, config={"displayModeBar": False})
            st.markdown("</div>", unsafe_allow_html=True)

    with st.expander("Data-quality report"):
        q = quality
        st.markdown(
            f'<div class="glass-panel"><b>{q["records_used"]}</b> of <b>{q["records_in_file"]}</b> records used '
            f'(<b>{q["records_excluded"]}</b> excluded). '
            f'<b>{q["empty_measurements"]}</b> records have no measured value.</div>',
            unsafe_allow_html=True)
        for issue, n in q["issue_counts"].items():
            st.markdown(f"&nbsp; • &nbsp; **{issue}**: {n}")

    banner("warn", "<b>Important:</b> A reading inside or outside a reference range is <em>not</em> a safety verdict. "
           "Missing values are never treated as zero. Consult official certified testing.")


def section_map(df):
    sec("Monitoring sites", "map")
    sites = an.site_summary(df)
    n_no_coords = int((~sites["has_coordinates"]).sum())
    if n_no_coords:
        banner("warn", f"{n_no_coords} site(s) have no valid coordinates and cannot appear on the map.")

    fmap = viz.build_map(sites, df)
    if fmap is None:
        banner("info", "The map requires latitude/longitude. No site in the current selection has valid coordinates.")
    else:
        legend_html = " &nbsp; ".join(
            f"<b>{status_label(s)}</b>" for s in [WITHIN, ABOVE, BELOW, MIXED, INSUFFICIENT])
        st.markdown(
            f'<div class="thresh-pill"> {legend_html} — marker colour shows status</div>',
            unsafe_allow_html=True)
        out = st_folium(fmap, height=500, use_container_width=True, key="site_map",
                        returned_objects=["last_object_clicked_tooltip"])
        clicked = (out or {}).get("last_object_clicked_tooltip")
        if clicked and clicked != st.session_state.get("last_map_click"):
            st.session_state["last_map_click"] = clicked
            st.session_state["site_select"] = clicked
            st.rerun()

    labels = [f"{r.site_name} ({r.site_id})" for r in sites.itertuples()]
    keep_valid("site_select", labels)
    choice  = st.selectbox("Selected site", labels, key="site_select")
    site_id = sites.iloc[labels.index(choice)]["site_id"]
    detail  = df[df["site_id"] == site_id].sort_values(["parameter", "sampling_date"])
    row     = sites[sites["site_id"] == site_id].iloc[0]

    sec(f"{row['site_name']} — {row['region']}", "map")
    banner("info", f"Site status: <b>{status_label(row['status'])}</b> &nbsp;|&nbsp; "
           f"{row['n_assessed']} of {row['n_measurements']} measurement(s) could be assessed")

    left, right = st.columns([3, 2])
    fig = viz.site_chart(detail)
    if fig:
        left.markdown('<div class="chart-wrap">', unsafe_allow_html=True)
        left.plotly_chart(fig, use_container_width=True)
        left.markdown("</div>", unsafe_allow_html=True)
    else:
        left.info("This site has no recorded values to chart.")
    right.dataframe(
        an.display_table(detail)[["sampling_date", "parameter", "measured_value",
                                  "unit", "reference_threshold", "assessment_status"]],
        use_container_width=True, hide_index=True)


def section_analytics(df):
    sec("Water quality analytics", "analytics")
    params = sorted(df["parameter"].unique())
    param  = st.selectbox("Parameter to analyse", params, key="a_param",
                          help="Charts show one parameter at a time so units are never mixed.")
    p_df   = df[df["parameter"] == param]
    units  = sorted(p_df["unit"].dropna().unique())
    if not units:
        banner("warn", "This parameter has no unit recorded.")
        return
    unit = units[0]
    if len(units) > 1:
        unit = st.selectbox("Unit (parameter appears with multiple units)", units, key="a_unit")
        banner("warn", "Units are not converted. Only records with the chosen unit are analysed.")
    p_df = p_df[p_df["unit"] == unit]
    info = an.threshold_info(p_df)
    thresh_info(info)

    if p_df["measured_value"].notna().sum() == 0:
        banner("info", "No recorded values for this parameter in the current selection.")
        return

    a, b = st.columns(2)
    for col, fig, note in (
        (a, viz.trend_chart(p_df, param, unit, info),                    "Gaps = missing measurements."),
        (b, viz.regional_chart(an.regional_summary(p_df), param, unit),  None),
        (a, viz.distribution_chart(p_df, param, unit, info),             None),
        (b, viz.threshold_chart(p_df, param, unit, info),                None),
    ):
        if fig:
            col.markdown('<div class="chart-wrap">', unsafe_allow_html=True)
            col.plotly_chart(fig, use_container_width=True)
            if note:
                col.caption(note)
            col.markdown("</div>", unsafe_allow_html=True)

    sec("Summary Statistics", "analytics")
    stats = an.summary_stats(p_df)
    if stats:
        st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
        st.dataframe(
            pd.DataFrame([{k: v for k, v in stats.items() if k != "excluded"}]).round(3),
            hide_index=True, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
        banner("info", f"Calculated from <b>{stats['count']}</b> recorded values; "
               f"<b>{stats['excluded']}</b> record(s) without a value excluded. "
               "Descriptive statistics do not establish whether water is safe.")


def section_details(df):
    sec("Measurement Details", "details")
    table = an.display_table(df)
    st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
    st.dataframe(table, use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)
    c = st.columns(2)
    c[0].download_button("Download filtered CSV",
                         table.to_csv(index=False).encode("utf-8"),
                         "filtered_water_quality.csv", "text/csv")
    summary = {"overview": an.overview_metrics(df), "rows": len(table)}
    c[1].download_button("Download analysis JSON",
                         json.dumps(summary, indent=2),
                         "analysis_summary.json", "application/json")


def section_ai(df, filters, is_synthetic):
    sec("AI-Powered Insights", "ai")
    banner("info", "Counts and threshold comparisons are calculated in Python first. "
           "Only that pre-computed summary is sent to the AI — and only when you press the button.")
    api_key, model = ai.get_ai_config(get_secret)
    if not api_key:
        banner("warn", "AI summaries are not configured. Set <code>OPENAI_API_KEY</code> in a "
               "<code>.env</code> file or <code>.streamlit/secrets.toml</code>.")
    payload   = an.build_ai_payload(df, filters, is_synthetic)
    signature = json.dumps(payload, sort_keys=True, default=str)
    if st.button("Explain My Results", type="primary", disabled=df.empty):
        with st.spinner("Writing a plain-language explanation…"):
            st.session_state["ai_result"] = (signature, ai.generate_summary(payload, api_key, model))
    saved = st.session_state.get("ai_result")
    if saved:
        sig, result = saved
        if sig != signature:
            banner("warn", "Filters or data changed. Press the button to refresh.")
        if result.error:
            st.error(result.error)
        else:
            st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
            if is_synthetic:
                banner("warn", "Based on <b>synthetic demo data</b> — not real observations.")
            st.markdown(result.text)
            st.caption("AI-generated. It may contain mistakes; it is not a safety assessment.")
            st.markdown("</div>", unsafe_allow_html=True)
    with st.expander("Exactly what is sent to the AI"):
        st.json(payload)


def section_sources(issues, thresholds, using_demo_thresholds, is_synthetic):
    sec("Data sources and limitations", "sources")
    st.markdown(f"""
    <div class="glass-panel" style="line-height:1.85;">
    <ul style="margin:0;padding-left:1.25rem;">
    <li><b>Measurements:</b> {"the built-in <em>synthetic</em> sample — invented for demonstration, not real observations." if is_synthetic else "the data you supplied. Check its provenance."}</li>
    <li><b>Reference thresholds:</b> {"the bundled <em>illustrative demo</em> ranges, which are <b>not</b> regulatory limits." if using_demo_thresholds else "the thresholds you supplied."}
    Confirm they suit the water type and intended use before relying on any comparison.</li>
    <li>A reading inside or outside a range is <b>not</b> a safety verdict. 'Cannot assess' means a verified, unit-compatible threshold was unavailable.</li>
    <li>No units are converted, no values are estimated, and missing values are <b>never</b> treated as zero.</li>
    </ul>
    </div>""", unsafe_allow_html=True)

    sec("Configured thresholds", "sources")
    if thresholds is None or thresholds.empty:
        banner("info", "No thresholds configured. All recorded measurements will show as 'Cannot assess'.")
    else:
        st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
        st.dataframe(thresholds, use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)

    sec("Data quality issues", "sources")
    if issues.empty:
        banner("success", "No data-quality issues found in the current dataset.")
    else:
        st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
        st.dataframe(issues, use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    # 1. Sidebar nav – get active page key
    active_page = build_sidebar()

    # 2. Load base sample data (fallback)
    try:
        base_df = cached_sample()
    except Exception:
        base_df = pd.DataFrame(columns=dl.REQUIRED_MEASUREMENT_COLUMNS)

    # 3. Inline controls (data source + filters) at top of main area
    (assessed, thresholds, allow_unverified, user_thresholds,
     is_synthetic, quality, issues, filters_dict,
     region, param, dates, status, chosen) = inline_controls(base_df)

    # 4. Apply filters
    df = an.apply_filters(assessed, region, param, dates, status, chosen)

    # 5. Top bar
    page_label = next((label for key, label in NAV_ITEMS if key == active_page), "Overview")
    data_label = "Synthetic demo" if is_synthetic else "Uploaded / Live"
    topbar(page_label, data_label)

    # 6. Compact global data information
    notices = []
    if is_synthetic:
        notices.append("<b>Synthetic demonstration data</b> — measurements are illustrative, not actual monitoring results.")
    if allow_unverified and not user_thresholds:
        notices.append("<b>Illustrative thresholds</b> — these are not verified regulatory limits.")
    if notices:
        banner("warn", " &nbsp; ".join(notices))

    # 7. Route to active page
    empty_msg = "No measurements match the current filters. Use the data and filters panel above to adjust them."

    if active_page == "overview":
        section_overview(df, quality, is_synthetic)

    elif active_page == "map":
        section_map(df) if not df.empty else banner("info", empty_msg)

    elif active_page == "analytics":
        section_analytics(df) if not df.empty else banner("info", empty_msg)

    elif active_page == "details":
        section_details(df) if not df.empty else banner("info", empty_msg)

    elif active_page == "ai":
        section_ai(df, filters_dict, is_synthetic) if not df.empty else banner("info", empty_msg)

    elif active_page == "sources":
        section_sources(issues, thresholds, allow_unverified and not user_thresholds, is_synthetic)


main()
