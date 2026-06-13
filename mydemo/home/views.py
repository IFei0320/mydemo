import json

from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render
from home.models import Part6, TravelInfo
from ai.Get_Message import Get_DeepSeek
from home.data_utils import _normalize_coord_pair, dedup_by_name
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
    top_5_review = dedup_by_name(all_by_review)[:5]

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
        "top_10_travel": top_5_review,  # 兼容旧模板命名，实际为评论数 Top5
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
    if request.method != 'POST':
        return render(request, 'ksh/get_ai_travelRoute.html')

    try:
        data = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return JsonResponse({'code': 400, 'message': '无效的 json 数据', 'data': None})

    try:
        required_fields = ['city', 'season', 'days']   # required_fields: 定义必须有的三个字段：城市、季节、天数。
        for field in required_fields:
            if field not in data:
                return JsonResponse({
                    'code': 400,
                    'message': f'缺少必要字段：{field}',
                    'data': None,
                })

        budget = data.get('budget', 0)
        if budget == 0:
            budget = '无预算'    # data.get('budget', 0): 尝试获取 'budget' 字段。
        # 如果用户没传 budget，默认值是 0。

        dp = Get_DeepSeek()
        result = dp.get_city_travel_overview(
            city=data["city"],
            season=data["season"],
            days=str(data["days"]),
            budget=str(budget),
        )

        if result["code"] != 200:
            return JsonResponse({
                "code": result["code"],
                "message": result.get("message", "生成失败"),
                "data": None,
            })

        city_key = str(data["city"]).strip()    # 清洗城市名，去掉首尾空格，转为字符串。
        city_rows = list(
            TravelInfo.objects.filter(city__icontains=city_key)
            .exclude(longitude__isnull=True)
            .exclude(latitude__isnull=True)[:250]
              # .exclude(longitude__isnull=True): 排除掉经度为空的记录（没坐标的不算）。
        # .exclude(latitude__isnull=True): 排除掉纬度为空的记录。
        # [:250]: 最多取前 250 条，防止数据太多拖慢速度。
        # list(...): 把查询结果集（QuerySet）转换成普通列表
        )
        primary = [
            row
            for row in city_rows
            if str(row.city or "").replace("市", "") == city_key.replace("市", "")
        ]
        source_rows = primary if len(primary) >= 9 else city_rows
        # 如果精确匹配的景点数量 >= 9 个：
        #   -> 只使用 primary（精确匹配的）。
        # 否则（少于 9 个）：
        #   -> 使用 city_rows（所有模糊匹配的）。
        # 目的：保证地图上至少有 9 个核心景点，不够的话就放宽范围凑数。

        map_spots = []
        for t in source_rows:
            lon, lat = _normalize_coord_pair(t.longitude, t.latitude)
            if not lon or not lat:   # 如果经度或纬度无效，跳过这条记录，不加入地图。
                continue
            price_hint = t.actual_price or t.market_price or ""
            map_spots.append({
                "name": t.name or "",
                "longitude": lon,
                "latitude": lat,
                "rating": t.rating or "",
                "area": t.area or "",
                "price_hint": str(price_hint)[:120],
            })
 # 构造一个字典，放入 map_spots 列表。
            # name, rating, area: 如果数据库是 None，就填空字符串。
            # price_hint[:120]: 截取价格描述的前 120 个字，防止太长。
        return JsonResponse({
            "code": 200,
            "message": "目的地概览生成成功",
            "data": {
                "overview": result["overview"],
                "map_spots": map_spots,
                "map_spot_count": len(map_spots),
                "city": city_key,
            },
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            "code": 500,
            "message": f"服务器内部错误：{str(e)}",
            "data": None,
        })


