# -*- encoding: utf-8 -*-
"""
License: MIT
Copyright (c) 2019 - present AppSeed.us
"""

import os
from decouple import config
from unipath import Path
import pymysql
from base64 import b64decode
import sys

AES_KEY = b64decode(config('AES_KEY'))  # This will load the AES key from .env

pymysql.install_as_MySQLdb()

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_DIR = Path(__file__).parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = ['www.aisteadmai.shop', 'aisteadmai.shop','3.129.248.34', 'localhost', '127.0.0.1']

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'authentication',  
    'django_recaptcha',
    'axes',

]

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
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    'authentication.middleware.SessionValidationMiddleware',
]


CSRF_TRUSTED_ORIGINS = ['https://www.aisteadmai.shop',
    'https://aisteadmai.shop',]

# Prevent clickjacking
X_FRAME_OPTIONS = "DENY"
CSP_FRAME_ANCESTORS = ["'none'"]

# Secure cookies
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 1800  #30 minutes

# Referrer Policy
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# Browser XSS Protection
SECURE_BROWSER_XSS_FILTER = True

# Permissions Policy (optional)
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_EMBEDDER_POLICY = "require-corp"


ROOT_URLCONF = 'core.urls'
LOGIN_REDIRECT_URL = "home"   # Route defined in app/urls.py
LOGOUT_REDIRECT_URL = "home"  # Route defined in app/urls.py
TEMPLATE_DIR = os.path.join(BASE_DIR, "core/templates")  # ROOT dir for templates

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

RECAPTCHA_PUBLIC_KEY = config("RECAPTCHA_PUBLIC_KEY")
RECAPTCHA_PRIVATE_KEY = config("RECAPTCHA_PRIVATE_KEY")
SILENCED_SYSTEM_CHECKS = config("SILENCED_SYSTEM_CHECKS")

WSGI_APPLICATION = 'core.wsgi.application'

# Database
# https://docs.djangoproject.com/en/3.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': config('DB_NAME'),         # ssd_db
        'USER': config('DB_USER'),         # root
        'PASSWORD': config('DB_PASSWORD'), # your password
        'HOST': config('DB_HOST'),
        'PORT': config('DB_PORT', default='3306'),
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        }
    }
}

#Stripe
STRIPE_PUBLISHABLE_KEY = config("STRIPE_PUBLISHABLE_KEY")
STRIPE_SECRET_KEY      = config("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET  = config("STRIPE_WEBHOOK_SECRET")
STRIPE_PRICE_ID_WEEK  = config("STRIPE_PRICE_ID_WEEK")
STRIPE_PRICE_ID_MONTH  = config("STRIPE_PRICE_ID_MONTH")
STRIPE_PRICE_ID_QUARTER  = config("STRIPE_PRICE_ID_QUARTER")

#NOSQL DB
MONGO_URI = config("MONGO_URI")
MONGO_DB = config("MONGO_DB_NAME")

#S3 Bucket Amazon
AWS_ACCESS_KEY_ID        = config("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY    = config("AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME  = config("AWS_STORAGE_BUCKET_NAME")
AWS_S3_REGION_NAME       = config("AWS_S3_REGION_NAME", default="ap-southeast-1")
AWS_S3_ENDPOINT          = f"https://{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com"

# Password validation
# https://docs.djangoproject.com/en/3.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# https://docs.djangoproject.com/en/3.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.0/howto/static-files/

STATIC_URL = '/static/'

# For production
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# For development (optional, if you want to load from app folders too)
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "core/static"),
]

AUTH_USER_MODEL = 'authentication.User'

LOGOUT_REDIRECT_URL = 'login'

SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# ImageKit Settings
IMAGEKIT_URL_ENDPOINT = config('IMAGEKIT_URL_ENDPOINT')

SENDGRID_API_KEY = config("SENDGRID_API_KEY")
DEFAULT_FROM_EMAIL = config("FROM_EMAIL")

# if someone tries to access a login-protected page, redirect them to /login/
LOGIN_URL = '/login/'

# -------------------------------
# CSP (Content Security Policy)
# -------------------------------
CSP_DEFAULT_SRC = ("'self'",)

CSP_SCRIPT_SRC = (
    "'self'",          # Allow scripts from your own domain
    "'nonce'",         # Enable nonce-based inline scripts
    "https://cdn.jsdelivr.net",   # Bootstrap 5
    "https://fonts.googleapis.com",  # Google Fonts
    "https://fonts.gstatic.com",     # Google Fonts static
    "https://js.stripe.com",         # Stripe.js
)

CSP_STYLE_SRC = (
    "'self'",
    "'nonce'",  # Enable nonce-based inline styles
    "https://fonts.googleapis.com",
)

CSP_IMG_SRC = (
    "'self'",
    "data:",  # Allow inline images (avatars, icons)
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

# Axes config
from datetime import timedelta
# Lockout after 5 failed attempts
AXES_FAILURE_LIMIT = 5

# Lockout duration: 10 minutes
AXES_COOLOFF_TIME = timedelta(minutes=10)

# Lockout is triggered after the failure limit is hit
AXES_LOCK_OUT_AT_FAILURE = True

# Lock out based on IP and user-agent (more secure)
AXES_LOCK_OUT_BY_IP_AND_USER_AGENT = True

# Count failures across users per IP (optional: False to count per username)
AXES_ONLY_USER_FAILURES = False

AXES_RAISE_PERMISSION_DENIED = False


AUTHENTICATION_BACKENDS = [
    'core.authentication_backend.CustomBackendForAxes',
    'django.contrib.auth.backends.ModelBackend',
]

TESTING = 'test' in sys.argv