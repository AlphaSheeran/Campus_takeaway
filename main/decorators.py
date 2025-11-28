from django.shortcuts import redirect
from django.contrib import messages

def user_login_required(view_func):
    """用户登录验证装饰器"""
    def wrapper(request, *args, **kwargs):
        if not request.session.get('user_id'):
            messages.warning(request, "请先登录后访问！")
            return redirect('user:user_login')  # 假设登录路由名称为'user:user_login'
        return view_func(request, *args, **kwargs)
    return wrapper

def merchant_login_required(view_func):
    """商家登录验证装饰器"""
    def wrapper(request, *args, **kwargs):
        if not request.session.get('merchant_id'):
            messages.warning(request, "请先登录商家账号！")
            return redirect('merchant:merchant_login')  # 假设商家登录路由名称
        return view_func(request, *args, **kwargs)
    return wrapper
