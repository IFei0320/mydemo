import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from home.wiki_service import ingest_all_raw, lint_wiki, query_wiki


def wiki_mvp_page(request):
    return render(request, "ksh/wiki_mvp.html")


@require_POST
def wiki_ingest(request):
    result = ingest_all_raw()
    return JsonResponse({"code": 200 if result.get("ok") else 500, "message": "摄入完成", "data": result})


@require_POST
def wiki_query(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"code": 400, "message": "无效的 json 数据", "data": None})
    result = query_wiki(
        str(data.get("question", "")).strip(),
        city=str(data.get("city", "")).strip(),
    )
    return JsonResponse({"code": 200 if result.get("ok") else 400, "message": "查询完成", "data": result})


@require_POST
def wiki_lint(request):
    result = lint_wiki()
    return JsonResponse({"code": 200 if result.get("ok") else 500, "message": "检查完成", "data": result})
