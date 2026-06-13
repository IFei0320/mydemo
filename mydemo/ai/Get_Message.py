import json
import os

from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

_SEASON_CN = {
    "spring": "春季",
    "summer": "夏季",
    "autumn": "秋季",
    "winter": "冬季",
}


class Get_DeepSeek:
    def __init__(self, model: str = "deepseek-v4-flash"):
        self.model = model
        self.client = OpenAI(
            api_key=os.getenv('LLM_API_KEY'),
            base_url="https://api.deepseek.com",
        )

    _overview_system_prompt = (
        "你是资深旅行顾问。用户在做攻略前需要「目的地速览」，不是具体每天的游玩排程。"
        "要求："
        "1) 用中文，语气务实；"
        "2) 说明该城市/目的地大致有哪些类型的去处（历史、自然、亲子、商圈等），偏概括，不要罗列成日程表；"
        "3) 结合用户给出的季节、天数与预算，写「行前注意什么」：交通、预约、穿衣、错峰、消费与常见坑；"
        "4) 不要输出 Markdown 表格，不要输出景点经纬度，不要按「第几天上午下午」排行程；"
        "5) 只输出一个 JSON 对象（不要用 markdown 代码围栏），严格符合下列键（缺失则给空数组或空字符串）："
        '{"city_summary":"","what_to_see":[],"watchouts":[],"regions":[]}'
        "其中 regions 为对象数组，每项含 title（片区或主题名）、blurb（一两句提示）。"
    )

    @staticmethod
    def _strip_code_fence(text: str) -> str: # text or "": 如果 text 是 None 或者空字符串，就把它变成空字符串 ""，防止报错
        t = (text or "").strip()
        if t.startswith("```"):   # 检查清理后的文本 t 是否以三个反引号 ``` 开头。
            lines = t.split("\n")     # 将文本按换行符 "\n" 分割成列表 lines。
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            t = "\n".join(lines).strip()
        return t

    def get_city_travel_overview(
        self, city: str, season: str, budget: str, days: str
    ) -> dict:
        raw = ""
        try:
            season_cn = _SEASON_CN.get(str(season).strip(), str(season))   # .get(..., ...): 如果字典里有这个季节，返回中文名；如果没有，就返回原样。
            user_msg = (
                f"目的地：{city}；季节：{season_cn}；大致行程长度：{days} 天；预算：{budget}。\n"
                "请只返回 JSON，键为 city_summary、what_to_see、watchouts、regions。"
            )
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._overview_system_prompt},
                    {"role": "user", "content": user_msg},
                ],
                stream=False,
                max_tokens=1400,
                extra_body={"thinking": {"type": "disabled"}},
            )
            raw = response.choices[0].message.content or ""
            stripped = self._strip_code_fence(raw)     # 调用上面定义的辅助方法，去掉 raw 中的 ``` 标记。
            data = json.loads(stripped)      # json.loads(): 尝试将清洗后的字符串解析为 Python 字典/列表。
            overview = {       # 创建一个新字典 overview，从解析出的 data 中提取对应字段。
                "city_summary": str(data.get("city_summary") or "").strip(),
                "what_to_see": data.get("what_to_see") or [],
                "watchouts": data.get("watchouts") or [],
                "regions": data.get("regions") or [],
            }
            if not isinstance(overview["what_to_see"], list):
                overview["what_to_see"] = []
            if not isinstance(overview["watchouts"], list):
                overview["watchouts"] = []
            if not isinstance(overview["regions"], list):
                overview["regions"] = []
            overview["what_to_see"] = [str(x).strip() for x in overview["what_to_see"] if str(x).strip()]
            overview["watchouts"] = [str(x).strip() for x in overview["watchouts"] if str(x).strip()]
            clean_regions = []
            for r in overview["regions"]:
                if isinstance(r, dict):
                    title = str(r.get("title") or "").strip()
                    blurb = str(r.get("blurb") or r.get("tips") or "").strip()
                    if title or blurb:
                        clean_regions.append({"title": title, "blurb": blurb})
            overview["regions"] = clean_regions
            return {"code": 200, "overview": overview, "raw": raw}
        except json.JSONDecodeError as e:
            fallback = {
                "city_summary": (raw or "")[:800],
                "what_to_see": [],
                "watchouts": [],
                "regions": [],
                "parse_note": f"模型输出未能解析为 JSON，已展示节选原文。技术信息：{e}",
            }
            return {"code": 200, "overview": fallback, "raw": raw}
        except Exception as e:
            return {"code": 500, "message": str(e), "raw": raw}
