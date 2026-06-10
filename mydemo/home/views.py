import json

from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render
# from numpy.core.multiarray import item
from home.models import Part6, TravelInfo
from ai.Get_Message import Get_DeepSeek
from home.data_utils import _normalize_coord_pair, dedup_by_name
# from home.wiki_service import retrieve_wiki_knowledge_cards
from django.db.models import Q, Sum, Count
from django.db.models.functions import TruncDate
from utils.decorators import login_required_custom
from user.models import UserInfo

# Create your views here.
@login_required_custom
def index(request):
    non_free_count = TravelInfo.objects.exclude(
        Q(actual_price='免费') | Q(actual_price__isnull=True)
    ).count()

    pro_count = TravelInfo.objects.values('province').distinct().count()
    city_count = TravelInfo.objects.values('city').distinct().count()
    total_reviews = TravelInfo.objects.aggregate(
        total_reviews=Sum('review_count')
    )['total_reviews'] or 0

    mapData = list(
        Part6.objects.values('name', 'value').order_by('-value')
    )

    all_by_hot = TravelInfo.objects.order_by('-popularity_score', '-review_count')
    top_5_travel = dedup_by_name(all_by_hot)[:5]

    all_by_review = TravelInfo.objects.order_by('-review_count', '-popularity_score')
    top_10_travel = dedup_by_name(all_by_review)[:5]

    daily_users = UserInfo.objects.annotate(
        date=TruncDate('created_at')
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')

    name_list=[str(item['date']) for item in daily_users]
    value_list=[item['count'] for item in daily_users]

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
    return render(request, 'index.html', content)  # 确保 context 是 content


@login_required_custom
def travel_list(request):
    province = TravelInfo.objects.exclude(province__isnull=True).values_list('province', flat=True).distinct()
    search_name = request.GET.get('search_name', '')
    selected_province = request.GET.get('province', '')

    travels_qs = TravelInfo.objects.order_by('-popularity_score', '-review_count')
    if search_name:
        travels_qs = travels_qs.filter(Q(name__icontains=search_name))
    if selected_province:
        travels_qs = travels_qs.filter(province=selected_province)

    travels = dedup_by_name(travels_qs)

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


@login_required_custom
def get_ai_travelRoute(request):
    if request.method == 'POST':
        try:
            # 解析请求数据
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
            for t in source_rows:
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


