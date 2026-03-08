from django.http import JsonResponse

from untils import util
from django.shortcuts import render



from django.shortcuts import render


def part1(request):
    sql1 = 'select * from part1'
    res = util.query(sql1)
    data_list = [{"value": i[2], "name": i[1]} for i in res]

    sql2='select * from part8'
    res2 = util.query(sql2)

    name_list = [i[1] for i in res2]
    travel_num_list = [i[2] for i in res2]
    avg_score_list = [i[3] for i in res2]
    content = {
        'data_list': data_list,
        'name_list': name_list,
        'travel_num_list': travel_num_list,
        'avg_score_list': avg_score_list
    }
    return render(request, 'ksh/part1.html', content)

# ... existing code ...

def part2(request):
    sql1 = 'select * from part2'
    res = util.query(sql1)
    name_list = [i[1] for i in res]
    data_list = [{"value": i[2], "name": i[1]} for i in res]
    sql2 = 'select distinct city from part7'
    res2 = util.query(sql2)
    select_list = [i[0] for i in res2]
    content = {
        'data_list': data_list,
        'name_list': name_list,
        'select_list': select_list,
    }
    return render(request, 'ksh/part2.html', content)


def get_cityData(request):
    city = request.GET.get('city', '')

    sql = f"select name,value from part7 where city='{city}'"
    res = util.query(sql)

    name_list = [i[0] for i in res]
    value_list = [i[1] for i in res]

    content = {
        'names': name_list,
        'values': value_list,
    }

    return JsonResponse({"data": content})