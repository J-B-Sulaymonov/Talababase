import datetime

from django.db import models
from django.utils import timezone
from smart_selects.db_fields import ChainedForeignKey
from decimal import Decimal, ROUND_HALF_UP
from django.core.exceptions import ValidationError

# =============================================================================
# 🌍 JOYLAShUV MODELLARI
# =============================================================================
class Country(models.Model):
    name = models.CharField("Davlat nomi", max_length=100, unique=True)

    class Meta:
        verbose_name = "Davlat"
        verbose_name_plural = "Davlatlar"
        ordering = ['name']

    def __str__(self):
        return self.name


class Region(models.Model):
    name = models.CharField("Viloyat nomi", max_length=100)
    country = models.ForeignKey(Country, on_delete=models.CASCADE, verbose_name="Davlat")

    class Meta:
        verbose_name = "Viloyat"
        verbose_name_plural = "Viloyatlar"
        unique_together = ('name', 'country')
        ordering = ['name']

    def __str__(self):
        return self.name


class District(models.Model):
    name = models.CharField("Tuman nomi", max_length=100)
    region = models.ForeignKey(Region, on_delete=models.CASCADE, verbose_name="Viloyat")

    class Meta:
        verbose_name = "Tuman"
        verbose_name_plural = "Tumanlar"
        unique_together = ('name', 'region')
        ordering = ['name']

    def __str__(self):
        return self.name


# =============================================================================
# 🎓 TA'LIMGA OID MODELLAR
# =============================================================================
class Specialty(models.Model):
    name = models.CharField("Yo'nalish nomi", max_length=255)
    code = models.CharField("Yo'nalish kodi", max_length=50, null=True, blank=True)

    class Meta:
        verbose_name = "Yo'nalish"
        verbose_name_plural = "Yo'nalishlar"
        ordering = ['name']

    def __str__(self):
        return self.name


class Group(models.Model):
    name = models.CharField("Guruh nomi", max_length=100)
    specialty = models.ForeignKey(Specialty, on_delete=models.CASCADE, verbose_name="Yo'nalishi")

    class Meta:
        verbose_name = "Guruh"
        verbose_name_plural = "Guruhlar"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.specialty.name})"


class AcademicYear(models.Model):
    name = models.CharField(
        "O‘quv yili nomi",
        max_length=20,
        unique=True,
        help_text="Masalan: 2023-2024"
    )
    is_active = models.BooleanField("Faol yil", default=False)

    class Meta:
        verbose_name = "O‘quv yili"
        verbose_name_plural = "O‘quv yillari"
        ordering = ['-id']

    def __str__(self):
        return self.name


class OrderType(models.Model):
    name = models.CharField("Buyruq turi", max_length=255, unique=True)

    class Meta:
        verbose_name = "Buyruq turi"
        verbose_name_plural = "Buyruq turlari"
        ordering = ['name']

    def __str__(self):
        return self.name


class Order(models.Model):
    class TschChoices(models.TextChoices):
        DU = 'du', "Diplomat University"
        STUDENTS = 'student', "Talaba"
    student = models.ForeignKey(
        'Student',
        on_delete=models.CASCADE,
        verbose_name="Talaba",
        related_name="orders"
    )
    order_type = models.ForeignKey(
        OrderType,
        on_delete=models.PROTECT,
        verbose_name="Buyruq turi"
    )
    order_number = models.CharField("Buyruq raqami", max_length=50)
    order_date = models.DateField("Buyruq sanasi")

    tsch_by_whom = models.CharField(
        "TSCH kim tomonidan",
        max_length=20,
        choices=TschChoices.choices,
        default=TschChoices.DU,
        null=True, blank=True
    )
    tsch_reason = models.CharField(
        "TSCH sababi",
        max_length=255,
        null=True, blank=True
    )
    notes = models.TextField("Izoh", null=True, blank=True)
    application_date = models.DateField("Ariza sanasi",null=True, blank=True)
    document_taken_date = models.DateField(
        "Hujjat olib ketilgan sanasi",
        null=True, blank=True
    )

    class Meta:
        verbose_name = "Buyruq"
        verbose_name_plural = "Buyruqlar"
        ordering = ['-order_date']

    def __str__(self):
        return f"{self.order_type.name} — {self.student.full_name}"


# =============================================================================
# 👩‍🎓 TALABA MODELI
# =============================================================================
class Student(models.Model):
    class GenderChoices(models.TextChoices):
        MALE = 'erkak', "Erkak"
        FEMALE = 'ayol', "Ayol"

    class StatusChoices(models.TextChoices):
        ACTIVE = 'active', "O'qiydi"
        ACADEMIC_LEAVE = 'academic', "Akademik ta'tilda"
        EXPELLED = 'expelled', "Chetlashtirilgan"
        GRADUATED = 'graduated', "Bitirgan"

    class EducationFormChoices(models.TextChoices):
        FULL_TIME = 'kunduzgi', "Kunduzgi"
        PART_TIME = 'sirtqi', "Sirtqi"
        EVENING = 'kechki', "Kechki"

    class EducationTypeChoices(models.TextChoices):
        GRANT = 'grant', "Davlat granti"
        CONTRACT = 'contract', "To‘lov-shartnoma"

    class DocumentStatusChoices(models.TextChoices):
        AVAILABLE = 'bor', "Bor"
        MISSING = 'yoq', "Yo‘q"
        INCOMPLETE = 'chala', "Chala"

    class DocumentTypeChoices(models.TextChoices):
        CERTIFICATE = 'shahodatnoma', "Shahodatnoma"
        DIPLOMA = 'diplom', "Diplom"

    SEMESTER_CHOICES = [(i, f"{i}-semestr") for i in range(1, 11)]

    full_name = models.CharField("F.I.Sh.", max_length=255)
    student_hemis_id = models.CharField("Talaba ID", max_length=100, unique=True, null=True, blank=True)
    COURSE_CHOICES = [(i, f"{i}-kurs") for i in range(1, 6)]
    course_year = models.PositiveSmallIntegerField("Kursi", choices=COURSE_CHOICES, default=1)
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Guruh")
    education_type = models.CharField(
        "To'lov shakli",
        max_length=20,
        choices=EducationTypeChoices.choices,
        default=EducationTypeChoices.CONTRACT
    )

    date_of_birth = models.DateField("Tug'ilgan sanasi", null=True, blank=True)
    birth_place = models.CharField("Tug'ilgan joyi (matn)", max_length=255, null=True, blank=True)
    gender = models.CharField("Jinsi", max_length=10, choices=GenderChoices.choices)
    phone_number = models.CharField("Telefon raqami", max_length=50)
    phone_number_2 = models.CharField("Telefon raqami 2", max_length=50, null=True, blank=True)
    citizenship = models.ForeignKey(
        Country,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Fuqaroligi",
        related_name="students_citizenship"
    )
    region = ChainedForeignKey(
        Region,
        chained_field="citizenship",
        chained_model_field="country",
        show_all=False,
        auto_choose=False,
        sort=True,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Viloyati",
        related_name="students_region"
    )
    district = ChainedForeignKey(
        District,
        chained_field="region",
        chained_model_field="region",
        show_all=False,
        auto_choose=False,
        sort=True,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Tumani"
    )
    address = models.TextField("Yashash manzili (ko'cha, uy)")
    nationality = models.CharField("Millati", max_length=100, null=True, blank=True)

    passport_series_number = models.CharField("Pasport SR", max_length=20, unique=True)
    personal_pin = models.CharField("JShShIR", max_length=14, unique=True)
    passport_issued_by = models.CharField("Kim tomonidan berilgan", max_length=255)
    passport_issue_date = models.DateField("Berilgan sanasi", null=True, blank=True)
    passport_expiry_date = models.DateField("Amal qilish muddati", null=True, blank=True)

    status = models.CharField("Statusi", max_length=20, choices=StatusChoices.choices, default=StatusChoices.ACTIVE)
    education_form = models.CharField("Ta'lim shakli", max_length=20, choices=EducationFormChoices.choices)
    current_semester = models.PositiveSmallIntegerField("Semestr", choices=SEMESTER_CHOICES, default=1)
    entry_score = models.FloatField("To'plagan bali", null=True, blank=True)
    document = models.CharField("Hujjat holati", max_length=10, choices=DocumentStatusChoices.choices, null=True, blank=True)
    document_info = models.CharField("Dokument haqida", max_length=255, null=True, blank=True)

    previous_education_country = models.ForeignKey(
        Country,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Davlati",
        related_name="students_previous_country"
    )
    previous_education_region = ChainedForeignKey(
        Region,
        chained_field="previous_education_country",
        chained_model_field="country",
        show_all=False,
        auto_choose=True,
        sort=True,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Viloyati",
        related_name="students_previous_region"
    )
    previous_institution = models.CharField("Ta'lim olgan muassasasi", max_length=255, null=True, blank=True)
    document_type = models.CharField("Hujjat turi", max_length=20, choices=DocumentTypeChoices.choices, null=True, blank=True)
    document_number = models.CharField("Hujjat raqami", max_length=255, null=True, blank=True)
    previous_graduation_year = models.IntegerField("Tamomlagan yili", null=True, blank=True)
    certificate_info = models.CharField("Sertifikat", max_length=255, null=True, blank=True)
    transferred_from_university = models.CharField("Ko'chirgan OTM", max_length=255, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Talaba"
        verbose_name_plural = "1. Talabalar"
        ordering = ['full_name']

    def __str__(self):
        return self.full_name


class StudentHistory(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='history', verbose_name="Talaba")
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, verbose_name="O‘quv yili")

    # O'sha paytdagi ma'lumotlar
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Guruh")
    course_year = models.PositiveSmallIntegerField("Kurs", choices=Student.COURSE_CHOICES)

    education_form = models.CharField("Ta'lim shakli", max_length=20, choices=Student.EducationFormChoices.choices)

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")

    class Meta:
        verbose_name = "Talaba tarixi (Arxiv)"
        verbose_name_plural = "Talaba tarixi (Arxiv)"
        unique_together = ('student', 'academic_year')  # Bir yilda bitta talaba uchun faqat bitta tarix bo'lsin
        ordering = ['-academic_year', 'student__full_name']

    def __str__(self):
        return f"{self.student.full_name} — {self.academic_year.name} ({self.course_year}-kurs)"

# =============================================================================
# 💰 KONTRAKT VA TO‘LOVLAR
# =============================================================================
class Contract(models.Model):
    class ContractTypeChoices(models.TextChoices):
        MODUL = 'modul', "Kredit-modul"
        CONTRACT = 'contract', "To'lov-shartnoma"

    class GrantTypeChoices(models.TextChoices):
        NONE = 'none', "Imtiyoz yo‘q"
        TYPE1 = 'CR', "Iqtidorli talabalar (25%)"
        TYPE2 = 'MT', "Faol talabalar (15%)"
        TYPE3 = "QH", "Qurbon Hayiti"
        TYPE4 = "QB", "Qabul"
        TYPE5 = 'XM', "Xodimlar"
        TYPE6 = 'IH', "Ijtimoiy himoya"


    student = models.ForeignKey('Student', on_delete=models.CASCADE, verbose_name="Talaba")
    academic_year = models.ForeignKey('AcademicYear', on_delete=models.PROTECT, verbose_name="O‘quv yili", related_name="contracts")
    contract_type = models.CharField("To'lov maqsadi", max_length=10, choices=ContractTypeChoices.choices, default=ContractTypeChoices.CONTRACT)

    contract_number = models.CharField("Shartnoma raqami", max_length=100)
    contract_date = models.DateField("Shartnoma sanasi", default=datetime.date.today)

    amount = models.DecimalField("Shartnoma summasi", max_digits=12, decimal_places=2)

    grant_type = models.CharField("Ichki grant turi", max_length=10, choices=GrantTypeChoices.choices, default=GrantTypeChoices.NONE)
    grant_date = models.DateField("Ichki grant sanasi", null=True, blank=True)
    grant_percent = models.DecimalField("Grant foizi (%)", max_digits=5, decimal_places=2, null=True, blank=True)
    grant_amount = models.DecimalField("Grant summasi (so‘m)", max_digits=12, decimal_places=2, null=True, blank=True, editable=True)

    class Meta:
        verbose_name = "Shartnoma"
        verbose_name_plural = "Shartnomalar"
        # unique_together = ('student', 'academic_year')

    def clean(self):
        # 1. Agar grant turi tanlanmagan bo'lsa, tekshirish shart emas
        if self.grant_type == self.GrantTypeChoices.NONE:
            return

        # 2. Qabul (QB) va Qurbon Hayiti (QH) konfliktini tekshirish
        RESTRICTED_TYPES = [self.GrantTypeChoices.TYPE3, self.GrantTypeChoices.TYPE4]  # QH va QB

        if self.grant_type in RESTRICTED_TYPES:
            # Shu talaba va shu o'quv yili uchun boshqa shartnomalarni qidiramiz
            conflicting_contracts = Contract.objects.filter(
                student=self.student,
                academic_year=self.academic_year
            ).exclude(id=self.id)  # Hozirgi o'zgartirilayotgan kontraktni hisobga olmaymiz

            # Agar bazada allaqachon QH yoki QB bor bo'lsa
            if conflicting_contracts.filter(grant_type__in=RESTRICTED_TYPES).exists():
                raise ValidationError(
                    "Talaba bir o‘quv yilida 'Qurbon Hayiti' va 'Qabul' grantlarining faqat bittasini olishi mumkin!"
                )

    def save(self, *args, **kwargs):
        self.clean()  # Save qilishdan oldin clean ni chaqiramiz
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.contract_number} - {self.student.full_name} - {self.academic_year}"


class Payment(models.Model):
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, verbose_name="Shartnoma")
    amount = models.DecimalField("To'lov summasi", max_digits=12, decimal_places=2)
    payment_date = models.DateField("To'lov sanasi", default=timezone.now)
    description = models.TextField("Izoh", null=True, blank=True)

    class Meta:
        verbose_name = "To'lov"
        verbose_name_plural = "To'lovlar"

    def __str__(self):
        return f"{self.contract.student.full_name} - {self.amount} so'm ({self.payment_date})"


# =============================================================================
# 📚 FANLAR VA QARZDORLIK
# =============================================================================
class Subject(models.Model):
    name = models.CharField("Fan nomi", max_length=255,db_index=True)

    class Meta:
        verbose_name = "Fan"
        verbose_name_plural = "Fanlar"
        ordering = ['name']

    def __str__(self):
        return self.name


class PerevodRate(models.Model):
    year = models.ForeignKey('AcademicYear', on_delete=models.CASCADE, verbose_name="O‘quv yili")
    amount = models.DecimalField("1 kredit uchun to‘lov (Perevod)", max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = "Perevod stavkasi"
        verbose_name_plural = "Perevod stavkalari"
        unique_together = ('year',)
        ordering = ['-year']

    def __str__(self):
        return f"{self.year.name} — {self.amount} so‘m/kredit"

class SubjectRate(models.Model):
    year = models.ForeignKey('AcademicYear', on_delete=models.CASCADE, verbose_name="O‘quv yili")
    specialty = models.ForeignKey('Specialty', on_delete=models.CASCADE, verbose_name="Yo'nalish")
    education_form = models.CharField(
        "Ta'lim shakli",
        max_length=20,
        choices=Student.EducationFormChoices.choices,
        default=Student.EducationFormChoices.FULL_TIME
    )
    amount = models.DecimalField("Kontrakt narxi", max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = "Fan stavkasi"
        verbose_name_plural = "Fan stavkalari"
        unique_together = ('year', 'specialty', 'education_form')
        ordering = ['-year']

    def __str__(self):
        return f"{self.year.name} | {self.specialty.name} ({self.get_education_form_display()}) — {self.amount}"

class SubjectDebt(models.Model):
    class DebtTypeChoices(models.TextChoices):
        DU = 'du', "DU fandan qarzdorlik"
        PEREVOD = 'perevod', "Perevod fandan qarzdorlik"

    class StatusChoices(models.TextChoices):
        CLOSED = 'yopildi', "Yopildi"
        OPEN = 'yopilmadi', "Yopilmadi"

    SEMESTER_CHOICES = [(i, f"{i}-semestr") for i in range(1, 11)]
    student = models.ForeignKey('Student', on_delete=models.CASCADE, verbose_name="Talaba")
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE, verbose_name="Fan")
    academic_year = models.ForeignKey('AcademicYear', on_delete=models.PROTECT, verbose_name="O‘quv yili")
    semester = models.PositiveSmallIntegerField("Semestr", choices=SEMESTER_CHOICES, default=1)
    year_credit = models.PositiveSmallIntegerField("O‘quv yili umumiy kreditlari", default=0)
    credit = models.PositiveSmallIntegerField("Fan krediti", default=0)
    debt_type = models.CharField("Qarzdorlik turi", max_length=10, choices=DebtTypeChoices.choices)
    amount = models.DecimalField("Qarzdorlik summasi (so‘m)", max_digits=14, decimal_places=2, blank=True, null=True)
    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, verbose_name="Shartnoma", blank=True, null=True)
    amount_summ = models.DecimalField("To'lov summasi", max_digits=12, decimal_places=2, blank=True, null=True)
    payment_date = models.DateField("To'lov sanasi", default=timezone.now, blank=True, null=True)
    status = models.CharField(
        "Holati",
        max_length=10,
        choices=StatusChoices.choices,
        default=StatusChoices.OPEN
    )
    class Meta:
        verbose_name = "Fan bo‘yicha qarzdorlik"
        verbose_name_plural = "Fanlar bo‘yicha qarzdorliklar"
        unique_together = ('student', 'subject', 'academic_year')

    def __str__(self):
        return f"{self.student.full_name} — {self.subject.name} ({self.get_debt_type_display()})"

    # YANGI QO'SHILGAN SAVE METODI
    # def save(self, *args, **kwargs):
    #     fan_credit = Decimal(self.credit or 0)
    #     yil_credit = Decimal(self.year_credit or 0)
    #     calculated_amount = Decimal('0.00')
    #     if self.debt_type == 'du':
    #         contract = Contract.objects.filter(student=self.student, academic_year=self.academic_year).first()
    #         if contract and yil_credit > 0:
    #             calculated_amount = (Decimal(contract.amount) / yil_credit) * fan_credit
    #     elif self.debt_type == 'perevod':
    #         rate = PerevodRate.objects.filter(year=self.academic_year).first()
    #         if rate:
    #             calculated_amount = Decimal(rate.amount) * fan_credit
    #
    #     self.amount = calculated_amount.quantize(Decimal('1.'), rounding=ROUND_HALF_UP)
    #
    #     super().save(*args, **kwargs)

    def save(self, *args, **kwargs):
        fan_credit = Decimal(self.credit or 0)
        yil_credit = Decimal(self.year_credit or 0)
        calculated_amount = Decimal('0.00')

        # 1. Agar qarzdorlik turi "DU" bo'lsa
        if self.debt_type == 'du':
            # Talabaning yo'nalishini (Specialty) aniqlaymiz
            specialty = None
            if self.student.group and self.student.group.specialty:
                specialty = self.student.group.specialty

            # Talabaning ta'lim shaklini olamiz (Kunduzgi/Sirtqi)
            student_form = self.student.education_form

            # Agar yo'nalish va yil bo'yicha SubjectRate belgilangan bo'lsa
            if specialty:
                subject_rate = SubjectRate.objects.filter(
                    year=self.academic_year,
                    specialty=specialty,
                    education_form=student_form  # <--- YANGI FILTR
                ).first()

                # FORMULA: (SubjectRate summasi / Yillik kredit) * Fan krediti
                if subject_rate and yil_credit > 0:
                    calculated_amount = (Decimal(subject_rate.amount) / yil_credit) * fan_credit

        # 2. Agar qarzdorlik turi "Perevod" bo'lsa
        elif self.debt_type == 'perevod':
            rate = PerevodRate.objects.filter(year=self.academic_year).first()
            if rate:
                calculated_amount = Decimal(rate.amount) * fan_credit

        # Yaxlitlash
        self.amount = calculated_amount.quantize(Decimal('1.'), rounding=ROUND_HALF_UP)

        super().save(*args, **kwargs)

class Hisobot(Student):
    class Meta:
        proxy = True
        verbose_name = "Hisobotlar"
        verbose_name_plural = "2. Hisobotlar"