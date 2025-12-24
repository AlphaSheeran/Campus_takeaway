import os
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent

# 安全密钥（生产环境需修改）
SECRET_KEY = 'django-insecure-xxx-your-secret-key-xxx'

# 调试模式（生产环境设为False）
DEBUG = True

ALLOWED_HOSTS = ['*']  # 允许所有IP访问（生产环境需限制）

# 应用配置
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'main', 
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'campus_takeaway.urls'

# 模板配置
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'main/templates')], 
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'campus_takeaway.wsgi.application'

# 数据库配置（MySQL）
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',  # 数据库引擎（MySQL）
        'NAME': 'campus_takeaway',  # 项目专用数据库名
        'USER': 'root',  # MySQL 用户名（默认root）
        'PASSWORD': '123456',  # 之前设置的MySQL密码
        'HOST': 'localhost',  # 数据库地址（本地）
        'PORT': '3306',  # 数据库端口（默认3306）
        'OPTIONS': {
            'charset': 'utf8mb4'  # 字符集
        }
    }
}

# 密码验证
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True

# 静态文件配置
STATIC_URL = 'static/'
# 静态文件收集目录
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# 开发环境静态文件路径
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'main/static'),
]

# 默认主键类型
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Session配置（有效期1天）
SESSION_COOKIE_AGE = 3600 * 24

# 媒体文件配置，用户上传的图片等
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')  # 本地保存路径
MEDIA_URL = '/media/'  # 访问URL前缀

SESSION_ENGINE = 'django.contrib.sessions.backends.db'  # 使用数据库存储session
SESSION_COOKIE_NAME = 'sessionid'  # 默认值
SESSION_COOKIE_SECURE = False  # 本地开发设为False（HTTPS环境设为True）
SESSION_COOKIE_HTTPONLY = True  # 安全配置
SESSION_COOKIE_PATH = '/'  # 确保session作用于全站
SESSION_COOKIE_AGE = 86400  # session默认有效期1天，和API中保持一致
SESSION_SAVE_EVERY_REQUEST = True  # 每次请求都保存session，避免失效
SESSION_EXPIRE_AT_BROWSER_CLOSE = False  # 浏览器关闭后不立即失效