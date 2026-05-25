import json
# import time
# import uuid
from datetime import datetime, timedelta
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render
# from numpy.core.multiarray import item
from django.views.decorators.http import require_POST
from ai.Get_Message import Get_DeepSeek
from home.models import TravelInfo
from home.nsga2_trip_planner import (
    _normalize_coord_pair,
    # build_candidates,
    # build_route_payload,
    # call_ai_html_report,
    # call_ai_refiner,
    # choose_solution,
    # retrieve_knowledge_cards,
    # run_nsga2,
)
# from home.wiki_service import retrieve_wiki_knowledge_cards
from django.db.models import Q, Sum
from utils import util
from django.db.models import Count
from django.db.models.functions import TruncDate
from user.models import UserInfo

PLAN_CACHE_TTL_SECONDS = 600
PLAN_CACHE = {}
RECENT_PLANS = []
RECENT_PLAN_LIMIT = 12


DIDA_FIXED_ACCESS_TOKEN = "dp_edb471742d2c40f7bf40589ba2366328"
DIDA_FIXED_PROJECT_INPUT = "旅游规划"
# Create your views here.
def index(request):
    non_free_count = TravelInfo.objects.exclude(
        Q(actual_price='免费') | Q(actual_price__isnull=True)
    ).count()

    pro_count = TravelInfo.objects.values('province').distinct().count()
    print(f"DEBUG: pro_count in view = {pro_count}")

    city_count = TravelInfo.objects.values('city').distinct().count()
    total_reviews = TravelInfo.objects.aggregate(
        total_reviews=Sum('review_count')
    )['total_reviews'] or 0

    sql = 'select * from part6'
    res=util.query(sql)
    mapData = [{"name":i[0],"value":i[1]} for i in res]
    top_5_travel = TravelInfo.objects.all().order_by('-popularity_score')[:5]


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
        'provinces': list(province),
        'search_name': search_name,
        'search_province': selected_province,
    }


    return render(request, 'travel_list.html', content)


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

            dp = Get_DeepSeek()
            result = dp.get_city_travel_overview(
                city=data["city"],
                season=data["season"],
                days=str(data["days"]),
                budget=str(budget),
            )

            if result["code"] != 200:
                return JsonResponse(
                    {
                        "code": result["code"],
                        "message": result.get("message", "生成失败"),
                        "data": None,
                    }
                )

            city_key = str(data["city"]).strip()
            city_rows = list(
                TravelInfo.objects.filter(city__icontains=city_key)
                .exclude(longitude__isnull=True)
                .exclude(latitude__isnull=True)[:250]
            )
            primary = [
                row
                for row in city_rows
                if str(row.city or "").replace("市", "") == city_key.replace("市", "")
            ]
            source_rows = primary if len(primary) >= 9 else city_rows

            map_spots = []
            for t in source_rows[:120]:
                lon, lat = _normalize_coord_pair(t.longitude, t.latitude)
                if not lon or not lat:
                    continue
                price_hint = t.actual_price or t.market_price or ""
                map_spots.append(
                    {
                        "name": t.name or "",
                        "longitude": lon,
                        "latitude": lat,
                        "rating": t.rating or "",
                        "area": t.area or "",
                        "price_hint": str(price_hint)[:120],
                    }
                )

            return JsonResponse(
                {
                    "code": 200,
                    "message": "目的地概览生成成功",
                    "data": {
                        "overview": result["overview"],
                        "map_spots": map_spots,
                        "map_spot_count": len(map_spots),
                        "city": city_key,
                    },
                }
            )

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
        detail_text = "\n".join(desc_lines)

        dida_payload = {
            "title": f"{row.get('visit_time', '')}｜{spot_name}",
            "projectId": project_id,
            # TickTick/Dida 客户端通常优先展示 content；将提醒详情放在 content 中确保可见
            "content": detail_text,
            # desc 作为兼容保留，避免某些端只读取该字段
            "desc": detail_text,
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
                        "content_preview": dida_payload["content"][:80],
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






