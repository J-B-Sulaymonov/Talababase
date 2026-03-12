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

@admin.register(LessonLog)
class LessonLogAdmin(admin.ModelAdmin):
    list_display = ('date', 'group', 'subject', 'planned_teacher', 'actual_teacher', 'employment_type', 'lesson_type', 'status', 'is_confirmed')
    list_filter = ('date', 'status', 'is_confirmed', 'employment_type', 'lesson_type', 'group')
    # O'quv bo'limi ro'yxatni o'zidan turib o'zgartira olishi uchun
    list_editable = ('actual_teacher', 'status', 'is_confirmed')
    search_fields = ('group__name', 'subject__name', 'actual_teacher__first_name')
    date_hierarchy = 'date'

    # O'quv bo'limi yangi qo'sholmasin, faqat generatsiya qilinganini tahrirlasin
    def has_add_permission(self, request):
        return request.user.is_superuser

    change_list_template = "admin/education/lessonlog/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('daily-batch/', self.admin_site.admin_view(self.daily_batch_logs_view), name='lessonlog_daily_batch'),
        ]
        return my_urls + urls

    def daily_batch_logs_view(self, request):
        from kadrlar.models import Teacher
        from students.models import AcademicYear

        # Bugungi sana standart sifatida
        selected_date_str = request.GET.get('date', datetime.date.today().strftime('%Y-%m-%d'))
        
        try:
            selected_date = datetime.datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        except ValueError:
            selected_date = datetime.date.today()
            selected_date_str = selected_date.strftime('%Y-%m-%d')

        # Tanlangan sanaga mos hafta kuni (1: Dushanba ... 6: Shanba)
        # Python: 0=Dushanba, Django (yoki odatiy 1=Dushanba)
        isoweekday = selected_date.isoweekday() 
        
        # POST kelganida (saqlash olinganida)
        if request.method == 'POST':
            # Barcha inputlarni o'qib olib saqlaymiz
            timetable_ids = request.POST.getlist('timetable_id')
            
            for t_id in timetable_ids:
                status = request.POST.get(f"status_{t_id}")
                actual_teacher_id = request.POST.get(f"actual_teacher_{t_id}")
                topic = request.POST.get(f"topic_{t_id}")
                
                if status:
                    # Bazadan qidiramiz
                    log = LessonLog.objects.filter(timetable_id=t_id, date=selected_date).first()
                    
                    if not log:
                        # Topilmasa yangi yaratamiz
                        tt = TimeTable.objects.select_related('stream').get(id=t_id)
                        log = LessonLog(
                            timetable=tt,
                            date=selected_date,
                            group=tt.group or (tt.stream.groups.first() if tt.stream else None),
                            subject=tt.subject,
                            room=tt.room,
                            planned_teacher=tt.teacher,
                            hours=2.00, # Standard 1 para = 2 soat
                            employment_type=tt.stream.employment_type if tt.stream else None,
                            lesson_type=tt.stream.lesson_type if tt.stream else None,
                        )
                        if not log.group:
                            continue # Guruh topilmasa tashlab o'tamiz

                    # O'qituvchi o'zgarishi
                    if actual_teacher_id:
                        log.actual_teacher_id = actual_teacher_id
                    else:
                        log.actual_teacher = log.planned_teacher

                    # Agar 'held' qilingan bo'lsa va o'qituvchi boshqa bo'lsa
                    if status == 'held' and log.actual_teacher_id != log.planned_teacher_id:
                        status = 'replaced'

                    log.status = status
                    log.topic = topic
                    log.save()
                    
            messages.success(request, f"{selected_date_str} kungi dars jurnallari saqlandi!")
            return redirect(reverse('admin:education_lessonlog_changelist'))


        # O'quv yili filtri
        active_year = AcademicYear.objects.filter(is_active=True).first()
        academic_year_id = request.GET.get('academic_year')
        if not academic_year_id and active_year:
            academic_year_id = active_year.id

        # Ushbu kun uchun dars jadvalini qidiramiz
        timetables = TimeTable.objects.filter(weekday__order=isoweekday).select_related(
            'subject', 'group', 'teacher', 'room', 'stream', 'timeslot'
        )
        if academic_year_id:
            timetables = timetables.filter(academic_year_id=academic_year_id)
        
        # Alfavit va dars vaqti bo'yicha tartiblaymiz
        timetables = timetables.order_by('timeslot__start_time', 'group__name', 'stream__name')

        # Tizimdagi bor LessonLog larni o'qib kelamiz
        existing_logs = {
            log.timetable_id: log 
            for log in LessonLog.objects.filter(date=selected_date)
        }

        # Fan bo'yicha o'qituvchilar keshi (har bir fan uchun faqat 1 marta so'rov)
        subject_teachers_cache = {}

        # Context Data tayyorlaymiz
        lessons_data = []
        for tt in timetables:
            group_name = tt.stream.name if tt.stream else (tt.group.name if tt.group else "Noma'lum")
            
            # Agar oldin saqlangan bo'lsa uni olamiz
            log = existing_logs.get(tt.id)
            
            current_status = log.status if log else 'scheduled'
            current_teacher_id = log.actual_teacher_id if log else tt.teacher_id
            current_topic = log.topic if log else ""

            # Fan bo'yicha o'qituvchilarni olish (kesh bilan)
            subject_id = tt.subject_id
            if subject_id not in subject_teachers_cache:
                subject_teachers_cache[subject_id] = list(
                    Teacher.objects.filter(
                        employee__status='active',
                        subjects__id=subject_id
                    ).select_related('employee').order_by('employee__last_name')
                )
            
            lessons_data.append({
                'timetable_id': tt.id,
                'timeslot': tt.timeslot,
                'group_name': group_name,
                'subject': tt.subject.name,
                'room_name': tt.room.name if tt.room else "-",
                'planned_teacher': tt.teacher,
                'current_teacher_id': current_teacher_id,
                'current_status': current_status,
                'current_topic': current_topic,
                'available_teachers': subject_teachers_cache[subject_id],
            })

        context = dict(
            self.admin_site.each_context(request),
            title="Kunlik Dars Jurnali (Guruhlash)",
            selected_date=selected_date_str,
            academic_year_id=int(academic_year_id) if academic_year_id else None,
            academic_years=AcademicYear.objects.all().order_by('-name'),
            lessons_data=lessons_data,
            status_choices=LessonLog.STATUS_CHOICES,
        )

        return render(request, "admin/education/lessonlog/daily_batch.html", context)

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
    filter_horizontal = ('plan_subjects', 'groups')
    inlines = [StreamInline]
    change_list_template = "admin/workload_change_list.html"

    class Media:
        js = ('admin/js/workload_v12.js',)
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
                    course = ps.education_plan.course
                    edu_form = ps.education_plan.education_form
                    filter_q |= Q(
                        specialty_id=spec_id, 
                        student__course_year=course,
                        student__education_form=edu_form,
                        student__status='active'
                    )
                if filter_q:
                    groups = Group.objects.filter(filter_q).distinct().order_by('name')
                    for g in groups:
                        results.append({'id': str(g.id), 'text': g.name})
        return JsonResponse({'results': results})