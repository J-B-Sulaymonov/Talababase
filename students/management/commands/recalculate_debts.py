from django.core.management.base import BaseCommand
from django.db import transaction
# DIQQAT: 'sizning_app' o'rniga o'z ilovangiz nomini yozing
from students.models import SubjectDebt
import time


class Command(BaseCommand):
    help = "Barcha talabalar uchun qarzdorlik summasini (amount) qayta hisoblash"

    def handle(self, *args, **options):
        self.stdout.write("Qayta hisoblash jarayoni boshlandi...")
        start_time = time.time()

        # Ma'lumotlarni bazadan olish.
        # select_related - bog'langan ma'lumotlarni bitta so'rovda olib kelish uchun (tezlikni oshiradi)
        debts = SubjectDebt.objects.select_related(
            'student',
            'student__group',
            'student__group__specialty',
            'academic_year',
            'subject'
        ).all()

        total = debts.count()
        updated_count = 0
        error_count = 0

        self.stdout.write(f"Jami {total} ta yozuv topildi.")

        # Tranzaksiya xavfsizligi uchun (agar xatolik bo'lsa, bazani buzmaslik uchun)
        with transaction.atomic():
            for index, debt in enumerate(debts, start=1):
                try:
                    # Modelning save() metodini chaqiramiz.
                    # Bu siz yozgan mantiq bo'yicha 'amount'ni qayta hisoblaydi.
                    debt.save()
                    updated_count += 1

                    # Har 100 ta yozuvda ekranga chiqarish
                    if index % 100 == 0:
                        self.stdout.write(f"{index}/{total} qayta hisoblandi...")

                except Exception as e:
                    error_count += 1
                    self.stdout.write(self.style.ERROR(f"Xatolik (ID: {debt.id}): {str(e)}"))

        end_time = time.time()
        duration = round(end_time - start_time, 2)

        self.stdout.write(self.style.SUCCESS('----------------------------------'))
        self.stdout.write(self.style.SUCCESS(f"Muvaffaqiyatli yakunlandi!"))
        self.stdout.write(f"Jami yangilandi: {updated_count}")
        self.stdout.write(self.style.ERROR(f"Xatoliklar: {error_count}") if error_count > 0 else "Xatoliklar: 0")
        self.stdout.write(f"Ketgan vaqt: {duration} soniya")