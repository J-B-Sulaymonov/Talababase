from django.core.management.base import BaseCommand
from django.db import transaction
from students.models import Student, StudentHistory, AcademicYear


class Command(BaseCommand):
    help = 'Talabalar tarixini generatsiya qilish (Nomi bo\'yicha tartiblash)'

    def handle(self, *args, **kwargs):
        self.stdout.write("--- JARAYON BOSHLANDI ---")

        # 1. Yillarni NOMI bo'yicha teskari tartibda olamiz (Newest -> Oldest)
        # Masalan: 2024-2025, 2023-2024, 2022-2023...
        all_years = list(AcademicYear.objects.all().order_by('-name'))

        if not all_years:
            self.stdout.write(self.style.ERROR("XATO: Bazada hech qanday O'quv yili (AcademicYear) yo'q!"))
            return

        # LOG: Tartibni ko'rsatamiz, shunda to'g'riligini tekshira olasiz
        self.stdout.write(self.style.WARNING(f"Yillar tartibi (tekshiring): {[y.name for y in all_years]}"))

        # 2. Aktiv yilni tekshirish
        current_year = AcademicYear.objects.filter(is_active=True).first()
        if not current_year:
            self.stdout.write(self.style.ERROR("XATO: 'is_active=True' bo'lgan joriy o'quv yili topilmadi!"))
            return

        self.stdout.write(self.style.SUCCESS(f"Joriy o'quv yili (asos): {current_year.name}"))

        students = Student.objects.all()
        total_students = students.count()
        self.stdout.write(f"Jami talabalar soni: {total_students}")

        current_created_count = 0
        past_created_count = 0

        with transaction.atomic():
            for student in students:
                # A) JORIY YIL UCHUN YOZISH
                if student.course_year:
                    obj, created = StudentHistory.objects.get_or_create(
                        student=student,
                        academic_year=current_year,
                        defaults={
                            'group': student.group,
                            'course_year': student.course_year,
                            'semester': student.current_semester,
                            'education_form': student.education_form,
                            'status': student.status
                        }
                    )
                    if created:
                        current_created_count += 1

                # B) O'TMISHNI TIKLASH
                current_course = student.course_year

                if not current_course or current_course <= 1:
                    continue

                # Ro'yxatdan joriy yilni topamiz
                try:
                    idx = all_years.index(current_year)
                except ValueError:
                    self.stdout.write(self.style.ERROR(f"Xato: {current_year.name} ro'yxat ichidan topilmadi."))
                    continue

                # Joriy yildan KEYINGI turgan hamma yil — bu o'tmishdir
                # Chunki biz order_by('-name') qildik (Katta yildan kichik yilga qarab)
                previous_years = all_years[idx + 1:]

                temp_course = current_course
                for year in previous_years:
                    temp_course -= 1

                    # Agar kurs 1 dan kichik bo'lib ketsa, to'xtatamiz
                    if temp_course < 1:
                        break

                    obj, created = StudentHistory.objects.get_or_create(
                        student=student,
                        academic_year=year,
                        defaults={
                            'group': student.group,
                            'course_year': temp_course,
                            'semester': 1,
                            'education_form': student.education_form,
                            'status': 'active'
                        }
                    )
                    if created:
                        past_created_count += 1

        self.stdout.write("------------------------------------------------")
        self.stdout.write(
            self.style.SUCCESS(f"Joriy yil ({current_year.name}) uchun: {current_created_count} ta yozildi"))
        self.stdout.write(self.style.SUCCESS(f"O'tmish yillar uchun: {past_created_count} ta yozildi"))