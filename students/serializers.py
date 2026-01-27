# serializers.py
from rest_framework import serializers
from .models import Student, Group, Specialty


class SpecialtySerializer(serializers.ModelSerializer):
    class Meta:
        model = Specialty
        fields = ['name']

class GroupSerializer(serializers.ModelSerializer):
    specialty = serializers.StringRelatedField()

    class Meta:
        model = Group
        fields = ['id', 'name', 'specialty']

class StudentSerializer(serializers.ModelSerializer):
    group = GroupSerializer(read_only=True)

    class Meta:
        model = Student
        fields = [
            'id',
            'full_name',
            'student_hemis_id',
            'status',
            'gender',
            'passport_series_number',
            'group',
            'course_year',

        ]

