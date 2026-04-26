import json
import re
from typing import NotRequired, TypedDict


class CanonicalPart(TypedDict):
    part_number: str
    name: str
    description: NotRequired[str | None]
    category: str
    source: str  # 'OE' | 'aftermarket'
    brand: NotRequired[str | None]
    price_usd: NotRequired[float | None]
    fit_notes: dict
    attributes: dict
    vendor_urls: list[dict]
    embedding: NotRequired[list[float] | None]


_CATEGORY_MAP = {
    "oil filter": "oil_filter",
    "fuel filter": "fuel_filter",
    "air filter": "air_filter",
    "serpentine belt": "drive_belt",
    "drive belt": "drive_belt",
    "belt": "drive_belt",
    "radiator": "radiator",
    "slack adjuster": "slack_adjuster",
    "brake shoe": "brake",
    "brake pad": "brake",
    "brake": "brake",
    "wheel seal": "wheel_seal",
    "thermostat": "thermostat",
    "water pump": "water_pump",
}


def normalize_oe(raw: dict) -> CanonicalPart:
    return CanonicalPart(
        part_number=str(raw.get("part_number", "")).strip(),
        name=str(raw.get("name", "")).strip(),
        description=raw.get("description") or None,
        category=_normalize_category(raw.get("category", "general")),
        source="OE",
        brand=raw.get("brand") or None,
        price_usd=_parse_price(raw.get("price_usd")),
        fit_notes=raw.get("fit_notes") or {},
        attributes=raw.get("attributes") or {},
        vendor_urls=raw.get("vendor_urls") or [],
        embedding=None,
    )


def normalize_aftermarket(row: dict) -> CanonicalPart:
    return CanonicalPart(
        part_number=str(row.get("part_number", "")).strip(),
        name=str(row.get("name", "")).strip(),
        description=row.get("description") or None,
        category=_normalize_category(row.get("category", "general")),
        source="aftermarket",
        brand=row.get("brand") or None,
        price_usd=_parse_price(row.get("price_usd")),
        fit_notes=_parse_json_field(row.get("fit_notes")),
        attributes=_parse_json_field(row.get("attributes")),
        vendor_urls=_parse_json_list(row.get("vendor_urls")),
        embedding=None,
    )


def _normalize_category(raw_category: str) -> str:
    lower = raw_category.lower().strip()
    for key, val in _CATEGORY_MAP.items():
        if key in lower:
            return val
    return re.sub(r"\s+", "_", lower)


def _parse_price(val: object) -> float | None:
    if val is None:
        return None
    try:
        cleaned = str(val).replace("$", "").replace(",", "").strip()
        return float(cleaned) if cleaned else None
    except (ValueError, TypeError):
        return None


def _parse_json_field(val: object) -> dict:
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, ValueError):
            return {}
    return {}


def _parse_json_list(val: object) -> list[dict]:
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, ValueError):
            return []
    return []
