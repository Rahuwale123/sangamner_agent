from __future__ import annotations

import json
from typing import Any, Dict, Optional

import httpx
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, ValidationError, model_validator

from config.settings import get_settings


EXPECTED_KEYS = {"latitude", "longitude", "client_id", "query"}


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped[3:]
        if stripped.startswith("tool_code"):
            stripped = stripped[len("tool_code"):].lstrip()
        if stripped.startswith("json"):
            stripped = stripped[len("json"):].lstrip()
        stripped = stripped.rstrip()
        if stripped.endswith("```"):
            stripped = stripped[:-3]
    return stripped.strip()


def _extract_json_segment(text: str) -> Optional[str]:
    start = text.find("{")
    if start == -1:
        return None
    stack = 0
    for idx in range(start, len(text)):
        ch = text[idx]
        if ch == "{":
            stack += 1
        elif ch == "}":
            stack -= 1
            if stack == 0:
                return text[start: idx + 1]
    return None


class NearbySearchInput(BaseModel):
    latitude: float = Field(..., description="User latitude")
    longitude: float = Field(..., description="User longitude")
    client_id: str = Field(..., description="Client/session identifier")
    query: str = Field(..., description="User query to search for")

    @model_validator(mode="before")
    @classmethod
    def _coerce_nested(cls, values):
        def decode(value):
            if isinstance(value, str):
                cleaned = _strip_code_fences(value)
                try:
                    return json.loads(cleaned)
                except json.JSONDecodeError:
                    segment = _extract_json_segment(cleaned)
                    if segment:
                        try:
                            return json.loads(segment)
                        except json.JSONDecodeError:
                            pass
                    return cleaned
            return value

        if isinstance(values, str):
            values = decode(values)

        if isinstance(values, dict):
            while True:
                updated = False

                for key in list(values.keys()):
                    item = values[key]

                    if key in EXPECTED_KEYS and isinstance(item, str):
                        decoded = decode(item)
                        if isinstance(decoded, dict):
                            values = decoded
                            updated = True
                            break
                        if decoded != item:
                            values[key] = decoded
                            updated = True

                    if key not in EXPECTED_KEYS:
                        decoded = decode(item)
                        if isinstance(decoded, dict):
                            values = decoded
                            updated = True
                            break
                        if decoded != item:
                            values[key] = decoded
                            updated = True

                if not updated:
                    break

            if "client_id" in values:
                values["client_id"] = str(values["client_id"])
            if "latitude" in values:
                try:
                    values["latitude"] = float(values["latitude"])
                except (TypeError, ValueError):
                    pass
            if "longitude" in values:
                try:
                    values["longitude"] = float(values["longitude"])
                except (TypeError, ValueError):
                    pass

        return values


def _simplify_results(raw: Dict[str, Any]) -> Dict[str, Any]:
    results = raw.get("results") or []
    simplified = []
    for item in results:
        payload = item.get("payload") or {}
        simplified.append(
            {
                "business_name": payload.get("business_name"),
                "phone": payload.get("phone"),
                "distance_km": item.get("distance_km"),
            }
        )
    return {
        "simplified": simplified,
        "total": raw.get("total"),
        "status": raw.get("status"),
    }


def _call_nearby_search(latitude: float, longitude: float, client_id: str, query: str) -> Dict[str, Any]:
    settings = get_settings()
    endpoint = settings.search_api_url
    if not endpoint:
        raise RuntimeError("SEARCH_API_URL not configured")

    payload = {
        "latitude": latitude,
        "longitude": longitude,
        "client_id": client_id,
        "query": query,
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(endpoint, json=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Nearby search API call failed: {exc}") from exc

    simplified = _simplify_results(data)
    return {
        "raw": data,
        "simplified": simplified,
    }


def _normalize_tool_kwargs(data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(data, dict) or not data:
        return data

    for key in EXPECTED_KEYS & data.keys():
        value = data.get(key)
        if isinstance(value, str):
            try:
                embedded = json.loads(_strip_code_fences(value))
            except json.JSONDecodeError:
                continue
            if isinstance(embedded, dict):
                return _normalize_tool_kwargs(embedded)

    if len(data) == 1:
        key, value = next(iter(data.items()))
        if key not in EXPECTED_KEYS:
            if isinstance(value, str):
                try:
                    nested = json.loads(_strip_code_fences(value))
                except json.JSONDecodeError:
                    return data
                if isinstance(nested, dict):
                    return _normalize_tool_kwargs(nested)
            elif isinstance(value, dict):
                return _normalize_tool_kwargs(value)
    return data


def _nearby_search_tool(*args: Any, **kwargs: Any) -> str:
    if args and not kwargs:
        first = args[0]
        if isinstance(first, str):
            cleaned = _strip_code_fences(first)
            try:
                decoded = json.loads(cleaned)
            except json.JSONDecodeError:
                segment = _extract_json_segment(cleaned)
                if segment:
                    try:
                        decoded = json.loads(segment)
                    except json.JSONDecodeError:
                        decoded = cleaned
                else:
                    decoded = cleaned
            if isinstance(decoded, dict):
                kwargs = decoded
        elif isinstance(first, dict):
            kwargs = first

    if len(kwargs) == 1 and isinstance(next(iter(kwargs.values())), str):
        try:
            raw_value = next(iter(kwargs.values()))
            cleaned = _strip_code_fences(raw_value)
            try:
                parsed = json.loads(cleaned)
            except json.JSONDecodeError:
                segment = _extract_json_segment(cleaned)
                if not segment:
                    raise
                parsed = json.loads(segment)
            if isinstance(parsed, dict):
                kwargs = parsed
        except json.JSONDecodeError:
            pass

    kwargs = _normalize_tool_kwargs(kwargs)
    try:
        parsed = NearbySearchInput(**kwargs)
    except ValidationError as exc:
        raise ValueError(f"Invalid input for NearbySearchTool: {exc}")

    result = _call_nearby_search(
        latitude=parsed.latitude,
        longitude=parsed.longitude,
        client_id=parsed.client_id,
        query=parsed.query,
    )
    return json.dumps(result)


def build_nearby_search_tool() -> StructuredTool:
    description = (
        "Use this tool to search for nearby businesses or services in Sangamner. "
        "Input must be a JSON object with keys latitude, longitude, client_id, and query."
    )
    return StructuredTool.from_function(
        func=_nearby_search_tool,
        name="NearbySearchTool",
        description=description,
        args_schema=NearbySearchInput,
    )
