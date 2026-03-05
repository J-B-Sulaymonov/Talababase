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
