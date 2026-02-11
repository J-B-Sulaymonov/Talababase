from datetime import timedelta, date
from django.db import transaction
from django.db.models import Sum

from education.models import TimeTable, LessonLog
from kadrlar.models import Weekday


def generate_semester_logs(start_date, end_date, academic_year_id, semester):
    """
    Berilgan sana, o'quv yili va semestr uchun jurnal yaratadi.
    """

    # --- O'ZGARISH SHU YERDA ---
    # Barcha jadvallarni emas, faqat tanlangan yil va semestrnikini olamiz!
    timetables = TimeTable.objects.filter(
        academic_year_id=academic_year_id,
        semester=semester
    ).select_related(
        'group', 'subject', 'teacher', 'stream__workload__plan_subjects'
    ).all()
    # ---------------------------

    if not timetables.exists():
        return 0  # Agar bu semestr uchun jadval bo'lmasa, 0 qaytaradi

    # Kesh (Optimization)
    plan_limits = {}
    current_hours_map = {}

    for tt in timetables:
        key = (tt.group.id, tt.subject.id)
        if key not in plan_limits:
            try:
                plan_subject = tt.stream.workload.plan_subjects.first()
                if plan_subject:
                    total_hours = (plan_subject.lecture_hours +
                                   plan_subject.practice_hours +
                                   plan_subject.seminar_hours +
                                   plan_subject.lab_hours)
                    plan_limits[key] = total_hours
                else:
                    plan_limits[key] = 1000
            except Exception:
                plan_limits[key] = 1000

            existing_hours = LessonLog.objects.filter(
                group_id=tt.group.id,
                subject_id=tt.subject.id
            ).aggregate(Sum('hours'))['hours__sum'] or 0
            current_hours_map[key] = existing_hours

    created_count = 0
    current_date = start_date

    with transaction.atomic():
        while current_date <= end_date:
            weekday_order = current_date.weekday() + 1
            # Python xotirasida filter qilish o'rniga QuerySet filter ishlatsak ham bo'ladi,
            # lekin timetables allaqachon olingan bo'lsa, list comprehension tezroq.
            daily_schedules = [t for t in timetables if t.weekday.order == weekday_order]

            for tt in daily_schedules:
                key = (tt.group.id, tt.subject.id)
                limit = plan_limits.get(key, 0)
                current = current_hours_map.get(key, 0)
                lesson_hours = 2.0

                if current + lesson_hours <= limit:
                    # Dublikat tekshiruvi (faqat shu kunga)
                    log, created = LessonLog.objects.get_or_create(
                        date=current_date,
                        timetable=tt,
                        group=tt.group,
                        defaults={
                            'subject': tt.subject,
                            'planned_teacher': tt.teacher,
                            'actual_teacher': tt.teacher,
                            'hours': lesson_hours,
                            'status': 'scheduled',
                            'is_confirmed': False
                        }
                    )
                    if created:
                        created_count += 1
                        current_hours_map[key] += lesson_hours

            current_date += timedelta(days=1)

    return created_count