import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any


DATA_PATH = Path(__file__).resolve().parent / "data" / "campus_locations.json"


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).lower().replace("臺", "台")
    text = re.sub(r"\s+", "", text)
    return re.sub(r"[、，,。.!！?？:：;；_\-／/（）()「」『』]", "", text)


@lru_cache(maxsize=1)
def load_campus_locations() -> tuple[dict[str, Any], ...]:
    with DATA_PATH.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    return tuple(payload["locations"])


@lru_cache(maxsize=1)
def _alias_index() -> tuple[tuple[str, str], ...]:
    aliases: dict[str, str] = {}
    for record in load_campus_locations():
        canonical = str(record["canonical"])
        for name in (canonical, *record.get("aliases", [])):
            normalized = _normalize(str(name))
            if normalized:
                aliases.setdefault(normalized, canonical)
    return tuple(sorted(aliases.items(), key=lambda item: (-len(item[0]), item[0])))


def resolve_campus_location(value: str) -> dict[str, Any] | None:
    """Resolve an exact canonical name or alias without inferring any service."""
    normalized = _normalize(value)
    canonical = next(
        (name for alias, name in _alias_index() if alias == normalized),
        None,
    )
    if canonical is None:
        return None
    return next(
        record for record in load_campus_locations() if record["canonical"] == canonical
    )


def match_campus_location_mention(message: str) -> str | None:
    """Return the canonical campus location mentioned in free-form text."""
    normalized = _normalize(message)
    matches: list[tuple[int, int, str]] = []
    for alias, canonical in _alias_index():
        position = normalized.find(alias)
        if position >= 0:
            matches.append((position, -len(alias), canonical))
    return min(matches)[2] if matches else None


def location_names_for(value: str) -> tuple[str, ...]:
    """Return canonical and aliases for downstream data lookup only."""
    record = resolve_campus_location(value)
    if record is None:
        return (value,)
    return tuple(dict.fromkeys((str(record["canonical"]), *record.get("aliases", []))))
