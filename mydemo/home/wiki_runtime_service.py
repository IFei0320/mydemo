from typing import Dict, List

from home.wiki_extract import (
    extract_month_signals,
    extract_pitfalls,
    has_llm_error,
    infer_best_time,
    infer_budget_level,
    infer_crowd_level,
    infer_transport_mode,
    season_to_months,
)
from home.wiki_store import CONCEPT_DIR, ENTITY_DIR, SUMMARY_DIR, ensure_default_concepts, ensure_dirs


def retrieve_wiki_knowledge_cards(
    city: str,
    route_data: List[Dict],
    max_cards: int = 8,
    season: str = "",
    budget: float = 0.0,
) -> List[Dict]:
    ensure_dirs()
    city_norm = (city or "").replace("市", "").strip().lower()
    if not city_norm or not route_data:
        return []

    pages = list(SUMMARY_DIR.glob("*.md"))
    if not pages:
        return []

    route_names = [str(item.get("name", "")).strip() for item in route_data if str(item.get("name", "")).strip()]
    if not route_names:
        return []

    raw_cards: List[Dict] = []
    seen = set()
    for page in pages:
        text = page.read_text(encoding="utf-8", errors="ignore")
        text_norm = text.replace("市", "").lower()
        if city_norm not in text_norm and city_norm not in page.stem.replace("市", "").lower():
            continue

        for spot in route_names:
            spot_norm = spot.lower()
            if spot_norm and spot_norm in text.lower():
                key = f"{page.name}|{spot_norm}"
                if key in seen:
                    continue
                seen.add(key)
                months = extract_month_signals(text)
                card = {
                    "spot_name": spot,
                    "city": city,
                    "best_months": months,
                    "best_time": infer_best_time(text),
                    "booking_required": ("预约" in text or "购票" in text),
                    "booking_tip": "建议提前在线预约，节假日至少提前1-3天。",
                    "transport_mode": infer_transport_mode(text),
                    "transport_tip": "建议地铁优先，跨区段打车补充。",
                    "budget_level": infer_budget_level(text),
                    "crowd_level": infer_crowd_level(text),
                    "duration_suggestion": "1-3小时",
                    "pitfalls": extract_pitfalls(text),
                    "source": f"wiki/summary/{page.name}",
                }
                rank_score = 0.0
                season_months = season_to_months(season)
                if season_months and any(m in card["best_months"] for m in season_months):
                    rank_score += 2.0
                elif card["best_months"]:
                    rank_score += 0.8
                else:
                    rank_score += 0.5

                if budget > 0:
                    if budget < 1200 and card["budget_level"] == "low":
                        rank_score += 1.5
                    elif 1200 <= budget <= 3000 and card["budget_level"] == "medium":
                        rank_score += 1.0
                    elif budget > 3000 and card["budget_level"] == "high":
                        rank_score += 1.0
                else:
                    rank_score += 0.5

                if card["crowd_level"] == "low":
                    rank_score += 1.0
                elif card["crowd_level"] == "medium":
                    rank_score += 0.6
                else:
                    rank_score += 0.2

                card["rank_score"] = round(rank_score, 3)
                raw_cards.append(card)
                if len(raw_cards) >= max_cards * 3:
                    break
            if len(raw_cards) >= max_cards * 3:
                break

    if not raw_cards:
        return []

    ranked = sorted(raw_cards, key=lambda x: x.get("rank_score", 0.0), reverse=True)
    cards: List[Dict] = []
    used_spot = set()
    for card in ranked:
        spot_key = card.get("spot_name", "").strip().lower()
        if spot_key in used_spot:
            continue
        used_spot.add(spot_key)
        cards.append(card)
        if len(cards) >= max_cards:
            break

    return cards


def backfill_concept_sources() -> Dict:
    ensure_dirs()
    ensure_default_concepts()
    linked = 0
    for concept_path in CONCEPT_DIR.glob("*.md"):
        concept = concept_path.stem
        content = concept_path.read_text(encoding="utf-8", errors="ignore")
        for summary_path in SUMMARY_DIR.glob("*.md"):
            summary_text = summary_path.read_text(encoding="utf-8", errors="ignore")
            if has_llm_error(summary_text):
                continue
            if concept in summary_text and f"[[wiki/summary/{summary_path.name}]]" not in content:
                concept_path.write_text(content.rstrip() + f"\n- [[wiki/summary/{summary_path.name}]]\n", encoding="utf-8")
                content = concept_path.read_text(encoding="utf-8", errors="ignore")
                linked += 1
    return {"ok": True, "linked": linked}


def list_entity_pages() -> List[str]:
    ensure_dirs()
    return sorted([p.name for p in ENTITY_DIR.glob("*.md")])
