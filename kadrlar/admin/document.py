from .base import *

@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    # 1. RO'YXAT KO'RINISHI
    list_display = ('get_full_name', 'department_col', 'work_type_display',

                    'schedule_status_col')

    list_filter = ('schedule_approved', 'work_type_permanent', 'work_type_hourly',
                   'employee__department')

    autocomplete_fields = ['employee']
    filter_horizontal = ('subjects',)
    # inlines = [TeacherAvailabilityInline] # Olib tashlaymiz, dinamik qo'shamiz
    search_fields = ['employee__first_name', 'employee__last_name']
    
    def get_inlines(self, request, obj=None):
        if obj:  # Obyekt saqlanganidan keyin barcha o'qituvchilarga (doimiy/soatbay) ko'rinadi
            return [TeacherAvailabilityInline]
        return []
    # 2. FORMA KO'RINISHI
    fieldsets = (
        ("Xodim", {'fields': ('employee',)}),


        # ------------------------------

        ("Ishlash turi", {
            'fields': ('work_type_permanent', 'work_type_hourly'),
            'description': "O'qituvchi bir vaqtning o'zida ham doimiy, ham soatbay ishlashi mumkin."
        }),
        ("Yuklama",
         {'fields': ('subjects',)}),
        ("Tasdiqlash", {'fields': ('schedule_approved',), 'classes': ('collapse',)}),
    )

    # 3. QUERYSET (Kafedra mudiri faqat o'z xodimlarini ko'radi)
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.filter(employee__archived=False)

        if is_hr_admin(request.user) or is_edu_admin(request.user):
            return qs

        return qs.filter(employee__department__head_manager=request.user)

    # 4. TAHRIRLASHNI CHEKLASH (READONLY FIELDS)
    def get_readonly_fields(self, request, obj=None):
        # --- KADRLAR BO'LIMI (HR) ---
        if is_hr_admin(request.user):
            # HR hamma narsani ko'radi, lekin faqat SHTAT, DARJA va UNVONni o'zgartira oladi.
            # Boshqa narsalar (Fanlar, yuklama) HR uchun yopiq bo'ladi.

            readonly_cols = [f.name for f in self.model._meta.fields]

            # Tahrirlashga ruxsat berilgan maydonlar:
            editable_fields = [
                'work_type_permanent',
                'work_type_hourly',
            ]

            for field in editable_fields:
                if field in readonly_cols:
                    readonly_cols.remove(field)

            # Subjects M2M bo'lgani uchun alohida qo'shib qo'yamiz (HR o'zgartirmasligi uchun)
            return readonly_cols + ['subjects']

        # --- O'QUV BO'LIMI VA KAFEDRA ---
        # Ular shtat va ilmiy darajani faqat ko'radi, o'zgartira olmaydi.
        readonly = [
            'work_type_permanent',
            'work_type_hourly',

        ]

        edu_admin = is_edu_admin(request.user)

        if not edu_admin:
            readonly.append('schedule_approved')

        if obj:
            readonly.append('employee')
            # Agar tasdiqlangan bo'lsa, O'quv bo'limidan boshqa hech kim o'zgartira olmaydi
            if obj.schedule_approved and not edu_admin:
                readonly.extend([
                    'subjects',

                ])
        return readonly

    # 5. FILTR (Department bo'yicha)
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "employee" and not (is_hr_admin(request.user) or is_edu_admin(request.user)):
            kwargs["queryset"] = Employee.objects.filter(
                department__head_manager=request.user,
                is_teacher=True
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    # 6. RUXSATLAR (Permissions)
    def has_add_permission(self, request):
        # HR Teacher profilini qo'sholmaydi (Faqat Kafedra yoki O'quv bo'limi)
        if is_hr_admin(request.user):
            return False
        return True

    def has_change_permission(self, request, obj=None):
        # HR ga o'zgartirish ruxsati KERAK (Ilmiy daraja va shtat uchun)
        if is_hr_admin(request.user):
            return True

        if is_edu_admin(request.user):
            return True
        if obj and obj.employee.department.head_manager == request.user:
            return True
        if obj is None: return True
        return False

    def has_delete_permission(self, request, obj=None):
        if is_hr_admin(request.user):
            return True
        if obj and obj.schedule_approved and not is_edu_admin(request.user):
            return False

        return True

    # 7. DIZAYN METODLARI
    def get_full_name(self, obj):
        return str(obj.employee)

    get_full_name.short_description = "O'qituvchi"

    def department_col(self, obj):
        return obj.employee.department

    department_col.short_description = "Kafedra / Bo'lim"

    def work_type_display(self, obj):
        tags = []
        if getattr(obj, 'work_type_permanent', False):
            tags.append(
                '<span style="background: #e0f2fe; color: #0369a1; padding: 2px 6px; border-radius: 4px; margin-right: 4px; font-size: 11px;">Doimiy</span>')
        if getattr(obj, 'work_type_hourly', False):
            tags.append(
                '<span style="background: #fef3c7; color: #b45309; padding: 2px 6px; border-radius: 4px; font-size: 11px;">Soatbay</span>')

        if not tags:
            return "-"
        return format_html("".join(tags))

    work_type_display.short_description = "Ishlash turi"

    def schedule_status_col(self, obj):
        return format_html(
            '<span style="background: {}; color: {}; padding: 4px 8px; border-radius: 4px; font-weight: bold;">{}</span>',
            '#dcfce7' if obj.schedule_approved else '#fee2e2',
            '#166534' if obj.schedule_approved else '#991b1b',
            '✅ Tasdiqlangan' if obj.schedule_approved else '⏳ Kutilmoqda')

    schedule_status_col.short_description = "O'quv Bo'limi"


