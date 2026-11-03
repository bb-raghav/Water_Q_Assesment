"""Loading and validating data. No Streamlit in this file, so it is easy to test."""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import requests

REQUIRED_MEASUREMENT_COLUMNS = ["site_id", "site_name", "region", "latitude", "longitude",
                                "sampling_date", "parameter", "measured_value", "unit", "data_source"]
REQUIRED_THRESHOLD_COLUMNS = ["parameter", "minimum_value", "maximum_value", "unit", "reference_name",
                              "source_organization", "source_url", "applicability_notes"]
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SAMPLE_PATH = DATA_DIR / "sample_water_quality.csv"
THRESHOLD_PATH = DATA_DIR / "reference_thresholds.csv"


class DataLoadError(Exception):
    """Raised with a message that is safe to show to the user (never contains secrets)."""


def load_env_file(path: str = ".env") -> None:
    """Tiny .env reader (avoids an extra dependency). Existing env vars win."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _read_csv(source) -> pd.DataFrame:
    try:
        return pd.read_csv(source, dtype=str, keep_default_na=False, na_values=[""])
    except FileNotFoundError:
        raise DataLoadError("The data file could not be found.")
    except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as exc:
        raise DataLoadError(f"The CSV file could not be read ({type(exc).__name__}).")


def _check_columns(df: pd.DataFrame, required: list[str], label: str) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise DataLoadError(f"{label} is missing required columns: {', '.join(missing)}")


def load_measurements_csv(source=SAMPLE_PATH) -> pd.DataFrame:
    df = _read_csv(source)
    _check_columns(df, REQUIRED_MEASUREMENT_COLUMNS, "Measurement data")
    return df


def load_thresholds_csv(source=THRESHOLD_PATH) -> pd.DataFrame:
    df = _read_csv(source)
    _check_columns(df, REQUIRED_THRESHOLD_COLUMNS, "Threshold data")
    for c in ("minimum_value", "maximum_value"):
        df[c] = pd.to_numeric(df[c], errors="coerce")  # blank = no limit
    return df


def validate_measurements(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (clean_df, issues_df). The raw frame is never modified.

    Excluded: invalid dates, missing site/parameter, exact duplicates.
    Kept but flagged: invalid values (value_invalid), bad coordinates (has_coordinates=False).
    """
    _check_columns(raw, REQUIRED_MEASUREMENT_COLUMNS, "Measurement data")
    df = raw[REQUIRED_MEASUREMENT_COLUMNS].copy().reset_index(drop=True)
    df.insert(0, "source_row", df.index + 2)  # +2 = spreadsheet row incl. header
    issues: list[dict] = []

    def note(mask, issue, detail):
        for _, r in df[mask].iterrows():
            issues.append({"source_row": r["source_row"], "site_id": r["site_id"], "issue": issue, "detail": detail})

    for c in ("site_id", "site_name", "region", "parameter", "unit", "data_source"):
        df[c] = df[c].astype("string").str.strip().replace("", pd.NA)
    df["data_source"] = df["data_source"].fillna("Unknown source")

    drop = df["site_id"].isna() | df["parameter"].isna()
    note(drop, "Missing site_id or parameter", "Record excluded.")
    df = df[~drop].copy()

    df["sampling_date"] = pd.to_datetime(df["sampling_date"], errors="coerce")
    bad_date = df["sampling_date"].isna()
    note(bad_date, "Invalid sampling date", "Record excluded.")
    df = df[~bad_date].copy()

    value_text = df["measured_value"].astype("string").str.strip().replace("", pd.NA)
    numeric = pd.to_numeric(value_text, errors="coerce")
    df["value_invalid"] = value_text.notna() & (numeric.isna() | ~pd.Series(
        [pd.notna(v) and abs(v) != float("inf") for v in numeric], index=df.index))
    df["measured_value"] = numeric.where(~df["value_invalid"])
    note(df["value_invalid"], "Invalid measured value", "Kept; treated as 'Cannot assess'.")

    for c in ("latitude", "longitude"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    ok_coords = df["latitude"].between(-90, 90) & df["longitude"].between(-180, 180)
    df["has_coordinates"] = ok_coords
    note(~ok_coords, "Missing or invalid coordinates", "Kept; site cannot be shown on the map.")
    df.loc[~ok_coords, ["latitude", "longitude"]] = float("nan")

    dup = df.duplicated(subset=["site_id", "sampling_date", "parameter", "measured_value", "unit"], keep="first")
    note(dup, "Duplicate record", "Later copy excluded.")
    df = df[~dup].copy()

    units = df.groupby(df["parameter"].str.lower())["unit"].nunique()
    for p in units[units > 1].index:
        issues.append({"source_row": None, "site_id": None, "issue": "Inconsistent units",
                       "detail": f"Parameter '{p}' appears with more than one unit. No conversion is attempted."})

    clean = df.reset_index(drop=True)
    issues_df = pd.DataFrame(issues, columns=["source_row", "site_id", "issue", "detail"])
    return clean, issues_df


def fetch_live_data(url: str, api_key: str | None = None, timeout: float = 10.0) -> pd.DataFrame:
    """Fetch JSON records from a user-configured provider. No endpoint is assumed."""
    if not url:
        raise DataLoadError("No live data URL is configured.")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
    except requests.Timeout:
        raise DataLoadError("The data provider timed out. Try again later.")
    except requests.RequestException:
        raise DataLoadError("Could not reach the data provider (network error).")
    if resp.status_code == 429:
        raise DataLoadError("The data provider rate limit was reached. Try again later.")
    if resp.status_code in (401, 403):
        raise DataLoadError("The data provider rejected the credentials.")
    if not resp.ok:
        raise DataLoadError(f"The data provider returned HTTP {resp.status_code}.")
    try:
        payload = resp.json()
    except ValueError:
        raise DataLoadError("The data provider did not return valid JSON.")
    records = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise DataLoadError("Unexpected response shape: expected a list of records.")
    df = pd.DataFrame(records).astype(object).where(lambda d: d.notna(), None)
    if "data_source" not in df.columns:
        df["data_source"] = "Live API"
    _check_columns(df, REQUIRED_MEASUREMENT_COLUMNS, "Live data")
    return df
