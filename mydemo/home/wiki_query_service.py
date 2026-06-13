import re
from typing import Dict, List

from ai.wiki_llm import WikiLLM
from home.wiki_extract import has_llm_error
from home.wiki_store import BASE_DIR, CONCEPT_DIR, ENTITY_DIR, RAW_DIR, SUMMARY_DIR, append_log, ensure_default_concepts, ensure_dirs


def _get_wiki_llm() -> WikiLLM:
    return WikiLLM()


def _clean_answer_text(text: str) -> str:
    # ── 基础清理 ──────────────────────────────────────────────
    value = (text or "").strip()
    if not value:
        return ""

    # ── 移除 Markdown 格式标记 ────────────────────────────────
    value = re.sub(r"\[\^[^\]]+\]", "", value)                                        # 脚注引用
    value = re.sub(r"^\s{0,3}#{1,6}\s*", "", value, flags=re.MULTILINE)               # 标题标记
    value = re.sub(r"^\s{0,3}[-*+]\s+", "", value, flags=re.MULTILINE)                # 无序列表
    value = re.sub(r"^\s{0,3}>\s*", "", value, flags=re.MULTILINE)                    # 引用块
    value = re.sub(r"^(\s*)(\d+)\.\s*", r"\1\2. ", value, flags=re.MULTILINE)        # 有序列表格式化
    value = re.sub(r"^\s*[-*_]{3,}\s*$", "", value, flags=re.MULTILINE)               # 分割线
    value = value.replace("**", "").replace("__", "").replace("`", "")                 # 加粗、行内代码

    # ── 移除文件路径前缀 ──────────────────────────────────────
    value = re.sub(r"\b(?:raw|wiki)/(?:summary|entity|concept)/", "", value)           # wiki/raw 目录路径
    value = re.sub(r"\braw/", "", value)                                               # raw/ 前缀
    value = re.sub(r"\.md\b", "", value)                                               # .md 后缀

    # ── 替换技术术语为用户友好表述 ────────────────────────────
    value = value.replace("Wiki 页面内容", "现有资料")
    value = value.replace("Wiki 页面", "资料页面")
    value = value.replace("实体清单", "资料中提到的地点")
    value = value.replace("关键实体", "相关地点")
    value = value.replace("结构化细节", "详细信息")
    value = value.replace("结构化详细信息", "详细信息")

    # ── 逐行清理 ──────────────────────────────────────────────
    cleaned_lines = []
    for raw_line in value.splitlines():
        line = raw_line.strip()
        if not line:
            cleaned_lines.append("")
            continue
        # 移除以 "根据" 开头的重复来源引用
        if re.match(r"^:\s*根据", line):
            continue
        # 处理表格行：转为文本拼接
        if line.startswith("|") and line.endswith("|"):
            parts = [part.strip() for part in line.strip("|").split("|") if part.strip()]
            if parts and not all(set(part) <= {":", "-"} for part in parts):
                line = "  ".join(parts)
            else:
                continue
        # 压缩多余空格
        line = re.sub(r"\s{2,}", " ", line).strip()
        cleaned_lines.append(line)

    # ── 最终整理 ──────────────────────────────────────────────
    value = "\n".join(cleaned_lines)
    value = re.sub(r"\n{3,}", "\n\n", value)                                          # 合并多余空行
    return value.strip()


def _rewrite_answer_for_user(question: str, draft_answer: str, hits: List[Dict]) -> str:
    # ── 空答案直接返回 ────────────────────────────────────────
    if not draft_answer.strip():
        return ""

    # ── 调用 LLM 进行二次润色 ────────────────────────────────
    rewritten = _get_wiki_llm().rewrite_answer_for_user(question, draft_answer, hits).get("answer", "").strip()

    # ── 校验结果有效性 ────────────────────────────────────────
    if not rewritten or has_llm_error(rewritten):
        return ""

    return _clean_answer_text(rewritten)


def query_wiki(question: str, top_k: int = 3, city: str = "") -> Dict:
    # ── 参数校验 ──────────────────────────────────────────────
    ensure_dirs()
    question = (question or "").strip()
    if not question:
        return {"ok": False, "message": "问题不能为空"}

    # ── 收集所有可查询页面 ────────────────────────────────────
    pages = list(SUMMARY_DIR.glob("*.md")) + list(ENTITY_DIR.glob("*.md")) + list(CONCEPT_DIR.glob("*.md"))
    if not pages:
        return {"ok": False, "message": "Wiki 为空，请先执行摄入"}

    # ── 提取关键词并规范化城市 ────────────────────────────────
    keywords = [k for k in re.split(r"[\s,，。；;、]+", question) if k]                # 按标点分词
    city_norm = (city or "").replace("市", "").strip().lower()                         # 去掉"市"后缀统一格式
    scored = []

    # ── 遍历页面进行评分 ──────────────────────────────────────
    for page in pages:
        text = page.read_text(encoding="utf-8", errors="ignore")

        # 城市过滤：跳过不包含目标城市的页面
        if city_norm:
            text_norm = text.replace("市", "").lower()
            page_norm = page.stem.replace("市", "").lower()
            if city_norm not in text_norm and city_norm not in page_norm:
                continue

        # 关键词评分：统计所有关键词在文本中出现的总次数
        score = sum(text.lower().count(k.lower()) for k in keywords)
        if score <= 0:
            continue

        # 提取安全文本行（排除 LLM 错误信息）
        safe_lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not has_llm_error(ln)]
        scored.append(
            {
                "page": page,
                "score": score,
                "snippet": "；".join(safe_lines[:6]),                                   # 取前6行作为摘要
                "content": "\n".join(safe_lines),
            }
        )

    # ── 无命中结果 ────────────────────────────────────────────
    if not scored:
        return {"ok": True, "answer": "当前知识库未命中该问题关键词，建议先补充原始资料再摄入。", "hits": []}

    # ── 排序并取 Top-K ────────────────────────────────────────
    scored.sort(key=lambda x: x["score"], reverse=True)
    top_hits = scored[:top_k]

    # ── 构建 LLM 上下文 ───────────────────────────────────────
    llm_pages = [
        {
            "source": f"wiki/{hit['page'].parent.name}/{hit['page'].name}",
            "content": hit["content"],
        }
        for hit in top_hits
    ]

    # ── 第一次 LLM 调用：生成初步答案 ─────────────────────────
    llm_answer = _get_wiki_llm().answer_query(question, llm_pages).get("answer", "").strip()

    # LLM 失败时的降级处理：直接返回命中页面列表
    if not llm_answer or has_llm_error(llm_answer):
        llm_answer = (
            "基于当前本地 Wiki 命中结果，建议优先参考以下页面进行路线设计："
            + "；".join([hit["page"].stem for hit in top_hits])
            + "。当前 LLM 总结暂不可用，请先参考下方命中页面与来源。"
        )
    llm_answer = _clean_answer_text(llm_answer)

    # ── 构建命中结果负载 ──────────────────────────────────────
    hit_payload = [
        {
            "page": f"wiki/{hit['page'].parent.name}/{hit['page'].name}",
            "score": hit["score"],
            "snippet": hit["snippet"][:300],
        }
        for hit in top_hits
    ]

    # ── 第二次 LLM 调用：润色为用户友好表述 ───────────────────
    final_answer = _rewrite_answer_for_user(question, llm_answer, hit_payload) or llm_answer

    # ── 记录查询日志 ──────────────────────────────────────────
    citations = [f"wiki/{hit['page'].parent.name}/{hit['page'].name}" for hit in top_hits]
    log_city = city_norm if city_norm else "-"
    append_log("QUERY", f"{question} (city={log_city}) -> {', '.join(citations)}")

    return {"ok": True, "answer": final_answer, "hits": hit_payload}


def lint_wiki() -> Dict:
    # ── 初始化 ────────────────────────────────────────────────
    ensure_dirs()
    ensure_default_concepts()
    pages = list(SUMMARY_DIR.glob("*.md")) + list(ENTITY_DIR.glob("*.md")) + list(CONCEPT_DIR.glob("*.md"))
    issues: List[str] = []
    if not pages:
        issues.append("wiki 目录为空，无法执行健康检查。")
        return {"ok": True, "issues": issues, "score": 30}

    # ── 收集所有已存在页面的名称和路径 ────────────────────────
    existing_names = {p.stem for p in pages}                                           # 页面文件名（不含后缀）
    existing_paths = set()
    for p in pages:
        rel = p.relative_to(BASE_DIR).as_posix()                                      # 相对路径
        existing_paths.add(rel)
        existing_paths.add(f"wiki/{p.parent.name}/{p.name}")                           # wiki/ 目录下的路径
    for p in RAW_DIR.glob("*"):
        if p.is_file():
            rel = p.relative_to(BASE_DIR).as_posix()
            existing_paths.add(rel)
            existing_paths.add(f"raw/{p.name}")                                        # raw/ 目录下的路径

    # ── 检查每个页面的交叉引用 ────────────────────────────────
    for page in pages:
        text = page.read_text(encoding="utf-8", errors="ignore")
        links = re.findall(r"\[\[([^\]]+)\]\]", text)                                 # 提取所有 [[链接]]

        # 检查孤立页面：没有任何交叉引用
        if not links:
            issues.append(f"{page.name} 缺少交叉引用（孤立页面风险）。")

        # 检查断裂链接：引用的页面是否存在
        for link in links:
            link_text = link.strip()

            # 处理带路径的链接（如 [[raw/xxx.md]]）
            if "/" in link_text or link_text.endswith(".md"):
                normalized = link_text.strip("/")
                if normalized not in existing_paths:
                    issues.append(f"{page.name} 引用了不存在页面：{link}")
                continue

            # 处理不带路径的链接（如 [[实体:外滩]]）
            link_name = link_text.split(":")[-1].strip()
            if link_name and link_name not in existing_names:
                issues.append(f"{page.name} 引用了不存在页面：{link}")

    # ── 检查摘要页面数量 ──────────────────────────────────────
    if len(list(SUMMARY_DIR.glob("*.md"))) < 2:
        issues.append("摘要页面少于2个，建议继续摄入原始资料。")

    # ── 计算健康分数并记录日志 ────────────────────────────────
    score = max(40, 100 - len(issues) * 8)                                            # 每个问题扣8分，最低40分
    append_log("LINT", f"issues={len(issues)}, score={score}")

    return {"ok": True, "issues": issues, "score": score}
