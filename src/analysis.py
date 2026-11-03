"""Filtering, metrics, statistics and AI-payload building. No Streamlit here."""
from __future__ import annotations

import pandas as pd

from src.threshold_validation import (ABOVE, ASSESSED_STATUSES, BELOW, CANNOT, INSUFFICIENT, MISSING,
                                      MIXED, WITHIN, status_label)

ALL_REGIONS, ALL_PARAMETERS, ALL_STATUSES_LABEL = "All regions", "All parameters", "All statuses"


def apply_filters(df, region=ALL_REGIONS, parameter=ALL_PARAMETERS, date_range=None,
                  status=ALL_STATUSES_LABEL, sources=None) -> pd.DataFrame:
    """Return a filtered copy. The original frame is untouched."""
    mask = pd.Series(True, index=df.index)
    if region != ALL_REGIONS:
        mask &= df["region"] == region
    if parameter != ALL_PARAMETERS:
        mask &= df["parameter"] == parameter
    if status != ALL_STATUSES_LABEL:
        mask &= df["status"] == status
    if sources is not None:
        mask &= df["data_source"].isin(sources)
    if date_range and len(date_range) == 2:
        day = df["sampling_date"].dt.normalize()
        mask &= (day >= pd.Timestamp(date_range[0])) & (day <= pd.Timestamp(date_range[1]))
    return df[mask].copy()


def overview_metrics(df) -> dict:
    s = df["status"]
    return {
        "total": int(len(df)),
        "sites": int(df["site_id"].nunique()),
        "regions": int(df["region"].nunique()),
        "recorded": int((s != MISSING).sum()),
        "assessed": int(s.isin(ASSESSED_STATUSES).sum()),
        "outside": int(s.isin([BELOW, ABOVE]).sum()),
        "missing": int((s == MISSING).sum()),
        "cannot_assess": int((s == CANNOT).sum()),
    }


def valid_values(df) -> pd.Series:
    return df.loc[df["measured_value"].notna(), "measured_value"]


def summary_stats(df) -> dict | None:
    """Descriptive stats on valid values only. Call with ONE parameter and ONE unit."""
    v = valid_values(df)
    if v.empty:
        return None
    return {"count": int(len(v)), "mean": float(v.mean()), "median": float(v.median()),
            "min": float(v.min()), "max": float(v.max()),
            "std": float(v.std(ddof=1)) if len(v) > 1 else None,
            "excluded": int(len(df) - len(v))}


def regional_summary(df) -> pd.DataFrame:
    v = df[df["measured_value"].notna()]
    if v.empty:
        return pd.DataFrame(columns=["region", "n", "sites", "mean", "median", "min", "max"])
    g = v.groupby("region")["measured_value"]
    out = g.agg(n="count", mean="mean", median="median", min="min", max="max")
    out["sites"] = v.groupby("region")["site_id"].nunique()
    return out.reset_index()


def site_summary(df) -> pd.DataFrame:
    """One row per site. Conflicting statuses -> 'Mixed results'; none assessed -> 'Insufficient data'."""
    cols = ["site_id", "site_name", "region", "latitude", "longitude", "has_coordinates",
            "status", "n_measurements", "n_assessed"]
    rows = []
    for site_id, g in df.groupby("site_id", sort=True):
        assessed = g.loc[g["status"].isin(ASSESSED_STATUSES), "status"].unique()
        status = INSUFFICIENT if len(assessed) == 0 else (assessed[0] if len(assessed) == 1 else MIXED)
        c = g.dropna(subset=["latitude", "longitude"])
        lat, lon = (c["latitude"].iloc[0], c["longitude"].iloc[0]) if not c.empty else (float("nan"),) * 2
        rows.append({"site_id": site_id, "site_name": g["site_name"].iloc[0], "region": g["region"].iloc[0],
                     "latitude": lat, "longitude": lon, "has_coordinates": not c.empty, "status": status,
                     "n_measurements": len(g), "n_assessed": int(g["status"].isin(ASSESSED_STATUSES).sum())})
    return pd.DataFrame(rows, columns=cols)


def threshold_text(tmin, tmax, unit) -> str:
    unit = unit or ""
    lo, hi = pd.notna(tmin), pd.notna(tmax)
    if lo and hi:
        return f"{tmin:g} to {tmax:g} {unit}".strip()
    if lo:
        return f"minimum {tmin:g} {unit}".strip()
    if hi:
        return f"maximum {tmax:g} {unit}".strip()
    return "not available"


def threshold_info(df) -> dict | None:
    """Threshold that was actually applied to rows in df (None if none was)."""
    applied = df[df["threshold_applied"]]
    if applied.empty:
        return None
    r = applied.iloc[0]
    return {"min": None if pd.isna(r["threshold_min"]) else float(r["threshold_min"]),
            "max": None if pd.isna(r["threshold_max"]) else float(r["threshold_max"]),
            "unit": r["threshold_unit"], "reference_name": r["reference_name"],
            "source_organization": r["source_organization"], "source_url": r["source_url"],
            "verified": r["threshold_verified"]}


def display_table(df) -> pd.DataFrame:
    """Readable table that is also used for the CSV export (no secrets, no internals)."""
    out = pd.DataFrame({
        "site_id": df["site_id"], "site_name": df["site_name"], "region": df["region"],
        "sampling_date": df["sampling_date"].dt.strftime("%Y-%m-%d"),
        "parameter": df["parameter"], "measured_value": df["measured_value"], "unit": df["unit"],
        "reference_threshold": [threshold_text(a, b, c) if t else "not applied / unavailable"
                                for a, b, c, t in zip(df["threshold_min"], df["threshold_max"],
                                                      df["threshold_unit"], df["threshold_applied"])],
        "reference_name": df["reference_name"], "assessment_status": df["status"],
        "status_reason": df["status_reason"], "data_source": df["data_source"]})
    return out.reset_index(drop=True)


def data_quality_summary(raw_count: int, clean: pd.DataFrame, issues: pd.DataFrame) -> dict:
    counts = issues["issue"].value_counts().to_dict() if not issues.empty else {}
    return {"records_in_file": int(raw_count), "records_used": int(len(clean)),
            "records_excluded": int(raw_count - len(clean)),
            "empty_measurements": int((clean["measured_value"].isna() & ~clean["value_invalid"]).sum())
            if len(clean) else 0,
            "issue_counts": {k: int(v) for k, v in counts.items()}}


def _r(x, n=3):
    return None if x is None or pd.isna(x) else round(float(x), n)


def build_ai_payload(df, filters: dict, is_synthetic: bool, max_flagged: int = 15) -> dict:
    """Compact, already-computed facts for the AI. Statuses come from Python, never from the model."""
    params = {}
    for p, g in df.groupby("parameter"):
        units = sorted(g["unit"].dropna().unique().tolist())
        entry = {"units": units, "records": int(len(g)), "valid_values": int(g["measured_value"].notna().sum()),
                 "status_counts": {k: int(v) for k, v in g["status"].value_counts().items()}}
        v = g.dropna(subset=["measured_value"])
        if len(units) == 1 and not v.empty:
            entry["values"] = {"min": _r(v["measured_value"].min()), "max": _r(v["measured_value"].max()),
                               "mean": _r(v["measured_value"].mean()), "median": _r(v["measured_value"].median())}
            by_date = v.groupby("sampling_date")["measured_value"].agg(["mean", "count"]).tail(12)
            if len(by_date) >= 3:
                entry["mean_by_date"] = [{"date": d.strftime("%Y-%m-%d"), "mean": _r(r["mean"]), "n": int(r["count"])}
                                         for d, r in by_date.iterrows()]
        info = threshold_info(g)
        if info:
            entry["threshold_used"] = info
        params[p] = entry
    flagged = df[df["status"].isin([BELOW, ABOVE])].sort_values("sampling_date").tail(max_flagged)
    regions = {r: {"records": int(len(g)), "outside_range": int(g["status"].isin([BELOW, ABOVE]).sum())}
               for r, g in df.groupby("region")}
    return {
        "data_is_synthetic_demo": bool(is_synthetic),
        "active_filters": filters,
        "totals": overview_metrics(df),
        "date_span": [df["sampling_date"].min().strftime("%Y-%m-%d"), df["sampling_date"].max().strftime("%Y-%m-%d")]
        if len(df) else None,
        "parameters": params,
        "regions": regions,
        "readings_outside_range": [{"site": r.site_name, "region": r.region, "date": r.sampling_date.strftime("%Y-%m-%d"),
                                    "parameter": r.parameter, "value": _r(r.measured_value), "unit": r.unit,
                                    "status": r.status} for r in flagged.itertuples()],
        "cannot_assess_reasons": {k: int(v) for k, v in
                                  df.loc[df["status"] == CANNOT, "status_reason"].value_counts().items()},
    }
