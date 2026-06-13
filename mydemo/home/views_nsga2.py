import json                                                                    # 导入JSON处理模块，用于解析和生成JSON数据
import time                                                                     # 导入时间模块，用于处理时间戳和缓存过期
import uuid                                                                    # 导入UUID模块，用于生成唯一标识符

from django.http import JsonResponse  
from django.shortcuts import render 
from django.views.decorators.http import require_POST                         # 导入装饰器，限制视图函数只接受POST请求

from home.config import (                                                     # 导入配置常量，包括默认敏感度、权重参数、缓存时间等
    DEFAULT_SENSITIVITY,
    EXPERIENCE_HOTNESS_WEIGHT,
    EXPERIENCE_RATING_WEIGHT,
    PLAN_CACHE_TTL,
    RECENT_PLAN_LIMIT,
    STYLE_LABELS,
    VALID_SEASONS,
) 
from home.nsga2_knowledge import retrieve_knowledge_cards                   # 导入知识卡片检索功能
from home.nsga2_report import generate_ai_summary, generate_html_report     # 导入AI摘要和HTML报告生成功能
from home.nsga2_trip_planner import (                                       # 导入NSGA2旅行规划的核心功能函数
    build_candidates,
    build_route_payload,
    choose_solution,
    run_nsga2,
)
from home.data_utils import (                                              # 导入数据工具函数，用于可行性评估、预算计算等
    assess_feasibility,
    compute_living_budget,
    get_city_tier,
)
from home.wiki_service import retrieve_wiki_knowledge_cards                # 导入Wiki知识卡片检索服务
from utils.decorators import login_required_custom                          # 导入自定义登录装饰器

PLAN_CACHE = {}                                                              # 全局变量：存储计划缓存的字典，用于避免重复计算相同请求
RECENT_PLANS = []                                                           # 全局变量：存储最近计划的列表，用于在页面上显示历史记录


@login_required_custom  
def ai_nsga2_route_page(request):
    return render(request, 'ksh/ai_nsga2_route.html')                          # 渲染AI NSGA2路线规划页面


@login_required_custom 
def get_recent_plans(request):
    """页面加载时获取缓存列表"""
    _cleanup_plan_cache()                                                            # 清理过期的计划缓存，释放内存
    return JsonResponse({"code": 200, "data": {"recent_plans": RECENT_PLANS[:6]}})  # 返回JSON响应，包含最近6个计划


def _cleanup_plan_cache():                                                               # 私有函数：清理过期的计划缓存
    now = time.time()                                                                    # 获取当前时间戳（秒）
    expired = [token for token, value in PLAN_CACHE.items() if value.get("expires_at", 0) < now]  # 找出所有已过期的缓存项（过期时间小于当前时间）
    for token in expired:                                                                 # 遍历所有过期项
        PLAN_CACHE.pop(token, None)                                                         # 从缓存字典中移除过期项


def _calc_advantage_label(option):                                                          # 私有函数：根据选项风格计算优势标签
    return STYLE_LABELS.get(option.get("style"), STYLE_LABELS["balanced"])                  # 从STYLE_LABELS字典中获取对应风格的标签，如果找不到则返回"balanced"的默认标签


def _pick_three_styles(pareto_set, sensitivities, budget):                                    # 私有函数：从Pareto前沿选出三种不同风格的方案（省钱型、均衡型、体验型）
    """从 Pareto 前沿选出省钱型、均衡型、体验型三种方案，去重后返回最多 3 个"""
    economy = min(pareto_set, key=lambda x: x["metrics"]["cost"])                               # 找出成本最低的方案作为省钱型方案
    experience = max(                                                                              # 找出体验最好的方案（综合评分和热门度加权）作为体验型方案
        pareto_set,
        key=lambda x: (x["metrics"]["rating"] * EXPERIENCE_RATING_WEIGHT + x["metrics"]["hotness"] * EXPERIENCE_HOTNESS_WEIGHT),
    )
    balanced = choose_solution(pareto_set, sensitivities, budget=budget)                            # 使用choose_solution函数选择均衡型方案

    raw = [                                                                                           # 创建原始方案列表，包含三种风格
        {"style": "economy", "solution": economy},
        {"style": "balanced", "solution": balanced},
        {"style": "experience", "solution": experience},
    ]
    unique = []                                                                                            # 去重处理：确保返回的方案路线不重复
    seen = set()                                                                                        # 用于记录已见过的路线（使用集合提高查找效率）
    for item in raw:
        route_key = tuple(item["solution"]["route"])                                                   # 将路线转换为元组作为唯一标识（因为列表不可哈希）
        if route_key in seen:                                                                           # 如果该路线已经存在，则跳过（避免重复）
            continue
        seen.add(route_key)                                                                               # 否则添加到已见集合
        unique.append(item)                                                                                   # 并添加到唯一方案列表中

    # 不足 3 个时从 Pareto 前沿补选
    fallback_styles = ["balanced", "experience", "economy"]  
    fallback_idx = 0 
    for sol in pareto_set:                                                                                 # 遍历整个Pareto前沿
        if len(unique) >= 3:                                                                                  # 如果已经有3个方案，停止补充
            break
        route_key = tuple(sol["route"])                                                                       # 检查新方案是否已存在
        if route_key not in seen:
            seen.add(route_key)                                                                             # 添加新方案到已见集合
            unique.append({"style": fallback_styles[fallback_idx % 3], "solution": sol})                   # 添加新方案到唯一方案列表
            fallback_idx += 1                                                                                   # 更新备用风格索引
    return unique                                                                                                # 返回最多3个不重复的方案


def _build_top3_options(pareto_set, spots, days, budget, sensitivities):                                      # 私有函数：构建前三个选项的详细信息
    if not pareto_set:                                                                                        # 如果Pareto前沿为空，返回空列表
        return []
    diverse = _pick_three_styles(pareto_set, sensitivities, budget)                                          # 调用_pick_three_styles获取三种风格的方案

    options = []                                                      # 构建最终的选项列表
    for idx, item in enumerate(diverse, start=1):                                                         # 遍历三种风格的方案，索引从1开始
        solution = item["solution"]  # 获取当前方案
        metrics = solution.get("metrics", {})  # 获取方案的指标数据
        route_data = build_route_payload(solution, spots=spots, days=days)                                 # 构建路线数据负载（包含景点详细信息）
        budget_ratio = (metrics.get("cost", 0) / budget * 100) if budget > 0 else 0.0                    # 计算预算使用百分比
        pref_match = max(                                                                                 # 计算偏好匹配度百分比（基于用户敏感度和方案指标）
            0.0,                                                                                                              # 确保最小值为0
            min(  
                100.0,                                                                                   # 确保最大值为100
                50.0                                                                                        # 基础匹配度50%
                + (sensitivities["rating"] - sensitivities["price"]) * 12                                   # 评分偏好与价格敏感度的差值影响
                + (metrics.get("rating", 0) - 4.5) * 8                                           # 方案评分与基准4.5分的差值影响
                - (metrics.get("distance", 0) / 50.0),                                                   # 距离惩罚项
            ),
        )
        options.append(                                                                         # 构建选项字典并添加到选项列表
            {
                "option_id": idx,  # 选项ID（1, 2, 3）
                "style": item["style"],  # 方案风格（economy/balanced/experience）
                "title": f"方案{idx}",  # 显示标题
                "advantage": _calc_advantage_label(item),  # 优势标签（如"省钱"、"均衡"、"体验"）
                "metrics": metrics,  # 方案指标（成本、评分、热门度、距离等）
                "route": route_data,  # 路线数据（包含每日行程安排）
                "explain": {  # 解释信息
                    "budget_usage_pct": round(budget_ratio, 1),  # 预算使用百分比（保留1位小数）
                    "preference_match_pct": round(pref_match, 1),  # 偏好匹配百分比（保留1位小数）
                },
                "ticket_cost": round(metrics.get("cost", 0)),  # 门票成本（四舍五入取整）
                "remaining": round(max(0.0, budget - metrics.get("cost", 0))),  # 剩余预算（确保不为负数）
            }
        )
    return options  # 返回构建好的选项列表


def _build_cache_key(city, season, days, budget, sensitivities):  # 私有函数：构建缓存键，用于唯一标识一个请求
    return json.dumps(  # 将请求参数序列化为JSON字符串作为缓存键
        {
            "city": city,  # 城市
            "season": season,  # 季节
            "days": days,  # 天数
            "budget": budget,  # 预算
            "sensitivities": sensitivities,  # 用户敏感度偏好
        },
        ensure_ascii=False,  # 允许非ASCII字符（如中文）
        sort_keys=True,  # 对键进行排序，确保相同参数总是生成相同的键
    )


def _as_bool(raw_value, default=False):  # 私有函数：将各种类型的值转换为布尔值
    if raw_value is None:  # 如果值为None，返回默认值
        return default
    if isinstance(raw_value, bool):  # 如果已经是布尔值，直接返回
        return raw_value
    text = str(raw_value).strip().lower()  # 转换为字符串并转为小写
    if text in {"1", "true", "yes", "on"}:  # 常见的真值表示
        return True
    if text in {"0", "false", "no", "off"}:  # 常见的假值表示
        return False
    return default  # 其他情况返回默认值


@login_required_custom  # 登录保护装饰器
@require_POST  # 限制只接受POST请求
def generate_ai_nsga2_route(request):  # 主要的AI路线生成视图函数
    _cleanup_plan_cache()  # 清理过期缓存
    try:
        data = json.loads(request.body.decode("utf-8"))  # 解析请求体中的JSON数据
    except json.JSONDecodeError:  # 处理JSON解析错误
        return JsonResponse({"code": 400, "message": "无效的 json 数据", "data": None})

    city = str(data.get("city", "")).strip()  # 获取城市参数并清理空白字符
    season = str(data.get("season", "")).strip()  # 获取季节参数并清理空白字符
    days = int(data.get("days", 1))  # 获取天数参数，默认为1
    budget = float(data.get("budget", 0) or 0)  # 获取预算参数，默认为0

    if not city:  # 验证城市参数
        return JsonResponse({"code": 400, "message": "城市不能为空", "data": None})
    if season not in VALID_SEASONS:  # 验证季节参数
        return JsonResponse({"code": 400, "message": "季节参数非法", "data": None})
    if days <= 0:  # 验证天数参数
        return JsonResponse({"code": 400, "message": "天数必须大于0", "data": None})

    sensitivities = {  # 构建用户敏感度偏好字典
        "price": float(data.get("price_sensitivity", DEFAULT_SENSITIVITY)) / 100.0,  # 价格敏感度（0-1范围）
        "distance": float(data.get("distance_sensitivity", DEFAULT_SENSITIVITY)) / 100.0,  # 距离敏感度（0-1范围）
        "hotness": float(data.get("hotness_preference", DEFAULT_SENSITIVITY)) / 100.0,  # 热门度偏好（0-1范围）
        "rating": float(data.get("rating_preference", DEFAULT_SENSITIVITY)) / 100.0,  # 评分偏好（0-1范围）
    }

    candidates = build_candidates(city=city, season=season)  # 构建候选景点列表
    if len(candidates) < 3:  # 验证候选景点数量
        return JsonResponse({"code": 400, "message": "该城市可用景点不足，请更换城市或放宽条件", "data": None})

    cache_key = _build_cache_key(city, season, days, budget, sensitivities)  # 构建缓存键
    now = time.time()  # 获取当前时间戳
    for token, value in PLAN_CACHE.items():  # 检查是否有相同的缓存结果
        if value.get("cache_key") == cache_key and value.get("expires_at", 0) > now:  # 缓存命中且未过期
            return JsonResponse(  # 直接返回缓存结果
                {
                    "code": 200,
                    "message": "已找到相同方案，直接查看结果",
                    "data": {
                        "request_token": token,  # 缓存令牌
                        "city": city,
                        "season": season,
                        "days": days,
                        "budget": budget,
                        "pareto_size": value.get("pareto_size", 0),  # Pareto前沿大小
                        "options": value.get("options_preview", []),  # 方案预览
                        "recent_plans": RECENT_PLANS[:6],  # 最近计划
                    },
                }
            )

    pareto_set, route_len = run_nsga2(spots=candidates, days=days, budget=budget)  # 运行NSGA2算法生成Pareto前沿
    if not pareto_set:  # 检查是否有可行解
        return JsonResponse({"code": 400, "message": "未找到满足预算的可行路线，请提高预算或减少天数", "data": None})

    options = _build_top3_options(pareto_set, candidates, days, budget, sensitivities)  # 构建前3个选项
    if not options:  # 检查选项是否生成成功
        return JsonResponse({"code": 400, "message": "未生成可用方案，请重试", "data": None})

    token = str(uuid.uuid4())  # 生成唯一令牌
    PLAN_CACHE[token] = {  # 存储完整结果到缓存
        "cache_key": cache_key,
        "expires_at": now + PLAN_CACHE_TTL,  # 设置过期时间
        "city": city,
        "season": season,
        "days": days,
        "budget": budget,
        "options": options,  # 完整选项数据
        "options_preview": [  # 选项预览数据（用于列表显示）
            {
                "option_id": item["option_id"],
                "title": item["title"],
                "style": item["style"],
                "advantage": item["advantage"],
                "metrics": item["metrics"],
                "explain": item["explain"],
                "ticket_cost": item.get("ticket_cost", 0),
                "remaining": item.get("remaining", 0),
            }
            for item in options
        ],
        "pareto_size": len(pareto_set),  # Pareto前沿大小
        "route_len": route_len,  # 路线长度
    }

    RECENT_PLANS.insert(  # 将新计划插入到最近计划列表开头
        0,
        {
            "token": token,
            "city": city,
            "season": season,
            "days": days,
            "budget": budget,
            "price_sensitivity": int(sensitivities["price"] * 100),  # 转换回百分比形式存储
            "distance_sensitivity": int(sensitivities["distance"] * 100),
            "hotness_preference": int(sensitivities["hotness"] * 100),
            "rating_preference": int(sensitivities["rating"] * 100),
            "created_at": int(now),  # 创建时间戳
            "options_preview": PLAN_CACHE[token]["options_preview"],  # 方案预览
        },
    )
    if len(RECENT_PLANS) > RECENT_PLAN_LIMIT:  # 限制最近计划列表长度
        RECENT_PLANS.pop()  # 移除最旧的计划

    return JsonResponse(  # 返回成功响应
        {
            "code": 200,
            "message": "方案生成成功，请选择一个方案继续",
            "data": {
                "request_token": token,
                "city": city,
                "season": season,
                "days": days,
                "budget": budget,
                "pareto_size": len(pareto_set),
                "options": PLAN_CACHE[token]["options_preview"],
                "recent_plans": RECENT_PLANS[:6],
            },
        }
    )


@login_required_custom  # 登录保护装饰器
@require_POST  # 限制只接受POST请求
def recall_ai_nsga2_plan(request):  # 回忆AI计划的视图函数（通过令牌恢复之前的方案）
    """用缓存 token 直接取回 Top3 方案（不重新计算）"""
    _cleanup_plan_cache()  # 清理过期缓存
    try:
        data = json.loads(request.body.decode("utf-8"))  # 解析JSON请求数据
    except json.JSONDecodeError:  # 处理JSON解析错误
        return JsonResponse({"code": 400, "message": "无效的 json 数据", "data": None})
    token = str(data.get("token", "")).strip()  # 获取令牌参数
    if not token:  # 验证令牌参数
        return JsonResponse({"code": 400, "message": "token 缺失", "data": None})
    cache_item = PLAN_CACHE.get(token)  # 从缓存中获取方案
    if not cache_item:  # 检查方案是否存在
        return JsonResponse({"code": 410, "message": "记录已过期，请重新生成", "data": None})
    return JsonResponse({  # 返回恢复的方案
        "code": 200,
        "message": "已恢复之前的方案",
        "data": {
            "request_token": token,
            "options": cache_item.get("options_preview", []),
            "recent_plans": RECENT_PLANS[:6],
        },
    })


@login_required_custom  # 登录保护装饰器
@require_POST  # 限制只接受POST请求
def select_ai_nsga2_plan(request):  # 选择AI计划的视图函数
    _cleanup_plan_cache()  # 清理过期缓存
    try:
        data = json.loads(request.body.decode("utf-8"))  # 解析JSON请求数据
    except json.JSONDecodeError:  # 处理JSON解析错误
        return JsonResponse({"code": 400, "message": "无效的 json 数据", "data": None})

    token = str(data.get("request_token", "")).strip()  # 获取请求令牌
    option_id = int(data.get("option_id", 0) or 0)  # 获取选项ID
    use_wiki_knowledge = _as_bool(data.get("use_wiki_knowledge", False), default=False)  # 获取是否使用Wiki知识的标志
    if not token or option_id <= 0:  # 验证必要参数
        return JsonResponse({"code": 400, "message": "请求参数缺失", "data": None})

    cache_item = PLAN_CACHE.get(token)  # 从缓存中获取方案
    if not cache_item:  # 检查方案是否存在
        return JsonResponse({"code": 400, "message": "方案已过期，请重新生成", "data": None})

    selected = next((item for item in cache_item["options"] if item["option_id"] == option_id), None)  # 查找选中的方案
    if not selected:  # 检查方案是否存在
        return JsonResponse({"code": 400, "message": "方案不存在，请重新选择", "data": None})

    # 检查是否有缓存的AI报告（保证10分钟内点同一方案，结果一模一样）
    cache_item.setdefault("ai_reports", {})
    if option_id in cache_item["ai_reports"]:
        return JsonResponse({"code": 200, "message": "方案已确认，已生成地图与AI报告", "data": cache_item["ai_reports"][option_id]})

    route_data = selected["route"]  # 获取选中方案的路线数据
    metrics = selected.get("metrics", {})  # 获取方案指标
    json_cards = retrieve_knowledge_cards(cache_item["city"], route_data, max_cards=12)  # 检索JSON知识卡片
    knowledge_cards = list(json_cards)  # 转换为列表
    wiki_cards = []  # 初始化Wiki卡片列表
    if use_wiki_knowledge:  # 如果启用Wiki知识
        wiki_cards = retrieve_wiki_knowledge_cards(  # 检索Wiki知识卡片
            city=cache_item["city"],
            route_data=route_data,
            max_cards=8,
            season=cache_item.get("season", ""),
            budget=float(cache_item.get("budget", 0) or 0),
        )
        knowledge_cards.extend(wiki_cards)  # 将Wiki卡片添加到知识卡片列表
    ai_text = generate_ai_summary(  # 生成AI文本摘要
        city=cache_item["city"],
        season=cache_item["season"],
        days=cache_item["days"],
        budget=cache_item["budget"],
        route_data=route_data,
        knowledge_cards=knowledge_cards,
    )
    ai_html = generate_html_report(  # 生成HTML报告
        city=cache_item["city"],
        season=cache_item["season"],
        days=cache_item["days"],
        budget=cache_item["budget"],
        route_data=route_data,
        metrics=metrics,
        knowledge_cards=knowledge_cards,
    )
    used_days = (len(route_data) + 2) // 3 if route_data else 0  # 计算实际使用的天数（假设每天3个景点）
    # 计算预算可行性：门票预算 vs (门票实际 + 食宿交通预估)
    ticket_cost = round(metrics.get("cost", 0))  # 门票成本
    tier = get_city_tier(cache_item["city"])  # 获取城市等级
    living = compute_living_budget(tier, cache_item["days"])  # 计算生活预算（食宿交通）
    total_estimate = ticket_cost + living["total_living"]  # 总预算估算
    feasibility = assess_feasibility(cache_item["budget"], total_estimate)  # 评估预算可行性
    response_data = {  # 构建最终响应数据
        "route": route_data,  # 路线数据
        "ai_summary": ai_text,  # AI文本摘要
        "used_days": min(used_days, cache_item["days"]),  # 实际使用天数
        "pareto_size": cache_item.get("pareto_size", 0),  # Pareto前沿大小
        "metrics": metrics,  # 方案指标
        "city": cache_item["city"],  # 城市
        "ai_html_report": ai_html,  # HTML报告
        "selected_option_id": option_id,  # 选中的选项ID
        "explain": selected.get("explain", {}),  # 解释信息
        "advantage": selected.get("advantage", ""),  # 优势标签
        "style": selected.get("style", ""),  # 方案风格
        "knowledge_cards": knowledge_cards,  # 知识卡片
        "knowledge_count": len(knowledge_cards),  # 知识卡片数量
        "knowledge_breakdown": {  # 知识卡片分类统计
            "json_count": len(json_cards),
            "wiki_count": len(wiki_cards),
            "use_wiki_knowledge": use_wiki_knowledge,
        },
        # 预算可行性数据
        "ticket_cost": ticket_cost,  # 门票成本
        "tier": tier,  # 城市等级
        "tier_label": living["tier_label"],  # 城市等级标签
        "daily_living": living["daily_living"],  # 每日生活费用
        "total_living": living["total_living"],  # 总生活费用
        "total_estimate": total_estimate,  # 总费用估算
        "feasibility": feasibility,  # 可行性评估结果
    }
    # 存回缓存，下次点同一方案直接返回一模一样的结果
    cache_item["ai_reports"][option_id] = response_data
    return JsonResponse({"code": 200, "message": "方案已确认，已生成地图与AI报告", "data": response_data})