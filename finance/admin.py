from django.contrib import admin
from django import forms
from .models import AcademicSalary


class AcademicSalaryForm(forms.ModelForm):
    # 1. Barcha summa maydonlarini "money-input" klassi bilan qamrab olamiz
    base_salary = forms.CharField(
        label="Oklad",
        required=False,
        widget=forms.TextInput(attrs={'class': 'money-input', 'autocomplete': 'off'})
    )
    allowance = forms.CharField(
        label="Nadbavka (Ustama)",
        required=False,
        widget=forms.TextInput(attrs={'class': 'money-input', 'autocomplete': 'off'})
    )
    # Amount endi editable, shuning uchun bunga ham widget qo'shamiz
    amount = forms.CharField(
        label="1 soat uchun to'lanadigan haq",
        widget=forms.TextInput(attrs={'class': 'money-input', 'autocomplete': 'off'})
    )

    class Meta:
        model = AcademicSalary
        fields = '__all__'

    # Probellarni tozalovchi universal funksiya
    def clean_field_money(self, field_name):
        value = self.cleaned_data.get(field_name)
        if value:
            return value.replace(' ', '').replace(',', '.')
        return 0

    def clean_base_salary(self):
        return self.clean_field_money('base_salary')

    def clean_allowance(self):
        return self.clean_field_money('allowance')

    def clean_amount(self):
        return self.clean_field_money('amount')


@admin.register(AcademicSalary)
class AcademicSalaryAdmin(admin.ModelAdmin):
    form = AcademicSalaryForm

    list_display = (
        'scientific_title',
        'scientific_degree',
        'job_type',
        'get_base_salary_display',
        'get_allowance_display',
        'get_amount_display'
    )

    list_filter = ('scientific_title', 'scientific_degree', 'job_type')
    list_display_links = ('scientific_title',)
    list_per_page = 20

    # Tahrirlash oynasidagi maydonlar tartibi
    fields = ('scientific_title', 'scientific_degree', 'job_type', 'amount', 'base_salary', 'allowance')

    # amount endi readonly EMAS (o'zgartirish mumkin)
    # readonly_fields = ()  <- olib tashlandi

    # Formatlash funksiyalari
    def format_money(self, value):
        if value:
            return '{:,.2f}'.format(value).replace(',', ' ') + " so'm"
        return "0.00 so'm"

    def get_base_salary_display(self, obj):
        return self.format_money(obj.base_salary)

    get_base_salary_display.short_description = "Oklad"
    get_base_salary_display.admin_order_field = 'base_salary'

    def get_allowance_display(self, obj):
        return self.format_money(obj.allowance)

    get_allowance_display.short_description = "Nadbavka"
    get_allowance_display.admin_order_field = 'allowance'

    def get_amount_display(self, obj):
        return self.format_money(obj.amount)

    get_amount_display.short_description = "1 soat uchun to'lanadigan haq"
    get_amount_display.admin_order_field = 'amount'

    class Media:
        js = (
            'admin/js/jquery.init.js',
            'admin/js/money_input.js',
        )