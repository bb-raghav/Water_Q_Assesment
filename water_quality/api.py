"""HTTP API response builders for the water quality dashboard."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any
from urllib.parse import unquote

from .assessment import assess_observation, load_profiles
from .data import DataRepository


class DashboardAPI:
    def __init__(self, repository: DataRepository | None = None):
        self.repository = repository or DataRepository()
        standards = load_profiles()
        self.profiles = {profile["id"]: profile for profile in standards["profiles"]}
        self.overall_assessment_note = standards["overall_assessment_note"]

    @staticmethod
    def _query(query: dict[str, list[str]]) -> dict[str, str]:
        return {key: values[-1] for key, values in query.items() if values}

    def _filtered_samples(self, query: dict[str, str]) -> list[dict[str, Any]]:
        result = []
        source = query.get("water_source", "").casefold()
        category = query.get("category", "").casefold()
        district = query.get("district", "").casefold()
        station = query.get("station", "").casefold()
        location = query.get("location", "").casefold()
        station_id = query.get("station_id", "").casefold()
        start_date, end_date = query.get("start_date", ""), query.get("end_date", "")
        for sample in self.repository.samples:
            if source and sample["water_source"] != source:
                continue
            if category and sample["category"] != category:
                continue
            if district and district not in sample["district"].casefold():
                continue
            if station and station not in sample["station"].casefold():
                continue
            if station_id and station_id != sample["station_id"].casefold():
                continue
            if location and location not in " ".join((sample["location"], sample["district"], sample["tehsil"], sample["block"], sample["village"], sample["river"])).casefold():
                continue
            if (start_date or end_date) and not sample["sample_date"]:
                continue
            sample_day = (sample["sample_date"] or "")[:10]
            if start_date and sample_day < start_date:
                continue
            if end_date and sample_day > end_date:
                continue
            result.append(sample)
        return result

    def _overview(self, query: dict[str, str]) -> dict[str, Any]:
        samples = self._filtered_samples(query)
        sources = Counter(sample["water_source"] for sample in samples)
        categories = Counter(sample["category"] for sample in samples)
        stations = {sample["station_id"] for sample in samples}
        parameter_keys = {
            (measurement["parameter_id"], measurement["unit"])
            for sample in samples for measurement in sample["measurements"]
        }
        latest = sorted(
            (measurement for sample in samples for measurement in sample["measurements"] if not measurement["is_missing"]),
            key=lambda item: item["sample_date"] or "",
            reverse=True,
        )[:15]
        profile_id = query.get("profile", "")
        assessment_summary = None
        if profile_id in self.profiles:
            assessment = self._assessment({"profile": profile_id, **query})
            assessment_summary = assessment["status_counts"]
        return {
            "total_samples": len(samples),
            "total_measurements": sum(len(sample["measurements"]) for sample in samples),
            "groundwater_samples": sources["groundwater"],
            "surface_water_samples": sources["surface_water"],
            "monitoring_stations": len(stations),
            "parameters": len(parameter_keys),
            "locations": len({sample["district"] for sample in samples if sample["district"]}),
            "dataset_coverage": len({sample["dataset_source"] for sample in samples}),
            "available_datasets": len(self.repository.datasets),
            "water_source_distribution": dict(sources),
            "category_distribution": dict(categories),
            "latest_observations": latest,
            "assessment_status_counts": assessment_summary,
            "districts": sorted({sample["district"] for sample in samples if sample["district"]}),
        }

    def _stations(self, query: dict[str, str]) -> list[dict[str, Any]]:
        samples = self._filtered_samples(query)
        station_map: dict[str, dict[str, Any]] = {}
        for sample in samples:
            station = station_map.setdefault(sample["station_id"], {
                "station_id": sample["station_id"], "station": sample["station"],
                "district": sample["district"], "location": sample["location"],
                "latitude": sample["latitude"], "longitude": sample["longitude"],
                "water_source": sample["water_source"], "agency": sample["agency"],
                "sample_count": 0, "latest_sample_date": None,
            })
            station["sample_count"] += 1
            if sample["sample_date"] and (not station["latest_sample_date"] or sample["sample_date"] > station["latest_sample_date"]):
                station["latest_sample_date"] = sample["sample_date"]
        return sorted(station_map.values(), key=lambda item: (item["district"].casefold(), item["station"].casefold()))

    def _heatmap(self, query: dict[str, str]) -> dict[str, Any]:
        parameter = query.get("parameter", "")
        parameter_key = query.get("parameter_key", "")
        source = query.get("water_source", "")
        if not (parameter or parameter_key) or not source:
            raise ValueError("Heatmap requires water_source and parameter query parameters.")
        measurements = self.repository.filters({**query, "include_missing": "false"})
        measurements = [item for item in measurements if item["value"] is not None and item["latitude"] is not None and item["longitude"] is not None]
        latest_by_station: dict[str, dict[str, Any]] = {}
        for item in measurements:
            previous = latest_by_station.get(item["station_id"])
            if previous is None or (item["sample_date"] or "") > (previous["sample_date"] or ""):
                latest_by_station[item["station_id"]] = item
        sample_by_id = {sample["sample_id"]: sample for sample in self.repository.samples}
        features = []
        for item in latest_by_station.values():
            sample = sample_by_id[item["sample_id"]]
            measurement_details = [
                {"parameter": measurement["parameter"], "value": measurement["value"],
                 "value_text": measurement["value_text"], "unit": measurement["unit"],
                 "is_missing": measurement["is_missing"]}
                for measurement in sample["measurements"]
                if not measurement["is_missing"]
            ]
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [item["longitude"], item["latitude"]]},
                "properties": {
                    "sample_id": item["sample_id"], "station_id": item["station_id"],
                    "station": item["station"], "location": item["location"],
                    "district": item["district"], "water_source": item["water_source"],
                    "sample_date": item["sample_date"], "parameter": item["parameter"],
                    "value": item["value"], "unit": item["unit"],
                    "dataset_source": item["dataset_source"], "agency": item["agency"],
                    "measurement_details": measurement_details,
                },
            })
        values = [feature["properties"]["value"] for feature in features]
        return {
            "type": "FeatureCollection", "features": features,
            "parameter": parameter or parameter_key, "water_source": source,
            "value_range": {"min": min(values) if values else None, "max": max(values) if values else None},
            "visualization_note": "Each point is an observed station value (latest within the selected date range). No spatial interpolation is used.",
        }

    def _comparison(self, query: dict[str, str]) -> dict[str, Any]:
        parameter = query.get("parameter", "")
        parameter_key = query.get("parameter_key", "")
        if not (parameter or parameter_key):
            raise ValueError("Comparison requires a parameter query parameter.")
        compare_by = query.get("compare_by", "water_source")
        allowed = {"water_source", "district", "station", "category", "agency", "date"}
        if compare_by not in allowed:
            raise ValueError(f"compare_by must be one of: {', '.join(sorted(allowed))}")
        observations = self.repository.filters({**query, "include_missing": "false"})
        groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for item in observations:
            if item["value"] is None:
                continue
            group_value = (item["sample_date"] or "")[:10] if compare_by == "date" else item.get(compare_by, "")
            groups[(str(group_value or "Unknown"), item["unit"])].append(item)
        results = []
        for (group_value, unit), items in sorted(groups.items()):
            results.append({
                "group": group_value,
                "unit": unit,
                "water_sources": sorted({item["water_source"] for item in items}),
                "sample_count": len({item["sample_id"] for item in items}),
                "observation_count": len(items),
                "distribution_values": [item["value"] for item in items[:2000]],
                "distribution_truncated": len(items) > 2000,
                **self.repository._statistics_for(items),
            })
        return {"parameter": parameter or parameter_key, "compare_by": compare_by, "comparisons": results, "note": "Results with different units are kept in separate groups."}

    def _trends(self, query: dict[str, str]) -> dict[str, Any]:
        parameter = query.get("parameter", "")
        parameter_key = query.get("parameter_key", "")
        if not (parameter or parameter_key):
            raise ValueError("Trends require a parameter query parameter.")
        observations = [item for item in self.repository.filters({**query, "include_missing": "false"}) if item["value"] is not None]
        observations.sort(key=lambda item: (item["sample_date"] or "", item["station"].casefold()))
        limit = max(1, min(int(query.get("limit", "5000")), 10000))
        return {
            "parameter": parameter or parameter_key,
            "observations": observations[:limit],
            "count": len(observations),
            "truncated": len(observations) > limit,
            "note": "Points are actual observations; no values are generated or interpolated over time.",
        }

    def _assessment(self, query: dict[str, str]) -> dict[str, Any]:
        profile_id = query.get("profile", "")
        if profile_id not in self.profiles:
            raise ValueError("Choose a valid assessment profile. See /api/standards/ for available profiles.")
        profile = self.profiles[profile_id]
        expected_ids = {criterion["parameter_id"] for criterion in profile["criteria"]}
        observations = self.repository.filters({**query, "water_source": profile["water_source"]})
        results = []
        for observation in observations:
            if observation["parameter_id"] not in expected_ids:
                continue
            assessed = assess_observation(observation, profile)
            if assessed:
                results.append(assessed)
        counts = Counter(item["status"] for item in results)
        criteria_coverage = []
        for criterion in profile["criteria"]:
            criterion_results = [item for item in results if item["parameter_id"] == criterion["parameter_id"]]
            if not criterion_results or criterion.get("method_confirmed") is False:
                coverage_status = "not assessed"
            elif all(item["status"] == "not assessed" for item in criterion_results):
                coverage_status = "not assessed"
            else:
                coverage_status = "available"
            criteria_coverage.append({
                "parameter_id": criterion["parameter_id"],
                "parameter": criterion["parameter"],
                "unit": criterion["unit"],
                "records_found": len(criterion_results),
                "status": coverage_status,
                "method_note": criterion.get("method_note"),
            })
        return {
            "profile": {key: value for key, value in profile.items() if key != "criteria"},
            "criteria_coverage": criteria_coverage,
            "status_counts": dict(counts),
            "assessed_parameter_observations": len(results),
            "results": results,
            "overall_assessment_note": self.overall_assessment_note,
        }

    def _biological(self, query: dict[str, str]) -> dict[str, Any]:
        observations = self.repository.filters({**query, "category": "biological"})
        groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
        for item in observations:
            groups[(item["parameter_id"], item["parameter"], item["unit"])].append(item)
        summaries = []
        for (parameter_id, parameter, unit), items in sorted(groups.items()):
            values = [item["value"] for item in items if item["value"] is not None]
            detected = [value for value in values if value > 0]
            summaries.append({
                "parameter_id": parameter_id, "parameter": parameter, "unit": unit,
                "observation_count": len(items), "measured_count": len(values),
                "missing_count": sum(item["is_missing"] for item in items),
                "positive_count": len(detected),
                "positive_percent_of_measured": len(detected) / len(values) * 100 if values else None,
                "mean": sum(values) / len(values) if values else None,
                "note": "Positive values are reported as measured; detection is not a safety classification.",
            })
        return {"summaries": summaries, "note": "Parameters and units are summarized separately; qualitative fields are not interpreted as numeric detections."}

    def dispatch(self, path: str, raw_query: dict[str, list[str]]) -> tuple[int, Any]:
        query = self._query(raw_query)
        try:
            if path == "/api/health/":
                return 200, {"status": "ok", "samples_loaded": len(self.repository.samples)}
            if path == "/api/dashboard/overview/":
                return 200, self._overview(query)
            if path == "/api/water-sources/":
                overview = self._overview(query)
                return 200, {"water_sources": [
                    {"id": "groundwater", "name": "Groundwater", "sample_count": overview["groundwater_samples"]},
                    {"id": "surface_water", "name": "Surface water", "sample_count": overview["surface_water_samples"]},
                ]}
            if path == "/api/parameters/":
                source = query.get("water_source", "").casefold()
                category = query.get("category", "").casefold()
                parameters = [item for item in self.repository._metadata["parameters"]
                              if (not source or source in item["water_sources"])
                              and (not category or category in item["categories"])]
                return 200, {"parameters": parameters}
            if path == "/api/stations/":
                stations = self._stations(query)
                return 200, {"count": len(stations), "stations": stations}
            if path == "/api/observations/":
                items = self.repository.filters(query)
                try:
                    limit = max(1, min(int(query.get("limit", "100")), 1000))
                    offset = max(0, int(query.get("offset", "0")))
                except ValueError:
                    raise ValueError("limit and offset must be integers.")
                return 200, {"count": len(items), "limit": limit, "offset": offset, "results": items[offset:offset + limit]}
            if path.startswith("/api/observations/") and path != "/api/observations/":
                station_id = unquote(path.removeprefix("/api/observations/").strip("/"))
                items = [item for item in self.repository.observations if item["station_id"] == station_id]
                items.sort(key=lambda item: (item["sample_date"] or "", item["dataset_source"], item["parameter"].casefold()))
                return 200, {"station_id": station_id, "count": len(items), "observations": items}
            if path == "/api/statistics/":
                return 200, self.repository.statistics(query)
            if path == "/api/heatmap/":
                return 200, self._heatmap(query)
            if path == "/api/comparison/":
                return 200, self._comparison(query)
            if path == "/api/trends/":
                return 200, self._trends(query)
            if path == "/api/standards/":
                return 200, {"profiles": list(self.profiles.values()), "overall_assessment_note": self.overall_assessment_note}
            if path == "/api/assessment/":
                return 200, self._assessment(query)
            if path == "/api/data-quality/":
                return 200, self.repository.data_quality()
            if path == "/api/biological/":
                return 200, self._biological(query)
            return 404, {"error": "Endpoint not found."}
        except ValueError as exc:
            return 400, {"error": str(exc)}
        except (KeyError, TypeError) as exc:
            return 500, {"error": "Unable to build response.", "detail": str(exc)}
