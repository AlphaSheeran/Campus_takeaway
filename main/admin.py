from django.contrib import admin
from .models import Merchant  # 导入你的原Merchant模型

@admin.register(Merchant)
class MerchantAdmin(admin.ModelAdmin):
    # 1. 后台列表显示的字段（只选模型中存在的字段）
    list_display = ['id', 'username', 'name', 'category', 'score', 'status_display', 'create_time']
    # 2. 可筛选字段（用status字段，方便快速找待审核商户）
    list_filter = ['status']
    # 3. 可搜索字段（按商户账号、店铺名称搜索）
    search_fields = ['username', 'name']
    # 4. 编辑页面显示的字段（管理员可修改的字段）
    fields = ['name', 'category', 'logo', 'score', 'status']
    # 5. 只读字段（不允许修改的字段，如账号、创建时间）
    readonly_fields = ['username', 'create_time']

    # 自定义方法：把数字status转成中文显示（优化体验）
    def status_display(self, obj):
        """将 status 0/1/2 转换为中文描述"""
        status_map = {
            0: '待审核',
            1: '已通过',
            2: '已拒绝'
        }
        return status_map.get(obj.status, '未知状态')
    
    # 给自定义字段设置表头名称
    status_display.short_description = '审核状态'