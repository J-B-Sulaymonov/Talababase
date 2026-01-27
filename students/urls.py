# students/urls.py
from django.urls import path
from .views import (
    StudentListAPIView, StudentDetailAPIView,
    GroupListAPIView, GroupDetailAPIView
)
app_name = 'students'

urlpatterns = [
    # Student API
    path('students/', StudentListAPIView.as_view(), name='student-list'),
    path('students/<int:pk>/', StudentDetailAPIView.as_view(), name='student-detail'),

    # Group API
    path('groups/', GroupListAPIView.as_view(), name='group-list'),
    path('groups/<int:pk>/', GroupDetailAPIView.as_view(), name='group-detail'),

]
