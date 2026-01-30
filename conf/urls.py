from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


# 1. Asosiy URLlar (Admin dan boshqa)
urlpatterns = [
    path('_nested_admin/', include('nested_admin.urls')),
    path('api/', include('students.urls', namespace='students')),
    path('chaining/', include('smart_selects.urls')),
    path('api-auth/', include('rest_framework.urls')),
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