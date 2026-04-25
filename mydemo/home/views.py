import json
import time
import uuid
from datetime import datetime, timedelta
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render
from numpy.core.multiarray import item
from django.views.decorators.http import require_POST

from ai.Get_Message import Get_DeepSeek
from home.models import TravelInfo
from home.nsga2_trip_planner import (
    build_candidates,
    build_route_payload,
    call_ai_html_report,
    call_ai_refiner,
    choose_solution,
    retrieve_knowledge_cards,
    run_nsga2,
)
from django.db.models import Q, Sum
from untils import util
from django.db.models import Count
from django.db.models.functions import TruncDate
from user.models import UserInfo

PLAN_CACHE_TTL_SECONDS = 600
PLAN_CACHE = {}
RECENT_PLANS = []
RECENT_PLAN_LIMIT = 12

# 毕设演示用固定配置（按用户要求内置）
DIDA_FIXED_ACCESS_TOKEN = "dp_edb471742d2c40f7bf40589ba2366328"
DIDA_FIXED_PROJECT_INPUT = "旅游规划"
# Create your views here.
def index(request):
    non_free_count = TravelInfo.objects.exclude(
        Q(actual_price='免费') | Q(actual_price__isnull=True)
    ).count()

    pro_count = TravelInfo.objects.values('province').distinct().count()
    print(f"DEBUG: pro_count in view = {pro_count}")  # 添加这行打印

    city_count = TravelInfo.objects.values('city').distinct().count()
    total_reviews = TravelInfo.objects.aggregate(
        total_reviews=Sum('review_count')
    )['total_reviews'] or 0

    sql = 'select * from part6'
    res=util.query(sql)
    mapData = [{"name":i[0],"value":i[1]} for i in res]
    top_5_travel = TravelInfo.objects.all().order_by('-popularity_score')[:5]

    # 按评论数取前5（原变量名 top_1e_travel 疑似拼写错误）
    top_10_travel = TravelInfo.objects.all().order_by('-review_count')[:5]

    daily_users = UserInfo.objects.annotate(
        date=TruncDate('created_at')
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')

    name_list=[str(item['date']) for item in daily_users]
    value_list=[item['count'] for item in daily_users]

    print(name_list,value_list)


    content = {
        "non_free_count": non_free_count,
        "pro_count": pro_count,
        "city_count": city_count,
        "total_reviews": total_reviews,
        "mapData": mapData,
        "top_5_travel": top_5_travel,
        "top_10_travel": top_10_travel,
        "name_list": name_list,
        "value_list": value_list

    }
    print(f"DEBUG: Context passed to template = {content}")  # 添加这行打印
    return render(request, 'index.html', content)  # 确保 context 是 content


# ... existing code ...
def travel_list(request):
    province = TravelInfo.objects.exclude(province__isnull=True).values_list('province', flat=True).distinct()
    travels = TravelInfo.objects.all()
    search_name = request.GET.get('search_name', '')
    selected_province = request.GET.get('province', '')
    if search_name:
        travels = travels.filter(Q(name__icontains=search_name))

    if selected_province:
        travels = travels.filter(province=selected_province)

    travels = travels.order_by('-popularity_score')

    paginator = Paginator(travels, 10)

    page_number = request.GET.get('page')

    page_obj = paginator.get_page(page_number)

    content={
        'page_obj': page_obj,
        'province': province,

        'search_name': search_name,
        'selected_province': selected_province,


    }


    return render(request, 'travel_list.html', content)


# def get_ai_travelRoute(request):
#     if request.method == 'POST':
#         try:
#             # 解析请求数据
#             if hasattr(request, 'data'):
#                 data = request.data
#             else:
#                 try:
#                     data = json.loads(request.body.decode('utf-8'))
#                 except json.JSONDecodeError:
#                     return JsonResponse({
#                         'code': 400,
#                         'message': '无效的json数据',
#                         'data': None
#                     })
#
#             # 验证必要字段
#             required_fields = ['city', 'season', 'days']
#             for field in required_fields:
#                 if field not in data:
#                     return JsonResponse({
#                         'code': 400,
#                         'message': f'缺少必要字段: {field}',
#                         'data': None
#                     })
#
#             # 处理预算参数
#             budget = data.get('budget', 0)
#             if budget == 0:
#                 budget = '无预算'
#
#             # 调用DeepSeek生成旅游计划
#             dp = Get_DeepSeek()
#             result = dp._get_travel_plan(
#                 city=data['city'],
#                 season=data['season'],
#                 days=data['days'],
#                 budget=budget
#             )
#
#             # 返回结果
#             if result['code'] == 200:
#                 return JsonResponse({
#                     'code': 200,
#                     'message': '旅游路线生成成功',
#                     'data': result['data']
#                 })
#             else:
#                 return JsonResponse({
#                     'code': result['code'],
#                     'message': '旅游路线生成失败',
#                     'data': None
#                 })
#
#         except Exception as e:
#             return JsonResponse({
#                 "code": 500,
#                 "message": f"服务器内部错误: {str(e)}",
#                 "data": None
#             })
#
#
#
#
#     return render(request, 'ksh/get_ai_travelRoute.html')

# ... existing code ...
def get_ai_travelRoute(request):
    if request.method == 'POST':
        try:
            # 解析请求数据
            if hasattr(request, 'data'):
                data = request.data
            else:
                try:
                    data = json.loads(request.body.decode('utf-8'))
                except json.JSONDecodeError:
                    return JsonResponse({
                        'code': 400,
                        'message': '无效的 json 数据',
                        'data': None
                    })

            # 验证必要字段
            required_fields = ['city', 'season', 'days']
            for field in required_fields:
                if field not in data:
                    return JsonResponse({
                        'code': 400,
                        'message': f'缺少必要字段：{field}',
                        'data': None
                    })

            # 处理预算参数
            budget = data.get('budget', 0)
            if budget == 0:
                budget = '无预算'

            print(f"DEBUG: 调用 Get_DeepSeek, 参数：city={data['city']}, season={data['season']}, days={data['days']}, budget={budget}")

            # 调用 DeepSeek 生成旅游计划
            dp = Get_DeepSeek()
            result = dp._get_travel_plan(
                city=data['city'],
                season=data['season'],
                days=data['days'],
                budget=budget
            )

            print(f"DEBUG: Get_DeepSeek 返回结果：{result}")

            # 返回结果
            if result['code'] == 200:
                return JsonResponse({
                    'code': 200,
                    'message': '旅游路线生成成功',
                    'data': result['data']
                })
            else:
                error_message = result.get('message', '未知错误')
                raw_result = result.get('raw', '')
                print(f"ERROR: 旅游路线生成失败 - {error_message}")
                print(f"ERROR: AI 原始返回：{raw_result}")
                return JsonResponse({
                    'code': result['code'],
                    'message': f'旅游路线生成失败：{error_message}',
                    'data': None
                })

        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"ERROR: 服务器异常 - {str(e)}")
            print(f"ERROR: 详细堆栈：{error_detail}")
            return JsonResponse({
                "code": 500,
                "message": f"服务器内部错误：{str(e)}",
                "data": None
            })


    return render(request, 'ksh/get_ai_travelRoute.html')


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
def select_ai_nsga2_plan(request):
    _cleanup_plan_cache()
    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"code": 400, "message": "无效的 json 数据", "data": None})

    token = str(data.get("request_token", "")).strip()
    option_id = int(data.get("option_id", 0) or 0)
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
    knowledge_cards = retrieve_knowledge_cards(cache_item["city"], route_data, max_cards=12)
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
            },
        }
    )


def _parse_day_slot(visit_time: str):
    text = str(visit_time or "")
    day_match = __import__("re").search(r"第(\d+)天", text)
    day_no = int(day_match.group(1)) if day_match else 1
    if "上午" in text:
        slot = "上午"
    elif "中午" in text:
        slot = "中午"
    else:
        slot = "下午"
    return day_no, slot


def _format_dida_datetime(dt_obj: datetime) -> str:
    return dt_obj.strftime("%Y-%m-%dT%H:%M:%S+0800")


def _resolve_dida_project_id(access_token: str, project_input: str) -> str:
    # 用户可能输入的是 projectId，也可能输入项目名称；优先直传，失败再按名称匹配
    if not project_input:
        return ""
    candidate = project_input.strip()
    if len(candidate) >= 20:
        return candidate

    req = urlrequest.Request(
        "https://api.dida365.com/open/v1/project",
        headers={"Authorization": f"Bearer {access_token}"},
        method="GET",
    )
    with urlrequest.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8") or "[]")
        if isinstance(data, list):
            for item in data:
                if str(item.get("name", "")).strip() == candidate:
                    return str(item.get("id", "")).strip()
    return ""


@require_POST
def export_to_dida_checklist(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"code": 400, "message": "无效的 json 数据", "data": None})

    access_token = DIDA_FIXED_ACCESS_TOKEN
    project_input = DIDA_FIXED_PROJECT_INPUT
    departure_time = str(data.get("departure_time", "")).strip()
    city = str(data.get("city", "")).strip()
    style = str(data.get("style", "")).strip()
    route = data.get("route", []) or []
    knowledge_cards = data.get("knowledge_cards", []) or []

    if not departure_time:
        return JsonResponse({"code": 400, "message": "departure_time 不能为空", "data": None})
    if not route:
        return JsonResponse({"code": 400, "message": "当前无可导出的行程数据", "data": None})

    try:
        base_dt = datetime.fromisoformat(departure_time)
    except ValueError:
        return JsonResponse({"code": 400, "message": "出发时间格式不正确", "data": None})

    slot_hour = {"上午": 9, "中午": 13, "下午": 16}
    try:
        project_id = _resolve_dida_project_id(access_token, project_input)
    except Exception:
        project_id = ""
    if not project_id:
        return JsonResponse({"code": 400, "message": "无法识别 projectId/项目名称，请检查是否有该清单", "data": None})

    # 构建知识卡索引：按景点名称模糊匹配，给每个任务加贴心提示
    knowledge_index = []
    for card in knowledge_cards:
        knowledge_index.append(
            {
                "spot_name": str(card.get("spot_name", "")).strip(),
                "best_time": str(card.get("best_time", "")).strip(),
                "booking_tip": str(card.get("booking_tip", "")).strip(),
                "transport_tip": str(card.get("transport_tip", "")).strip(),
                "pitfalls": card.get("pitfalls", []) or [],
            }
        )

    def _match_knowledge(spot_name: str):
        name = (spot_name or "").strip().lower()
        for item in knowledge_index:
            k = item["spot_name"].lower()
            if k and (k in name or name in k):
                return item
        return None

    created_tasks = []
    failed_tasks = []
    for row in route:
        day_no, slot = _parse_day_slot(row.get("visit_time", ""))
        start_dt = (base_dt + timedelta(days=day_no - 1)).replace(
            hour=slot_hour.get(slot, 9), minute=0, second=0, microsecond=0
        )
        due_dt = start_dt + timedelta(hours=2)
        spot_name = str(row.get("name", "")).strip()
        knowledge = _match_knowledge(spot_name)
        pitfalls = []
        if knowledge:
            pitfalls = knowledge.get("pitfalls", [])[:3]

        desc_lines = [
            f"行程时段：{row.get('visit_time', '')}",
            f"景点特点：{row.get('features', '')}",
            f"预计花费：{row.get('estimated_cost', '免费')}",
            f"坐标：{row.get('latitude', '')}, {row.get('longitude', '')}",
            "",
            "贴心提醒：",
            f"- 最佳游玩时段：{(knowledge or {}).get('best_time', '建议按实时天气灵活调整')}",
            f"- 预约提示：{(knowledge or {}).get('booking_tip', '建议提前查看官方公告')}",
            f"- 交通建议：{(knowledge or {}).get('transport_tip', '建议地铁优先，打车补充')}",
            f"- 避坑建议：{'；'.join(pitfalls) if pitfalls else '避开高峰时段，注意随身物品'}",
            "",
            "出发前检查：证件/电量/网络/交通路线，建议提前15分钟出发。",
        ]

        dida_payload = {
            "title": f"{row.get('visit_time', '')}｜{spot_name}",
            "projectId": project_id,
            "content": f"{city} {style or '推荐'}方案 · 单景点执行任务",
            "desc": "\n".join(desc_lines),
            "isAllDay": False,
            "startDate": _format_dida_datetime(start_dt),
            "dueDate": _format_dida_datetime(due_dt),
            "timeZone": "Asia/Shanghai",
            "priority": 3,
            "tags": ["旅行计划", "AI路线", f"第{day_no}天"],
        }

        req = urlrequest.Request(
            "https://api.dida365.com/open/v1/task",
            data=json.dumps(dida_payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
            },
            method="POST",
        )
        try:
            with urlrequest.urlopen(req, timeout=20) as resp:
                resp_text = resp.read().decode("utf-8")
                resp_json = json.loads(resp_text) if resp_text else {}
                created_tasks.append(
                    {
                        "task_id": resp_json.get("id", ""),
                        "title": dida_payload["title"],
                    }
                )
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            failed_tasks.append({"title": dida_payload["title"], "error": f"{exc.code} {body}"})
        except URLError as exc:
            failed_tasks.append({"title": dida_payload["title"], "error": str(exc.reason)})

    if not created_tasks:
        return JsonResponse(
            {
                "code": 500,
                "message": "滴答任务创建失败",
                "data": {"failed_tasks": failed_tasks[:3]},
            }
        )
    return JsonResponse(
        {
            "code": 200,
            "message": f"已创建 {len(created_tasks)} 个景点任务（每个地点一个任务）",
            "data": {
                "project_id": project_id,
                "created_count": len(created_tasks),
                "failed_count": len(failed_tasks),
                "created_tasks": created_tasks[:5],
                "failed_tasks": failed_tasks[:3],
            },
        }
    )
