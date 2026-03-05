from .base import *


# =============================================================================
# 📚 QO'SHIMCHA MODELLAR (Ma'lumotnomalar)
# =============================================================================
class OrderTypeResource(resources.ModelResource):
    class Meta:
        model = OrderType


@admin.register(OrderType)
class OrderTypeAdmin(ImportExportModelAdmin):
    resource_class = OrderTypeResource
    list_display = ('name', 'id')
    search_fields = ('name',)


class MultiFormatDateWidget(DateWidget):
    def __init__(self, input_formats=None, render_format='%Y-%m-%d'):
        super().__init__(format=render_format)
        self.input_formats = input_formats or [
            '%d.%m.%Y',
            '%Y-%m-%d',
            '%Y-%m-%d %H:%M:%S',
        ]

    def clean(self, value, row=None, **kwargs):
        if value in (None, '', 'None'):
            return None
        v = str(value).strip()
        for fmt in self.input_formats:
            try:
                return datetime.strptime(v, fmt).date()
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(v.replace('Z', '')).date()
        except Exception:
            raise ValueError(f"Sana formati noto'g'ri: {v}")


# admin.py faylida OrderResource klassini to'liq shunday o'zgartiring:

class OrderResource(resources.ModelResource):
    # 1. Talabani HEMIS ID orqali topish
    student = fields.Field(
        column_name='student',
        attribute='student',
        widget=ForeignKeyWidget(Student, 'student_hemis_id')
    )

    # 2. Buyruq turini ID orqali topish (masalan, 1 - Qabul buyrug'i)
    order_type = fields.Field(
        column_name='order_type',
        attribute='order_type',
        widget=ForeignKeyWidget(OrderType, 'id')
    )

    # 3. Sanani to'g'ri o'qish (16.10.2025 formati uchun)
    order_date = fields.Field(
        column_name='order_date',
        attribute='order_date',
        widget=MultiFormatDateWidget()
    )

    # 4. Boshqa sanalar (agar Excelda bo'lsa, bo'lmasa shart emas)
    application_date = fields.Field(
        column_name='application_date',
        attribute='application_date',
        widget=MultiFormatDateWidget()
    )
    document_taken_date = fields.Field(
        column_name='document_taken_date',
        attribute='document_taken_date',
        widget=MultiFormatDateWidget()
    )

    class Meta:
        model = Order

        # --- ENG MUHIM QISM SHU YERDA ---
        # Tizim qatorni yangilash yoki yaratishni shu ikki maydon orqali aniqlaydi.
        # Ma'nosi: "Agar shu TALABAda shu TURDAGI buyruq (masalan, 1-turi) allaqachon bo'lsa -> UPDATE qil".
        # Agar bu ikkisi topilmasa -> CREATE qil.
        import_id_fields = ('student', 'order_type')

        fields = (
            'student',
            'order_type',
            'order_number',
            'order_date',
            'application_date',
            'document_taken_date',
            'notes',
            'tsch_reason'
        )

        skip_unchanged = True
        report_skipped = True


@admin.register(Order)
class OrderAdmin(ImportExportMixin, admin.ModelAdmin):
    resource_class = OrderResource
    list_display = ('order_date', 'order_type', 'order_number', 'student')
    list_filter = ('order_type', 'order_date')
    date_hierarchy = 'order_date'
    ordering = ('-order_date',)
    list_select_related = ('student', 'order_type')
    autocomplete_fields = ('student', 'order_type')
    search_fields = (
        'order_number',
        'student__full_name',
        'student__student_hemis_id',
    )



class AcademicYearResource(resources.ModelResource):
    class Meta:
        model = AcademicYear


@admin.register(AcademicYear)
class AcademicYearAdmin(ImportExportModelAdmin):
    resource_class = AcademicYearResource
    list_display = ('name', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)


class SubjectResource(resources.ModelResource):
    class Meta:
        model = Subject


@admin.register(Subject)
class SubjectAdmin(ImportExportModelAdmin):
    resource_class = SubjectResource
    list_display = ('name',)
    search_fields = ('name',)



class SubjectRateResource(resources.ModelResource):
    class Meta:
        model = SubjectRate
        # education_form ni import/exportga qo'shamiz
        fields = ('id', 'year', 'specialty', 'education_form', 'amount')

@admin.register(SubjectRate)
class SubjectRateAdmin(ImportExportModelAdmin):
    resource_class = SubjectRateResource
    form = SubjectRateForm
    list_display = ('year', 'specialty', 'education_form', 'get_amount_display')
    list_filter = ('year', 'education_form', 'specialty')            # Filterga ham qo'shildi
    search_fields = ('specialty__name', 'year__name')
    autocomplete_fields = ['year', 'specialty']
    @admin.display(description="Kontrakt narxi", ordering='amount')
    def get_amount_display(self, obj):
        # Agar summa bor bo'lsa, uni formatlaymiz
        if obj.amount:
            # 24000000 -> 24,000,000 -> 24 000 000
            return f"{obj.amount:,.0f}".replace(",", " ")
        return "0"

    class Media:
        js = (
            'admin/js/jquery.init.js',
            'admin/js/money_input.js',
        )

class PerevodRateResource(resources.ModelResource):
    class Meta:
        model = PerevodRate


@admin.register(PerevodRate)
class PerevodRateAdmin(ImportExportModelAdmin):
    resource_class = PerevodRateResource
    form = PerevodRateForm
    list_display = ('year','get_amount_display')
    search_fields = ('year__name',)
    autocomplete_fields = ['year']

    @admin.display(description="Kontrakt narxi", ordering='amount')
    def get_amount_display(self, obj):
        # Agar summa bor bo'lsa, uni formatlaymiz
        if obj.amount:
            # 24000000 -> 24,000,000 -> 24 000 000
            return f"{obj.amount:,.0f}".replace(",", " ")
        return "0"

    class Media:
        js = (
            'admin/js/jquery.init.js',
            'admin/js/money_input.js',
        )
