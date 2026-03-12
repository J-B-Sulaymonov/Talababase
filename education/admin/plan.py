from .base import *
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
        subjects = PlanSubject.objects.filter(education_plan=plan).select_related('subject').prefetch_related('alternative_subjects').order_by('semester',
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

        if plan.education_form in ['sirtqi', 'masofaviy']:
            max_sem = 10
        else:
            max_sem = 8

        # ==========================================
        # 2. JADVALNI BOSHLASH (OFFSET)
        # ==========================================
        START_ROW = 3

        worksheet.set_row(0, 25)
        worksheet.set_row(1, 25)
        worksheet.set_row(2, 10)
        worksheet.set_row(START_ROW + 0, 30)
        worksheet.set_row(START_ROW + 1, 30)
        worksheet.set_row(START_ROW + 2, 10)
        worksheet.set_row(START_ROW + 3, 10)
        worksheet.set_row(START_ROW + 4, 20)
        worksheet.set_row(START_ROW + 5, 25)
        worksheet.set_row(START_ROW + 6, 18)

        worksheet.set_column('A:A', 4)  # T/r
        worksheet.set_column('B:B', 40)  # Fan nomi
        worksheet.set_column('C:C', 6)
        worksheet.set_column('D:D', 4)
        worksheet.set_column('E:E', 5)
        worksheet.set_column('F:I', 4)
        worksheet.set_column('J:J', 4)
        worksheet.set_column('K:K', 4)
        worksheet.set_column(11, 11 + max_sem - 1, 4)  # Semestrlar time
        worksheet.set_column(11 + max_sem, 11 + (max_sem * 2) - 1, 4)  # Semestrlar credit
        worksheet.set_column(11 + (max_sem * 2), 11 + (max_sem * 2), 6)  # Jami kredit

        # --- HEADER CHIZISH ---
        worksheet.merge_range(START_ROW, 0, START_ROW + 5, 0, "T/r", fmt_bold)
        worksheet.merge_range(START_ROW, 1, START_ROW + 5, 1, "O'quv fanlari, bloklar va faoliyat turlarining nomlari", fmt_bold)
        worksheet.merge_range(START_ROW, 2, START_ROW, 10, "Talabaning o'quv yuklamasi, soatlarda", fmt_bold)
        worksheet.merge_range(START_ROW, 11, START_ROW, 11 + max_sem - 1, "Soatlarning kurs, semestr va haftalar bo'yicha taqsimoti", fmt_bold)
        worksheet.merge_range(START_ROW, 11 + max_sem, START_ROW, 11 + (max_sem * 2) - 1, "Kreditlarning kurs, semestr va haftalar bo'yicha taqsimoti", fmt_bold)
        worksheet.merge_range(START_ROW, 11 + (max_sem * 2), START_ROW + 5, 11 + (max_sem * 2), "Jami kreditlar", fmt_vertical)

        # 1-QATOR
        worksheet.merge_range(START_ROW + 1, 2, START_ROW + 5, 3, "Umumiy yuklama hajmi", fmt_bold_horizontal)
        worksheet.merge_range(START_ROW + 1, 4, START_ROW + 1, 9, "Auditoriya mashg'ulotlari, soatlarda", fmt_bold)
        worksheet.merge_range(START_ROW + 1, 10, START_ROW + 5, 10, "Mustaqil ta'lim", fmt_vertical)

        # Kurslar
        worksheet.merge_range(START_ROW + 1, 11, START_ROW + 1, 12, "1-kurs", fmt_base)
        worksheet.merge_range(START_ROW + 1, 13, START_ROW + 1, 14, "2-kurs", fmt_base)
        worksheet.merge_range(START_ROW + 1, 15, START_ROW + 1, 16, "3-kurs", fmt_base)
        worksheet.merge_range(START_ROW + 1, 17, START_ROW + 1, 18, "4-kurs", fmt_base)
        if max_sem == 10:
            worksheet.merge_range(START_ROW + 1, 19, START_ROW + 1, 20, "5-kurs", fmt_base)
        
        offset = 11 + max_sem
        worksheet.merge_range(START_ROW + 1, offset, START_ROW + 1, offset + 1, "1-kurs", fmt_base)
        worksheet.merge_range(START_ROW + 1, offset + 2, START_ROW + 1, offset + 3, "2-kurs", fmt_base)
        worksheet.merge_range(START_ROW + 1, offset + 4, START_ROW + 1, offset + 5, "3-kurs", fmt_base)
        worksheet.merge_range(START_ROW + 1, offset + 6, START_ROW + 1, offset + 7, "4-kurs", fmt_base)
        if max_sem == 10:
            worksheet.merge_range(START_ROW + 1, offset + 8, START_ROW + 1, offset + 9, "5-kurs", fmt_base)

        # 2-QATOR
        headers_aud = ["Jami", "Ma'ruza", "Amaliy", "Laboratoriya", "Seminar", "Kurs ishi"]
        for i, h in enumerate(headers_aud):
            worksheet.merge_range(START_ROW + 2, 4 + i, START_ROW + 5, 4 + i, h, fmt_vertical)

        worksheet.merge_range(START_ROW + 2, 11, START_ROW + 3, 11 + max_sem - 1, "Semestrlar", fmt_base)
        worksheet.merge_range(START_ROW + 2, offset, START_ROW + 3, offset + max_sem - 1, "Semestrlar", fmt_base)

        # 4-QATOR
        for i in range(1, max_sem + 1):
            worksheet.write(START_ROW + 4, 10 + i, i, fmt_base)
            worksheet.write(START_ROW + 4, offset - 1 + i, i, fmt_base)

        # 5-QATOR
        worksheet.merge_range(START_ROW + 5, 11, START_ROW + 5, 11 + max_sem - 1, "Semestrdagi auditoriya mashg'ulotlari haftalarining soni", fmt_base_no_wrap)
        worksheet.merge_range(START_ROW + 5, offset, START_ROW + 5, offset + max_sem - 1, "Kredit taqsimoti", fmt_base)

        # 6-QATOR
        worksheet.write(START_ROW + 6, 0, 1, fmt_gray)
        worksheet.write(START_ROW + 6, 1, 2, fmt_gray)
        worksheet.write(START_ROW + 6, 2, 3, fmt_gray)
        worksheet.write(START_ROW + 6, 3, 4, fmt_gray)

        start_idx = 5
        total_cols = 11 + (max_sem * 2) + 1
        for i in range(4, total_cols):
            worksheet.write(START_ROW + 6, i, start_idx, fmt_gray)
            start_idx += 1

        # --- DATA QISMI ---
        row_idx = START_ROW + 7  # Data START_ROW + 7 dan boshlanadi

        # JAMI HISOB-KITOB (Guruhlar bo'yicha alohida)
        majburiy_subjects = [s for s in subjects if s.subject_type == 'majburiy']
        tanlov_subjects = [s for s in subjects if s.subject_type == 'tanlov']

        def get_totals(subject_list):
            res = {
                'credit': 0, 'total': 0, 'aud': 0, 'lec': 0, 'prac': 0,
                'lab': 0, 'sem': 0, 'ind': 0, 'data': []
            }
            for item in subject_list:
                aud = item.lecture_hours + item.practice_hours + item.seminar_hours + item.lab_hours
                total = item.total_hours if item.total_hours else (item.credit * 30)
                ind = total - aud
                
                res['credit'] += item.credit
                res['total'] += total
                res['aud'] += aud
                res['lec'] += item.lecture_hours
                res['prac'] += item.practice_hours
                res['lab'] += item.lab_hours
                res['sem'] += item.seminar_hours
                res['ind'] += ind
                res['data'].append({'obj': item, 'aud': aud, 'ind': ind, 'total': total})
            return res

        m_totals = get_totals(majburiy_subjects)
        t_totals = get_totals(tanlov_subjects)

        def write_total_row(row_idx, label, totals):
            worksheet.write(row_idx, 0, "", fmt_bold)
            worksheet.write(row_idx, 1, f"{label.upper()}:", fmt_bold)
            worksheet.write(row_idx, 2, totals['total'], fmt_bold)
            worksheet.write(row_idx, 3, 0, fmt_bold)
            worksheet.write(row_idx, 4, totals['aud'], fmt_bold)
            worksheet.write(row_idx, 5, totals['lec'], fmt_bold)
            worksheet.write(row_idx, 6, totals['prac'], fmt_bold)
            worksheet.write(row_idx, 7, totals['lab'], fmt_bold)
            worksheet.write(row_idx, 8, totals['sem'], fmt_bold)
            worksheet.write(row_idx, 9, 0, fmt_bold)
            worksheet.write(row_idx, 10, totals['ind'], fmt_bold)
            for c in range(11, 11 + (max_sem * 2)):
                worksheet.write(row_idx, c, "", fmt_base)
            worksheet.write(row_idx, 11 + (max_sem * 2), totals['credit'], fmt_bold)
            return row_idx + 1

        # Majburiy fanlar qismini chiqarish
        if m_totals['data']:
            row_idx = write_total_row(row_idx, "MAJBURIY FANLAR", m_totals)
            counter = 1
            for p in m_totals['data']:
                item = p['obj']
                worksheet.write(row_idx, 0, counter, fmt_base)
                subject_text = item.subject.name
                alts = item.alternative_subjects.all()
                if alts:
                    alt_names = "\n".join([a.name for a in alts])
                    subject_text += f"\n{alt_names}"
                worksheet.write(row_idx, 1, subject_text, fmt_left)
                worksheet.write(row_idx, 2, p['total'], fmt_bold)
                worksheet.write(row_idx, 3, 0, fmt_bold)
                worksheet.write(row_idx, 4, p['aud'], fmt_bold)
                worksheet.write(row_idx, 5, item.lecture_hours if item.lecture_hours else "", fmt_base)
                worksheet.write(row_idx, 6, item.practice_hours if item.practice_hours else "", fmt_base)
                worksheet.write(row_idx, 7, item.lab_hours if item.lab_hours else "", fmt_base)
                worksheet.write(row_idx, 8, item.seminar_hours if item.seminar_hours else "", fmt_base)
                worksheet.write(row_idx, 9, "", fmt_base)
                worksheet.write(row_idx, 10, p['ind'], fmt_bold)
                for i in range(1, max_sem + 1):
                    col_h = 11 + (i - 1); col_c = 11 + max_sem + (i - 1)
                    if item.semester == i:
                        worksheet.write(row_idx, col_h, item.semester_time, fmt_base)
                        worksheet.write(row_idx, col_c, item.credit, fmt_bold)
                    else:
                        worksheet.write(row_idx, col_h, "", fmt_base)
                        worksheet.write(row_idx, col_c, "", fmt_base)
                worksheet.write(row_idx, 11 + (max_sem * 2), item.credit, fmt_bold)
                row_idx += 1
                counter += 1

        # Tanlov fanlari qismini chiqarish
        if t_totals['data']:
            row_idx = write_total_row(row_idx, "TANLOV FANLARI", t_totals)
            counter = 1
            for p in t_totals['data']:
                item = p['obj']
                worksheet.write(row_idx, 0, counter, fmt_base)
                subject_text = item.subject.name
                alts = item.alternative_subjects.all()
                if alts:
                    alt_names = "\n".join([a.name for a in alts])
                    subject_text += f"\n{alt_names}"
                worksheet.write(row_idx, 1, subject_text, fmt_left)
                worksheet.write(row_idx, 2, p['total'], fmt_bold)
                worksheet.write(row_idx, 3, 0, fmt_bold)
                worksheet.write(row_idx, 4, p['aud'], fmt_bold)
                worksheet.write(row_idx, 5, item.lecture_hours if item.lecture_hours else "", fmt_base)
                worksheet.write(row_idx, 6, item.practice_hours if item.practice_hours else "", fmt_base)
                worksheet.write(row_idx, 7, item.lab_hours if item.lab_hours else "", fmt_base)
                worksheet.write(row_idx, 8, item.seminar_hours if item.seminar_hours else "", fmt_base)
                worksheet.write(row_idx, 9, "", fmt_base)
                worksheet.write(row_idx, 10, p['ind'], fmt_bold)
                for i in range(1, max_sem + 1):
                    col_h = 11 + (i - 1); col_c = 11 + max_sem + (i - 1)
                    if item.semester == i:
                        worksheet.write(row_idx, col_h, item.semester_time, fmt_base)
                        worksheet.write(row_idx, col_c, item.credit, fmt_bold)
                    else:
                        worksheet.write(row_idx, col_h, "", fmt_base)
                        worksheet.write(row_idx, col_c, "", fmt_base)
                worksheet.write(row_idx, 11 + (max_sem * 2), item.credit, fmt_bold)
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
        subjects = PlanSubject.objects.filter(education_plan=plan).select_related('subject').prefetch_related('alternative_subjects').order_by('semester',
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

        m_subjects = []
        t_subjects = []
        m_totals = {'credit': 0, 'total': 0, 'auditorium': 0, 'lecture': 0, 'practice': 0, 'seminar': 0, 'lab': 0, 'independent': 0}
        t_totals = {'credit': 0, 'total': 0, 'auditorium': 0, 'lecture': 0, 'practice': 0, 'seminar': 0, 'lab': 0, 'independent': 0}

        for item in subjects:
            aud_hours = item.lecture_hours + item.practice_hours + item.seminar_hours + item.lab_hours
            total = item.total_hours if item.total_hours else (item.credit * 30)
            ind_hours = total - aud_hours
            alts = item.alternative_subjects.all()
            alt_names = "<br>".join([a.name for a in alts]) if alts else ""

            data = {
                'obj': item,
                'auditorium_hours': aud_hours,
                'independent_hours': ind_hours,
                'total_calc': total,
                'alt_names': alt_names
            }

            if item.subject_type == 'majburiy':
                m_subjects.append(data)
                target = m_totals
            else:
                t_subjects.append(data)
                target = t_totals
                
            target['credit'] += item.credit
            target['total'] += total
            target['auditorium'] += aud_hours
            target['lecture'] += item.lecture_hours
            target['practice'] += item.practice_hours
            target['seminar'] += item.seminar_hours
            target['lab'] += item.lab_hours
            target['independent'] += ind_hours
        context = self.admin_site.each_context(request)
        context.update({
            'title': f"O'quv reja: {plan}",
            'site_header': self.admin_site.site_header,
            'has_permission': True,
            'user': request.user,
            'plan': plan,
            'm_subjects': m_subjects,
            't_subjects': t_subjects,
            'm_totals': m_totals,
            't_totals': t_totals,
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