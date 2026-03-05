from django.utils.translation import gettext_lazy as _
from .education import GroupResource
from .base import *
# =============================================================================
# 1. TALABALARNI GURUH ICHIDA KO'RSATISH UCHUN INLINE
# =============================================================================
class StudentInline(admin.TabularInline):
    model = Student
    fields = ('full_name', 'student_hemis_id', 'phone_number', 'status', 'contract_amount_display')
    readonly_fields = ('full_name', 'student_hemis_id', 'phone_number', 'status', 'contract_amount_display')
    can_delete = False
    extra = 0
    show_change_link = True  # Talabaning shaxsiy sahifasiga o'tish tugmasi
    verbose_name = "Guruh talabasi"
    verbose_name_plural = "Guruh talabalari"

    def contract_amount_display(self, obj):
        # Talabaning joriy yilgi shartnoma summasini ko'rsatish (ixtiyoriy)
        contract = obj.contract_set.last()  # Yoki active yil bo'yicha filter
        return f"{contract.amount:,.0f}" if contract else "-"

    contract_amount_display.short_description = "Shartnoma"


# =============================================================================
# 2. GURUH ADMINI (YANGILANGAN)
# =============================================================================
@admin.register(Group)
class GroupAdmin(ImportExportModelAdmin):
    resource_class = GroupResource
    list_display = ('name', 'specialty', 'get_student_count', 'view_students_link', 'id')

    list_filter = (
        'specialty',
        ('student__status', admin.ChoicesFieldListFilter),
        ('student__course_year', admin.ChoicesFieldListFilter),
        ('student__education_form', admin.ChoicesFieldListFilter),
    )
    search_fields = ('name',)

    def apply_student_count_annotation(self, queryset, request):
        """Filtrlar asosida dinamik hisoblash (Annotate)"""
        status_filter = request.GET.get('student__status__exact')
        course_filter = request.GET.get('student__course_year__exact')
        form_filter = request.GET.get('student__education_form__exact')

        count_filter = Q()
        if status_filter:
            count_filter &= Q(student__status=status_filter)
        if course_filter:
            count_filter &= Q(student__course_year=course_filter)
        if form_filter:
            count_filter &= Q(student__education_form=form_filter)

        return queryset.annotate(
            student_count=Count('student', filter=count_filter)
        )

    def get_queryset(self, request):
        """Admin paneli uchun"""
        qs = super().get_queryset(request)
        return self.apply_student_count_annotation(qs, request)

    def get_export_queryset(self, request):
        """Excel eksporti uchun"""
        qs = super().get_export_queryset(request)
        return self.apply_student_count_annotation(qs, request)

    @admin.display(description='Talabalar soni', ordering='student_count')
    def get_student_count(self, obj):
        return obj.student_count

    @admin.display(description="Ro'yxat")
    def view_students_link(self, obj):
        url = reverse('admin:students_student_changelist')
        return format_html(
            '<a class="button" style="background-color: #264b5d; color: white; padding: 5px 10px; border-radius: 4px;" '
            'href="{}?group__id__exact={}">Talabalarni ko\'rish</a>',
            url, obj.id
        )


# =============================================================================
# 🧩 TALABA ADMIN YORDAMCHI KLASSLAR
# (O'zgarishsiz qoldirildi)
# =============================================================================
class DatalistTextInput(forms.TextInput):
    def __init__(self, datalist, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._datalist = sorted(list(datalist))

    def render(self, name, value, attrs=None, renderer=None):
        if attrs is None:
            attrs = {}
        attrs['list'] = f'{name}_datalist'
        input_html = super().render(name, value, attrs)
        datalist_html = f'<datalist id="{attrs["list"]}">'
        for item in self._datalist:
            if item:
                datalist_html += f'<option value="{item}">'
        datalist_html += '</datalist>'
        return mark_safe(f'{input_html}{datalist_html}')


# =============================================================================
# 🧾 BUYRUQLAR INLINE FORM
# (O'zgarishsiz qoldirildi)
# =============================================================================
class OrderInlineForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        order_type = cleaned_data.get('order_type')

        if order_type and order_type.id == 2:
            tsch_reason = cleaned_data.get('tsch_reason')
            application_date = cleaned_data.get('application_date')
            document_taken_date = cleaned_data.get('document_taken_date')

            missing_fields = []
            if not tsch_reason:
                missing_fields.append("TSCH sababi")
            if not application_date:
                missing_fields.append("Ariza sanasi")
            if not document_taken_date:
                missing_fields.append("Hujjat olib ketilgan sanasi")

            if missing_fields:
                raise ValidationError(
                    f"Quyidagi maydonlarni to‘ldirish majburiy: {', '.join(missing_fields)}"
                )

        return cleaned_data


# =============================================================================
# 📑 INLINE MODELLAR
# (O'zgarishsiz qoldirildi)
# =============================================================================

class StudentHistoryInline(admin.TabularInline):
    model = StudentHistory
    extra = 1  # 1 ta bo'sh qator doim ko'rinib turadi (qo'shish oson bo'lishi uchun)

    fields = ('academic_year', 'group', 'course_year',  'education_form')


    ordering = ('-academic_year__name',)
    can_delete = True
    verbose_name = "O'quv yili tarixi"
    verbose_name_plural = "O'quv yillari bo'yicha tarixi"


class ContractInline(admin.StackedInline):
    model = Contract
    form = ContractForm
    extra = 0
    fields = (
        'academic_year', 'contract_type', 'contract_number', 'contract_date',
        'amount',
        'grant_type', 'grant_date', 'grant_percent',
        'grant_amount',
    )
    class Media:
        js = (
            'admin/js/contract_grant_auto_summ.js',
            )

    def save_model(self, request, obj, form, change):
        obj.save()


class OrderInline(admin.StackedInline):
    model = Order
    form = OrderInlineForm
    extra = 0
    fields = (
        'order_type', 'order_number', 'order_date',
        'application_date','tsch_by_whom',  'tsch_reason', 'notes', 'document_taken_date',
    )

    class Media:
        js = ('admin/js/order_inline_dynamic_fields.js',)




class SubjectDebtInline(admin.StackedInline):
    model = SubjectDebt
    form = SubjectDebtForm
    extra = 0
    readonly_fields = ['amount']
    raw_id_fields = ['subject']   # contractni ham qoldirish mumkin, lekin biz uni filterlaymiz
    fields = (
        'subject', 'academic_year', 'semester',
        'year_credit', 'credit', 'debt_type', 'amount',
        'contract', 'amount_summ', 'payment_date', 'status'
    )
    class Media:
        js = ('admin/js/disable_text_input_and_open_lookup.js',)

    def get_formset(self, request, obj=None, **kwargs):
        """
        obj = parent Student obyektidir (agar mavjud bo'lsa).
        Biz form klassining base_fields orqali 'contract' maydonining querysetini
        faqat shu studentga tegishlilarga limitlaymiz.
        """
        FormSet = super().get_formset(request, obj, **kwargs)

        # Agar obj mavjud bo'lsa (yani edit rejimida) -> kontraktlarni filterlaymiz
        try:
            if obj is not None:
                # form class ning maydonlarini o'zgartiramiz
                if 'contract' in FormSet.form.base_fields:
                    FormSet.form.base_fields['contract'].queryset = Contract.objects.filter(student=obj)
            else:
                # Yangi student yaratishda kontrakt bo'lmaydi -> bo'sh queryset
                if 'contract' in FormSet.form.base_fields:
                    FormSet.form.base_fields['contract'].queryset = Contract.objects.none()
        except Exception:
            # fallback: hech qanday o'zgartirish qilmasdan qaytaramiz
            pass

        return FormSet




# =============================================================================
# 🎓 TALABA ADMIN (IMPORT/EXPORT)
# (O'zgarishsiz qoldirildi)
# =============================================================================
class StudentResource(resources.ModelResource):
    # 1. Mavjud ForeignKey maydonlar (Import/Export uchun)
    group = fields.Field(
        column_name='group',
        attribute='group',
        widget=ForeignKeyWidget(Group, 'name')
    )

    citizenship = fields.Field(
        column_name='citizenship',
        attribute='citizenship',
        widget=ForeignKeyWidget(Country, 'id')
    )

    region = fields.Field(
        column_name='region',
        attribute='region',
        widget=ForeignKeyWidget(Region, 'id')
    )

    district = fields.Field(
        column_name='district',
        attribute='district',
        widget=ForeignKeyWidget(District, 'id')
    )

    previous_education_country = fields.Field(
        column_name='previous_education_country',
        attribute='previous_education_country',
        widget=ForeignKeyWidget(Country, 'name')
    )

    previous_education_region = fields.Field(
        column_name='previous_education_region',
        attribute='previous_education_region',
        widget=ForeignKeyWidget(Region, 'name')
    )

    # -------------------------------------------------------------------------
    # YANGI QO'SHILGAN MAYDONLAR (Qabul buyrug'i ma'lumotlari)
    # -------------------------------------------------------------------------
    qabul_order_number = fields.Field(
        column_name='Qabul buyruq raqami',
        readonly=True
    )

    qabul_order_date = fields.Field(
        column_name='Qabul buyruq sanasi',
        readonly=True
    )

    class Meta:
        model = Student
        import_id_fields = ['student_hemis_id']
        exclude = ('id', 'created_at', 'updated_at')
        skip_unchanged = True
        report_skipped = True
        use_bulk = False
        # Agar ustunlar ketma-ketligini o'zingiz xohlagandek qilmoqchi bo'lsangiz,
        # export_order ni ishlatishingiz mumkin. Hozircha default qoldiramiz.

    # -------------------------------------------------------------------------
    # YANGI LOGIKA: Buyruq ma'lumotlarini olish (Dehydrate)
    # -------------------------------------------------------------------------
    def dehydrate_qabul_order_number(self, student):
        # order_type_id=1 (Qabul) bo'lgan eng oxirgi buyruqni olamiz
        order = student.orders.filter(order_type_id=1).order_by('-order_date').first()
        return order.order_number if order else ""

    def dehydrate_qabul_order_date(self, student):
        order = student.orders.filter(order_type_id=1).order_by('-order_date').first()
        if order and order.order_date:
            return order.order_date.strftime('%d.%m.%Y')
        return ""

    # -------------------------------------------------------------------------
    # ESKI LOGIKA: Import jarayoni uchun (O'zgarishsiz)
    # -------------------------------------------------------------------------
    def get_instance(self, instance_loader, row):
        hemis_id = row.get('student_hemis_id')
        if hemis_id:
            try:
                return Student.objects.get(student_hemis_id=str(hemis_id).strip())
            except Student.DoesNotExist:
                return None
        return None

    def before_import_row(self, row, **kwargs):
        map_dictionaries = {
            'education_type': {
                'To‘lov-shartnoma': 'contract',
                'Davlat granti': 'grant',
            },
            'gender': {
                'Erkak': 'erkak',
                'Ayol': 'ayol',
            },
            'education_form': {
                'Kunduzgi': 'kunduzgi',
                'Sirtqi': 'sirtqi',
                'Kechki': 'kechki',
            },
            'status': {
                "O'qiydi": 'active',
                "Akademik ta'tilda": 'academic',
                "Chetlashtirilgan": 'expelled',
                "Bitirgan": 'graduated',
                'active': 'active',
            }
        }

        for field_name, mapping in map_dictionaries.items():
            if field_name in row and row[field_name] in mapping:
                row[field_name] = mapping[row[field_name]]

        text_fields_to_protect = [
            'address',
            'passport_issued_by',
            'phone_number',
            'passport_series_number',
            'personal_pin',
            'full_name'
        ]

        for field_name in text_fields_to_protect:
            if field_name in row and (row[field_name] == '' or row[field_name] is None):
                if field_name == 'phone_number':
                    row[field_name] = '000000000'
                else:
                    row[field_name] = 'Kiritilmagan'

        numeric_fields = [
            'entry_score',
            'previous_graduation_year',
            'citizenship',
            'region',
            'district',
        ]

        for field_name in numeric_fields:
            if field_name in row and (row[field_name] == '' or row[field_name] is None):
                row[field_name] = None

        defaulted_numeric_fields = [
            'course_year',
            'current_semester',
        ]

        for field_name in defaulted_numeric_fields:
            if field_name in row and (row[field_name] == '' or row[field_name] is None):
                row[field_name] = None

        foreign_key_fields = [
            'group',
            'previous_education_country',
            'previous_education_region'
        ]

        for field_name in foreign_key_fields:
            if field_name in row and (row[field_name] == '' or row[field_name] is None):
                row[field_name] = None

        date_fields = [
            'date_of_birth',
            'passport_issue_date',
            'passport_expiry_date'
        ]

        for field_name in date_fields:
            if field_name in row and (row[field_name] == '' or row[field_name] is None):
                row[field_name] = None




# =============================================================================
# 🔍 YANGI FILTERLAR
# =============================================================================

class AcademicYearFilter(admin.SimpleListFilter):
    title = _("O‘quv yili (Hisob-kitob uchun)")
    parameter_name = 'academic_year_calc'

    def lookups(self, request, model_admin):
        years = AcademicYear.objects.all().order_by('-name')
        # ID larni string qilib qaytaramiz
        return [(str(y.id), y.name) for y in years]

    def queryset(self, request, queryset):
        # Bu yerda hech narsa qilmaymiz, chunki logika StudentAdmin.get_queryset da
        return queryset

class StatusFilter(admin.SimpleListFilter):
    title = "Status"
    parameter_name = 'status'

    def lookups(self, request, model_admin):
        return (
            ('all', "Barcha talabalar"),
            ('active', "O'qiydi"),
            ('academic', "Akademik ta'tilda"),
            ('expelled', "Chetlashtirilgan"),
            ('graduated', "Bitirgan"),
        )

    def choices(self, cl):
        # BU YERDA SEHR QILINADI: Standart "Hammasi" ni olib tashlaymiz
        for lookup, title in self.lookup_choices:
            # Agar URLda status bo'lmasa -> active tanlangan bo'lsin
            selected = (self.value() == str(lookup)) or (self.value() is None and lookup == 'active')
            yield {
                'selected': selected,
                'query_string': cl.get_query_string({self.parameter_name: lookup}, []),
                'display': title,
            }

    def queryset(self, request, queryset):
        # Mantiq: Hech narsa tanlanmasa -> faqat 'active'
        if self.value() is None or self.value() == 'active':
            return queryset.filter(status='active')
        elif self.value() == 'all':
            return queryset # Hammasi kerak bo'lsa
        else:
            return queryset.filter(status=self.value())


# =========================================================
# 🛠 FILTER KLASSLAR (TO'LIQ RO'YXAT)
# =========================================================

# 1. TO'LOV FOIZI FILTERI (QAYTARILDI)
class PaymentPercentFilter(admin.SimpleListFilter):
    title = "To'lov foizi"
    parameter_name = 'payment_percent'

    def lookups(self, request, model_admin):
        return (
            ('0', '0% (To\'lamagan)'),
            ('1-24', '1% - 24%'),
            ('25', '25%'),
            ('26-49', '26% - 49%'),
            ('50', '50%'),
            ('51-74', '51% - 74%'),
            ('75', '75%'),
            ('76-99', '76% - 99%'),
            ('100', '100% (To\'liq)'),
            ('over', 'Ortiqcha (>100%)'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if not value:
            return queryset

        selected_values = value.split(',')
        combined_query = Q()

        for val in selected_values:
            # --- ORALIQLARDA BO'SHLIQ QOLMASLIGI UCHUN "LT" (<) ISHLATAMIZ ---

            if val == '0':
                # 1% dan kam (masalan 0.5% ham kiradi)
                combined_query |= Q(payment_percent__lt=1)

            elif val == '25':
                # 25.0 dan boshlab 26 gacha
                combined_query |= Q(payment_percent__gte=25, payment_percent__lt=26)

            elif val == '50':
                combined_query |= Q(payment_percent__gte=50, payment_percent__lt=51)

            elif val == '75':
                combined_query |= Q(payment_percent__gte=75, payment_percent__lt=76)

            elif val == '100':
                combined_query |= Q(payment_percent__gte=100, payment_percent__lt=101)

            elif val == 'over':
                combined_query |= Q(payment_percent__gte=101)

            elif '-' in val:
                # Masalan "1-24".
                # Biz buni "1 dan katta yoki teng" VA "25 dan KICHIK" deb olishimiz kerak.
                # Shunda 24.99% ham kirib ketadi.
                try:
                    parts = val.split('-')
                    min_val = int(parts[0])
                    max_val = int(parts[1])

                    # DIQQAT: max_val ga +1 qo'shib, 'lt' (kichik) ishlatamiz
                    # Masalan: 1-24 bo'lsa -> 1 dan 25 gacha (25 kirmaydi)
                    combined_query |= Q(payment_percent__gte=min_val, payment_percent__lt=max_val + 1)
                except ValueError:
                    pass

        return queryset.filter(combined_query)


# 2. GURUH FILTERI (YANGI)
class GroupFilter(admin.SimpleListFilter):
    title = "Guruh"
    parameter_name = 'group_filter'

    def lookups(self, request, model_admin):
        return [(g.id, g.name) for g in Group.objects.all()]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(group__id__in=self.value().split(','))
        return queryset


# 3. TA'LIM SHAKLI FILTERI (YANGI)
class EducationFormFilter(admin.SimpleListFilter):
    title = "Ta'lim shakli"
    parameter_name = 'education_form_filter'

    def lookups(self, request, model_admin):
        return Student.EducationFormChoices.choices

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(education_form__in=self.value().split(','))
        return queryset


# 4. KURS FILTERI (YANGI)
class CourseFilter(admin.SimpleListFilter):
    title = "Kurs"
    parameter_name = 'course_filter'

    def lookups(self, request, model_admin):
        return [(i, f"{i}-kurs") for i in range(1, 6)]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(course_year__in=self.value().split(','))
        return queryset

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    change_list_template = "admin/students/student/change_list.html"

    # ---------------------------------------------------------
    # 1. SHABLON VA DISPLAY SOZLAMALARI
    # ---------------------------------------------------------

    list_display = (
        'student_hemis_id',
        'full_name',
        # 'phone_number', # Kerak bo'lsa yoqing
        'education_form',
        'get_course_year',
        'get_group_name',

        # --- KONTRAKT USTUNLARI ---
        'get_contract_amount',
        'get_total_payment',
        'get_paid_percent',
        'get_payment_debt',

        # --- FAN QARZDORLIGI USTUNLARI ---
        'get_subject_debt_amount',  # Jami hisoblangan qarz
        'get_subject_debt_paid',  # To'langan qismi
        'get_subject_debt_diff',  # Qoldiq qarz
        'get_open_debt_count',
        'view_student_link',
    )

    list_filter = (
        PaymentPercentFilter,
        GroupFilter,
        EducationFormFilter,
        CourseFilter,
        AcademicYearFilter,
        StatusFilter,
    )

    search_fields = (
        'full_name',
        'student_hemis_id',
        'passport_series_number',
        'personal_pin',
        'group__name',  # Guruh nomi bo'yicha ham qidirish (juda qulay)
        'phone_number',  # Telefon raqam bo'yicha ham
    )


    raw_id_fields=['group','previous_education_country', 'citizenship',
        'region', 'district', 'previous_education_region']

    inlines = [ContractInline, OrderInline, SubjectDebtInline, StudentHistoryInline]

    fieldsets = (
        ('Asosiy ma\'lumotlar', {
            'fields': ('full_name', 'student_hemis_id', 'education_type', 'group', 'phone_number', 'phone_number_2')
        }),
        ('Pasport ma\'lumotlari', {
            'classes': ('collapse',),
            'fields': (
                'passport_series_number', 'personal_pin', 'passport_issued_by',
                'passport_issue_date', 'passport_expiry_date', 'date_of_birth',
                'birth_place', 'gender', 'nationality', 'citizenship', 'region', 'district', 'address'
            )
        }),
        ("O'qishga oid ma'lumotlar", {
            'fields': ('status', 'education_form', 'course_year', 'current_semester', 'entry_score', 'document',
                       'document_info')
        }),
        ("Oldingi ta'lim", {
            'classes': ('collapse',),
            'fields': (
                'previous_education_country', 'previous_education_region', 'previous_institution',
                'document_type', 'document_number', 'previous_graduation_year',
                'certificate_info', 'transferred_from_university'
            )
        }),
    )

    list_select_related = ('group__specialty', 'region', 'district')
    list_per_page = 50  # Sahifada kamroq bo'lsa tezroq ishlaydi
    show_full_result_count = False
    actions = None

    class Media:
        css = {
            'all': ('admin/css/custom_scroll.css',)
        }
        js = (
            'admin/js/jquery.init.js',
            'admin/js/money_input.js',
        )

    # ---------------------------------------------------------
    # 2. QUERYSET LOGIKASI (YIL VA HISOB-KITOB)
    # ---------------------------------------------------------
    def get_queryset(self, request):
        queryset = super().get_queryset(request)

        # 1. Tanlangan o'quv yilini aniqlash
        selected_year_id = request.GET.get('academic_year_calc')
        if selected_year_id:
            current_year = AcademicYear.objects.filter(id=selected_year_id).first()
        else:
            current_year = self.get_current_year()

        if not current_year:
            return queryset

        # --- A) KONTRAKT SUMMASI (GROSS - YALPI) ---
        # Bu yerda hech narsa ayirmaymiz, shunchaki shartnoma summasi
        contract_subquery = Contract.objects.filter(
            student=OuterRef('pk'),
            academic_year=current_year,
            contract_type='contract'
        ).values('student').annotate(
            total_amount=Sum('amount')
        ).values('total_amount')

        # --- B) GRANT SUMMASI ---
        grant_subquery = Contract.objects.filter(
            student=OuterRef('pk'),
            academic_year=current_year,
            contract_type='contract'
        ).values('student').annotate(
            total_grant=Sum('grant_amount')
        ).values('total_grant')

        # --- C) TO'LOV SUMMASI ---
        payment_subquery = Payment.objects.filter(
            contract__student=OuterRef('pk'),
            contract__academic_year=current_year,
            contract__contract_type='contract'
        ).values('contract__student').annotate(
            total=Sum('amount')
        ).values('total')

        # --- D) FAN QARZLARI ---
        subject_debt_total_subquery = SubjectDebt.objects.filter(
            student=OuterRef('pk')
        ).values('student').annotate(
            total=Sum('amount')
        ).values('total')

        subject_debt_paid_subquery = SubjectDebt.objects.filter(
            student=OuterRef('pk')
        ).values('student').annotate(
            total=Sum('amount_summ')
        ).values('total')

        open_debt_count_subquery = SubjectDebt.objects.filter(
            student=OuterRef('pk'),
            status__in=['yopilmadi', 'jarayonda']
        ).values('student').annotate(
            cnt=Count('id')
        ).values('cnt')

        # 1-BOSQICH: MA'LUMOTLARNI OLIB KELISH
        queryset = queryset.annotate(
            gross_contract_amount=Coalesce(Subquery(contract_subquery), Value(Decimal(0))),  # <--- JAMI KONTRAKT UCHUN
            current_grant_amount=Coalesce(Subquery(grant_subquery), Value(Decimal(0))),  # Grant
            total_paid_amount=Coalesce(Subquery(payment_subquery[:1]), Value(Decimal(0))),

            subject_debt_total=Coalesce(Subquery(subject_debt_total_subquery), Value(Decimal(0))),
            subject_debt_paid=Coalesce(Subquery(subject_debt_paid_subquery), Value(Decimal(0))),
            open_debt_count=Coalesce(Subquery(open_debt_count_subquery), Value(0)),
        )

        # 2-BOSQICH: REAL KONTRAKTNI HISOBLASH (Jadval ustunlari uchun)
        # Jadvalda "Kontrakt" ustuni Real (Net) summani ko'rsatishi kerak
        queryset = queryset.annotate(
            current_contract_amount=ExpressionWrapper(
                F('gross_contract_amount') - F('current_grant_amount'),
                output_field=DecimalField()
            )
        )

        # 3-BOSQICH: QARZ VA FOIZLAR (Real kontraktga asoslanadi)
        queryset = queryset.annotate(
            payment_percent=Case(
                When(current_contract_amount__lte=0, then=Value(Decimal(0))),
                default=(F('total_paid_amount') * 100) / F('current_contract_amount'),
                output_field=DecimalField()
            ),
            # Qarzdorlik = Real Kontrakt - To'lov
            payment_diff=F('current_contract_amount') - F('total_paid_amount'),

            subject_debt_diff=F('subject_debt_total') - F('subject_debt_paid'),
        )

        return queryset

    # ---------------------------------------------------------
    # 3. STATISTIKA PANELINI CHIQARISH (YANGILANDI)
    # ---------------------------------------------------------
    def changelist_view(self, request, extra_context=None):
        if request.method == 'GET':
            q = request.GET.copy()
            if 'academic_year_calc' not in q:
                active_year = AcademicYear.objects.filter(is_active=True).first()
                if active_year:
                    q['academic_year_calc'] = str(active_year.id)
                    request.GET = q
                    request.META['QUERY_STRING'] = q.urlencode()

        groups_data = list(Group.objects.values('id', 'name').order_by('name'))
        extra_context = extra_context or {}
        extra_context['groups_json'] = json.dumps(groups_data)

        response = super().changelist_view(request, extra_context)

        if not hasattr(response, 'context_data') or 'cl' not in response.context_data:
            return response

        cl = response.context_data['cl']
        qs = cl.queryset

        # 4. AGGREGATSIYA (HISOBLASH)
        metrics = qs.aggregate(
            # A) JAMI KONTRAKT (Grant ayrilmagan - YALPI)
            jami_gross_shartnoma=Sum('gross_contract_amount'),

            # B) REAL KONTRAKT (Grant ayrilgan - SOF)
            jami_real_shartnoma=Sum('current_contract_amount'),

            jami_grant=Sum('current_grant_amount'),
            jami_tolov=Sum('total_paid_amount'),

            # Haqiqiy umumiy qarz (Real Shartnoma - To'lov)
            haqiqiy_qarz=Sum(
                Case(
                    When(
                        current_contract_amount__gt=F('total_paid_amount'),
                        then=F('current_contract_amount') - F('total_paid_amount')
                    ),
                    default=Value(Decimal('0')),
                    output_field=DecimalField()
                )
            ),
        )

        val_gross = metrics['jami_gross_shartnoma'] or 0
        val_real = metrics['jami_real_shartnoma'] or 0
        val_grant = metrics['jami_grant'] or 0
        val_paid = metrics['jami_tolov'] or 0
        val_debt = metrics['haqiqiy_qarz'] or 0

        response.context_data['footer_stats'] = {
            'contract': val_gross,  # <--- 1-BOX: Grant ayrilmagan summa (Jami Kontrakt)
            'real_contract': val_real,  # <--- 2-BOX: Grant ayrilgan summa (Real Kontrakt)
            'grant': val_grant,  # 3-BOX: Grant
            'paid': val_paid,  # 4-BOX: To'langan
            'debt': val_debt,  # 5-BOX: Qarz (Realga nisbatan)
        }

        return response

    # ---------------------------------------------------------
    # 4. DISPLAY METODLARI (CHIROYLI DIZAYN BILAN)
    # ---------------------------------------------------------

    def get_current_year(self):
        return AcademicYear.objects.filter(is_active=True).first()

    @admin.display(description="Kurs", ordering='course_year')
    def get_course_year(self, obj):
        return obj.course_year if obj.group else "-"

    @admin.display(description="Guruh", ordering='group__name')
    def get_group_name(self, obj):
        if obj.group:
            # Guruh nomini chiroyli kulrang fonda chiqarish
            return format_html(
                '<span class="group-badge">{}</span>',
                obj.group.name
            )
        return "-"

    # --- KONTRAKT DISPLAY ---
    @admin.display(description="kontrakt", ordering='current_contract_amount')
    def get_contract_amount(self, obj):
        if hasattr(obj, 'current_contract_amount') and obj.current_contract_amount > 0:
            return f"{obj.current_contract_amount:,.0f}".replace(",", " ")
        return "-"

    @admin.display(description="To‘lov", ordering='total_paid_amount')
    def get_total_payment(self, obj):
        if hasattr(obj, 'total_paid_amount') and obj.total_paid_amount > 0:
            return f"{obj.total_paid_amount:,.0f}".replace(",", " ")
        return "-"

    @admin.display(description="Foizi", ordering='payment_percent')  # <-- O'ZGARTIRILDI
    def get_paid_percent(self, obj):
        if not hasattr(obj, 'current_contract_amount') or obj.current_contract_amount == 0:
            return format_html('<span class="status-badge badge-secondary">-</span>')

        percent = obj.payment_percent.quantize(Decimal('1.'), rounding=ROUND_HALF_UP)

        # Rang logikasi
        if percent >= 100:
            css_class = 'badge-success'
            icon = '✓'
        elif percent >= 50:
            css_class = 'badge-info'
            icon = ''
        elif percent > 0:
            css_class = 'badge-warning'
            icon = ''
        else:
            css_class = 'badge-danger'
            icon = '!'

        return format_html(
            '<div class="status-badge {}">{} {}%</div>',
            css_class, icon, percent
        )

    @admin.display(description="Qarzi", ordering='payment_diff')
    def get_payment_debt(self, obj):
        if not hasattr(obj, 'current_contract_amount') or obj.current_contract_amount == 0:
            return "-"

        debt = obj.payment_diff

        if debt <= 0:
            # Qarzi yo'q bo'lsa
            return format_html('<span style="color: #20c997; font-weight: bold; font-size: 16px;">✓</span>')

        formatted = f"{debt:,.0f}".replace(",", " ")
        # Qarzi bor bo'lsa, qizil badge
        return format_html(
            '<span class="status-badge badge-danger">{}</span>',
            formatted
        )

    # --- FAN QARZDORLIGI DISPLAY (YANGI) ---
    @admin.display(description="K-M shartnoma", ordering='subject_debt_total')
    def get_subject_debt_amount(self, obj):
        if hasattr(obj, 'subject_debt_total') and obj.subject_debt_total > 0:
            return f"{obj.subject_debt_total:,.0f}".replace(",", " ")
        return "-"

    @admin.display(description="K-M To'lov", ordering='subject_debt_paid')
    def get_subject_debt_paid(self, obj):
        if hasattr(obj, 'subject_debt_paid') and obj.subject_debt_paid > 0:
            return f"{obj.subject_debt_paid:,.0f}".replace(",", " ")
        return "-"

    @admin.display(description="K-M Qarz", ordering='subject_debt_diff')
    def get_subject_debt_diff(self, obj):
        if not hasattr(obj, 'subject_debt_total') or obj.subject_debt_total == 0:
            return "-"

        debt = obj.subject_debt_diff

        if debt <= 0:
            return format_html('<span style="color: #20c997; font-weight: bold;">Yopilgan</span>')

        formatted = f"{debt:,.0f}".replace(",", " ")
        # Fan qarzi uchun alohida ogohlantirish stili
        return format_html(
            '<span class="status-badge badge-danger" style="border: 1px dashed #fa5252;">{}</span>',
            formatted
        )

    @admin.display(description="Qarz fanlar", ordering='open_debt_count')
    def get_open_debt_count(self, obj):
        # Annotatsiyadan kelgan qiymatni olamiz
        count = getattr(obj, 'open_debt_count', 0)

        if count == 0:
            # Agar qarzdorlik soni 0 bo'lsa, yashil belgi yoki chiziqcha
            return format_html('<span style="color: #20c997; font-weight: bold;">-</span>')

        # Agar qarzi bor bo'lsa, qizil badgeda sonini chiqaramiz
        return format_html(
            '<span class="status-badge badge-danger" style="font-size: 13px; padding: 4px 8px;">{} ta</span>',
            count
        )

    # ---------------------------------------------------------
    # 5. QO'SHIMCHA URL VA VIEWLAR
    # ---------------------------------------------------------

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<path:object_id>/detail/',
                self.admin_site.admin_view(self.student_detail_view),
                name='students_student_detail'
            ),
            path('export-excel/', self.admin_site.admin_view(self.export_excel_view), name='students_student_export'),
        ]
        return custom_urls + urls

    def export_excel_view(self, request):
        """
        Talabalar ro'yxatini Excelga export qilish.
        Yangilangan: Yo'nalish va Guruh alohida, pullar va foizlar butun sonda.
        """
        # 1. Filtrlangan ma'lumotlarni olish
        try:
            cl = self.get_changelist_instance(request)
            queryset = cl.get_queryset(request)
        except AttributeError:
            queryset = self.filter_queryset(self.get_queryset(request))

        # 2. Formadan tanlangan ustunlarni olish
        selected_fields = request.POST.getlist('selected_fields')

        # --- O'ZGARISH: Default ro'yxatga Yo'nalish, Grant va boshqalar qo'shildi ---
        if not selected_fields:
            selected_fields = [
                'full_name',
                'student_hemis_id',
                'specialty',               # <--- Yangi: Yo'nalish
                'group',                   # <--- Guruh (Alohida)
                'education_form',
                'current_contract_amount', # <--- Shartnoma (Jami)
                'current_grant_amount',    # <--- Grant (Jami)
                'total_paid_amount',       # <--- To'lov
                'payment_diff',            # <--- Qarz
                'payment_percent',         # <--- Foiz
                'qabul_order_number',
                'qabul_order_date'
            ]
        # ---------------------------------------------

        # 3. Excel fayl yaratish
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Talabalar Export"

        # Dizayn
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
        center_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
        left_align = Alignment(horizontal='left', vertical='center', wrap_text=True)
        thin_border = Border(left=Side(style='thin'), right=Side(style='thin'),
                             top=Side(style='thin'), bottom=Side(style='thin'))
        money_format = '#,##0'  # Faqat butun sonlar uchun format

        # 4. Header nomlari
        field_titles = {
            'student_hemis_id': 'ID (Hemis)',
            'full_name': 'F.I.SH.',
            'specialty': "Yo'nalish",         # <--- Sarlavha
            'group': 'Guruh',
            'course_year': 'Kurs',
            'education_form': "Ta'lim shakli",
            'education_type': "Ta'lim turi",
            'payment_type': "To'lov turi",

            'contract_number': 'Shartnoma raqami',
            'contract_date': 'Shartnoma sanasi',

            'current_contract_amount': 'Hisoblangan kontrakt',
            'current_grant_amount': 'Grant summasi', # <--- Sarlavha
            'total_paid_amount': "To'langan summa",
            'payment_diff': 'Qarzdorlik',
            'payment_percent': 'Foiz (%)',

            'passport_serial': 'Pasport Seriya',
            'passport_number': 'Pasport Raqami',
            'pinfl': 'JSHSHIR',
            'gender': 'Jinsi',
            'birth_date': "Tug'ilgan sana",
            'region': 'Viloyat',
            'district': 'Tuman',
            'address': 'Manzil',
            'phone_number': 'Telefon',

            'previous_institution': 'Oldingi muassasa',
            'document_type': 'Hujjat turi',
            'document_number': 'Hujjat raqami',
            'transferred_from_university': "Ko'chirgan OTM",

            'qabul_order_number': 'Qabul buyruq №',
            'qabul_order_date': 'Qabul buyruq sanasi',
        }

        # Headerlarni chizish
        for col_num, field in enumerate(selected_fields, 1):
            column_letter = get_column_letter(col_num)
            cell = ws.cell(row=1, column=col_num)
            cell.value = field_titles.get(field, field)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center_align
            cell.border = thin_border

            if field == 'full_name':
                ws.column_dimensions[column_letter].width = 35
            elif field == 'specialty':
                ws.column_dimensions[column_letter].width = 30
            elif field in ['contract_number', 'contract_date']:
                ws.column_dimensions[column_letter].width = 20
            else:
                ws.column_dimensions[column_letter].width = 15

        # 5. Ma'lumotlarni yozish
        # Grantni ham pul maydonlariga qo'shdik
        money_fields = ['current_contract_amount', 'current_grant_amount', 'total_paid_amount', 'payment_diff',
                        'subject_debt_total', 'subject_debt_paid', 'subject_debt_diff']

        row_num = 2
        active_year = AcademicYear.objects.filter(is_active=True).first()

        for obj in queryset:
            # --- SHARTNOMANI OLISH LOGIKASI ---
            active_contract = None
            need_contract = ('contract_number' in selected_fields or 'contract_date' in selected_fields)

            if need_contract and active_year:
                active_contract = obj.contract_set.filter(
                    academic_year=active_year,
                    contract_type='contract'
                ).first()

            # Qabul buyrug'ini olish
            qabul_order = None
            if 'qabul_order_number' in selected_fields or 'qabul_order_date' in selected_fields:
                qabul_order = obj.order_set.filter(
                    order_type__name__icontains='qabul',
                    is_deleted=False
                ).order_by('-order_date').first()

            for col_num, field in enumerate(selected_fields, 1):
                cell = ws.cell(row=row_num, column=col_num)
                val = None

                # --- 1. Shartnoma ma'lumotlari ---
                if field == 'contract_number':
                    val = active_contract.contract_number if active_contract else ""
                    cell.alignment = center_align

                elif field == 'contract_date':
                    if active_contract and active_contract.contract_date:
                        val = active_contract.contract_date.strftime('%d.%m.%Y')
                    else:
                        val = ""
                    cell.alignment = center_align

                # --- 2. Qabul buyrug'i ---
                elif field == 'qabul_order_number':
                    val = qabul_order.order_number if qabul_order else ""
                    cell.alignment = center_align

                elif field == 'qabul_order_date':
                    if qabul_order and qabul_order.order_date:
                        val = qabul_order.order_date.strftime('%d.%m.%Y')
                    else:
                        val = ""
                    cell.alignment = center_align

                # --- 3. Foizni butun qilish ---
                elif field == 'payment_percent':
                    if hasattr(obj, 'payment_percent') and obj.payment_percent is not None:
                        val = int(obj.payment_percent) # Butun qismga o'tkazish
                    else:
                        val = 0

                # --- 4. Bog'langan maydonlar ---
                elif field == 'specialty': # <--- Yo'nalishni guruh orqali olish
                    val = obj.group.specialty.name if obj.group and obj.group.specialty else ""
                elif field == 'group':
                    val = str(obj.group.name) if obj.group else ""
                elif field == 'course_year':
                    val = str(obj.course_year) if obj.course_year else ""
                elif field == 'region':
                    val = obj.region.name if obj.region else ""
                elif field == 'district':
                    val = obj.district.name if obj.district else ""

                # --- 5. Obyektning o'z maydonlari (Grant va Contract shu yerda avtomatik olinadi) ---
                elif hasattr(obj, field):
                    val = getattr(obj, field)
                    if isinstance(val, (datetime, date)):
                        val = val.strftime('%d.%m.%Y')
                    elif callable(val):
                        val = val()

                # --- Qiymatni yozish ---
                if val is None:
                    val = ""

                if field in money_fields:
                    try:
                        # MUHIM: Floatni Int ga o'tkazish (faqat butun qism)
                        cell.value = int(float(val)) if val else 0
                        cell.number_format = money_format
                    except (ValueError, TypeError):
                        cell.value = val
                elif field == 'payment_percent':
                    cell.value = val
                    cell.alignment = center_align
                else:
                    cell.value = str(val)

                cell.border = thin_border

                if field not in ['full_name', 'address', 'specialty'] and field not in money_fields:
                    cell.alignment = center_align
                elif field in ['full_name', 'specialty']:
                    cell.alignment = left_align

            row_num += 1

        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        response['Content-Disposition'] = f'attachment; filename=Students_Export_{timestamp}.xlsx'
        wb.save(response)
        return response

    # D) ChangeList yordamchisi (Filter ishlashi uchun kerak)
    def get_changelist_instance(self, request):
        list_display = self.get_list_display(request)
        list_display_links = self.get_list_display_links(request, list_display)
        list_filter = self.get_list_filter(request)
        search_fields = self.get_search_fields(request)
        list_select_related = self.get_list_select_related(request)

        try:
            actions = self.get_actions(request)
            if actions:
                list_display = ['action_checkbox'] + list(list_display)
        except (AttributeError, KeyError):
            pass

        ChangeListClass = self.get_changelist(request)

        return ChangeListClass(
            request,
            self.model,
            list_display,
            list_display_links,
            list_filter,
            self.date_hierarchy,
            search_fields,
            list_select_related,
            self.list_per_page,
            self.list_max_show_all,
            self.list_editable,
            self,
            self.sortable_by,
            self.search_help_text,
        )

    @admin.display(description="Ko'rish")
    def view_student_link(self, obj):
        url = reverse('admin:students_student_detail', args=[obj.pk])
        # Ko'zchani chiroyli qilish
        return format_html(
            '<a href="{}" title="To\'liq ma\'lumot" class="view-link" style="color: #adb5bd; font-size: 1.2rem; transition: 0.2s;">'
            '<i style="color:blue" class="fas fa-eye"></i>'
            '</a>',
            url
        )

    def student_detail_view(self, request, object_id):
        student = self.get_object(request, object_id)
        if student is None:
            return self._get_obj_does_not_exist_redirect(request, self.model._meta, object_id)

        contracts = student.contract_set.all().order_by('-academic_year__name')
        payments = Payment.objects.filter(contract__student=student).order_by('-payment_date')
        orders = student.orders.all().order_by('-order_date')

        # --- O'ZGARTIRILGAN QISM (ANNOTATE QO'SHILDI) ---
        debts = student.subjectdebt_set.annotate(
            paid_amount=Coalesce('amount_summ', Value(Decimal('0'))),
            remaining_debt=F('amount') - Coalesce('amount_summ', Value(Decimal('0')))
        ).order_by('-academic_year__name', 'subject__name')
        # ------------------------------------------------

        context = {
            # ... (eski context qismi o'zgarishsiz)
            'title': f"{student.full_name} ma'lumotlari",
            'student': student,
            'contracts': contracts,
            'payments': payments,
            'orders': orders,
            'debts': debts,
            'opts': self.model._meta,
            'has_change_permission': self.has_change_permission(request, student),
        }
        return render(request, 'admin/students/student/student_detail.html', context)

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == 'birth_place':
            existing_places = Student.objects.exclude(birth_place__isnull=True).exclude(
                birth_place__exact='').values_list('birth_place', flat=True).distinct()
            kwargs['widget'] = DatalistTextInput(datalist=existing_places)
        elif db_field.name == 'nationality':
            existing_nationalities = Student.objects.exclude(nationality__isnull=True).exclude(
                nationality__exact='').values_list('nationality', flat=True).distinct()
            kwargs['widget'] = DatalistTextInput(datalist=existing_nationalities)
        return super().formfield_for_dbfield(db_field, request, **kwargs)