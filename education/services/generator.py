from django.db import transaction
from django.db.models import Count
from education.models import TimeTable, ScheduleError, Room, Stream, SessionPeriod
from kadrlar.models import Weekday, TimeSlot, TeacherAvailability


class ScheduleGeneratorService:
    WEEKS_IN_SEMESTER = 15  # Default kunduzgi uchun

    def __init__(self, year_id, season, shift1_levels=None, shift2_levels=None, education_form='kunduzgi'):
        self.year_id = year_id
        self.season = season
        self.education_form = education_form
        self.shift1_levels = shift1_levels if shift1_levels is not None else [1, 4]
        self.shift2_levels = shift2_levels if shift2_levels is not None else [2, 3]

        self.weekdays = list(Weekday.objects.order_by('order'))
        self.timeslots = list(TimeSlot.objects.order_by('start_time'))
        self.rooms = list(Room.objects.filter(is_active=True).order_by('capacity'))

        # O'qituvchi bo'sh vaqtlari keshi (soatbay uchun)
        self.teacher_availability_cache = set()
        availabilities = TeacherAvailability.objects.all().prefetch_related('timeslots')
        for av in availabilities:
            for slot in av.timeslots.all():
                self.teacher_availability_cache.add((av.teacher_id, av.weekday_id, slot.id))

        # SessionPeriod keshi (kurs -> hafta soni)
        self.session_weeks_cache = {}
        periods = SessionPeriod.objects.filter(
            academic_year_id=self.year_id,
            semester=self.season,
            education_form=self.education_form
        )
        for p in periods:
            self.session_weeks_cache[p.course] = p.weeks_count

        self.matrix_teacher = set()
        self.matrix_group = set()
        self.matrix_room = set()
        self.schedule_map = []
        self.errors = []

        # Boshqa ta'lim shaklining dars jadvalidan teacher/room bandligini yuklash
        # (Kunduzgi generatsiya qilganda sirtqi jadval inobatga olinadi va aksincha)
        self._load_cross_form_conflicts()

    def _load_cross_form_conflicts(self):
        """
        Boshqa ta'lim shakli bo'yicha mavjud jadvaldan o'qituvchi va xona
        bandligini matrix'ga qo'shadi. Bu kunduzgi va sirtqi dars vaqtlari
        bir-biriga to'g'ri kelmasligi uchun zarur.
        """
        other_form = 'sirtqi' if self.education_form == 'kunduzgi' else 'kunduzgi'
        existing = TimeTable.objects.filter(
            academic_year_id=self.year_id,
            semester=self.season,
            education_form=other_form
        ).values_list('weekday_id', 'timeslot_id', 'teacher_id', 'room_id')

        for weekday_id, timeslot_id, teacher_id, room_id in existing:
            self.matrix_teacher.add((weekday_id, timeslot_id, teacher_id))
            if room_id:
                self.matrix_room.add((weekday_id, timeslot_id, room_id))

    def get_target_semesters(self):
        return [1, 3, 5, 7, 9] if self.season == 'autumn' else [2, 4, 6, 8, 10]

    def fetch_streams(self):
        semesters = self.get_target_semesters()
        streams = Stream.objects.filter(
            workload__plan_subjects__education_plan__academic_year_id=self.year_id,
            workload__plan_subjects__semester__in=semesters,
            workload__plan_subjects__education_plan__education_form=self.education_form,
            teacher__isnull=False
        ).select_related(
            'workload', 'workload__subject', 'teacher'
        ).prefetch_related(
            'groups', 'workload__plan_subjects', 'workload__plan_subjects__education_plan'
        ).annotate(
            group_count=Count('groups')
        ).distinct()
        return list(streams)

    # --- YORDAMCHI METOD ---
    def get_stream_course(self, stream):
        """Stream qaysi kursga tegishliligini O'quv Rejasidan aniqlaydi"""
        plan_subject = stream.workload.plan_subjects.first()
        if plan_subject and plan_subject.education_plan:
            return plan_subject.education_plan.course
        return 1  # Topilmasa default 1-kurs

    # -----------------------------

    def get_weeks_duration(self, stream):
        """SessionPeriod dan dinamik hafta sonini olish"""
        level = self.get_stream_course(stream)

        # Avval keshdan qidiramiz
        if level in self.session_weeks_cache:
            return self.session_weeks_cache[level]

        # Kesh topilmasa, ta'lim shakliga qarab default
        if self.education_form == 'sirtqi':
            return 4  # Sirtqi default: 4 hafta
        return self.WEEKS_IN_SEMESTER  # Kunduzgi default: 15 hafta

    def calculate_pairs(self, stream):
        plan_subject = stream.workload.plan_subjects.first()
        if not plan_subject: return 0

        hours_map = {
            'lecture': plan_subject.lecture_hours,
            'practice': plan_subject.practice_hours,
            'lab': plan_subject.lab_hours,
            'seminar': plan_subject.seminar_hours
        }
        total_hours = hours_map.get(stream.lesson_type, 0)
        weeks = self.get_weeks_duration(stream)

        pairs = (total_hours / weeks) / 2
        if pairs > 0 and pairs < 1:
            return 1
        return int(pairs + 0.5)

    def get_student_count(self, groups):
        count = 0
        for g in groups:
            c = 0
            if hasattr(g, 'student_count') and g.student_count > 0:
                c = g.student_count
            elif hasattr(g, 'student_set'):
                c = g.student_set.count()
            elif hasattr(g, 'students'):
                c = g.students.count()
            count += c
        return count if count > 0 else 1

    def sort_streams_by_priority(self, streams):
        def priority_key(stream):
            group_score = stream.group_count * 100
            emp_type = getattr(stream.teacher, 'employment_type', 'main')
            teacher_score = 1000 if emp_type == 'hourly' else 0
            type_score = 50 if stream.lesson_type == 'lab' else 0

            level = self.get_stream_course(stream)
            level_score = 500 if self.education_form == 'sirtqi' else 0

            return -(group_score + teacher_score + type_score + level_score)

        return sorted(streams, key=priority_key)

    def get_allowed_slots_for_stream(self, stream):
        """
        Sirtqi talabalar uchun smena cheklovi yo'q (kun bo'yi dars).
        Kunduzgi talabalar uchun shift1/shift2 bo'yicha cheklov saqlanadi.
        """
        level = self.get_stream_course(stream)
        all_slots = self.timeslots

        if len(all_slots) < 4: return all_slots

        # Sirtqi talabalar uchun smena cheklovi yo'q - kun bo'yi dars
        if self.education_form == 'sirtqi':
            return all_slots

        # Kunduzgi: Smena tekshiruvi
        is_shift1 = level in self.shift1_levels
        is_shift2 = level in self.shift2_levels

        if is_shift1:
            return all_slots[:4]
        elif is_shift2:
            start_index = 2
            return all_slots[start_index: start_index + 4]

        return all_slots

    def is_teacher_available(self, teacher, day_id, slot_id):
        if (day_id, slot_id, teacher.id) in self.matrix_teacher:
            return False, "O'qituvchi boshqa darsda band"
        emp_type = getattr(teacher, 'employment_type', 'main')
        if emp_type != 'hourly':
            return True, "OK"
        if (teacher.id, day_id, slot_id) in self.teacher_availability_cache:
            return True, "OK"
        return False, "O'qituvchi ish vaqti emas (Soatbay)"

    def find_best_slot(self, stream, groups, pairs_needed, student_count):
        group_ids = [g.id for g in groups]
        teacher = stream.teacher
        allowed_slots = self.get_allowed_slots_for_stream(stream)

        room_type_map = {
            'lecture': ['lecture'],
            'practice': ['practice', 'lecture'],
            'lab': ['lab', 'computer'],
            'seminar': ['practice']
        }
        allowed_room_types = room_type_map.get(stream.lesson_type, ['practice'])

        placed_slots = []
        fail_reasons = {
            "teacher_busy": 0, "group_busy": 0, "room_busy": 0,
            "room_capacity": 0, "teacher_unavailable": 0
        }

        for day in self.weekdays:
            if any(p['weekday_id'] == day.id for p in self.schedule_map if p['stream'] == stream):
                continue

            for slot in allowed_slots:
                is_avail, reason = self.is_teacher_available(teacher, day.id, slot.id)
                if not is_avail:
                    if "ish vaqti" in reason:
                        fail_reasons["teacher_unavailable"] += 1
                    else:
                        fail_reasons["teacher_busy"] += 1
                    continue

                groups_busy = False
                for g_id in group_ids:
                    if (day.id, slot.id, g_id) in self.matrix_group:
                        groups_busy = True
                        break
                if groups_busy:
                    fail_reasons["group_busy"] += 1
                    continue

                best_room = None
                for room in self.rooms:
                    if room.room_type not in allowed_room_types: continue
                    if room.capacity < student_count: continue
                    if (day.id, slot.id, room.id) in self.matrix_room: continue
                    best_room = room
                    break

                if not best_room:
                    valid_type_rooms = [r for r in self.rooms if r.room_type in allowed_room_types]
                    if any(r.capacity >= student_count for r in valid_type_rooms):
                        fail_reasons["room_busy"] += 1
                    else:
                        fail_reasons["room_capacity"] += 1
                    continue

                placed_slots.append({'weekday': day, 'timeslot': slot, 'room': best_room})
                self.matrix_teacher.add((day.id, slot.id, teacher.id))
                self.matrix_room.add((day.id, slot.id, best_room.id))
                for g_id in group_ids:
                    self.matrix_group.add((day.id, slot.id, g_id))

                if len(placed_slots) == pairs_needed:
                    return placed_slots, None

            if len(placed_slots) == pairs_needed: break

        return placed_slots, fail_reasons

    def generate(self, dry_run=True):
        raw_streams = self.fetch_streams()
        streams = self.sort_streams_by_priority(raw_streams)

        self.schedule_map = []
        self.errors = []

        # Cross-form konflikt matritsalarini saqlab qolish kerak - ularni tozalamaymiz
        # Faqat yangi generatsiya jarayonidagi bandlikni saqlaymiz
        # Eslatma: __init__ da cross-form konfliktlar allaqachon yuklangan

        for stream in streams:
            pairs_needed = self.calculate_pairs(stream)
            if pairs_needed < 1: continue

            groups = list(stream.groups.all())
            student_count = self.get_student_count(groups)

            allocated, reasons = self.find_best_slot(stream, groups, pairs_needed, student_count)

            # --- Streamning kursini ham natijaga qo'shamiz (Template uchun) ---
            course_level = self.get_stream_course(stream)

            for item in allocated:
                self.schedule_map.append({
                    'stream': stream,
                    'workload': stream.workload,
                    'weekday': item['weekday'], 'weekday_id': item['weekday'].id,
                    'timeslot': item['timeslot'], 'timeslot_id': item['timeslot'].id,
                    'room': item['room'], 'room_id': item['room'].id,
                    'teacher_name': str(stream.teacher),
                    'subject_name': stream.workload.subject.name,
                    'group_ids': [g.id for g in groups],
                    'label': f"{stream.workload.subject.name} ({stream.get_lesson_type_display()})",
                    'student_count': student_count,
                    'room_name': item['room'].name,
                    'course_level': course_level,  # <-- MUHIM
                })

            missing = pairs_needed - len(allocated)
            if missing > 0:
                if reasons:
                    top_reason = max(reasons, key=reasons.get)
                    detail = f"{missing} ta para qolib ketdi. Sabab: {top_reason}"
                else:
                    detail = f"{missing} ta para joylashmadi."
                self.errors.append({'workload': stream.workload, 'reason': detail, 'stats': reasons})

        if not dry_run:
            self._save_to_db()

        return self.schedule_map, self.errors

    def _save_to_db(self):
        with transaction.atomic():
            # Faqat shu ta'lim shakli bo'yicha tozalash
            TimeTable.objects.filter(
                academic_year_id=self.year_id,
                semester=self.season,
                education_form=self.education_form
            ).delete()

            objs = []
            for item in self.schedule_map:
                for group_id in item['group_ids']:
                    objs.append(TimeTable(
                        academic_year_id=self.year_id,
                        semester=self.season,
                        education_form=self.education_form,
                        weekday=item['weekday'],
                        timeslot=item['timeslot'],
                        stream=item['stream'],
                        subject=item['stream'].workload.subject,
                        teacher=item['stream'].teacher,
                        group_id=group_id,
                        room=item['room']
                    ))
            TimeTable.objects.bulk_create(objs)
            # Xatoliklar (ixtiyoriy)
            ScheduleError.objects.filter(academic_year_id=self.year_id).delete()