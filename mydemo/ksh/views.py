import json

from django.http import JsonResponse
from django.shortcuts import render
from django.utils.safestring import mark_safe

from utils.decorators import login_required_custom

from home.models import (
    Part1, Part2, Part3, Part4, Part5, Part6, Part7, Part8, TravelInfo,
)
from home.nsga2_trip_planner import _parse_price


@login_required_custom
def part1(request):
    data_list = list(
        Part1.objects.values('score', 'value').order_by('score')
    )
    # 重命名为模板需要的字段名
    for item in data_list:
        item['name'] = item.pop('score')

    res2 = Part8.objects.values('name', 'travel_num', 'avg_score')
    name_list = [i['name'] for i in res2]
    travel_num_list = [i['travel_num'] for i in res2]
    avg_score_list = [i['avg_score'] for i in res2]
    content = {
        'data_list': data_list,
        'name_list': name_list,
        'travel_num_list': travel_num_list,
        'avg_score_list': avg_score_list
    }
    return render(request, 'ksh/part1.html', content)

@login_required_custom
def part2(request):
    data_list = list(
        Part2.objects.values('name', 'value').order_by('-value')
    )
    name_list = [i['name'] for i in data_list]
    select_list = list(
        Part7.objects.values_list('city', flat=True).distinct().order_by('city')
    )
    content = {
        'data_list': data_list,
        'name_list': name_list,
        'select_list': select_list,
    }
    return render(request, 'ksh/part2.html', content)


@login_required_custom
def get_cityData(request):
    city = request.GET.get('city', '')
    res = Part7.objects.filter(city=city).values_list('name', 'value')
    name_list = [i[0] for i in res]
    value_list = [i[1] for i in res]
    content = {
        'names': name_list,
        'values': value_list,
    }
    return JsonResponse({"data": content})


@login_required_custom
def part3(request):
    """
    门票价格页：展示各景点名称与解析后的票价。
    注：dy_analysis.part3 表由 data_analysis.part3() 写入的是「价格区间 -> 该区间景点数量」，
    并非单景点票价；若用该表会把「数量」误当「元」参与平均，且名称列会变成区间代号。
    """
    from collections import defaultdict

    selected_province = request.GET.get('province', '')

    # 获取所有省份列表（用于下拉筛选）
    provinces = list(
        TravelInfo.objects.exclude(province__isnull=True)
        .exclude(province='')
        .values_list('province', flat=True)
        .distinct()
        .order_by('province')
    )

    if selected_province:
        # 详情模式：指定省份的景点价格
        qs = TravelInfo.objects.filter(province=selected_province)
        pairs = []
        for row in qs.only("name", "actual_price", "market_price", "is_free"):
            name = (row.name or "").strip() or "未知景点"
            if bool(row.is_free):
                price = 0.0
            else:
                price = _parse_price(row.actual_price)
                if price <= 0:
                    price = _parse_price(row.market_price)
            pairs.append((name, round(float(price), 2)))
        pairs.sort(key=lambda x: -x[1])
        chart_mode = 'detail'
    else:
        # 汇总模式：各省份平均门票价格
        province_prices = defaultdict(list)
        for row in TravelInfo.objects.all().only("province", "actual_price", "market_price", "is_free"):
            province = row.province
            if not province:
                continue
            if bool(row.is_free):
                price = 0.0
            else:
                price = _parse_price(row.actual_price)
                if price <= 0:
                    price = _parse_price(row.market_price)
            province_prices[province].append(round(float(price), 2))

        pairs = []
        for prov, prices in province_prices.items():
            if prices:
                avg_price = round(sum(prices) / len(prices), 2)
                pairs.append((prov, avg_price))
        pairs.sort(key=lambda x: -x[1])
        chart_mode = 'summary'

    name_list = [p[0] for p in pairs]
    value_list = [p[1] for p in pairs]

    content = {
        "name_list_json": mark_safe(json.dumps(name_list, ensure_ascii=False)),
        "value_list_json": mark_safe(json.dumps(value_list)),
        "provinces": provinces,
        "selected_province": selected_province,
        "chart_mode": chart_mode,
    }
    return render(request, "ksh/part3.html", content)




@login_required_custom
def part4(request):
    """
    区域分布：优先用 TravelInfo 聚合。
    若「所在区域」在库中过细（大量一区一条），按区域汇总会全是 count=1，
    占比在局部视图里也会像「全是 100%」。此时自动改为「按城市」或「从区域文本抽取区县」再汇总。
    """
    from collections import defaultdict
    import re

    from django.db.models import Count

    qs = TravelInfo.objects.all()
    if not qs.exists():
        data_list = list(
            Part4.objects.values('name', 'value').order_by('-value')
        )
        chart_note = "当前使用离线表 part4（TravelInfo 无数据）。"
        group_mode = "legacy"
    else:

        def _is_degenerate(area_rows):
            if not area_rows:
                return True
            n = len(area_rows)
            ones = sum(1 for g in area_rows if g["count"] == 1)
            return ones >= max(5, int(0.7 * n)) or (n > 12 and ones / n >= 0.55)

        area_rows = list(
            qs.exclude(area__isnull=True)
            .exclude(area="")
            .values("area")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        data_list = []
        chart_note = ""
        group_mode = "area"

        if not _is_degenerate(area_rows):
            data_list = [
                {"name": (r["area"] or "未知区域").strip(), "value": r["count"]}
                for r in area_rows
            ]
        else:
            city_rows = list(
                qs.exclude(city__isnull=True)
                .exclude(city="")
                .values("city")
                .annotate(count=Count("id"))
                .order_by("-count")
            )
            if len(city_rows) > 1:
                data_list = [
                    {"name": (r["city"] or "未知城市").strip(), "value": r["count"]}
                    for r in city_rows
                ]
                group_mode = "city"
                chart_note = (
                    "库中「所在区域」过细，多数区域仅对应单条景点；已改为按「城市」汇总，便于对比。"
                )
            else:
                district_re = re.compile(r"([\u4e00-\u9fa5]{2,14}(?:区|县))")

                def _bucket(area: str, city: str) -> str:
                    text = (area or "").strip()
                    if text:
                        m = district_re.search(text)
                        if m:
                            return m.group(1)
                    c = (city or "").strip()
                    return c or "未填写"

                bucket = defaultdict(int)
                for row in qs.only("area", "city"):
                    bucket[_bucket(row.area, row.city)] += 1
                data_list = [
                    {"name": k, "value": v}
                    for k, v in sorted(bucket.items(), key=lambda kv: -kv[1])
                    if v > 0
                ]
                group_mode = "district"
                chart_note = (
                    "单城市数据下「所在区域」过细；已尝试从区域文本抽取「区/县」关键字再汇总。"
                    "若仍偏碎，请在数据源中把「所在区域」写成更大粒度（如区县或商圈）。"
                )

    content = {
        "data_list_json": mark_safe(json.dumps(data_list, ensure_ascii=False)),
        "chart_note": chart_note,
        "group_mode": group_mode,
    }
    return render(request, "ksh/part4.html", content)
