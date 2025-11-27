import json
import uuid
import os
from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.conf import settings
from django.db.models import Q, Sum
from django.contrib import messages  # 用于页面提示信息

# 导入所有模型（去重合并）
from .models import User, Merchant, Dish, Order, OrderItem, Address, Admin

# ---------------------- 公共工具函数 ----------------------
def generate_order_no():
    """生成唯一订单号（UUID前8位+时间戳）"""
    return f"{uuid.uuid4().hex[:8]}-{datetime.now().strftime('%Y%m%d%H%M%S')}"


# ---------------------- 用户端视图 ----------------------
def user_index(request):
    """用户首页"""
    return render(request, 'main/user/index.html')

def user_login(request):
    """用户登录页面"""
    return render(request, 'main/user/login.html')

@ensure_csrf_cookie
def user_login_api(request):
    """用户登录API"""
    if request.method == 'POST':
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return JsonResponse({'code': 0, 'msg': '账号不存在'})

        if not check_password(password, user.password):
            return JsonResponse({'code': 0, 'msg': '密码错误'})

        # 设置Session
        request.session['user_id'] = user.id
        request.session['user_name'] = user.name
        return JsonResponse({'code': 1, 'msg': '登录成功'})
    return JsonResponse({'code': 0, 'msg': '请求方式错误'})

def user_register(request):
    """用户注册页面"""
    return render(request, 'main/user/register.html')

@ensure_csrf_cookie
def user_register_api(request):
    """用户注册API"""
    if request.method == 'POST':
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')
        name = data.get('name')
        phone = data.get('phone', '')

        if User.objects.filter(username=username).exists():
            return JsonResponse({'code': 0, 'msg': '账号已存在'})

        # 创建用户（密码加密）
        User.objects.create(
            username=username,
            password=make_password(password),  # 显式加密（避免模型未配置的情况）
            name=name,
            phone=phone
        )
        return JsonResponse({'code': 1, 'msg': '注册成功，请登录'})
    return JsonResponse({'code': 0, 'msg': '请求方式错误'})

def user_logout(request):
    """用户退出登录"""
    request.session.flush()
    return redirect('user:user_login')

def user_profile(request):
    """用户个人中心（整合所有模块逻辑）"""
    # 1. 验证用户是否登录（未登录跳转登录页）
    if not request.session.get('user_id'):
        messages.warning(request, "请先登录后访问个人中心！")
        return redirect('/user/login/')
    
    # 2. 获取当前登录用户信息
    user = get_object_or_404(User, id=request.session['user_id'])
    # 获取用户的收货地址（默认地址排前面）
    addresses = Address.objects.filter(user=user).order_by('-is_default')
    # 获取用户最近 5 条订单（按创建时间倒序）
    recent_orders = Order.objects.filter(user=user).order_by('-create_time')[:5]

    # 3. 处理 POST 请求（表单提交）
    if request.method == 'POST':
        # 3.1 编辑个人信息（昵称、手机号）
        if 'edit_info' in request.POST:
            nickname = request.POST.get('nickname', '').strip()
            phone = request.POST.get('phone', '').strip()
            # 简单验证
            if not nickname:
                messages.error(request, "昵称不能为空！")
            elif len(phone) != 11 and phone:  # 手机号可选填，填则必须11位
                messages.error(request, "手机号格式不正确！")
            else:
                user.name = nickname
                user.phone = phone
                user.save()
                messages.success(request, "个人信息修改成功！")
                return redirect('/user/profile/')  # 刷新页面
        
        # 3.2 新增/编辑收货地址
        elif 'save_address' in request.POST:
            address_id = request.POST.get('address_id', '')  # 编辑时传地址ID，新增时为空
            receiver = request.POST.get('receiver', '').strip()
            phone = request.POST.get('addr_phone', '').strip()
            detail = request.POST.get('addr_detail', '').strip()
            is_default = request.POST.get('is_default') == 'on'  # 是否设为默认

            # 验证
            if not (receiver and phone and detail):
                messages.error(request, "收件人、手机号、详细地址不能为空！")
                return redirect('/user/profile/')
            
            # 处理：新增地址 / 编辑地址
            if address_id:  # 编辑已有地址
                addr = get_object_or_404(Address, id=address_id, user=user)
            else:  # 新增地址
                addr = Address(user=user)
            
            # 如果设为默认，取消其他地址的默认状态
            if is_default:
                Address.objects.filter(user=user, is_default=True).update(is_default=False)
            
            # 保存地址信息
            addr.receiver = receiver
            addr.phone = phone
            addr.detail = detail
            addr.is_default = is_default
            addr.save()
            messages.success(request, "地址保存成功！")
            return redirect('/user/profile/')
        
        # 3.3 删除收货地址
        elif 'delete_address' in request.POST:
            address_id = request.POST.get('address_id')
            addr = get_object_or_404(Address, id=address_id, user=user)
            addr.delete()
            messages.success(request, "地址已删除！")
            return redirect('/user/profile/')
        
        # 3.4 修改密码
        elif 'change_password' in request.POST:
            old_pwd = request.POST.get('old_pwd', '').strip()
            new_pwd = request.POST.get('new_pwd', '').strip()
            confirm_pwd = request.POST.get('confirm_pwd', '').strip()

            # 验证
            if not check_password(old_pwd, user.password):
                messages.error(request, "原密码输入错误！")
            elif len(new_pwd) < 6:
                messages.error(request, "新密码长度不能少于 6 位！")
            elif new_pwd != confirm_pwd:
                messages.error(request, "两次输入的新密码不一致！")
            else:
                user.password = make_password(new_pwd)  # 加密保存新密码
                user.save()
                messages.success(request, "密码修改成功！请重新登录～")
                # 退出登录（修改密码后强制重新登录）
                del request.session['user_id']
                del request.session['user_name']
                return redirect('/user/login/')

    # 4. 组织数据传递给模板
    context = {
        'user': user,  # 当前用户信息
        'addresses': addresses,  # 收货地址列表
        'recent_orders': recent_orders,  # 最近订单
        # 订单状态映射（数字转中文）
        'order_status_map': {
            0: '待支付',
            1: '已支付',
            2: '已接单',
            3: '已完成',
            4: '已取消'
        }
    }
    return render(request, 'main/user/profile.html', context)

def user_order_list(request):
    """用户订单列表页面（修复关联名称 + 缩进格式错误）"""
    # 1. 登录验证
    if not request.session.get('user_id'):
        messages.warning(request, "请先登录后查看订单列表！")
        return redirect('user:user_login')
    
    # 2. 查询订单（关联商家、订单项、菜品）
    user_id = request.session['user_id']
    orders = Order.objects.filter(user_id=user_id) \
        .select_related('merchant') \
        .prefetch_related('items__dish') \
        .order_by('-create_time')
    
    # 3. 构建订单数据
    order_list = []
    for order in orders:
        order_items = []
        for item in order.items.all():  # 遍历关联名称 'items'
            order_items.append({
                'dish_name': item.dish.name,
                'price': float(item.price),
                'quantity': item.quantity,
                'subtotal': float(item.price * item.quantity)
            })
        order_list.append({
            'order': order,
            'merchant_name': order.merchant.name,
            'order_items': order_items,
            'status_text': {0: '待支付', 1: '已支付', 2: '已接单', 3: '已完成', 4: '已取消'}.get(order.status, '未知状态')
        })
    
    # 4. 传递数据到模板
    return render(request, 'main/user/order_list.html', {
        'order_list': order_list,
        'order_status_map': {0: 'badge bg-warning', 1: 'badge bg-info', 2: 'badge bg-primary', 3: 'badge bg-success', 4: 'badge bg-danger'}
    })

# 确认退出登录视图（已修复命名空间，避免反向解析失败）
def user_logout(request):
    """用户退出登录（正确重定向到登录页）"""
    request.session.flush()  # 清空所有session
    return redirect('user:user_login')  # 命名空间+视图名，反向解析正确

# 补充：用户最近订单API（之前缺失，导致报错）
@ensure_csrf_cookie
def user_recent_orders_api(request):
    """用户最近订单API：返回用户最近3条订单（用于首页/个人中心展示）"""
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'code': 0, 'msg': '请先登录'})
    
    # 查询用户最近3条订单（关联商家信息）
    orders = Order.objects.filter(
        user_id=user_id
    ).select_related('merchant').order_by('-create_time')[:3]
    
    order_list = []
    for order in orders:
        # 查询该订单的订单项数量（用于展示"x件商品"）
        item_count = OrderItem.objects.filter(order=order).count()
        order_list.append({
            'order_no': order.order_no,
            'merchant_name': order.merchant.name,
            'total_price': float(order.total_price),
            'create_time': order.create_time.strftime('%Y-%m-%d %H:%M'),
            'status': order.status,
            'status_text': {
                0: '待支付',
                1: '已支付',
                2: '已接单',
                3: '已完成',
                4: '已取消'
            }.get(order.status, '未知状态'),
            'item_count': item_count  # 商品件数
        })
    
    return JsonResponse({'code': 1, 'data': order_list})

def merchant_list(request):
    """商家列表页面"""
    return render(request, 'main/user/merchant_list.html')

def merchant_list_api(request):
    """商家列表API（支持搜索）"""
    keyword = request.GET.get('keyword', '')
    # 只显示已审核通过的商家（status=1）
    merchants = Merchant.objects.filter(status=1)
    if keyword:
        merchants = merchants.filter(
            Q(name__icontains=keyword) | 
            Q(category__icontains=keyword)
        )
    data = [{
        'id': m.id,
        'name': m.name,
        'category': m.category,
        'logo': m.logo or 'default_merchant.jpg',
        'score': float(m.score) if hasattr(m, 'score') else 4.5  # 兼容无score字段的情况
    } for m in merchants]
    return JsonResponse({'code': 1, 'data': data})

def dish_list_api(request):
    """菜品列表API（按商家ID查询）"""
    merchant_id = request.GET.get('merchant_id')
    if not merchant_id:
        return JsonResponse({'code': 0, 'msg': '商家ID不能为空'})
    dishes = Dish.objects.filter(merchant_id=merchant_id, status=1)  # 只显示上架菜品
    data = [{
        'id': d.id,
        'name': d.name,
        'category': d.category,
        'price': float(d.price),
        'stock': d.stock,
        'image': d.image or 'default_dish.jpg'
    } for d in dishes]
    return JsonResponse({'code': 1, 'data': data})

def address_list_api(request):
    """用户地址列表API（修复字段错误：name→receiver）"""
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'code': 0, 'msg': '请先登录'})
    addresses = Address.objects.filter(user_id=user_id)
    data = [{
        'id': a.id,
        'receiver': a.receiver,  # 原错误：a.name（Address模型无name字段，应为receiver）
        'phone': a.phone,
        'detail': a.detail,
        'is_default': a.is_default
    } for a in addresses]
    return JsonResponse({'code': 1, 'data': data})

@ensure_csrf_cookie
def submit_order_api(request):
    """提交订单API"""
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'code': 0, 'msg': '请先登录'})

    if request.method == 'POST':
        data = json.loads(request.body)
        merchant_id = data.get('merchant_id')
        delivery_type = data.get('delivery_type')
        delivery_info = data.get('delivery_info')
        pay_type = data.get('pay_type')
        order_items = data.get('order_items')

        if not (merchant_id and delivery_type is not None and delivery_info and pay_type is not None and order_items):
            return JsonResponse({'code': 0, 'msg': '参数不完整'})

        # 验证商家存在
        try:
            merchant = Merchant.objects.get(id=merchant_id, status=1)
        except Merchant.DoesNotExist:
            return JsonResponse({'code': 0, 'msg': '商家不存在或未通过审核'})

        # 计算总金额并验证库存
        total_price = 0
        for item in order_items:
            dish_id = item.get('dish_id')
            quantity = item.get('quantity', 1)
            try:
                dish = Dish.objects.get(id=dish_id, merchant_id=merchant_id, status=1)
            except Dish.DoesNotExist:
                return JsonResponse({'code': 0, 'msg': f'菜品不存在或已下架：{dish_id}'})
            if dish.stock < quantity:
                return JsonResponse({'code': 0, 'msg': f'菜品库存不足：{dish.name}'})
            total_price += dish.price * quantity

        # 创建订单（事务保证原子性）
        with transaction.atomic():
            order = Order.objects.create(
                order_no=generate_order_no(),
                user_id=user_id,
                merchant_id=merchant_id,
                total_price=total_price,
                delivery_type=delivery_type,
                delivery_info=delivery_info,
                pay_type=pay_type,
                status=0  # 0-待支付
            )

            # 创建订单项并扣减库存
            for item in order_items:
                dish_id = item.get('dish_id')
                quantity = item.get('quantity', 1)
                dish = Dish.objects.get(id=dish_id)
                OrderItem.objects.create(
                    order=order,
                    dish=dish,
                    quantity=quantity,
                    price=dish.price
                )
                # 扣减库存
                dish.stock -= quantity
                dish.save()

        return JsonResponse({
            'code': 1,
            'msg': '订单创建成功',
            'order_no': order.order_no,
            'order_id': order.id  # 新增订单ID，方便支付时使用
        })
    return JsonResponse({'code': 0, 'msg': '请求方式错误'})

def user_order_detail(request):
    """订单详情页面"""
    # 1. 登录验证（未登录跳转登录页）
    if not request.session.get('user_id'):
        messages.warning(request, "请先登录后查看订单详情！")
        return redirect('user:user_login')
    
    # 2. 获取订单号并验证
    order_no = request.GET.get('order_no')
    if not order_no:
        messages.error(request, "订单号不存在！")
        return redirect('user:user_order_list')
    
    # 3. 查询订单及关联数据（预取订单项和菜品信息，优化性能）
    try:
        order = Order.objects.filter(
            order_no=order_no, 
            user_id=request.session['user_id']
        ).select_related('merchant', 'user').first()
        
        if not order:
            messages.error(request, "订单不存在或不属于当前用户！")
            return redirect('user:user_order_list')
        
        # 4. 预计算每个订单项的小计（核心修复：避免模板算术运算）
        order_items = []
        for item in OrderItem.objects.filter(order=order).select_related('dish'):
            order_items.append({
                'dish_name': item.dish.name,
                'price': float(item.price),  # 确保浮点数格式
                'quantity': item.quantity,
                'subtotal': float(item.price * item.quantity)  # 预计算小计
            })
        
    except Exception as e:
        messages.error(request, f"查询订单失败：{str(e)}")
        return redirect('user:user_order_list')
    
    # 5. 组织数据传递给模板
    context = {
        'order': order,
        'order_items': order_items,  # 传递包含小计的字典列表
        'order_status_map': {
            0: '待支付',
            1: '已支付',
            2: '已接单',
            3: '已完成',
            4: '已取消'
        }
    }
    return render(request, 'main/user/order_detail.html', context)

# 补充：用户订单列表API（用于订单列表页异步加载）
@ensure_csrf_cookie
def user_order_list_api(request):
    """用户订单列表API（支持按状态筛选）"""
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'code': 0, 'msg': '请先登录'})
    
    # 筛选条件：状态（0-待支付/1-已支付/2-已接单/3-已完成/4-已取消）
    status = request.GET.get('status')
    orders = Order.objects.filter(user_id=user_id).select_related('merchant').order_by('-create_time')
    
    if status is not None and status.isdigit():
        status = int(status)
        if status in [0, 1, 2, 3, 4]:
            orders = orders.filter(status=status)
    
    # 构造返回数据
    order_list = []
    for order in orders:
        item_count = OrderItem.objects.filter(order=order).count()
        order_list.append({
            'order_no': order.order_no,
            'merchant_name': order.merchant.name,
            'total_price': float(order.total_price),
            'create_time': order.create_time.strftime('%Y-%m-%d %H:%M:%S'),
            'status': order.status,
            'status_text': {
                0: '待支付',
                1: '已支付',
                2: '已接单',
                3: '已完成',
                4: '已取消'
            }.get(order.status, '未知状态'),
            'item_count': item_count,
            'pay_time': order.pay_time.strftime('%Y-%m-%d %H:%M:%S') if order.pay_time else ''
        })
    
    return JsonResponse({'code': 1, 'data': order_list})

@ensure_csrf_cookie
def user_pay(request):
    """完善的用户支付功能（对接订单状态更新）"""
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('/user/login/')  # 未登录跳转登录页

    # GET请求：返回支付页面（携带订单号/订单ID）
    if request.method == 'GET':
        order_no = request.GET.get('order_no')
        order_id = request.GET.get('order_id')
        if not (order_no or order_id):
            return HttpResponse('缺少订单号参数')
        
        # 查询订单信息（支持按订单号或订单ID查询）
        try:
            if order_no:
                order = Order.objects.get(order_no=order_no, user_id=user_id)
            else:
                order = Order.objects.get(id=order_id, user_id=user_id)
        except Order.DoesNotExist:
            return HttpResponse('订单不存在或不属于当前用户')
        
        # 订单状态验证（只能支付待支付状态的订单）
        if order.status != 0:
            status_text = {0: '待支付', 1: '已支付', 2: '已接单', 3: '已完成', 4: '已取消'}.get(order.status, '未知状态')
            return HttpResponse(f'订单状态异常（当前状态：{status_text}）')
        
        # 传递订单信息到支付页面
        context = {
            'order_no': order.order_no,
            'total_price': float(order.total_price),
            'merchant_name': order.merchant.name,
            'pay_type': '校园卡' if order.pay_type == 0 else '微信'
        }
        return render(request, 'main/user/pay.html', context)

    # POST请求：处理支付提交
    elif request.method == 'POST':
        data = json.loads(request.body)
        order_no = data.get('order_no')
        if not order_no:
            return JsonResponse({'code': 0, 'msg': '订单号不能为空'})
        
        try:
            with transaction.atomic():
                # 1. 查询订单（加行锁，防止并发支付）
                order = Order.objects.select_for_update().get(order_no=order_no, user_id=user_id)
                
                # 2. 状态验证
                if order.status != 0:
                    return JsonResponse({'code': 0, 'msg': '订单已支付或已取消，无需重复支付'})
                
                # 3. 更新订单状态（0-待支付 → 1-已支付）
                order.status = 1
                order.pay_time = datetime.now()
                order.save()
        
            return JsonResponse({
                'code': 1,
                'msg': '支付成功',
                'redirect_url': '/user/order_list/'  # 支付成功跳转订单列表页
            })
        except Order.DoesNotExist:
            return JsonResponse({'code': 0, 'msg': '订单不存在'})
        except Exception as e:
            return JsonResponse({'code': 0, 'msg': f'支付失败：{str(e)}'})

    return JsonResponse({'code': 0, 'msg': '请求方式错误'})


# ---------------------- 商户端视图 ----------------------
def merchant_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        merchant = Merchant.objects.filter(username=username).first()
        
        if not merchant:
            messages.error(request, '商户账号不存在！')
        elif not check_password(password, merchant.password):
            messages.error(request, '密码错误！')
        elif merchant.status == 0:  # 待审核状态
            messages.error(request, '你的商户账号正在审核中，请耐心等待管理员通过！')
        elif merchant.status == 2:  # 已拒绝状态
            messages.error(request, '你的商户账号审核未通过，如需重新申请请联系管理员！')
        else:  # status == 1，已通过审核
            # 登录成功，设置Session
            request.session['merchant_id'] = merchant.id
            request.session['merchant_name'] = merchant.name
            return redirect('/merchant/dashboard/')  # 商户后台首页
    
    return render(request, 'main/merchant/login.html')

@ensure_csrf_cookie
def merchant_login_api(request):
    """商户登录API"""
    if request.method == 'POST':
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')

        try:
            merchant = Merchant.objects.get(username=username)
        except Merchant.DoesNotExist:
            return JsonResponse({'code': 0, 'msg': '商户账号不存在'})

        if merchant.status != 1:
            return JsonResponse({'code': 0, 'msg': '账号未通过审核或已被禁用'})

        if not check_password(password, merchant.password):
            return JsonResponse({'code': 0, 'msg': '密码错误'})

        request.session['merchant_id'] = merchant.id
        request.session['merchant_name'] = merchant.name
        return JsonResponse({'code': 1, 'msg': '登录成功'})
    return JsonResponse({'code': 0, 'msg': '请求方式错误'})

def merchant_register(request):
    """商户注册页面"""
    return render(request, 'main/merchant/register.html')

@ensure_csrf_cookie
def merchant_register_api(request):
    """商户注册API"""
    if request.method == 'POST':
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')
        name = data.get('name')
        category = data.get('category')

        if Merchant.objects.filter(username=username).exists():
            return JsonResponse({'code': 0, 'msg': '商户账号已存在'})

        # 创建商户（密码加密）
        Merchant.objects.create(
            username=username,
            password=make_password(password),  # 显式加密
            name=name,
            category=category,
            status=0  # 0-待审核
        )
        return JsonResponse({'code': 1, 'msg': '注册成功，请等待管理员审核'})
    return JsonResponse({'code': 0, 'msg': '请求方式错误'})

def merchant_logout(request):
    """商户退出登录"""
    request.session.flush()
    return redirect('merchant_login')

# 补充：商户中心视图（解决 urls.py 引用报错）
def merchant_profile(request):
    """商户中心（编辑商户信息、修改密码）"""
    # 1. 验证商户是否登录
    if not request.session.get('merchant_id'):
        messages.warning(request, "请先登录商户账号！")
        return redirect('/merchant/login/')
    
    # 2. 获取当前商户信息
    merchant = get_object_or_404(Merchant, id=request.session['merchant_id'])
    
    # 3. 处理 POST 请求（编辑信息/修改密码）
    if request.method == 'POST':
        # 3.1 编辑商户基本信息
        if 'edit_info' in request.POST:
            merchant_name = request.POST.get('merchant_name', '').strip()
            category = request.POST.get('category', '').strip()
            phone = request.POST.get('phone', '').strip()
            description = request.POST.get('description', '').strip()

            # 验证
            if not (merchant_name and category):
                messages.error(request, "商户名称和分类不能为空！")
                return redirect('/merchant/profile/')
            
            # 更新信息
            merchant.name = merchant_name
            merchant.category = category
            merchant.phone = phone
            merchant.description = description  # 假设Merchant模型有description字段（无则删除该行）
            merchant.save()
            messages.success(request, "商户信息修改成功！")
            return redirect('/merchant/profile/')
        
        # 3.2 修改密码
        elif 'change_password' in request.POST:
            old_pwd = request.POST.get('old_pwd', '').strip()
            new_pwd = request.POST.get('new_pwd', '').strip()
            confirm_pwd = request.POST.get('confirm_pwd', '').strip()

            # 验证
            if not check_password(old_pwd, merchant.password):
                messages.error(request, "原密码输入错误！")
            elif len(new_pwd) < 6:
                messages.error(request, "新密码长度不能少于6位！")
            elif new_pwd != confirm_pwd:
                messages.error(request, "两次输入的新密码不一致！")
            else:
                merchant.password = make_password(new_pwd)
                merchant.save()
                messages.success(request, "密码修改成功！请重新登录～")
                # 强制退出登录
                request.session.flush()
                return redirect('/merchant/login/')
    
    # 4. 传递数据到模板
    context = {
        'merchant': merchant
    }
    return render(request, 'main/merchant/profile.html', context)

def dish_list(request):
    """菜品管理页面"""
    return render(request, 'main/merchant/dish_list.html')

def merchant_dish_list_api(request):
    """商户查询自己的菜品API"""
    merchant_id = request.session.get('merchant_id')
    if not merchant_id:
        return JsonResponse({'code': 0, 'msg': '请先登录'})
    dishes = Dish.objects.filter(merchant_id=merchant_id)
    data = [{
        'id': d.id,
        'name': d.name,
        'category': d.category,
        'price': float(d.price),
        'stock': d.stock,
        'image': d.image or 'default_dish.jpg',
        'status': d.status,
        'status_text': '上架' if d.status == 1 else '下架'
    } for d in dishes]
    return JsonResponse({'code': 1, 'data': data})

@ensure_csrf_cookie
def add_dish_api(request):
    """新增菜品API（含图片上传）"""
    merchant_id = request.session.get('merchant_id')
    if not merchant_id:
        return JsonResponse({'code': 0, 'msg': '请先登录'})

    if request.method == 'POST':
        name = request.POST.get('name')
        category = request.POST.get('category')
        price = request.POST.get('price')
        stock = request.POST.get('stock')
        image = request.FILES.get('image')

        if not (name and category and price and stock):
            return JsonResponse({'code': 0, 'msg': '参数不完整'})

        # 验证价格和库存为有效数字
        try:
            price = float(price)
            stock = int(stock)
            if price <= 0 or stock < 0:
                return JsonResponse({'code': 0, 'msg': '价格必须大于0，库存不能为负数'})
        except ValueError:
            return JsonResponse({'code': 0, 'msg': '价格请输入数字，库存请输入整数'})

        # 处理图片（保存到static目录）
        image_name = None
        if image:
            # 验证图片格式
            allowed_ext = ['jpg', 'jpeg', 'png', 'gif']
            image_ext = image.name.split('.')[-1].lower()
            if image_ext not in allowed_ext:
                return JsonResponse({'code': 0, 'msg': '仅支持jpg、jpeg、png、gif格式图片'})
            
            # 生成唯一文件名
            image_name = f"{uuid.uuid4().hex}.{image_ext}"
            # 确保保存目录存在
            save_dir = os.path.join(settings.STATICFILES_DIRS[0], 'main', 'img', 'dish')
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)
            # 保存图片
            image_path = os.path.join(save_dir, image_name)
            with open(image_path, 'wb+') as f:
                for chunk in image.chunks():
                    f.write(chunk)

        # 创建菜品
        Dish.objects.create(
            merchant_id=merchant_id,
            name=name,
            category=category,
            price=price,
            stock=stock,
            image=image_name,
            status=1  # 1-上架
        )
        return JsonResponse({'code': 1, 'msg': '菜品新增成功'})
    return JsonResponse({'code': 0, 'msg': '请求方式错误'})

@ensure_csrf_cookie
def edit_dish_api(request):
    """补充：商户编辑菜品API（含图片更新）"""
    merchant_id = request.session.get('merchant_id')
    if not merchant_id:
        return JsonResponse({'code': 0, 'msg': '请先登录'})

    if request.method == 'POST':
        # 获取参数（支持普通字段和图片字段）
        dish_id = request.POST.get('dish_id')
        name = request.POST.get('name')
        category = request.POST.get('category')
        price = request.POST.get('price')
        stock = request.POST.get('stock')
        image = request.FILES.get('image')  # 可选：更新图片

        # 1. 必传参数验证
        if not (dish_id and name and category and price and stock):
            return JsonResponse({'code': 0, 'msg': '菜品ID、名称、分类、价格、库存为必填项'})

        # 2. 验证菜品存在且属于当前商户
        try:
            dish = Dish.objects.get(id=dish_id, merchant_id=merchant_id)
        except Dish.DoesNotExist:
            return JsonResponse({'code': 0, 'msg': '菜品不存在或无权编辑'})

        # 3. 价格和库存验证
        try:
            price = float(price)
            stock = int(stock)
            if price <= 0 or stock < 0:
                return JsonResponse({'code': 0, 'msg': '价格必须大于0，库存不能为负数'})
        except ValueError:
            return JsonResponse({'code': 0, 'msg': '价格请输入数字，库存请输入整数'})

        # 4. 处理图片更新（如有新图片上传）
        if image:
            allowed_ext = ['jpg', 'jpeg', 'png', 'gif']
            image_ext = image.name.split('.')[-1].lower()
            if image_ext not in allowed_ext:
                return JsonResponse({'code': 0, 'msg': '仅支持jpg、jpeg、png、gif格式图片'})
            
            # 生成唯一文件名
            image_name = f"{uuid.uuid4().hex}.{image_ext}"
            save_dir = os.path.join(settings.STATICFILES_DIRS[0], 'main', 'img', 'dish')
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)
            # 保存新图片
            image_path = os.path.join(save_dir, image_name)
            with open(image_path, 'wb+') as f:
                for chunk in image.chunks():
                    f.write(chunk)
            # 更新图片名称（旧图片可后续手动清理，或添加自动删除逻辑）
            dish.image = image_name

        # 5. 更新菜品信息
        dish.name = name
        dish.category = category
        dish.price = price
        dish.stock = stock
        dish.save()

        return JsonResponse({'code': 1, 'msg': '菜品编辑成功'})
    return JsonResponse({'code': 0, 'msg': '请求方式错误'})

@ensure_csrf_cookie
def delete_dish_api(request):
    """补充：商户删除菜品API"""
    merchant_id = request.session.get('merchant_id')
    if not merchant_id:
        return JsonResponse({'code': 0, 'msg': '请先登录'})

    if request.method == 'POST':
        data = json.loads(request.body)
        dish_id = data.get('dish_id')
        if not dish_id:
            return JsonResponse({'code': 0, 'msg': '菜品ID不能为空'})

        # 验证菜品存在且属于当前商户
        try:
            dish = Dish.objects.get(id=dish_id, merchant_id=merchant_id)
        except Dish.DoesNotExist:
            return JsonResponse({'code': 0, 'msg': '菜品不存在或无权删除'})

        # 执行删除（物理删除，如需逻辑删除可改为 dish.status=0 并 save()）
        dish.delete()
        return JsonResponse({'code': 1, 'msg': '菜品删除成功'})
    return JsonResponse({'code': 0, 'msg': '请求方式错误'})

@ensure_csrf_cookie
def change_dish_status_api(request):
    """修改菜品状态（上架/下架）API"""
    merchant_id = request.session.get('merchant_id')
    if not merchant_id:
        return JsonResponse({'code': 0, 'msg': '请先登录'})

    if request.method == 'POST':
        data = json.loads(request.body)
        dish_id = data.get('dish_id')
        status = data.get('status')  # 0-下架，1-上架

        try:
            dish = Dish.objects.get(id=dish_id, merchant_id=merchant_id)
        except Dish.DoesNotExist:
            return JsonResponse({'code': 0, 'msg': '菜品不存在'})

        # 验证状态值合法
        if status not in [0, 1]:
            return JsonResponse({'code': 0, 'msg': '状态值只能是0（下架）或1（上架）'})

        dish.status = status
        dish.save()
        return JsonResponse({'code': 1, 'msg': '状态修改成功'})
    return JsonResponse({'code': 0, 'msg': '请求方式错误'})

def merchant_order_list(request):
    """商户订单列表页面"""
    return render(request, 'main/merchant/order_list.html')

@ensure_csrf_cookie
def merchant_order_list_api(request):
    """补充：商户查询自己的订单API"""
    merchant_id = request.session.get('merchant_id')
    if not merchant_id:
        return JsonResponse({'code': 0, 'msg': '请先登录'})

    # 支持按状态筛选（0-待支付/1-已支付/2-已接单/3-已完成/4-已取消）
    status = request.GET.get('status')
    orders = Order.objects.filter(merchant_id=merchant_id)
    if status is not None and status.isdigit():
        status = int(status)
        if status in [0, 1, 2, 3, 4]:
            orders = orders.filter(status=status)

    # 按创建时间倒序排列（最新订单在前）
    orders = orders.order_by('-create_time')

    # 构造返回数据（包含订单项信息）
    data = []
    for order in orders:
        # 查询订单项
        order_items = OrderItem.objects.filter(order=order)
        items_data = [{
            'dish_name': item.dish.name,
            'quantity': item.quantity,
            'price': float(item.price),
            'total': float(item.price * item.quantity)
        } for item in order_items]

        data.append({
            'order_id': order.id,
            'order_no': order.order_no,
            'user_name': order.user.name,
            'total_price': float(order.total_price),
            'status': order.status,
            'status_text': {
                0: '待支付',
                1: '已支付',
                2: '已接单',
                3: '已完成',
                4: '已取消'
            }.get(order.status, '未知状态'),
            'delivery_type': '堂食' if order.delivery_type == 0 else '外卖',
            'delivery_info': order.delivery_info,
            'pay_type': '校园卡' if order.pay_type == 0 else '微信',
            'create_time': order.create_time.strftime('%Y-%m-%d %H:%M:%S'),
            'pay_time': order.pay_time.strftime('%Y-%m-%d %H:%M:%S') if order.pay_time else '',
            'items': items_data
        })
    return JsonResponse({'code': 1, 'data': data})

@ensure_csrf_cookie
def merchant_order_update_api(request):
    """补充：商户更新订单状态API（接单/完成/取消）"""
    merchant_id = request.session.get('merchant_id')
    if not merchant_id:
        return JsonResponse({'code': 0, 'msg': '请先登录'})

    if request.method == 'POST':
        data = json.loads(request.body)
        order_id = data.get('order_id')
        new_status = data.get('new_status')  # 2-已接单/3-已完成/4-已取消

        # 1. 参数验证
        if not (order_id and new_status in [2, 3, 4]):
            return JsonResponse({'code': 0, 'msg': '订单ID不能为空，状态只能是2（已接单）、3（已完成）、4（已取消）'})

        # 2. 验证订单存在且属于当前商户
        try:
            order = Order.objects.get(id=order_id, merchant_id=merchant_id)
        except Order.DoesNotExist:
            return JsonResponse({'code': 0, 'msg': '订单不存在或无权操作'})

        # 3. 状态流转合法性验证
        valid_transitions = {
            0: [],  # 待支付 → 不允许直接接单/完成/取消
            1: [2, 4],  # 已支付 → 可接单/取消
            2: [3, 4],  # 已接单 → 可完成/取消
            3: [],  # 已完成 → 不允许修改
            4: []   # 已取消 → 不允许修改
        }
        if new_status not in valid_transitions[order.status]:
            return JsonResponse({'code': 0, 'msg': f'当前订单状态（{order.status}）不允许修改为{new_status}'})

        # 4. 更新订单状态
        order.status = new_status
        order.save()
        return JsonResponse({'code': 1, 'msg': '订单状态更新成功'})
    return JsonResponse({'code': 0, 'msg': '请求方式错误'})

# 补充：商户后台仪表盘页面
def merchant_dashboard(request):
    """商户后台仪表盘（展示核心数据）"""
    if not request.session.get('merchant_id'):
        messages.warning(request, "请先登录商户账号！")
        return redirect('/merchant/login/')
    
    return render(request, 'main/merchant/dashboard.html')

# 补充：商户后台仪表盘API（用于展示核心数据）
@ensure_csrf_cookie
def merchant_dashboard_api(request):
    """商户仪表盘数据API（订单量、销售额、热销菜品）"""
    merchant_id = request.session.get('merchant_id')
    if not merchant_id:
        return JsonResponse({'code': 0, 'msg': '请先登录'})
    
    # 1. 今日核心数据
    today = datetime.now().date()
    today_orders = Order.objects.filter(merchant_id=merchant_id, create_time__date=today).count()
    today_sales = Order.objects.filter(
        merchant_id=merchant_id,
        create_time__date=today,
        status__in=[1,2,3]  # 已支付/已接单/已完成视为有效订单
    ).aggregate(total=Sum('total_price'))['total'] or 0.0

    # 2. 近7日订单趋势
    trend_data = []
    for i in range(6, -1, -1):
        date = (today - timedelta(days=i)).strftime('%m-%d')
        count = Order.objects.filter(
            merchant_id=merchant_id,
            create_time__date=(today - timedelta(days=i))
        ).count()
        trend_data.append({'date': date, 'order_count': count})

    # 3. 热销菜品Top3
    hot_dishes = []
    # 按订单项销量分组查询
    items = OrderItem.objects.filter(
        order__merchant_id=merchant_id,
        order__status__in=[1,2,3]
    ).values('dish__id', 'dish__name').annotate(
        total_quantity=Sum('quantity')
    ).order_by('-total_quantity')[:3]
    
    for item in items:
        hot_dishes.append({
            'dish_name': item['dish__name'],
            'sales_count': item['total_quantity']
        })

    return JsonResponse({
        'code': 1,
        'data': {
            'today_orders': today_orders,
            'today_sales': float(today_sales),
            'trend_data': trend_data,
            'hot_dishes': hot_dishes
        }
    })


# ---------------------- 管理员端视图 ----------------------
def admin_login(request):
    """管理员登录页面"""
    return render(request, 'main/admin/login.html')

@ensure_csrf_cookie
def admin_login_api(request):
    """管理员登录API"""
    if request.method == 'POST':
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')

        try:
            admin = Admin.objects.get(username=username)
        except Admin.DoesNotExist:
            return JsonResponse({'code': 0, 'msg': '管理员账号不存在'})

        if not check_password(password, admin.password):
            return JsonResponse({'code': 0, 'msg': '密码错误'})

        request.session['admin_id'] = admin.id
        request.session['admin_name'] = admin.name
        return JsonResponse({'code': 1, 'msg': '登录成功'})
    return JsonResponse({'code': 0, 'msg': '请求方式错误'})

def admin_logout(request):
    """管理员退出登录"""
    request.session.flush()
    return redirect('admin_login')

def merchant_audit(request):
    """商家审核页面"""
    return render(request, 'main/admin/merchant_audit.html')

@ensure_csrf_cookie
def merchant_audit_api(request):
    """商家审核API（查询/审核）"""
    admin_id = request.session.get('admin_id')
    if not admin_id:
        return JsonResponse({'code': 0, 'msg': '请先登录'})

    if request.method == 'GET':
        # 查询待审核商家（status=0）
        merchants = Merchant.objects.filter(status=0)
        data = [{
            'id': m.id,
            'username': m.username,
            'name': m.name,
            'category': m.category,
            'create_time': m.create_time.strftime('%Y-%m-%d %H:%M')
        } for m in merchants]
        return JsonResponse({'code': 1, 'data': data})

    elif request.method == 'POST':
        # 审核操作（通过/拒绝）
        data = json.loads(request.body)
        merchant_id = data.get('merchant_id')
        status = data.get('status')  # 1-通过，2-拒绝

        try:
            merchant = Merchant.objects.get(id=merchant_id)
        except Merchant.DoesNotExist:
            return JsonResponse({'code': 0, 'msg': '商家不存在'})

        merchant.status = status
        merchant.save()
        return JsonResponse({'code': 1, 'msg': '审核成功'})

    return JsonResponse({'code': 0, 'msg': '请求方式错误'})

def data_stat(request):
    """数据统计页面"""
    return render(request, 'main/admin/data_stat.html')

@ensure_csrf_cookie
def data_stat_api(request):
    """补充：数据统计API（给前端图表提供数据）"""
    admin_id = request.session.get('admin_id')
    if not admin_id:
        return JsonResponse({'code': 0, 'msg': '请先登录'})

    # 1. 核心数据概览
    total_user = User.objects.count()
    total_merchant = Merchant.objects.filter(status=1).count()
    total_order = Order.objects.count()
    # 修复：models.Sum → Sum（已导入Sum，无需models前缀）
    total_sales = Order.objects.filter(status__in=[1,2,3]).aggregate(
        total=Sum('total_price')
    )['total'] or 0

    # 2. 近7日订单趋势（简化版，实际可按日期分组）
    order_trend = []
    today = datetime.now().date()
    for i in range(6, -1, -1):
        date = (today - timedelta(days=i)).strftime('%Y-%m-%d')
        date_obj = datetime.strptime(date, '%Y-%m-%d').date()
        count = Order.objects.filter(create_time__date=date_obj).count()
        sales = Order.objects.filter(
            create_time__date=date_obj,
            status__in=[1,2,3]
        ).aggregate(total=Sum('total_price'))['total'] or 0
        order_trend.append({
            'date': date,
            'order_count': count,
            'sales_amount': float(sales)
        })

    # 3. 商家销售额排行（Top10）
    merchant_sales = []
    merchants = Merchant.objects.filter(status=1)
    for m in merchants:
        sales = Order.objects.filter(merchant=m, status__in=[1,2,3]).aggregate(
            total=Sum('total_price')
        )['total'] or 0
        if sales > 0:
            merchant_sales.append({
                'name': m.name,
                'sales': float(sales)
            })
    # 排序取前10
    merchant_sales.sort(key=lambda x: x['sales'], reverse=True)
    merchant_sales = merchant_sales[:10]

    # 4. 分类订单占比
    category_order = []
    categories = Merchant.objects.filter(status=1).values_list('category', flat=True).distinct()
    for cate in categories:
        merchant_ids = Merchant.objects.filter(category=cate, status=1).values_list('id', flat=True)
        count = Order.objects.filter(merchant_id__in=merchant_ids).count()
        if count > 0:
            category_order.append({
                'name': cate,
                'value': count
            })

    return JsonResponse({
        'code': 1,
        'data': {
            'core_stats': {
                'total_user': total_user,
                'total_merchant': total_merchant,
                'total_order': total_order,
                'total_sales': float(total_sales)
            },
            'order_trend': order_trend,
            'merchant_sales': merchant_sales,
            'category_order': category_order
        }
    })