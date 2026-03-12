from django.contrib import admin
from django import forms
from .models import HourlyRate, MainSalary

class HourlyRateForm(forms.ModelForm):
    hourly_rate = forms.CharField(
        label="1 soat uchun haq",
        widget=forms.TextInput(attrs={'class': 'money-input', 'autocomplete': 'off'})
    )

    class Meta:
        model = HourlyRate
        fields = '__all__'

    def clean_hourly_rate(self):
        value = self.cleaned_data.get('hourly_rate')
        if value:
            if isinstance(value, str):
                return value.replace(' ', '').replace(',', '.')
            return value
        return 0

@admin.register(HourlyRate)
class HourlyRateAdmin(admin.ModelAdmin):
    form = HourlyRateForm
    change_list_template = "admin/finance/hourlyrate/change_list.html"

    list_display = (
        'teacher_name',
        'department_name',
        'scientific_degree',
        'scientific_title',
        'is_active_teacher',
        'hourly_rate'
    )
    list_editable = ('hourly_rate',)

    search_fields = (
        'teacher__employee__first_name', 
        'teacher__employee__last_name', 
        'teacher__employee__department__name'
    )
    
    autocomplete_fields = ['teacher']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('teacher__employee', 'teacher__employee__department')

    def teacher_name(self, obj):
        return str(obj.teacher)
    teacher_name.short_description = "O'qituvchi"
    teacher_name.admin_order_field = 'teacher__employee__last_name'

    def department_name(self, obj):
        if obj.teacher.employee.department:
            return obj.teacher.employee.department.name
        return "-"
    department_name.short_description = "Kafedra"
    department_name.admin_order_field = 'teacher__employee__department__name'

    def scientific_degree(self, obj):
        return obj.teacher.employee.get_scientific_degree_display()
    scientific_degree.short_description = "Ilmiy daraja"
    scientific_degree.admin_order_field = 'teacher__employee__scientific_degree'

    def scientific_title(self, obj):
        return obj.teacher.employee.get_scientific_title_display()
    scientific_title.short_description = "Ilmiy unvon"
    scientific_title.admin_order_field = 'teacher__employee__scientific_title'

    def is_active_teacher(self, obj):
        from django.utils.html import format_html
        if obj.teacher.employee.status == 'active':
            return format_html('<img src="/static/admin/img/icon-yes.svg" alt="True">')
        return format_html('<img src="/static/admin/img/icon-no.svg" alt="False">')
    is_active_teacher.short_description = "Faolmi?"

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('sync-teachers/', self.admin_site.admin_view(self.sync_teachers), name='finance_hourlyrate_sync'),
        ]
        return custom_urls + urls

    def sync_teachers(self, request):
        from django.shortcuts import redirect
        from django.contrib import messages
        from kadrlar.models import Teacher
        
        active_hourly_teachers = Teacher.objects.filter(employee__status='active', work_type_hourly=True)
        created_count = 0
        for teacher in active_hourly_teachers:
            obj, created = HourlyRate.objects.get_or_create(teacher=teacher, defaults={'hourly_rate': 0})
            if created:
                created_count += 1
        
        if created_count > 0:
            messages.success(request, f"{created_count} ta yangi soatbay o'qituvchi muvaffaqiyatli sinxronizatsiya qilindi.")
        else:
            messages.info(request, "Yangi soatbay o'qituvchilar topilmadi. Barcha faollari ro'yxatda bor.")
            
        return redirect('admin:finance_hourlyrate_changelist')

    class Media:
        js = (
            'admin/js/jquery.init.js',
            'admin/js/money_input.js',
        )

class MainSalaryForm(forms.ModelForm):
    base_salary = forms.CharField(label="Oklad", widget=forms.TextInput(attrs={'class': 'money-input', 'autocomplete': 'off'}))
    allowance_percent = forms.CharField(label="Nadbavka (%)", widget=forms.TextInput(attrs={'class': 'money-input', 'autocomplete': 'off'}))
    job_rate = forms.CharField(label="Shtat birligi", widget=forms.TextInput(attrs={'class': 'money-input', 'autocomplete': 'off'}))
    vacation_pay = forms.CharField(label="Otpusknoy", widget=forms.TextInput(attrs={'class': 'money-input', 'autocomplete': 'off'}))
    annual_base_load = forms.CharField(label="Yillik asosiy yuklama", widget=forms.TextInput(attrs={'class': 'money-input', 'autocomplete': 'off'}))

    class Meta:
        model = MainSalary
        fields = '__all__'

    def clean_money_field(self, field_name):
        value = self.cleaned_data.get(field_name)
        if value:
            if isinstance(value, str):
                return value.replace(' ', '').replace(',', '.')
            return value
        return 0

    def clean_base_salary(self): return self.clean_money_field('base_salary')
    def clean_allowance_percent(self): return self.clean_money_field('allowance_percent')
    def clean_job_rate(self): return self.clean_money_field('job_rate')
    def clean_vacation_pay(self): return self.clean_money_field('vacation_pay')
    def clean_annual_base_load(self): return self.clean_money_field('annual_base_load')

@admin.register(MainSalary)
class MainSalaryAdmin(admin.ModelAdmin):
    form = MainSalaryForm
    change_list_template = "admin/finance/mainsalary/change_list.html"

    list_display = (
        'teacher_name',
        'base_salary',
        'allowance_percent',
        'job_rate',
        'get_annual_salary_display',
        'vacation_pay',
        'annual_base_load',
        'get_calculated_hourly_rate_display'
    )
    list_editable = (
        'base_salary',
        'allowance_percent',
        'job_rate',
        'vacation_pay',
        'annual_base_load'
    )

    search_fields = ('teacher__employee__first_name', 'teacher__employee__last_name', 'teacher__employee__department__name')
    autocomplete_fields = ['teacher']

    readonly_fields = (
        'get_allowance_amount_display',
        'get_monthly_salary_display',
        'get_annual_salary_display',
        'get_total_annual_salary_display',
        'get_calculated_hourly_rate_display'
    )
    
    fieldsets = (
        ("Asosiy ma'lumotlar", {
            'fields': ('teacher', 'base_salary', 'allowance_percent', 'job_rate')
        }),
        ("Avtomatik hisoblangan qo'shimchalar", {
            'fields': ('get_allowance_amount_display', 'get_monthly_salary_display', 'get_annual_salary_display')
        }),
        ("Yillik yuklama va Otpusknoy", {
            'fields': ('vacation_pay', 'get_total_annual_salary_display', 'annual_base_load')
        }),
        ("Natija (1 soatlik stavka)", {
            'fields': ('get_calculated_hourly_rate_display',)
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('teacher__employee', 'teacher__employee__department')

    def format_money(self, value):
        if value:
            return '{:,.2f}'.format(value).replace(',', ' ')
        return "0.00"

    def teacher_name(self, obj): return str(obj.teacher)
    teacher_name.short_description = "O'qituvchi"

    def department_name(self, obj):
        return obj.teacher.employee.department.name if obj.teacher.employee.department else "-"
    department_name.short_description = "Kafedra"

    def is_active_teacher(self, obj):
        from django.utils.html import format_html
        if obj.teacher.employee.status == 'active':
            return format_html('<img src="/static/admin/img/icon-yes.svg" alt="True">')
        return format_html('<img src="/static/admin/img/icon-no.svg" alt="False">')
    is_active_teacher.short_description = "Faolmi?"

    # Displays
    def get_base_salary_display(self, obj): return self.format_money(obj.base_salary)
    get_base_salary_display.short_description = "Oklad"

    def get_allowance_amount_display(self, obj): return self.format_money(obj.allowance_amount)
    get_allowance_amount_display.short_description = "Nadbavka (so'm)"

    def get_monthly_salary_display(self, obj): return self.format_money(obj.monthly_salary)
    get_monthly_salary_display.short_description = "Oylik ish haqi"

    def get_annual_salary_display(self, obj): return self.format_money(obj.annual_salary)
    get_annual_salary_display.short_description = "Yillik ish haqi"

    def get_vacation_pay_display(self, obj): return self.format_money(obj.vacation_pay)
    get_vacation_pay_display.short_description = "Otpusknoy"

    def get_total_annual_salary_display(self, obj): return self.format_money(obj.total_annual_salary)
    get_total_annual_salary_display.short_description = "Jami yillik ish haqi"

    def get_calculated_hourly_rate_display(self, obj): 
        from django.utils.html import format_html
        return format_html('<b>{}</b>', self.format_money(obj.calculated_hourly_rate))
    get_calculated_hourly_rate_display.short_description = "Stavka"

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('sync-teachers/', self.admin_site.admin_view(self.sync_teachers), name='finance_mainsalary_sync'),
        ]
        return custom_urls + urls

    def sync_teachers(self, request):
        from django.shortcuts import redirect
        from django.contrib import messages
        from kadrlar.models import Teacher
        
        active_main_teachers = Teacher.objects.filter(employee__status='active', work_type_permanent=True)
        created_count = 0
        for teacher in active_main_teachers:
            obj, created = MainSalary.objects.get_or_create(teacher=teacher)
            if created:
                created_count += 1
        
        if created_count > 0:
            messages.success(request, f"{created_count} ta yangi asosiy (shtat) o'qituvchi muvaffaqiyatli sinxronizatsiya qilindi.")
        else:
            messages.info(request, "Yangi asosiy o'qituvchilar topilmadi. Barcha faollari ro'yxatda bor.")
            
        return redirect('admin:finance_mainsalary_changelist')

    class Media:
        js = (
            'admin/js/jquery.init.js',
            'admin/js/money_input.js',
        )