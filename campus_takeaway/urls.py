from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),  # Django自带管理员后台（可用于初始化数据）
    path('', include('main.urls')),   # 主应用URL
]

# 开发环境下提供静态文件访问（生产环境需Nginx配置）
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
