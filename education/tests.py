"""
education app uchun Unit testlari.
Testlar: EducationPlan, PlanSubject, Room, Workload, SessionPeriod modellari.
"""
import datetime

from django.test import TestCase
from django.core.exceptions import ValidationError

from students.models import Specialty, AcademicYear, Subject, Group
from .models import (
    EducationPlan, PlanSubject, Room,
    Workload, SubGroup, SessionPeriod,
)


# =============================================================================
# 🔧 UMUMIY MA'LUMOTLAR
# =============================================================================
class EducationBaseSetup(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.specialty = Specialty.objects.create(name="Kompyuter injiniringi", code="60610")
        cls.specialty2 = Specialty.objects.create(name="Iqtisodiyot", code="60400")
        cls.academic_year = AcademicYear.objects.create(name="2024-2025", is_active=True)
        cls.group = Group.objects.create(name="KI-21", specialty=cls.specialty)
        cls.group2 = Group.objects.create(name="IQ-21", specialty=cls.specialty2)
        cls.subject = Subject.objects.create(name="Matematik analiz")
        cls.subject2 = Subject.objects.create(name="Fizika")

        cls.plan = EducationPlan.objects.create(
            specialty=cls.specialty,
            academic_year=cls.academic_year,
            education_form='kunduzgi',
            course=1,
        )


# =============================================================================
# ✅ EDUCATION PLAN TESTLARI
# =============================================================================
class EducationPlanModelTest(EducationBaseSetup):
    def test_str_representation(self):
        result = str(self.plan)
        self.assertIn("Kompyuter injiniringi", result)
        self.assertIn("2024-2025", result)

    def test_unique_together(self):
        """Bir yo'nalish, bir yil, bir shakl, bir kurs uchun faqat bitta reja."""
        with self.assertRaises(Exception):
            EducationPlan.objects.create(
                specialty=self.specialty,
                academic_year=self.academic_year,
                education_form='kunduzgi',
                course=1,
            )

    def test_different_course_allowed(self):
        """Boshqa kurs uchun reja yaratilishi mumkin."""
        plan2 = EducationPlan.objects.create(
            specialty=self.specialty,
            academic_year=self.academic_year,
            education_form='kunduzgi',
            course=2,
        )
        self.assertIsNotNone(plan2.pk)

    def test_different_education_form_allowed(self):
        """Boshqa ta'lim shakli uchun reja yaratilishi mumkin."""
        plan_sirtqi = EducationPlan.objects.create(
            specialty=self.specialty,
            academic_year=self.academic_year,
            education_form='sirtqi',
            course=1,
        )
        self.assertIsNotNone(plan_sirtqi.pk)


# =============================================================================
# 📚 PLAN SUBJECT TESTLARI
# =============================================================================
class PlanSubjectModelTest(EducationBaseSetup):
    def test_str_representation(self):
        ps = PlanSubject.objects.create(
            education_plan=self.plan,
            subject=self.subject,
            semester=1,
            credit=4,
        )
        self.assertIn("Matematik analiz", str(ps))
        self.assertIn("1-semestr", str(ps))

    def test_unique_together(self):
        """Bir rejada, bir fan, bir semestrda takroriy yozuv bo'lmasligi kerak."""
        PlanSubject.objects.create(
            education_plan=self.plan,
            subject=self.subject,
            semester=1,
            credit=4,
        )
        with self.assertRaises(Exception):
            PlanSubject.objects.create(
                education_plan=self.plan,
                subject=self.subject,
                semester=1,
                credit=6,
            )

    def test_default_values(self):
        ps = PlanSubject.objects.create(
            education_plan=self.plan,
            subject=self.subject,
            semester=2,
        )
        self.assertEqual(ps.credit, 4)  # default
        self.assertEqual(ps.subject_type, 'majburiy')  # default
        self.assertEqual(ps.semester_time, 4)  # default

    def test_different_semester_allowed(self):
        """Bir xil fan lekin boshqa semestrda — ruxsat beriladi."""
        PlanSubject.objects.create(
            education_plan=self.plan,
            subject=self.subject,
            semester=1,
            credit=4,
        )
        ps2 = PlanSubject.objects.create(
            education_plan=self.plan,
            subject=self.subject,
            semester=2,
            credit=4,
        )
        self.assertIsNotNone(ps2.pk)


# =============================================================================
# 🏫 AUDITORIYA (ROOM) TESTLARI
# =============================================================================
class RoomModelTest(EducationBaseSetup):
    def test_str_representation(self):
        room = Room.objects.create(
            name="301",
            capacity=40,
            room_type='lecture',
        )
        self.assertIn("301", str(room))
        self.assertIn("40", str(room))

    def test_unique_name(self):
        Room.objects.create(name="202", capacity=30)
        with self.assertRaises(Exception):
            Room.objects.create(name="202", capacity=25)

    def test_default_values(self):
        room = Room.objects.create(name="101")
        self.assertEqual(room.capacity, 0)
        self.assertEqual(room.room_type, 'practice')
        self.assertTrue(room.is_active)


# =============================================================================
# 📚 WORKLOAD TESTLARI
# =============================================================================
class WorkloadModelTest(EducationBaseSetup):
    def test_str_representation(self):
        wl = Workload.objects.create(subject=self.subject)
        self.assertEqual(str(wl), "Matematik analiz")

    def test_calculate_total_hours_empty(self):
        """Guruh va reja tanlanmagan bo'lsa 0 qaytarishi kerak."""
        wl = Workload.objects.create(subject=self.subject)
        self.assertEqual(wl.calculate_total_hours(), 0)

    def test_calculate_total_hours_with_data(self):
        """Guruh va reja bor bo'lsa soatlar to'g'ri hisoblanishi kerak."""
        ps = PlanSubject.objects.create(
            education_plan=self.plan,
            subject=self.subject,
            semester=1,
            credit=4,
            lecture_hours=30,
            practice_hours=15,
            lab_hours=0,
            seminar_hours=0,
        )
        wl = Workload.objects.create(subject=self.subject)
        wl.plan_subjects.add(ps)
        wl.groups.add(self.group)

        total = wl.calculate_total_hours()
        # lecture_hours + practice_hours + lab + seminar = 30 + 15 + 0 + 0 = 45
        self.assertEqual(total, 45)


# =============================================================================
# 🏢 KICHIK GURUH TESTLARI
# =============================================================================
class SubGroupModelTest(EducationBaseSetup):
    def test_str_representation(self):
        sg = SubGroup.objects.create(group=self.group, name="1-yarim")
        self.assertIn("KI-21", str(sg))
        self.assertIn("1-yarim", str(sg))

    def test_unique_together(self):
        """Bir guruhda ikki xil bir nomdagi kichik guruh bo'lmasligi kerak."""
        SubGroup.objects.create(group=self.group, name="1-yarim")
        with self.assertRaises(Exception):
            SubGroup.objects.create(group=self.group, name="1-yarim")


# =============================================================================
# 📅 SESSIYA DAVRI TESTLARI
# =============================================================================
class SessionPeriodModelTest(EducationBaseSetup):
    def test_str_representation(self):
        sp = SessionPeriod.objects.create(
            academic_year=self.academic_year,
            semester='autumn',
            education_form='kunduzgi',
            course=1,
            start_date=datetime.date(2024, 9, 2),
            end_date=datetime.date(2024, 12, 25),
            weeks_count=15,
        )
        self.assertIn("15 hafta", str(sp))

    def test_start_after_end_validation(self):
        """Boshlanish sanasi tugash sanasidan keyin bo'lsa xato berishi kerak."""
        sp = SessionPeriod(
            academic_year=self.academic_year,
            semester='autumn',
            education_form='kunduzgi',
            course=1,
            start_date=datetime.date(2025, 1, 30),
            end_date=datetime.date(2024, 9, 1),  # Noto'g'ri!
            weeks_count=15,
        )
        with self.assertRaises(ValidationError):
            sp.clean()

    def test_unique_together(self):
        """Bir yil, bir mavsum, bir shakl, bir kurs uchun bitta davr."""
        SessionPeriod.objects.create(
            academic_year=self.academic_year,
            semester='autumn',
            education_form='kunduzgi',
            course=1,
            start_date=datetime.date(2024, 9, 2),
            end_date=datetime.date(2024, 12, 25),
            weeks_count=15,
        )
        with self.assertRaises(Exception):
            SessionPeriod.objects.create(
                academic_year=self.academic_year,
                semester='autumn',
                education_form='kunduzgi',
                course=1,  # Takroriy!
                start_date=datetime.date(2024, 9, 5),
                end_date=datetime.date(2024, 12, 20),
                weeks_count=14,
            )


# =============================================================================
# 🧠 SCHEDULE GENERATOR SERVICE TESTLARI
# =============================================================================
from django.contrib.auth import get_user_model
from kadrlar.models import (
    Department, Employee, Position, Teacher,
    Weekday, TimeSlot, TeacherAvailability,
)
from education.models import Stream, TimeTable
from education.services.generator import ScheduleGeneratorService
from students.models import Student

User = get_user_model()


class ScheduleGeneratorBaseSetup(TestCase):
    """Generator testlari uchun asosiy setup."""

    @classmethod
    def setUpTestData(cls):
        # Asosiy ma'lumotlar
        cls.specialty = Specialty.objects.create(name="Kompyuter injiniringi", code="60610")
        cls.specialty2 = Specialty.objects.create(name="Iqtisodiyot", code="60400")
        cls.academic_year = AcademicYear.objects.create(name="2024-2025", is_active=True)

        cls.group1 = Group.objects.create(name="KI-21", specialty=cls.specialty)
        cls.group2 = Group.objects.create(name="KI-22", specialty=cls.specialty)
        cls.group3 = Group.objects.create(name="IQ-21", specialty=cls.specialty2)

        cls.subject1 = Subject.objects.create(name="Matematik analiz")
        cls.subject2 = Subject.objects.create(name="Fizika")
        cls.subject3 = Subject.objects.create(name="Kimyo")

        # Hafta kunlari
        cls.mon = Weekday.objects.create(name="Dushanba", order=1)
        cls.tue = Weekday.objects.create(name="Seshanba", order=2)
        cls.wed = Weekday.objects.create(name="Chorshanba", order=3)
        cls.thu = Weekday.objects.create(name="Payshanba", order=4)
        cls.fri = Weekday.objects.create(name="Juma", order=5)
        cls.sat = Weekday.objects.create(name="Shanba", order=6)

        # Vaqt slotlari (6 para)
        cls.slot1 = TimeSlot.objects.create(index=1, start_time="08:00", end_time="09:30")
        cls.slot2 = TimeSlot.objects.create(index=2, start_time="09:40", end_time="11:10")
        cls.slot3 = TimeSlot.objects.create(index=3, start_time="11:20", end_time="12:50")
        cls.slot4 = TimeSlot.objects.create(index=4, start_time="13:30", end_time="15:00")
        cls.slot5 = TimeSlot.objects.create(index=5, start_time="15:10", end_time="16:40")
        cls.slot6 = TimeSlot.objects.create(index=6, start_time="16:50", end_time="18:20")

        # Xonalar
        cls.room_small = Room.objects.create(name="101", capacity=30, room_type='practice')
        cls.room_medium = Room.objects.create(name="201", capacity=60, room_type='practice')
        cls.room_large = Room.objects.create(name="301", capacity=120, room_type='lecture')
        cls.room_lab = Room.objects.create(name="Lab-1", capacity=25, room_type='lab')

        # Department
        cls.department = Department.objects.create(name="Informatika kafedrasi")

        # Xodimlar va O'qituvchilar
        cls.emp1 = Employee.objects.create(
            first_name="Ali", last_name="Valiyev", gender='male',
            passport_info="AA1111111", pid="11111111111111",
            department=cls.department, status='active',
        )
        cls.emp2 = Employee.objects.create(
            first_name="Vali", last_name="Aliyev", gender='male',
            passport_info="BB2222222", pid="22222222222222",
            department=cls.department, status='active',
        )

        cls.teacher1 = Teacher.objects.create(
            employee=cls.emp1, work_type_permanent=True
        )
        cls.teacher2 = Teacher.objects.create(
            employee=cls.emp2, work_type_permanent=True
        )

        # O'quv reja
        cls.plan = EducationPlan.objects.create(
            specialty=cls.specialty,
            academic_year=cls.academic_year,
            education_form='kunduzgi',
            course=1,
        )

        # PlanSubject
        cls.plan_subject1 = PlanSubject.objects.create(
            education_plan=cls.plan,
            subject=cls.subject1,
            semester=1,
            credit=4,
            lecture_hours=30,
            practice_hours=30,
            lab_hours=0,
            seminar_hours=0,
        )

        # Talabalar yaratish (student_count testi uchun)
        for i in range(25):
            Student.objects.create(
                full_name=f"Talaba {i+1}",
                student_hemis_id=f"HID-{i+1:04d}",
                gender='erkak',
                phone_number=f"+99890000{i+1:04d}",
                passport_series_number=f"AB{i+1:07d}",
                personal_pin=f"5{i+1:013d}",
                address="Test manzil",
                education_form='kunduzgi',
                group=cls.group1,
                status='active',
            )
        # group2 ga 15 ta talaba
        for i in range(15):
            Student.objects.create(
                full_name=f"Talaba G2-{i+1}",
                student_hemis_id=f"HID-G2-{i+1:04d}",
                gender='erkak',
                phone_number=f"+99891000{i+1:04d}",
                passport_series_number=f"CD{i+1:07d}",
                personal_pin=f"6{i+1:013d}",
                address="Test manzil 2",
                education_form='kunduzgi',
                group=cls.group2,
                status='active',
            )

        # SessionPeriod
        SessionPeriod.objects.create(
            academic_year=cls.academic_year,
            semester='autumn',
            education_form='kunduzgi',
            course=1,
            start_date=datetime.date(2024, 9, 2),
            end_date=datetime.date(2024, 12, 25),
            weeks_count=15,
        )

    def _create_workload_with_stream(self, subject, plan_subject, groups, teacher,
                                      lesson_type='lecture', employment_type='permanent'):
        """Yordamchi: Workload + Stream yaratish."""
        workload = Workload.objects.create(subject=subject)
        workload.plan_subjects.add(plan_subject)
        for g in groups:
            workload.groups.add(g)

        stream = Stream.objects.create(
            workload=workload,
            name=f"{subject.name} - {lesson_type}",
            teacher=teacher,
            employment_type=employment_type,
            lesson_type=lesson_type,
        )
        for g in groups:
            stream.groups.add(g)

        return workload, stream

    def _create_service(self):
        """Yangi generator service yaratish."""
        return ScheduleGeneratorService(
            year_id=self.academic_year.id,
            season='autumn',
            shift1_levels=[1, 4],
            shift2_levels=[2, 3],
            education_form='kunduzgi',
        )


class CalculatePairsTest(ScheduleGeneratorBaseSetup):
    """#7: calculate_pairs metodi testlari."""

    def test_basic_pair_calculation(self):
        """30 soat / 15 hafta / 2 = 1 para."""
        _, stream = self._create_workload_with_stream(
            self.subject1, self.plan_subject1, [self.group1],
            self.teacher1, 'lecture',
        )
        service = self._create_service()
        pairs = service.calculate_pairs(stream)
        self.assertEqual(pairs, 1)

    def test_practice_pair_calculation(self):
        """30 soat amaliyot / 15 hafta / 2 = 1 para."""
        _, stream = self._create_workload_with_stream(
            self.subject1, self.plan_subject1, [self.group1],
            self.teacher1, 'practice',
        )
        service = self._create_service()
        pairs = service.calculate_pairs(stream)
        self.assertEqual(pairs, 1)

    def test_zero_hours_returns_zero(self):
        """Lab soati 0 bo'lsa 0 para qaytishi kerak."""
        _, stream = self._create_workload_with_stream(
            self.subject1, self.plan_subject1, [self.group1],
            self.teacher1, 'lab',
        )
        service = self._create_service()
        pairs = service.calculate_pairs(stream)
        self.assertEqual(pairs, 0)


class StudentCountTest(ScheduleGeneratorBaseSetup):
    """#6: student_count to'g'ri hisoblash testlari."""

    def test_real_student_count_from_db(self):
        """DB dan haqiqiy aktiv talabalar soni olinishi kerak."""
        service = self._create_service()
        count = service.get_student_count([self.group1])
        self.assertEqual(count, 25)

    def test_multiple_groups_count(self):
        """Bir nechta guruh talabalarini to'g'ri qo'shishi kerak."""
        service = self._create_service()
        count = service.get_student_count([self.group1, self.group2])
        self.assertEqual(count, 40)  # 25 + 15

    def test_empty_group_returns_one(self):
        """Bo'sh guruh uchun 1 qaytishi kerak (division by zero oldini olish)."""
        service = self._create_service()
        count = service.get_student_count([self.group3])  # group3 da talaba yo'q
        self.assertEqual(count, 1)

    def test_caching(self):
        """Bir xil guruh uchun DB so'rovi takrorlanmasligi (kesh ishlashi)."""
        service = self._create_service()
        # Birinchi chaqiruv — DB dan oladi
        count1 = service.get_student_count([self.group1])
        # Ikkinchi chaqiruv — keshdan olishi kerak
        count2 = service.get_student_count([self.group1])
        self.assertEqual(count1, count2)
        self.assertIn(self.group1.id, service._student_count_cache)


class BestFitRoomTest(ScheduleGeneratorBaseSetup):
    """#5: Best-Fit xona tanlash testlari."""

    def test_selects_closest_capacity_room(self):
        """25 talaba uchun 30 o'rinli xona tanlashi kerak (120 emas)."""
        service = self._create_service()
        room = service._find_best_fit_room(
            self.mon.id, self.slot1.id, 25, ['practice']
        )
        self.assertEqual(room.id, self.room_small.id)  # 30 o'rinli

    def test_skips_small_rooms(self):
        """50 talaba uchun 30 o'rinli xona mos emas, 60 o'rinli tanlashi kerak."""
        service = self._create_service()
        room = service._find_best_fit_room(
            self.mon.id, self.slot1.id, 50, ['practice']
        )
        self.assertEqual(room.id, self.room_medium.id)  # 60 o'rinli

    def test_skips_wrong_type(self):
        """Lab dars uchun lecture xona tanlama, lab xonani tanlashi kerak."""
        service = self._create_service()
        room = service._find_best_fit_room(
            self.mon.id, self.slot1.id, 20, ['lab', 'computer']
        )
        self.assertEqual(room.id, self.room_lab.id)

    def test_skips_busy_room(self):
        """Band xonani tanlama, keyingisini tanlashi kerak."""
        service = self._create_service()
        # room_small ni band qilish
        service.matrix_room.add((self.mon.id, self.slot1.id, self.room_small.id))
        room = service._find_best_fit_room(
            self.mon.id, self.slot1.id, 25, ['practice']
        )
        self.assertEqual(room.id, self.room_medium.id)  # Keyingi mos xona

    def test_returns_none_if_no_room(self):
        """Mos xona topilmasa None qaytishi kerak."""
        service = self._create_service()
        room = service._find_best_fit_room(
            self.mon.id, self.slot1.id, 500, ['practice']  # 500 talaba — hech qaysi xona sig'maydi
        )
        self.assertIsNone(room)


class DayLoadBalancingTest(ScheduleGeneratorBaseSetup):
    """#2: Kun bo'yicha muvozanat testlari."""

    def test_sorted_days_empty_load(self):
        """Hech qanday yuk yo'q bo'lsa, barcha kunlar qaytishi kerak."""
        service = self._create_service()
        days = service._get_sorted_days_for_groups([self.group1.id], self.teacher1.id)
        self.assertEqual(len(days), 6)

    def test_sorted_days_prefers_less_loaded(self):
        """Yuklanishi kam bo'lgan kun birinchi bo'lishi kerak."""
        service = self._create_service()
        # Dushanbaga 3 ta dars yuklash
        service._day_load_group[(self.mon.id, self.group1.id)] = 3
        service._day_load_teacher[(self.mon.id, self.teacher1.id)] = 3

        days = service._get_sorted_days_for_groups([self.group1.id], self.teacher1.id)
        # Dushanba eng oxirida bo'lishi kerak (eng ko'p yukli)
        self.assertNotEqual(days[0].id, self.mon.id)
        self.assertEqual(days[-1].id, self.mon.id)


class GapPenaltyTest(ScheduleGeneratorBaseSetup):
    """#3: 'Oyna' darslar jarimasi testlari."""

    def test_no_gap_penalty_for_empty(self):
        """Hech qanday dars yo'q bo'lsa, penalty 0 yoki slot indeksi."""
        service = self._create_service()
        penalty = service._calculate_gap_penalty(
            self.mon.id, self.slot1, [self.group1.id]
        )
        # Bo'sh bo'lganda slot_index qaytadi (slot1 = index 0)
        self.assertEqual(penalty, 0)

    def test_consecutive_no_gap(self):
        """Ketma-ket darslar uchun gap penalty 0 bo'lishi kerak."""
        service = self._create_service()
        # slot1 band (index 0)
        service.matrix_group.add((self.mon.id, self.slot1.id, self.group1.id))
        # slot2 ni qo'shsak (index 1) — ketma-ket, gap yo'q
        penalty = service._calculate_gap_penalty(
            self.mon.id, self.slot2, [self.group1.id]
        )
        self.assertEqual(penalty, 0)

    def test_gap_has_penalty(self):
        """Oraliqda bo'shliq bo'lsa penalty > 0."""
        service = self._create_service()
        # slot1 band (index 0)
        service.matrix_group.add((self.mon.id, self.slot1.id, self.group1.id))
        # slot3 ni qo'shsak (index 2) — slot2 bo'sh, 1 gap
        penalty = service._calculate_gap_penalty(
            self.mon.id, self.slot3, [self.group1.id]
        )
        self.assertGreater(penalty, 0)


class TeacherDailyLimitTest(ScheduleGeneratorBaseSetup):
    """#4: O'qituvchi kunlik limiti testlari."""

    def test_teacher_limit_respected(self):
        """O'qituvchi kuniga max N paradan ko'p dars olmaydi."""
        service = self._create_service()
        service.MAX_PAIRS_PER_DAY_TEACHER = 2  # Test uchun 2 para limit

        # Workload + Stream yaratish
        _, stream = self._create_workload_with_stream(
            self.subject1, self.plan_subject1, [self.group1],
            self.teacher1, 'lecture',
        )

        # Dushanba uchun teacher1 ga 2 ta dars yuklaymiz
        service._day_load_teacher[(self.mon.id, self.teacher1.id)] = 2

        # find_best_slot Dushanbani o'tkazib yuborishi kerak
        allocated, reasons = service.find_best_slot(
            stream, [self.group1], 1, 25
        )

        if allocated:
            # Birinchi joylashgan kun Dushanba bo'lmasligi kerak
            self.assertNotEqual(allocated[0]['weekday'].id, self.mon.id)


class CrossFormConflictTest(ScheduleGeneratorBaseSetup):
    """Cross-form konflikt testlari."""

    def test_loads_other_form_conflicts(self):
        """Boshqa ta'lim shakli bandligi yuklanishi kerak."""
        # Sirtqi jadvalda teacher1 Dushanba 1-para da band
        TimeTable.objects.create(
            academic_year=self.academic_year,
            semester='autumn',
            education_form='sirtqi',
            weekday=self.mon,
            timeslot=self.slot1,
            subject=self.subject1,
            teacher=self.teacher1,
            group=self.group1,
        )

        # Kunduzgi generator yaratamiz — sirtqi jadvaldan konflikt yuklanishi kerak
        service = self._create_service()
        self.assertIn(
            (self.mon.id, self.slot1.id, self.teacher1.id),
            service.matrix_teacher
        )


class FullGenerationTest(ScheduleGeneratorBaseSetup):
    """To'liq generatsiya integratsiya testlari."""

    def test_simple_generation(self):
        """Oddiy bitta stream generatsiyasi muvaffaqiyatli bo'lishi kerak."""
        _, stream = self._create_workload_with_stream(
            self.subject1, self.plan_subject1, [self.group1],
            self.teacher1, 'lecture',
        )

        service = self._create_service()
        schedule, errors = service.generate(dry_run=True)

        self.assertGreater(len(schedule), 0)

    def test_stats_populated(self):
        """#9: Generatsiyadan keyin statistika to'ldirilishi kerak."""
        _, stream = self._create_workload_with_stream(
            self.subject1, self.plan_subject1, [self.group1],
            self.teacher1, 'lecture',
        )

        service = self._create_service()
        service.generate(dry_run=True)
        stats = service.get_stats_summary()

        self.assertGreater(stats['total_streams'], 0)
        self.assertIn('success_percent', stats)
        self.assertIn('backtrack_attempts', stats)

    def test_configurable_parameters(self):
        """#7: Klass parametrlari o'zgartirilishi mumkin."""
        service = self._create_service()
        self.assertEqual(service.HOURS_PER_PAIR, 2)
        self.assertEqual(service.MAX_PAIRS_PER_DAY_TEACHER, 4)
        self.assertEqual(service.MAX_BACKTRACK_ATTEMPTS, 3)

        # O'zgartirsak ham ishlashi kerak
        service.MAX_PAIRS_PER_DAY_TEACHER = 6
        self.assertEqual(service.MAX_PAIRS_PER_DAY_TEACHER, 6)

