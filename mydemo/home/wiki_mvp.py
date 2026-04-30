import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List


BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BASE_DIR / "raw"
WIKI_DIR = BASE_DIR / "wiki"
SUMMARY_DIR = WIKI_DIR / "summary"
ENTITY_DIR = WIKI_DIR / "entity"
CONCEPT_DIR = WIKI_DIR / "concept"
INDEX_FILE = BASE_DIR / "index.md"
LOG_FILE = BASE_DIR / "log.md"


def _ensure_dirs() -> None:
    for path in [RAW_DIR, WIKI_DIR, SUMMARY_DIR, ENTITY_DIR, CONCEPT_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def _slugify(name: str) -> str:
    value = re.sub(r"[^\w\u4e00-\u9fff\-]+", "-", name.strip().lower())
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or "untitled"


def _extract_title(content: str, fallback: str) -> str:
    for line in content.splitlines():
        text = line.strip()
        if text.startswith("#"):
            return text.lstrip("#").strip()
    return fallback


def _extract_focus_lines(content: str, limit: int = 12) -> List[str]:
    patterns = ["交通", "门票", "开放", "预约", "避雷", "预算", "路线", "时间", "推荐"]
    selected: List[str] = []
    for line in content.splitlines():
        text = line.strip()
        if not text:
            continue
        if any(token in text for token in patterns):
            selected.append(text)
        if len(selected) >= limit:
            break
    if selected:
        return selected
    chunks = [line.strip() for line in content.splitlines() if line.strip()]
    return chunks[: min(limit, len(chunks))]


def _extract_month_signals(content: str) -> List[str]:
    month_hits = re.findall(r"(1[0-2]|[1-9])月", content)
    unique = []
    for m in month_hits:
        token = f"{int(m)}月"
        if token not in unique:
            unique.append(token)
    return unique[:8]


def _season_to_months(season: str) -> List[str]:
    mapping = {
        "spring": ["3月", "4月", "5月"],
        "summer": ["6月", "7月", "8月"],
        "autumn": ["9月", "10月", "11月"],
        "winter": ["12月", "1月", "2月"],
    }
    return mapping.get((season or "").strip().lower(), [])


def _infer_budget_level(text: str) -> str:
    t = (text or "").lower()
    if any(k in t for k in ["免费", "低价", "便宜", "性价比"]):
        return "low"
    if any(k in t for k in ["高价", "贵", "票价较高", "消费高", "溢价"]):
        return "high"
    return "medium"


def _infer_transport_mode(text: str) -> str:
    t = text or ""
    if "地铁" in t:
        return "metro"
    if "公交" in t:
        return "bus"
    if "打车" in t or "出租车" in t:
        return "taxi"
    if "步行" in t:
        return "walk"
    return "mixed"


def _infer_crowd_level(text: str) -> str:
    t = text or ""
    if "极高" in t or "人流量极大" in t or "排队" in t:
        return "high"
    if "较少" in t or "低" in t:
        return "low"
    return "medium"


def _infer_best_time(text: str) -> str:
    t = text or ""
    if "夜景" in t or "日落" in t or "亮灯" in t:
        return "傍晚至夜间"
    if "上午" in t:
        return "工作日上午"
    return "白天错峰时段"


def _extract_pitfalls(text: str, limit: int = 3) -> List[str]:
    lines = [ln.strip("- ").strip() for ln in (text or "").splitlines() if ln.strip()]
    result = []
    for ln in lines:
        if any(k in ln for k in ["避雷", "避坑", "注意", "不要", "排队", "拥挤"]):
            result.append(ln[:60])
        if len(result) >= limit:
            break
    if not result:
        return ["避开高峰排队时段", "注意景区临时公告", "热门点位提前到达"]
    return result


def _extract_spot_names(content: str, limit: int = 10) -> List[str]:
    spot_names: List[str] = []
    for line in content.splitlines():
        text = line.strip().lstrip("#").strip()
        if not text:
            continue
        if "——" in text:
            name = text.split("——", 1)[0].strip(" -：:")
            if 1 < len(name) <= 30 and name not in spot_names:
                spot_names.append(name)
        elif text.startswith("###"):
            name = text.lstrip("#").strip().split(" ")[0].strip("：:")
            if 1 < len(name) <= 30 and name not in spot_names:
                spot_names.append(name)
        if len(spot_names) >= limit:
            break
    return spot_names


def _extract_concepts(content: str, limit: int = 6) -> List[str]:
    concept_rules = {
        "亲子出行": ["亲子", "儿童", "小朋友", "家庭"],
        "夜景路线": ["夜景", "亮灯", "日落", "晚上"],
        "交通换乘": ["地铁", "换乘", "公交", "打车", "交通"],
        "预约策略": ["预约", "购票", "抢票", "官方渠道"],
        "预算分层": ["预算", "人均", "省钱", "花费", "门票"],
        "避坑指南": ["避雷", "避坑", "注意事项", "陷阱", "不要"],
        "历史人文": ["历史", "博物馆", "纪念馆", "人文", "故居"],
        "自然生态": ["公园", "植物园", "森林", "湿地", "自然"],
        "游玩时段": ["上午", "下午", "最佳时间", "时段", "工作日"],
    }
    hits: List[str] = []
    text = content.lower()
    for concept, keywords in concept_rules.items():
        if any(k.lower() in text for k in keywords):
            hits.append(concept)
        if len(hits) >= limit:
            break
    return hits


def _append_log(event: str, detail: str) -> None:
    if not LOG_FILE.exists():
        LOG_FILE.write_text("# Wiki 操作日志\n\n", encoding="utf-8")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with LOG_FILE.open("a", encoding="utf-8") as fp:
        fp.write(f"- [{now}] [{event}] {detail}\n")


def _refresh_index() -> None:
    _ensure_dirs()
    summary_pages = sorted(SUMMARY_DIR.glob("*.md"))
    entity_pages = sorted(ENTITY_DIR.glob("*.md"))
    concept_pages = sorted(CONCEPT_DIR.glob("*.md"))

    lines = [
        "# LLM Wiki 索引",
        "",
        f"- 更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 原始资料数：{len(list(RAW_DIR.glob('*')))}",
        "",
        "## 摘要页面",
    ]
    if summary_pages:
        for p in summary_pages:
            lines.append(f"- [summary/{p.name}](wiki/summary/{p.name})")
    else:
        lines.append("- 暂无")

    lines.extend(["", "## 实体页面"])
    if entity_pages:
        for p in entity_pages:
            lines.append(f"- [entity/{p.name}](wiki/entity/{p.name})")
    else:
        lines.append("- 暂无")

    lines.extend(["", "## 概念页面"])
    if concept_pages:
        for p in concept_pages:
            lines.append(f"- [concept/{p.name}](wiki/concept/{p.name})")
    else:
        lines.append("- 暂无")

    INDEX_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _ensure_default_concepts() -> None:
    _ensure_dirs()
    concepts = {
        "错峰出行": [
            "# 概念：错峰出行",
            "",
            "## 定义",
            "在热门景点中，优先选择工作日、早场或晚场，降低排队与拥堵风险。",
            "",
            "## 应用要点",
            "- 尽量避开节假日高峰时段。",
            "- 热门场馆优先预约早场。",
            "- 可把核心景点安排在上午。",
        ],
        "预算控制": [
            "# 概念：预算控制",
            "",
            "## 定义",
            "在满足主要游玩目标前提下，通过门票、交通和餐饮策略控制总花费。",
            "",
            "## 应用要点",
            "- 先锁定高优先级景点预算。",
            "- 优先地铁与步行，减少打车占比。",
            "- 淡旺季票价差异要提前纳入规划。",
        ],
    }
    for name, lines in concepts.items():
        path = CONCEPT_DIR / f"{name}.md"
        if not path.exists():
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _upsert_dynamic_concept_pages(concepts: List[str], source_name: str, title: str) -> None:
    _ensure_dirs()
    for concept in concepts:
        concept_path = CONCEPT_DIR / f"{concept}.md"
        source_line = f"- 来源补充：{source_name}（{title}）"
        if concept_path.exists():
            text = concept_path.read_text(encoding="utf-8", errors="ignore")
            if source_line not in text:
                with concept_path.open("a", encoding="utf-8") as fp:
                    fp.write(source_line + "\n")
            continue

        lines = [
            f"# 概念：{concept}",
            "",
            "## 定义",
            f"{concept}是旅游路线规划中的关键语义维度，可用于约束筛选与行程优化。",
            "",
            "## 适用规则",
            "- 结合城市、景点热度、预算与时段信息进行策略推荐。",
            "- 优先根据原始资料中的明确描述提炼执行建议。",
            "",
            "## 来源关联",
            source_line,
            "",
            "## 交叉引用",
            "- [[概念:错峰出行]]",
            "- [[概念:预算控制]]",
        ]
        concept_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_source_links_to_concept(concept_name: str, source_name: str, summary_name: str) -> None:
    concept_path = CONCEPT_DIR / f"{concept_name}.md"
    if not concept_path.exists():
        return
    text = concept_path.read_text(encoding="utf-8", errors="ignore")
    source_line = f"- raw: [[raw/{source_name}]]"
    summary_line = f"- summary: [[wiki/summary/{summary_name}]]"
    marker = "## 来源追溯"
    if marker not in text:
        with concept_path.open("a", encoding="utf-8") as fp:
            fp.write("\n## 来源追溯\n")
            fp.write(source_line + "\n")
            fp.write(summary_line + "\n")
        return
    if source_line not in text or summary_line not in text:
        with concept_path.open("a", encoding="utf-8") as fp:
            if source_line not in text:
                fp.write(source_line + "\n")
            if summary_line not in text:
                fp.write(summary_line + "\n")


def ingest_raw_file(raw_path: Path) -> Dict:
    _ensure_dirs()
    if not raw_path.exists():
        return {"ok": False, "message": f"文件不存在: {raw_path.name}"}

    content = raw_path.read_text(encoding="utf-8", errors="ignore")
    if not content.strip():
        return {"ok": False, "message": f"文件为空: {raw_path.name}"}

    title = _extract_title(content, raw_path.stem)
    focus_lines = _extract_focus_lines(content)
    month_signals = _extract_month_signals(content)
    spot_names = _extract_spot_names(content)
    concept_hits = _extract_concepts(content)
    slug = _slugify(raw_path.stem)
    summary_path = SUMMARY_DIR / f"{slug}.md"
    word_count = len(content)

    summary = [
        f"# {title}",
        "",
        "## 来源信息",
        f"- source_file: raw/{raw_path.name}",
        f"- compiled_at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- char_count: {word_count}",
        "",
        "## 摘要",
        f"该资料已摄入，主题为：{title}。以下为可用于路线推荐的关键线索。",
        "",
        "## 关键要点",
    ]
    for line in focus_lines:
        summary.append(f"- {line}")
    summary.extend(
        [
            "",
            "## 关系抽取（景点-月份-策略）",
            f"- 识别景点: {'、'.join(spot_names) if spot_names else '未显式识别，建议补充小标题格式'}",
            f"- 识别月份: {'、'.join(month_signals) if month_signals else '未识别到月份，默认按季节规则处理'}",
            f"- 识别概念: {'、'.join(concept_hits) if concept_hits else '未识别到新概念'}",
            "- 策略提示: 优先将“高热度景点”放在工作日上午，夜景类景点放在日落后时段。",
            "",
            "## 关联建议",
            "- 可与其他景点页建立 [[概念:错峰出行]]、[[概念:预算控制]] 的交叉引用。",
            "- 后续查询时优先命中“交通/预约/避雷/预算”字段。",
        ]
    )
    summary_path.write_text("\n".join(summary) + "\n", encoding="utf-8")
    _upsert_dynamic_concept_pages(concept_hits, raw_path.name, title)
    for concept in ["错峰出行", "预算控制"] + concept_hits:
        _append_source_links_to_concept(concept, raw_path.name, summary_path.name)

    _append_log("INGEST", f"{raw_path.name} -> wiki/summary/{summary_path.name}")
    return {
        "ok": True,
        "source": raw_path.name,
        "summary_page": summary_path.name,
        "title": title,
        "char_count": word_count,
        "concepts": concept_hits,
    }


def backfill_concept_sources() -> Dict:
    _ensure_dirs()
    summary_files = list(SUMMARY_DIR.glob("*.md"))
    touched = 0
    for summary in summary_files:
        text = summary.read_text(encoding="utf-8", errors="ignore")
        source_match = re.search(r"source_file:\s*raw/(.+)", text)
        raw_name = source_match.group(1).strip() if source_match else ""
        if not raw_name:
            continue
        concept_names = ["错峰出行", "预算控制"] + _extract_concepts(text)
        for concept in concept_names:
            before = (CONCEPT_DIR / f"{concept}.md").read_text(encoding="utf-8", errors="ignore") if (CONCEPT_DIR / f"{concept}.md").exists() else ""
            _append_source_links_to_concept(concept, raw_name, summary.name)
            after = (CONCEPT_DIR / f"{concept}.md").read_text(encoding="utf-8", errors="ignore") if (CONCEPT_DIR / f"{concept}.md").exists() else ""
            if after != before:
                touched += 1
    return {"ok": True, "touched": touched}


def ingest_all_raw() -> Dict:
    _ensure_dirs()
    _ensure_default_concepts()
    candidates = [p for p in RAW_DIR.glob("*") if p.is_file() and p.suffix.lower() in {".md", ".txt"}]
    results = [ingest_raw_file(p) for p in candidates]
    _refresh_index()
    success = [r for r in results if r.get("ok")]
    failed = [r for r in results if not r.get("ok")]
    return {"ok": True, "total": len(results), "success": success, "failed": failed}


def query_wiki(question: str, top_k: int = 3, city: str = "") -> Dict:
    _ensure_dirs()
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
            # 城市粗过滤：只保留明显提及该城市的页面
            if city_norm not in text_norm and city_norm not in page_norm:
                continue
        score = sum(text.lower().count(k.lower()) for k in keywords)
        if score > 0:
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            snippet = "；".join(lines[0:6])
            scored.append({"page": page, "score": score, "snippet": snippet})

    if not scored:
        return {"ok": True, "answer": "当前知识库未命中该问题关键词，建议先补充原始资料再摄入。", "hits": []}

    scored.sort(key=lambda x: x["score"], reverse=True)
    top_hits = scored[:top_k]
    citations = [f"wiki/{hit['page'].parent.name}/{hit['page'].name}" for hit in top_hits]
    answer = (
        "基于当前本地 Wiki 命中结果，建议优先参考以下页面进行路线设计："
        + "；".join([hit["page"].stem for hit in top_hits])
        + "。可优先采用其中的预约、交通和避雷信息作为约束条件。"
    )
    log_city = city_norm if city_norm else "-"
    _append_log("QUERY", f"{question} (city={log_city}) -> {', '.join(citations)}")
    return {
        "ok": True,
        "answer": answer,
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
    _ensure_dirs()
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
                months = _extract_month_signals(text)
                card = {
                    "spot_name": spot,
                    "city": city,
                    "best_months": months,
                    "best_time": _infer_best_time(text),
                    "booking_required": ("预约" in text or "购票" in text),
                    "booking_tip": "建议提前在线预约，节假日至少提前1-3天。",
                    "transport_mode": _infer_transport_mode(text),
                    "transport_tip": "建议地铁优先，跨区段打车补充。",
                    "budget_level": _infer_budget_level(text),
                    "crowd_level": _infer_crowd_level(text),
                    "duration_suggestion": "1-3小时",
                    "pitfalls": _extract_pitfalls(text),
                    "source": f"wiki/summary/{page.name}",
                }
                # 召回后重排：月份、预算、拥挤度
                rank_score = 0.0
                season_months = _season_to_months(season)
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
    _ensure_dirs()
    _ensure_default_concepts()
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
            # 支持 [[raw/xxx.md]]、[[wiki/summary/xxx.md]] 这类路径链接
            if "/" in link_text or link_text.endswith(".md"):
                normalized = link_text.strip("/")
                if normalized not in existing_paths:
                    issues.append(f"{page.name} 引用了不存在页面：{link}")
                continue

            # 支持 [[概念:错峰出行]] 这类语义链接
            link_name = link_text.split(":")[-1].strip()
            if link_name and link_name not in existing_names:
                issues.append(f"{page.name} 引用了不存在页面：{link}")

    if len(list(SUMMARY_DIR.glob("*.md"))) < 2:
        issues.append("摘要页面少于2个，建议继续摄入原始资料。")

    score = max(40, 100 - len(issues) * 8)
    _append_log("LINT", f"issues={len(issues)}, score={score}")
    return {"ok": True, "issues": issues, "score": score}
