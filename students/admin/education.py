from .base import *

# (O'zgarishsiz qoldirildi)
# =============================================================================
class SpecialtyResource(resources.ModelResource):
    class Meta:
        model = Specialty


@admin.register(Specialty)
class SpecialtyAdmin(ImportExportModelAdmin):
    resource_class = SpecialtyResource
    list_display = ('name', 'code', 'id')
    search_fields = ('name', 'code')


class GroupResource(resources.ModelResource):
    specialty = fields.Field(
        column_name="Yo'nalishi",
        attribute='specialty__name'
    )

    # YANGI USTUNLAR
    group_course = fields.Field(
        column_name="Kursi",
        readonly=True
    )

    education_form = fields.Field(
        column_name="Ta'lim shakli",
        readonly=True
    )

    total_students = fields.Field(
        column_name="Jami talabalar soni",
        readonly=True
    )

    filtered_students_count = fields.Field(
        column_name="Filtr bo'yicha talabalar soni",
        readonly=True
    )

    class Meta:
        model = Group
        # Excelda chiqadigan barcha ustunlar ro'yxati
        fields = ('id', 'name', 'specialty', 'group_course', 'education_form', 'total_students',
                  'filtered_students_count')
        export_order = ('id', 'name', 'specialty', 'group_course', 'education_form', 'total_students',
                        'filtered_students_count')

    # MA'LUMOTLARNI OLISH LOGIKASI
    def dehydrate_group_course(self, group):
        """Guruhdagi birinchi talaba kursini oladi"""
        student = group.student_set.first()
        return f"{student.course_year}-kurs" if student else "-"

    def dehydrate_education_form(self, group):
        """Guruhdagi birinchi talaba ta'lim shaklini oladi"""
        student = group.student_set.first()
        return student.get_education_form_display() if student else "-"

    def dehydrate_total_students(self, group):
        return group.student_set.count()

    def dehydrate_filtered_students_count(self, group):
        return getattr(group, 'student_count', 0)


