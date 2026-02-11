from .models import TimeTable, ScheduleError, LessonLog
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
from .models import EducationPlan, PlanSubject, Workload, Stream, SubGroup, Room
from .services.main import generate_semester_logs


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


# -----------------------------------------------------------------------------
# 2. YANGI ADMIN: LESSON LOG (JURNAL)
# -----------------------------------------------------------------------------
@admin.register(LessonLog)
class LessonLogAdmin(admin.ModelAdmin):
    list_display = ('date', 'group', 'subject', 'planned_teacher', 'actual_teacher', 'status', 'is_confirmed')
    list_filter = ('date', 'status', 'is_confirmed', 'group')
    # O'quv bo'limi ro'yxatni o'zidan turib o'zgartira olishi uchun
    list_editable = ('actual_teacher', 'status', 'is_confirmed')
    search_fields = ('group__name', 'subject__name', 'actual_teacher__first_name')
    date_hierarchy = 'date'

    # O'quv bo'limi yangi qo'sholmasin, faqat generatsiya qilinganini tahrirlasin
    def has_add_permission(self, request):
        return request.user.is_superuser

@admin.register(SubGroup)
class SubGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'group',)
    search_fields = ('group__name', 'name')
    list_filter = ('name',)
    ordering = ('group__name', 'name')


class PlanSubjectInline(admin.TabularInline):
    model = PlanSubject
    extra = 0
    min_num = 0
    fields = (
        'subject', 'total_hours', 'lecture_hours', 'practice_hours',
        'lab_hours', 'seminar_hours', 'independent_hours', 'semester', 'semester_time',
        'subject_type', 'credit',
    )
    autocomplete_fields = ['subject']

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


# ----------------------------------------------------------
# YANGI FILTER: AKTIV O'QUV YILI BO'YICHA
# ----------------------------------------------------------
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


@admin.register(EducationPlan)
class EducationPlanAdmin(admin.ModelAdmin):
    list_display = (
        'name_display',
        'specialty',
        'academic_year',
        'course',
        'get_total_credits',
        'print_button'  # <--- Yangi tugma
    )

    # Filtrlarni qo'shamiz
    list_filter = (ActiveYearFilter, 'specialty', 'course')
    search_fields = ('specialty__name', 'academic_year__name')
    inlines = [PlanSubjectInline]
    save_on_top = True
    list_per_page = 20

    # -------------------------------------------------------
    # TUSHIB QOLGAN FUNKSIYALAR (QAYTA TIKLANDI)
    # -------------------------------------------------------
    def name_display(self, obj):
        return str(obj)

    name_display.short_description = "Reja nomi"

    def get_total_credits(self, obj):
        """Rejadagi barcha fanlar kreditlari yig'indisi"""
        total = obj.subjects.aggregate(Sum('credit'))['credit__sum']
        return total or 0

    get_total_credits.short_description = "Jami Kredit"

    # -------------------------------------------------------
    # YANGI PRINT TUGMASI
    # -------------------------------------------------------
    def print_button(self, obj):
        url = reverse('admin:education_plan_print', args=[obj.pk])
        return format_html(
            '<a href="{}" target="_blank" style="'
            'background-color: #009688; '       # Zamonaviy yashil-ko\'k (Teal) rang
            'color: white; '                    # Oq yozuv
            'padding: 8px 16px; '               # Ichki masofa (kattaroq)
            'border-radius: 50px; '             # To\'liq aylana burchaklar
            'text-decoration: none; '           # Tag chiziqni olib tashlash
            'font-family: Segoe UI, sans-serif; '
            'font-weight: 600; '                # Qalin shrift
            'font-size: 13px; '
            'box-shadow: 0 4px 6px rgba(0,0,0,0.15); ' # Chiroyli soya
            'display: inline-flex; align-items: center; transition: all 0.3s ease;">'
            '<i class="fas fa-print" style="margin-right: 8px; font-size: 14px;"></i> Reja</a>',
            url
        )

    print_button.short_description = "Ko'rish"
    print_button.allow_tags = True

    # -------------------------------------------------------
    # CUSTOM URL VA VIEW (Excel shakl chiqarish uchun)
    # -------------------------------------------------------
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:pk>/print/', self.admin_site.admin_view(self.education_plan_print_view),
                 name='education_plan_print'),
            # EXCEL UCHUN URL
            path('<int:pk>/export/', self.admin_site.admin_view(self.export_education_plan_excel),
                 name='education_plan_export'),
        ]
        return custom_urls + urls

    def export_education_plan_excel(self, request, pk):
        plan = get_object_or_404(EducationPlan, pk=pk)
        subjects = PlanSubject.objects.filter(education_plan=plan).select_related('subject').order_by('semester',
                                                                                                      'subject__name')

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet("O'quv Reja")

        # --- FORMATLAR ---
        fmt_base = workbook.add_format({
            'border': 1, 'align': 'center', 'valign': 'vcenter',
            'font_name': 'Times New Roman', 'font_size': 10, 'text_wrap': True
        })
        # Qalin Gorizontal
        fmt_bold_horizontal = workbook.add_format({
            'border': 1, 'align': 'center', 'valign': 'vcenter', 'bold': True,
            'font_name': 'Times New Roman', 'font_size': 10, 'text_wrap': True
        })
        fmt_bold = workbook.add_format({
            'border': 1, 'align': 'center', 'valign': 'vcenter', 'bold': True,
            'font_name': 'Times New Roman', 'font_size': 10, 'text_wrap': True
        })
        # Tik yozuv
        fmt_vertical = workbook.add_format({
            'border': 1, 'align': 'center', 'valign': 'vcenter', 'bold': True,
            'rotation': 90, 'text_wrap': True,
            'font_name': 'Times New Roman', 'font_size': 9
        })
        fmt_left = workbook.add_format({
            'border': 1, 'align': 'left', 'valign': 'vcenter',
            'font_name': 'Times New Roman', 'font_size': 10, 'text_wrap': True,
            'indent': 1
        })
        # Izohlar uchun
        fmt_base_no_wrap = workbook.add_format({
            'border': 1, 'align': 'center', 'valign': 'vcenter',
            'font_name': 'Times New Roman', 'font_size': 8, 'text_wrap': False
        })
        fmt_gray = workbook.add_format({
            'border': 1, 'align': 'center', 'valign': 'vcenter',
            'bg_color': '#f2f2f2', 'bold': True, 'font_size': 9
        })

        # --- TEPADAGI SARLAVHA FORMATLARI (Jadval tashqarisida) ---
        fmt_title = workbook.add_format({
            'align': 'center', 'valign': 'vcenter', 'bold': True,
            'font_name': 'Times New Roman', 'font_size': 14
        })
        fmt_info = workbook.add_format({
            'align': 'center', 'valign': 'vcenter', 'bold': False,
            'font_name': 'Times New Roman', 'font_size': 11
        })

        # ==========================================
        # 1. TEPADAGI MA'LUMOTLARNI YOZISH
        # ==========================================

        # 0-qator: O'QUV REJASI
        worksheet.merge_range(0, 0, 0, 27, "O'QUV REJA", fmt_title)

        # 1-qator: Yo'nalish | Yil | Kurs
        info_text = f"Yo'nalish: {plan.specialty.name} | O'quv yili: {plan.academic_year} | Kurs: {plan.course}"
        worksheet.merge_range(1, 0, 1, 27, info_text, fmt_info)

        # ==========================================
        # 2. JADVALNI BOSHLASH (OFFSET)
        # ==========================================
        # Jadval 3-qatordan (index 3) boshlanadi.
        # Shuning uchun hamma joyda "row + START_ROW" qilamiz.
        START_ROW = 3

        # --- O'LCHAMLAR ---
        # Tepadagi sarlavha qatorlari balandligi
        worksheet.set_row(0, 25)
        worksheet.set_row(1, 25)
        worksheet.set_row(2, 10)  # Ajratuvchi bo'sh joy

        # SIZ BERGAN O'LCHAMLAR (START_ROW ga qo'shib yozamiz)
        worksheet.set_row(START_ROW + 0, 30)  # Sarlavha
        worksheet.set_row(START_ROW + 1, 30)  # Auditoriya

        # 3 va 4 (Excelda 3 va 4-qatorlar) -> Bizda index 2 va 3
        worksheet.set_row(START_ROW + 2, 10)  # Kichkina
        worksheet.set_row(START_ROW + 3, 10)  # Kichkina

        worksheet.set_row(START_ROW + 4, 20)  # Raqamlar
        worksheet.set_row(START_ROW + 5, 25)  # Izoh
        worksheet.set_row(START_ROW + 6, 18)  # Indekslar

        # Ustun kengliklari
        worksheet.set_column('A:A', 4)  # T/r
        worksheet.set_column('B:B', 40)  # Fan nomi
        worksheet.set_column('C:C', 6)  # 3-ustun (Umumiy)
        worksheet.set_column('D:D', 4)  # 4-ustun (0)
        worksheet.set_column('E:E', 5)  # Jami
        worksheet.set_column('F:I', 4)  # Ma'ruza...
        worksheet.set_column('J:J', 4)  # Kurs ishi
        worksheet.set_column('K:K', 4)  # Mustaqil ta'lim
        worksheet.set_column('L:AA', 4)  # Semestrlar
        worksheet.set_column('AB:AB', 6)  # Jami kredit

        # --- HEADER CHIZISH ---

        # 0-QATOR (START_ROW + 0)
        worksheet.merge_range(START_ROW, 0, START_ROW + 5, 0, "T/r", fmt_bold)
        worksheet.merge_range(START_ROW, 1, START_ROW + 5, 1, "O'quv fanlari, bloklar va faoliyat turlarining nomlari",
                              fmt_bold)
        worksheet.merge_range(START_ROW, 2, START_ROW, 10, "Talabaning o'quv yuklamasi, soatlarda", fmt_bold)
        worksheet.merge_range(START_ROW, 11, START_ROW, 18, "Soatlarning kurs, semestr va haftalar bo'yicha taqsimoti",
                              fmt_bold)
        worksheet.merge_range(START_ROW, 19, START_ROW, 26,
                              "Kreditlarning kurs, semestr va haftalar bo'yicha taqsimoti", fmt_bold)
        worksheet.merge_range(START_ROW, 27, START_ROW + 5, 27, "Jami kreditlar", fmt_vertical)

        # 1-QATOR (START_ROW + 1)
        # Umumiy yuklama C va D ustunlari BIRLASHADI (Sarlavhada)
        worksheet.merge_range(START_ROW + 1, 2, START_ROW + 5, 3, "Umumiy yuklama hajmi", fmt_bold_horizontal)

        worksheet.merge_range(START_ROW + 1, 4, START_ROW + 1, 9, "Auditoriya mashg'ulotlari, soatlarda", fmt_bold)
        worksheet.merge_range(START_ROW + 1, 10, START_ROW + 5, 10, "Mustaqil ta'lim", fmt_vertical)

        # Kurslar
        worksheet.merge_range(START_ROW + 1, 11, START_ROW + 1, 12, "1-kurs", fmt_base)
        worksheet.merge_range(START_ROW + 1, 13, START_ROW + 1, 14, "2-kurs", fmt_base)
        worksheet.merge_range(START_ROW + 1, 15, START_ROW + 1, 16, "3-kurs", fmt_base)
        worksheet.merge_range(START_ROW + 1, 17, START_ROW + 1, 18, "4-kurs", fmt_base)
        worksheet.merge_range(START_ROW + 1, 19, START_ROW + 1, 20, "1-kurs", fmt_base)
        worksheet.merge_range(START_ROW + 1, 21, START_ROW + 1, 22, "2-kurs", fmt_base)
        worksheet.merge_range(START_ROW + 1, 23, START_ROW + 1, 24, "3-kurs", fmt_base)
        worksheet.merge_range(START_ROW + 1, 25, START_ROW + 1, 26, "4-kurs", fmt_base)

        # 2-QATOR (START_ROW + 2) - Vertikal turlar
        headers_aud = ["Jami", "Ma'ruza", "Amaliy", "Labaratoriya", "Seminar", "Kurs ishi"]
        for i, h in enumerate(headers_aud):
            worksheet.merge_range(START_ROW + 2, 4 + i, START_ROW + 5, 4 + i, h, fmt_vertical)

        worksheet.merge_range(START_ROW + 2, 11, START_ROW + 3, 18, "Semestrlar", fmt_base)
        worksheet.merge_range(START_ROW + 2, 19, START_ROW + 3, 26, "Semestrlar", fmt_base)

        # 4-QATOR (START_ROW + 4) - Raqamlar
        for i in range(1, 9):
            worksheet.write(START_ROW + 4, 10 + i, i, fmt_base)
            worksheet.write(START_ROW + 4, 18 + i, i, fmt_base)

        # 5-QATOR (START_ROW + 5) - Izohlar
        worksheet.merge_range(START_ROW + 5, 11, START_ROW + 5, 18,
                              "Semestrdagi auditoriya mashg'ulotlari haftalarining soni", fmt_base_no_wrap)
        worksheet.merge_range(START_ROW + 5, 19, START_ROW + 5, 26, "Kredit taqsimoti", fmt_base)

        # 6-QATOR (START_ROW + 6) - Indekslar
        worksheet.write(START_ROW + 6, 0, 1, fmt_gray)
        worksheet.write(START_ROW + 6, 1, 2, fmt_gray)

        # 3 va 4 ALOHIDA
        worksheet.write(START_ROW + 6, 2, 3, fmt_gray)  # C ustun
        worksheet.write(START_ROW + 6, 3, 4, fmt_gray)  # D ustun

        # Qolganlar (5 dan boshlab)
        start_idx = 5
        for i in range(4, 28):  # E(4) dan AB(27) gacha
            worksheet.write(START_ROW + 6, i, start_idx, fmt_gray)
            start_idx += 1

        # --- DATA QISMI ---
        row_idx = START_ROW + 7  # Data START_ROW + 7 dan boshlanadi

        t_credit = 0;
        t_total = 0;
        t_aud = 0
        t_lec = 0;
        t_prac = 0;
        t_lab = 0;
        t_sem = 0;
        t_ind = 0
        processed_data = []

        for item in subjects:
            aud = item.lecture_hours + item.practice_hours + item.seminar_hours + item.lab_hours
            total = item.total_hours if item.total_hours else (item.credit * 30)
            ind = total - aud

            t_credit += item.credit;
            t_total += total;
            t_aud += aud
            t_lec += item.lecture_hours;
            t_prac += item.practice_hours
            t_lab += item.lab_hours;
            t_sem += item.seminar_hours;
            t_ind += ind

            processed_data.append({'obj': item, 'aud': aud, 'ind': ind, 'total': total})

        # JAMI QATORI
        worksheet.write(row_idx, 0, "1.00", fmt_bold)
        worksheet.write(row_idx, 1, "JAMI FANLAR:", fmt_bold)

        # 3 va 4-ustunlar ALOHIDA
        worksheet.write(row_idx, 2, t_total, fmt_bold)  # C ustun (Total)
        worksheet.write(row_idx, 3, 0, fmt_bold)  # D ustun (0)

        worksheet.write(row_idx, 4, t_aud, fmt_bold)
        worksheet.write(row_idx, 5, t_lec, fmt_bold)
        worksheet.write(row_idx, 6, t_prac, fmt_bold)
        worksheet.write(row_idx, 7, t_lab, fmt_bold)
        worksheet.write(row_idx, 8, t_sem, fmt_bold)
        worksheet.write(row_idx, 9, 0, fmt_bold)
        worksheet.write(row_idx, 10, t_ind, fmt_bold)
        for c in range(11, 27):
            worksheet.write(row_idx, c, "", fmt_base)
        worksheet.write(row_idx, 27, t_credit, fmt_bold)
        row_idx += 1

        # LIST
        counter = 1
        for p in processed_data:
            item = p['obj']
            worksheet.write(row_idx, 0, counter, fmt_base)
            worksheet.write(row_idx, 1, item.subject.name, fmt_left)

            # 3 va 4-ustunlar ALOHIDA
            worksheet.write(row_idx, 2, p['total'], fmt_bold)  # C ustun
            worksheet.write(row_idx, 3, 0, fmt_bold)  # D ustun

            worksheet.write(row_idx, 4, p['aud'], fmt_bold)
            worksheet.write(row_idx, 5, item.lecture_hours if item.lecture_hours else "", fmt_base)
            worksheet.write(row_idx, 6, item.practice_hours if item.practice_hours else "", fmt_base)
            worksheet.write(row_idx, 7, item.lab_hours if item.lab_hours else "", fmt_base)
            worksheet.write(row_idx, 8, item.seminar_hours if item.seminar_hours else "", fmt_base)
            worksheet.write(row_idx, 9, "", fmt_base)
            worksheet.write(row_idx, 10, p['ind'], fmt_bold)

            for i in range(1, 9):
                col_h = 11 + (i - 1);
                col_c = 19 + (i - 1)
                if item.semester == i:
                    worksheet.write(row_idx, col_h, item.semester_time, fmt_base)
                    worksheet.write(row_idx, col_c, item.credit, fmt_bold)
                else:
                    worksheet.write(row_idx, col_h, "", fmt_base)
                    worksheet.write(row_idx, col_c, "", fmt_base)
            worksheet.write(row_idx, 27, item.credit, fmt_bold)
            row_idx += 1
            counter += 1

        workbook.close()
        output.seek(0)
        filename = f"Reja_{plan.specialty.name}_{plan.course}-kurs.xlsx"
        response = HttpResponse(output,
                                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    def education_plan_print_view(self, request, pk):
        plan = get_object_or_404(EducationPlan, pk=pk)
        subjects = PlanSubject.objects.filter(education_plan=plan).select_related('subject').order_by('semester',
                                                                                                      'subject__name')

        # --- QOLIB KETGAN QISM: Semestrlar sonini aniqlash ---
        # Agar Sirtqi yoki Masofaviy bo'lsa 10 semestr, bo'lmasa 8 semestr
        if plan.education_form in ['sirtqi', 'masofaviy']:
            max_sem = 10
            edu_type_display = plan.get_education_form_display()
        else:
            max_sem = 8
            edu_type_display = plan.get_education_form_display()

        semester_range = range(1, max_sem + 1)
        # -----------------------------------------------------

        processed_subjects = []
        totals = {
            'credit': 0, 'total': 0, 'auditorium': 0,
            'lecture': 0, 'practice': 0, 'seminar': 0, 'lab': 0,
            'independent': 0
        }

        for item in subjects:
            aud_hours = item.lecture_hours + item.practice_hours + item.seminar_hours + item.lab_hours
            total = item.total_hours if item.total_hours else (item.credit * 30)
            ind_hours = total - aud_hours

            processed_subjects.append({
                'obj': item,
                'auditorium_hours': aud_hours,
                'independent_hours': ind_hours,
                'total_calc': total
            })

            totals['credit'] += item.credit
            totals['total'] += total
            totals['auditorium'] += aud_hours
            totals['lecture'] += item.lecture_hours
            totals['practice'] += item.practice_hours
            totals['seminar'] += item.seminar_hours
            totals['lab'] += item.lab_hours
            totals['independent'] += ind_hours
        context = self.admin_site.each_context(request)
        context.update({
            'title': f"O'quv reja: {plan}",
            'site_header': self.admin_site.site_header,
            'has_permission': True,
            'user': request.user,
            'plan': plan,
            'subjects': processed_subjects,
            'totals': totals,
            'semester_range': semester_range,
            'max_sem': max_sem,
            'edu_type': edu_type_display,
        })
        return render(request, 'admin/education/education_plan/print.html', context)




@admin.register(PlanSubject)
class PlanSubjectAdmin(admin.ModelAdmin):
    list_display = ('subject', 'education_plan', 'semester', 'credit')
    search_fields = ('subject__name', 'education_plan__specialty__name')
    list_filter = ('education_plan__course', 'education_plan__academic_year')

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        return queryset, use_distinct


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


# --- INLINE VA ADMIN ---

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


class WorkloadAdminForm(forms.ModelForm):
    class Meta:
        model = Workload
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Form logikasi o'zgarishsiz qoldi
        if self.data:
            self.fields['plan_subjects'].queryset = PlanSubject.objects.all()
            self.fields['groups'].queryset = Group.objects.all()
        elif self.instance.pk:
            if self.instance.subject:
                self.fields['plan_subjects'].queryset = PlanSubject.objects.filter(
                    subject=self.instance.subject
                ).select_related('education_plan', 'education_plan__specialty')
            saved_plans = self.instance.plan_subjects.all()
            if saved_plans.exists():
                spec_ids = saved_plans.values_list('education_plan__specialty', flat=True).distinct()
                self.fields['groups'].queryset = Group.objects.filter(specialty__in=spec_ids).order_by('name')
            else:
                self.fields['groups'].queryset = Group.objects.none()
        else:
            self.fields['plan_subjects'].queryset = PlanSubject.objects.none()
            self.fields['groups'].queryset = Group.objects.none()


@admin.register(Workload)
class WorkloadAdmin(admin.ModelAdmin):
    form = WorkloadAdminForm
    list_display = ('subject', 'get_specialty_names', 'get_group_names', 'calculate_total_hours')
    search_fields = ('subject__name',)
    autocomplete_fields = ['subject']
    inlines = [StreamInline]
    change_list_template = "admin/workload_change_list.html"

    class Media:
        js = ('admin/js/workload.js',)
        css = {
            'all': ('admin/css/workload_custom.css',)
        }

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related('groups', 'groups__specialty', 'plan_subjects')

    def get_specialty_names(self, obj):
        specialties = set()
        for group in obj.groups.all():
            if hasattr(group, 'specialty') and group.specialty:
                specialties.add(group.specialty.name)
        return ", ".join(specialties)

    get_specialty_names.short_description = "Yo'nalishlar"

    def get_group_names(self, obj):
        groups = [group.name for group in obj.groups.all()]
        return ", ".join(groups)

    get_group_names.short_description = "Guruhlar"

    # --- URLS (O'zgartirildi: Excel export qo'shildi) ---
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        my_urls = [
            path('general-report/', self.admin_site.admin_view(self.general_report_view),
                 name='workload_general_report'),
            # YANGI: Excel export URL
            path('general-report/export/', self.admin_site.admin_view(self.export_workload_excel),
                 name='workload_export_excel'),
            path('ajax/get-plans/', self.admin_site.admin_view(self.get_plans_view), name='ajax_get_plans'),
            path('ajax/get-groups/', self.admin_site.admin_view(self.get_groups_view), name='ajax_get_groups'),
        ]
        return my_urls + urls

    def general_report_view(self, request):
        # Bu funksiya o'zgarishsiz qoldi (Sizning kodingizdagi kabi)
        active_year_obj = AcademicYear.objects.filter(is_active=True).first()
        if not active_year_obj:
            active_year_obj = AcademicYear.objects.order_by('-name').first()

        selected_year_id = request.GET.get('academic_year')
        if selected_year_id is None and active_year_obj:
            selected_year_id = active_year_obj.id

        selected_edu_form = request.GET.get('education_form', 'kunduzgi')
        selected_course = request.GET.get('course', '')

        filter_form = WorkloadReportFilterForm(initial={
            'academic_year': selected_year_id,
            'education_form': selected_edu_form,
            'course': selected_course
        })
        filter_form.fields['academic_year'].queryset = AcademicYear.objects.all().order_by('-name')

        workloads = Workload.objects.all().select_related('subject').prefetch_related(
            'groups', 'groups__specialty',
            'plan_subjects', 'plan_subjects__education_plan',
            'streams', 'streams__groups', 'streams__sub_groups', 'streams__teacher'
        )

        if selected_year_id:
            workloads = workloads.filter(plan_subjects__education_plan__academic_year_id=selected_year_id)
        if selected_edu_form:
            workloads = workloads.filter(plan_subjects__education_plan__education_form=selected_edu_form)
        if selected_course:
            workloads = workloads.filter(plan_subjects__education_plan__course=selected_course)

        workloads = workloads.distinct()
        report_data = []

        for load in workloads:
            representative_plans = {}
            for ps in load.plan_subjects.all():
                if ps.semester not in representative_plans:
                    representative_plans[ps.semester] = ps

            if not representative_plans:
                continue

            first_plan = list(representative_plans.values())[0]
            course_num = first_plan.education_plan.course

            streams_map = {}
            all_streams = load.streams.all()

            if not all_streams.exists():
                streams_map[(None, None)] = []
            else:
                for stream in all_streams:
                    t = stream.teacher
                    e_type = stream.employment_type if t else None
                    key = (t, e_type)
                    if key not in streams_map:
                        streams_map[key] = []
                    streams_map[key].append(stream)

            for (teacher, emp_type), streams in streams_map.items():
                if teacher:
                    type_display = dict(Stream.EMPLOYMENT_TYPE_CHOICES).get(emp_type, emp_type)
                    if emp_type == 'permanent':
                        short_type = "Shtat"
                    elif emp_type == 'hourly':
                        short_type = "Soatbay"
                    else:
                        short_type = type_display
                    teacher_name = f"{teacher} ({short_type})"
                else:
                    teacher_name = "Vakant"

                row_groups_set = set()
                if streams:
                    for s in streams:
                        for g in s.groups.all(): row_groups_set.add(g)
                        for sg in s.sub_groups.all(): row_groups_set.add(sg.group)
                else:
                    for g in load.groups.all(): row_groups_set.add(g)

                sorted_groups = sorted(list(row_groups_set), key=lambda x: x.name)
                group_names = ", ".join([g.name for g in sorted_groups])
                specialties = ", ".join(list(set([g.specialty.name for g in row_groups_set if g.specialty])))
                total_students = sum([getattr(g, 'student_count', 0) for g in row_groups_set])
                group_count_val = len(row_groups_set)

                lec_count = len([s for s in streams if s.lesson_type == 'lecture'])
                prac_count = len([s for s in streams if s.lesson_type == 'practice'])
                lab_count = len([s for s in streams if s.lesson_type == 'lab'])
                sem_count = len([s for s in streams if s.lesson_type == 'seminar'])

                is_vacant_row = (teacher is None) and (not streams)
                if is_vacant_row:
                    lec_count = 1
                    prac_count = 1
                    lab_count = 1
                    sem_count = 1

                kuzgi = {'lec_r': '', 'lec_j': '', 'prac_r': '', 'prac_j': '',
                         'lab_r': '', 'lab_j': '', 'sem_r': '', 'sem_j': '', 'total': 0}
                bahorgi = {'lec_r': '', 'lec_j': '', 'prac_r': '', 'prac_j': '',
                           'lab_r': '', 'lab_j': '', 'sem_r': '', 'sem_j': '', 'total': 0}

                for sem, ps in representative_plans.items():
                    is_autumn = (sem % 2 != 0)
                    target = kuzgi if is_autumn else bahorgi

                    def set_hours(plan_hour, stream_count, field_name):
                        if (plan_hour and plan_hour > 0) and (stream_count > 0 or is_vacant_row):
                            target[f'{field_name}_r'] = plan_hour
                            if is_vacant_row:
                                total_calc = plan_hour
                            else:
                                total_calc = plan_hour * stream_count
                            target[f'{field_name}_j'] = total_calc
                            return total_calc
                        return 0

                    t_lec = set_hours(ps.lecture_hours, lec_count, 'lec')
                    t_prac = set_hours(ps.practice_hours, prac_count, 'prac')
                    t_lab = set_hours(ps.lab_hours, lab_count, 'lab')
                    t_sem = set_hours(ps.seminar_hours, sem_count, 'sem')

                    target['total'] += (t_lec + t_prac + t_lab + t_sem)

                year_total = kuzgi['total'] + bahorgi['total']

                report_data.append({
                    'subject': load.subject.name,
                    'specialties': specialties,
                    'groups': group_names,
                    'course': course_num,
                    'students': total_students,
                    'group_count': group_count_val,
                    'kuzgi': kuzgi,
                    'bahorgi': bahorgi,
                    'year_total': year_total,
                    'teacher': teacher_name
                })

        report_data.sort(key=lambda x: (x['subject'], x['teacher']))

        context = self.admin_site.each_context(request)
        context.update({
            'report_data': report_data,
            'filter_form': filter_form,
            'title': "Professor-o'qituvchilarning o'quv yuklamasi hajmlari"
        })
        return render(request, 'admin/workload_report.html', context)

    # --- YANGI EXCEL EXPORT FUNKSIYASI ---
    def export_workload_excel(self, request):
        # 1. MA'LUMOTLARNI YIG'ISH (general_report_view logikasi bilan aynan bir xil)
        # --------------------------------------------------------------------------
        active_year_obj = AcademicYear.objects.filter(is_active=True).first()
        if not active_year_obj:
            active_year_obj = AcademicYear.objects.order_by('-name').first()

        selected_year_id = request.GET.get('academic_year')
        if selected_year_id is None and active_year_obj:
            selected_year_id = active_year_obj.id

        selected_edu_form = request.GET.get('education_form', 'kunduzgi')
        selected_course = request.GET.get('course', '')

        # QuerySet
        workloads = Workload.objects.all().select_related('subject').prefetch_related(
            'groups', 'groups__specialty',
            'plan_subjects', 'plan_subjects__education_plan',
            'streams', 'streams__groups', 'streams__sub_groups', 'streams__teacher'
        )

        if selected_year_id:
            workloads = workloads.filter(plan_subjects__education_plan__academic_year_id=selected_year_id)
        if selected_edu_form:
            workloads = workloads.filter(plan_subjects__education_plan__education_form=selected_edu_form)
        if selected_course:
            workloads = workloads.filter(plan_subjects__education_plan__course=selected_course)

        workloads = workloads.distinct()
        report_data = []

        # Ma'lumotlarni qayta ishlash
        for load in workloads:
            representative_plans = {}
            for ps in load.plan_subjects.all():
                if ps.semester not in representative_plans:
                    representative_plans[ps.semester] = ps

            if not representative_plans:
                continue

            first_plan = list(representative_plans.values())[0]
            course_num = first_plan.education_plan.course

            streams_map = {}
            all_streams = load.streams.all()

            if not all_streams.exists():
                streams_map[(None, None)] = []
            else:
                for stream in all_streams:
                    t = stream.teacher
                    e_type = stream.employment_type if t else None
                    key = (t, e_type)
                    if key not in streams_map:
                        streams_map[key] = []
                    streams_map[key].append(stream)

            for (teacher, emp_type), streams in streams_map.items():
                if teacher:
                    type_display = dict(Stream.EMPLOYMENT_TYPE_CHOICES).get(emp_type, emp_type)
                    short_type = "Shtat" if emp_type == 'permanent' else (
                        "Soatbay" if emp_type == 'hourly' else type_display)
                    teacher_name = f"{teacher} ({short_type})"
                else:
                    teacher_name = "Vakant"

                row_groups_set = set()
                if streams:
                    for s in streams:
                        for g in s.groups.all(): row_groups_set.add(g)
                        for sg in s.sub_groups.all(): row_groups_set.add(sg.group)
                else:
                    for g in load.groups.all(): row_groups_set.add(g)

                sorted_groups = sorted(list(row_groups_set), key=lambda x: x.name)
                group_names = ", ".join([g.name for g in sorted_groups])
                specialties = ", ".join(list(set([g.specialty.name for g in row_groups_set if g.specialty])))
                total_students = sum([getattr(g, 'student_count', 0) for g in row_groups_set])
                group_count_val = len(row_groups_set)

                lec_count = len([s for s in streams if s.lesson_type == 'lecture'])
                prac_count = len([s for s in streams if s.lesson_type == 'practice'])
                lab_count = len([s for s in streams if s.lesson_type == 'lab'])
                sem_count = len([s for s in streams if s.lesson_type == 'seminar'])

                is_vacant_row = (teacher is None) and (not streams)
                if is_vacant_row:
                    lec_count = 1;
                    prac_count = 1;
                    lab_count = 1;
                    sem_count = 1

                kuzgi = {'lec_r': '', 'lec_j': '', 'prac_r': '', 'prac_j': '',
                         'lab_r': '', 'lab_j': '', 'sem_r': '', 'sem_j': '', 'total': 0}
                bahorgi = {'lec_r': '', 'lec_j': '', 'prac_r': '', 'prac_j': '',
                           'lab_r': '', 'lab_j': '', 'sem_r': '', 'sem_j': '', 'total': 0}

                for sem, ps in representative_plans.items():
                    is_autumn = (sem % 2 != 0)
                    target = kuzgi if is_autumn else bahorgi

                    def set_hours(plan_hour, stream_count, field_name):
                        if (plan_hour and plan_hour > 0) and (stream_count > 0 or is_vacant_row):
                            target[f'{field_name}_r'] = plan_hour
                            total_calc = plan_hour if is_vacant_row else plan_hour * stream_count
                            target[f'{field_name}_j'] = total_calc
                            return total_calc
                        return 0

                    t_lec = set_hours(ps.lecture_hours, lec_count, 'lec')
                    t_prac = set_hours(ps.practice_hours, prac_count, 'prac')
                    t_lab = set_hours(ps.lab_hours, lab_count, 'lab')
                    t_sem = set_hours(ps.seminar_hours, sem_count, 'sem')
                    target['total'] += (t_lec + t_prac + t_lab + t_sem)

                year_total = kuzgi['total'] + bahorgi['total']
                report_data.append({
                    'subject': load.subject.name, 'specialties': specialties, 'groups': group_names,
                    'course': course_num, 'students': total_students, 'group_count': group_count_val,
                    'kuzgi': kuzgi, 'bahorgi': bahorgi, 'year_total': year_total, 'teacher': teacher_name
                })

        report_data.sort(key=lambda x: (x['subject'], x['teacher']))

        # 2. EXCEL GENERATSIYA
        # --------------------------------------------------------------------------
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet("Yuklama")

        # Formatlar
        fmt_header = workbook.add_format(
            {'border': 1, 'align': 'center', 'valign': 'vcenter', 'bold': True, 'text_wrap': True, 'font_size': 9})
        fmt_vertical = workbook.add_format(
            {'border': 1, 'align': 'center', 'valign': 'vcenter', 'bold': True, 'rotation': 90, 'text_wrap': True,
             'font_size': 9})
        fmt_center = workbook.add_format(
            {'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True, 'font_size': 9})
        fmt_left = workbook.add_format(
            {'border': 1, 'align': 'left', 'valign': 'vcenter', 'text_wrap': True, 'font_size': 9, 'bold': True})

        # Rangli formatlar (CSS dan olingan)
        fmt_kuzgi = workbook.add_format(
            {'border': 1, 'align': 'center', 'valign': 'vcenter', 'bold': True, 'bg_color': '#d99694', 'font_size': 9})
        fmt_bahorgi = workbook.add_format(
            {'border': 1, 'align': 'center', 'valign': 'vcenter', 'bold': True, 'bg_color': '#dce6f1', 'font_size': 9})
        fmt_yellow = workbook.add_format(
            {'border': 1, 'align': 'center', 'valign': 'vcenter', 'bold': True, 'bg_color': '#ffff00', 'font_size': 9})
        fmt_pink = workbook.add_format(
            {'border': 1, 'align': 'center', 'valign': 'vcenter', 'bold': True, 'bg_color': '#e6b8b7', 'font_size': 9})
        fmt_purple = workbook.add_format(
            {'border': 1, 'align': 'center', 'valign': 'vcenter', 'bold': True, 'bg_color': '#ccc1d9', 'font_size': 9,
             'text_wrap': True})
        fmt_blue_light = workbook.add_format(
            {'border': 1, 'align': 'center', 'valign': 'vcenter', 'bold': True, 'bg_color': '#b8cce4', 'font_size': 9})
        fmt_row_num = workbook.add_format(
            {'border': 1, 'align': 'center', 'valign': 'vcenter', 'bg_color': '#f2f2f2', 'font_color': '#555555',
             'font_size': 8})

        # Sarlavha ma'lumotlari
        title = "Professor-o'qituvchilarning o'quv yuklamasi hajmlari"
        worksheet.merge_range(0, 0, 0, 26, title,
                              workbook.add_format({'bold': True, 'font_size': 14, 'align': 'center'}))

        # Filter info
        info_text = f"O'quv yili: {AcademicYear.objects.filter(id=selected_year_id).first() if selected_year_id else 'Barchasi'} | " \
                    f"Ta'lim shakli: {selected_edu_form} | Kurs: {selected_course if selected_course else 'Barchasi'}"
        worksheet.merge_range(1, 0, 1, 26, info_text, workbook.add_format({'align': 'center', 'font_size': 10}))

        # JADVAL HEADER
        # 3-qator (Index 3) - Asosiy sarlavhalar
        worksheet.merge_range(3, 0, 5, 0, "№", fmt_header)
        worksheet.merge_range(3, 1, 5, 1, "Fanlar nomi", fmt_header)
        worksheet.merge_range(3, 2, 5, 2, "Ta'lim yo'nalishlari", fmt_header)
        worksheet.merge_range(3, 3, 5, 3, "Guruh raqami", fmt_header)
        worksheet.merge_range(3, 4, 5, 4, "Kurs", fmt_vertical)
        worksheet.merge_range(3, 5, 5, 5, "Talabalar\nsoni", fmt_vertical)
        worksheet.merge_range(3, 6, 5, 6, "Guruhlar\nsoni", fmt_vertical)

        worksheet.merge_range(3, 7, 3, 15, "KUZGI SEMESTR", fmt_kuzgi)
        worksheet.merge_range(3, 16, 3, 24, "BAHORGI SEMESTR", fmt_bahorgi)

        worksheet.merge_range(3, 25, 5, 25, "JAMI\nYILLIK\nYUKLAMA", fmt_purple)
        worksheet.merge_range(3, 26, 5, 26, "Professor - o'qituvchi F.I.Sh", fmt_header)

        # 4-qator (Kuzgi/Bahorgi ichki sarlavhalar)
        sub_headers = ["Ma'ruza", "Amaliy", "Laboratoriya", "Seminar"]

        # Kuzgi
        col_idx = 7
        for h in sub_headers:
            worksheet.merge_range(4, col_idx, 4, col_idx + 1, h, fmt_header)
            col_idx += 2
        worksheet.merge_range(4, 15, 5, 15, "Jami", fmt_pink)

        # Bahorgi
        col_idx = 16
        for h in sub_headers:
            worksheet.merge_range(4, col_idx, 4, col_idx + 1, h, fmt_header)
            col_idx += 2
        worksheet.merge_range(4, 24, 5, 24, "Jami", fmt_blue_light)

        # 5-qator (reja/jami)
        col_idx = 7
        for _ in range(4):  # Kuzgi
            worksheet.write(5, col_idx, "reja", fmt_header)
            worksheet.write(5, col_idx + 1, "jami", fmt_yellow)
            col_idx += 2

        col_idx = 16
        for _ in range(4):  # Bahorgi
            worksheet.write(5, col_idx, "reja", fmt_header)
            worksheet.write(5, col_idx + 1, "jami", fmt_yellow)
            col_idx += 2

        # 6-qator (Raqamlar)
        for i in range(27):
            worksheet.write(6, i, i + 1, fmt_row_num)

            # Columns width (Ustun kengliklari)
            worksheet.set_column(0, 0, 4)  # No
            worksheet.set_column(1, 1, 30)  # Fan
            worksheet.set_column(2, 2, 20)  # Yo'nalish
            worksheet.set_column(3, 3, 15)  # Guruh
            worksheet.set_column(4, 6, 5)  # Kurs, Talaba, Guruh soni
            worksheet.set_column(7, 24, 4)
            worksheet.set_column(11, 12, 5)
            worksheet.set_column(20, 21, 5)
            worksheet.set_column(15, 15, 6)  # Kuzgi Jami
            worksheet.set_column(24, 24, 6)  # Bahorgi Jami
            worksheet.set_column(25, 25, 8)  # Yillik
            worksheet.set_column(26, 26, 25)  # O'qituvchi

        # MA'LUMOTLARNI YOZISH
        row = 7
        for idx, item in enumerate(report_data, 1):
            worksheet.write(row, 0, idx, fmt_center)
            worksheet.write(row, 1, item['subject'], fmt_left)
            worksheet.write(row, 2, item['specialties'], workbook.add_format(
                {'border': 1, 'font_size': 8, 'text_wrap': True, 'align': 'center', 'valign': 'vcenter'}))
            worksheet.write(row, 3, item['groups'], workbook.add_format(
                {'border': 1, 'font_size': 8, 'text_wrap': True, 'align': 'center', 'valign': 'vcenter'}))
            worksheet.write(row, 4, item['course'], fmt_center)
            worksheet.write(row, 5, item['students'], fmt_center)
            worksheet.write(row, 6, item['group_count'], fmt_center)

            # Kuzgi
            k = item['kuzgi']
            worksheet.write(row, 7, k['lec_r'], fmt_center)
            worksheet.write(row, 8, k['lec_j'], fmt_yellow)
            worksheet.write(row, 9, k['prac_r'], fmt_center)
            worksheet.write(row, 10, k['prac_j'], fmt_yellow)
            worksheet.write(row, 11, k['lab_r'], fmt_center)
            worksheet.write(row, 12, k['lab_j'], fmt_yellow)
            worksheet.write(row, 13, k['sem_r'], fmt_center)
            worksheet.write(row, 14, k['sem_j'], fmt_yellow)
            worksheet.write(row, 15, k['total'], fmt_pink)

            # Bahorgi
            b = item['bahorgi']
            worksheet.write(row, 16, b['lec_r'], fmt_center)
            worksheet.write(row, 17, b['lec_j'], fmt_yellow)
            worksheet.write(row, 18, b['prac_r'], fmt_center)
            worksheet.write(row, 19, b['prac_j'], fmt_yellow)
            worksheet.write(row, 20, b['lab_r'], fmt_center)
            worksheet.write(row, 21, b['lab_j'], fmt_yellow)
            worksheet.write(row, 22, b['sem_r'], fmt_center)
            worksheet.write(row, 23, b['sem_j'], fmt_yellow)
            worksheet.write(row, 24, b['total'], fmt_blue_light)

            # Jami
            worksheet.write(row, 25, item['year_total'], fmt_purple)
            worksheet.write(row, 26, item['teacher'], fmt_left)

            row += 1

        workbook.close()
        output.seek(0)

        filename = f"Yuklama_{datetime.date.today()}.xlsx"
        response = HttpResponse(output,
                                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    # --- AJAX METHODS (O'zgarishsiz) ---
    def get_plans_view(self, request):
        subject_id = request.GET.get('subject_id')
        results = []
        if subject_id:
            plans = PlanSubject.objects.filter(subject_id=subject_id).select_related('education_plan',
                                                                                     'education_plan__specialty')
            for p in plans:
                results.append({
                    'id': str(p.id),
                    'text': f"{p.education_plan.specialty.name} | {p.semester}-sem | {p.education_plan.academic_year}"
                })
        return JsonResponse({'results': results})

    def get_groups_view(self, request):
        plan_ids_str = request.GET.get('plan_ids', '')
        results = []
        if plan_ids_str:
            plan_ids = [x for x in plan_ids_str.split(',') if x.isdigit()]
            if plan_ids:
                selected_plans = PlanSubject.objects.filter(id__in=plan_ids).select_related('education_plan')
                filter_q = Q()
                for ps in selected_plans:
                    spec_id = ps.education_plan.specialty_id
                    filter_q |= Q(specialty_id=spec_id)
                if filter_q:
                    groups = Group.objects.filter(filter_q).distinct().order_by('name')
                    for g in groups:
                        results.append({'id': str(g.id), 'text': g.name})
        return JsonResponse({'results': results})


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    # Ro'yxatda ko'rinadigan ustunlar
    list_display = ('name', 'room_type', 'capacity', 'is_active')

    # Ro'yxatning o'zidan tahrirlash imkoniyati (juda qulay)
    list_editable = ('capacity', 'is_active')

    # O'ng tomondagi filtrlar
    list_filter = ('room_type', 'is_active')

    # Qidiruv maydoni (Xona raqami bo'yicha)
    search_fields = ('name',)

    # Sahifalash (har bir betda 20 tadan)
    list_per_page = 20

    # Formani chiroyli guruhlash
    fieldsets = (
        ('Asosiy ma\'lumotlar', {
            'fields': ('name', 'room_type', 'capacity', 'is_active',)
        }),

    )

    # Qo'shimcha funksiyalar (Actions)
    actions = ['make_inactive', 'make_active']

    @admin.action(description="Tanlangan xonalarni yopish (Noaktiv qilish)")
    def make_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} ta xona muvaffaqiyatli yopildi (Noaktiv qilindi).")

    @admin.action(description="Tanlangan xonalarni ochish (Aktiv qilish)")
    def make_active(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} ta xona muvaffaqiyatli aktivlashtirildi.")


@admin.register(TimeTable)
class TimeTableAdmin(admin.ModelAdmin):
    list_display = ('weekday', 'timeslot', 'get_target', 'subject', 'teacher', 'room', 'semester')
    list_filter = ('academic_year', 'semester', 'weekday', 'teacher', 'room')
    change_list_template = "admin/education/timetable/change_list.html"  # Tugma uchun

    def get_target(self, obj):
        return obj.stream.name if obj.stream else (obj.group.name if obj.group else "-")
    get_target.short_description = "Guruh/Patok"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            # ESKI GENERATSIYA (O'zgartirilmadi)
            path('generate/', self.admin_site.admin_view(self.generate_view), name='education_timetable_generate'),
            # YANGI LOG GENERATSIYA
            path('generate-logs/', self.admin_site.admin_view(self.generate_logs_view), name='education_timetable_generate_logs'),
        ]
        return custom_urls + urls

    # --- YANGI METOD: LOGLARNI GENERATSIYA QILISH ---
    def generate_logs_view(self, request):
        if request.method == 'POST':
            form = SemesterDateForm(request.POST)
            if form.is_valid():
                # Formadan ma'lumotlarni olamiz
                year_obj = form.cleaned_data['academic_year']
                sem = form.cleaned_data['semester']
                start = form.cleaned_data['start_date']
                end = form.cleaned_data['end_date']

                try:
                    # Servisga yil va semestrni ham yuboramiz
                    count = generate_semester_logs(
                        start_date=start,
                        end_date=end,
                        academic_year_id=year_obj.id,
                        semester=sem
                    )

                    if count > 0:
                        self.message_user(request,
                                          f"Muvaffaqiyatli! {year_obj} - {sem} semestri uchun {count} ta dars jurnali yaratildi.",
                                          messages.SUCCESS)
                    else:
                        self.message_user(request,
                                          "Jurnal yaratilmadi. Tanlangan yil va semestr uchun jadval topilmadi yoki limit to'lgan.",
                                          messages.WARNING)
                except Exception as e:
                    self.message_user(request, f"Xatolik yuz berdi: {str(e)}", messages.ERROR)

                return redirect('admin:education_timetable_changelist')
        else:
            # Get so'rovida oxirgi yil va semestrni default qilib qo'yishimiz mumkin
            last_year = AcademicYear.objects.order_by('-name').first()
            form = SemesterDateForm(initial={'academic_year': last_year, 'semester': 'autumn'})

        context = {
            'title': "Semestr uchun jurnalni to'ldirish",
            'form': form,
            'opts': self.model._meta,
            'app_label': self.model._meta.app_label,
            'site_header': self.admin_site.site_header,
            'site_title': self.admin_site.site_title,
            'has_permission': True,
        }
        return render(request, "admin/education/timetable/generate_logs.html", context)


    # --- ESKI GENERATSIYA KODI (O'ZGARISHSIZ) ---
    def generate_view(self, request):
        if request.method == 'POST':
            action = request.POST.get('action')
            year_id = request.POST.get('academic_year')
            season = request.POST.get('season')

            s1_raw = request.POST.getlist('shift1_levels')
            s2_raw = request.POST.getlist('shift2_levels')
            shift1 = [int(x) for x in s1_raw] if s1_raw else []
            shift2 = [int(x) for x in s2_raw] if s2_raw else []

            service = ScheduleGeneratorService(year_id, season, shift1, shift2)

            if action == 'save':
                service.generate(dry_run=False)
                self.message_user(request, "Dars jadvali muvaffaqiyatli saqlandi!", messages.SUCCESS)
                return redirect('admin:education_timetable_changelist')

            schedule_map, errors = service.generate(dry_run=True)

            # --- GURUHLASH LOGIKASI ---
            grouped_data = {}
            all_group_ids = set()
            for item in schedule_map:
                all_group_ids.update(item['group_ids'])

            groups_map = {g.id: g for g in Group.objects.filter(id__in=all_group_ids).select_related('specialty')}

            for item in schedule_map:
                c_level = item.get('course_level', 1)
                for gr_id in item['group_ids']:
                    if gr_id not in grouped_data:
                        group = groups_map.get(gr_id)
                        if not group: continue
                        grouped_data[gr_id] = {
                            'group': group,
                            'course_level': c_level,
                            'grid': defaultdict(lambda: defaultdict(list))
                        }
                    grouped_data[gr_id]['grid'][item['timeslot_id']][item['weekday_id']].append(item)

            final_groups_list = []
            for g_id, data in grouped_data.items():
                data['grid'] = {k: dict(v) for k, v in data['grid'].items()}
                final_groups_list.append(data)

            final_groups_list.sort(key=lambda x: (x['course_level'], x['group'].name))

            raw_streams = service.fetch_streams()
            total_streams = len(raw_streams)
            unique_placed = len(set(item['stream'].id for item in schedule_map))
            success_percent = int((unique_placed / total_streams) * 100) if total_streams > 0 else 0

            context = {
                'title': "Jadval Generatsiyasi (Simulyatsiya)",
                'academic_years': AcademicYear.objects.all(),
                'selected_year': int(year_id) if year_id else None,
                'selected_season': season,
                'selected_shift1': shift1,
                'selected_shift2': shift2,
                'preview_mode': True,
                'grouped_schedules': final_groups_list,
                'errors': errors,
                'weekdays': service.weekdays,
                'timeslots': service.timeslots,
                'total_streams': total_streams,
                'success_percent': success_percent,
                'opts': self.model._meta,
                'has_view_permission': self.has_view_permission(request),
                'site_header': self.admin_site.site_header,
                'site_title': self.admin_site.site_title,
            }
            return render(request, "admin/education/timetable/generate.html", context)

        context = {
            'title': "Avtomatik Jadval Generatori",
            'academic_years': AcademicYear.objects.all(),
            'selected_season': 'autumn',
            'selected_shift1': [1, 4],
            'selected_shift2': [2, 3],
            'opts': self.model._meta,
            'has_view_permission': self.has_view_permission(request),
            'site_header': self.admin_site.site_header,
            'site_title': self.admin_site.site_title,
        }
        return render(request, "admin/education/timetable/generate.html", context)


@admin.register(ScheduleError)
class ScheduleErrorAdmin(admin.ModelAdmin):
    list_display = ('workload', 'reason', 'created_at')
    list_filter = ('academic_year', 'reason')