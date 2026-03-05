"""
students app uchun Unit va Integration testlari.
Testlar: Model, Serializer, API endpointlari.
"""
import datetime
from decimal import Decimal

from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from .models import (
    Country, Region, District,
    Specialty, Group, AcademicYear,
    OrderType, Order,
    Student, StudentHistory,
    Contract, Payment,
    Subject, SubjectDebt, PerevodRate, SubjectRate,
)
from .serializers import StudentSerializer, GroupSerializer


# =============================================================================
# 🔧 TEST UCHUN YORDAMCHI FUNKSIYA
# =============================================================================
class BaseTestSetup(TestCase):
    """Barcha testlar uchun umumiy ma'lumotlarni tayyorlash."""

    @classmethod
    def setUpTestData(cls):
        # Joylashuv
        cls.country = Country.objects.create(name="O'zbekiston")
        cls.region = Region.objects.create(name="Toshkent viloyati", country=cls.country)
        cls.district = District.objects.create(name="Chirchiq", region=cls.region)

        # Ta'lim
        cls.specialty = Specialty.objects.create(name="Kompyuter injiniringi", code="60610")
        cls.group = Group.objects.create(name="KI-21", specialty=cls.specialty)
        cls.academic_year = AcademicYear.objects.create(name="2024-2025", is_active=True)

        # Buyruq
        cls.order_type = OrderType.objects.create(name="Qabul buyrug'i")

        # Talaba
        cls.student = Student.objects.create(
            full_name="Aliyev Jasur Kamoliddin o'g'li",
            student_hemis_id="H12345",
            course_year=2,
            group=cls.group,
            education_type='contract',
            gender='male',
            phone_number='+998901234567',
            passport_series_number='AB1234567',
            personal_pin='12345678901234',
            passport_issued_by='Toshkent IIB',
            status='active',
            education_form='kunduzgi',
            address='Toshkent shahar',
        )

        # Fan
        cls.subject = Subject.objects.create(name="Matematik analiz")


# =============================================================================
# ✅ MODEL TESTLARI
# =============================================================================
class CountryModelTest(BaseTestSetup):
    def test_str_representation(self):
        self.assertEqual(str(self.country), "O'zbekiston")

    def test_unique_name(self):
        with self.assertRaises(Exception):
            Country.objects.create(name="O'zbekiston")


class RegionModelTest(BaseTestSetup):
    def test_str_representation(self):
        self.assertEqual(str(self.region), "Toshkent viloyati")

    def test_unique_together(self):
        """Bir davlatda ikki xil bir nomdagi viloyat bo'lmasligi kerak."""
        with self.assertRaises(Exception):
            Region.objects.create(name="Toshkent viloyati", country=self.country)


class DistrictModelTest(BaseTestSetup):
    def test_str_representation(self):
        self.assertEqual(str(self.district), "Chirchiq")


class SpecialtyModelTest(BaseTestSetup):
    def test_str_representation(self):
        self.assertEqual(str(self.specialty), "Kompyuter injiniringi")


class GroupModelTest(BaseTestSetup):
    def test_str_includes_specialty(self):
        self.assertIn("KI-21", str(self.group))
        self.assertIn("Kompyuter injiniringi", str(self.group))


class AcademicYearModelTest(BaseTestSetup):
    def test_str_representation(self):
        self.assertEqual(str(self.academic_year), "2024-2025")

    def test_is_active_default_false(self):
        year = AcademicYear.objects.create(name="2023-2024")
        self.assertFalse(year.is_active)


class StudentModelTest(BaseTestSetup):
    def test_str_representation(self):
        self.assertEqual(str(self.student), "Aliyev Jasur Kamoliddin o'g'li")

    def test_default_status_active(self):
        self.assertEqual(self.student.status, 'active')

    def test_unique_passport(self):
        """Passport raqami takrorlanmasligi kerak."""
        with self.assertRaises(Exception):
            Student.objects.create(
                full_name="Boshqa Talaba",
                passport_series_number='AB1234567',  # Yana shu
                personal_pin='99999999999999',
                passport_issued_by='Test',
                phone_number='+998999999999',
                gender='male',
                education_form='kunduzgi',
                address='Test',
            )

    def test_unique_personal_pin(self):
        """JShShIR takrorlanmasligi kerak."""
        with self.assertRaises(Exception):
            Student.objects.create(
                full_name="Boshqa Talaba",
                passport_series_number='XY9876543',
                personal_pin='12345678901234',  # Yana shu
                passport_issued_by='Test',
                phone_number='+998999999999',
                gender='male',
                education_form='kunduzgi',
                address='Test',
            )


class OrderModelTest(BaseTestSetup):
    def test_str_representation(self):
        order = Order.objects.create(
            student=self.student,
            order_type=self.order_type,
            order_number="B-001",
            order_date=datetime.date(2024, 9, 1),
        )
        self.assertIn("Qabul buyrug'i", str(order))
        self.assertIn("Aliyev", str(order))


class StudentHistoryModelTest(BaseTestSetup):
    def test_unique_together(self):
        """Bir o'quv yilida bitta talaba uchun faqat bitta tarix bo'lishi kerak."""
        StudentHistory.objects.create(
            student=self.student,
            academic_year=self.academic_year,
            group=self.group,
            course_year=2,
            education_form='kunduzgi',
        )
        with self.assertRaises(Exception):
            StudentHistory.objects.create(
                student=self.student,
                academic_year=self.academic_year,
                group=self.group,
                course_year=2,
                education_form='kunduzgi',
            )


# =============================================================================
# 💰 KONTRAKT VA TO'LOV TESTLARI
# =============================================================================
class ContractModelTest(BaseTestSetup):
    def test_str_representation(self):
        contract = Contract.objects.create(
            student=self.student,
            academic_year=self.academic_year,
            contract_number="SH-001",
            amount=Decimal('15000000.00'),
        )
        self.assertIn("SH-001", str(contract))
        self.assertIn("Aliyev", str(contract))

    def test_grant_conflict_validation(self):
        """QH va QB grantlaridan faqat bittasini olishi mumkin."""
        Contract.objects.create(
            student=self.student,
            academic_year=self.academic_year,
            contract_number="SH-001",
            amount=Decimal('15000000.00'),
            grant_type='QH',  # Qurbon Hayiti
        )
        with self.assertRaises(Exception):
            Contract.objects.create(
                student=self.student,
                academic_year=self.academic_year,
                contract_number="SH-002",
                amount=Decimal('15000000.00'),
                grant_type='QB',  # Qabul — yangi entry, lekin QB, ruxsat yo'q
            )


class PaymentModelTest(BaseTestSetup):
    def test_str_representation(self):
        contract = Contract.objects.create(
            student=self.student,
            academic_year=self.academic_year,
            contract_number="SH-001",
            amount=Decimal('15000000.00'),
        )
        payment = Payment.objects.create(
            contract=contract,
            amount=Decimal('5000000.00'),
        )
        self.assertIn("Aliyev", str(payment))
        self.assertIn("5000000", str(payment))


# =============================================================================
# 📚 FAN QARZDORLIGI TESTLARI
# =============================================================================
class SubjectDebtModelTest(BaseTestSetup):
    def test_perevod_debt_amount_calculation(self):
        """Perevod qarzdorligida summa = rate.amount * fan_credit."""
        PerevodRate.objects.create(year=self.academic_year, amount=Decimal('500000.00'))
        debt = SubjectDebt(
            student=self.student,
            subject=self.subject,
            academic_year=self.academic_year,
            semester=1,
            credit=4,
            year_credit=60,
            debt_type='perevod',
        )
        debt.save()
        # 500000 * 4 = 2000000
        self.assertEqual(debt.amount, Decimal('2000000'))

    def test_du_debt_with_subject_rate(self):
        """DU qarzdorligida summa = (SubjectRate / yil_credit) * fan_credit."""
        SubjectRate.objects.create(
            year=self.academic_year,
            specialty=self.specialty,
            education_form='kunduzgi',
            amount=Decimal('15000000.00'),
        )
        debt = SubjectDebt(
            student=self.student,
            subject=self.subject,
            academic_year=self.academic_year,
            semester=1,
            credit=4,
            year_credit=60,
            debt_type='du',
        )
        debt.save()
        # (15000000 / 60) * 4 = 1000000
        self.assertEqual(debt.amount, Decimal('1000000'))

    def test_default_status_in_progress(self):
        """Standart holat 'jarayonda' bo'lishi kerak."""
        debt = SubjectDebt.objects.create(
            student=self.student,
            subject=self.subject,
            academic_year=self.academic_year,
            semester=1,
            credit=0,
            debt_type='du',
        )
        self.assertEqual(debt.status, 'jarayonda')


# =============================================================================
# 🌐 SERIALIZER TESTLARI
# =============================================================================
class GroupSerializerTest(BaseTestSetup):
    def test_fields(self):
        serializer = GroupSerializer(self.group)
        data = serializer.data
        self.assertEqual(set(data.keys()), {'id', 'name', 'specialty'})
        self.assertEqual(data['name'], 'KI-21')
        self.assertEqual(data['specialty'], str(self.specialty))


class StudentSerializerTest(BaseTestSetup):
    def test_fields(self):
        serializer = StudentSerializer(self.student)
        data = serializer.data
        expected_fields = {
            'id', 'full_name', 'student_hemis_id', 'status',
            'gender', 'passport_series_number', 'group',
            'course_year', 'payment_percent',
        }
        self.assertEqual(set(data.keys()), expected_fields)

    def test_payment_percent_no_contract(self):
        """Shartnoma yo'q bo'lsa 0 qaytarishi kerak."""
        serializer = StudentSerializer(self.student)
        self.assertEqual(serializer.data['payment_percent'], 0)

    def test_payment_percent_with_payments(self):
        """To'lov bo'lsa foiz to'g'ri hisoblanishi kerak."""
        contract = Contract.objects.create(
            student=self.student,
            academic_year=self.academic_year,
            contract_number="SH-001",
            amount=Decimal('10000000.00'),
            grant_amount=Decimal('0.00'),
        )
        Payment.objects.create(contract=contract, amount=Decimal('5000000.00'))

        serializer = StudentSerializer(self.student)
        # 5000000 / 10000000 * 100 = 50.0%
        self.assertEqual(serializer.data['payment_percent'], 50.0)

    def test_payment_percent_with_grant(self):
        """Grant bor bo'lsa, net summa bo'yicha hisoblash kerak."""
        contract = Contract.objects.create(
            student=self.student,
            academic_year=self.academic_year,
            contract_number="SH-002",
            amount=Decimal('10000000.00'),
            grant_amount=Decimal('2500000.00'),  # 25% grant
        )
        Payment.objects.create(contract=contract, amount=Decimal('3750000.00'))

        serializer = StudentSerializer(self.student)
        # net = 10000000 - 2500000 = 7500000
        # 3750000 / 7500000 * 100 = 50.0%
        self.assertEqual(serializer.data['payment_percent'], 50.0)


# =============================================================================
# 🌐 API ENDPOINT TESTLARI
# =============================================================================
class StudentAPITest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser', password='testpass123')
        cls.specialty = Specialty.objects.create(name="Kompyuter injiniringi")
        cls.group = Group.objects.create(name="KI-21", specialty=cls.specialty)
        cls.student = Student.objects.create(
            full_name="Test Talaba",
            student_hemis_id="TEST001",
            course_year=1,
            group=cls.group,
            education_type='contract',
            gender='male',
            phone_number='+998901111111',
            passport_series_number='TT1234567',
            personal_pin='11111111111111',
            passport_issued_by='Test IIB',
            status='active',
            education_form='kunduzgi',
            address='Test manzil',
        )

    def setUp(self):
        self.client = APIClient()

    def test_student_list_requires_auth(self):
        """Autentifikatsiyasiz 401/403 qaytishi kerak."""
        response = self.client.get('/api/students/')
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_student_list_authenticated(self):
        """Autentifikatsiya bilan ro'yxat qaytarishi kerak."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/students/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Pagination qo'shilgani uchun results ichida bo'ladi
        self.assertIn('results', response.data)
        self.assertEqual(len(response.data['results']), 1)

    def test_student_list_pagination(self):
        """Pagination ishlashi kerak (count, next, previous)."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/students/')
        self.assertIn('count', response.data)
        self.assertIn('next', response.data)
        self.assertIn('previous', response.data)

    def test_student_detail_authenticated(self):
        """Bitta talaba ma'lumotlarini olish."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(f'/api/students/{self.student.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['full_name'], "Test Talaba")

    def test_student_detail_not_found(self):
        """Mavjud bo'lmagan ID uchun 404."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/students/99999/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class GroupAPITest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='testuser2', password='testpass123')
        cls.specialty = Specialty.objects.create(name="Iqtisodiyot")
        cls.group = Group.objects.create(name="IQ-22", specialty=cls.specialty)

    def setUp(self):
        self.client = APIClient()

    def test_group_list_requires_auth(self):
        response = self.client.get('/api/groups/')
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_group_list_authenticated(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/groups/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], 'IQ-22')

    def test_group_detail(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(f'/api/groups/{self.group.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'IQ-22')
