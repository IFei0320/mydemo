from functools import wraps

from django.http import JsonResponse
from django.shortcuts import redirect


def login_required_custom(view_func):
    """自定义登录校验装饰器：检查 session uid，兼容页面重定向与 AJAX JSON 响应"""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.session.get("uid"):
            return view_func(request, *args, **kwargs)

        if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.method == "POST":
            return JsonResponse({"code": 401, "message": "请先登录", "data": None}, status=401)

        return redirect("user:login")

    return wrapper
