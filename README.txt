------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
软件工程实验校园外卖平台使用前配置（必看）：

1.安装好python以及必备依赖后（pip requirements），以管理员身份运行命令提示符：cd /d "C:\YOUR_PATH\campus_takeaway"

2.输入.\venv\Scripts\Activate激活权限

3.启动MySQL服务net start MySQL

4.在命令提示符中：
# 登录MySQL
mysql -u root -p  
# 创建数据库
CREATE DATABASE campus_takeaway_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;  
exit

5.生成迁移文件：
python manage.py makemigrations

6.执行迁移
python manage.py migrate

7. 创建超级管理员（用于登录Django Admin后台管理数据）
python manage.py createsuperuser  
------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
完成以上部署后，日常启动django:
1.以管理员身份运行命令提示符：cd /d "C:\YOUR_PATH\campus_takeaway" /    cd /d "D:\BaiduNetdiskDownload\gooledownload\大三上\软工实验\system\campus_takeaway"

2.激活权限.\venv\Scripts\Activate

3.启动服务python manage.py runserver

------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
通过浏览器在开启服务后可访问的网页：
http://127.0.0.1:8000/	项目首页（用户首页）	user_index
http://127.0.0.1:8000/user/login/	用户登录页面	user_login
http://127.0.0.1:8000/user/register/	用户注册页面	user_register
http://127.0.0.1:8000/merchant/login/	商户登录页面	merchant_login
http://127.0.0.1:8000/merchant/register/	商户注册页面	merchant_register

http://127.0.0.1:8000/user/merchant/list/	商家列表页面	merchant_list
http://127.0.0.1:8000/user/order/list/	我的订单列表页面	user_order_list
http://127.0.0.1:8000/user/pay/?order_no=xxx	订单支付页面（xxx 替换为实际订单号）	user_pay
http://127.0.0.1:8000/user/logout/	用户退出登录（跳转登录页）	user_logout

http://127.0.0.1:8000/merchant/dish/list/	菜品管理页面（新增 / 编辑 / 删除菜品）	dish_list
http://127.0.0.1:8000/merchant/order/list/	商户订单列表页面（接单 / 完成 / 取消订单）	merchant_order_list
http://127.0.0.1:8000/merchant/logout/	商户退出登录（跳转登录页）	merchant_logout

http://127.0.0.1:8000/admin/	Django 自带后台（管理所有数据库数据）	需用 createsuperuser 创建的超级用户登录
