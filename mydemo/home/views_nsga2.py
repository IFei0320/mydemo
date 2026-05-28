import json
import time
import uuid

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from home.models import TravelInfo
from home.nsga2_knowledge import retrieve_knowledge_cards
from home.nsga2_report import call_ai_html_report, call_ai_refiner
from home.nsga2_trip_planner import (
    build_candidates,
    build_route_payload,
    choose_solution,
    run_nsga2,
)
from home.wiki_service import retrieve_wiki_knowledge_cards

PLAN_CACHE_TTL_SECONDS = 600
PLAN_CACHE = {}
RECENT_PLANS = []
RECENT_PLAN_LIMIT = 12


def ai_nsga2_route_page(request):
    return render(request, 'ksh/ai_nsga2_route.html')


def _cleanup_plan_cache():
    now = time.time()
    expired = [token for token, value in PLAN_CACHE.items() if value.get("expires_at", 0) < now]
    for token in expired:
        PLAN_CACHE.pop(token, None)


def _calc_advantage_label(option):
    style = option.get("style")
    if style == "economy":
        return "省钱型：花费最低，预算压力最小"
    if style == "experience":
        return "体验型：评分与热度表现更高"
    return "均衡型：成本、路程与体验更平衡"


def _build_top3_options(pareto_set, spots, days, budget, sensitivities):
    if not pareto_set:
        return []
    economy = min(pareto_set, key=lambda x: x["metrics"]["cost"])
    experience = max(
        pareto_set,
        key=lambda x: (x["metrics"]["rating"] * 0.6 + x["metrics"]["hotness"] * 0.4),
    )
    balanced = choose_solution(pareto_set, sensitivities, budget=budget)

    raw = [
        {"style": "economy", "solution": economy},
        {"style": "balanced", "solution": balanced},
        {"style": "experience", "solution": experience},
    ]
    unique = []
    seen = set()
    for item in raw:
        route_key = tuple(item["solution"]["route"])
        if route_key in seen:
            continue
        seen.add(route_key)
        unique.append(item)

    # 去重后不足 3 个时，从 Pareto 前沿补选其他路线
    fallback_styles = ["balanced", "experience", "economy"]
    fallback_idx = 0
    for sol in pareto_set:
        if len(unique) >= 3:
            break
        route_key = tuple(sol["route"])
        if route_key not in seen:
            seen.add(route_key)
            unique.append({"style": fallback_styles[fallback_idx % 3], "solution": sol})
            fallback_idx += 1

    options = []
    for idx, item in enumerate(unique, start=1):
        solution = item["solution"]
        metrics = solution.get("metrics", {})
        route_data = build_route_payload(solution, spots=spots, days=days, per_day=3)
        budget_ratio = (metrics.get("cost", 0) / budget * 100) if budget > 0 else 0.0
        crowd_score = max(0.0, 100.0 - min(100.0, metrics.get("hotness", 0) * 10))
        pref_match = max(
            0.0,
            min(
                100.0,
                50.0
                + (sensitivities["rating"] - sensitivities["price"]) * 12
                + (metrics.get("rating", 0) - 4.5) * 8
                - (metrics.get("distance", 0) / 50.0),
            ),
        )
        options.append(
            {
                "option_id": idx,
                "style": item["style"],
                "title": f"方案{idx}",
                "advantage": _calc_advantage_label(item),
                "metrics": metrics,
                "route": route_data,
                "explain": {
                    "budget_usage_pct": round(budget_ratio, 1),
                    "preference_match_pct": round(pref_match, 1),
                    "crowd_avoid_score": round(crowd_score, 1),
                },
            }
        )
    return options


def _build_cache_key(city, season, days, budget, sensitivities):
    return json.dumps(
        {
            "city": city,
            "season": season,
            "days": days,
            "budget": budget,
            "sensitivities": sensitivities,
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _as_bool(raw_value, default=False):
    if raw_value is None:
        return default
    if isinstance(raw_value, bool):
        return raw_value
    text = str(raw_value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


@require_POST
def generate_ai_nsga2_route(request):
    _cleanup_plan_cache()
    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"code": 400, "message": "无效的 json 数据", "data": None})

    city = str(data.get("city", "")).strip()
    season = str(data.get("season", "")).strip()
    days = int(data.get("days", 1))
    budget = float(data.get("budget", 0) or 0)

    if not city:
        return JsonResponse({"code": 400, "message": "城市不能为空", "data": None})
    if season not in {"spring", "summer", "autumn", "winter"}:
        return JsonResponse({"code": 400, "message": "季节参数非法", "data": None})
    if days <= 0:
        return JsonResponse({"code": 400, "message": "天数必须大于0", "data": None})

    sensitivities = {
        "price": float(data.get("price_sensitivity", 50)) / 100.0,
        "distance": float(data.get("distance_sensitivity", 50)) / 100.0,
        "hotness": float(data.get("hotness_preference", 50)) / 100.0,
        "rating": float(data.get("rating_preference", 50)) / 100.0,
        "crowd_avoid": float(data.get("crowd_avoidance", 50)) / 100.0,
    }

    candidates = build_candidates(TravelInfo.objects.all(), city=city, season=season)
    if len(candidates) < 3:
        return JsonResponse({"code": 400, "message": "该城市可用景点不足，请更换城市或放宽条件", "data": None})

    cache_key = _build_cache_key(city, season, days, budget, sensitivities)
    now = time.time()
    for token, value in PLAN_CACHE.items():
        if value.get("cache_key") == cache_key and value.get("expires_at", 0) > now:
            return JsonResponse(
                {
                    "code": 200,
                    "message": "命中缓存，已返回Top3方案",
                    "data": {
                        "request_token": token,
                        "city": city,
                        "season": season,
                        "days": days,
                        "budget": budget,
                        "pareto_size": value.get("pareto_size", 0),
                        "options": value.get("options_preview", []),
                        "recent_plans": RECENT_PLANS[:6],
                    },
                }
            )

    pareto_set, route_len = run_nsga2(spots=candidates, days=days, budget=budget, per_day=3)
    if not pareto_set:
        return JsonResponse({"code": 400, "message": "未找到满足预算的可行路线，请提高预算或减少天数", "data": None})

    options = _build_top3_options(pareto_set, candidates, days, budget, sensitivities)
    if not options:
        return JsonResponse({"code": 400, "message": "未生成可用方案，请重试", "data": None})

    token = str(uuid.uuid4())
    PLAN_CACHE[token] = {
        "cache_key": cache_key,
        "expires_at": now + PLAN_CACHE_TTL_SECONDS,
        "city": city,
        "season": season,
        "days": days,
        "budget": budget,
        "options": options,
        "options_preview": [
            {
                "option_id": item["option_id"],
                "title": item["title"],
                "style": item["style"],
                "advantage": item["advantage"],
                "metrics": item["metrics"],
                "explain": item["explain"],
            }
            for item in options
        ],
        "pareto_size": len(pareto_set),
        "route_len": route_len,
    }

    RECENT_PLANS.insert(
        0,
        {
            "token": token,
            "city": city,
            "season": season,
            "days": days,
            "budget": budget,
            "price_sensitivity": int(sensitivities["price"] * 100),
            "distance_sensitivity": int(sensitivities["distance"] * 100),
            "hotness_preference": int(sensitivities["hotness"] * 100),
            "rating_preference": int(sensitivities["rating"] * 100),
            "crowd_avoidance": int(sensitivities["crowd_avoid"] * 100),
            "created_at": int(now),
        },
    )
    if len(RECENT_PLANS) > RECENT_PLAN_LIMIT:
        RECENT_PLANS.pop()

    return JsonResponse(
        {
            "code": 200,
            "message": "Top3方案生成成功，请先选择方案",
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


@require_POST
def recall_ai_nsga2_plan(request):
    """用缓存 token 直接取回 Top3 方案（不重新计算）"""
    _cleanup_plan_cache()
    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"code": 400, "message": "无效的 json 数据", "data": None})
    token = str(data.get("token", "")).strip()
    if not token:
        return JsonResponse({"code": 400, "message": "token 缺失", "data": None})
    cache_item = PLAN_CACHE.get(token)
    if not cache_item:
        return JsonResponse({"code": 410, "message": "缓存已过期，请重新生成", "data": None})
    return JsonResponse({
        "code": 200,
        "message": "命中缓存，直接恢复方案",
        "data": {
            "request_token": token,
            "options": cache_item.get("options_preview", []),
            "recent_plans": RECENT_PLANS[:6],
        },
    })


@require_POST
def select_ai_nsga2_plan(request):
    _cleanup_plan_cache()
    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"code": 400, "message": "无效的 json 数据", "data": None})

    token = str(data.get("request_token", "")).strip()
    option_id = int(data.get("option_id", 0) or 0)
    use_wiki_knowledge = _as_bool(data.get("use_wiki_knowledge", False), default=False)
    if not token or option_id <= 0:
        return JsonResponse({"code": 400, "message": "请求参数缺失", "data": None})

    cache_item = PLAN_CACHE.get(token)
    if not cache_item:
        return JsonResponse({"code": 400, "message": "方案已过期，请重新生成", "data": None})

    selected = next((item for item in cache_item["options"] if item["option_id"] == option_id), None)
    if not selected:
        return JsonResponse({"code": 400, "message": "方案不存在，请重新选择", "data": None})

    route_data = selected["route"]
    metrics = selected.get("metrics", {})
    json_cards = retrieve_knowledge_cards(cache_item["city"], route_data, max_cards=12)
    knowledge_cards = list(json_cards)
    wiki_cards = []
    if use_wiki_knowledge:
        wiki_cards = retrieve_wiki_knowledge_cards(
            city=cache_item["city"],
            route_data=route_data,
            max_cards=8,
            season=cache_item.get("season", ""),
            budget=float(cache_item.get("budget", 0) or 0),
        )
        knowledge_cards.extend(wiki_cards)
    ai_text = call_ai_refiner(
        city=cache_item["city"],
        season=cache_item["season"],
        days=cache_item["days"],
        budget=cache_item["budget"],
        route_data=route_data,
        knowledge_cards=knowledge_cards,
    )
    ai_html = call_ai_html_report(
        city=cache_item["city"],
        season=cache_item["season"],
        days=cache_item["days"],
        budget=cache_item["budget"],
        route_data=route_data,
        metrics=metrics,
        knowledge_cards=knowledge_cards,
    )
    used_days = (len(route_data) + 2) // 3 if route_data else 0
    return JsonResponse(
        {
            "code": 200,
            "message": "方案已确认，已生成地图与AI报告",
            "data": {
                "route": route_data,
                "ai_summary": ai_text,
                "used_days": min(used_days, cache_item["days"]),
                "pareto_size": cache_item.get("pareto_size", 0),
                "metrics": metrics,
                "city": cache_item["city"],
                "ai_html_report": ai_html,
                "selected_option_id": option_id,
                "explain": selected.get("explain", {}),
                "advantage": selected.get("advantage", ""),
                "style": selected.get("style", ""),
                "knowledge_cards": knowledge_cards,
                "knowledge_count": len(knowledge_cards),
                "knowledge_breakdown": {
                    "json_count": len(json_cards),
                    "wiki_count": len(wiki_cards),
                    "use_wiki_knowledge": use_wiki_knowledge,
                },
            },
        }
    )
