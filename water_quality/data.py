"""CSV ingestion, provenance, filtering, and descriptive data summaries."""

from __future__ import annotations

import csv
import math
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean, median, pstdev
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
TARGET_DISTRICTS = {"bangalore urban", "bangalore rural"}
MISSING_MARKERS = {"", "-", "null", "none", "nan", "na", "n/a"}

METADATA_FIELDS = {
    "slno", "station", "agency", "state lgd code", "state", "district lgd code",
    "district", "tehsil", "block", "village", "river", "basin", "tributary",
    "subtributary", "subsubtributary", "local river", "latitude", "longitude",
    "data acquisition time",
}

ALIASES = {
    "potential of hydrogen ph": "pH",
    "potential of hydrogen": "pH",
    "ph": "pH",
    "electric conductivity": "Electrical Conductivity",
    "electrical conductivity": "Electrical Conductivity",
    "total dissolved solids": "Total Dissolved Solids",
    "biochemical oxygen demand": "Biochemical Oxygen Demand",
    "chemical oxygen demand": "Chemical Oxygen Demand",
    "fecal coliform": "Faecal Coliform",
    "faecal coliform": "Faecal Coliform",
    "total coliform": "Total Coliform",
    "amonia n": "Ammonia-N",
    "ammonia n": "Ammonia-N",
    "nitrate n": "Nitrate-N",
    "nitrite n nitrate n": "Nitrite + Nitrate-N",
    "total hardness": "Total Hardness",
    "dissolved oxygen": "Dissolved Oxygen",
    "total alkalinity": "Total Alkalinity",
    "sodium adsorption ratio": "Sodium Adsorption Ratio",
}

QUALITATIVE_PARAMETERS = {"colour", "color", "odour", "odor"}


def _words(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def _district_key(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def _parse_date(value: str) -> tuple[str | None, str | None]:
    raw = value.strip()
    if not raw:
        return None, None
    formats = (
        "%d-%m-%Y %H:%M", "%d-%m-%Y", "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d",
    )
    for date_format in formats:
        try:
            parsed = datetime.strptime(raw, date_format)
            return parsed.isoformat(timespec="minutes" if parsed.time().second == 0 else "seconds"), None
        except ValueError:
            continue
    return None, raw


def _number(value: str) -> float | None:
    cleaned = value.strip().replace(",", "")
    if not cleaned or cleaned.casefold() in MISSING_MARKERS:
        return None
    try:
        parsed = float(cleaned)
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def _unit(header: str, parameter_id: str) -> str:
    if parameter_id == "ph":
        return ""
    match = re.search(r"\(([^()]*)\)\s*$", header.strip())
    if not match:
        return ""
    value = match.group(1).strip().replace("μ", "µ")
    if value.casefold() == "ºc":
        return "°C"
    return value


def parameter_info(header: str) -> dict[str, str]:
    match = re.search(r"\(([^()]*)\)\s*$", header.strip())
    base = header[:match.start()].strip() if match else header.strip()
    normalized = _words(base)
    display = ALIASES.get(normalized, base.strip().rstrip(".,;:").title())
    if display.casefold() == "ph":
        display = "pH"
    parameter_id = _words(display).replace(" ", "_")
    return {
        "parameter": display,
        "parameter_id": parameter_id,
        "unit": _unit(header, parameter_id),
    }


def _classify_dataset(path: Path) -> tuple[str, str]:
    stem = path.stem.casefold()
    source = "groundwater" if stem.startswith("gwq_") else "surface_water"
    if "biological" in stem:
        category = "biological"
    elif "physical" in stem:
        category = "physical"
    elif "chemical" in stem:
        category = "chemical"
    else:
        category = "other"
    return source, category


def _station_id(source: str, agency: str, station: str, district: str, lat: float | None, lon: float | None) -> str:
    parts = (source, agency, station, district, "" if lat is None else f"{lat:.5f}", "" if lon is None else f"{lon:.5f}")
    return "|".join(" ".join(part.strip().casefold().split()) for part in parts)


class DataRepository:
    """Loads source CSVs once and keeps each source row as a distinct sample."""

    def __init__(self, data_dir: Path = DATA_DIR, districts: set[str] | None = None):
        self.data_dir = data_dir
        self.districts = districts or TARGET_DISTRICTS
        self.samples: list[dict[str, Any]] = []
        self.datasets: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if not self.data_dir.is_dir():
            raise FileNotFoundError(f"Dataset directory not found: {self.data_dir}")

        for path in sorted(self.data_dir.glob("*.csv")):
            source, category = _classify_dataset(path)
            dataset_report: dict[str, Any] = {
                "dataset_source": path.name,
                "water_source": source,
                "category": category,
                "source_rows": 0,
                "included_rows": 0,
                "excluded_out_of_scope_rows": 0,
                "measurement_columns": 0,
                "exact_duplicate_rows": 0,
                "duplicate_station_date_rows": 0,
                "missing_measurements": 0,
                "invalid_dates": 0,
                "missing_dates": 0,
                "missing_coordinates": 0,
                "invalid_coordinates": 0,
                "invalid_numeric_values": 0,
                "parameters": [],
                "error": None,
            }
            try:
                with path.open("r", encoding="utf-8-sig", newline="") as input_file:
                    reader = csv.reader(input_file)
                    header = next(reader, None)
                    if header is None:
                        self.datasets.append(dataset_report)
                        continue

                    normalized_headers = [_words(name) for name in header]
                    measurement_columns = [
                        index for index, name in enumerate(normalized_headers)
                        if name not in METADATA_FIELDS
                    ]
                    infos = {index: parameter_info(header[index]) for index in measurement_columns}
                    dataset_report["measurement_columns"] = len(measurement_columns)
                    dataset_report["parameters"] = sorted({infos[i]["parameter"] for i in measurement_columns})
                    seen_rows: set[tuple[str, ...]] = set()
                    seen_sample_signatures: set[tuple[str, ...]] = set()
                    district_index = normalized_headers.index("district") if "district" in normalized_headers else -1

                    for row_number, row in enumerate(reader, start=2):
                        dataset_report["source_rows"] += 1
                        district = row[district_index].strip() if district_index >= 0 and district_index < len(row) else ""
                        if _district_key(district) not in self.districts:
                            dataset_report["excluded_out_of_scope_rows"] += 1
                            continue

                        dataset_report["included_rows"] += 1
                        row_signature = tuple(row)
                        if row_signature in seen_rows:
                            dataset_report["exact_duplicate_rows"] += 1
                        else:
                            seen_rows.add(row_signature)

                        def raw_field(name: str) -> str:
                            try:
                                index = normalized_headers.index(_words(name))
                            except ValueError:
                                return ""
                            return row[index].strip() if index < len(row) else ""

                        signature = tuple(raw_field(name).casefold() for name in (
                            "Station", "District", "Data Acquisition Time", "Latitude", "Longitude"
                        ))
                        if all(signature) and signature in seen_sample_signatures:
                            dataset_report["duplicate_station_date_rows"] += 1
                        elif all(signature):
                            seen_sample_signatures.add(signature)

                        def field(name: str) -> str:
                            try:
                                index = normalized_headers.index(_words(name))
                            except ValueError:
                                return ""
                            return row[index].strip() if index < len(row) else ""

                        latitude_raw, longitude_raw = field("Latitude"), field("Longitude")
                        latitude, longitude = _number(latitude_raw), _number(longitude_raw)
                        coordinates_valid = (
                            latitude is not None and longitude is not None
                            and -90 <= latitude <= 90 and -180 <= longitude <= 180
                        )
                        if not latitude_raw or not longitude_raw:
                            dataset_report["missing_coordinates"] += 1
                        elif not coordinates_valid:
                            dataset_report["invalid_coordinates"] += 1
                        sample_date, invalid_date = _parse_date(field("Data Acquisition Time"))
                        if not field("Data Acquisition Time"):
                            dataset_report["missing_dates"] += 1
                        if invalid_date:
                            dataset_report["invalid_dates"] += 1

                        station = field("Station")
                        agency = field("Agency")
                        local_parts = [field(name) for name in ("Village", "Block", "Tehsil", "River")]
                        local_parts = [part for part in local_parts if part and part != "-"]
                        sample_id = f"{path.name}#row-{row_number}"
                        sample: dict[str, Any] = {
                            "sample_id": sample_id,
                            "source_row_number": row_number,
                            "station_id": _station_id(source, agency, station, district, latitude, longitude),
                            "station": station,
                            "agency": agency,
                            "location": ", ".join(dict.fromkeys(local_parts)),
                            "district": district,
                            "tehsil": field("Tehsil"),
                            "block": field("Block"),
                            "village": field("Village"),
                            "river": field("River"),
                            "latitude": latitude if coordinates_valid else None,
                            "longitude": longitude if coordinates_valid else None,
                            "coordinates_valid": coordinates_valid,
                            "sample_date": sample_date,
                            "sample_date_raw": field("Data Acquisition Time"),
                            "water_source": source,
                            "category": category,
                            "dataset_source": path.name,
                            "measurements": [],
                        }

                        for index in measurement_columns:
                            raw_value = row[index].strip() if index < len(row) else ""
                            info = infos[index]
                            is_missing = raw_value.casefold() in MISSING_MARKERS
                            is_qualitative = info["parameter_id"] in QUALITATIVE_PARAMETERS
                            value = None if is_missing or is_qualitative else _number(raw_value)
                            invalid_numeric = not is_missing and not is_qualitative and value is None
                            if is_missing:
                                dataset_report["missing_measurements"] += 1
                            if invalid_numeric:
                                dataset_report["invalid_numeric_values"] += 1
                            sample["measurements"].append({
                                **info,
                                "parameter_key": f"{info['parameter_id']}|{info['unit'].casefold()}",
                                "raw_parameter": header[index],
                                "value": value,
                                "value_text": None if is_missing or value is not None else raw_value,
                                "is_missing": is_missing,
                                "invalid_numeric": invalid_numeric,
                                "sample_id": sample_id,
                                "station_id": sample["station_id"],
                                "station": station,
                                "location": sample["location"],
                                "district": district,
                                "tehsil": sample["tehsil"],
                                "block": sample["block"],
                                "village": sample["village"],
                                "river": sample["river"],
                                "latitude": sample["latitude"],
                                "longitude": sample["longitude"],
                                "sample_date": sample_date,
                                "water_source": source,
                                "category": category,
                                "agency": agency,
                                "dataset_source": path.name,
                            })
                        self.samples.append(sample)
            except (OSError, csv.Error, UnicodeError) as exc:
                dataset_report["error"] = str(exc)
            self.datasets.append(dataset_report)

        self.observations = [measurement for sample in self.samples for measurement in sample["measurements"]]
        self._metadata = self._build_metadata()

    def _build_metadata(self) -> dict[str, Any]:
        parameters: dict[tuple[str, str], dict[str, Any]] = {}
        station_keys: dict[str, dict[str, Any]] = {}
        for sample in self.samples:
            station = station_keys.setdefault(sample["station_id"], {
                "station_id": sample["station_id"],
                "station": sample["station"],
                "district": sample["district"],
                "location": sample["location"],
                "latitude": sample["latitude"],
                "longitude": sample["longitude"],
                "water_source": sample["water_source"],
                "agency": sample["agency"],
                "sample_count": 0,
                "latest_sample_date": None,
            })
            station["sample_count"] += 1
            if sample["sample_date"] and (not station["latest_sample_date"] or sample["sample_date"] > station["latest_sample_date"]):
                station["latest_sample_date"] = sample["sample_date"]
            for observation in sample["measurements"]:
                key = (observation["parameter_id"], observation["unit"])
                item = parameters.setdefault(key, {
                    "parameter_id": observation["parameter_id"],
                    "parameter_key": f"{observation['parameter_id']}|{observation['unit'].casefold()}",
                    "parameter": observation["parameter"],
                    "unit": observation["unit"],
                    "categories": set(),
                    "water_sources": set(),
                    "dataset_sources": set(),
                    "record_count": 0,
                    "measured_count": 0,
                })
                item["categories"].add(observation["category"])
                item["water_sources"].add(observation["water_source"])
                item["dataset_sources"].add(observation["dataset_source"])
                item["record_count"] += 1
                if not observation["is_missing"]:
                    item["measured_count"] += 1

        finalized_parameters = []
        for item in parameters.values():
            finalized_parameters.append({
                **item,
                "categories": sorted(item["categories"]),
                "water_sources": sorted(item["water_sources"]),
                "dataset_sources": sorted(item["dataset_sources"]),
            })
        return {
            "parameters": sorted(finalized_parameters, key=lambda x: (x["parameter"].casefold(), x["unit"])),
            "stations": sorted(station_keys.values(), key=lambda x: (x["district"].casefold(), x["station"].casefold(), x["water_source"])),
            "districts": sorted({sample["district"] for sample in self.samples if sample["district"]}),
            "water_sources": ["groundwater", "surface_water"],
            "categories": ["chemical", "physical", "biological", "other"],
        }

    def filters(self, query: dict[str, str], items: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        result = self.observations if items is None else items
        source = query.get("water_source", "").casefold()
        category = query.get("category", "").casefold()
        parameter = query.get("parameter", "").casefold()
        parameter_key = query.get("parameter_key", "").casefold()
        unit = query.get("unit", "").casefold()
        station_id = query.get("station_id", "").casefold()
        station = query.get("station", "").casefold()
        location = query.get("location", "").casefold()
        district = query.get("district", "").casefold()
        start_date = query.get("start_date", "")
        end_date = query.get("end_date", "")
        include_missing = query.get("include_missing", "true").casefold() not in {"0", "false", "no"}
        filtered = []
        for item in result:
            if source and item["water_source"] != source:
                continue
            if category and item["category"] != category:
                continue
            if parameter and parameter not in {item["parameter_id"].casefold(), item["parameter"].casefold()}:
                continue
            if parameter_key and item["parameter_key"].casefold() != parameter_key:
                continue
            if unit and item["unit"].casefold() != unit:
                continue
            if station_id and item["station_id"].casefold() != station_id:
                continue
            if station and station not in item["station"].casefold():
                continue
            if district and district not in item["district"].casefold():
                continue
            if location and location not in " ".join((item["location"], item["district"], item.get("tehsil", ""), item.get("block", ""), item.get("village", ""), item.get("river", ""))).casefold():
                continue
            if (start_date or end_date) and item["sample_date"] is None:
                continue
            sample_day = (item["sample_date"] or "")[:10]
            if start_date and sample_day < start_date:
                continue
            if end_date and sample_day > end_date:
                continue
            if not include_missing and item["is_missing"]:
                continue
            filtered.append(item)
        return filtered

    @staticmethod
    def _statistics_for(items: list[dict[str, Any]]) -> dict[str, Any]:
        values = [item["value"] for item in items if item["value"] is not None]
        if not values:
            return {
                "count": 0, "mean": None, "median": None, "min": None, "max": None,
                "stddev": None, "p25": None, "p75": None,
                "missing_count": sum(1 for item in items if item["is_missing"]),
                "missing_percent": 100.0 if items else None,
            }
        ordered = sorted(values)
        def percentile(p: float) -> float:
            if len(ordered) == 1:
                return ordered[0]
            position = (len(ordered) - 1) * p
            lower = math.floor(position)
            upper = math.ceil(position)
            if lower == upper:
                return ordered[lower]
            return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)
        missing_count = sum(1 for item in items if item["is_missing"])
        return {
            "count": len(values),
            "mean": mean(values),
            "median": median(values),
            "min": min(values),
            "max": max(values),
            "stddev": pstdev(values) if len(values) > 1 else 0.0,
            "p25": percentile(0.25),
            "p75": percentile(0.75),
            "missing_count": missing_count,
            "missing_percent": missing_count / len(items) * 100 if items else None,
        }

    def statistics(self, query: dict[str, str]) -> dict[str, Any]:
        items = self.filters(query)
        groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
        for item in items:
            if item["value"] is None and not item["is_missing"]:
                continue
            groups[(item["parameter_id"], item["parameter"], item["unit"], item["water_source"])].append(item)
        rows = []
        for (parameter_id, parameter, unit, source), members in sorted(groups.items()):
            rows.append({
                "parameter_id": parameter_id,
                "parameter_key": f"{parameter_id}|{unit.casefold()}",
                "parameter": parameter,
                "unit": unit,
                "water_source": source,
                "categories": sorted({item["category"] for item in members}),
                **self._statistics_for(members),
            })
        return {"count": len(rows), "statistics": rows, "filtered_observation_count": len(items)}

    def data_quality(self) -> dict[str, Any]:
        totals = Counter()
        all_params: dict[tuple[str, str], dict[str, Any]] = {}
        for dataset in self.datasets:
            for key in ("source_rows", "included_rows", "excluded_out_of_scope_rows", "exact_duplicate_rows", "duplicate_station_date_rows", "missing_measurements", "invalid_dates", "missing_dates", "missing_coordinates", "invalid_coordinates", "invalid_numeric_values"):
                totals[key] += dataset[key]
        for observation in self.observations:
            key = observation["parameter_id"]
            unit_key = (key, observation["unit"])
            item = all_params.setdefault(unit_key, {
                "parameter_id": key, "parameter_key": observation["parameter_key"], "parameter": observation["parameter"], "unit": observation["unit"],
                "record_count": 0, "missing_count": 0, "invalid_numeric_count": 0,
                "numeric_count": 0, "recorded_count": 0, "water_sources": set(), "categories": set(),
            })
            item["record_count"] += 1
            item["missing_count"] += int(observation["is_missing"])
            item["recorded_count"] += int(not observation["is_missing"])
            item["invalid_numeric_count"] += int(observation["invalid_numeric"])
            item["numeric_count"] += int(observation["value"] is not None)
            item["water_sources"].add(observation["water_source"])
            item["categories"].add(observation["category"])
        parameters = []
        for item in all_params.values():
            parameters.append({
                **item,
                "missing_percent": item["missing_count"] / item["record_count"] * 100 if item["record_count"] else None,
                "water_sources": sorted(item["water_sources"]),
                "categories": sorted(item["categories"]),
            })
        source_rows = totals["source_rows"]
        included = totals["included_rows"]
        return {
            "scope": {"districts": sorted(self.districts), "source_directory": str(self.data_dir)},
            "total_source_records": source_rows,
            "records_processed": included,
            "records_successfully_processed": included,
            "records_excluded_by_district_scope": totals["excluded_out_of_scope_rows"],
            "measurement_observations": len(self.observations),
            "duplicate_rows_within_dataset": totals["exact_duplicate_rows"],
            "repeated_station_date_signatures_within_dataset": totals["duplicate_station_date_rows"],
            "missing_measurement_cells": totals["missing_measurements"],
            "missing_coordinates": totals["missing_coordinates"],
            "invalid_coordinates": totals["invalid_coordinates"],
            "missing_dates": totals["missing_dates"],
            "invalid_dates": totals["invalid_dates"],
            "invalid_numeric_values": totals["invalid_numeric_values"],
            "available_parameters": sorted(parameters, key=lambda x: x["parameter"].casefold()),
            "dataset_reports": self.datasets,
            "notes": [
                "Each source CSV row remains a distinct sample; records from different dates or files are not merged.",
                "Repeated site/date signatures across parameter files are preserved and are not counted as duplicate rows.",
                "Only source rows in Bangalore Urban or Bangalore Rural are included in analysis; excluded rows are counted above.",
                "Missing values remain missing and are never treated as zero.",
            ],
        }
