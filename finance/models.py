from django.db import models

class AcademicSalary(models.Model):
    DEGREE_CHOICES = [
        ('none', "Yo'q"),
        ('phd', "PhD"),
        ('dsc', "DSc"),
    ]

    # Yangilangan unvonlar ro'yxati
    TITLE_CHOICES = [
        ('none', "Yo'q"),
        ('teacher', "O'qituvchi"),
        ('senior_teacher', "Katta o'qituvchi"),
        ('docent', "Dotsent"),
        ('professor', "Professor"),
        ('academic', "Akademik"),
    ]

    JOB_TYPE_CHOICES = [
        ('main', "Asosiy"),
        ('hourly', "Soatbay"),
    ]

    scientific_degree = models.CharField(
        max_length=10,
        choices=DEGREE_CHOICES,
        default='none',
        verbose_name="Ilmiy daraja"
    )

    scientific_title = models.CharField(
        max_length=20,  # Unvon nomi uzaygani uchun uzunlikni oshirdim
        choices=TITLE_CHOICES,
        default='none',
        verbose_name="Ilmiy unvon"
    )

    job_type = models.CharField(
        max_length=10,
        choices=JOB_TYPE_CHOICES,
        default='main',
        verbose_name="Ish turi"
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="1 soat uchun to'lanadigan haq"
    )

    base_salary = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Oklad (Asosiy uchun)",
        blank=True,
        null=True,
    )

    allowance = models.DecimalField(
        max_digits=2,
        decimal_places=2,
        verbose_name="Nadbavka (Ustama, Asosiy uchun)",
        blank = True,
        null = True,
    )
    annual_base_load = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Yillik asosiy yuklama",
        blank=True,
        null=True,
    )


    class Meta:
        verbose_name = "Ilmiy maosh"
        verbose_name_plural = "Ilmiy maoshlar"

    def __str__(self):
        return f"{self.get_scientific_title_display()} - {self.get_scientific_degree_display()}"