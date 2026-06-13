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
    """为路线中的每个景点检索 Wiki 知识卡片（结构化景点信息）。

    数据流：
        SUMMARY_DIR/*.md  →  关键词匹配路线景点名  →  提取结构化字段
        →  按季节/预算/人流量打分  →  排序去重  →  返回 topN

    打分逻辑（rank_score）：
        - 季节匹配当前查询季节           +2.0
        - 有最佳月份但未匹配当前季节        +0.8
        - 无最佳月份                     +0.5
        - 预算匹配景点消费等级            +1.0~1.5
        - 人流量低/中/高                +1.0/+0.6/+0.2

    参数：
        city: 目标城市名（自动去掉"市"后缀）
        route_data: 路线数据，每项需含 "name" 字段
        max_cards: 返回的最大卡片数，默认 8
        season: 查询季节，用于排序加权
        budget: 用户预算，用于排序加权

    返回：
        按 rank_score 降序排列的卡片列表，每个景点最多一张卡片。
    """
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
    """补全概念页面的来源追溯链接。

    遍历所有概念页（CONCEPT_DIR），检查每个概念的摘要页（SUMMARY_DIR）
    是否已被引用。如果某摘要页包含该概念的文本但概念页尚未引用它，
    则在概念页追加 `- [[wiki/summary/xxx.md]]` 链接。

    用途：
        确保概念页的交叉引用完整性，用于 lint_wiki() 健康检查。

    返回：
        {"ok": True, "linked": N}  —  N 为本次新增的引用数。
    """
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
    """列出实体目录下的所有页面文件名。

    返回：
        str 列表，如 ["外滩.md", "南京路步行街.md", ...]。
    """
    ensure_dirs()
    return sorted([p.name for p in ENTITY_DIR.glob("*.md")])
