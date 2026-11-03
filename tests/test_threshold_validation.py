import pandas as pd

from src.threshold_validation import (ABOVE, BELOW, CANNOT, MISSING, WITHIN, assess_dataframe,
                                      assess_measurement, build_threshold_lookup)

TH = pd.DataFrame([
    {"parameter": "pH", "minimum_value": 6.5, "maximum_value": 8.5, "unit": "pH units", "reference_name": "R",
     "source_organization": "Org", "source_url": "", "applicability_notes": "", "is_verified": "true"},
    {"parameter": "Nitrate", "minimum_value": None, "maximum_value": 10, "unit": "mg/L", "reference_name": "R",
     "source_organization": "Org", "source_url": "", "applicability_notes": "", "is_verified": "true"},
    {"parameter": "DO", "minimum_value": 5, "maximum_value": None, "unit": "mg/L", "reference_name": "R",
     "source_organization": "Org", "source_url": "", "applicability_notes": "", "is_verified": "false"},
])
LK = build_threshold_lookup(TH)


def status(value, unit, parameter, **kw):
    return assess_measurement(value, unit, parameter, LK, **kw)["status"]


def test_within_range_and_inclusive_limits():
    assert status(7.0, "pH units", "pH") == WITHIN
    assert status(6.5, "pH units", "pH") == WITHIN
    assert status(8.5, "pH units", "pH") == WITHIN


def test_below_minimum():
    assert status(6.0, "pH units", "pH") == BELOW


def test_above_maximum():
    assert status(9.0, "pH units", "pH") == ABOVE


def test_one_sided_limits_only_apply_configured_side():
    assert status(0.1, "mg/L", "Nitrate") == WITHIN  # no minimum configured
    assert status(11, "mg/L", "Nitrate") == ABOVE


def test_missing_measurement_is_not_zero_or_within():
    assert status(None, "mg/L", "Nitrate") == MISSING
    assert status(float("nan"), "mg/L", "Nitrate") == MISSING


def test_missing_threshold_cannot_assess():
    assert status(5, "mg/L", "Arsenic") == CANNOT


def test_incompatible_units_cannot_assess():
    r = assess_measurement(5, "FNU", "Nitrate", LK)
    assert r["status"] == CANNOT and "unit" in r["status_reason"].lower()


def test_unverified_threshold_needs_explicit_opt_in():
    assert status(3, "mg/L", "DO") == CANNOT
    assert status(3, "mg/L", "DO", allow_unverified=True) == BELOW


def test_invalid_value_cannot_assess():
    assert status(5, "mg/L", "Nitrate", value_invalid=True) == CANNOT


def test_parameter_matching_is_case_insensitive():
    assert status(7, "PH UNITS", " ph ") == WITHIN


def test_assess_dataframe_does_not_modify_input_and_handles_empty():
    df = pd.DataFrame({"measured_value": [7.0, None], "unit": ["pH units", "pH units"], "parameter": ["pH", "pH"]})
    before = df.copy()
    out = assess_dataframe(df, TH)
    assert list(out["status"]) == [WITHIN, MISSING]
    pd.testing.assert_frame_equal(df, before)
    empty = assess_dataframe(df.iloc[0:0], TH)
    assert empty.empty and "status" in empty.columns


def test_no_thresholds_at_all():
    df = pd.DataFrame({"measured_value": [7.0], "unit": ["x"], "parameter": ["pH"]})
    assert assess_dataframe(df, None)["status"].iloc[0] == CANNOT
