import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

from campus_locations import location_names_for


UNIFORM_COVERAGE_URL = "https://net.nthu.edu.tw/netsys/wireless:uniform"
PUBLIC_COVERAGE_URL = "https://www.wlan.nthu.edu.tw/~wlan/NM/MyUserZone_new.html"
WIRELESS_APPLICATION_URL = "https://net.nthu.edu.tw/netsys/wireless:application:ccxp"
DATA_PATH = Path(__file__).resolve().parent / "data" / "wireless_coverage.json"
CAMPUS_ACCOUNT_SSIDS = {"nthupeap", "eduroam", "nthu-cc", "tanetroaming"}


@lru_cache(maxsize=1)
def load_coverage_data() -> dict[str, Any]:
    with DATA_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def _normalize_location(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).lower()
    text = text.replace("臺", "台")
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"(?:那邊|那裡|這邊|這裡)$", "", text)
    return re.sub(r"[、，,。.!！?？:：;；_\-]", "", text)


def _strip_floor_details(value: str) -> str:
    text = re.sub(
        r"(?:b?\d+(?:f|樓)?(?:[~～至,，及]+b?\d+(?:f|樓)?)*)",
        "",
        value,
        flags=re.IGNORECASE,
    )
    text = text.replace("全區", "").strip()
    return text.strip("()（）~～").strip()


def _base_variants(value: str) -> set[str]:
    normalized = _normalize_location(value)
    if not normalized:
        return set()

    variants = {normalized}
    floorless = _strip_floor_details(normalized)
    if floorless:
        variants.add(floorless)

    for inner in re.findall(r"[（(]([^）)]+)[）)]", normalized):
        variants.add(inner)
        variants.add(_strip_floor_details(inner))

    for building in re.findall(
        r"[\u4e00-\u9fffA-Za-z·]{1,16}?(?:大樓|中心|學院|館|院|樓)",
        floorless,
    ):
        variants.add(building)

    expanded = set(variants)
    for variant in variants:
        for suffix in ("大樓", "中心", "學院", "館", "院", "樓"):
            if variant.endswith(suffix) and len(variant) > len(suffix):
                expanded.add(variant[: -len(suffix)])
                break
    return {item for item in expanded if item}


def _record_variants(record: dict[str, Any]) -> set[str]:
    return _base_variants(str(record["location"])) | _base_variants(str(record["manager"]))


@lru_cache(maxsize=1)
def _location_mention_index() -> tuple[tuple[str, str], ...]:
    """Build a longest-first entity index from the official location records."""
    canonical_by_variant: dict[str, str] = {}
    for record in load_coverage_data()["records"]:
        location = str(record["location"])
        manager = str(record["manager"])
        location_name = _strip_floor_details(location) or location
        manager_name = _strip_floor_details(manager) or manager

        for variant in _base_variants(location):
            if len(variant) >= 2:
                canonical = (
                    variant
                    if re.search(r"(?:大樓|中心|學院|館|院|樓)$", variant)
                    else location_name
                )
                canonical_by_variant.setdefault(variant, canonical)
        for variant in _base_variants(manager):
            if len(variant) >= 2:
                canonical_by_variant[variant] = manager_name

    return tuple(
        sorted(
            canonical_by_variant.items(),
            key=lambda item: (-len(item[0]), item[0]),
        )
    )


def match_coverage_location_mention(message: str) -> str | None:
    """Resolve a location mention from ingested entities, ignoring surrounding speech."""
    normalized = _normalize_location(message)
    matches: list[tuple[int, int, str]] = []
    for variant, canonical in _location_mention_index():
        position = normalized.find(variant)
        if position >= 0:
            matches.append((position, -len(variant), canonical))
    if not matches:
        return None
    return min(matches)[2]


def _record_haystack(record: dict[str, Any]) -> str:
    return _normalize_location(f"{record['manager']} {record['location']} {record['scope_detail']}")


def lookup_coverage(location: str) -> dict[str, Any]:
    records = load_coverage_data()["records"]
    query_variants: set[str] = set()
    for name in location_names_for(location):
        query_variants.update(_base_variants(name))
    exact = [
        record
        for record in records
        if query_variants.intersection(_record_variants(record))
    ]
    if exact:
        best_priority = min(int(record.get("source_priority", 99)) for record in exact)
        return {
            "match_level": "exact",
            "query_location": location,
            "records": [
                record
                for record in exact
                if int(record.get("source_priority", 99)) == best_priority
            ],
        }

    normalized_query = _normalize_location(location)
    partial = [
        record
        for record in records
        if len(normalized_query) >= 2 and normalized_query in _record_haystack(record)
    ]
    return {
        "match_level": "partial" if partial else "none",
        "query_location": location,
        "records": partial,
    }


def _ordered_ssids(records: list[dict[str, Any]]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for record in records:
        for ssid in record.get("ssids", []):
            key = str(ssid).lower()
            if key not in seen:
                seen.add(key)
                result.append(str(ssid))
    return result


def _format_ssids(ssids: list[str]) -> str:
    return "、".join(f"`{ssid}`" for ssid in ssids)


def _source_payload(records: list[dict[str, Any]] | None = None) -> list[dict[str, str]]:
    data = load_coverage_data()
    selected_urls = {
        str(record["source_url"])
        for record in (records or [])
    }
    if not selected_urls:
        selected_urls = {str(item["url"]) for item in data["sources"]}

    sources: list[dict[str, str]] = []
    for item in data["sources"]:
        if item["url"] not in selected_urls:
            continue
        sources.append(
            {
                "title": item["title"],
                "source_name": item["title"],
                "url": item["url"],
                "content": "清大官方校園無線網路服務範圍與地點、SSID 對照資料。",
            }
        )
    return sources


def build_coverage_response(location: str) -> dict[str, Any]:
    result = lookup_coverage(location)
    records = result["records"]

    if result["match_level"] == "none":
        answer = (
            f"目前查不到「{location}」是否提供校園無線網路，因此無法直接確認該地點有 Wi-Fi。"
            "若地點有別名，請補充正式館舍名稱，"
            "或向無線網路服務信箱 wlan@cc.nthu.edu.tw 確認。"
        )
        return {"answer": answer, "sources": _source_payload()}

    if result["match_level"] == "partial":
        scopes = "、".join(dict.fromkeys(str(record["scope_detail"]) for record in records))
        ssids = _ordered_ssids(records)
        answer = (
            f"目前只能確認「{scopes}」提供校園無線網路 {_format_ssids(ssids)}。"
            f"這不代表「{location}」的其他區域也有 Wi-Fi。"
        )
        return {"answer": answer, "sources": _source_payload(records)}

    ssids = _ordered_ssids(records)
    scopes = list(dict.fromkeys(str(record["scope_detail"]) for record in records))
    if len(scopes) == 1:
        answer = (
            f"有。「{scopes[0]}」可使用的校園無線網路為 {_format_ssids(ssids)}。"
        )
    else:
        details = []
        for record in records:
            details.append(
                f"- {record['scope_detail']}：{_format_ssids(list(record.get('ssids', [])))}"
            )
        answer = (
            f"有。「{location}」不同區域或樓層可使用的校園無線網路名稱不完全相同：\n\n"
            + "\n".join(dict.fromkeys(details))
        )
    answer += "\n\n實際連線時仍應以所在樓層現場可搜尋到的 SSID 與訊號為準。"
    return {"answer": answer, "sources": _source_payload(records)}


def build_campus_ssid_response() -> dict[str, Any]:
    """List public-area SSIDs by aggregating the official location records."""
    records = [
        record
        for record in load_coverage_data()["records"]
        if record.get("source_url") == PUBLIC_COVERAGE_URL
    ]
    if not records:
        records = list(load_coverage_data()["records"])
    ssids = _ordered_ssids(records)
    answer = (
        f"清大公共區常見的 Wi-Fi 名稱有 {_format_ssids(ssids)}。"
        "不同館舍或樓層實際可搜尋到的名稱可能不同，請以所在位置顯示的 Wi-Fi 清單為準。"
    )
    return {"answer": answer, "sources": _source_payload(records)}


def _campus_account_ssids(records: list[dict[str, Any]]) -> set[str]:
    return {
        str(ssid).lower()
        for record in records
        for ssid in record.get("ssids", [])
        if str(ssid).lower() in CAMPUS_ACCOUNT_SSIDS
    }


def build_account_scope_comparison_response(
    current_location: str,
    referenced_location: str,
    application_answer: str,
) -> dict[str, Any]:
    current = lookup_coverage(current_location)
    referenced = lookup_coverage(referenced_location)

    if current["match_level"] == "exact" and referenced["match_level"] == "exact":
        shared = sorted(
            _campus_account_ssids(current["records"])
            & _campus_account_ssids(referenced["records"])
        )
        if shared:
            shared_text = _format_ssids(shared)
            answer = (
                f"是的。{current_location}和{referenced_location}的校園無線網路申請方式相同，"
                "只需要申請一個校園無線網路帳號，不必按地點重複申請。\n\n"
                f"兩地都提供 {shared_text}，"
                "同一組校園無線網路帳號可在有提供相應 SSID 的校園區域使用。"
                "各地點實際提供的其他 SSID 或涵蓋樓層仍可能不同。\n\n"
                f"{application_answer}"
            )
            records = [*current["records"], *referenced["records"]]
            sources = _source_payload(records)
            sources.append(
                {
                    "title": "校務資訊系統申請無線區域網路帳號",
                    "source_name": "校務資訊系統申請無線區域網路帳號",
                    "url": WIRELESS_APPLICATION_URL,
                    "content": "清大官方無線區域網路帳號申請步驟。",
                }
            )
            return {"answer": answer, "sources": sources}

    missing = [
        name
        for name, lookup in (
            (current_location, current),
            (referenced_location, referenced),
        )
        if lookup["match_level"] != "exact"
    ]
    if missing:
        direct = (
            f"目前查不到「{'、'.join(missing)}」的完整校園無線網路資訊，"
            "因此無法直接確認兩地是否完全相同。"
        )
    else:
        direct = (
            "目前查不到兩地共同提供的校園帳號型 Wi-Fi，"
            "因此無法只憑地點名稱確認申請方式相同。"
        )
    return {
        "answer": direct + "\n\n" + application_answer,
        "sources": _source_payload([*current["records"], *referenced["records"]]),
    }


def build_coverage_documents() -> list[dict[str, Any]]:
    counters: dict[str, int] = {}
    documents: list[dict[str, Any]] = []
    for record in load_coverage_data()["records"]:
        url = str(record["source_url"])
        counters[url] = counters.get(url, 0) + 1
        ssids = ", ".join(str(item) for item in record.get("ssids", []))
        location_keys = sorted(_record_variants(record))
        documents.append(
            {
                "title": "清大校園無線網路服務範圍",
                "url": url,
                "chunk_index": counters[url],
                "content": (
                    f"服務：校園無線網路\n資訊類型：服務範圍\n"
                    f"地點：{record['location']}\n管理單位：{record['manager']}\n"
                    f"涵蓋範圍：{record['scope_detail']}\nSSID：{ssids}\n"
                    f"認證方式：{record['authentication']}"
                ),
                "service": "campus_wifi",
                "intent": "coverage",
                "location": record["location"],
                "location_keys": location_keys,
                "source_type": "official_coverage",
            }
        )
    return documents
