import json
from pathlib import Path
from typing import Dict, List


def _load_travel_knowledge() -> List[Dict]:
    knowledge_path = Path(__file__).resolve().parent / "travel_knowledge.json"
    if not knowledge_path.exists():
        return []
    try:
        payload = json.loads(knowledge_path.read_text(encoding="utf-8"))
        return payload.get("items", []) if isinstance(payload, dict) else []
    except Exception:
        return []


def retrieve_knowledge_cards(city: str, route_data: List[Dict], max_cards: int = 10) -> List[Dict]:
    items = _load_travel_knowledge()
    if not items:
        return []
    city_norm = (city or "").replace("市", "").strip().lower()
    matched: List[Dict] = []
    seen = set()
    for route in route_data:
        spot_name = str(route.get("name", "")).strip()
        if not spot_name:
            continue
        spot_lower = spot_name.lower()
        for item in items:
            item_city = str(item.get("city", "")).replace("市", "").strip().lower()
            if item_city != city_norm:
                continue
            keywords = item.get("spot_keywords", []) or []
            hit = any((kw and (kw.lower() in spot_lower or spot_lower in kw.lower())) for kw in keywords)
            if not hit:
                continue
            key = f"{item_city}|{','.join(keywords)}"
            if key in seen:
                continue
            seen.add(key)
            matched.append(
                {
                    "spot_name": spot_name,
                    "best_time": item.get("best_time", ""),
                    "booking_tip": item.get("booking_tip", ""),
                    "transport_tip": item.get("transport_tip", ""),
                    "pitfalls": item.get("pitfalls", []),
                    "crowd_level": item.get("crowd_level", ""),
                    "duration_suggestion": item.get("duration_suggestion", ""),
                }
            )
            if len(matched) >= max_cards:
                return matched
    return matched
