from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
   openapi.Info(
      title="Talababase API",
      default_version='v1',
      description="Diplomat University Education Management API",
      terms_of_service="https://www.google.com/policies/terms/",
      contact=openapi.Contact(email="contact@diplomat.university"),
      license=openapi.License(name="BSD License"),
   ),
   public=False,
   permission_classes=(permissions.IsAdminUser,),
)


# 1. Asosiy URLlar (Admin dan boshqa)
urlpatterns = [
    path('_nested_admin/', include('nested_admin.urls')),
    path('api/', include('students.urls', namespace='students')),
    path('chaining/', include('smart_selects.urls')),
    path('api-auth/', include('rest_framework.urls')),
    
    # Swagger API Documentation
    path('dipbase-swagger<format>/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('dipbase-swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('dipbase-redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    # DIQQAT: Admin yo'lini bu yerdan olib tashladik!
]

# 2. Media va Static fayllarni ULASH (Admin dan OLDIN bo'lishi shart)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# 3. Admin panelni ENG OXIRIGA qo'shamiz
# Shunda u media fayllarni "tutib ololmaydi"
urlpatterns += [
    path('personnel/', include('kadrlar.urls')),
    path('', admin.site.urls),
    # path('personnel/', include('kadrlar.urls')),



]