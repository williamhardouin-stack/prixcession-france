from __future__ import annotations

import json
import math
import re
import unicodedata
from calendar import monthrange
from datetime import date
from statistics import mean, median
from typing import Any, Iterable


PRICE_WITH_CONTEXT_RE = re.compile(
    r"(?is)(?:prix(?:\s+(?:de\s+vente|de\s+cession|stipul[ée]|principal))?"
    r"|cession\s+(?:pour|au\s+prix\s+de))"
    r"[^0-9]{0,55}"
    r"([0-9]{1,3}(?:[\s.\u00a0\u202f,'][0-9]{3})+(?:[.,][0-9]{2})?"
    r"|[0-9]{4,}(?:[.,][0-9]{2})?)"
    r"\s*(?:€|eur(?:os?)?)"
)


def parse_jsonish(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped or stripped[0] not in "[{":
        return value
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return value


def flatten_strings(value: Any) -> list[str]:
    value = parse_jsonish(value)
    if value is None:
        return []
    if isinstance(value, dict):
        result: list[str] = []
        for key, child in value.items():
            result.append(str(key))
            result.extend(flatten_strings(child))
        return result
    if isinstance(value, (list, tuple, set)):
        result = []
        for child in value:
            result.extend(flatten_strings(child))
        return result
    return [str(value)]


def normalize_for_match(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", without_accents.casefold()).strip()


def parse_euro_number(raw: str) -> float | None:
    cleaned = raw.replace("\u00a0", "").replace("\u202f", "").replace(" ", "").replace("'", "")
    if not cleaned:
        return None

    if "," in cleaned:
        # French formatting: dots are thousands separators and comma is decimal.
        integer_part, decimal_part = cleaned.rsplit(",", 1)
        integer_part = integer_part.replace(".", "").replace(",", "")
        normalized = integer_part + (f".{decimal_part}" if decimal_part else "")
    elif cleaned.count(".") > 1:
        parts = cleaned.split(".")
        if len(parts[-1]) == 2:
            normalized = "".join(parts[:-1]) + "." + parts[-1]
        else:
            normalized = "".join(parts)
    elif "." in cleaned:
        left, right = cleaned.split(".", 1)
        normalized = left + right if len(right) == 3 else left + "." + right
    else:
        normalized = cleaned

    try:
        return float(normalized)
    except ValueError:
        return None


def extract_price_eur(value: Any) -> float | None:
    text = " ".join(flatten_strings(value))
    for match in PRICE_WITH_CONTEXT_RE.finditer(text):
        parsed = parse_euro_number(match.group(1))
        if parsed is not None:
            return round(parsed, 2)
    return None


def record_blob(record: dict[str, Any]) -> str:
    useful_fields = (
        "acte",
        "listeetablissements",
        "listepersonnes",
        "listeprecedentexploitant",
        "listeprecedentproprietaire",
        "commercant",
        "ville",
        "departement_nom_officiel",
    )
    return " ".join(part for field in useful_fields for part in flatten_strings(record.get(field)))


def matches_keywords(record: dict[str, Any], keywords: Iterable[str]) -> bool:
    normalized_blob = normalize_for_match(record_blob(record))
    normalized_keywords = [normalize_for_match(keyword) for keyword in keywords if keyword.strip()]
    return any(keyword in normalized_blob for keyword in normalized_keywords)


def excerpt(text: str, keywords: Iterable[str], max_length: int = 360) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_length:
        return compact

    normalized = normalize_for_match(compact)
    positions = [normalized.find(normalize_for_match(keyword)) for keyword in keywords]
    positions = [position for position in positions if position >= 0]
    center = min(positions) if positions else 0
    start = max(0, center - max_length // 3)
    end = min(len(compact), start + max_length)
    prefix = "…" if start else ""
    suffix = "…" if end < len(compact) else ""
    return prefix + compact[start:end] + suffix


def comparable_from_record(
    record: dict[str, Any],
    keywords: list[str],
    min_price: float,
    max_price: float,
) -> dict[str, Any] | None:
    if not matches_keywords(record, keywords):
        return None

    price = extract_price_eur(record.get("acte")) or extract_price_eur(record)
    if price is None or price < min_price or price > max_price:
        return None

    blob = record_blob(record)
    return {
        "record_type": "comparable",
        "transaction_price_eur": price,
        "publication_date": record.get("dateparution"),
        "company": record.get("commercant"),
        "city": record.get("ville"),
        "postal_code": record.get("cp"),
        "department_code": record.get("numerodepartement"),
        "department": record.get("departement_nom_officiel"),
        "activity_excerpt": excerpt(blob, keywords),
        "official_url": record.get("url_complete"),
        "bodacc_id": record.get("id"),
    }


def percentile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def confidence_label(count: int) -> str:
    if count >= 25:
        return "élevée"
    if count >= 10:
        return "moyenne"
    if count >= 5:
        return "faible"
    return "échantillon insuffisant"


def build_summary(
    comparables: list[dict[str, Any]],
    *,
    keywords: list[str],
    departments: list[str],
    date_from: str,
    date_to: str,
    scanned_count: int,
) -> dict[str, Any]:
    prices = [float(item["transaction_price_eur"]) for item in comparables]
    count = len(prices)
    return {
        "record_type": "summary",
        "query": {
            "activity_keywords": keywords,
            "departments": departments or ["France entière"],
            "date_from": date_from,
            "date_to": date_to,
        },
        "notices_scanned": scanned_count,
        "comparables_found": count,
        "median_price_eur": round(median(prices), 2) if prices else None,
        "average_price_eur": round(mean(prices), 2) if prices else None,
        "q1_price_eur": round(percentile(prices, 0.25), 2) if prices else None,
        "q3_price_eur": round(percentile(prices, 0.75), 2) if prices else None,
        "minimum_price_eur": round(min(prices), 2) if prices else None,
        "maximum_price_eur": round(max(prices), 2) if prices else None,
        "confidence": confidence_label(count),
        "source": "BODACC open data — DILA — Licence Ouverte 2.0",
        "method": "Prix extraits automatiquement des avis de ventes et cessions correspondant aux filtres.",
        "warning": (
            "Repère indicatif fondé sur des transactions déjà publiées, et non estimation financière, "
            "conseil juridique ou liste d'entreprises actuellement à vendre. Vérifiez chaque avis officiel."
        ),
    }


def subtract_months(day: date, months: int) -> date:
    month_index = day.year * 12 + day.month - 1 - months
    year, zero_based_month = divmod(month_index, 12)
    month = zero_based_month + 1
    return date(year, month, min(day.day, monthrange(year, month)[1]))


def escape_ods_literal(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def build_where_clause(
    *,
    keywords: list[str],
    departments: list[str],
    date_from: str,
    date_to: str,
) -> str:
    clauses = [
        'familleavis = "vente"',
        f'dateparution >= "{escape_ods_literal(date_from)}"',
        f'dateparution <= "{escape_ods_literal(date_to)}"',
    ]
    if keywords:
        searches = [f'search(*, "{escape_ods_literal(keyword)}")' for keyword in keywords]
        clauses.append("(" + " OR ".join(searches) + ")")
    if departments:
        department_filters = [
            f'numerodepartement = "{escape_ods_literal(department)}"' for department in departments
        ]
        clauses.append("(" + " OR ".join(department_filters) + ")")
    return " AND ".join(clauses)
