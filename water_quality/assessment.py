"""Configurable parameter-level standards assessment."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


STANDARDS_PATH = Path(__file__).resolve().parents[1] / "standards.json"


def _unit_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold().replace("µ", "u").replace("μ", "u"))


def load_profiles(path: Path = STANDARDS_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as standards_file:
        payload = json.load(standards_file)
    return {"profiles": payload["profiles"], "overall_assessment_note": payload["overall_assessment_note"]}


def _outside_range(value: float, minimum: float | None, maximum: float | None) -> str | None:
    if minimum is not None and value < minimum:
        return "below"
    if maximum is not None and value > maximum:
        return "above"
    return None


def assess_value(observation: dict[str, Any], criterion: dict[str, Any]) -> dict[str, Any]:
    """Compare one numeric observation with its configured criterion."""
    result = {
        "parameter": observation["parameter"],
        "parameter_id": observation["parameter_id"],
        "unit": observation["unit"],
        "value": observation["value"],
        "status": "not assessed",
        "reason": None,
    }
    if observation["parameter_id"] != criterion["parameter_id"]:
        result["reason"] = "Parameter does not match this criterion."
        return result
    if _unit_key(observation["unit"]) != _unit_key(criterion["unit"]):
        result["reason"] = f"Unit mismatch: expected {criterion['unit'] or 'unitless'}, observed {observation['unit'] or 'unitless'}."
        return result
    if observation["is_missing"]:
        result["status"] = "insufficient data"
        result["reason"] = "This parameter is missing for the sample."
        return result
    if criterion.get("method_confirmed") is False:
        result["reason"] = criterion.get("method_note", "Measurement method is not documented in the dataset.")
        return result
    if observation["value"] is None:
        result["reason"] = "The value is qualitative or not a valid number for this criterion."
        return result

    value = observation["value"]
    acceptable_min = criterion.get("acceptable_min")
    acceptable_max = criterion.get("acceptable_max")
    permiss_min = criterion.get("permissible_min", acceptable_min)
    permiss_max = criterion.get("permissible_max", acceptable_max)
    acceptable_side = _outside_range(value, acceptable_min, acceptable_max)
    if acceptable_side is None:
        result["status"] = "within acceptable limits"
        return result
    permissible_side = _outside_range(value, permiss_min, permiss_max)
    if permissible_side is None:
        result["status"] = f"{acceptable_side} acceptable limits"
        return result
    result["status"] = f"{permissible_side} permissible limits"
    return result


def assess_observation(observation: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any] | None:
    criterion = next(
        (rule for rule in profile["criteria"] if rule["parameter_id"] == observation["parameter_id"]),
        None,
    )
    if criterion is None:
        return None
    result = assess_value(observation, criterion)
    result.update({
        "sample_id": observation["sample_id"],
        "station_id": observation["station_id"],
        "station": observation["station"],
        "district": observation["district"],
        "sample_date": observation["sample_date"],
        "water_source": observation["water_source"],
        "category": observation["category"],
        "dataset_source": observation["dataset_source"],
        "standard_reference": profile["standard_reference"],
        "profile_id": profile["id"],
        "acceptable_min": criterion.get("acceptable_min"),
        "acceptable_max": criterion.get("acceptable_max"),
        "permissible_min": criterion.get("permissible_min", criterion.get("acceptable_min")),
        "permissible_max": criterion.get("permissible_max", criterion.get("acceptable_max")),
    })
    return result
