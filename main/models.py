from django.db import models
from django.contrib.auth.hashers import make_password

# 用户表（学生/老师）
class User(models.Model):
    username = models.CharField(max_length=50, unique=True, verbose_name="账号（手机号/校园卡号）")
    password = models.CharField(max_length=128, verbose_name="密码")
    name = models.CharField(max_length=50, verbose_name="姓名")
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="电话")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    def save(self, *args, **kwargs):
        # 密码加密存储（避免重复加密）
        if not self.password.startswith('pbkdf2_sha256$'):  # 判断是否已加密
            self.password = make_password(self.password)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "用户"
        verbose_name_plural = "用户"

# 地址表（用户配送地址）
class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="addresses", verbose_name="所属用户")
    name = models.CharField(max_length=50, verbose_name="收件人")
    phone = models.CharField(max_length=20, verbose_name="联系电话")
    detail = models.CharField(max_length=200, verbose_name="详细地址")
    is_default = models.BooleanField(default=False, verbose_name="是否默认地址")

    class Meta:
        verbose_name = "地址"
        verbose_name_plural = "地址"

# 商户表（食堂/店铺）
class Merchant(models.Model):
    username = models.CharField(max_length=50, unique=True, verbose_name="商户账号")
    password = models.CharField(max_length=128, verbose_name="密码")
    name = models.CharField(max_length=100, verbose_name="店铺名称")
    category = models.CharField(max_length=50, verbose_name="分类（快餐/奶茶等）")
    logo = models.CharField(max_length=200, blank=True, null=True, verbose_name="店铺logo")
    score = models.DecimalField(max_digits=3, decimal_places=1, default=5.0, verbose_name="评分")
    # 状态：0-待审核/1-已通过/2-已拒绝
    status = models.IntegerField(default=0, verbose_name="状态（0-待审核/1-已通过/2-已拒绝）")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    def save(self, *args, **kwargs):
        if not self.password.startswith('pbkdf2_sha256$'):
            self.password = make_password(self.password)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "商户"
        verbose_name_plural = "商户"

# 菜品表
class Dish(models.Model):
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="dishes", verbose_name="所属商户")
    name = models.CharField(max_length=100, verbose_name="菜品名称")
    category = models.CharField(max_length=50, verbose_name="菜品分类")
    price = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="单价")
    stock = models.IntegerField(default=0, verbose_name="库存")
    image = models.CharField(max_length=200, blank=True, null=True, verbose_name="菜品图片")
    # 状态：0-下架/1-上架
    status = models.IntegerField(default=1, verbose_name="状态（0-下架/1-上架）")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "菜品"
        verbose_name_plural = "菜品"

# 订单表
class Order(models.Model):
    order_no = models.CharField(max_length=50, unique=True, verbose_name="订单号")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders", verbose_name="下单用户")
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="orders", verbose_name="所属商户")
    total_price = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="总金额")
    # 配送方式：0-堂食/1-外卖
    delivery_type = models.IntegerField(verbose_name="配送方式（0-堂食/1-外卖）")
    delivery_info = models.CharField(max_length=200, verbose_name="配送信息（地址/取餐时间）")
    # 支付方式：0-校园卡/1-微信
    pay_type = models.IntegerField(verbose_name="支付方式（0-校园卡/1-微信）")
    # 状态：0-待支付/1-已支付/2-已接单/3-已完成/4-已取消
    status = models.IntegerField(default=0, verbose_name="状态（0-待支付/1-已支付/2-已接单/3-已完成/4-已取消）")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    pay_time = models.DateTimeField(blank=True, null=True, verbose_name="支付时间")

    def get_status_text(self):
        """统一订单状态文本描述"""
        status_map = {
            0: '待支付',
            1: '已支付',
            2: '已接单',
            3: '已完成',
            4: '已取消'
        }
        return status_map.get(self.status, '未知状态')

    class Meta:
        verbose_name = "订单"
        verbose_name_plural = "订单"

# 订单项表（订单包含的菜品）
class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items", verbose_name="所属订单")
    dish = models.ForeignKey(Dish, on_delete=models.CASCADE, verbose_name="菜品")
    quantity = models.IntegerField(verbose_name="数量")
    price = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="下单时单价")  # 记录下单时价格

    class Meta:
        verbose_name = "订单项"
        verbose_name_plural = "订单项"

# 管理员表
class Admin(models.Model):
    username = models.CharField(max_length=50, unique=True, verbose_name="管理员账号")
    password = models.CharField(max_length=128, verbose_name="密码")
    name = models.CharField(max_length=50, verbose_name="姓名")

    def save(self, *args, **kwargs):
        if not self.password.startswith('pbkdf2_sha256$'):
            self.password = make_password(self.password)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "管理员"
        verbose_name_plural = "管理员"