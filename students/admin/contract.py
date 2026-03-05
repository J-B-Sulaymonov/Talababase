from .base import *


# =============================================================================
# 📄 SHARTNOMA ADMIN (ContractResource + ContractAdmin + Widgetlar)
# =============================================================================

class CustomForeignKeyWidget(ForeignKeyWidget):
    def clean(self, value, row=None, **kwargs):
        if not value:
            return None
        val = str(value).strip()
        try:
            return super().clean(val, row, **kwargs)
        except ObjectDoesNotExist:
            raise ValueError(f"Bazada '{val}' IDli {self.model._meta.verbose_name} topilmadi!")


class GrantTypeWidget(Widget):
    def clean(self, value, row=None, *args, **kwargs):
        """
        Exceldagi matnni Contract.GrantTypeChoices kodiga o'giradi.
        """
        if not value:
            return Contract.GrantTypeChoices.NONE

        # 1. Matnni tozalash (probellarni olib tashlash va kichik harfga o'tkazish)
        val = str(value).strip().lower()

        # Qo'shtirnoqlarni standartlashtirish (Word/Excelda har xil bo'lishi mumkin)
        val = val.replace("\u2018", "'").replace("\u2019", "'").replace("`", "'").replace('"', '')

        # 2. Bazadagi variantlarni tekshirish
        for code, label in Contract.GrantTypeChoices.choices:
            # Labelni ham tozalab olamiz
            clean_label = label.lower().replace("\u2018", "'").replace("\u2019", "'").replace("`", "'").replace('"', '')
            clean_code = code.lower()

            # A) Agar kodning o'zi yozilgan bo'lsa (masalan: "CR")
            if clean_code == val:
                return code

            # B) Agar to'liq nomi yozilgan bo'lsa
            if clean_label == val:
                return code

            # C) Qisman moslik (Eng muhim qismi):
            # Agar kod Exceldagi matn ichida bo'lsa (va kod 'none' bo'lmasa)
            # Masalan: "Rag'batlantirish-CR" ichida "cr" bor.
            if clean_code != 'none' and clean_code in val:
                return code

            # D) Agar nomining asosiy qismi mos kelsa
            if len(val) > 3 and val in clean_label:
                return code

        # Agar hech narsa topilmasa
        return Contract.GrantTypeChoices.NONE


# =========================================================
# 2. RESOURCE (Import/Export sozlamalari)
# =========================================================
class ContractResource(resources.ModelResource):
    # --- 1. ID va Bog'lanishlar ---
    id = fields.Field(column_name='id', attribute='id')

    student = fields.Field(
        column_name='student',
        attribute='student',
        widget=CustomForeignKeyWidget(Student, 'student_hemis_id')
    )

    academic_year = fields.Field(
        column_name='academic_year',
        attribute='academic_year',
        widget=CustomForeignKeyWidget(AcademicYear, 'name')
    )

    # --- 2. Asosiy summalar ---
    amount = fields.Field(
        column_name='amount',
        attribute='amount',
        widget=NumberWidget()
    )

    contract_date = fields.Field(
        column_name='contract_date',
        attribute='contract_date',
        widget=DateWidget(format='%d.%m.%Y')
    )

    # --- 3. Grant turlari (Import uchun) ---
    grant_type = fields.Field(
        column_name='Grant turi',
        attribute='grant_type',
        widget=GrantTypeWidget()
    )

    # --- 4. YANGI QO'SHILGAN MAYDONLAR (EXPORT UCHUN) ---

    # Kurs
    student_course = fields.Field(
        column_name='Kurs',
        attribute='student__course_year',
        readonly=True
    )

    # Ta'lim shakli (Chiroyli nomini oladi)
    student_education_form = fields.Field(
        column_name="Ta'lim shakli",
        attribute='student__get_education_form_display',
        readonly=True
    )

    # Yo'nalish (Dehydrate orqali olinadi)
    student_specialty = fields.Field(
        column_name="Yo'nalish",
        readonly=True
    )

    # Grant turi (Display - Chiroyli nomi)
    grant_type_display = fields.Field(
        column_name='Grant turi (Display)',
        attribute='get_grant_type_display',
        readonly=True
    )

    grant_date = fields.Field(
        column_name='Grant sanasi',
        attribute='grant_date',
        widget=DateWidget(format='%d.%m.%Y')
    )

    grant_percent = fields.Field(
        column_name='Grant foizi',
        attribute='grant_percent',
        widget=NumberWidget()
    )

    grant_amount = fields.Field(
        column_name='Grant summasi',
        attribute='grant_amount',
        widget=NumberWidget()
    )

    class Meta:
        model = Contract

        # --- MUHIM O'ZGARISH SHU YERDA ---
        # "fields" ro'yxatiga barcha yangi fieldlarni qo'shish SHART!
        # Aks holda "UserWarning: cannot identify field" xatosi chiqadi.
        fields = (
            'id',
            'student',
            'student_specialty',  # <--- Qo'shildi
            'student_education_form',  # <--- Qo'shildi
            'student_course',  # <--- Qo'shildi
            'academic_year',
            'contract_number',
            'contract_date',
            'amount',
            'grant_type',
            'grant_type_display',  # <--- Qo'shildi
            'grant_date',
            'grant_percent',
            'grant_amount',
        )

        # Export qilish ketma-ketligi
        export_order = (
            'id',
            'student',
            'student_specialty',
            'student_education_form',
            'student_course',
            'academic_year',
            'contract_number',
            'contract_date',
            'amount',
            'grant_type',
            'grant_type_display',
            'grant_date',
            'grant_percent',
            'grant_amount'
        )

        import_id_fields = ('id',)
        raise_errors = False
        skip_unchanged = True
        report_skipped = True

    # Yo'nalish nomini olish uchun metod (Xatolik chiqmasligi uchun)
    def dehydrate_student_specialty(self, contract):
        try:
            if contract.student and contract.student.group and contract.student.group.specialty:
                return contract.student.group.specialty.name
        except Exception:
            return ""
        return ""

    def get_instance(self, instance_loader, row):
        row_id = row.get('id')
        if row_id:
            try:
                return Contract.objects.get(id=row_id)
            except Contract.DoesNotExist:
                pass
        return None


# =========================================================
# 3. ADMIN REGISTRATION
# =========================================================
@admin.register(Contract)
class ContractAdmin(ImportExportModelAdmin):
    resource_class = ContractResource
    form = ContractForm  # Agar sizda ContractForm bo'lsa

    list_display = (
        'student', 'id', 'academic_year', 'contract_number', 'contract_date', 'amount',
        'grant_type', 'grant_date', 'grant_percent',
    )
    list_filter = ('academic_year', 'grant_type')

    search_fields = (

        'contract_number',
        'student__full_name',
        'student__student_hemis_id',
        'student__passport_series_number',
        'student__personal_pin',
    )

    raw_id_fields = ['student']
    list_per_page = 500

    class Media:
        js = (
            'admin/js/jquery.init.js',
            'admin/js/money_input.js',
            'admin/js/contract_grant_standalone.js',
        )
