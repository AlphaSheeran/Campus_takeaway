from django.contrib import admin
from .models import Merchant

@admin.register(Merchant)
class MerchantAdmin(admin.ModelAdmin):
    # 1. 后台列表显示的字段
    list_display = ['id', 'username', 'name', 'category', 'score', 'status_display', 'create_time']
    # 2. 可筛选字段
    list_filter = ['status']
    # 3. 可搜索字段
    search_fields = ['username', 'name']
    # 4. 编辑页面显示的字段
    fields = ['name', 'category', 'logo', 'score', 'status']
    # 5. 只读字段
    readonly_fields = ['username', 'create_time']

    # 自定义方法：把数字status转成中文显示
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