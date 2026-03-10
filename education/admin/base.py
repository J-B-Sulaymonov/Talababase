from education.models import TimeTable, ScheduleError, LessonLog
from education.services.generator import ScheduleGeneratorService
from collections import defaultdict
from django.shortcuts import render, redirect
from django.contrib import messages
import datetime
import xlsxwriter
from django.contrib import admin
from django.http import JsonResponse, HttpResponse
from django.utils.html import format_html
from django.urls import path, reverse
from django.shortcuts import render, get_object_or_404
from django.db.models import Sum, Q
from django.utils.translation import gettext_lazy as _
from django import forms
import io
from students.models import Group, AcademicYear
from education.models import EducationPlan, PlanSubject, Workload, Stream, SubGroup, Room, SessionPeriod
from education.services.main import generate_semester_logs

class SemesterDateForm(forms.Form):
    academic_year = forms.ModelChoiceField(
        queryset=AcademicYear.objects.all().order_by('-name'),
        label="O'quv yili",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    semester = forms.ChoiceField(
        choices=[
            ('autumn', 'Kuzgi (1, 3, 5...)'),
            ('spring', 'Bahorgi (2, 4, 6...)'),
        ],
        label="Mavsum (Semestr)",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    start_date = forms.DateField(
        label="Boshlanish sanasi",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'vDateField'})
    )
    end_date = forms.DateField(
        label="Tugash sanasi",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'vDateField'})
    )

class PlanSubjectInline(admin.TabularInline):
    model = PlanSubject
    extra = 0
    min_num = 0
    fields = (
        'subject', 'alternative_subjects', 'total_hours', 'lecture_hours', 'practice_hours',
        'lab_hours', 'seminar_hours', 'independent_hours', 'semester', 'semester_time',
        'subject_type', 'credit',
    )
    autocomplete_fields = ['subject', 'alternative_subjects']

    class Media:
        css = {
            'all': ('admin/css/custom_inline.css',)
        }
        js = ('admin/js/calculate_hours.js',)

    # --- YANGI QO'SHILADIGAN QISM ---
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        # Faqat 'total_hours' maydoni uchun
        if db_field.name == 'total_hours':
            # Inputga 'readonly' atributi va vizual ko'rinish (kulrang fon) beramiz
            kwargs['widget'] = forms.TextInput(attrs={
                'readonly': 'readonly',
                'style': 'background-color: #e9ecef; color: #495057; cursor: not-allowed; text-align: center;'
            })
        return super().formfield_for_dbfield(db_field, request, **kwargs)

class ActiveYearFilter(admin.SimpleListFilter):
    title = _("O'quv yili")
    parameter_name = 'academic_year'

    def lookups(self, request, model_admin):
        # Barcha o'quv yillarini chiqaramiz
        years = AcademicYear.objects.all().order_by('-name')
        return [(y.id, str(y)) for y in years]

    def queryset(self, request, queryset):
        # Agar filtr tanlanmagan bo'lsa, eng oxirgi yilni default qilamiz
        if self.value() is None:
            last_year = queryset.order_by('-academic_year__name').first()
            if last_year:
                # Eslatma: Bu yerda qat'iy filtrlash o'rniga, shunchaki qaytaramiz
                # yoki "active" status bo'lsa o'shani olish kerak.
                # Hozircha hammasini ko'rsataveramiz yoki quyidagini yoqish mumkin:
                # return queryset.filter(academic_year=last_year.academic_year)
                pass
            return queryset

        return queryset.filter(academic_year__id=self.value())

class WorkloadReportFilterForm(forms.Form):
    academic_year = forms.ModelChoiceField(
        # O'zgartirish: Yillarni nomi bo'yicha kamayish tartibida saralash (2026, 2025...)
        queryset=AcademicYear.objects.all().order_by('-name'),
        required=False,
        label="O'quv yili",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    education_form = forms.ChoiceField(
        choices=[
            ('kunduzgi', 'Kunduzgi'),
            ('sirtqi', 'Sirtqi'),
            ('kechki', 'Kechki'),
            ('masofaviy', 'Masofaviy'),
        ],
        required=False,
        label="Ta'lim shakli",
        initial='kunduzgi'
    )
    course = forms.ChoiceField(
        choices=[('', 'Barchasi')] + list(EducationPlan.COURSE_CHOICES),
        required=False,
        label="Kurs"
    )

class StreamInline(admin.TabularInline):
    model = Stream
    extra = 0
    show_change_link = True
    fields = ('name', 'lesson_type', 'teacher', 'employment_type', 'groups', 'sub_groups')
    autocomplete_fields = ['teacher']

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name in ["groups", "sub_groups"]:
            kwargs['widget'] = forms.SelectMultiple(attrs={
                'style': 'width: 250px; height: 120px;',
                'class': 'browser-default'
            })

        # Obyekt mavjud bo'lsa, faqat unga tegishli guruhlarni ko'rsatish
        if request.resolver_match.kwargs.get('object_id'):
            workload_id = request.resolver_match.kwargs.get('object_id')
            try:
                workload = Workload.objects.get(pk=workload_id)
                if db_field.name == "groups":
                    kwargs["queryset"] = workload.groups.all().order_by('name')
                if db_field.name == "sub_groups":
                    kwargs["queryset"] = SubGroup.objects.filter(
                        group__in=workload.groups.all()
                    ).select_related('group').order_by('group__name', 'name')
            except Workload.DoesNotExist:
                pass
        else:
            if db_field.name in ["groups", "sub_groups"]:
                kwargs["queryset"] = Group.objects.none()

        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def get_formset(self, request, obj=None, **kwargs):
        """
        Dars turlarini (choices) rejadagi soatlarga qarab filtrlash.
        Faqat soati 0 dan katta bo'lgan dars turlari chiqadi.
        """
        formset = super().get_formset(request, obj, **kwargs)

        # Agar biz mavjud Workload ichida bo'lsak (obj mavjud bo'lsa)
        if obj:
            # 1. Shu Workloadga tegishli barcha rejalarni olamiz
            plans = obj.plan_subjects.all()

            # 2. Barcha soatlarni yig'indisini hisoblaymiz
            stats = plans.aggregate(
                lec=Sum('lecture_hours'),
                prac=Sum('practice_hours'),
                sem=Sum('seminar_hours'),
                lab=Sum('lab_hours')
            )

            # 3. Yangi choices ro'yxatini shakllantiramiz
            valid_choices = []

            # None qiymat kelishi mumkinligini hisobga olib (or 0) ishlatamiz
            if (stats['lec'] or 0) > 0:
                valid_choices.append(('lecture', "Ma'ruza"))
            if (stats['prac'] or 0) > 0:
                valid_choices.append(('practice', "Amaliyot"))
            if (stats['sem'] or 0) > 0:
                valid_choices.append(('seminar', "Seminar"))
            if (stats['lab'] or 0) > 0:
                valid_choices.append(('lab', "Laboratoriya"))

            # Agar reja hali tanlanmagan yoki hammasi 0 bo'lsa, xatolik bermaslik uchun
            # default holatda hammasini yoki bo'sh ro'yxatni qaytarish mumkin.
            # Hozircha agar valid_choices bo'sh bo'lsa, hech narsa o'zgartirmaymiz.
            if valid_choices:

                # 4. Formani dinamik tarzda o'zgartiramiz
                # Formsetning asosiy formasidan meros olamiz
                _BaseForm = formset.form

                class FilteredStreamForm(_BaseForm):
                    def __init__(self, *args, **kwargs):
                        super().__init__(*args, **kwargs)
                        # 'lesson_type' maydoni choiceslarini yangilaymiz
                        if 'lesson_type' in self.fields:
                            self.fields['lesson_type'].choices = valid_choices

                # Yangi formani formsetga biriktiramiz
                formset.form = FilteredStreamForm

        return formset

def education_general_view(request):
    models_links = [
        {"title": "Rejadagi fanlar", "subtitle": "PlanSubject", "url": reverse('admin:education_plansubject_changelist'), "icon": "fas fa-book-open"},
        {"title": "Kichik guruhlar", "subtitle": "SubGroup", "url": reverse('admin:education_subgroup_changelist'), "icon": "fas fa-users-cog"},
        {"title": "Auditoriyalar", "subtitle": "Room", "url": reverse('admin:education_room_changelist'), "icon": "fas fa-door-open"},
        {"title": "Kunlik Dars Qaydi", "subtitle": "LessonLog", "url": reverse('admin:education_lessonlog_changelist'), "icon": "fas fa-clipboard-check"},
        {"title": "Jadval xatolari", "subtitle": "ScheduleError", "url": reverse('admin:education_scheduleerror_changelist'), "icon": "fas fa-exclamation-circle"},
        {"title": "Sessiya davrlari", "subtitle": "SessionPeriod", "url": reverse('admin:education_sessionperiod_changelist'), "icon": "fas fa-calendar-alt"},
    ]

    context = admin.site.each_context(request)
    context.update({
        'title': "O'quv bo'limi sozlamalari",
        'models_links': models_links,
    })

    return render(request, 'admin/students/general.html', context)

original_get_urls = admin.site.get_urls

def get_urls():
    custom_urls = [
        path('education/general/', admin.site.admin_view(education_general_view), name='education_general'),
    ]
    return custom_urls + original_get_urls()

admin.site.get_urls = get_urls