# from django.http import JsonResponse
# from django.shortcuts import render
# from user.models import UserInfo
# import hashlib
#
#
# # Create your views here.
#
# def login(request):
#     if request.method == 'POST':
#         try:
#             username = request.POST.get('username')
#             password = request.POST.get('password')
#             try:
#                 user = UserInfo.objects.get(username=username)
#             except UserInfo.DoesNotExist:
#                 return JsonResponse({'code': 400, 'msg': '用户不存在'})
#
#             if password != user.password:  # 注意：实际项目中应使用密码哈希验证
#                 return JsonResponse({'code': 400, 'msg': '用户名或密码错误'})
#
#             request.session['uid'] = user.id
#             request.session['uname'] = user.username
#             request.session['avatar'] = user.avatar
#
#             return JsonResponse({'code': 200, 'msg': '登录成功'})
#         except Exception as e:
#             return JsonResponse({'code': 500, 'msg': f'服务器错误{str(e)}'})
#     else:
#         return render(request, 'login.html')
#
#
#
#
# def register(request):
#     if request.method == 'POST':
#         try:
#             username = request.POST.get('username')
#             email = request.POST.get('email')
#             password = request.POST.get('password')
#             print(username, email, password)
#             if UserInfo.objects.filter(username=username).exists():
#                 return JsonResponse({'code': 400, 'msg': '用户已存在'})
#             if UserInfo.objects.filter(uemail=email).exists():
#                 return JsonResponse({'code': 400, 'msg': '邮箱已存在'})
#             UserInfo.objects.create(
#                 username=username,
#                 uemail=email,
#                 password=password,
#                 uaddress='',
#                 uphone='',
#                 uyoubian='',
#                 avatar=''
#             )
#             return JsonResponse({'code': 200, 'msg': '注册成功'})
#         except Exception as e:
#             return JsonResponse({'code': 500, 'msg': f'服务器错误{str(e)}'})
#     return render(request, 'register.html')
#
#
from django.http import JsonResponse
from django.shortcuts import render
# from django.contrib.auth.hashers import make_password, check_password # 暂时注释掉
from user.models import UserInfo


# import hashlib # 可以移除，我们先不用它

def login(request):
    if request.method == 'POST':
        try:
            username = request.POST.get('username')
            password = request.POST.get('password')  # 登录时获取的密码

            print(f"Login attempt for user: {username}, password: '{password}'")  # 打印日志，调试用

            try:
                user = UserInfo.objects.get(username=username)
            except UserInfo.DoesNotExist:
                return JsonResponse({'code': 400, 'msg': '用户不存在'})

            print(f"Retrieved user from DB: {user.username}, stored password: '{user.password}'")  # 打印日志，调试用

            # 明文比较
            if password != user.password:
                print("Password mismatch!")  # 打印日志，调试用
                return JsonResponse({'code': 400, 'msg': '用户名或密码错误'})

            print("Password match!")  # 打印日志，调试用

            request.session['uid'] = user.id
            request.session['uname'] = user.username
            request.session['avatar'] = user.avatar

            return JsonResponse({'code': 200, 'msg': '登录成功'})
        except Exception as e:
            print(f"Login error: {e}")  # 打印日志，调试用
            return JsonResponse({'code': 500, 'msg': f'服务器错误{str(e)}'})
    else:
        return render(request, 'login.html')


def register(request):
    if request.method == 'POST':
        try:
            username = request.POST.get('username')
            email = request.POST.get('email')
            password = request.POST.get('password')

            print(f"Register attempt for user: {username}, email: {email}, password: '{password}'")  # 打印日志，调试用

            if UserInfo.objects.filter(username=username).exists():
                return JsonResponse({'code': 400, 'msg': '用户已存在'})
            if UserInfo.objects.filter(uemail=email).exists():
                return JsonResponse({'code': 400, 'msg': '邮箱已存在'})

            UserInfo.objects.create(
                username=username,
                uemail=email,
                password=password,  # 直接存入原始密码
                uaddress='',
                uphone='',
                uyoubian='',
                avatar=''
            )
            print(f"User {username} registered successfully with password: '{password}'")  # 打印日志，调试用
            return JsonResponse({'code': 200, 'msg': '注册成功'})
        except Exception as e:
            print(f"Registration error: {e}")  # 打印日志，调试用
            return JsonResponse({'code': 500, 'msg': f'服务器错误{str(e)}'})
    return render(request, 'register.html')