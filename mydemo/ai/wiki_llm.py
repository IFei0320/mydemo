import json
import re

LLM_ERROR_PREFIX = "[LLM 调用异常:"

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


class WikiLLM:
    """Wiki 专用 LLM 封装层。

    负责：
    - 将原始文档编译为结构化 Wiki 摘要（compile_raw）
    - 基于召回的 Wiki 页面生成带引用的答案（answer_query）
    - 对 Wiki 页面进行深度健康检查（lint_pages）
    """

    def __init__(self, model: str = "deepseek-chat"):
        self.model = model
        self.client = None
        if OpenAI is not None:
            self.client = OpenAI(
                api_key="sk-d2e0034a6f264140a8017b1e98359312",
                base_url="https://api.deepseek.com",
            )

    def _call(self, system_prompt: str, user_prompt: str, max_tokens: int = 2000) -> str:
        if self.client is None:
            return f"{LLM_ERROR_PREFIX} openai SDK 未安装或初始化失败]"
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                stream=False,
                max_tokens=max_tokens,
                extra_body={"thinking": {"type": "disabled"}},
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            return f"{LLM_ERROR_PREFIX} {e}]"

    @staticmethod
    def _strip_code_fence(text: str) -> str:
        t = (text or "").strip()
        if t.startswith("```"):
            lines = t.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            t = "\n".join(lines).strip()
        return t

    def compile_raw(self, raw_content: str, source_name: str) -> dict:
        system = (
            "你是一个 Wiki 编译器。你的任务是将原始旅游攻略文档编译成结构化的 Markdown 知识摘要，\n"
            "并为文中提到的每个景点预生成结构化知识卡片。\n"
            "\n"
            "要求：\n"
            "1. 深入理解原文，提炼隐含信息（如\"适合傍晚去\"背后是日落+夜景+避开高峰）\n"
            "2. 识别具体实体：景点、餐厅、酒店、交通站点等\n"
            "3. 提炼概念标签：如错峰出行、预算控制、预约策略、夜景路线等\n"
            "4. 建立交叉引用：用 [[实体:xxx]]、[[概念:xxx]]、[[raw/xxx.md]] 语法\n"
            "5. 摘要必须包含：关键要点（bullet list）、实体清单、概念标签、隐含策略提示\n"
            "6. 为每个景点生成结构化知识卡片，字段如下：\n"
            "   - spot_name: 景点名称（尽量简短，如\"外滩\"而非\"上海外滩风景区\"）\n"
            "   - best_months: 推荐月份列表，如[\"3月\",\"4月\"]\n"
            "   - best_time: 具体推荐时段，含隐含信息，如\"傍晚至夜间（17:30-21:00），建议17:30占位\"\n"
            "   - booking_required: true/false\n"
            "   - booking_tip: 预约建议，如\"无需预约\"或\"提前3天在官方小程序预约\"\n"
            "   - transport_mode: metro/bus/taxi/walk/mixed\n"
            "   - transport_tip: 具体交通建议\n"
            "   - budget_level: low/medium/high\n"
            "   - crowd_level: low/medium/high\n"
            "   - crowd_tip: 人流提示，如\"节假日19:00-20:30极度拥挤\"\n"
            "   - duration_suggestion: 建议游玩时长，如\"2-3小时\"\n"
            "   - pitfalls: 避坑建议列表\n"
            "   - nearby: 附近关联景点列表\n"
            "   - llm_note: LLM 的额外洞察，如\"亮灯时间随季节变化，冬季约17:00，夏季约19:00\"\n"
            "\n"
            "输出必须是 JSON 对象，不要 markdown 代码围栏，格式如下：\n"
            '{\n'
            '  "summary": "Markdown 字符串",\n'
            '  "concepts": ["概念A", "概念B"],\n'
            '  "entities": ["实体A", "实体B"],\n'
            '  "cards": [\n'
            '    {"spot_name": "...", "best_time": "...", "booking_required": false, ...}\n'
            '  ]\n'
            '}'
        )

        truncated = raw_content[:8000]
        user = f"来源文件：{source_name}\n\n原始内容：\n{truncated}"
        raw = self._call(system, user, max_tokens=2500)
        stripped = self._strip_code_fence(raw)

        try:
            data = json.loads(stripped)
            cards = data.get("cards", [])
            clean_cards = []
            for card in cards:
                if isinstance(card, dict) and card.get("spot_name"):
                    clean_cards.append({
                        "spot_name": str(card.get("spot_name", "")).strip(),
                        "best_months": card.get("best_months", []),
                        "best_time": str(card.get("best_time", "")),
                        "booking_required": bool(card.get("booking_required", False)),
                        "booking_tip": str(card.get("booking_tip", "")),
                        "transport_mode": str(card.get("transport_mode", "mixed")),
                        "transport_tip": str(card.get("transport_tip", "")),
                        "budget_level": str(card.get("budget_level", "medium")),
                        "crowd_level": str(card.get("crowd_level", "medium")),
                        "crowd_tip": str(card.get("crowd_tip", "")),
                        "duration_suggestion": str(card.get("duration_suggestion", "1-3小时")),
                        "pitfalls": card.get("pitfalls", []),
                        "nearby": card.get("nearby", []),
                        "llm_note": str(card.get("llm_note", "")),
                    })
            return {
                "summary": str(data.get("summary", "")).strip(),
                "concepts": [str(c).strip() for c in data.get("concepts", []) if c],
                "entities": [str(e).strip() for e in data.get("entities", []) if e],
                "cards": clean_cards,
                "raw": raw,
            }
        except json.JSONDecodeError:
            return {
                "summary": stripped,
                "concepts": [],
                "entities": [],
                "cards": [],
                "raw": raw,
            }

    def answer_query(self, question: str, pages: list) -> dict:
        system = (
            "你是一个旅游知识库助手。基于提供的 Wiki 页面内容，为用户问题生成结构化、带引用的答案。\n"
            "要求：\n"
            "1. 用中文，语气务实\n"
            "2. 答案必须标注信息来源（如\"根据《上海攻略》…\"）\n"
            "3. 如果多个来源有冲突，指出冲突并给出建议\n"
            "4. 输出 Markdown 格式，不要 JSON\n"
            "5. 如果信息不足，明确说明\n"
            "6. 可以按天、按主题或按优先级组织答案结构"
        )

        context_parts = []
        for p in pages:
            src = p.get("source", "未知来源")
            ctx = p.get("content", "")[:2000]
            context_parts.append(f"【来源：{src}】\n{ctx}")

        context = "\n\n---\n\n".join(context_parts)
        user = f"问题：{question}\n\n相关 Wiki 页面内容：\n{context}"
        answer = self._call(system, user, max_tokens=2000)
        return {"answer": answer.strip(), "raw": answer}

    def lint_pages(self, pages: list) -> dict:
        system = (
            "你是一个 Wiki 健康检查助手。请检查提供的 Wiki 页面，发现问题。\n"
            "检查维度：\n"
            "1. 矛盾：不同页面对同一实体的描述是否冲突（如 A 说\"免费\"，B 说\"门票 100\"）\n"
            "2. 过时：是否有已关闭的景点、变化的票价、失效的交通信息\n"
            "3. 遗漏交叉引用：页面中提及了实体或概念，但没有用 [[...]] 建立链接\n"
            "4. 孤立页面：没有入链、没有被其他页面引用的页面\n"
            "5. 信息空白：明显缺失的关键信息（如只说\"提前预约\"但没给预约渠道）\n"
            "输出必须是 JSON，不要 markdown 代码围栏，格式：\n"
            '{\n'
            '  "issues": [\n'
            '    {"severity": "high", "page": "页面名或-", "description": "问题描述"}\n'
            '  ]\n'
            '}'
        )

        context_parts = []
        for p in pages:
            name = p.get("name", "未命名")
            ctx = p.get("content", "")[:1500]
            context_parts.append(f"【{name}】\n{ctx}")

        context = "\n\n---\n\n".join(context_parts)
        user = f"请检查以下 Wiki 页面：\n{context}"
        raw = self._call(system, user, max_tokens=2000)
        stripped = self._strip_code_fence(raw)

        try:
            data = json.loads(stripped)
            issues = data.get("issues", [])
            clean_issues = []
            for issue in issues:
                if isinstance(issue, dict):
                    clean_issues.append({
                        "severity": str(issue.get("severity", "medium")).lower(),
                        "page": str(issue.get("page", "-")).strip() or "-",
                        "description": str(issue.get("description", "")).strip(),
                    })
            return {"issues": clean_issues, "raw": raw}
        except json.JSONDecodeError:
            return {
                "issues": [{"severity": "medium", "page": "-", "description": stripped[:500] or "LLM 输出无法解析"}],
                "raw": raw,
            }
