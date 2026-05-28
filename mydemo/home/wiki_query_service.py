import re
from typing import Dict, List

from ai.wiki_llm import WikiLLM
from home.wiki_extract import has_llm_error
from home.wiki_store import BASE_DIR, CONCEPT_DIR, ENTITY_DIR, RAW_DIR, SUMMARY_DIR, append_log, ensure_default_concepts, ensure_dirs


def _get_wiki_llm() -> WikiLLM:
    return WikiLLM()


def _clean_answer_text(text: str) -> str:
    value = (text or "").strip()
    if not value:
        return ""

    value = re.sub(r"\[\^[^\]]+\]", "", value)
    value = re.sub(r"^\s{0,3}#{1,6}\s*", "", value, flags=re.MULTILINE)
    value = re.sub(r"^\s{0,3}[-*+]\s+", "", value, flags=re.MULTILINE)
    value = re.sub(r"^\s{0,3}>\s*", "", value, flags=re.MULTILINE)
    value = re.sub(r"^(\s*)(\d+)\.\s*", r"\1\2. ", value, flags=re.MULTILINE)
    value = re.sub(r"^\s*[-*_]{3,}\s*$", "", value, flags=re.MULTILINE)
    value = value.replace("**", "").replace("__", "").replace("`", "")
    value = re.sub(r"\b(?:raw|wiki)/(?:summary|entity|concept)/", "", value)
    value = re.sub(r"\braw/", "", value)
    value = re.sub(r"\.md\b", "", value)
    value = value.replace("Wiki 页面内容", "现有资料")
    value = value.replace("Wiki 页面", "资料页面")
    value = value.replace("实体清单", "资料中提到的地点")
    value = value.replace("关键实体", "相关地点")
    value = value.replace("结构化细节", "详细信息")
    value = value.replace("结构化详细信息", "详细信息")

    cleaned_lines = []
    for raw_line in value.splitlines():
        line = raw_line.strip()
        if not line:
            cleaned_lines.append("")
            continue
        if re.match(r"^:\s*根据", line):
            continue
        if line.startswith("|") and line.endswith("|"):
            parts = [part.strip() for part in line.strip("|").split("|") if part.strip()]
            if parts and not all(set(part) <= {":", "-"} for part in parts):
                line = "  ".join(parts)
            else:
                continue
        line = re.sub(r"\s{2,}", " ", line).strip()
        cleaned_lines.append(line)

    value = "\n".join(cleaned_lines)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _rewrite_answer_for_user(question: str, draft_answer: str, hits: List[Dict]) -> str:
    if not draft_answer.strip():
        return ""
    rewritten = _get_wiki_llm().rewrite_answer_for_user(question, draft_answer, hits).get("answer", "").strip()
    if not rewritten or has_llm_error(rewritten):
        return ""
    return _clean_answer_text(rewritten)


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
        scored.append(
            {
                "page": page,
                "score": score,
                "snippet": "；".join(safe_lines[:6]),
                "content": "\n".join(safe_lines),
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
    llm_answer = _clean_answer_text(llm_answer)

    hit_payload = [
        {
            "page": f"wiki/{hit['page'].parent.name}/{hit['page'].name}",
            "score": hit["score"],
            "snippet": hit["snippet"][:300],
        }
        for hit in top_hits
    ]
    final_answer = _rewrite_answer_for_user(question, llm_answer, hit_payload) or llm_answer

    citations = [f"wiki/{hit['page'].parent.name}/{hit['page'].name}" for hit in top_hits]
    log_city = city_norm if city_norm else "-"
    append_log("QUERY", f"{question} (city={log_city}) -> {', '.join(citations)}")
    return {"ok": True, "answer": final_answer, "hits": hit_payload}


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
