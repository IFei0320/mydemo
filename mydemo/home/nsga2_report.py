import html  
import os  
import re 
from typing import Dict, List                               # 导入类型提示，用于函数参数和返回值类型声明
from openai import OpenAI  
from dotenv import load_dotenv                             # 导入dotenv模块，用于加载.env文件中的环境变量
from pathlib import Path  

from django.template.loader import render_to_string        # 导入Django模板渲染函数，用于生成HTML报告

from home.config import AI_BASE_URL, AI_MAX_TOKENS, AI_MODEL  # 导入AI配置常量：API基础URL、最大token数、模型名称
from home.data_utils import (  # 导入数据处理工具函数
    _safe_float,
    assess_feasibility,
    compute_living_budget,
    get_city_tier,
)

BASE_DIR = Path(__file__).resolve().parent.parent 
load_dotenv(BASE_DIR / '.env')                                    # 加载项目根目录下的.env文件中的环境变量


def _calc_budget_context(city: str, days: int, budget: float, route_data: List[Dict]) -> Dict:  # 统一计算预算上下文：门票实际 + 食宿交通预估 + 可行性
    """统一计算预算上下文：门票实际 + 食宿交通预估 + 可行性。"""
    ticket_cost = 0.0  # 初始化门票总成本为0
    for item in (route_data or []):  # 遍历路线数据中的每个景点
        ticket_cost += _safe_float(item.get("estimated_cost", "免费"), 0.0)  # 累加每个景点的预计花费（安全转换为浮点数）
    tier = get_city_tier(city)  # 获取城市的消费档位（H/M/L）
    living = compute_living_budget(tier, days)  # 计算该城市的生活预算（餐饮+住宿+交通）
    total_estimate = ticket_cost + living["total_living"]  # 计算总预估费用（门票 + 生活成本）
    feasibility = assess_feasibility(budget, total_estimate)  # 评估预算可行性（充足/偏紧/不足）
    return {  # 返回预算上下文字典
        "ticket_cost": ticket_cost,  # 门票总成本
        "tier": tier,  # 城市消费档位
        "living": living,  # 生活预算详情
        "total_estimate": total_estimate,  # 总预估费用
        "feasibility": feasibility,  # 可行性评估结果
    }


def generate_ai_summary(                                        # 生成AI文本摘要的主函数
    city: str,
    season: str,
    days: int,
    budget: float,
    route_data: List[Dict],
    knowledge_cards: List[Dict],
) -> str:
    ctx = _calc_budget_context(city, days, budget, route_data)     # 计算预算上下文
    ticket_cost = ctx["ticket_cost"]                               # 提取门票成本
    tier = ctx["tier"]                                                 # 提取城市档位
    living = ctx["living"]                                        # 提取生活预算
    total_estimate = ctx["total_estimate"]                           # 提取总预估费用
    feasibility = ctx["feasibility"]                              # 提取可行性评估

    system_prompt = (                                          # 定义系统提示，指导AI生成旅游攻略
        "你是资深旅游策划师。请基于给定的结构化行程，输出详细攻略。"
        "要求：1) 按天分段；2) 每个景点说明亮点与游玩建议；3) 给出交通衔接建议；"
        "4) 根据提供的预算数据给出食宿交通花费提醒——直接引用我给你的数字，不要自己编造；"
        "5) 当 feasibility 为 insufficient 时，明确指出：门票预算不足以覆盖全程（门票+食宿），"
        "需额外预留食宿交通费用，给出具体建议（默认过夜游含住宿）；"
        "6) 用中文，结构清晰，纯文本，不要 Markdown/星号/表格线；"
        "7) 优先融入本地知识卡（RAG）中的最佳时段、预约提示、避坑点。"
    )
    user_content = {                                             # 构建用户内容字典，包含所有需要传递给AI的信息
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
        "route": route_data,  # 路线数据
        "local_knowledge_cards": knowledge_cards,  # 本地知识卡片
    }

    try:                                                              # 尝试调用AI API生成摘要
        client = OpenAI(                                              # 创建OpenAI客户端实例
            api_key=os.getenv('LLM_API_KEY'),                        # 从环境变量获取API密钥
            base_url=os.getenv('LLM_BASE_URL', AI_BASE_URL),         # 从环境变量获取API基础URL，如果不存在则使用默认值
        )
        response = client.chat.completions.create(  
            model=AI_MODEL,  
            messages=[  
                {"role": "system", "content": system_prompt},            # 系统提示消息
                {"role": "user", "content": str(user_content)},           # 用户内容消息（转换为字符串）
            ],
            max_tokens=AI_MAX_TOKENS,  
            stream=False,  
            extra_body={"thinking": {"type": "disabled"}}, 
        )
        return response.choices[0].message.content or ""             # 返回AI生成的内容，如果为空则返回空字符串
    except Exception as exc:  # 捕获所有异常
        err = str(exc)  
        if "Connection" in err or "timeout" in err or "connect" in err.lower():  
            hint = "（网络不通：请检查 VPN 是否已开启，或 DeepSeek API 是否可达）"
        elif "api_key" in err.lower() or "auth" in err.lower() or "401" in err or "403" in err: 
            hint = "（API 密钥无效或过期，请检查 .env 中 LLM_API_KEY）"
        elif "insufficient" in err.lower() or "balance" in err.lower() or "402" in err: 
            hint = "（API 余额不足，请充值）"
        else:  # 其他未知错误
            hint = "（请检查网络连接，若已开启 VPN 请确认节点可用）"
        return f"AI润色暂时不可用。{hint} 原始错误：{err}" 


def generate_html_report(                                           # 生成HTML报告的主函数
    city: str,
    season: str,
    days: int,
    budget: float,
    route_data: List[Dict],
    metrics: Dict,
    knowledge_cards: List[Dict],
) -> str:
    route_data = route_data or []                                      # 确保路线数据不为None
    metrics = metrics or {}                                           # 确保指标数据不为None
    knowledge_cards = knowledge_cards or []                               # 确保知识卡片不为None

    ctx = _calc_budget_context(city, days, budget, route_data)          # 计算预算上下文
    ticket_cost = ctx["ticket_cost"]                                       # 提取门票成本
    tier = ctx["tier"]                                                      # 提取城市消费档位（修复：之前遗漏了这行）
    living = ctx["living"]                                                # 提取生活预算
    total_estimate = ctx["total_estimate"]                                  # 提取总预估费用
    feasibility = ctx["feasibility"]                                           # 提取可行性评估

    day_groups: Dict[int, List[Dict]] = {}                                   # 创建按天分组的字典
    for row in route_data:                                                             # 遍历路线数据
        match = re.search(r"第(\d+)天", str(row.get("visit_time", "")))  # 使用正则表达式提取天数信息
        day_no = int(match.group(1)) if match else 1                     # 提取天数，如果没有匹配则默认为第1天
        day_groups.setdefault(day_no, []).append(row)                           # 将景点添加到对应天数的分组中

    day_cards_html = []                                                         # 存储每天的HTML卡片
    day_budget_rows = []                                                        # 存储每日预算表格行
    total_cost = 0.0                                                              # 初始化总成本
    traffic_rows = []                                                               # 存储交通建议行
    for day_no in sorted(day_groups.keys()):                                             # 按天数顺序遍历
        items = day_groups[day_no]                                                           # 获取当天的所有景点
        row_html = []                                                                      # 存储当天景点的HTML
        day_cost = 0.0                                                                           # 初始化当天成本
        for i, item in enumerate(items):                                                    # 遍历当天的每个景点
            spot_name = html.escape(str(item.get("name", "")))                                   # 获取并转义景点名称
            visit_time = html.escape(str(item.get("visit_time", "")))                          # 获取并转义访问时间
            features = html.escape(str(item.get("features", "")))                             # 获取并转义特色描述
            estimated_cost = str(item.get("estimated_cost", "免费"))                                 # 获取预计花费
            amount = _safe_float(estimated_cost, 0.0)                                                       # 安全转换为浮点数
            day_cost += amount                                                                            # 累加到当天成本
            total_cost += amount                                                                          # 累加到总成本
            lon = item.get("longitude", "")  
            lat = item.get("latitude", "") 
            row_html.append(  # 添加景点卡片HTML
                f"""
                <div class=\"spot-card\">\n                    <div class=\"spot-title\">{spot_name}</div>\n                    <div class=\"spot-meta\">{visit_time}</div>\n                    <div class=\"spot-desc\">{features}</div>\n                    <div class=\"spot-line\"><b>建议停留：</b>1-2小时</div>\n                    <div class=\"spot-line\"><b>预计花费：</b>{html.escape(estimated_cost)}</div>\n                    <div class=\"spot-line\"><b>坐标：</b>{html.escape(str(lat))}, {html.escape(str(lon))}</div>\n                </div>
                """
            )
            if i < len(items) - 1:  # 如果不是最后一个景点
                from_name = html.escape(str(item.get("name", "")))  # 获取当前景点名称
                to_name = html.escape(str(items[i + 1].get("name", "")))  # 获取下一个景点名称
                traffic_rows.append(  # 添加交通建议HTML
                    f"<li><b>{from_name}</b> -> <b>{to_name}</b>：建议优先地铁/公交，若时间紧可打车；以地图App实时导航为准。</li>"
                )
        day_cards_html.append(  # 添加当天行程区块HTML
            f"""
            <section class=\"day-block\">\n              <h3>第{day_no}天行程</h3>\n              <div class=\"spot-grid\">{''.join(row_html)}</div>\n              <div class=\"day-summary\">当日小结：建议先完成核心景点，再安排拍照/休息时段，避免反复折返。</div>\n            </section>
            """
        )
        day_budget_rows.append(f"<tr><td>第{day_no}天</td><td>{day_cost:.2f} 元</td></tr>")  # 添加当天预算表格行

    budget_usage = (total_cost / budget * 100.0) if budget > 0 else 0.0  # 计算预算使用百分比
    risk_text = "预算充足" if (budget <= 0 or total_cost <= budget) else "存在超支风险"  # 判断预算风险状态

    knowledge_html = []  # 存储知识卡片HTML
    for card in knowledge_cards[:12]:  # 遍历前12个知识卡片
        pitfalls = card.get("pitfalls", []) or []  # 获取避坑要点列表
        pitfalls_text = "；".join(html.escape(str(p)) for p in pitfalls[:3]) if pitfalls else "建议以现场提示为准"  # 格式化避坑要点（最多3条）
        knowledge_html.append(  # 添加知识卡片HTML
            f"""
            <div class=\"knowledge-item\">\n              <div class=\"knowledge-title\">{html.escape(str(card.get('spot_name', '')))}</div>\n              <div>最佳时段：{html.escape(str(card.get('best_time', '-')))}</div>\n              <div>预约提示：{html.escape(str(card.get('booking_tip', '-')))}</div>\n              <div>避坑要点：{pitfalls_text}</div>\n            </div>
            """
        )

    traffic_html = "".join(traffic_rows) if traffic_rows else "<li>建议以地铁优先，跨区段可打车衔接，以导航实时路况为准。</li>"  # 拼接交通建议HTML，如果没有则使用默认提示
    knowledge_section = (  # 构建知识卡片区块HTML
        f"<div class='knowledge-box'>{''.join(knowledge_html)}</div>"
        if knowledge_html
        else "<p class='muted'>本次未命中本地知识卡，建议以官方公告与地图App信息为准。</p>"
    )

    risk_class = "risk-ok" if risk_text == "预算充足" else "risk-warn"  # 根据风险状态设置CSS类名

    context = {  # 构建模板上下文字典
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
        "hotel_per_night": living["hotel_per_night"],  # 每晚住宿费用
        "transport_per_day": living["transport_per_day"],  # 每日交通费用
        "feasibility": feasibility,  # 可行性评估结果
        "total_estimate": round(total_estimate),  # 总预估费用（四舍五入）
    }
    return render_to_string("ksh/nsga2_report.html", context)  # 渲染HTML模板并返回结果