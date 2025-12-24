from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),  # Django自带管理员后台，用于通过商家或初始化数据
    path('', include('main.urls')),   # 主应用URL
]

if settings.DEBUG:
    # 静态文件访问配置
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
    # 媒体文件访问配置
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)