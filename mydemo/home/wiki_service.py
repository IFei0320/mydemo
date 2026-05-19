import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from ai.wiki_llm import WikiLLM
from home.wiki_extract import (
    clean_text,
    extract_concepts,
    extract_month_signals,
    extract_pitfalls,
    extract_spot_names,
    extract_title,
    has_llm_error,
    infer_best_time,
    infer_budget_level,
    infer_crowd_level,
    infer_transport_mode,
    normalize_entity_name,
    safe_list,
    season_to_months,
    slugify,
)
from home.wiki_store import (
    BASE_DIR,
    CONCEPT_DIR,
    ENTITY_DIR,
    RAW_DIR,
    SUMMARY_DIR,
    append_log,
    append_source_links_to_concept,
    build_rule_based_summary,
    ensure_default_concepts,
    ensure_dirs,
    format_summary_markdown,
    refresh_index,
    sanitize_existing_entity_pages,
    upsert_dynamic_concept_pages,
    upsert_entity_pages,
)


def _get_wiki_llm() -> WikiLLM:
    return WikiLLM()


def _normalize_compile_result(raw_content: str, source_name: str, title: str) -> Dict:
    llm = _get_wiki_llm()
    compiled = llm.compile_raw(raw_content, source_name)

    summary = clean_text(compiled.get("summary", ""))
    if '"summary"' in summary and '"concepts"' in summary and '"cards"' in summary:
        try:
            import json
            parsed = json.loads(summary)
            summary = clean_text(parsed.get("summary", ""))
        except Exception:
            summary = ""

    concepts = safe_list(compiled.get("concepts", []))
    entities = []
    for item in compiled.get("entities", []):
        name = normalize_entity_name(str(item))
        if name and name not in entities:
            entities.append(name)

    cards = []
    for card in compiled.get("cards", []):
        if not isinstance(card, dict):
            continue
        spot_name = normalize_entity_name(str(card.get("spot_name", "")))
        if not spot_name:
            continue
        cards.append(
            {
                "spot_name": spot_name,
                "best_months": safe_list(card.get("best_months", []), limit=8),
                "best_time": clean_text(str(card.get("best_time", ""))),
                "booking_required": bool(card.get("booking_required", False)),
                "booking_tip": clean_text(str(card.get("booking_tip", ""))),
                "transport_mode": clean_text(str(card.get("transport_mode", "mixed"))) or "mixed",
                "transport_tip": clean_text(str(card.get("transport_tip", ""))),
                "budget_level": clean_text(str(card.get("budget_level", "medium"))) or "medium",
                "crowd_level": clean_text(str(card.get("crowd_level", "medium"))) or "medium",
                "crowd_tip": clean_text(str(card.get("crowd_tip", ""))),
                "duration_suggestion": clean_text(str(card.get("duration_suggestion", "1-3小时"))) or "1-3小时",
                "pitfalls": [p for p in safe_list(card.get("pitfalls", []), limit=6) if not any(token in p for token in ["## ", "### ", "|", "[^", "——"])],
                "nearby": [normalize_entity_name(name) for name in safe_list(card.get("nearby", []), limit=8) if normalize_entity_name(name)],
                "llm_note": clean_text(str(card.get("llm_note", ""))),
            }
        )

    if not summary:
        summary = build_rule_based_summary(raw_content, source_name, title)

    if not concepts:
        concepts = extract_concepts(raw_content)
    if not entities:
        entities = [normalize_entity_name(name) for name in extract_spot_names(raw_content) if normalize_entity_name(name)]

    if not cards:
        for name in entities:
            cards.append(
                {
                    "spot_name": name,
                    "best_months": extract_month_signals(raw_content),
                    "best_time": "",
                    "booking_required": False,
                    "booking_tip": "",
                    "transport_mode": "mixed",
                    "transport_tip": "",
                    "budget_level": "medium",
                    "crowd_level": "medium",
                    "crowd_tip": "",
                    "duration_suggestion": "",
                    "pitfalls": [],
                    "nearby": [],
                    "llm_note": "",
                }
            )

    return {
        "summary": summary,
        "concepts": concepts,
        "entities": entities,
        "cards": cards,
        "llm_failed": has_llm_error(str(compiled.get("raw", ""))),
    }


def ingest_raw_file(raw_path: Path) -> Dict:
    ensure_dirs()
    if not raw_path.exists():
        return {"ok": False, "message": f"文件不存在: {raw_path.name}"}

    content = raw_path.read_text(encoding="utf-8", errors="ignore")
    if not content.strip():
        return {"ok": False, "message": f"文件为空: {raw_path.name}"}

    title = extract_title(content, raw_path.stem)
    slug = slugify(raw_path.stem)
    summary_path = SUMMARY_DIR / f"{slug}.md"

    compiled = _normalize_compile_result(content, raw_path.name, title)
    summary_markdown = format_summary_markdown(compiled["summary"], raw_path.name, len(content))
    summary_path.write_text(summary_markdown, encoding="utf-8")

    concept_hits = compiled["concepts"] or extract_concepts(content)
    upsert_dynamic_concept_pages(concept_hits, raw_path.name, title)
    for concept in ["错峰出行", "预算控制"] + concept_hits:
        append_source_links_to_concept(concept, raw_path.name, summary_path.name)

    entity_touched = upsert_entity_pages(compiled["cards"], raw_path.name, summary_path.name)

    append_log("INGEST", f"{raw_path.name} -> wiki/summary/{summary_path.name}")
    return {
        "ok": True,
        "source": raw_path.name,
        "summary_page": summary_path.name,
        "title": title,
        "char_count": len(content),
        "concepts": concept_hits,
        "entities": compiled["entities"],
        "entity_pages_updated": entity_touched,
        "llm_failed": compiled["llm_failed"],
    }


def ingest_all_raw() -> Dict:
    ensure_dirs()
    ensure_default_concepts()
    for path in ENTITY_DIR.glob("*.md"):
        path.unlink(missing_ok=True)
    candidates = [p for p in RAW_DIR.glob("*") if p.is_file() and p.suffix.lower() in {".md", ".txt"}]
    results = [ingest_raw_file(p) for p in candidates]
    sanitize_existing_entity_pages()
    refresh_index()
    success = [r for r in results if r.get("ok")]
    failed = [r for r in results if not r.get("ok")]
    return {"ok": True, "total": len(results), "success": success, "failed": failed}


def query_wiki(question: str, top_k: int = 3, city: str = "") -> Dict:
    ensure_dirs()
    question = (question or "").strip()
    if not question:
        return {"ok": False, "message": "问题不能为空"}

    pages = list(SUMMARY_DIR.glob("*.md")) + list(ENTITY_DIR.glob("*.md")) + list(CONCEPT_DIR.glob("*.md"))
    if not pages:
        return {"ok": False, "message": "Wiki 为空，请先执行摄入"}

    keywords = [k for k in re.split(r"[\s,，。；;、]+", question) if k]
    city_norm = (city or "").replace("市", "").strip().lower()
    scored = []

    for page in pages:
        text = page.read_text(encoding="utf-8", errors="ignore")
        if city_norm:
            text_norm = text.replace("市", "").lower()
            page_norm = page.stem.replace("市", "").lower()
            if city_norm not in text_norm and city_norm not in page_norm:
                continue

        score = sum(text.lower().count(k.lower()) for k in keywords)
        if score <= 0:
            continue

        safe_lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not has_llm_error(ln)]
        snippet = "；".join(safe_lines[:6])
        safe_text = "\n".join(safe_lines)
        scored.append(
            {
                "page": page,
                "score": score,
                "snippet": snippet,
                "content": safe_text,
            }
        )

    if not scored:
        return {"ok": True, "answer": "当前知识库未命中该问题关键词，建议先补充原始资料再摄入。", "hits": []}

    scored.sort(key=lambda x: x["score"], reverse=True)
    top_hits = scored[:top_k]

    llm_pages = [
        {
            "source": f"wiki/{hit['page'].parent.name}/{hit['page'].name}",
            "content": hit["content"],
        }
        for hit in top_hits
    ]

    llm_answer = _get_wiki_llm().answer_query(question, llm_pages).get("answer", "").strip()
    if not llm_answer or has_llm_error(llm_answer):
        llm_answer = (
            "基于当前本地 Wiki 命中结果，建议优先参考以下页面进行路线设计："
            + "；".join([hit["page"].stem for hit in top_hits])
            + "。当前 LLM 总结暂不可用，请先参考下方命中页面与来源。"
        )

    citations = [f"wiki/{hit['page'].parent.name}/{hit['page'].name}" for hit in top_hits]
    log_city = city_norm if city_norm else "-"
    append_log("QUERY", f"{question} (city={log_city}) -> {', '.join(citations)}")

    return {
        "ok": True,
        "answer": llm_answer,
        "hits": [
            {
                "page": f"wiki/{hit['page'].parent.name}/{hit['page'].name}",
                "score": hit["score"],
                "snippet": hit["snippet"][:300],
            }
            for hit in top_hits
        ],
    }


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


def lint_wiki() -> Dict:
    ensure_dirs()
    ensure_default_concepts()
    pages = list(SUMMARY_DIR.glob("*.md")) + list(ENTITY_DIR.glob("*.md")) + list(CONCEPT_DIR.glob("*.md"))
    issues: List[str] = []
    if not pages:
        issues.append("wiki 目录为空，无法执行健康检查。")
        return {"ok": True, "issues": issues, "score": 30}

    existing_names = {p.stem for p in pages}
    existing_paths = set()
    for p in pages:
        rel = p.relative_to(BASE_DIR).as_posix()
        existing_paths.add(rel)
        existing_paths.add(f"wiki/{p.parent.name}/{p.name}")
    for p in RAW_DIR.glob("*"):
        if p.is_file():
            rel = p.relative_to(BASE_DIR).as_posix()
            existing_paths.add(rel)
            existing_paths.add(f"raw/{p.name}")
    for page in pages:
        text = page.read_text(encoding="utf-8", errors="ignore")
        links = re.findall(r"\[\[([^\]]+)\]\]", text)
        if not links:
            issues.append(f"{page.name} 缺少交叉引用（孤立页面风险）。")
        for link in links:
            link_text = link.strip()
            if "/" in link_text or link_text.endswith(".md"):
                normalized = link_text.strip("/")
                if normalized not in existing_paths:
                    issues.append(f"{page.name} 引用了不存在页面：{link}")
                continue

            link_name = link_text.split(":")[-1].strip()
            if link_name and link_name not in existing_names:
                issues.append(f"{page.name} 引用了不存在页面：{link}")

    if len(list(SUMMARY_DIR.glob("*.md"))) < 2:
        issues.append("摘要页面少于2个，建议继续摄入原始资料。")

    score = max(40, 100 - len(issues) * 8)
    append_log("LINT", f"issues={len(issues)}, score={score}")
    return {"ok": True, "issues": issues, "score": score}


def backfill_concept_sources() -> Dict:
    ensure_dirs()
    summary_files = list(SUMMARY_DIR.glob("*.md"))
    touched = 0
    for summary in summary_files:
        text = summary.read_text(encoding="utf-8", errors="ignore")
        source_match = re.search(r"source_file:\s*raw/(.+)", text)
        raw_name = source_match.group(1).strip() if source_match else ""
        if not raw_name:
            continue
        concept_names = ["错峰出行", "预算控制"] + extract_concepts(text)
        for concept in concept_names:
            before = (CONCEPT_DIR / f"{concept}.md").read_text(encoding="utf-8", errors="ignore") if (CONCEPT_DIR / f"{concept}.md").exists() else ""
            append_source_links_to_concept(concept, raw_name, summary.name)
            after = (CONCEPT_DIR / f"{concept}.md").read_text(encoding="utf-8", errors="ignore") if (CONCEPT_DIR / f"{concept}.md").exists() else ""
            if after != before:
                touched += 1
    return {"ok": True, "touched": touched}
