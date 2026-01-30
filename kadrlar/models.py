from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from mptt.fields import TreeForeignKey
from mptt.models import MPTTModel

User = get_user_model()


# =========================================================
# 1. ASOSIY MA'LUMOTNOMALAR (HR & SCHEDULE UCHUN)
# =========================================================

class Department(models.Model):
    name = models.CharField("Nomi", max_length=200)
    # parent = models.ForeignKey(
    #     'self',
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     related_name='children',
    #     verbose_name="Yuqori turuvchi tuzilma"
    # )
    order = models.PositiveIntegerField("Tartib raqami", default=0, blank=True, null=True)
    # Faqat Kafedra mudiri biriktiriladi
    head_manager = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='managed_department',
        verbose_name="Kafedra yoki Bo'lim Rahbari",
        help_text="Ushbu tuzilmani (kafedra yoki bo'limni) boshqaradigan user"
    )
    head_manager = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='managed_department',
        verbose_name="Kafedra yoki Bo'lim Rahbari"
    )
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "Kafedra / Bo'lim"
        verbose_name_plural = "Kafedralar / Bo'limlar"

    def __str__(self):
        return self.name


class Weekday(models.Model):
    """Hafta kunlari (Jadval uchun)"""
    name = models.CharField("Kun nomi", max_length=20)  # Dushanba, Seshanba...
    order = models.PositiveSmallIntegerField("Tartib raqami", unique=True)  # 1, 2, ...

    class Meta:
        ordering = ['order']
        verbose_name = "Hafta kuni"
        verbose_name_plural = "Hafta kunlari"

    def __str__(self):
        return self.name


class TimeSlot(models.Model):
    """Dars vaqtlari (Paralar)"""
    index = models.PositiveSmallIntegerField(unique=True, verbose_name="Para #")
    start_time = models.TimeField("Boshlanish vaqti")
    end_time = models.TimeField("Tugash vaqti")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Vaqt bloki (Para)"
        verbose_name_plural = "Vaqt bloklari"
        ordering = ['index']

    def __str__(self) -> str:
        return f"{self.index}-para ({self.start_time:%H:%M}-{self.end_time:%H:%M})"


# =========================================================
# 2. XODIMLAR (HR) MODELLARI
# =========================================================
class Position(models.Model):
    name = models.CharField("Lavozim nomi", max_length=200, unique=True)

    class Meta:
        verbose_name = "Lavozim"
        verbose_name_plural = "Lavozimlar"
        ordering = ['id']

    def __str__(self):
        return self.name

class Employee(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Kutilmoqda'),
        ('active', 'Faol'),
        ('dismissed', "Ishdan bo'shatilgan"),
    ]

    GENDER_CHOICES = [
        ('male', 'Erkak'),
        ('female', 'Ayol'),
    ]
    DEGREE_CHOICES = [
        ('none', "Yo'q"),
        ('phd', "PhD (Falsafa doktori)"),
        ('dsc', "DSc (Fan doktori)"),
    ]

    TITLE_CHOICES = [
        ('none', "Yo'q"),
        ('docent', "Dotsent"),
        ('professor', "Professor"),
        ('academic', "Akademik"),
    ]


    first_name = models.CharField("Ism", max_length=120)
    last_name = models.CharField("Familiya", max_length=120)
    middle_name = models.CharField("Otasining ismi", max_length=120, blank=True)
    gender = models.CharField("Jinsi", max_length=10, choices=GENDER_CHOICES, default='male')
    passport_info = models.CharField(
        "Passport Seriya va Raqam",
        max_length=20,
        unique=True,
        help_text="Masalan: AA1234567"
    )
    pid = models.CharField("JSHShIR / Passport", max_length=50, unique=True)
    birth_date = models.DateField("Tug'ilgan sana", null=True, blank=True)
    photo = models.ImageField("Rasm", upload_to='kadrlar/photos/', null=True, blank=True)

    department = models.ForeignKey(
        Department, verbose_name="Kafedra/Bo'lim",
        null=True, blank=True, on_delete=models.SET_NULL, related_name='employees'
    )
    # position = models.CharField("Lavozim", max_length=200, blank=True)
    positions = models.ManyToManyField(
        Position,
        verbose_name="Lavozimlar",
        related_name='employees',
        blank=True,
        help_text="Xodim bir vaqtning o'zida bir nechta lavozimda ishlashi mumkin"
    )
    scientific_degree = models.CharField(
        "Ilmiy daraja",
        max_length=10,
        choices=DEGREE_CHOICES,
        default='none',
        blank=True
    )

    scientific_title = models.CharField(
        "Ilmiy unvon",
        max_length=20,
        choices=TITLE_CHOICES,
        default='none',
        blank=True
    )
    is_teacher = models.BooleanField("O'qituvchi", default=False)

    hired_at = models.DateField("Ishga qabul qilingan sana", null=True, blank=True)

    # HR TASDIQLASH QISMI
    status = models.CharField("Holat", max_length=20, choices=STATUS_CHOICES, default='pending')
    approved = models.BooleanField("Tasdiqlangan (HR)", default=False)
    archived = models.BooleanField("Arxivlangan (soft)", default=False)

    order = models.PositiveIntegerField("Tartib raqami", default=0, blank=True, null=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name='created_employees')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['department__order', 'order']
        verbose_name = "Xodim"
        verbose_name_plural = "Xodimlar (HR)"

    def __str__(self):
        return f"{self.last_name} {self.first_name}"

    def get_positions_display(self):
        return ", ".join([p.name for p in self.positions.all()])

    get_positions_display.short_description = "Lavozimlar"

class Document(models.Model):
    DOCUMENT_TYPE_CHOICES = [
        ('reference', "Ma'lumotnoma"),
        ('diploma', 'Diplom'),
        ('certificate', 'Sertifikat'),
        ('other', 'Boshqa'),
    ]
    employee = models.ForeignKey(Employee, related_name='documents', on_delete=models.CASCADE)
    doc_type = models.CharField("Hujjat turi", max_length=50, choices=DOCUMENT_TYPE_CHOICES)
    file = models.FileField("Fayl", upload_to='kadrlar/documents/')
    number = models.CharField("Hujjat raqami", max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        verbose_name = "Hujjat"
        verbose_name_plural = "Hujjatlar"


class Order(models.Model):
    ORDER_TYPE_CHOICES = [
        ('hire', 'Qabul qilish'),
        ('dismiss', "Ishdan bo‘shatish"),
        ('transfer', "Ko‘chirish"),
    ]
    employee = models.ForeignKey(Employee, related_name='orders', on_delete=models.CASCADE)
    number = models.CharField("Buyruq raqami", max_length=100)
    order_type = models.CharField("Turi", max_length=20, choices=ORDER_TYPE_CHOICES)
    date = models.DateField("Sana")
    document = models.FileField("Buyruq fayli", upload_to='kadrlar/orders/', null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (('employee', 'number'),)
        verbose_name = "Buyruq"
        verbose_name_plural = "Buyruqlar"


# =========================================================
# 3. O'QUV JARAYONI (TEACHER & SCHEDULE) MODELLARI
# =========================================================

class Teacher(models.Model):
    """
    O'qituvchi profili.
    - Kafedra: Fanlarni va vaqtni to'ldiradi.
    - O'quv bo'limi: schedule_approved ni tasdiqlaydi.
    """

    employee = models.OneToOneField(
        Employee,
        on_delete=models.CASCADE,
        related_name='teacher_profile',
        verbose_name="Xodim (O'qituvchi)"
    )

    work_type_permanent = models.BooleanField("Doimiy (Shtat)", default=False)
    work_type_hourly = models.BooleanField("Soatbay", default=False)
    # Students appdagi Subject modeliga bog'lanish
    subjects = models.ManyToManyField(
        'students.Subject',
        related_name='teachers',
        verbose_name="Dars beradigan fanlari",
        blank=True
    )

    can_teach_lecture = models.BooleanField("Ma'ruza o'ta oladimi?", default=False)
    can_teach_practice = models.BooleanField("Amaliyot o'ta oladimi?", default=False)
    can_teach_lab = models.BooleanField("Laboratoriya o'ta oladimi?", default=False)
    can_teach_seminar = models.BooleanField("Seminar o'ta oladimi?", default=False)

    # O'QUV BO'LIMI TASDIQLASH QISMI
    schedule_approved = models.BooleanField(
        "Jadval va Yuklama tasdiqlandi (O'quv bo'limi)",
        default=False,
        help_text="O'qituvchining fanlari va bo'sh vaqtlari O'quv bo'limi tomonidan tekshirib tasdiqlanganda belgilanadi."
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "O'qituvchi profili"
        verbose_name_plural = "O'qituvchilar (O'quv bo'limi)"
        permissions = [
            ("can_approve_schedule", "Jadvalni tasdiqlay oladi (O'quv bo'limi)"),
        ]

    def __str__(self):
        status = "✅" if self.schedule_approved else "⏳"
        return f"{self.employee} [{status}]"

    def clean(self):
        # Mantiq: Agar HR xodimni 'active' qilmagan bo'lsa, O'quv bo'limi unga dars bera olmaydi
        if self.schedule_approved and self.employee.status != 'active':
            raise ValidationError({
                'schedule_approved': "Xatolik! Kadrlar bo'limi bu xodimni hali to'liq ishga qabul qilmagan (Status: Active emas)."
            })


class TeacherAvailability(models.Model):
    """O'qituvchining bo'sh vaqtlari"""
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='availabilities')
    weekday = models.ForeignKey(Weekday, on_delete=models.CASCADE, verbose_name="Hafta kuni")
    timeslots = models.ManyToManyField(TimeSlot, blank=True, verbose_name="Bo'sh vaqtlar (Paralar)")

    class Meta:
        verbose_name = "Bo'sh vaqt"
        verbose_name_plural = "O'qituvchi vaqtlari"
        unique_together = ('teacher', 'weekday')
        ordering = ['weekday__order']


# =========================================================
# 4. UNIVERSAL TEST TIZIMI (KPI & PSIXOLOGIK)
# =========================================================
class Quiz(models.Model):
    """Umumiy Quiz (Maslow, IQ yoki oddiy test)"""
    title = models.CharField("Quiz nomi", max_length=255)
    description = models.TextField("Tavsif", blank=True)
    is_active = models.BooleanField("Faol", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Quiz"
        verbose_name_plural = "Quizlar"

    def __str__(self):
        return self.title

class QuizResultKey(models.Model):
    """
    Natija Kalitlari (Masalan: DISC testidagi D, I, S, C yoki Maslowdagi ustunlar)
    """
    VARIANT_CHOICES = [
        ('A', 'A'),
        ('B', 'B'),
        ('C', 'C'),
        ('D', 'D'),
        ('E', 'E'),
        ('F', 'F'),
        ('G', 'G'),
        ('H', 'H'),
        # Kerak bo'lsa so'zli variantlar ham qo'shish mumkin:
        ('Ha', 'Ha'),
        ('Yo\'q', 'Yo\'q'),
    ]
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='result_keys')
    code =  models.CharField(
        "Variant",
        max_length=10,
        choices=VARIANT_CHOICES,  # <-- Select box bo'lishini ta'minlaydi
        default='A'
    )
    description = models.TextField("Tavsif", help_text="Ushbu tip haqida to'liq ma'lumot")

    class Meta:
        verbose_name = "Natija Kaliti"
        verbose_name_plural = "Natija Kalitlari"

    def __str__(self):
        return f"{self.id}"

class QuizQuestion(models.Model):
    """Quiz savoli"""
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField("Savol matni")
    order = models.PositiveSmallIntegerField("Tartib raqami", default=1)

    class Meta:
        ordering = ['order']
        verbose_name = "Savol"
        verbose_name_plural = "Savollar"

    def __str__(self):
        return f"{self.order}. {self.text}"


class QuizAnswer(models.Model):
    """
    Javob varianti (Inline).
    Har bir variantga o'z bali qo'yiladi (Kalit).

    """
    VARIANT_CHOICES = [
        ('A', 'A'),
        ('B', 'B'),
        ('C', 'C'),
        ('D', 'D'),
        ('E', 'E'),
        ('F', 'F'),
        ('G', 'G'),
        ('H', 'H'),
        # Kerak bo'lsa so'zli variantlar ham qo'shish mumkin:
        ('Ha', 'Ha'),
        ('Yo\'q', 'Yo\'q'),
    ]
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE, related_name='answers')
    text = models.TextField("Javob matni")
    symbol = models.CharField(
        "Variant",
        max_length=10,
        choices=VARIANT_CHOICES,
        default='A'
    )
    score = models.IntegerField("Ball", default=0, help_text="Ushbu javob tanlansa beriladigan ball")

    class Meta:
        verbose_name = "Javob"
        verbose_name_plural = "Javoblar"

    def __str__(self):
        return f"{self.id}"


class QuizPermission(models.Model):
    """
    Xodimga test topshirish uchun ruxsat.
    Agar is_active=True bo'lsa, xodim kirib test yecha oladi.
    Test tugagach, avtomatik is_active=False bo'ladi.
    """
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='permissions')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='quiz_permissions')
    is_active = models.BooleanField("Ruxsat berilgan", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Testga ruxsat"
        verbose_name_plural = "Testga ruxsatlar"
        unique_together = ('quiz', 'employee')  # Bir xodimga bir vaqtda bitta ruxsat

    def __str__(self):
        return f"{self.employee} -> {self.quiz} ({'Ochiq' if self.is_active else 'Yopiq'})"


class QuizResult(models.Model):
    """
    Test natijalari.
    Batafsil ma'lumot JSON formatida 'struct' fieldida saqlanadi.
    """
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)

    # Talab qilingan JSON strukturasi uchun field
    struct = models.JSONField("Batafsil natijalar")

    total_score = models.IntegerField("Umumiy ball", default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Test Natijasi"
        verbose_name_plural = "Test Natijalari"

    def __str__(self):
        return f"{self.employee} - {self.quiz.title} ({self.total_score} ball)"


class QuizScoringRule(models.Model):
    """
    Test natijalarini talqin qilish qoidalari (Maslow va shunga o'xshashlar uchun).
    Misol:
    - Kategoriya: "Xavfsizlikka ehtiyoj (1-ustun)"
    - Savollar: "1, 5, 9, 13"
    - Min: 20, Max: 25 -> "Juda muhim"
    """
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='scoring_rules')

    category_name = models.CharField(
        "Kategoriya nomi",
        max_length=200,
        help_text="Masalan: Xavfsizlikka ehtiyoj, Ijtimoiy ehtiyoj"
    )

    related_questions = models.CharField(
        "Tegishli savollar",
        max_length=200,
        blank=True,
        help_text="Qaysi savollar ushbu kategoriyani baholaydi? (Masalan: 1, 5, 9, 13)"
    )

    min_score = models.IntegerField("Min. Ball", default=0)
    max_score = models.IntegerField("Max. Ball", default=25)

    conclusion = models.TextField(
        "Xulosa / Tavsif",
        help_text="Agar to'plangan ball shu oraliqda bo'lsa, chiqadigan matn."
    )

    class Meta:
        verbose_name = "Baholash Mezoni"
        verbose_name_plural = "Baholash Mezonlari (Tahlil)"
        ordering = ['id',]

    def __str__(self):
        return f"{self.id}"


class QuizScoringInfo(models.Model):

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='scoring_info')

    min_score = models.IntegerField("Min. Ball", default=0)
    max_score = models.IntegerField("Max. Ball", default=25)

    conclusion = models.TextField(
        "Xulosa / Tavsif",
        help_text="Agar to'plangan ball shu oraliqda bo'lsa, chiqadigan matn."
    )

    class Meta:
        verbose_name = "Baholash Mezoni izohi"
        verbose_name_plural = "Baholash Mezoni izohi"
        ordering = ['id',]

    def __str__(self):
        return f"{self.id}"

# kadrlar/models.py oxiriga qo'shing:

class ArchivedEmployee(Employee):
    """
    Faqat arxivlangan (ishdan bo'shagan) xodimlarni ko'rsatish uchun soxta model.
    Baza o'zgarmaydi.
    """
    class Meta:
        proxy = True  # <--- Bu juda muhim! Yangi jadval ochilmaydi.
        verbose_name = "Arxivdagi xodim"
        verbose_name_plural = "Arxiv (Bo'shaganlar)"


class OrganizationStructure(models.Model):
    title = models.CharField("Tuzilma nomi", max_length=255, default="Asosiy Tashkiliy Tuzilma")
    xml_data = models.TextField("Diagramma kodi (XML)", blank=True, help_text="Bu yerga tegmang, diagramma avtomatik saqlanadi.")
    is_active = models.BooleanField("Faol", default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Tashkiliy Tuzilma"
        verbose_name_plural = "Tashkiliy Tuzilma"

    def __str__(self):
        return self.title


class SimpleStructure(MPTTModel):

    name = models.CharField("Tugun nomi", max_length=255, help_text="Masalan: Rektor, Buxgalteriya")
    parent = TreeForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children',
                            verbose_name="Yuqori tugun")

    # --- YANGI MANTIQ ---
    # 1. Agar bo'lim tanlansa -> Shu bo'limdagi HAMMA chiqadi.
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True,
                                   verbose_name="Bo'lim (Butun jamoani chiqarish)")

    # 2. Agar xodim tanlansa -> Faqat SHU ODAM chiqadi.
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True,
                                 verbose_name="Aniq xodim (Yakka tartibda)")

    order = models.PositiveIntegerField("Ko'rinish tartibi", default=0)

    class MPTTMeta:
        order_insertion_by = ['order']

    class Meta:
        verbose_name = "Tuzilma Elementi"
        verbose_name_plural = "Tashkiliy Tuzilma (Sozlamalar)"

    def __str__(self):
        return self.name

    def get_employees(self):
        """
        Xodimlarni qaytarish mantig'i:
        1. Agar 'employee' tanlangan bo'lsa -> Faqat o'shani qaytar (Boshqalarni aralashtirma).
        2. Agar 'department' tanlangan bo'lsa -> Shu bo'limdagi barcha faol xodimlarni qaytar.
        """

        # 1-HOLAT: Aniq xodim biriktirilgan (Masalan: Rektor)
        if self.employee:
            # Biz baribir QuerySet qaytarishimiz kerak (loop ishlashi uchun)
            return Employee.objects.filter(id=self.employee.id)

        # 2-HOLAT: Bo'lim biriktirilgan (Masalan: Buxgalteriya)
        if self.department:
            return Employee.objects.filter(
                department=self.department,
                status='active',
                archived=False
            ).order_by('order')

        # Hech narsa tanlanmagan bo'lsa
        return Employee.objects.none()

    def get_employee_count(self):
        return self.get_employees().count()