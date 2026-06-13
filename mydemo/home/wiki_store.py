from datetime import datetime
from pathlib import Path
from typing import Dict, List

from home.wiki_extract import (
    clean_text,
    extract_concepts,
    extract_focus_lines,
    extract_month_signals,
    extract_spot_names,
    has_llm_error,
    normalize_entity_name,
    safe_list,
)

# ── 目录常量定义 ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parents[1]                   # 项目根目录
RAW_DIR = BASE_DIR / "raw"                                       # 原始资料目录
WIKI_DIR = BASE_DIR / "wiki"                                     # Wiki 知识库根目录
SUMMARY_DIR = WIKI_DIR / "summary"                               # 摘要页面目录
ENTITY_DIR = WIKI_DIR / "entity"                                 # 实体页面目录
CONCEPT_DIR = WIKI_DIR / "concept"                               # 概念页面目录
INDEX_FILE = WIKI_DIR / "index.md"                               # 索引文件路径
LOG_FILE = WIKI_DIR / "log.md"                                   # 日志文件路径


def ensure_dirs() -> None:
    """确保所有必要的目录存在，不存在则创建。"""
    for path in [RAW_DIR, WIKI_DIR, SUMMARY_DIR, ENTITY_DIR, CONCEPT_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def append_log(event: str, detail: str) -> None:
    """追加操作日志到 log.md 文件。"""
    # ── 初始化日志文件 ────────────────────────────────────────
    if not LOG_FILE.exists():
        LOG_FILE.write_text("# Wiki 操作日志\n\n", encoding="utf-8")

    # ── 写入日志条目 ──────────────────────────────────────────
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with LOG_FILE.open("a", encoding="utf-8") as fp:
        fp.write(f"- [{now}] [{event}] {detail}\n")


def refresh_index() -> None:
    """重新生成 wiki/index.md 索引文件，列出所有摘要、实体、概念页面。"""
    ensure_dirs()

    # ── 收集所有页面 ──────────────────────────────────────────
    summary_pages = sorted(SUMMARY_DIR.glob("*.md"))
    entity_pages = sorted(ENTITY_DIR.glob("*.md"))
    concept_pages = sorted(CONCEPT_DIR.glob("*.md"))

    # ── 构建索引头部 ──────────────────────────────────────────
    lines = [
        "# LLM Wiki 索引",
        "",
        f"- 更新时刻：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 原始资料数：{len(list(RAW_DIR.glob('*')))}",
        "",
        "## 摘要页面",
    ]

    # ── 列出摘要页面 ──────────────────────────────────────────
    if summary_pages:
        for p in summary_pages:
            lines.append(f"- [summary/{p.name}](wiki/summary/{p.name})")
    else:
        lines.append("- 暂无")

    # ── 列出实体页面 ──────────────────────────────────────────
    lines.extend(["", "## 实体页面"])
    if entity_pages:
        for p in entity_pages:
            lines.append(f"- [entity/{p.name}](wiki/entity/{p.name})")
    else:
        lines.append("- 暂无")

    # ── 列出概念页面 ──────────────────────────────────────────
    lines.extend(["", "## 概念页面"])
    if concept_pages:
        for p in concept_pages:
            lines.append(f"- [concept/{p.name}](wiki/concept/{p.name})")
    else:
        lines.append("- 暂无")

    # ── 写入索引文件 ──────────────────────────────────────────
    INDEX_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ensure_default_concepts() -> None:
    """确保默认概念页面存在（错峰出行、预算控制），不存在则创建。"""
    ensure_dirs()

    # ── 默认概念内容定义 ──────────────────────────────────────
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

    # ── 创建不存在的概念页面 ──────────────────────────────────
    for name, lines in concepts.items():
        path = CONCEPT_DIR / f"{name}.md"
        if not path.exists():
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_rule_based_summary(content: str, raw_name: str, title: str) -> str:
    """基于规则生成摘要页面内容（当 LLM 不可用时的降级方案）。"""
    # ── 提取关键信息 ──────────────────────────────────────────
    focus_lines = extract_focus_lines(content)                   # 重点行（含交通、门票等关键词）
    month_signals = extract_month_signals(content)               # 月份信号
    spot_names = extract_spot_names(content)                     # 景点名称
    concept_hits = extract_concepts(content)                     # 概念标签

    # ── 构建摘要结构 ──────────────────────────────────────────
    lines = [
        f"# {title}",
        "",
        "## 来源信息",
        f"- source_file: raw/{raw_name}",
        f"- compiled_at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- char_count: {len(content)}",
        "",
        "## AI 摘要",
        f"该资料已摄入，主题为：{title}。以下为可用于路线推荐的关键线索。",
        "",
        "## 关键要点",
    ]

    # ── 添加重点行 ────────────────────────────────────────────
    for line in focus_lines:
        lines.append(f"- {line}")

    # ── 添加实体清单、概念标签、策略提示 ──────────────────────
    lines.extend(
        [
            "",
            "## 实体清单",
            f"- {'、'.join(spot_names) if spot_names else '未显式识别，建议补充小标题格式'}",
            "",
            "## 概念标签",
            f"- {'、'.join(concept_hits) if concept_hits else '未识别到新概念'}",
            "",
            "## 隐含策略提示",
            f"- 推荐月份线索：{'、'.join(month_signals) if month_signals else '未识别到明确月份，建议结合季节判断'}",
            "- 优先将高热度景点放在工作日上午，夜景类景点放在日落后时段。",
            "",
            "## 交叉引用",
            f"- [[raw/{raw_name}]]",
            "- [[概念:错峰出行]]",
            "- [[概念:预算控制]]",
        ]
    )

    return "\n".join(lines).strip()


def format_summary_markdown(summary_text: str, raw_name: str, char_count: int) -> str:
    """格式化摘要文本为标准 Markdown 格式，补充来源信息和交叉引用。"""
    # ── 尝试解析 JSON 格式的摘要 ──────────────────────────────
    text = (summary_text or "").strip()
    if '"summary"' in text and '"concepts"' in text and '"cards"' in text:
        try:
            import json
            parsed = json.loads(text)
            text = clean_text(parsed.get("summary", ""))
        except Exception:
            text = ""

    # ── 降级处理：生成空摘要 ──────────────────────────────────
    if not text:
        text = f"# {Path(raw_name).stem}\n\n## AI 摘要\n暂无摘要。"

    # ── 补充来源信息区块 ──────────────────────────────────────
    if "## 来源信息" not in text:
        title_line = text.splitlines()[0].strip() if text.splitlines() else f"# {Path(raw_name).stem}"
        body = text
        if title_line.startswith("#"):
            body = "\n".join(text.splitlines()[1:]).strip()
        lines = [
            title_line if title_line.startswith("#") else f"# {Path(raw_name).stem}",
            "",
            "## 来源信息",
            f"- source_file: raw/{raw_name}",
            f"- compiled_at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"- char_count: {char_count}",
            "",
        ]
        if body:
            lines.append(body)
        text = "\n".join(lines).strip()

    # ── 补充交叉引用 ──────────────────────────────────────────
    if f"[[raw/{raw_name}]]" not in text:
        text += f"\n\n## 交叉引用\n- [[raw/{raw_name}]]"

    return text.strip() + "\n"


def upsert_entity_pages(cards: List[Dict], source_name: str, summary_name: str) -> int:
    """根据知识卡片列表创建或更新实体页面，返回处理的实体数量。"""
    touched = 0

    for card in cards:
        # ── 获取实体名称 ──────────────────────────────────────
        spot_name = normalize_entity_name(card.get("spot_name", ""))
        if not spot_name:
            continue

        entity_path = ENTITY_DIR / f"{spot_name}.md"
        source_line = f"- 来源：{source_name}"
        summary_line = f"- 摘要页：[[wiki/summary/{summary_name}]]"

        # ── 提取结构化描述字段 ────────────────────────────────
        desc_lines = []

        best_time = clean_text(card.get("best_time", ""))
        if best_time:
            desc_lines.append(f"- 推荐时段：{best_time}")

        booking_tip = clean_text(card.get("booking_tip", ""))
        if booking_tip:
            desc_lines.append(f"- 预约建议：{booking_tip}")

        transport_tip = clean_text(card.get("transport_tip", ""))
        if transport_tip:
            desc_lines.append(f"- 交通建议：{transport_tip}")

        crowd_tip = clean_text(card.get("crowd_tip", ""))
        if crowd_tip:
            desc_lines.append(f"- 人流提示：{crowd_tip}")

        duration_suggestion = clean_text(card.get("duration_suggestion", ""))
        if duration_suggestion:
            desc_lines.append(f"- 建议时长：{duration_suggestion}")

        # ── 提取避坑建议（过滤无效内容） ──────────────────────
        pitfalls = [
            p for p in safe_list(card.get("pitfalls", []), limit=4)
            if not any(token in p for token in ["## ", "### ", "|", "[^", "——"])
        ]
        if pitfalls:
            desc_lines.append(f"- 避坑建议：{'；'.join(pitfalls)}")

        # ── 提取补充洞察 ──────────────────────────────────────
        llm_note = clean_text(card.get("llm_note", ""))
        if llm_note:
            desc_lines.append(f"- 补充洞察：{llm_note}")
        if not desc_lines:
            desc_lines.append("- 暂无结构化细节，建议回看原始资料与摘要页。")

        # ── 构建概念交叉引用 ──────────────────────────────────
        concept_refs = ["[[概念:错峰出行]]", "[[概念:预算控制]]"]
        if card.get("booking_required") and booking_tip:
            concept_refs.append("[[概念:预约策略]]")
        if (card.get("transport_mode") or "") == "metro" and transport_tip:
            concept_refs.append("[[概念:交通换乘]]")

        # ── 构建附近景点引用 ──────────────────────────────────
        nearby_refs = [
            f"[[实体:{name}]]"
            for name in safe_list(card.get("nearby", []), limit=6)
            if name != spot_name
        ]

        # ── 组装实体页面内容 ──────────────────────────────────
        lines = [
            f"# 实体：{spot_name}",
            "",
            "## 定义",
            f"{spot_name}是旅游知识库中的关键实体，可能为景点、餐厅、酒店或交通站点。",
            "",
            "## 来源聚合",
            source_line,
            summary_line,
            *desc_lines,
            "",
            "## 交叉引用",
            *[f"- {ref}" for ref in concept_refs],
        ]
        if nearby_refs:
            lines.extend(["", "## 附近关联", *[f"- {ref}" for ref in nearby_refs]])

        # ── 写入文件 ──────────────────────────────────────────
        entity_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        touched += 1

    return touched


def sanitize_existing_entity_pages() -> int:
    """清理现有实体页面中的 LLM 错误内容，返回清理的页面数量。"""
    touched = 0

    for path in ENTITY_DIR.glob("*.md"):
        text = path.read_text(encoding="utf-8", errors="ignore")

        # ── 跳过无错误的页面 ──────────────────────────────────
        if not has_llm_error(text):
            continue

        # ── 移除包含错误的行 ──────────────────────────────────
        cleaned_lines = [line for line in text.splitlines() if not has_llm_error(line)]
        cleaned = "\n".join(line for line in cleaned_lines if line.strip()).strip()

        # ── 补充清理说明 ──────────────────────────────────────
        if "## 来源聚合" in cleaned and "- 描述摘录：" not in cleaned:
            cleaned = cleaned.replace(
                "## 来源聚合",
                "## 来源聚合\n- 描述摘录：历史 LLM 异常内容已清理，建议重新摄入后补全结构化描述。",
                1,
            )

        # ── 写入清理后的内容 ──────────────────────────────────
        path.write_text(cleaned + "\n", encoding="utf-8")
        touched += 1

    return touched


def upsert_dynamic_concept_pages(concepts: List[str], source_name: str, title: str) -> None:
    """动态创建或更新概念页面，追加来源信息。"""
    ensure_dirs()

    for concept in concepts:
        concept_path = CONCEPT_DIR / f"{concept}.md"
        source_line = f"- 来源补充：{source_name}（{title}）"

        # ── 已存在：追加来源行 ────────────────────────────────
        if concept_path.exists():
            text = concept_path.read_text(encoding="utf-8", errors="ignore")
            if source_line not in text:
                with concept_path.open("a", encoding="utf-8") as fp:
                    fp.write(source_line + "\n")
            continue

        # ── 不存在：创建新概念页面 ────────────────────────────
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


def append_source_links_to_concept(concept_name: str, source_name: str, summary_name: str) -> None:
    """向概念页面追加来源追溯信息（原始文件和摘要页）。"""
    concept_path = CONCEPT_DIR / f"{concept_name}.md"
    if not concept_path.exists():
        return

    text = concept_path.read_text(encoding="utf-8", errors="ignore")
    source_line = f"- raw: [[raw/{source_name}]]"
    summary_line = f"- summary: [[wiki/summary/{summary_name}]]"
    marker = "## 来源追溯"

    # ── 不存在来源追溯区块：创建并写入 ────────────────────────
    if marker not in text:
        with concept_path.open("a", encoding="utf-8") as fp:
            fp.write("\n## 来源追溯\n")
            fp.write(source_line + "\n")
            fp.write(summary_line + "\n")
        return

    # ── 已存在区块：追加缺失的行 ──────────────────────────────
    if source_line not in text or summary_line not in text:
        with concept_path.open("a", encoding="utf-8") as fp:
            if source_line not in text:
                fp.write(source_line + "\n")
            if summary_line not in text:
                fp.write(summary_line + "\n")
