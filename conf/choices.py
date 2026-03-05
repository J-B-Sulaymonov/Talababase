"""
Markazlashtirilgan choices'lar.
Barcha applar shu fayldan import qiladi — DRY prinsipi.
"""

from django.db import models


class EducationFormChoices(models.TextChoices):
    FULL_TIME = 'kunduzgi', "Kunduzgi"
    PART_TIME = 'sirtqi', "Sirtqi"
    EVENING = 'kechki', "Kechki"


class GenderChoices(models.TextChoices):
    MALE = 'erkak', "Erkak"
    FEMALE = 'ayol', "Ayol"


COURSE_CHOICES = [(i, f"{i}-kurs") for i in range(1, 6)]

SEMESTER_CHOICES = [(i, f"{i}-semestr") for i in range(1, 11)]
