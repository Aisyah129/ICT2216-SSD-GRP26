# -*- encoding: utf-8 -*-
"""
License: MIT
"""

import os
from unipath import Path
import pymysql
from base64 import b64decode
from dotenv import load_dotenv

# Optional: Load .env only for local development
load_dotenv()

# Decode AES key from base64 string
AES_KEY = b64decode(os.environ.get('AES_KEY', ''))

pymysql.install_as_MySQLdb()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_DIR = Path(__file__).parent

# Security
SECRET_KEY = os.environ.get('SECRET_KEY')
DEBUG = os.environ.get('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = ['3.129.248.34', 'localhost', '127.0.0.1']

# Installed apps
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'authentication',
    'django_recaptcha'
]

# Middleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'authentication.middleware.SessionTimeoutMiddleware',
    'csp.middleware.CSPMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Clickjacking and Security Headers
X_FRAME_OPTIONS = "DENY"
CSP_FRAME_ANCESTORS = ["'none'"]
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_BROWSER_XSS_FILTER = True
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_EMBEDDER_POLICY = "require-corp"

ROOT_URLCONF = 'core.urls'
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "login"

TEMPLATE_DIR = os.path.join(BASE_DIR, "core/templates")

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [TEMPLATE_DIR],
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

# reCAPTCHA keys
RECAPTCHA_PUBLIC_KEY = os.environ.get('RECAPTCHA_PUBLIC_KEY', '')
RECAPTCHA_PRIVATE_KEY = os.environ.get('RECAPTCHA_PRIVATE_KEY', '')
SILENCED_SYSTEM_CHECKS = ['captcha.recaptcha_test_key_error']

WSGI_APPLICATION = 'core.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DB_NAME'),
        'USER': os.environ.get('DB_USER'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '3306'),
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        }
    }
}

# Stripe
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")
STRIPE_PRICE_ID_WEEK = os.environ.get("STRIPE_PRICE_ID_WEEK")
STRIPE_PRICE_ID_MONTH = os.environ.get("STRIPE_PRICE_ID_MONTH")
STRIPE_PRICE_ID_QUARTER = os.environ.get("STRIPE_PRICE_ID_QUARTER")

# MongoDB
MONGO_URI = os.environ.get("MONGO_URI")
MONGO_DB = os.environ.get("MONGO_DB_NAME", "chat_db")

# AWS S3
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME")
AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME", "ap-southeast-1")
AWS_S3_ENDPOINT = f"https://{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com"

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True

STATIC_URL = '/static/'

# For production: collectstatic will dump everything here
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Where Django looks for static files in your apps during collectstatic
STATICFILES_DIRS = (
    os.path.join(BASE_DIR, "core/static"),
)
# Custom user model
AUTH_USER_MODEL = 'authentication.User'

# Session behavior
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# ImageKit
IMAGEKIT_URL_ENDPOINT = os.environ.get("IMAGEKIT_URL_ENDPOINT")
IMAGEKIT_PUBLIC_KEY = os.environ.get("IMAGEKIT_PUBLIC_KEY")
IMAGEKIT_PRIVATE_KEY = os.environ.get("IMAGEKIT_PRIVATE_KEY")

# SendGrid
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")
DEFAULT_FROM_EMAIL = os.environ.get("FROM_EMAIL")

# Login page for @login_required
LOGIN_URL = '/login/'

# Content Security Policy (CSP)
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = (
    "'self'",
    "'nonce'",
    "https://cdn.jsdelivr.net",
    "https://fonts.googleapis.com",
    "https://fonts.gstatic.com",
    "https://js.stripe.com",
)
CSP_STYLE_SRC = (
    "'self'",
    "'nonce'",
    "https://fonts.googleapis.com",
)
CSP_IMG_SRC = (
    "'self'",
    "data:",
)
CSP_FONT_SRC = (
    "'self'",
    "https://fonts.gstatic.com",
)
CSP_CONNECT_SRC = (
    "'self'",
    "https://api.stripe.com",
    "https://js.stripe.com",
)
