import html
import re
from typing import Dict, List

from openai import OpenAI


def _safe_float(raw_value, default=0.0) -> float:
    if raw_value is None:
        return default
    value = str(raw_value).strip()
    if not value:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        digits = re.findall(r"-?\d+\.?\d*", value)
        if digits:
            try:
                return float(digits[0])
            except ValueError:
                return default
    return default


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
            api_key="sk-d2e0034a6f264140a8017b1e98359312",
            base_url="https://api.deepseek.com",
        )
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": str(user_content)},
            ],
            max_tokens=1200,
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

    return f"""<!doctype html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{html.escape(city)} 行程报告</title>
  <style>
    body {{ font-family: -apple-system,BlinkMacSystemFont,\"Segoe UI\",Arial,sans-serif; margin:0; background:#f5f7fb; color:#1f2937; }}
    .wrap {{ max-width: 1080px; margin: 24px auto; padding: 0 16px; }}
    .header {{ background:#fff; border-radius:12px; padding:18px 20px; box-shadow:0 2px 10px rgba(0,0,0,.06); }}
    h1 {{ margin:0 0 8px; font-size:24px; }}
    .sub {{ color:#6b7280; margin:0; }}
    .grid {{ display:grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap:12px; margin-top:14px; }}
    .card {{ background:#fff; border-radius:12px; padding:14px; box-shadow:0 2px 10px rgba(0,0,0,.05); }}
    .k {{ color:#6b7280; font-size:13px; }}
    .v {{ font-size:18px; font-weight:700; margin-top:4px; }}
    .section {{ background:#fff; border-radius:12px; padding:16px; box-shadow:0 2px 10px rgba(0,0,0,.05); margin-top:14px; }}
    .section h2 {{ margin:0 0 10px; font-size:19px; color:#1677ff; }}
    .day-block {{ border:1px solid #e5e7eb; border-radius:10px; padding:12px; margin-top:10px; }}
    .day-block h3 {{ margin:0 0 8px; font-size:17px; }}
    .spot-grid {{ display:grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap:10px; }}
    .spot-card {{ border:1px solid #e5e7eb; border-radius:8px; padding:10px; background:#fafcff; }}
    .spot-title {{ font-weight:700; margin-bottom:4px; }}
    .spot-meta {{ color:#2563eb; font-size:13px; margin-bottom:6px; }}
    .spot-desc {{ font-size:13px; margin-bottom:6px; }}
    .spot-line {{ font-size:13px; color:#374151; }}
    .day-summary {{ margin-top:8px; color:#374151; font-size:13px; }}
    ul {{ margin:8px 0 0 18px; padding:0; }}
    li {{ margin:6px 0; }}
    table {{ width:100%; border-collapse:collapse; }}
    th, td {{ border:1px solid #e5e7eb; padding:8px 10px; text-align:left; }}
    th {{ background:#f3f4f6; }}
    .risk-ok {{ color:#16a34a; font-weight:700; }}
    .risk-warn {{ color:#dc2626; font-weight:700; }}
    .knowledge-box {{ display:grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap:10px; }}
    .knowledge-item {{ border:1px solid #e5e7eb; border-radius:8px; padding:10px; background:#fffdf7; }}
    .knowledge-title {{ font-weight:700; margin-bottom:4px; }}
    .muted {{ color:#6b7280; }}
    @media (max-width: 900px) {{ .grid, .spot-grid, .knowledge-box {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <div class=\"wrap\">
    <div class=\"header\">
      <h1>{html.escape(city)} {html.escape(season)}出行报告</h1>
      <p class=\"sub\">基于NSGA-II多目标优化 + 本地知识库RAG增强，适合答辩展示与落地执行。</p>
      <div class=\"grid\">
        <div class=\"card\"><div class=\"k\">城市</div><div class=\"v\">{html.escape(city)}</div></div>
        <div class=\"card\"><div class=\"k\">季节</div><div class=\"v\">{html.escape(season)}</div></div>
        <div class=\"card\"><div class=\"k\">天数</div><div class=\"v\">{days} 天</div></div>
        <div class=\"card\"><div class=\"k\">预算</div><div class=\"v\">{budget:.2f} 元</div></div>
        <div class=\"card\"><div class=\"k\">预计花费</div><div class=\"v\">{total_cost:.2f} 元</div></div>
        <div class=\"card\"><div class=\"k\">景点数</div><div class=\"v\">{len(route_data)} 个</div></div>
      </div>
    </div>

    <div class=\"section\">
      <h2>行程总览摘要</h2>
      <p>策略：在预算约束下平衡评分、热度与路程，优先保证核心景点覆盖，再优化交通衔接与体验节奏。</p>
      {''.join(day_cards_html)}
    </div>

    <div class=\"section\">
      <h2>交通衔接建议</h2>
      <ul>{traffic_html}</ul>
    </div>

    <div class=\"section\">
      <h2>RAG本地知识卡（命中 {len(knowledge_cards)} 条）</h2>
      {knowledge_section}
    </div>

    <div class=\"section\">
      <h2>注意事项</h2>
      <ul>
        <li>天气与穿搭：春秋季昼夜温差较大，建议叠穿并备轻薄外套。</li>
        <li>预约与排队：热门场馆优先预约，尽量错峰（早场/工作日）。</li>
        <li>财物安全：在人流密集区域注意随身物品，手机与证件分开存放。</li>
        <li>文明游览：遵守景区秩序，拍照时避免影响他人通行。</li>
        <li>导航建议：交通与开放信息可能变化，出发前请以官方公告和地图App实时信息为准。</li>
      </ul>
    </div>

    <div class=\"section\">
      <h2>预算明细</h2>
      <table>
        <thead><tr><th>日期</th><th>预计花费</th></tr></thead>
        <tbody>{''.join(day_budget_rows)}</tbody>
      </table>
      <p style=\"margin-top:10px;\">
        总计：<b>{total_cost:.2f} 元</b>，
        预算利用率：<b>{budget_usage:.1f}%</b>，
        风险评估：<span class=\"{'risk-ok' if risk_text == '预算充足' else 'risk-warn'}\">{risk_text}</span>
      </p>
    </div>

    <div class=\"section\">
      <h2>应急与备选方案</h2>
      <ul>
        <li>雨天：优先博物馆/商圈/室内观景点，户外点顺延到次日。</li>
        <li>拥堵：跨区移动改为地铁优先，压缩非核心打卡点。</li>
        <li>超支：减少高票价项目，增加免费景点与步行线路。</li>
      </ul>
    </div>

    <div class=\"section\">
      <h2>出发前清单</h2>
      <ul>
        <li>证件：身份证、学生证/优惠证件</li>
        <li>设备：充电宝、充电线、耳机</li>
        <li>行前：门票预约截图、酒店/交通订单截图</li>
        <li>工具：离线地图、应急联系人、常用药品</li>
      </ul>
    </div>
  </div>
</body>
</html>"""
