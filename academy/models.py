from django.db import models
from django.utils import timezone

class WeekDay(models.Model):
    """
    Hafta kunlari (Dushanba, Seshanba...)
    """
    name = models.CharField(max_length=20, verbose_name="Kun nomi")
    order = models.PositiveSmallIntegerField(unique=True, verbose_name="Tartib raqami (1-7)")

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['order']
        verbose_name = "Hafta kuni"
        verbose_name_plural = "Hafta kunlari"


class Level(models.Model):
    name = models.CharField(max_length=50, verbose_name="Daraja nomi")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Daraja"
        verbose_name_plural = "Darajalar"


class Teacher(models.Model):
    first_name = models.CharField(max_length=50, verbose_name="Ism")
    last_name = models.CharField(max_length=50, verbose_name="Familiya", blank=True, null=True)
    phone_number = models.CharField(max_length=20, verbose_name="Telefon", blank=True, null=True)
    is_active = models.BooleanField(default=True, verbose_name="Hozir ishlaydimi?")

    def __str__(self):
        return f"{self.first_name} {self.last_name or ''}"

    class Meta:
        verbose_name = "O'qituvchi"
        verbose_name_plural = "O'qituvchilar"


class Group(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name="Guruh kodi")
    level = models.ForeignKey(Level, on_delete=models.CASCADE, verbose_name="Daraja")
    teacher = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, verbose_name="O'qituvchi")
    price = models.DecimalField(decimal_places=2, max_digits=10, verbose_name="Guruh narxi (oylik)")
    teacher_price = models.DecimalField(decimal_places=2, max_digits=10, verbose_name="O'qituvchi uchun to'lanadigan pul miqdori", default=0)
    days = models.ManyToManyField(WeekDay, related_name='groups', verbose_name="Dars kunlari")
    lesson_time_start = models.TimeField(verbose_name="Boshlanish vaqti",)
    lesson_time_end = models.TimeField(verbose_name="Tugash vaqti",)

    is_active = models.BooleanField(default=True, verbose_name="Guruh faolmi?")
    lessons_per_month = models.PositiveIntegerField(default=12, verbose_name="Darslar soni")

    # === Hisoblangan moliyaviy ko'rsatkichlar ===
    def get_active_student_count(self):
        """Faol o'quvchilar soni"""
        # Agar admin annotation orqali student_count kelgan bo'lsa, shuni ishlatamiz
        if hasattr(self, 'student_count') and isinstance(self.student_count, int):
            return self.student_count
        return self.enrollments.filter(left_date__isnull=True).count()

    def total_revenue(self):
        """Umumiy pul miqdori (talabalar soni × guruh narxi)"""
        return self.get_active_student_count() * self.price

    def payment_per_lesson(self):
        """Har bir dars uchun to'lov (o'qituvchi oyligini darslar soniga bo'lish)"""
        if self.lessons_per_month > 0:
            return self.teacher_price / self.lessons_per_month
        return 0

    def teacher_share_percentage(self):
        """O'rtacha to'lanadigan ulush (o'qituvchi maoshi / umumiy pul × 100%)"""
        total = self.total_revenue()
        if total > 0:
            return (self.teacher_price / total) * 100
        return 0

    def __str__(self):
        return f"{self.name}"

    class Meta:
        verbose_name = "Guruh"
        verbose_name_plural = "Guruhlar"


class Student(models.Model):
    full_name = models.CharField(max_length=50, verbose_name="F.I.SH")
    phone_number = models.CharField(max_length=20, verbose_name="Telefon", null=True, blank=True)
    parent_phone = models.CharField(max_length=20, verbose_name="Ota-ona telefoni", null=True, blank=True)

    status = models.CharField(max_length=20, choices=[('active', 'Faol'), ('inactive', 'Nofaol')], default='active')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name}"

    class Meta:
        verbose_name = "O'quvchi"
        verbose_name_plural = "O'quvchilar"


# =============================================================================
# 📋 KURSGA QABUL / CHIQARISH (Enrollment)
# =============================================================================

class Enrollment(models.Model):
    """
    O'quvchini kursga (guruhga) qabul qilish va chiqarish yozuvi.
    Har bir guruh uchun alohida enrollment yaratiladi.
    """
    LEAVE_REASONS = [
        ('completed', 'Kursni tugatdi'),
        ('financial', 'Moliyaviy sabab'),
        ('personal', 'Shaxsiy sabab'),
        ('moved', "Ko'chib ketdi"),
        ('dissatisfied', 'Qoniqmadi'),
        ('other', 'Boshqa sabab'),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='enrollments', verbose_name="O'quvchi")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='enrollments', verbose_name="Guruh")

    enrolled_date = models.DateField(default=timezone.now, verbose_name="Kursga qabul sanasi")
    left_date = models.DateField(null=True, blank=True, verbose_name="Kursdan ketgan sana")
    leave_reason = models.CharField(
        max_length=20, choices=LEAVE_REASONS, null=True, blank=True,
        verbose_name="Ketish sababi"
    )
    leave_comment = models.TextField(
        null=True, blank=True,
        verbose_name="Ketish haqida izoh",
        help_text="Qisqacha izoh (ixtiyoriy)"
    )

    is_active = models.BooleanField(default=True, verbose_name="Hozir o'qiyaptimi?")

    def __str__(self):
        status = "✓" if self.is_active else "✗"
        return f"{status} {self.student.full_name} → {self.group.name}"

    def months_enrolled(self):
        """Necha oy o'qigani (joriy oyni ham hisoblaydi)"""
        from datetime import date
        end = self.left_date if self.left_date else date.today()
        return max((end.year - self.enrolled_date.year) * 12 + (end.month - self.enrolled_date.month) + 1, 1)

    def expected_payment(self):
        """Kutilgan to'lov summasi (oylar * guruh narxi)"""
        return self.months_enrolled() * self.group.price

    class Meta:
        verbose_name = "Kursga qabul"
        verbose_name_plural = "Kursga qabul qilishlar"
        ordering = ['-enrolled_date']
        unique_together = ['student', 'group', 'enrolled_date']


# =============================================================================
# 💰 TO'LOV TURLARI
# =============================================================================

class PaymentMethod(models.TextChoices):
    CASH = 'cash', 'Naqd pul'
    CARD = 'card', 'Plastik karta'
    CLICK = 'click', 'Click/Payme'
    TRANSFER = 'transfer', "Bank o'tkazmasi"


class StudentPayment(models.Model):
    """
    O'quvchilardan qabul qilingan to'lovlar (Kirim)
    """
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='payments', verbose_name="O'quvchi")
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, verbose_name="Qaysi guruh uchun")

    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="To'lov summasi")
    payment_date = models.DateField(default=timezone.now, verbose_name="To'lov qilingan sana")

    # Muhim: To'lov qaysi oy uchun? (Masalan: Fevralda turib Mart uchun to'lashi mumkin)
    month_for = models.DateField(verbose_name="Qaysi oy uchun to'lov",
                                 help_text="Oyning istalgan sanasini belgilang (odatda 1-sana)")

    payment_type = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH,
                                    verbose_name="To'lov turi")
    comment = models.TextField(blank=True, null=True, verbose_name="Izoh")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.full_name} - {self.amount} ({self.month_for.strftime('%B %Y')})"

    class Meta:
        verbose_name = "O'quvchi to'lovi"
        verbose_name_plural = "O'quvchi to'lovlari"
        ordering = ['-payment_date']


class TeacherSalary(models.Model):
    """
    O'qituvchilarga to'langan pullar (Chiqim)
    """
    PAYMENT_TYPES = [
        ('salary', 'Oylik maosh'),
        ('advance', 'Avans'),
        ('bonus', 'Bonus/Mukofot'),
    ]

    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='salaries', verbose_name="O'qituvchi")

    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Berilgan summa")
    payment_date = models.DateField(default=timezone.now, verbose_name="Berilgan sana")

    # Qaysi oy hisobidan berilyapti?
    month_for = models.DateField(verbose_name="Qaysi oy hisobidan", help_text="Oyning istalgan sanasini belgilang")

    type = models.CharField(max_length=20, choices=PAYMENT_TYPES, default='salary', verbose_name="To'lov turi")
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH,
                                      verbose_name="To'lov usuli")

    comment = models.TextField(blank=True, null=True, verbose_name="Izoh")

    def __str__(self):
        return f"{self.teacher} - {self.amount} ({self.get_type_display()})"

    class Meta:
        verbose_name = "O'qituvchi maoshi"
        verbose_name_plural = "O'qituvchi maoshlari"
        ordering = ['-payment_date']
