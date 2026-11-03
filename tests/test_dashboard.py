import csv
import tempfile
import unittest
from pathlib import Path

from water_quality.api import DashboardAPI
from water_quality.assessment import assess_value, load_profiles
from water_quality.data import DataRepository


HEADER = [
    "SlNo", "Station", "Agency", "State LGD Code", "State", "District LGD Code",
    "District", "Tehsil", "Block", "Village", "River", "Latitude", "Longitude",
    "Data Acquisition Time", "Potential of Hydrogen (pH)", "Chloride (mg/L)", "Colour",
]


def sample_row(number, district, date, ph, chloride, colour="Clear", station="Lake A"):
    return [
        str(number), station, "CPCB", "29", "Karnataka", "525", district,
        "Bengaluru", "North", "", "", "13.00", "77.00", date, ph, chloride, colour,
    ]


class DashboardTests(unittest.TestCase):
    def fixture_repository(self):
        temporary = tempfile.TemporaryDirectory()
        folder = Path(temporary.name)
        path = folder / "swq_chemical_fixture.csv"
        with path.open("w", encoding="utf-8", newline="") as output:
            writer = csv.writer(output)
            writer.writerow(HEADER)
            writer.writerow(sample_row(1, "Bangalore Urban", "01-01-2020 09:00", "7", "25"))
            writer.writerow(sample_row(2, "Bangalore Urban", "02-01-2020 09:00", "", "45", "Colorless"))
            writer.writerow(sample_row(3, "Bangalore Urban", "03-01-2020 09:00", "9", "50"))
            writer.writerow(sample_row(4, "Other District", "04-01-2020 09:00", "8", "99"))
        return temporary, DataRepository(folder)

    def test_fixture_ingestion_preserves_missing_and_filters_district(self):
        temporary, repository = self.fixture_repository()
        self.addCleanup(temporary.cleanup)
        self.assertEqual(len(repository.samples), 3)
        self.assertEqual({sample["district"] for sample in repository.samples}, {"Bangalore Urban"})
        self.assertEqual(sum(dataset["source_rows"] for dataset in repository.datasets), 4)
        self.assertEqual(sum(dataset["included_rows"] for dataset in repository.datasets), 3)
        self.assertEqual(sum(dataset["excluded_out_of_scope_rows"] for dataset in repository.datasets), 1)
        missing_ph = [item for item in repository.observations if item["parameter_id"] == "ph" and item["is_missing"]]
        self.assertEqual(len(missing_ph), 1)
        self.assertTrue(all(sample["sample_date"] for sample in repository.samples))
        self.assertTrue(all(sample["coordinates_valid"] for sample in repository.samples))

    def test_statistics_are_correct_and_unit_specific(self):
        temporary, repository = self.fixture_repository()
        self.addCleanup(temporary.cleanup)
        result = repository.statistics({"parameter_key": "ph|"})
        self.assertEqual(result["count"], 1)
        stats = result["statistics"][0]
        self.assertEqual(stats["count"], 2)
        self.assertEqual(stats["mean"], 8)
        self.assertEqual(stats["median"], 8)
        self.assertEqual(stats["min"], 7)
        self.assertEqual(stats["max"], 9)
        self.assertEqual(stats["p25"], 7.5)
        self.assertEqual(stats["p75"], 8.5)
        self.assertEqual(stats["missing_count"], 1)
        self.assertAlmostEqual(stats["missing_percent"], 100 / 3)

    def test_api_filters_paginates_and_does_not_merge_samples(self):
        temporary, repository = self.fixture_repository()
        self.addCleanup(temporary.cleanup)
        api = DashboardAPI(repository)
        status, page = api.dispatch("/api/observations/", {"limit": ["2"], "offset": ["1"]})
        self.assertEqual(status, 200)
        self.assertEqual(page["count"], 9)
        self.assertEqual(len(page["results"]), 2)
        status, filtered = api.dispatch("/api/observations/", {"parameter_key": ["ph|"], "include_missing": ["false"]})
        self.assertEqual(status, 200)
        self.assertEqual(filtered["count"], 2)
        self.assertEqual(len({item["sample_id"] for item in repository.observations}), 3)
        status, heatmap = api.dispatch("/api/heatmap/", {"water_source": ["surface_water"], "parameter_key": ["ph|"]})
        self.assertEqual(status, 200)
        self.assertEqual(len(heatmap["features"]), 1)
        self.assertEqual(heatmap["features"][0]["properties"]["value"], 9)

    def test_assessment_statuses_distinguish_missing_and_limit_outcomes(self):
        profiles = load_profiles()["profiles"]
        profile = next(item for item in profiles if item["id"] == "groundwater_bis_10500")
        criterion = profile["criteria"][0]
        base = {"parameter_id": "ph", "parameter": "pH", "unit": "", "is_missing": False}
        self.assertEqual(assess_value({**base, "value": 7.0}, criterion)["status"], "within acceptable limits")
        self.assertEqual(assess_value({**base, "value": 9.0}, criterion)["status"], "above permissible limits")
        self.assertEqual(assess_value({**base, "value": 6.0}, criterion)["status"], "below permissible limits")
        self.assertEqual(assess_value({**base, "value": None, "is_missing": True}, criterion)["status"], "insufficient data")

    def test_all_project_csvs_load_and_scope_is_applied(self):
        project_data = Path(__file__).resolve().parents[1] / "data"
        repository = DataRepository(project_data)
        self.assertEqual(len(repository.datasets), 16)
        self.assertTrue(all(dataset["error"] is None for dataset in repository.datasets))
        self.assertEqual(len(repository.samples), sum(dataset["included_rows"] for dataset in repository.datasets))
        self.assertTrue(all(sample["district"].casefold() in {"bangalore urban", "bangalore rural"} for sample in repository.samples))
        self.assertEqual(len(repository.samples), 13840)
        self.assertTrue(all(sample["sample_date"] for sample in repository.samples))
        self.assertTrue(all(sample["coordinates_valid"] for sample in repository.samples))
        report = repository.data_quality()
        self.assertGreater(report["records_excluded_by_district_scope"], 0)
        self.assertGreater(report["missing_measurement_cells"], 0)

    def test_core_api_endpoints_return_expected_shapes(self):
        project_data = Path(__file__).resolve().parents[1] / "data"
        api = DashboardAPI(DataRepository(project_data))
        checks = {
            "/api/health/": "status",
            "/api/dashboard/overview/": "total_samples",
            "/api/water-sources/": "water_sources",
            "/api/parameters/": "parameters",
            "/api/stations/": "stations",
            "/api/statistics/": "statistics",
            "/api/standards/": "profiles",
            "/api/data-quality/": "dataset_reports",
            "/api/biological/": "summaries",
        }
        for path, expected_key in checks.items():
            with self.subTest(path=path):
                status, payload = api.dispatch(path, {})
                self.assertEqual(status, 200)
                self.assertIn(expected_key, payload)


if __name__ == "__main__":
    unittest.main()
