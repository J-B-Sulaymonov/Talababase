from rest_framework import serializers
from django.db.models import Sum
from .models import Student, Group, Specialty, Contract


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
    # Yangi maydon: To'lov foizi
    payment_percent = serializers.SerializerMethodField()

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
            'payment_percent',  # <--- Ro'yxatga qo'shildi
        ]

    def get_payment_percent(self, obj):
        """
        Talabaning aktiv o'quv yili bo'yicha to'lov foizini hisoblash.
        """
        # 1. Aktiv o'quv yili uchun shartnomani topamiz
        # contract_set - bu Student modelidagi Contract foreign keydan kelgan default related_name
        contract = obj.contract_set.filter(academic_year__is_active=True).first()

        if not contract:
            return 0

        # 2. Haqiqiy to'lanishi kerak bo'lgan summa (Kontrakt - Grant)
        contract_amount = contract.amount or 0
        grant_amount = contract.grant_amount or 0
        net_contract = contract_amount - grant_amount

        # Agar to'lanadigan summa 0 bo'lsa (masalan 100% grant), foizni 0 yoki 100 deb olish mumkin.
        # Hozircha xatolik chiqmasligi uchun 0 qaytaramiz.
        if net_contract <= 0:
            return 0

        # 3. To'langan summani hisoblash
        # payment_set - bu Contract modelidagi Payment foreign keydan kelgan default related_name
        total_paid = contract.payment_set.aggregate(total=Sum('amount'))['total'] or 0

        # 4. Foizni hisoblash
        percent = (total_paid * 100) / net_contract

        # 1 xona aniqlikda yaxlitlash (masalan: 45.5)
        return round(percent, 1)