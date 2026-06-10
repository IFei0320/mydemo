import html
import os
import re
from typing import Dict, List
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path

from django.template.loader import render_to_string

from home.config import AI_MAX_TOKENS, AI_MODEL
from home.data_utils import (
    _safe_float,
    assess_feasibility,
    compute_living_budget,
    get_city_tier,
)

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

def generate_ai_summary(
    city: str,
    season: str,
    days: int,
    budget: float,
    route_data: List[Dict],
    knowledge_cards: List[Dict],
) -> str:
    # 计算：门票预算 vs（门票实际 + 食宿交通预估）
    ticket_cost = 0.0
    for item in (route_data or []):
        ticket_cost += _safe_float(item.get("estimated_cost", "免费"), 0.0)
    tier = get_city_tier(city)
    living = compute_living_budget(tier, days)
    total_estimate = ticket_cost + living["total_living"]
    feasibility = assess_feasibility(budget, total_estimate)

    system_prompt = (
        "你是资深旅游策划师。请基于给定的结构化行程，输出详细攻略。"
        "要求：1) 按天分段；2) 每个景点说明亮点与游玩建议；3) 给出交通衔接建议；"
        "4) 根据提供的预算数据给出食宿交通花费提醒——直接引用我给你的数字，不要自己编造；"
        "5) 当 feasibility 为 insufficient 时，明确指出：门票预算不足以覆盖全程（门票+食宿），"
        "需额外预留食宿交通费用，给出具体建议（默认过夜游含住宿）；"
        "6) 用中文，结构清晰，纯文本，不要 Markdown/星号/表格线；"
        "7) 优先融入本地知识卡（RAG）中的最佳时段、预约提示、避坑点。"
    )
    user_content = {
        "city": city,
        "season": season,
        "days": days,
        "门票预算": f"{budget:.0f} 元（用户只规划了门票开支）",
        "门票实际": f"{ticket_cost:.0f} 元（NSGA-II 算法优化结果）",
        "城市消费档位": f"{tier}档（{living['tier_label']}）",
        "食宿交通参考": (
            f"约 {living['total_living']:.0f} 元（{days}天过夜游，"
            f"餐 {living['meal_per_meal']}元/顿×2.5顿 + 行 {living['transport_per_day']}元/天"
            + (f" + 住 {living['hotel_per_night']}元/晚×{living['hotel_nights']}晚" if living['hotel_nights'] > 0 else "")
            + "）"
        ),
        "全程预估合计": f"约 {total_estimate:.0f} 元（门票 + 食宿交通）",
        "可行性": feasibility["label"],
        "差距": f"{feasibility['gap']:.0f} 元" if feasibility["gap"] < 0 else "门票预算内可覆盖",
        "提示": (
            "全程预估已超出门票预算，请提醒用户：门票之外还需预留食宿交通费用。"
            if feasibility["level"] == "insufficient" else
            "门票预算偏紧，食宿交通需精打细算。"
            if feasibility["level"] == "tight" else
            "门票预算较充裕，食宿交通可按正常水平安排。"
        ),
        "route": route_data,
        "local_knowledge_cards": knowledge_cards,
    }

    try:
        client = OpenAI(
            api_key=os.getenv('LLM_API_KEY'),
            base_url=os.getenv('LLM_BASE_URL', 'https://api.deepseek.com'),
        )
        response = client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": str(user_content)},
            ],
            max_tokens=AI_MAX_TOKENS,
            stream=False,
            extra_body={"thinking": {"type": "disabled"}},
        )
        return response.choices[0].message.content or ""
    except Exception as exc:
        err = str(exc)
        if "Connection" in err or "timeout" in err or "connect" in err.lower():
            hint = "（网络不通：请检查 VPN 是否已开启，或 DeepSeek API 是否可达）"
        elif "api_key" in err.lower() or "auth" in err.lower() or "401" in err or "403" in err:
            hint = "（API 密钥无效或过期，请检查 .env 中 LLM_API_KEY）"
        elif "insufficient" in err.lower() or "balance" in err.lower() or "402" in err:
            hint = "（API 余额不足，请充值）"
        else:
            hint = "（请检查网络连接，若已开启 VPN 请确认节点可用）"
        return f"AI润色暂时不可用。{hint} 原始错误：{err}"


def generate_html_report(
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

    # 计算预算可行性：门票预算 vs（门票实际 + 食宿交通预估）
    ticket_cost = 0.0
    for item in route_data:
        ticket_cost += _safe_float(item.get("estimated_cost", "免费"), 0.0)
    tier = get_city_tier(city)
    living = compute_living_budget(tier, days)
    total_estimate = ticket_cost + living["total_living"]
    feasibility = assess_feasibility(budget, total_estimate)

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
        "ticket_cost": round(ticket_cost),
        "spot_count": len(route_data),
        "day_cards_html": "".join(day_cards_html),
        "traffic_html": traffic_html,
        "knowledge_count": len(knowledge_cards),
        "knowledge_section": knowledge_section,
        "day_budget_rows": "".join(day_budget_rows),
        "budget_usage": budget_usage,
        "risk_class": risk_class,
        "risk_text": risk_text,
        # 预算可行性数据
        "tier": tier,
        "tier_label": living["tier_label"],
        "daily_living": living["daily_living"],
        "total_living": living["total_living"],
        "hotel_nights": living["hotel_nights"],
        "meal_per_meal": living["meal_per_meal"],
        "hotel_per_night": living["hotel_per_night"],
        "transport_per_day": living["transport_per_day"],
        "feasibility": feasibility,
        "total_estimate": round(total_estimate),
    }
    return render_to_string("ksh/nsga2_report.html", context)
