from django.utils import timezone
from datetime import timedelta
from .models import Employee

def birthday_notifications(request):
    # Agar foydalanuvchi tizimga kirmagan bo'lsa, hech narsa qaytarmaymiz
    if not request.user.is_authenticated:
        return {}

    # Agar foydalanuvchi Kadr yoki Superuser bo'lmasa, ma'lumot ko'rsatmaymiz
    # (Agar oddiy o'qituvchilarga ham ko'rinishi kerak bo'lsa, bu shartni olib tashlang)
    is_hr = request.user.is_superuser or request.user.groups.filter(name='Kadrlar').exists()
    if not is_hr:
        return {}

    today = timezone.now().date()
    tomorrow = today + timedelta(days=1)

    # 1. Bugungi tug'ilgan kunlar
    birthdays_today = Employee.objects.filter(
        birth_date__month=today.month,
        birth_date__day=today.day,
        status='active',
        archived=False
    )

    # 2. Ertangi tug'ilgan kunlar
    birthdays_tomorrow = Employee.objects.filter(
        birth_date__month=tomorrow.month,
        birth_date__day=tomorrow.day,
        status='active',
        archived=False
    )

    count = birthdays_today.count() + birthdays_tomorrow.count()

    return {
        'notify_birthdays_today': birthdays_today,
        'notify_birthdays_tomorrow': birthdays_tomorrow,
        'notify_birthdays_count': count,
    }