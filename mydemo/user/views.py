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
import os
from time import timezone

from django.http import JsonResponse
from django.shortcuts import render, redirect
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


def changeInfo(request):
    uid = request.session.get('uid')
    if request.method == 'POST':
        return None
    else:
        # GET请求，显示个人信息
        try:
            user = UserInfo.objects.get(id=uid)
            return render(request, 'ksh/changeInfo.html', {
                'user': user,
                'success': None,
                'error': None
            })
        except UserInfo.DoesNotExist:
            return render(request, 'ksh/changeInfo.html', {
                'error': '用户不存在',
                'success': None
            })

def upload_avatar(request):
    """上传头像"""
    if request.method == 'POST':
        uid = request.session.get('uid')
        if not uid:
            return JsonResponse({'code': 401, 'msg': '请先登录'})

        try:
            user = UserInfo.objects.get(id=uid)

            if 'avatar' not in request.FILES:
                return JsonResponse({'code': 400, 'msg': '请选择头像文件'})

            avatar_file = request.FILES['avatar']

            # 验证文件类型
            allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
            if avatar_file.content_type not in allowed_types:
                return JsonResponse({'code': 400, 'msg': '只支持JPEG、PNG、GIF和WebP格式的图片'})

            # 验证文件大小（最大2MB）
            if avatar_file.size > 2 * 1024 * 1024:
                return JsonResponse({'code': 400, 'msg': '图片大小不能超过2MB'})

            # 创建头像存储目录
            from mydemo import settings
            avatar_dir = os.path.join(settings.MEDIA_ROOT, 'avatars')
            if not os.path.exists(avatar_dir):
                os.makedirs(avatar_dir)

            # 生成文件名
            file_extension = os.path.splitext(avatar_file.name)[1]
            filename = f'avatar_{uid}_{int(timezone.now().timestamp())}{file_extension}'
            filepath = os.path.join(avatar_dir, filename)

            # 保存文件
            with open(filepath, 'wb+') as destination:
                for chunk in avatar_file.chunks():
                    destination.write(chunk)

            # 更新用户头像路径（相对路径）
            avatar_url = f'/media/avatars/{filename}'
            user.avatar = avatar_url
            user.save()

            # 更新session中的头像
            request.session['avatar'] = avatar_url

            return JsonResponse({
                'code': 200,
                'msg': '头像上传成功',
                'avatar_url': avatar_url
            })

        except UserInfo.DoesNotExist:
            return JsonResponse({'code': 404, 'msg': '用户不存在'})
        except Exception as e:
            return JsonResponse({'code': 500, 'msg': '服务器错误：' + str(e)})

    return JsonResponse({'code': 400, 'msg': '请求方法错误'})


def logout(request):
    request.session.clear()

    return redirect('user:login')