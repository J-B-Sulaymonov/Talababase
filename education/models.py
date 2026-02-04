from django.core.exceptions import ValidationError
from django.db import models

from kadrlar.models import Teacher
from students.models import Specialty, AcademicYear, Subject, Group


class EducationPlan(models.Model):
    COURSE_CHOICES = (
        (1, '1-kurs'),
        (2, '2-kurs'),
        (3, '3-kurs'),
        (4, '4-kurs'),
        (5, '5-kurs'),
    )
    specialty = models.ForeignKey(
        Specialty,
        on_delete=models.CASCADE,
        verbose_name="Yo'nalish"
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        verbose_name="O'quv yili"
    )
    course = models.IntegerField(
        choices=COURSE_CHOICES,
        default=1,
        verbose_name="Kurs"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.specialty} - {self.get_course_display()} ({self.academic_year})"

    class Meta:
        verbose_name = "O'quv reja"
        verbose_name_plural = "O'quv rejalar"
        unique_together = ['specialty', 'academic_year', 'course']
        ordering = ['-academic_year', 'specialty', 'course']


class PlanSubject(models.Model):
    SEMESTER_CHOICES = [
        (1, '1-semestr'), (2, '2-semestr'),
        (3, '3-semestr'), (4, '4-semestr'),
        (5, '5-semestr'), (6, '6-semestr'),
        (7, '7-semestr'), (8, '8-semestr'),
    ]

    TYPE_CHOICES = [
        ('majburiy', 'Majburiy'),
        ('tanlov', 'Tanlov'),
    ]

    education_plan = models.ForeignKey(
        'EducationPlan',
        on_delete=models.CASCADE,
        related_name='subjects',
        verbose_name="O'quv reja"
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        verbose_name="Fan"
    )

    subject_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default='majburiy',
        verbose_name="Fan turi"
    )

    credit = models.PositiveSmallIntegerField(verbose_name="Kredit", default=6)
    semester = models.PositiveSmallIntegerField(choices=SEMESTER_CHOICES, verbose_name="Semestr")

    # Haftasiga necha soat dars bo'lishi
    semester_time = models.PositiveIntegerField(
        verbose_name="Haftalik soat",
        default=4,
        help_text="Masalan: 4 soat (Auditoriya soati / 15 hafta)"
    )

    total_hours = models.PositiveIntegerField(
        verbose_name="Umumiy soat",
        blank=True,
        null=True,
        help_text="Avtomatik hisoblanadi (Kredit * 30)"
    )

    lecture_hours = models.PositiveIntegerField(default=0, verbose_name="Ma'ruza")
    practice_hours = models.PositiveIntegerField(default=0, verbose_name="Amaliyot")
    lab_hours = models.PositiveIntegerField(default=0, verbose_name="Laboratoriya")
    seminar_hours = models.PositiveIntegerField(default=0, verbose_name="Seminar")

    # independent_hours - OLIB TASHLANDI

    class Meta:
        verbose_name = "Rejadagi fan"
        verbose_name_plural = "Rejadagi fanlar"
        ordering = ['semester', 'subject__name']
        unique_together = ['education_plan', 'subject', 'semester']

    def __str__(self):
        return f"{self.education_plan} {self.subject} ({self.semester}-semestr)"

    def clean(self):
        """
        Ma'lumotlar to'g'riligini tekshirish.
        DIQQAT: Mustaqil ta'lim olib tashlangani uchun, endi
        Total Hours == Auditoriya soatlari yig'indisi bo'lishi shart EMAS.
        Chunki Total Hours kreditga qarab 180 bo'lishi mumkin, auditoriya esa 60.
        Shuning uchun bu yerdagi qat'iy tekshiruv olib tashlandi.
        """
        pass

    def save(self, *args, **kwargs):
        """Avtomatizatsiya"""

        # 1. Umumiy soatni hisoblash (Kredit * 30)
        if not self.total_hours and self.credit:
            self.total_hours = self.credit * 30

        # 2. Haftalik soatni (semester_time) avtomatik hisoblash
        auditorium = self.lecture_hours + self.practice_hours + self.lab_hours + self.seminar_hours

        # Standart semestr 15 hafta deb hisoblanadi.
        if self.semester_time == 0 and auditorium > 0:
            self.semester_time = int(auditorium / 15)

        super().save(*args, **kwargs)


class Workload(models.Model):
    # 1. FAN (Filtrlash uchun asos)
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        verbose_name="Fan"
    )

    # 2. REJADAGI FANLAR (Many-to-Many) - Endi ko'plikda
    plan_subjects = models.ManyToManyField(
        PlanSubject,
        verbose_name="Rejadagi fanlar",
        help_text="Ushbu fan bo'yicha bir yoki bir nechta rejalarni tanlang (Masalan: Iqtisodiyot va Moliya)."
    )

    # 3. GURUHLAR (Many-to-Many)
    groups = models.ManyToManyField(
        Group,
        verbose_name="Guruhlar",
        help_text="Tanlangan rejalarga mos guruhlarni tanlang."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Yuklama hajmi"
        verbose_name_plural = "Yuklamalar hajmi"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.subject.name}"

    def clean(self):
        """
        Validatsiya
        """
        super().clean()
        # M2M maydonlarni bu yerda (save bo'lmasdan oldin) tekshirish qiyin,
        # shuning uchun asosiy tekshiruvlarni Admin Formda qilamiz.
        pass

    def calculate_total_hours(self):
        """
        Jami soatni hisoblash.
        Mantiq: Har bir tanlangan guruhni olamiz, uning yo'nalishiga (Specialty)
        mos keluvchi PlanSubject ni topamiz va soatini qo'shamiz.
        """
        if not self.pk:
            return 0

        total_hours = 0

        # Barcha tanlangan rejalar va guruhlarni olamiz
        selected_plans = self.plan_subjects.all()  # QuerySet
        selected_groups = self.groups.all()  # QuerySet

        if not selected_plans or not selected_groups:
            return 0

        # Har bir guruh uchun hisoblaymiz
        for group in selected_groups:
            # Shu guruhning yo'nalishiga mos keladigan rejani tanlanganlar ichidan qidiramiz
            # (PlanSubject -> EducationPlan -> Specialty)
            match_plan = selected_plans.filter(education_plan__specialty=group.specialty).first()

            if match_plan:
                # Agar reja topilsa, uning soatlarini qo'shamiz
                h = match_plan.lecture_hours + match_plan.practice_hours + \
                    match_plan.lab_hours + match_plan.seminar_hours
                total_hours += h

        return total_hours


class SubGroup(models.Model):
    """
    Guruhni bo'laklash (masalan: 1-yarim guruh, 2-yarim guruh)
    """
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='subgroups', verbose_name="Asosiy guruh")
    name = models.CharField(max_length=50, verbose_name="Kichik guruh nomi")

    class Meta:
        verbose_name = "Kichik guruh"
        verbose_name_plural = "Kichik guruhlar"
        unique_together = ['group', 'name']

    def __str__(self):
        return f"{self.group.name} ({self.name})"


class Stream(models.Model):
    """
    Oqim (Patok) - Workloadning ijro qismi.
    """
    LESSON_TYPES = [
        ('lecture', "Ma'ruza"),
        ('practice', "Amaliyot"),
        ('seminar', "Seminar"),
        ('lab', "Laboratoriya"),
    ]

    # Asosiy bog'lovchi - WORKLOAD
    workload = models.ForeignKey(
        'Workload',  # String reference agar Workload pastroqda yozilgan bo'lsa yoki shu faylda bo'lsa
        on_delete=models.CASCADE,
        related_name='streams',
        verbose_name="Yuklama (Workload)"
    )

    name = models.CharField(max_length=255, verbose_name="Nomi", help_text="Masalan: Ma'ruza-1 (Iqtisodiyot)")

    teacher = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="O'qituvchi")
    lesson_type = models.CharField(max_length=20, choices=LESSON_TYPES, verbose_name="Dars turi")

    # Guruhlar (Faqat Workladdagilar tanlanadi)
    groups = models.ManyToManyField(Group, blank=True, verbose_name="Guruhlar", related_name='streams')
    sub_groups = models.ManyToManyField(SubGroup, blank=True, verbose_name="Kichik guruhlar", related_name='streams')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Patok"
        verbose_name_plural = "Patok"
        ordering = ['lesson_type', 'name']

    def __str__(self):
        # Workload orqali fanni nomini olamiz
        return f"{self.workload.subject.name} - {self.name} ({self.get_lesson_type_display()})"

    def clean(self):
        """
        Validatsiya:
        1. Agar oqim saqlanayotgan bo'lsa, tanlangan guruhlar Workload ichida borligini tekshirish kerak.
        (Admin panelda filtrlash vizual, bu yerda esa backend himoyasi)
        """
        super().clean()
        # M2M validatsiyasi odatda save() dan keyin ishlaydi yoki signal orqali,
        # lekin bu yerda mantiqiy tekshiruv qoldiramiz.
        pass

