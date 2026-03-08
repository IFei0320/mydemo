from django.core.paginator import Paginator
from django.shortcuts import render
from numpy.core.multiarray import item

from home.models import TravelInfo
from django.db.models import Q, Sum
from untils import util
from django.db.models import Count
from django.db.models.functions import TruncDate
from user.models import UserInfo
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
