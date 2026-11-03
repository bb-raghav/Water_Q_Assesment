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

st.set_page_config(page_title="Water Quality Dashboard", page_icon="💧", layout="wide")
dl.load_env_file()

FILTER_KEYS = ["f_region", "f_param", "f_dates", "f_status", "f_sources"]
st.markdown("""<style>
div[data-testid="stMetric"]{background:#f1f8f9;border:1px solid #cfe6e8;border-radius:10px;padding:12px 14px}
h1,h2,h3{color:#0b4f6c}
</style>""", unsafe_allow_html=True)


def get_secret(name: str):
    """Environment variable first, then Streamlit secrets. Values are never displayed."""
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


# ---------------------------------------------------------------- data selection
def choose_data() -> tuple[pd.DataFrame | None, bool, str]:
    """Returns (raw_df, is_synthetic, label)."""
    st.sidebar.title("💧 Water Quality")
    modes = ["Synthetic demo data", "Upload CSV"]
    if get_secret("LIVE_DATA_URL"):
        modes.append("Live API")
    mode = st.sidebar.radio("Data mode", modes, key="data_mode")
    try:
        if mode == "Synthetic demo data":
            return cached_sample(), True, "Synthetic demo data"
        if mode == "Upload CSV":
            f = st.sidebar.file_uploader("Measurements CSV", type="csv")
            return (dl.load_measurements_csv(f), False, "Uploaded file") if f else (None, False, "Uploaded file")
        if st.sidebar.button("Fetch live data"):
            with st.spinner("Contacting data provider..."):
                st.session_state["live_df"] = dl.fetch_live_data(get_secret("LIVE_DATA_URL"),
                                                                 get_secret("LIVE_DATA_API_KEY"))
        return st.session_state.get("live_df"), False, "Live API"
    except dl.DataLoadError as exc:
        st.sidebar.error(str(exc))
        return None, False, mode


def choose_thresholds():
    up = st.sidebar.file_uploader("Reference thresholds CSV (optional)", type="csv",
                                  help="Upload your own, properly sourced thresholds. Without an is_verified column, "
                                       "all rows are treated as verified by you.")
    allow_unverified = st.sidebar.checkbox("Use illustrative demo thresholds", value=True,
                                           help="Demo thresholds are NOT regulatory limits. Untick to see what "
                                                "happens when no verified thresholds exist.")
    try:
        return (dl.load_thresholds_csv(up) if up else cached_default_thresholds()), allow_unverified, bool(up)
    except dl.DataLoadError as exc:
        st.sidebar.error(str(exc))
        return None, allow_unverified, False


def sidebar_filters(df: pd.DataFrame):
    st.sidebar.header("Filters")
    st.sidebar.button("Reset filters", on_click=reset_filters)
    if df.empty:
        return an.ALL_REGIONS, an.ALL_PARAMETERS, None, an.ALL_STATUSES_LABEL, None
    regions = [an.ALL_REGIONS] + sorted(df["region"].dropna().unique())
    params = [an.ALL_PARAMETERS] + sorted(df["parameter"].dropna().unique())
    statuses = [an.ALL_STATUSES_LABEL] + ALL_STATUSES
    sources = sorted(df["data_source"].dropna().unique())
    for k, opts in (("f_region", regions), ("f_param", params), ("f_status", statuses)):
        keep_valid(k, opts)
    region = st.sidebar.selectbox("Region", regions, key="f_region")
    param = st.sidebar.selectbox("Parameter", params, key="f_param")
    dmin, dmax = df["sampling_date"].min().date(), df["sampling_date"].max().date()
    cur = st.session_state.get("f_dates")
    if isinstance(cur, tuple) and len(cur) == 2 and not (dmin <= cur[0] <= dmax and dmin <= cur[1] <= dmax):
        st.session_state.pop("f_dates")
    dates = st.sidebar.date_input("Sampling date range", value=(dmin, dmax), min_value=dmin, max_value=dmax,
                                  key="f_dates")
    dates = tuple(dates) if isinstance(dates, (tuple, list)) and len(dates) == 2 else (dmin, dmax)
    status = st.sidebar.selectbox("Measurement status", statuses, key="f_status")
    if "f_sources" in st.session_state:
        st.session_state["f_sources"] = [s for s in st.session_state["f_sources"] if s in sources]
    extra = {} if "f_sources" in st.session_state else {"default": sources}
    chosen = st.sidebar.multiselect("Data source", sources, key="f_sources", **extra)
    return region, param, dates, status, chosen


# ---------------------------------------------------------------- sections
def section_overview(df, quality, is_synthetic):
    st.header("Dashboard Overview")
    m = an.overview_metrics(df)
    c = st.columns(5)
    c[0].metric("Total measurements", m["total"])
    c[1].metric("Monitoring sites", m["sites"])
    c[2].metric("Regions", m["regions"])
    c[3].metric("Outside reference range", m["outside"], help="Below or above an applicable threshold")
    c[4].metric("Missing measurements", m["missing"], help="Missing values are never counted as zero")
    c = st.columns(3)
    c[0].metric("Recorded (value present)", m["recorded"])
    c[1].metric("Successfully assessed", m["assessed"])
    c[2].metric("Cannot be assessed", m["cannot_assess"], help="No verified threshold, unit mismatch, or invalid value")
    if m["total"]:
        counts = df["status"].value_counts().reindex(ALL_STATUSES, fill_value=0)
        st.bar_chart(pd.DataFrame({"Measurements": counts.values}, index=[status_label(s) for s in counts.index]),
                     horizontal=True)
    with st.expander("Data-quality summary", expanded=False):
        q = quality
        st.write(f"**{q['records_used']}** of **{q['records_in_file']}** records in the file are used "
                 f"(**{q['records_excluded']}** excluded). **{q['empty_measurements']}** records have no measured value.")
        for issue, n in q["issue_counts"].items():
            st.write(f"- {issue}: {n}")


def section_map(df):
    st.header("Geographic Monitoring Map")
    sites = an.site_summary(df)
    n_no_coords = int((~sites["has_coordinates"]).sum())
    if n_no_coords:
        st.caption(f"{n_no_coords} site(s) have no valid coordinates and cannot be shown on the map. "
                   "They are still listed in the site selector below.")
    fmap = viz.build_map(sites, df)
    if fmap is None:
        st.info("The map needs latitude/longitude. No site in the current selection has valid coordinates.")
    else:
        st.markdown(" &nbsp; ".join(f"**{status_label(s)}**" for s in
                                    [WITHIN, ABOVE, BELOW, MIXED, INSUFFICIENT]) +
                    "  \n<small>Marker icon + colour show the status. 'Mixed results' = readings at this site disagree; "
                    "'Insufficient data' = nothing could be assessed.</small>", unsafe_allow_html=True)
        out = st_folium(fmap, height=480, use_container_width=True, key="site_map",
                        returned_objects=["last_object_clicked_tooltip"])
        clicked = (out or {}).get("last_object_clicked_tooltip")
        if clicked and clicked != st.session_state.get("last_map_click"):
            st.session_state["last_map_click"] = clicked
            st.session_state["site_select"] = clicked
            st.rerun()

    labels = [f"{r.site_name} ({r.site_id})" for r in sites.itertuples()]
    keep_valid("site_select", labels)
    choice = st.selectbox("Selected site", labels, key="site_select")
    site_id = sites.iloc[labels.index(choice)]["site_id"]
    detail = df[df["site_id"] == site_id].sort_values(["parameter", "sampling_date"])
    row = sites[sites["site_id"] == site_id].iloc[0]
    st.subheader(f"{row['site_name']} - {row['region']}")
    st.write(f"Site status: **{status_label(row['status'])}** ({row['n_assessed']} of {row['n_measurements']} "
             "measurements could be assessed)")
    left, right = st.columns([3, 2])
    fig = viz.site_chart(detail)
    if fig:
        left.plotly_chart(fig, use_container_width=True)
    else:
        left.info("This site has no recorded values to chart.")
    right.dataframe(an.display_table(detail)[["sampling_date", "parameter", "measured_value", "unit",
                                              "reference_threshold", "assessment_status"]],
                    use_container_width=True, hide_index=True)


def section_analytics(df):
    st.header("Water Quality Analytics")
    params = sorted(df["parameter"].unique())
    param = st.selectbox("Parameter to analyse", params, key="a_param",
                         help="Charts show one parameter at a time so units are never mixed.")
    p_df = df[df["parameter"] == param]
    units = sorted(p_df["unit"].dropna().unique())
    if not units:
        st.warning("This parameter has no unit recorded.")
        return
    unit = units[0]
    if len(units) > 1:
        unit = st.selectbox("Unit (this parameter appears with several units)", units, key="a_unit")
        st.warning("Units are not converted. Only records with the chosen unit are analysed.")
    p_df = p_df[p_df["unit"] == unit]
    info = an.threshold_info(p_df)
    if info:
        verified = "" if info["verified"] else " - **illustrative / not verified**"
        st.caption(f"Reference: {info['reference_name'] or 'unnamed'} "
                   f"({info['source_organization'] or 'source not stated'}){verified}. "
                   f"Limits: {an.threshold_text(info['min'], info['max'], info['unit'])}.")
    else:
        st.caption("No applicable, usable reference threshold for these records - no limit lines are drawn. "
                   "(This is different from a missing measurement.)")
    if p_df["measured_value"].notna().sum() == 0:
        st.info("No recorded values for this parameter in the current selection.")
        return
    a, b = st.columns(2)
    for col, fig, note in ((a, viz.trend_chart(p_df, param, unit, info), "Gaps = missing measurements."),
                           (b, viz.regional_chart(an.regional_summary(p_df), param, unit), None),
                           (a, viz.distribution_chart(p_df, param, unit, info), None),
                           (b, viz.threshold_chart(p_df, param, unit, info), None)):
        if fig:
            col.plotly_chart(fig, use_container_width=True)
            if note:
                col.caption(note)
    stats = an.summary_stats(p_df)
    st.subheader("Summary statistics")
    if stats:
        st.dataframe(pd.DataFrame([{k: v for k, v in stats.items() if k != "excluded"}]).round(3),
                     hide_index=True, use_container_width=True)
        st.caption(f"Calculated from {stats['count']} recorded values; {stats['excluded']} record(s) without a value "
                   "were excluded. Descriptive statistics do not establish whether water is safe.")


def section_details(df):
    st.header("Measurement Details")
    table = an.display_table(df)
    st.dataframe(table, use_container_width=True, hide_index=True)
    c = st.columns(2)
    c[0].download_button("⬇️ Download filtered measurements (CSV)", table.to_csv(index=False).encode("utf-8"),
                         "filtered_water_quality.csv", "text/csv")
    summary = {"overview": an.overview_metrics(df), "rows": len(table)}
    c[1].download_button("⬇️ Download analysis summary (JSON)", json.dumps(summary, indent=2),
                         "analysis_summary.json", "application/json")


def section_ai(df, filters, is_synthetic):
    st.header("AI-Powered Insights")
    st.caption("Counts and threshold comparisons are calculated in Python first. Only that summary is sent to the AI, "
               "and only when you press the button.")
    api_key, model = ai.get_ai_config(get_secret)
    if not api_key:
        st.info("AI summaries are not configured. Set `OPENAI_API_KEY` (and optionally `OPENAI_MODEL`) in a `.env` "
                "file or `.streamlit/secrets.toml` - see the README. The rest of the dashboard works without it.")
    payload = an.build_ai_payload(df, filters, is_synthetic)
    signature = json.dumps(payload, sort_keys=True, default=str)
    if st.button("Explain My Results", type="primary", disabled=df.empty):
        with st.spinner("Writing a plain-language explanation..."):
            st.session_state["ai_result"] = (signature, ai.generate_summary(payload, api_key, model))
    saved = st.session_state.get("ai_result")
    if saved:
        sig, result = saved
        if sig != signature:
            st.warning("Filters or data have changed since this explanation was written. Press the button to refresh it.")
        if result.error:
            st.error(result.error)
        else:
            with st.container(border=True):
                if is_synthetic:
                    st.warning("Based on synthetic demo data - not real observations.")
                st.markdown(result.text)
                st.caption("AI-generated from the summary below. It may contain mistakes; "
                           "it is not a safety assessment.")
    with st.expander("Exactly what is sent to the AI"):
        st.json(payload)


def section_sources(issues, thresholds, using_demo_thresholds, is_synthetic):
    st.header("Data Sources and Limitations")
    st.markdown(
        "- **Measurements:** " + ("the built-in *synthetic* sample - invented for demonstration, not real observations."
                                   if is_synthetic else "the data you supplied. Check its provenance.") + "\n"
        "- **Reference thresholds:** "
        + ("the bundled *illustrative demo* ranges, which are **not** regulatory limits. " if using_demo_thresholds else
           "the thresholds you supplied. ")
        + "Confirm they suit the water type and intended use before relying on any comparison.\n"
        "- A reading inside or outside a range is **not** a safety verdict. 'Cannot assess' means a verified, "
        "unit-compatible threshold was unavailable.\n"
        "- No units are converted, no values are estimated, and missing values are never treated as zero.")
    st.subheader("Configured thresholds")
    if thresholds is None or thresholds.empty:
        st.info("No thresholds configured. All recorded measurements will show as 'Cannot assess'.")
    else:
        st.dataframe(thresholds, use_container_width=True, hide_index=True)
    st.subheader("Data-quality issues found")
    if issues.empty:
        st.success("No issues found.")
    else:
        st.dataframe(issues, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------- main
def main():
    st.title("Water Quality Dashboard")
    st.caption("Explore measurements against reference thresholds - with plain-language AI explanations.")
    raw, is_synthetic, label = choose_data()
    thresholds, allow_unverified, user_thresholds = choose_thresholds()
    if raw is None:
        raw = pd.DataFrame(columns=dl.REQUIRED_MEASUREMENT_COLUMNS)
        st.info("No data loaded yet. Pick 'Synthetic demo data', upload a CSV, or fetch live data.")
    try:
        clean, issues = dl.validate_measurements(raw)
    except dl.DataLoadError as exc:
        st.error(str(exc))
        clean, issues = dl.validate_measurements(pd.DataFrame(columns=dl.REQUIRED_MEASUREMENT_COLUMNS))
    quality = an.data_quality_summary(len(raw), clean, issues)
    assessed = assess_dataframe(clean, thresholds, allow_unverified)

    region, param, dates, status, sources = sidebar_filters(assessed)
    df = an.apply_filters(assessed, region, param, dates, status, sources)
    filters = {"region": region, "parameter": param, "status": status,
               "date_range": [str(d) for d in dates] if dates else None, "data_sources": sources}

    if is_synthetic:
        st.warning("**Synthetic demo data.** These measurements are invented for demonstration only.")
    if allow_unverified and not user_thresholds:
        st.warning("**Illustrative demo thresholds in use.** They are not verified regulatory limits.")

    tabs = st.tabs(["Overview", "Map", "Analytics", "Measurement Details", "AI Insights", "Sources & Limitations"])
    with tabs[0]:
        section_overview(df, quality, is_synthetic)
    empty_msg = "No measurements match the current filters. Adjust or reset the filters in the sidebar."
    for tab, fn in ((tabs[1], lambda: section_map(df)), (tabs[2], lambda: section_analytics(df)),
                    (tabs[3], lambda: section_details(df))):
        with tab:
            fn() if not df.empty else st.info(empty_msg)
    with tabs[4]:
        section_ai(df, filters, is_synthetic) if not df.empty else st.info(empty_msg)
    with tabs[5]:
        section_sources(issues, thresholds, allow_unverified and not user_thresholds, is_synthetic)


main()
