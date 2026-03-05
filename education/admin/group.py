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

@admin.register(SubGroup)
class SubGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'group',)
    search_fields = ('group__name', 'name')
    list_filter = ('name',)
    ordering = ('group__name', 'name')

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
            education_form = request.POST.get('education_form', 'kunduzgi')

            s1_raw = request.POST.getlist('shift1_levels')
            s2_raw = request.POST.getlist('shift2_levels')
            shift1 = [int(x) for x in s1_raw] if s1_raw else []
            shift2 = [int(x) for x in s2_raw] if s2_raw else []

            service = ScheduleGeneratorService(year_id, season, shift1, shift2, education_form)

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
                'selected_education_form': education_form,
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
            'selected_education_form': 'kunduzgi',
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

@admin.register(SessionPeriod)
class SessionPeriodAdmin(admin.ModelAdmin):
    list_display = (
        'academic_year', 'semester', 'education_form',
        'course', 'start_date', 'end_date', 'weeks_count'
    )
    list_filter = ('academic_year', 'semester', 'education_form', 'course')
    search_fields = ('academic_year__name',)
    ordering = ('-academic_year__name', 'education_form', 'course', 'semester')