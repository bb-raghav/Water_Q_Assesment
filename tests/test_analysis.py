import io

import pandas as pd

from src import ai_summary, analysis as an, data_loader as dl
from src.threshold_validation import ABOVE, CANNOT, MISSING, WITHIN, assess_dataframe

TH = pd.DataFrame([{"parameter": "Nitrate", "minimum_value": None, "maximum_value": 10, "unit": "mg/L",
                    "reference_name": "R", "source_organization": "Org", "source_url": "",
                    "applicability_notes": "", "is_verified": "true"}])


def raw_rows(rows):
    base = dict(site_id="S1", site_name="A", region="R1", latitude="13", longitude="77",
                sampling_date="2025-01-01", parameter="Nitrate", measured_value="5", unit="mg/L", data_source="t")
    return pd.DataFrame([{**base, **r} for r in rows])


def prepared(rows):
    clean, issues = dl.validate_measurements(raw_rows(rows))
    return assess_dataframe(clean, TH), issues


def test_invalid_dates_are_excluded_and_reported():
    clean, issues = dl.validate_measurements(raw_rows([{}, {"sampling_date": "nope"}]))
    assert len(clean) == 1 and "Invalid sampling date" in set(issues["issue"])


def test_duplicates_are_removed_and_reported():
    clean, issues = dl.validate_measurements(raw_rows([{}, {}]))
    assert len(clean) == 1 and "Duplicate record" in set(issues["issue"])


def test_missing_and_invalid_coordinates_are_flagged_not_invented():
    clean, _ = dl.validate_measurements(raw_rows([{"latitude": "", "longitude": ""}, {"latitude": "999", "site_id": "S2"}]))
    assert not clean["has_coordinates"].any() and clean["latitude"].isna().all()
    assert an.site_summary(assess_dataframe(clean, TH))["has_coordinates"].eq(False).all()


def test_missing_value_is_not_counted_as_zero():
    df, _ = prepared([{"measured_value": ""}, {"measured_value": "4", "sampling_date": "2025-02-01"}])
    m = an.overview_metrics(df)
    assert m["missing"] == 1 and m["recorded"] == 1
    assert an.summary_stats(df)["mean"] == 4.0 and an.summary_stats(df)["excluded"] == 1


def test_invalid_numeric_text_is_kept_but_cannot_assess():
    df, issues = prepared([{"measured_value": "abc"}])
    assert df["status"].iloc[0] == CANNOT and "Invalid measured value" in set(issues["issue"])


def test_incompatible_units_reported_and_not_assessed():
    df, issues = prepared([{}, {"unit": "ug/L", "sampling_date": "2025-02-01"}])
    assert "Inconsistent units" in set(issues["issue"]) and set(df["status"]) == {WITHIN, CANNOT}


def test_filters_work_and_do_not_modify_original():
    df, _ = prepared([{}, {"region": "R2", "measured_value": "12", "site_id": "S2"}])
    before = df.copy()
    assert len(an.apply_filters(df, region="R2")) == 1
    assert an.apply_filters(df, status=ABOVE)["site_id"].tolist() == ["S2"]
    pd.testing.assert_frame_equal(df, before)


def test_no_records_match_filters_and_metrics_do_not_crash():
    df, _ = prepared([{}])
    empty = an.apply_filters(df, region="Nowhere")
    assert empty.empty and an.overview_metrics(empty)["total"] == 0
    assert an.summary_stats(empty) is None and an.site_summary(empty).empty


def test_empty_dataset_validates():
    clean, issues = dl.validate_measurements(pd.DataFrame(columns=dl.REQUIRED_MEASUREMENT_COLUMNS))
    assert clean.empty and issues.empty
    assert an.overview_metrics(assess_dataframe(clean, TH))["total"] == 0


def test_missing_required_columns_raise_clear_error():
    try:
        dl.load_measurements_csv(io.StringIO("a,b\n1,2\n"))
        assert False
    except dl.DataLoadError as e:
        assert "missing required columns" in str(e)


def test_site_with_conflicting_statuses_is_mixed():
    df, _ = prepared([{}, {"measured_value": "50", "sampling_date": "2025-02-01"}])
    assert an.site_summary(df)["status"].iloc[0] == "Mixed results"


def test_site_with_nothing_assessable_is_insufficient():
    df, _ = prepared([{"measured_value": ""}])
    assert an.site_summary(df)["status"].iloc[0] == "Insufficient data"


def test_ai_payload_contains_python_computed_facts():
    df, _ = prepared([{"measured_value": "50"}])
    p = an.build_ai_payload(df, {}, is_synthetic=True)
    assert p["data_is_synthetic_demo"] and p["totals"]["outside"] == 1
    assert p["parameters"]["Nitrate"]["threshold_used"]["max"] == 10


def test_ai_missing_credentials():
    r = ai_summary.generate_summary({}, None, "m")
    assert r.text is None and "API key" in r.error


def test_ai_api_failure_returns_error_not_fabricated_text():
    original = ai_summary._call_model

    class RateLimitError(Exception):
        pass

    def boom(*a, **k):
        raise RateLimitError("secret-ish detail")

    ai_summary._call_model = boom
    try:
        r = ai_summary.generate_summary({}, "key", "m")
    finally:
        ai_summary._call_model = original
    assert r.text is None and "rate limit" in r.error.lower() and "secret" not in r.error


def test_live_data_failure_is_handled():
    original = dl.requests.get

    def boom(*a, **k):
        raise dl.requests.ConnectionError("x")

    dl.requests.get = boom
    try:
        try:
            dl.fetch_live_data("http://example.invalid", "KEY123")
            assert False
        except dl.DataLoadError as e:
            assert "KEY123" not in str(e)
    finally:
        dl.requests.get = original
