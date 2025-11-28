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
    """用户订单列表页面（修复关联名称 + 缩进格式错误）"""
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
    """用户最近订单API：返回用户最近3条订单（用于首页/个人中心展示）"""
    user_id = request.session.get('user_id')
    
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

@user_login_required
def address_list_api(request):
    """用户地址列表API（修复字段错误：name→receiver）"""
    user_id = request.session.get('user_id')
    
    addresses = Address.objects.filter(user_id=user_id)
    data = [{
        'id': a.id,
        'receiver': a.receiver,  # 原错误：a.name（Address模型无name字段，应为receiver）
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
            'order_id': order.id  # 新增订单ID，方便支付时使用
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
    
    # 2. 查询订单及关联数据（预取订单项和菜品信息，优化性能）
    try:
        order = Order.objects.filter(
            order_no=order_no, 
            user_id=request.session['user_id']
        ).select_related('merchant', 'user').first()
        
        if not order:
            messages.error(request, "订单不存在或不属于当前用户！")
            return redirect('user:user_order_list')
        
        # 3. 预计算每个订单项的小计（核心修复：避免模板算术运算）
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
    
    # 4. 组织数据传递给模板
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

@user_login_required
@ensure_csrf_cookie
def user_order_list_api(request):
    """用户订单列表API（支持按状态筛选）"""
    user_id = request.session.get('user_id')
    
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

@user_login_required
@ensure_csrf_cookie
def user_pay(request):
    """完善的用户支付功能（对接订单状态更新）"""
    user_id = request.session.get('user_id')

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

@merchant_login_required
def merchant_logout(request):
    """商户退出登录"""
    request.session.flush()
    return redirect('merchant_login')

@merchant_login_required
def merchant_profile(request):
    """商户中心（编辑商户信息、修改密码）"""
    # 1. 获取当前商户信息
    merchant = get_object_or_404(Merchant, id=request.session['merchant_id'])
    
    # 2. 处理 POST 请求（编辑信息/修改密码）
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
            merchant.description = description  # 假设Merchant模型有description字段（无则删除该行）
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