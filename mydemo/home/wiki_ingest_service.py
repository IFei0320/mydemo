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


def _normalize_compile_result(raw_content: str, source_name: str, title: str) -> Dict:
    compiled = _get_wiki_llm().compile_raw(raw_content, source_name)

    summary = clean_text(compiled.get("summary", ""))
    if '"summary"' in summary and '"concepts"' in summary and '"cards"' in summary:
        try:
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
    manifest = _load_ingest_manifest()
    candidates = [p for p in RAW_DIR.glob("*") if p.is_file() and p.suffix.lower() in {".md", ".txt"}]

    success = []
    failed = []
    skipped = []
    new_files = []
    updated_files = []
    next_manifest = dict(manifest)

    for path in candidates:
        raw_hash = _compute_file_hash(path)
        prev = manifest.get(path.name)
        if prev and prev.get("hash") == raw_hash:
            skipped.append({
                "source": path.name,
                "summary_page": str(prev.get("summary_page") or f"{slugify(path.stem)}.md"),
            })
            continue

        result = ingest_raw_file(path)
        if result.get("ok"):
            success.append(result)
            next_manifest[path.name] = _manifest_entry(path, str(result.get("summary_page") or f"{slugify(path.stem)}.md"))
            if prev:
                updated_files.append(path.name)
            else:
                new_files.append(path.name)
        else:
            failed.append(result)

    sanitize_existing_entity_pages()
    refresh_index()
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
