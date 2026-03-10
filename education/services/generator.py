from collections import defaultdict
from django.db import transaction
from django.db.models import Count
from education.models import TimeTable, ScheduleError, Room, Stream, SessionPeriod
from kadrlar.models import Weekday, TimeSlot, TeacherAvailability


class ScheduleGeneratorService:
    """
    Dars jadvali generatsiya servisi.

    Yaxshilashlar:
    - #6: student_count DB dan haqiqiy aktiv talabalar soni
    - #5: Best-Fit xona tanlash (sig'imga eng yaqin)
    - #2: Kun bo'yicha muvozanat (eng kam yukli kunga joylash)
    - #3: "Oyna" darslarni kamaytirish (ketma-ket slotlar ustuvorligi)
    - #1: Backtracking (joylanmagan stream uchun oldingilarni surish)
    - #4: O'qituvchi kunlik yuklamasi cheklovi
    - #7: Konfigurlash mumkin bo'lgan parametrlar
    - #9: Batafsil generatsiya statistikasi
    """

    # =========================================================
    # #7: KONFIGURLASH MUMKIN BO'LGAN PARAMETRLAR
    # =========================================================
    HOURS_PER_PAIR = 2              # 1 para = 2 soat
    MAX_PAIRS_PER_DAY_TEACHER = 4   # O'qituvchi uchun kunlik max paralar
    MAX_BACKTRACK_ATTEMPTS = 3      # Backtrack urinishlari soni
    BACKTRACK_WINDOW = 5            # Oxirgi nechta joylashtirilgan stream tekshiriladi
    DEFAULT_WEEKS_FULLTIME = 15     # Kunduzgi default hafta soni
    DEFAULT_WEEKS_PARTTIME = 4      # Sirtqi default hafta soni

    # Xona turlari mosligi
    ROOM_TYPE_MAP = {
        'lecture': ['lecture'],
        'practice': ['practice', 'lecture'],
        'lab': ['lab', 'computer'],
        'seminar': ['practice'],
    }

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

        # #6: Talabalar soni keshi (group_id -> count)
        self._student_count_cache = {}

        self.matrix_teacher = set()
        self.matrix_group = set()
        self.matrix_room = set()
        self.schedule_map = []
        self.errors = []

        # #9: Batafsil statistika
        self.stats = {
            'total_streams': 0,
            'placed_streams': 0,
            'failed_streams': 0,
            'backtrack_attempts': 0,
            'backtrack_successes': 0,
            'total_pairs_placed': 0,
            'total_pairs_needed': 0,
            'fail_reasons': defaultdict(int),
            'per_teacher': defaultdict(lambda: {'placed': 0, 'failed': 0}),
            'per_group': defaultdict(lambda: {'placed': 0, 'failed': 0}),
        }

        # #2: Kun yuklamasi hisoblagichlari
        self._day_load_group = defaultdict(int)      # (day_id, group_id) -> dars soni
        self._day_load_teacher = defaultdict(int)     # (day_id, teacher_id) -> dars soni

        # #1: Backtracking uchun joylashtirilgan streamlar tarixi
        self._placement_history = []  # [(stream, groups, group_ids, placement_item), ...]

        # Boshqa ta'lim shaklining dars jadvalidan teacher/room bandligini yuklash
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

    # --- YORDAMCHI METODLAR ---
    def get_stream_course(self, stream):
        """Stream qaysi kursga tegishliligini O'quv Rejasidan aniqlaydi"""
        plan_subject = stream.workload.plan_subjects.first()
        if plan_subject and plan_subject.education_plan:
            return plan_subject.education_plan.course
        return 1  # Topilmasa default 1-kurs

    def get_weeks_duration(self, stream):
        """SessionPeriod dan dinamik hafta sonini olish"""
        level = self.get_stream_course(stream)

        # Avval keshdan qidiramiz
        if level in self.session_weeks_cache:
            return self.session_weeks_cache[level]

        # Kesh topilmasa, ta'lim shakliga qarab default
        if self.education_form == 'sirtqi':
            return self.DEFAULT_WEEKS_PARTTIME
        return self.DEFAULT_WEEKS_FULLTIME

    def calculate_pairs(self, stream):
        plan_subject = stream.workload.plan_subjects.first()
        if not plan_subject:
            return 0

        hours_map = {
            'lecture': plan_subject.lecture_hours,
            'practice': plan_subject.practice_hours,
            'lab': plan_subject.lab_hours,
            'seminar': plan_subject.seminar_hours
        }
        total_hours = hours_map.get(stream.lesson_type, 0)
        weeks = self.get_weeks_duration(stream)

        pairs = (total_hours / weeks) / self.HOURS_PER_PAIR
        if pairs > 0 and pairs < 1:
            return 1
        return int(pairs + 0.5)

    # =========================================================
    # #6: STUDENT_COUNT TO'G'RI HISOBLASH
    # =========================================================
    def get_student_count(self, groups):
        """
        Guruhlar bo'yicha haqiqiy aktiv talabalar sonini hisoblash.
        DB dan to'g'ridan-to'g'ri so'rov yuboriladi va keshlanadi.
        """
        from students.models import Student

        count = 0
        for g in groups:
            if g.id not in self._student_count_cache:
                # DB dan haqiqiy aktiv talabalar sonini olamiz
                real_count = Student.objects.filter(
                    group_id=g.id,
                    status='active'
                ).count()
                self._student_count_cache[g.id] = real_count

            count += self._student_count_cache[g.id]

        # Agar birorta ham talaba topilmasa, 1 qaytaramiz (division by zero oldini olish)
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

        if len(all_slots) < 4:
            return all_slots

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

    # =========================================================
    # #2: KUN BO'YICHA MUVOZANAT
    # =========================================================
    def _get_sorted_days_for_groups(self, group_ids, teacher_id):
        """
        Kunlarni guruh va o'qituvchi yuklanishi bo'yicha saralab beradi.
        Eng kam yukli kun birinchi bo'ladi.
        """
        day_scores = []
        for day in self.weekdays:
            # Guruhlarning shu kundagi umumiy darslar soni
            group_load = sum(
                self._day_load_group.get((day.id, g_id), 0)
                for g_id in group_ids
            )
            # O'qituvchining shu kundagi darslar soni
            teacher_load = self._day_load_teacher.get((day.id, teacher_id), 0)

            # Umumiy yuk = guruh yuki + o'qituvchi yuki
            total_load = group_load + teacher_load
            day_scores.append((day, total_load))

        # Eng kam yukli kundan boshlaymiz
        day_scores.sort(key=lambda x: x[1])
        return [d[0] for d in day_scores]

    # =========================================================
    # #3: "OYNA" DARSLARNI KAMAYTIRISH
    # =========================================================
    def _calculate_gap_penalty(self, day_id, slot, group_ids):
        """
        Berilgan slot uchun "oyna" (bo'shliq) jarimasi hisoblash.
        Agar slot guruhning mavjud darslariga yaqin (ketma-ket) bo'lsa — jarima past.
        Agar slot "oyna" hosil qilsa — jarima yuqori.
        """
        slot_index = None
        for i, ts in enumerate(self.timeslots):
            if ts.id == slot.id:
                slot_index = i
                break

        if slot_index is None:
            return 0

        # Shu kundagi guruhlarga tegishli band slotlar indekslari
        occupied_indices = set()
        for g_id in group_ids:
            for i, ts in enumerate(self.timeslots):
                if (day_id, ts.id, g_id) in self.matrix_group:
                    occupied_indices.add(i)

        if not occupied_indices:
            # Hali hech narsa yo'q — jarima yo'q, lekin erta slotlarni afzal ko'ramiz
            return slot_index  # Past indeks = past jarima

        # Yangi slotni qo'shganda bo'shliq (gap) bor-yo'qligini tekshirish
        test_indices = sorted(occupied_indices | {slot_index})
        total_gap = 0
        for i in range(1, len(test_indices)):
            gap = test_indices[i] - test_indices[i - 1] - 1
            if gap > 0:
                total_gap += gap * gap  # Katta bo'shliq = katta jarima (kvadratik)

        return total_gap

    # =========================================================
    # #5: AQLLI XONA TANLASH (BEST-FIT)
    # =========================================================
    def _find_best_fit_room(self, day_id, slot_id, student_count, allowed_room_types):
        """
        Sig'imga eng yaqin (lekin kichik bo'lmagan) xonani tanlaydi.
        Bu katta xonalarni katta guruhlarga saqlashga yordam beradi.
        """
        best_room = None
        best_diff = float('inf')

        for room in self.rooms:
            if room.room_type not in allowed_room_types:
                continue
            if room.capacity < student_count:
                continue
            if (day_id, slot_id, room.id) in self.matrix_room:
                continue

            diff = room.capacity - student_count
            if diff < best_diff:
                best_diff = diff
                best_room = room

        return best_room

    # =========================================================
    # #4 + #2 + #3: YAXSHILANGAN SLOT TOPISH
    # =========================================================
    def find_best_slot(self, stream, groups, pairs_needed, student_count):
        group_ids = [g.id for g in groups]
        teacher = stream.teacher
        allowed_slots = self.get_allowed_slots_for_stream(stream)
        allowed_room_types = self.ROOM_TYPE_MAP.get(stream.lesson_type, ['practice'])

        placed_slots = []
        fail_reasons = {
            "teacher_busy": 0,
            "group_busy": 0,
            "room_busy": 0,
            "room_capacity": 0,
            "teacher_unavailable": 0,
            "teacher_overloaded": 0,  # #4: Yangi sabab
        }

        # #2: Kunlarni yuklanish bo'yicha saralash (eng bo'sh kundan boshlash)
        sorted_days = self._get_sorted_days_for_groups(group_ids, teacher.id)

        for day in sorted_days:
            # Shu stream shu kunga allaqachon qo'yilgan bo'lsa, o'tkazamiz
            if any(p['weekday_id'] == day.id for p in self.schedule_map if p['stream'] == stream):
                continue

            # #4: O'qituvchi kunlik limiti tekshiruvi
            teacher_day_load = self._day_load_teacher.get((day.id, teacher.id), 0)
            if teacher_day_load >= self.MAX_PAIRS_PER_DAY_TEACHER:
                fail_reasons["teacher_overloaded"] += 1
                continue

            # #3: Slotlarni "oyna" jarimasi bo'yicha saralash
            slot_candidates = []
            for slot in allowed_slots:
                gap_penalty = self._calculate_gap_penalty(day.id, slot, group_ids)
                slot_candidates.append((slot, gap_penalty))

            # Past jarima = yaxshiroq (ketma-ket darslar)
            slot_candidates.sort(key=lambda x: x[1])

            for slot, _ in slot_candidates:
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

                # #5: Best-Fit xona tanlash
                best_room = self._find_best_fit_room(
                    day.id, slot.id, student_count, allowed_room_types
                )

                if not best_room:
                    valid_type_rooms = [r for r in self.rooms if r.room_type in allowed_room_types]
                    if any(r.capacity >= student_count for r in valid_type_rooms):
                        fail_reasons["room_busy"] += 1
                    else:
                        fail_reasons["room_capacity"] += 1
                    continue

                # Joylashtiramiz
                placed_slots.append({'weekday': day, 'timeslot': slot, 'room': best_room})
                self.matrix_teacher.add((day.id, slot.id, teacher.id))
                self.matrix_room.add((day.id, slot.id, best_room.id))
                for g_id in group_ids:
                    self.matrix_group.add((day.id, slot.id, g_id))

                # #2: Yuklanish hisoblagichlarini yangilash
                self._day_load_teacher[(day.id, teacher.id)] += 1
                for g_id in group_ids:
                    self._day_load_group[(day.id, g_id)] += 1

                if len(placed_slots) == pairs_needed:
                    return placed_slots, None

                # Shu kundan faqat bitta slot olamiz, keyingi kunga o'tamiz
                break

            if len(placed_slots) == pairs_needed:
                break

        return placed_slots, fail_reasons

    # =========================================================
    # #1: BACKTRACKING
    # =========================================================
    def _try_backtrack(self, stream, groups, pairs_needed, student_count):
        """
        Joylanmagan stream uchun oldingi joylashtirilgan streamlarni
        boshqa slotlarga surish va qayta urinish.

        Mantiq:
        1. Oxirgi N ta joylashtirilgan streamni ko'rib chiqamiz
        2. Har birini o'chirib, hozirgi streamni joylashtira olamizmi tekshiramiz
        3. Agar ha — o'chrilganini boshqa joyga qayta o'rnatamiz
        4. MAX_BACKTRACK_ATTEMPTS ta urinish
        """
        self.stats['backtrack_attempts'] += 1

        # Oxirgi BACKTRACK_WINDOW ta joylashtirilgan stream
        candidates = self._placement_history[-self.BACKTRACK_WINDOW:]
        group_ids_current = [g.id for g in groups]
        teacher_current = stream.teacher
        allowed_slots_current = self.get_allowed_slots_for_stream(stream)
        allowed_room_types_current = self.ROOM_TYPE_MAP.get(stream.lesson_type, ['practice'])

        attempts = 0

        for prev_stream, prev_groups, prev_group_ids, prev_items in reversed(candidates):
            if attempts >= self.MAX_BACKTRACK_ATTEMPTS:
                break
            attempts += 1

            # O'zimizning stream ni qayta joylashtirmaymiz
            if prev_stream.id == stream.id:
                continue

            # Oldingi streamning bitta slotini o'chirish simulyatsiyasi
            for prev_item in prev_items:
                prev_day_id = prev_item['weekday_id']
                prev_slot_id = prev_item['timeslot_id']

                # Oldingi joyni bo'shatish
                self.matrix_teacher.discard((prev_day_id, prev_slot_id, prev_stream.teacher.id))
                self.matrix_room.discard((prev_day_id, prev_slot_id, prev_item['room_id']))
                for g_id in prev_group_ids:
                    self.matrix_group.discard((prev_day_id, prev_slot_id, g_id))

                # Yuklanish hisoblagichlarini kamaytirish
                key_t = (prev_day_id, prev_stream.teacher.id)
                if self._day_load_teacher[key_t] > 0:
                    self._day_load_teacher[key_t] -= 1
                for g_id in prev_group_ids:
                    key_g = (prev_day_id, g_id)
                    if self._day_load_group[key_g] > 0:
                        self._day_load_group[key_g] -= 1

            # Hozirgi streamni shu bo'shatilgan joyga joylashtirishga urinish
            new_placed, new_reasons = self.find_best_slot(
                stream, groups, pairs_needed, student_count
            )

            if len(new_placed) == pairs_needed:
                # Muvaffaqiyat! Endi oldingi streamni boshqa joyga joylashtiramiz
                prev_pairs = len(prev_items)
                prev_student_count = self.get_student_count(prev_groups)

                # Oldingi streamni schedule_map dan o'chiramiz
                self.schedule_map = [
                    item for item in self.schedule_map
                    if item['stream'].id != prev_stream.id
                ]

                re_placed, _ = self.find_best_slot(
                    prev_stream, prev_groups, prev_pairs, prev_student_count
                )

                if len(re_placed) >= prev_pairs:
                    # Barcha joylanganlarni schedule_map ga qo'shamiz
                    prev_course = self.get_stream_course(prev_stream)
                    for item in re_placed:
                        self.schedule_map.append({
                            'stream': prev_stream,
                            'workload': prev_stream.workload,
                            'weekday': item['weekday'], 'weekday_id': item['weekday'].id,
                            'timeslot': item['timeslot'], 'timeslot_id': item['timeslot'].id,
                            'room': item['room'], 'room_id': item['room'].id,
                            'teacher_name': str(prev_stream.teacher),
                            'subject_name': prev_stream.workload.subject.name,
                            'group_ids': prev_group_ids,
                            'label': f"{prev_stream.workload.subject.name} ({prev_stream.get_lesson_type_display()})",
                            'student_count': prev_student_count,
                            'room_name': item['room'].name,
                            'course_level': prev_course,
                        })

                    self.stats['backtrack_successes'] += 1
                    return new_placed
                else:
                    # Oldingi streamni qayta joylashtirib bo'lmadi,
                    # hammasini tiklash kerak — hozirgi stream ni o'chiramiz
                    for item in new_placed:
                        d_id = item['weekday'].id
                        s_id = item['timeslot'].id
                        self.matrix_teacher.discard((d_id, s_id, teacher_current.id))
                        self.matrix_room.discard((d_id, s_id, item['room'].id))
                        for g_id in group_ids_current:
                            self.matrix_group.discard((d_id, s_id, g_id))
                        key_t = (d_id, teacher_current.id)
                        if self._day_load_teacher[key_t] > 0:
                            self._day_load_teacher[key_t] -= 1
                        for g_id in group_ids_current:
                            key_g = (d_id, g_id)
                            if self._day_load_group[key_g] > 0:
                                self._day_load_group[key_g] -= 1

                    # Hozirgi streamning yozuvlarini o'chiramiz
                    self.schedule_map = [
                        item for item in self.schedule_map
                        if item['stream'].id != stream.id
                    ]

                    # Oldingi streamni eski joylariga tiklash
                    for prev_item in prev_items:
                        d_id = prev_item['weekday_id']
                        s_id = prev_item['timeslot_id']
                        self.matrix_teacher.add((d_id, s_id, prev_stream.teacher.id))
                        self.matrix_room.add((d_id, s_id, prev_item['room_id']))
                        for g_id in prev_group_ids:
                            self.matrix_group.add((d_id, s_id, g_id))
                        self._day_load_teacher[(d_id, prev_stream.teacher.id)] += 1
                        for g_id in prev_group_ids:
                            self._day_load_group[(d_id, g_id)] += 1

                    # schedule_map ga qaytaramiz
                    for prev_item in prev_items:
                        self.schedule_map.append(prev_item)

                    continue  # Keyingi candidateni sinash
            else:
                # Joylashmadi, matritsalarni orqaga qaytarish
                # Hozirgi urinishda qisman joylashgan narsalarni tozalash
                for item in new_placed:
                    d_id = item['weekday'].id
                    s_id = item['timeslot'].id
                    self.matrix_teacher.discard((d_id, s_id, teacher_current.id))
                    self.matrix_room.discard((d_id, s_id, item['room'].id))
                    for g_id in group_ids_current:
                        self.matrix_group.discard((d_id, s_id, g_id))
                    key_t = (d_id, teacher_current.id)
                    if self._day_load_teacher[key_t] > 0:
                        self._day_load_teacher[key_t] -= 1
                    for g_id in group_ids_current:
                        key_g = (d_id, g_id)
                        if self._day_load_group[key_g] > 0:
                            self._day_load_group[key_g] -= 1

                # Oldingilarni tiklash
                for prev_item in prev_items:
                    d_id = prev_item['weekday_id']
                    s_id = prev_item['timeslot_id']
                    self.matrix_teacher.add((d_id, s_id, prev_stream.teacher.id))
                    self.matrix_room.add((d_id, s_id, prev_item['room_id']))
                    for g_id in prev_group_ids:
                        self.matrix_group.add((d_id, s_id, g_id))
                    self._day_load_teacher[(d_id, prev_stream.teacher.id)] += 1
                    for g_id in prev_group_ids:
                        self._day_load_group[(d_id, g_id)] += 1

                continue

        return None  # Backtracking muvaffaqiyatsiz

    # =========================================================
    # ASOSIY GENERATSIYA
    # =========================================================
    def generate(self, dry_run=True):
        raw_streams = self.fetch_streams()
        streams = self.sort_streams_by_priority(raw_streams)

        self.schedule_map = []
        self.errors = []
        self._placement_history = []

        # #9: Statistikani boshlash
        self.stats['total_streams'] = len(streams)

        for stream in streams:
            pairs_needed = self.calculate_pairs(stream)
            if pairs_needed < 1:
                continue

            self.stats['total_pairs_needed'] += pairs_needed

            groups = list(stream.groups.all())
            group_ids = [g.id for g in groups]
            student_count = self.get_student_count(groups)
            teacher_name = str(stream.teacher)

            allocated, reasons = self.find_best_slot(stream, groups, pairs_needed, student_count)

            # #1: Agar to'liq joylashmagan bo'lsa — Backtracking urinishi
            missing = pairs_needed - len(allocated)
            if missing > 0 and len(self._placement_history) > 0:
                # Avval qisman joylashganlarni qaytarib olamiz (backtrack uchun toza holat)
                # Backtrack bilan qayta urinish
                backtrack_result = self._try_backtrack(
                    stream, groups, pairs_needed, student_count
                )
                if backtrack_result is not None:
                    allocated = backtrack_result
                    missing = 0
                    reasons = None

            # --- Streamning kursini ham natijaga qo'shamiz (Template uchun) ---
            course_level = self.get_stream_course(stream)

            placed_items = []
            for item in allocated:
                entry = {
                    'stream': stream,
                    'workload': stream.workload,
                    'weekday': item['weekday'], 'weekday_id': item['weekday'].id,
                    'timeslot': item['timeslot'], 'timeslot_id': item['timeslot'].id,
                    'room': item['room'], 'room_id': item['room'].id,
                    'teacher_name': teacher_name,
                    'subject_name': stream.workload.subject.name,
                    'group_ids': group_ids,
                    'label': f"{stream.workload.subject.name} ({stream.get_lesson_type_display()})",
                    'student_count': student_count,
                    'room_name': item['room'].name,
                    'course_level': course_level,
                }
                self.schedule_map.append(entry)
                placed_items.append(entry)

            # #1: Backtracking tarixga qo'shish
            if placed_items:
                self._placement_history.append(
                    (stream, groups, group_ids, placed_items)
                )

            # #9: Statistika yangilash
            self.stats['total_pairs_placed'] += len(allocated)
            if missing <= 0:
                self.stats['placed_streams'] += 1
                self.stats['per_teacher'][teacher_name]['placed'] += 1
                for g_id in group_ids:
                    self.stats['per_group'][g_id]['placed'] += 1
            else:
                self.stats['failed_streams'] += 1
                self.stats['per_teacher'][teacher_name]['failed'] += 1
                for g_id in group_ids:
                    self.stats['per_group'][g_id]['failed'] += 1

            if missing > 0:
                if reasons:
                    top_reason = max(reasons, key=reasons.get)
                    detail = f"{missing} ta para qolib ketdi. Sabab: {top_reason}"
                    # #9: Sabablarni yig'ish
                    for r_key, r_count in reasons.items():
                        if r_count > 0:
                            self.stats['fail_reasons'][r_key] += r_count
                else:
                    detail = f"{missing} ta para joylashmadi."
                    self.stats['fail_reasons']['unknown'] += missing

                self.errors.append({
                    'workload': stream.workload,
                    'reason': detail,
                    'stats': reasons,
                    # #9: Qo'shimcha ma'lumot
                    'teacher': teacher_name,
                    'groups': ', '.join([g.name for g in groups]),
                    'lesson_type': stream.get_lesson_type_display(),
                    'pairs_needed': pairs_needed,
                    'pairs_placed': len(allocated),
                })

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

    # =========================================================
    # #9: STATISTIKA OLISH
    # =========================================================
    def get_stats_summary(self):
        """Generatsiya natijalarining inson o'qiy oladigan xulosasi"""
        s = self.stats
        total = s['total_streams']
        placed = s['placed_streams']
        failed = s['failed_streams']
        pct = (placed / total * 100) if total > 0 else 0

        summary = {
            'total_streams': total,
            'placed_streams': placed,
            'failed_streams': failed,
            'success_percent': round(pct, 1),
            'total_pairs_needed': s['total_pairs_needed'],
            'total_pairs_placed': s['total_pairs_placed'],
            'backtrack_attempts': s['backtrack_attempts'],
            'backtrack_successes': s['backtrack_successes'],
            'fail_reasons': dict(s['fail_reasons']),
        }
        return summary