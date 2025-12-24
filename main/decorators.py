from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps

# 用户登录验证装饰器
def user_login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.session.get('user_id'):  # 验证用户session
            return view_func(request, *args, **kwargs)
        else:
            messages.error(request, '请先登录')
            return redirect('user:user_login')  # 跳转用户登录页（带命名空间）
    return wrapper

# 商家登录验证装饰器
def merchant_login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.session.get('merchant_id'):  # 验证商家session
            return view_func(request, *args, **kwargs)
        else:
            messages.error(request, '请先登录商家账号')
            return redirect('merchant:merchant_login')  # 跳转商家登录页（带命名空间）
    return wrapper

# 管理员登录验证装饰器
def admin_login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # 验证管理员session
        if request.session.get('admin_id'):
            return view_func(request, *args, **kwargs)
        else:
            messages.error(request, '请先登录管理员账号')
            # 跳转至自定义管理员登录路由
            return redirect('admin_login')
    return wrapper