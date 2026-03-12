from django.db import models
from kadrlar.models import Teacher

class HourlyRate(models.Model):
    teacher = models.OneToOneField(
        Teacher,
        on_delete=models.CASCADE,
        related_name='hourly_rate',
        verbose_name="O'qituvchi"
    )
    
    hourly_rate = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="1 soat uchun haq"
    )

    class Meta:
        verbose_name = "Soatbay stavka"
        verbose_name_plural = "Soatbay stavkalar"

    def __str__(self):
        return f"{self.teacher} - {self.hourly_rate} so'm"

class MainSalary(models.Model):
    teacher = models.OneToOneField(
        Teacher,
        on_delete=models.CASCADE,
        related_name='main_salary',
        verbose_name="O'qituvchi (Asosiy)"
    )
    
    base_salary = models.DecimalField("Oklad", max_digits=12, decimal_places=2, default=0)
    allowance_percent = models.DecimalField("Nadbavka (%)", max_digits=5, decimal_places=2, default=0, help_text="Masalan: 20")
    job_rate = models.DecimalField("Shtat birligi", max_digits=4, decimal_places=2, default=1.0)
    vacation_pay = models.DecimalField("Otpusknoy", max_digits=12, decimal_places=2, default=0)
    annual_base_load = models.DecimalField("Yillik asosiy yuklama", max_digits=10, decimal_places=2, default=600)

    @property
    def allowance_amount(self):
        return self.base_salary * (self.allowance_percent / 100)

    @property
    def monthly_salary(self):
        return (self.base_salary + self.allowance_amount) * self.job_rate

    @property
    def annual_salary(self):
        return self.monthly_salary * 12

    @property
    def total_annual_salary(self):
        return self.annual_salary + self.vacation_pay

    @property
    def calculated_hourly_rate(self):
        if self.annual_base_load > 0:
            return self.total_annual_salary / self.annual_base_load
        return 0

    class Meta:
        verbose_name = "Asosiy stavka"
        verbose_name_plural = "Asosiy stavkalar"

    def __str__(self):
        return f"{self.teacher} - {self.base_salary} so'm (Oklad)"