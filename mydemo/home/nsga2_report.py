import html
import os
import re
from typing import Dict, List
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path

from django.template.loader import render_to_string

from home.data_utils import _safe_float

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

def call_ai_refiner(
    city: str,
    season: str,
    days: int,
    budget: float,
    route_data: List[Dict],
    knowledge_cards: List[Dict],
) -> str:
    prompt = (
        "你是资深旅游策划师。请基于给定的结构化行程，输出详细攻略。"
        "要求：1) 按天分段；2) 每个景点说明亮点与游玩建议；3) 给出交通衔接建议；"
        "4) 给出预算提醒和避坑建议；5) 用中文，结构清晰；"
        "6) 只输出纯文本，不要 Markdown，不要星号，不要表格线；"
        "7) 优先使用我提供的“本地知识卡（RAG）”，把最佳时段、预约提示、避坑点融入内容。"
    )
    user_content = {
        "city": city,
        "season": season,
        "days": days,
        "budget": budget,
        "route": route_data,
        "local_knowledge_cards": knowledge_cards,
    }

    try:
        client = OpenAI(
            api_key=os.getenv('LLM_API_KEY'),
            base_url=os.getenv('LLM_BASE_URL', 'https://api.deepseek.com'),
        )
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": str(user_content)},
            ],
            max_tokens=3200,
            stream=False,
            extra_body={"thinking": {"type": "disabled"}},
        )
        return response.choices[0].message.content or ""
    except Exception as exc:
        return f"AI润色暂时不可用，已返回算法行程结果。错误信息：{exc}"


def call_ai_html_report(
    city: str,
    season: str,
    days: int,
    budget: float,
    route_data: List[Dict],
    metrics: Dict,
    knowledge_cards: List[Dict],
) -> str:
    route_data = route_data or []
    metrics = metrics or {}
    knowledge_cards = knowledge_cards or []

    day_groups: Dict[int, List[Dict]] = {}
    for row in route_data:
        match = re.search(r"第(\d+)天", str(row.get("visit_time", "")))
        day_no = int(match.group(1)) if match else 1
        day_groups.setdefault(day_no, []).append(row)

    day_cards_html = []
    day_budget_rows = []
    total_cost = 0.0
    traffic_rows = []
    for day_no in sorted(day_groups.keys()):
        items = day_groups[day_no]
        row_html = []
        day_cost = 0.0
        for i, item in enumerate(items):
            spot_name = html.escape(str(item.get("name", "")))
            visit_time = html.escape(str(item.get("visit_time", "")))
            features = html.escape(str(item.get("features", "")))
            estimated_cost = str(item.get("estimated_cost", "免费"))
            amount = _safe_float(estimated_cost, 0.0)
            day_cost += amount
            total_cost += amount
            lon = item.get("longitude", "")
            lat = item.get("latitude", "")
            row_html.append(
                f"""
                <div class=\"spot-card\">\n                    <div class=\"spot-title\">{spot_name}</div>\n                    <div class=\"spot-meta\">{visit_time}</div>\n                    <div class=\"spot-desc\">{features}</div>\n                    <div class=\"spot-line\"><b>建议停留：</b>1-2小时</div>\n                    <div class=\"spot-line\"><b>预计花费：</b>{html.escape(estimated_cost)}</div>\n                    <div class=\"spot-line\"><b>坐标：</b>{html.escape(str(lat))}, {html.escape(str(lon))}</div>\n                </div>
                """
            )
            if i < len(items) - 1:
                from_name = html.escape(str(item.get("name", "")))
                to_name = html.escape(str(items[i + 1].get("name", "")))
                traffic_rows.append(
                    f"<li><b>{from_name}</b> -> <b>{to_name}</b>：建议优先地铁/公交，若时间紧可打车；以地图App实时导航为准。</li>"
                )
        day_cards_html.append(
            f"""
            <section class=\"day-block\">\n              <h3>第{day_no}天行程</h3>\n              <div class=\"spot-grid\">{''.join(row_html)}</div>\n              <div class=\"day-summary\">当日小结：建议先完成核心景点，再安排拍照/休息时段，避免反复折返。</div>\n            </section>
            """
        )
        day_budget_rows.append(f"<tr><td>第{day_no}天</td><td>{day_cost:.2f} 元</td></tr>")

    budget_usage = (total_cost / budget * 100.0) if budget > 0 else 0.0
    risk_text = "预算充足" if (budget <= 0 or total_cost <= budget) else "存在超支风险"

    knowledge_html = []
    for card in knowledge_cards[:12]:
        pitfalls = card.get("pitfalls", []) or []
        pitfalls_text = "；".join(html.escape(str(p)) for p in pitfalls[:3]) if pitfalls else "建议以现场提示为准"
        knowledge_html.append(
            f"""
            <div class=\"knowledge-item\">\n              <div class=\"knowledge-title\">{html.escape(str(card.get('spot_name', '')))}</div>\n              <div>最佳时段：{html.escape(str(card.get('best_time', '-')))}</div>\n              <div>预约提示：{html.escape(str(card.get('booking_tip', '-')))}</div>\n              <div>避坑要点：{pitfalls_text}</div>\n            </div>
            """
        )

    traffic_html = "".join(traffic_rows) if traffic_rows else "<li>建议以地铁优先，跨区段可打车衔接，以导航实时路况为准。</li>"
    knowledge_section = (
        f"<div class='knowledge-box'>{''.join(knowledge_html)}</div>"
        if knowledge_html
        else "<p class='muted'>本次未命中本地知识卡，建议以官方公告与地图App信息为准。</p>"
    )

    risk_class = "risk-ok" if risk_text == "预算充足" else "risk-warn"

    context = {
        "city": city,
        "season": season,
        "days": days,
        "budget": budget,
        "total_cost": total_cost,
        "spot_count": len(route_data),
        "day_cards_html": "".join(day_cards_html),
        "traffic_html": traffic_html,
        "knowledge_count": len(knowledge_cards),
        "knowledge_section": knowledge_section,
        "day_budget_rows": "".join(day_budget_rows),
        "budget_usage": budget_usage,
        "risk_class": risk_class,
        "risk_text": risk_text,
    }
    return render_to_string("ksh/nsga2_report.html", context)
