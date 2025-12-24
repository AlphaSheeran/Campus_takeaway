from django.urls import path, include
from . import views

# ---------------------- 1. 用户端路由 ---------------------------------------------------------
user_urlpatterns = [
    path('', views.user_index, name='user_index'),  # /user/
    path('login/', views.user_login, name='user_login'),  # /user/login/
    path('login/api/', views.user_login_api, name='user_login_api'),
    path('register/', views.user_register, name='user_register'),  # /user/register/
    path('register/api/', views.user_register_api, name='user_register_api'),
    path('logout/', views.user_logout, name='user_logout'),  # /user/logout/
    path('merchant/list/', views.merchant_list, name='merchant_list'),
    path('merchant/list/api/', views.merchant_list_api, name='merchant_list_api'),
    path('dish/list/api/', views.dish_list_api, name='dish_list_api'),
    path('address/list/api/', views.address_list_api, name='address_list_api'),
    path('submit/order/api/', views.submit_order_api, name='submit_order_api'),
    path('order/list/', views.user_order_list, name='user_order_list'),  # /user/order/list/
    path('order/detail/', views.user_order_detail, name='user_order_detail'),
    path('order/recent/api/', views.user_recent_orders_api, name='user_recent_orders_api'),  # 最近订单API
    path('order/cancel/api/', views.cancel_order_api, name='cancel_order_api'),
    path('pay/', views.user_pay, name='user_pay'),  # /user/pay/
    path('profile/', views.user_profile, name='user_profile'),  # /user/profile/

]

# ---------------------- 2. 商户端路由 ----------------------------------------------------------
merchant_urlpatterns = [
    path('login/', views.merchant_login, name='merchant_login'),
    path('login/api/', views.merchant_login_api, name='merchant_login_api'),
    path('register/', views.merchant_register, name='merchant_register'),
    path('register/api/', views.merchant_register_api, name='merchant_register_api'),
    path('logout/', views.merchant_logout, name='merchant_logout'),
    path('dish/list/', views.dish_list, name='dish_list'),
    path('dish/list/api/', views.merchant_dish_list_api, name='merchant_dish_list_api'),
    path('dish/detail/api/', views.dish_detail_api, name='dish_detail_api'),
    path('add/dish/api/', views.add_dish_api, name='add_dish_api'),
    path('edit/dish/api/', views.edit_dish_api, name='edit_dish_api'),
    path('change/dish/status/api/', views.change_dish_status_api, name='change_dish_status_api'),
    path('delete/dish/api/', views.delete_dish_api, name='delete_dish_api'),
    path('order/list/', views.merchant_order_list, name='merchant_order_list'),
    path('order/update/api/', views.merchant_order_update_api, name='merchant_order_update_api'),
    path('profile/', views.merchant_profile, name='merchant_profile'),  # 商户中心
    path('profile/update/logo/api/', views.merchant_logo_update_api, name='merchant_logo_update'),
]

# ---------------------- 3. 根路径和各端路由入口 -------------------------------------------------
urlpatterns = [
    # 根路径http://127.0.0.1:8000/指向用户首页
    path('', views.user_index, name='root_index'),
    # 用户端路由
    path('user/', include((user_urlpatterns, 'main'), namespace='user')),
    # 商户端路由
    path('merchant/', include((merchant_urlpatterns, 'main'), namespace='merchant')),
    # 管理员端路由
    path('admin/login/', views.admin_login, name='admin_login'),
    path('admin/login/api/', views.admin_login_api, name='admin_login_api'),
    path('admin/logout/', views.admin_logout, name='admin_logout'),
    path('admin/merchant/audit/', views.merchant_audit, name='merchant_audit'),
    path('admin/merchant/audit/api/', views.merchant_audit_api, name='merchant_audit_api'),
    path('admin/data/stat/', views.data_stat, name='data_stat'),
]