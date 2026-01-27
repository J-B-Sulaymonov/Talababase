from django.urls import path

from .views import quiz_login_view, quiz_process_view

app_name = 'kadrlar'

urlpatterns = [
    path('quiz/<int:quiz_id>/', quiz_login_view, name='quiz_login'),
    path('quiz/<int:quiz_id>/start/', quiz_process_view, name='quiz_process'),
]