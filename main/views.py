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
from django.contrib import messages
from .decorators import user_login_required, merchant_login_required, admin_login_required
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

@user_login_required
def user_logout(request):
    """用户退出登录"""
    request.session.flush()
    return redirect('user:user_login')

@user_login_required
def user_profile(request):
    """用户个人中心（整合所有模块逻辑）"""
    # 1. 获取当前登录用户信息
    user = get_object_or_404(User, id=request.session['user_id'])
    # 获取用户的收货地址（默认地址排前面）
    addresses = Address.objects.filter(user=user).order_by('-is_default')
    # 获取用户最近 5 条订单（按创建时间倒序）
    recent_orders = Order.objects.filter(user=user).order_by('-create_time')[:5]

    # 2. 处理 POST 请求（表单提交）
    if request.method == 'POST':
        # 2.1 编辑个人信息（昵称、手机号）
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
        
        # 2.2 新增/编辑收货地址
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
        
        # 2.3 删除收货地址
        elif 'delete_address' in request.POST:
            address_id = request.POST.get('address_id')
            addr = get_object_or_404(Address, id=address_id, user=user)
            addr.delete()
            messages.success(request, "地址已删除！")
            return redirect('/user/profile/')
        
        # 2.4 修改密码
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

    # 3. 组织数据传递给模板
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

@user_login_required
def user_order_list(request):
    """用户订单列表页面"""
    # 1. 查询订单（关联商家、订单项、菜品）
    user_id = request.session['user_id']
    orders = Order.objects.filter(user_id=user_id) \
        .select_related('merchant') \
        .prefetch_related('items__dish') \
        .order_by('-create_time')
    
    # 2. 构建订单数据
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

    # 3. 传递数据到模板
    return render(request, 'main/user/order_list.html', {
        'order_list': order_list,
        'order_status_map': {0: 'badge bg-warning', 1: 'badge bg-info', 2: 'badge bg-primary', 3: 'badge bg-success', 4: 'badge bg-danger'}
    })

@user_login_required
def user_recent_orders_api(request):
    """用户最近订单API：返回用户最近3条订单"""
    user_id = request.session.get('user_id')
    
    # 查询用户最近3条订单（关联商家信息）
    orders = Order.objects.filter(
        user_id=user_id
    ).select_related('merchant').order_by('-create_time')[:3]
    
    order_list = []
    for order in orders:
        # 查询该订单的订单项数量
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

@user_login_required
def address_list_api(request):
    """用户地址列表API"""
    user_id = request.session.get('user_id')
    
    addresses = Address.objects.filter(user_id=user_id)
    data = [{
        'id': a.id,
        'receiver': a.receiver,
        'phone': a.phone,
        'detail': a.detail,
        'is_default': a.is_default
    } for a in addresses]
    return JsonResponse({'code': 1, 'data': data})

@user_login_required
@ensure_csrf_cookie
def submit_order_api(request):
    """提交订单API"""
    user_id = request.session.get('user_id')

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
            'order_id': order.id
        })
    return JsonResponse({'code': 0, 'msg': '请求方式错误'})

@user_login_required
def user_order_detail(request):
    """订单详情页面"""
    # 1. 获取订单号并验证
    order_no = request.GET.get('order_no')
    if not order_no:
        messages.error(request, "订单号不存在！")
        return redirect('user:user_order_list')
    
    # 2. 查询订单及关联数据
    try:
        order = Order.objects.filter(
            order_no=order_no, 
            user_id=request.session['user_id']
        ).select_related('merchant', 'user').first()
        
        if not order:
            messages.error(request, "订单不存在或不属于当前用户！")
            return redirect('user:user_order_list')
        
        # 3. 预计算每个订单项的小计
        order_items = []
        for item in OrderItem.objects.filter(order=order).select_related('dish'):
            order_items.append({
                'dish_name': item.dish.name,
                'price': float(item.price),
                'quantity': item.quantity,
                'subtotal': float(item.price * item.quantity)
            })
        
    except Exception as e:
        messages.error(request, f"查询订单失败：{str(e)}")
        return redirect('user:user_order_list')
    
    # 4. 组织数据传递给模板
    context = {
        'order': order,
        'order_items': order_items,
        'order_status_map': {
            0: '待支付',
            1: '已支付',
            2: '已接单',
            3: '已完成',
            4: '已取消'
        }
    }
    return render(request, 'main/user/order_detail.html', context)

@user_login_required
@ensure_csrf_cookie
def user_order_list_api(request):
    """用户订单列表API（支持按状态筛选）"""
    user_id = request.session.get('user_id')
    
    # 筛选条件：状态
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

@user_login_required
@ensure_csrf_cookie
def user_pay(request):
    """用户支付功能"""
    user_id = request.session.get('user_id')

    # GET请求：返回支付页面
    if request.method == 'GET':
        order_no = request.GET.get('order_no')
        order_id = request.GET.get('order_id')
        if not (order_no or order_id):
            return HttpResponse('缺少订单号参数')
        
        # 查询订单信息
        try:
            if order_no:
                order = Order.objects.get(order_no=order_no, user_id=user_id)
            else:
                order = Order.objects.get(id=order_id, user_id=user_id)
        except Order.DoesNotExist:
            return HttpResponse('订单不存在或不属于当前用户')
        
        # 订单状态验证
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
                'redirect_url': '/user/order_list/'
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

@merchant_login_required
def merchant_logout(request):
    """商户退出登录"""
    request.session.flush()
    return redirect('merchant:merchant_login')

@merchant_login_required
def merchant_profile(request):
    """商户中心"""
    # 1. 获取当前商户信息
    merchant = get_object_or_404(Merchant, id=request.session['merchant_id'])
    
    # 2. 处理 POST 请求
    if request.method == 'POST':
        # 2.1 编辑商户基本信息
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
            merchant.description = description
            merchant.save()
            messages.success(request, "商户信息修改成功！")
            return redirect('/merchant/profile/')
        
        # 2.2 修改密码
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
    
    # 3. 传递数据到模板
    context = {
        'merchant': merchant
    }
    return render(request, 'main/merchant/profile.html', context)

@merchant_login_required
def dish_list(request):
    """菜品管理页面"""
    return render(request, 'main/merchant/dish_list.html')

@merchant_login_required
def merchant_dish_list_api(request):
    """商户查询自己的菜品API"""
    merchant_id = request.session.get('merchant_id')
    
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

@merchant_login_required
@ensure_csrf_cookie
def add_dish_api(request):
    """新增菜品API（含图片上传）"""
    merchant_id = request.session.get('merchant_id')

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
            image_name = f"dish_{uuid.uuid4().hex[:10]}.{image_ext}"
            image_path = os.path.join(settings.STATIC_ROOT, 'dish_images', image_name)
            os.makedirs(os.path.dirname(image_path), exist_ok=True)
            
            # 保存图片
            with open(image_path, 'wb+') as f:
                for chunk in image.chunks():
                    f.write(chunk)

        # 创建菜品
        dish = Dish.objects.create(
            merchant_id=merchant_id,
            name=name,
            category=category,
            price=price,
            stock=stock,
            image=f"dish_images/{image_name}" if image_name else None,
            status=1  # 默认上架
        )

        return JsonResponse({'code': 1, 'msg': '菜品添加成功', 'dish_id': dish.id})
    
    return JsonResponse({'code': 0, 'msg': '请求方式错误'})

@merchant_login_required
@ensure_csrf_cookie
def edit_dish_api(request):
    """编辑菜品API（支持更新基本信息和图片）"""
    merchant_id = request.session.get('merchant_id')

    if request.method == 'POST':
        # 获取前端传递的参数
        dish_id = request.POST.get('dish_id')
        name = request.POST.get('name')
        category = request.POST.get('category')
        price = request.POST.get('price')
        stock = request.POST.get('stock')
        status = request.POST.get('status')  # 可选：是否同步更新上下架状态
        image = request.FILES.get('image')  # 可选：新图片

        # 基础参数验证
        if not (dish_id and name and category and price and stock):
            return JsonResponse({'code': 0, 'msg': '参数不完整（需包含菜品ID、名称、分类、价格、库存）'})

        # 验证菜品是否存在且属于当前商户
        try:
            dish = Dish.objects.get(id=dish_id, merchant_id=merchant_id)
        except Dish.DoesNotExist:
            return JsonResponse({'code': 0, 'msg': '菜品不存在或无权限编辑'})

        # 验证价格和库存为有效数字（修正缩进错误）
        try:
            price = float(price)
            stock = int(stock)
            if price <= 0 or stock < 0:
                return JsonResponse({'code': 0, 'msg': '价格必须大于0，库存不能为负数'})
        except ValueError:
            return JsonResponse({'code': 0, 'msg': '价格请输入数字，库存请输入整数'})

        # 处理图片（如有新图片上传）
        if image:
            # 验证图片格式
            allowed_ext = ['jpg', 'jpeg', 'png', 'gif']
            image_ext = image.name.split('.')[-1].lower()
            if image_ext not in allowed_ext:
                return JsonResponse({'code': 0, 'msg': '仅支持jpg、jpeg、png、gif格式图片'})
            
            # 生成唯一文件名（避免重复）
            image_name = f"dish_{uuid.uuid4().hex[:10]}.{image_ext}"
            # 保存路径（假设项目static目录下有dish_images文件夹）
            image_path = os.path.join(settings.STATIC_ROOT, 'dish_images', image_name)
            os.makedirs(os.path.dirname(image_path), exist_ok=True)  # 确保目录存在
            
            # 保存图片
            with open(image_path, 'wb+') as f:
                for chunk in image.chunks():
                    f.write(chunk)
            dish.image = f"dish_images/{image_name}"  # 更新图片路径

        # 更新菜品基本信息
        dish.name = name
        dish.category = category
        dish.price = price
        dish.stock = stock
        if status is not None:  # 如传递了status参数，同步更新上下架状态
            dish.status = int(status)
        dish.save()

        return JsonResponse({'code': 1, 'msg': '菜品更新成功', 'dish_id': dish.id})
    
    return JsonResponse({'code': 0, 'msg': '请求方式错误（仅支持POST）'})

@merchant_login_required
@ensure_csrf_cookie
def change_dish_status_api(request):
    """修改菜品状态API（上下架切换）"""
    merchant_id = request.session.get('merchant_id')

    if request.method == 'POST':
        # 获取前端参数（菜品ID + 目标状态）
        data = json.loads(request.body)
        dish_id = data.get('dish_id')
        target_status = data.get('status')  # 1=上架，0=下架

        # 基础参数验证
        if dish_id is None or target_status not in [0, 1]:
            return JsonResponse({'code': 0, 'msg': '参数错误（菜品ID不能为空，状态只能是0或1）'})

        # 验证菜品是否存在且属于当前商户
        try:
            dish = Dish.objects.get(id=dish_id, merchant_id=merchant_id)
        except Dish.DoesNotExist:
            return JsonResponse({'code': 0, 'msg': '菜品不存在或无权限操作'})

        # 更新菜品状态
        dish.status = target_status
        dish.save()

        # 返回结果（包含当前状态文本）
        status_text = '上架' if target_status == 1 else '下架'
        return JsonResponse({
            'code': 1,
            'msg': f'菜品已成功{status_text}',
            'dish_id': dish.id,
            'current_status': target_status,
            'status_text': status_text
        })
    
    return JsonResponse({'code': 0, 'msg': '请求方式错误（仅支持POST）'})

# 新增：商户订单列表页面
@merchant_login_required
def merchant_order_list(request):
    """商户订单列表页面"""
    merchant_id = request.session.get('merchant_id')
    
    # 查询当前商户的所有订单（关联用户、订单项、菜品）
    orders = Order.objects.filter(merchant_id=merchant_id) \
        .select_related('user') \
        .prefetch_related('items__dish') \
        .order_by('-create_time')
    
    # 构建订单数据（供模板渲染）
    order_list = []
    for order in orders:
        order_items = []
        for item in order.items.all():
            order_items.append({
                'dish_name': item.dish.name,
                'price': float(item.price),
                'quantity': item.quantity,
                'subtotal': float(item.price * item.quantity)
            })
        order_list.append({
            'order': order,
            'user_name': order.user.name,
            'user_phone': order.user.phone,
            'order_items': order_items,
            'status_text': {
                0: '待支付',
                1: '已支付',
                2: '已接单',
                3: '已完成',
                4: '已取消'
            }.get(order.status, '未知状态'),
            'status_class': {
                0: 'badge bg-warning',
                1: 'badge bg-info',
                2: 'badge bg-primary',
                3: 'badge bg-success',
                4: 'badge bg-danger'
            }.get(order.status, 'badge bg-secondary')
        })
    
    return render(request, 'main/merchant/order_list.html', {
        'order_list': order_list
    })

# 新增：商户更新订单状态API
@merchant_login_required
@ensure_csrf_cookie
def merchant_order_update_api(request):
    """商户更新订单状态API（接单/完成/取消）"""
    merchant_id = request.session.get('merchant_id')
    
    if request.method == 'POST':
        data = json.loads(request.body)
        order_id = data.get('order_id')
        target_status = data.get('status')  # 2=已接单，3=已完成，4=已取消（商户仅能操作这三个状态）
        
        # 验证参数
        if order_id is None or target_status not in [2, 3, 4]:
            return JsonResponse({'code': 0, 'msg': '参数错误（订单ID不能为空，状态只能是2/3/4）'})
        
        # 验证订单是否存在且属于当前商户
        try:
            order = Order.objects.get(id=order_id, merchant_id=merchant_id)
        except Order.DoesNotExist:
            return JsonResponse({'code': 0, 'msg': '订单不存在或无权限操作'})
        
        # 验证状态流转合法性（避免非法状态变更）
        valid_status_flow = {
            1: [2, 4],    # 已支付 → 可接单/取消
            2: [3, 4],    # 已接单 → 可完成/取消
            3: [],        # 已完成 → 不可变更
            4: [],        # 已取消 → 不可变更
            0: []         # 待支付 → 商户不可操作
        }
        if target_status not in valid_status_flow.get(order.status, []):
            current_status_text = {0: '待支付', 1: '已支付', 2: '已接单', 3: '已完成', 4: '已取消'}.get(order.status)
            target_status_text = {2: '已接单', 3: '已完成', 4: '已取消'}.get(target_status)
            return JsonResponse({'code': 0, 'msg': f'非法状态变更（当前：{current_status_text} → 目标：{target_status_text}）'})
        
        # 更新订单状态
        order.status = target_status
        order.save()
        
        status_text = {2: '接单', 3: '完成', 4: '取消'}.get(target_status)
        return JsonResponse({'code': 1, 'msg': f'订单已成功{status_text}', 'order_id': order.id})
    
    return JsonResponse({'code': 0, 'msg': '请求方式错误（仅支持POST）'})

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

        # 设置管理员Session
        request.session['admin_id'] = admin.id
        request.session['admin_name'] = admin.username
        return JsonResponse({'code': 1, 'msg': '登录成功'})
    return JsonResponse({'code': 0, 'msg': '请求方式错误'})

@admin_login_required
def admin_logout(request):
    """管理员退出登录"""
    request.session.flush()
    return redirect('admin_login')

@admin_login_required
def merchant_audit(request):
    """商户审核页面"""
    return render(request, 'main/admin/merchant_audit.html')

@admin_login_required
@ensure_csrf_cookie
def merchant_audit_api(request):
    """商户审核API（查询待审核商户 + 处理审核结果）"""
    if request.method == 'GET':
        # 查询所有待审核商户（status=0）
        merchants = Merchant.objects.filter(status=0).order_by('-create_time')
        data = [{
            'id': m.id,
            'username': m.username,
            'name': m.name,
            'category': m.category,
            'create_time': m.create_time.strftime('%Y-%m-%d %H:%M:%S'),
            'phone': m.phone or '未填写'
        } for m in merchants]
        return JsonResponse({'code': 1, 'data': data})
    
    elif request.method == 'POST':
        # 处理审核结果（通过/拒绝）
        data = json.loads(request.body)
        merchant_id = data.get('merchant_id')
        audit_result = data.get('result')  # 1=通过，2=拒绝

        if merchant_id is None or audit_result not in [1, 2]:
            return JsonResponse({'code': 0, 'msg': '参数错误（商户ID不能为空，结果只能是1或2）'})

        try:
            merchant = Merchant.objects.get(id=merchant_id, status=0)
        except Merchant.DoesNotExist:
            return JsonResponse({'code': 0, 'msg': '商户不存在或已审核'})

        # 更新商户状态
        merchant.status = audit_result
        merchant.save()

        result_text = '通过' if audit_result == 1 else '拒绝'
        return JsonResponse({'code': 1, 'msg': f'审核{result_text}成功', 'merchant_id': merchant.id})
    
    return JsonResponse({'code': 0, 'msg': '请求方式错误'})

@admin_login_required
def data_stat(request):
    """数据统计页面（简单实现）"""
    # 统计核心数据
    total_users = User.objects.count()  # 总用户数
    total_merchants = Merchant.objects.count()  # 总商户数
    total_approved_merchants = Merchant.objects.filter(status=1).count()  # 已通过商户数
    total_orders = Order.objects.count()  # 总订单数
    total_sales = Order.objects.filter(status__in=[1,2,3]).aggregate(total=Sum('total_price'))['total'] or 0  # 总销售额（已支付/已接单/已完成）

    context = {
        'total_users': total_users,
        'total_merchants': total_merchants,
        'total_approved_merchants': total_approved_merchants,
        'total_orders': total_orders,
        'total_sales': round(float(total_sales), 2)
    }
    return render(request, 'main/admin/data_stat.html', context)