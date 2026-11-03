"""Deterministic threshold comparison. No AI and no Streamlit in this file."""
from __future__ import annotations

import math

import pandas as pd

WITHIN, BELOW, ABOVE = "Within range", "Below range", "Above range"
MISSING, CANNOT = "Missing", "Cannot assess"
MIXED, INSUFFICIENT = "Mixed results", "Insufficient data"  # site-level only
ASSESSED_STATUSES = [WITHIN, BELOW, ABOVE]
ALL_STATUSES = ASSESSED_STATUSES + [MISSING, CANNOT]
STATUS_ICONS = {WITHIN: "✅", BELOW: "🔻", ABOVE: "🔺", MISSING: "⚪", CANNOT: "❓",
                MIXED: "🔀", INSUFFICIENT: "❔"}
RESULT_COLUMNS = ["status", "status_reason", "threshold_min", "threshold_max", "threshold_unit",
                  "reference_name", "source_organization", "source_url", "applicability_notes",
                  "threshold_verified", "threshold_applied"]


def status_label(status: str) -> str:
    """Text + icon, so status never relies on colour alone."""
    return f"{STATUS_ICONS.get(status, '')} {status}".strip()


def _is_blank(x) -> bool:
    if x is None:
        return True
    try:
        if pd.isna(x):
            return True
    except (TypeError, ValueError):
        return False
    return isinstance(x, str) and not x.strip()


def _to_float(x):
    if _is_blank(x):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) or math.isinf(v) else v


def _truthy(x) -> bool:
    return (not _is_blank(x)) and str(x).strip().lower() in {"true", "yes", "y", "1"}


def _text(x):
    return None if _is_blank(x) else str(x).strip()


def normalize_unit(unit) -> str:
    return "" if _is_blank(unit) else str(unit).strip().lower().replace("μ", "µ")


def normalize_parameter(parameter) -> str:
    return "" if _is_blank(parameter) else " ".join(str(parameter).strip().lower().split())


def build_threshold_lookup(thresholds: pd.DataFrame | None) -> dict:
    """parameter -> threshold dict. First row per parameter wins.

    A missing is_verified column means the user supplied the file themselves and
    vouches for it; a blank value in that column counts as NOT verified.
    """
    lookup: dict = {}
    if thresholds is None or thresholds.empty:
        return lookup
    has_flag = "is_verified" in thresholds.columns
    for row in thresholds.to_dict("records"):
        key = normalize_parameter(row.get("parameter"))
        if not key or key in lookup:
            continue
        lookup[key] = {
            "min": _to_float(row.get("minimum_value")),
            "max": _to_float(row.get("maximum_value")),
            "unit": _text(row.get("unit")),
            "reference_name": _text(row.get("reference_name")),
            "source_organization": _text(row.get("source_organization")),
            "source_url": _text(row.get("source_url")),
            "applicability_notes": _text(row.get("applicability_notes")),
            "verified": _truthy(row.get("is_verified")) if has_flag else True,
        }
    return lookup


def assess_measurement(value, unit, parameter, lookup: dict, allow_unverified: bool = False,
                       value_invalid: bool = False) -> dict:
    """Compare one measurement with its threshold. Limits are inclusive."""
    res = {"status": CANNOT, "status_reason": "", "threshold_min": None, "threshold_max": None,
           "threshold_unit": None, "reference_name": None, "source_organization": None,
           "source_url": None, "applicability_notes": None, "threshold_verified": None,
           "threshold_applied": False}
    key = normalize_parameter(parameter)
    t = lookup.get(key) if key else None
    if t:
        res.update(threshold_min=t["min"], threshold_max=t["max"], threshold_unit=t["unit"],
                   reference_name=t["reference_name"], source_organization=t["source_organization"],
                   source_url=t["source_url"], applicability_notes=t["applicability_notes"],
                   threshold_verified=t["verified"])

    if value_invalid:
        res["status_reason"] = "Measured value is not a valid number."
        return res
    if _is_blank(value):
        res.update(status=MISSING, status_reason="No measurement was recorded.")
        return res
    v = _to_float(value)
    if v is None:
        res["status_reason"] = "Measured value is not a valid number."
        return res
    if not key:
        res["status_reason"] = "Parameter name is missing."
        return res
    if t is None:
        res["status_reason"] = "No reference threshold is configured for this parameter."
        return res
    if not t["verified"] and not allow_unverified:
        res["status_reason"] = "Reference threshold is not marked as verified."
        return res
    if t["min"] is None and t["max"] is None:
        res["status_reason"] = "Threshold has no minimum or maximum limit."
        return res
    if not normalize_unit(unit) or normalize_unit(unit) != normalize_unit(t["unit"]):
        res["status_reason"] = (f"Unit '{unit}' does not match threshold unit '{t['unit']}'. "
                                "No unit conversion is attempted.")
        return res

    res["threshold_applied"] = True
    if t["min"] is not None and v < t["min"]:
        res.update(status=BELOW, status_reason=f"{v:g} is below the minimum {t['min']:g}.")
    elif t["max"] is not None and v > t["max"]:
        res.update(status=ABOVE, status_reason=f"{v:g} is above the maximum {t['max']:g}.")
    else:
        res.update(status=WITHIN, status_reason="Within the configured limits (limits inclusive).")
    return res


def assess_dataframe(df: pd.DataFrame, thresholds: pd.DataFrame | None,
                     allow_unverified: bool = False) -> pd.DataFrame:
    """Return a copy of df with assessment columns. The input is never modified."""
    lookup = build_threshold_lookup(thresholds)
    out = df.drop(columns=[c for c in RESULT_COLUMNS if c in df.columns]).copy()
    invalid = df["value_invalid"] if "value_invalid" in df.columns else pd.Series(False, index=df.index)
    rows = [assess_measurement(v, u, p, lookup, allow_unverified, bool(bad))
            for v, u, p, bad in zip(df["measured_value"], df["unit"], df["parameter"], invalid)]
    res = pd.DataFrame(rows, index=df.index, columns=RESULT_COLUMNS)
    for c in ("threshold_min", "threshold_max"):
        res[c] = pd.to_numeric(res[c], errors="coerce")
    res["threshold_applied"] = res["threshold_applied"].astype(bool)
    return pd.concat([out, res], axis=1)
