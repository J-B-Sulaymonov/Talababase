# views.py
from rest_framework import generics
from .models import Student, Group
from .serializers import StudentSerializer
from .serializers import GroupSerializer

class StudentListAPIView(generics.ListAPIView):
    queryset = Student.objects.select_related('group__specialty').all()
    serializer_class = StudentSerializer


class StudentDetailAPIView(generics.RetrieveAPIView):
    queryset = Student.objects.select_related('group__specialty').all()
    serializer_class = StudentSerializer



class GroupListAPIView(generics.ListAPIView):
    queryset = Group.objects.select_related('specialty').all()
    serializer_class = GroupSerializer


class GroupDetailAPIView(generics.RetrieveAPIView):
    queryset = Group.objects.select_related('specialty').all()
    serializer_class = GroupSerializer