import os
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = 'django-insecure-gg4wpc4^gc83mroq##9ia#*sh804poaqbak&^!jg&4h=%^l@mu'
DEBUG = True
ALLOWED_HOSTS = ["*"]

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
    # 'academy',
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
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'students',
        'USER': 'postgres',
        'PASSWORD': 'Ab0199797',
        'HOST': '192.168.0.254',
        'PORT': '5432',
    }
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
        "kadrlar.SimpleStructure",
        # Academy Hidden Models
        "academy.Level", "academy.Teacher", "academy.WeekDay",
        "academy.Enrollment", "academy.StudentPayment", "academy.TeacherSalary",
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
        "academy": [
            {
                "name": "Sozlamalar",
                "url": "admin:academy_general",
                "icon": "fas fa-cogs",
                "permissions": ["academy.view_teacher"],
            },
        ]
    },
    "order_with_respect_to": [
        "academy",
        "academy.Group",
        "academy.Student",
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

        "academy": "fas fa-university",
        "academy.Group": "fas fa-users",
        "academy.Student": "fas fa-user-graduate",
        "academy.Teacher": "fas fa-chalkboard-teacher",
        "academy.Level": "fas fa-layer-group",
    },
    "use_google_fonts_cdn": True,
}