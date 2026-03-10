import os
import environ
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False)
)
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

SECRET_KEY = env('SECRET_KEY')

DEBUG = env('DEBUG')

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')
INSTALLED_APPS = [
    'nested_admin',
    'jazzmin',
    'more_admin_filters',
    'rangefilter',
    'import_export',
    'mptt',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'students',
    'kadrlar',
    'education',
    'finance',
    'rest_framework',
    'rest_framework.authtoken',
    'drf_yasg',
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

ROOT_URLCONF = 'conf.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'kadrlar.context_processors.birthday_notifications',
            ],
        },
    },
]

WSGI_APPLICATION = 'conf.wsgi.application'

DATABASES = {
    'default': env.db('DATABASE_URL', default=f"psql://{env('DB_USER')}:{env('DB_PASSWORD')}@{env('DB_HOST')}:{env('DB_PORT')}/{env('DB_NAME')}")
}

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

LANGUAGE_CODE = 'uz'

TIME_ZONE = 'Asia/Tashkent'

USE_I18N = True

USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'conf' / 'static',
]
STATIC_ROOT = BASE_DIR / 'static'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

JAZZMIN_SETTINGS = {
    "site_title": "DIPLOMAT BASE ADMIN",
    "site_header": "DIPLOMAT BASE Boshqaruv",
    "site_brand": "Diplomat University",
    "welcome_sign": "Tizimga xush kelibsiz",
    "copyright": "Diplomat University",
    "show_sidebar": True,
    "navigation_expanded": False,
    "topmenu_links": [
        {"name": "Bosh sahifa", "url": "admin:index", "permissions": ["auth.view_user"]},
        {"model": "auth.User"},
    ],
    "hide_models": [
        "students.Country", "students.Region", "students.District",
        "students.Specialty", "students.Group", "students.OrderType",
        "students.Contract", "students.Payment", "students.Order",
        "students.AcademicYear", "students.SubjectDebt", "students.PerevodRate",
        "students.Subject", "students.SubjectRate",
        "kadrlar.Document",
        "kadrlar.Order",
        "kadrlar.TeacherAvailability",
        "kadrlar.TimeSlot",
        "kadrlar.Weekday",
        "kadrlar.Teacher",
        "kadrlar.Quiz",
        "kadrlar.QuizResult",
        "kadrlar.QuizPermission",
        "kadrlar.QuizScoringRule",
        "kadrlar.QuizScoringInfo",
        "kadrlar.QuizQuestion",
        "kadrlar.QuizResultKey",
        "kadrlar.ArchivedEmployee",
        "kadrlar.Department",
        "kadrlar.Position",
        "kadrlar.OrganizationStructure",
        "kadrlar.OrganizationStructure",
        "kadrlar.OrganizationStructure",
        "kadrlar.SimpleStructure",
        "education.PlanSubject",
        "education.SubGroup",
        "education.Room",
        "education.LessonLog",
        "education.ScheduleError",
        "education.SessionPeriod",
    ],
    "custom_links": {
        "students": [
            {
                "name": "Sozlamalar",
                "url": "admin:students_general",
                "icon": "fas fa-chart-line",
            },
        ],
        "kadrlar": [
            {
                "name": "Sozlamalar",
                "url": "admin:kadrlar_general",
                "icon": "fas fa-chart-pie",
                "permissions": ["kadrlar.view_employee"],
            },
        ],
        "education": [
            {
                "name": "Sozlamalar",
                "url": "admin:education_general",
                "icon": "fas fa-cogs",
            },
        ],
    },
    "order_with_respect_to": [
        "students",
        "kadrlar",
        "kadrlar.Department",
        "kadrlar.Employee",
        "education",
        "finance",
        "auth",
    ],
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",

        "students": "fas fa-school",
        "students.student": "fas fa-user-graduate",

        "kadrlar": "fas fa-building",
        "kadrlar.Department": "fas fa-sitemap",
        "kadrlar.Employee": "fas fa-id-card",
        "kadrlar.Department": "fas fa-sitemap",
        "kadrlar.Employee": "fas fa-id-card",
        "kadrlar.Teacher": "fas fa-chalkboard-teacher",
    },
    "use_google_fonts_cdn": True,
}

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.BasicAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
}

SWAGGER_SETTINGS = {
    'SECURITY_DEFINITIONS': {
        'Token': {
            'type': 'apiKey',
            'name': 'Authorization',
            'in': 'header'
        }
    },
    'USE_SESSION_AUTH': False,
}

# =========================================================
# LOGGING CONFIGURATION
# =========================================================
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file_error': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOGS_DIR, 'error.log'),
            'maxBytes': 1024 * 1024 * 5,  # 5 MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'file_general': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOGS_DIR, 'general.log'),
            'maxBytes': 1024 * 1024 * 5,  # 5 MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file_general', 'file_error'],
            'level': 'INFO',
            'propagate': True,
        },
        'django.request': {
            'handlers': ['file_error'],
            'level': 'ERROR',
            'propagate': False,
        },
        'talababase': {
            'handlers': ['console', 'file_general', 'file_error'],
            'level': 'INFO',
        }
    },
}
