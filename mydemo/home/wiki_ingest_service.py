import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Dict

from ai.wiki_llm import WikiLLM
from home.wiki_extract import (
    clean_text,
    extract_concepts,
    extract_month_signals,
    extract_spot_names,
    extract_title,
    has_llm_error,
    normalize_entity_name,
    safe_list,
    slugify,
)
from home.wiki_store import (
    BASE_DIR,
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

MANIFEST_FILE = BASE_DIR / "wiki" / ".ingest_manifest.json"


def _get_wiki_llm() -> WikiLLM:
    return WikiLLM()


def _load_ingest_manifest() -> Dict[str, Dict]:
    ensure_dirs()
    if not MANIFEST_FILE.exists():
        return {}
    try:
        data = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_ingest_manifest(manifest: Dict[str, Dict]) -> None:
    ensure_dirs()
    MANIFEST_FILE.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def _compute_file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest_entry(raw_path: Path, summary_page: str) -> Dict:
    stat = raw_path.stat()
    return {
        "hash": _compute_file_hash(raw_path),
        "summary_page": summary_page,
        "size": stat.st_size,
        "mtime": int(stat.st_mtime),
        "ingested_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _normalize_compile_result(raw_content: str, source_name: str, title: str) -> Dict:    # 定义一个私有函数，用于标准化和清理从 LLM (大语言模型) 编译得到的结果。
    compiled = _get_wiki_llm().compile_raw(raw_content, source_name)      # 调用全局 LLM 实例的 compile_raw 方法，对原始内容进行初步编译/解析。

    summary = clean_text(compiled.get("summary", ""))    # 获取 LLM 生成的摘要并清洗文本。
    if '"summary"' in summary and '"concepts"' in summary and '"cards"' in summary:
        try:
            parsed = json.loads(summary)
            summary = clean_text(parsed.get("summary", ""))
        except Exception:
            summary = ""

    concepts = safe_list(compiled.get("concepts", []))        # 获取概念列表，使用 safe_list 确保结果是列表类型，防止 None 报错
    entities = []               # 初始化实体列表。
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
                "pitfalls": [
                    p for p in safe_list(card.get("pitfalls", []), limit=6)
                    if not any(token in p for token in ["## ", "### ", "|", "[^", "——"])
                ],
                "nearby": [
                    normalize_entity_name(name)
                    for name in safe_list(card.get("nearby", []), limit=8)
                    if normalize_entity_name(name)
                ],
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


def ingest_raw_file(raw_path: Path) -> Dict:     # 该函数负责处理单个原始文件（.md 或 .txt）的摄入逻辑：解析内容、提取信息、生成摘要、更新概念和实体页面。
    ensure_dirs()                                 # 再次调用 ensure_dirs()，确保在文件处理过程中所需的目录结构存在，防止写入操作失败。
    if not raw_path.exists():
        return {"ok": False, "message": f"文件不存在: {raw_path.name}"}

    content = raw_path.read_text(encoding="utf-8", errors="ignore")       # 读取文件的全部内容。
    if not content.strip():
        return {"ok": False, "message": f"文件为空: {raw_path.name}"}

    title = extract_title(content, raw_path.stem)     # 调用 extract_title 函数从内容中提取标题。
    slug = slugify(raw_path.stem)                      # 使用 slugify 函数将原始文件名转换为Slug格式。
    summary_path = SUMMARY_DIR / f"{slug}.md"          # 创建一个与原始文件同名的摘要文件路径。

    compiled = _normalize_compile_result(content, raw_path.name, title)     # 调用私有函数 _normalize_compile_result，对原始内容进行编译/解析。
    summary_markdown = format_summary_markdown(compiled["summary"], raw_path.name, len(content))      # 调用 format_summary_markdown，根据编译后的摘要内容格式化 Markdown 字符串
    summary_path.write_text(summary_markdown, encoding="utf-8")

    concept_hits = compiled["concepts"] or extract_concepts(content)        # 优先使用编译结果中的 concepts；如果为空，则调用 extract_concepts 函数从原始内容中手动提取概念。
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


def ingest_all_raw() -> Dict:   # 返回类型为字典 (Dict)。该函数的核心逻辑是遍历 RAW_DIR 目录下的所有有效文件（.md 或 .txt），并根据增量更新策略进行摄入处理。
    ensure_dirs()               # 调用辅助函数 ensure_dirs()，确保程序运行所需的必要目录结构存在        
    ensure_default_concepts()    
    manifest = _load_ingest_manifest()     # 调用私有函数 _load_ingest_manifest() 加载当前的“摄入清单”（manifest）
    candidates = [p for p in RAW_DIR.glob("*") if p.is_file() and p.suffix.lower() in {".md", ".txt"}]      # candidates 变量存储了所有待处理文件的 Path 对象列表。
 # 初始化多个空列表和字典，用于分类统计处理结果：
    success = []
    failed = []
    skipped = []
    new_files = []
    updated_files = []
    next_manifest = dict(manifest)

    for path in candidates:
        raw_hash = _compute_file_hash(path)         # 计算当前文件 path 的内容哈希值（raw_hash），用于判断文件内容是否发生变化。
        prev = manifest.get(path.name)
        if prev and prev.get("hash") == raw_hash:
            skipped.append({               # 将跳过信息加入 skipped 列表，并跳过本次循环，不执行后续的摄入逻辑，节省资源。
                "source": path.name,
                "summary_page": str(prev.get("summary_page") or f"{slugify(path.stem)}.md"),
            })
            continue

        result = ingest_raw_file(path)        # 调用核心摄入函数 ingest_raw_file(path)，对当前文件进行解析、清洗、入库等操作。
        if result.get("ok"):
            success.append(result)
            next_manifest[path.name] = _manifest_entry(path, str(result.get("summary_page") or f"{slugify(path.stem)}.md"))
            if prev:
                updated_files.append(path.name)
            else:
                new_files.append(path.name)
        else:
            failed.append(result)

    sanitize_existing_entity_pages()                                # 调用辅助函数 sanitize_existing_entity_pages()，对wiki/entity 目录中的文件进行清理，确保文件内容符合要求。
    refresh_index()                                                   # 调用辅助函数 refresh_index()，更新wiki/entity 目录中的索引文件，确保索引文件内容正确。
    _save_ingest_manifest(next_manifest)
    append_log(
        "INGEST_ALL",
        f"total={len(candidates)}, new={len(new_files)}, updated={len(updated_files)}, skipped={len(skipped)}, failed={len(failed)}",
    )
    return {
        "ok": True,
        "total": len(candidates),
        "ingested": len(success),
        "new_files": new_files,
        "updated_files": updated_files,
        "skipped": len(skipped),
        "failed_count": len(failed),
        "success": success,
        "failed": failed,
        "skipped_items": skipped,
        "mode": "incremental_only",
    }
