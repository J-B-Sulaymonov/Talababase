from .base import *

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('number', 'employee', 'order_type', 'date')
    list_filter = ('order_type', 'date')
    search_fields = ('number', 'employee__first_name', 'employee__last_name', 'employee__pid')
    date_hierarchy = 'date'

    def has_module_permission(self, request):
        return is_hr_admin(request.user)

    def has_add_permission(self, request):
        return is_hr_admin(request.user)

    def has_change_permission(self, request, obj=None):
        return is_hr_admin(request.user)

    def has_delete_permission(self, request, obj=None):
        return is_hr_admin(request.user)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('doc_type', 'employee', 'number', 'uploaded_at')
    list_filter = ('doc_type',)
    search_fields = ('number', 'employee__first_name')

    def has_module_permission(self, request):
        return is_hr_admin(request.user)


@admin.register(TeacherAvailability)
class TeacherAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('teacher', 'weekday')
    list_filter = ('weekday',)

    def has_module_permission(self, request):
        return is_edu_admin(request.user)


@admin.register(Weekday)
class WeekdayAdmin(admin.ModelAdmin):
    list_display = ('name', 'order')
    ordering = ('order',)

    def has_module_permission(self, request):
        return is_edu_admin(request.user) or is_hr_admin(request.user)


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ('index', 'start_time', 'end_time', 'is_active')
    ordering = ('index',)

    def has_module_permission(self, request):
        return is_edu_admin(request.user) or is_hr_admin(request.user)


class QuizResultKeyInline(NestedTabularInline):
    model = QuizResultKey
    extra = 0
    fields = ('code', 'description',)
    verbose_name = "Natija Kaliti (Masalan: A, B, C, D)"
    verbose_name_plural = "Test Kalitlari va Tavsiflari"
    classes = ['wide'] # Kengroq ko'rinish uchun

class QuizAnswerInline(NestedTabularInline):
    model = QuizAnswer
    extra = 0
    min_num = 1
    fields = ('text', 'symbol', 'score')
    verbose_name = "Javob varianti"
    verbose_name_plural = "Javob variantlari"
    # classes = ['collapse']  # Buni olib tashlab turing, ochilib turgani ma'qul

# 2. Savollar (O'rta qism - Savol va ichida Javoblar)
class QuizQuestionInline(NestedStackedInline):
    model = QuizQuestion
    extra = 0
    fields = ('text', 'order')
    inlines = [QuizAnswerInline] # <--- MANA SHU JAVOBLARNI CHIQARADI
    verbose_name = "Savol"
    verbose_name_plural = "Savollar"
class QuizScoringRuleInline(NestedTabularInline):
    model = QuizScoringRule
    extra = 0
    fields = ('category_name', 'related_questions', 'min_score', 'max_score', 'conclusion')
    verbose_name = "Natija talqini"
    verbose_name_plural = "Natija talqinlari (Min-Max ballar)"
    classes = ['wide']

class QuizScoringInfoInline(NestedTabularInline):
    model = QuizScoringInfo
    extra = 0
    fields = ('min_score', 'max_score', 'conclusion')
    verbose_name = "Natija bali izohi"
    verbose_name_plural = "Natija bali (oraliq ballari)"
    classes = ['wide']

# 3. Asosiy Quiz Admin
@admin.register(Quiz)
class QuizAdmin(NestedModelAdmin):
    list_display = ('title', 'question_count', 'is_active', 'created_at','id')
    inlines = [QuizQuestionInline,QuizResultKeyInline,QuizScoringRuleInline,QuizScoringInfoInline]
    search_fields = ('title',)

    def question_count(self, obj):
        return obj.questions.count()
    question_count.short_description = "Savollar soni"

    class Media:
        css = {
            'all': ('admin/css/admin_quiz.css',)
        }


@admin.register(QuizPermission)
class QuizPermissionAdmin(admin.ModelAdmin):
    list_display = ('employee', 'quiz', 'is_active', 'created_at')
    list_filter = ('quiz', 'is_active', 'employee__department')
    search_fields = ('employee__first_name', 'employee__last_name', 'employee__pid')
    autocomplete_fields = ['employee', 'quiz']
    actions = ['activate_permissions', 'deactivate_permissions']

    def activate_permissions(self, request, queryset):
        queryset.update(is_active=True)

    activate_permissions.short_description = "Tanlanganlarga qayta topshirishga RUXSAT berish"

    def deactivate_permissions(self, request, queryset):
        queryset.update(is_active=False)

    deactivate_permissions.short_description = "Ruxsatni YOPISH"


@admin.register(QuizResult)
class QuizResultAdmin(admin.ModelAdmin):
    list_display = ('employee', 'quiz', 'total_score', 'created_at')
    list_filter = ('quiz', 'created_at', 'employee__department')
    readonly_fields = ('formatted_struct',)
    exclude = ('struct',)  # Xom JSON ni yashiramiz

    def formatted_struct(self, obj):
        """JSON ma'lumotni chiroyli jadval shaklida chiqarish"""
        if not obj.struct:
            return "-"

        # 1. Ma'lumot turini tekshirish va to'g'irlash
        # Agar baza allaqachon DICT yoki LIST qaytargan bo'lsa, o'zini olamiz.
        if isinstance(obj.struct, (dict, list)):
            data = obj.struct
        else:
            # Agar string bo'lsa, json.loads qilamiz
            try:
                data = json.loads(obj.struct)
            except:
                return "Ma'lumot formati noto'g'ri"

        # 2. Javoblar ro'yxatini ajratib olish
        # Biz yangi formatda { "answers": [...], "analysis": [...] } qildik.
        # Shuning uchun 'answers' kalitini qidiramiz.
        answers_list = []

        if isinstance(data, dict):
            # Yangi format
            answers_list = data.get('answers', [])
        elif isinstance(data, list):
            # Eski format (agar eski testlar bo'lsa)
            answers_list = data

        # 3. Jadval chizish
        html = '<table style="width:100%; border-collapse: collapse; border: 1px solid #ddd;">'
        html += '<thead style="background:#f8f9fa;"><tr>' \
                '<th style="padding:10px; border:1px solid #ddd; text-align:left;">Savol</th>' \
                '<th style="padding:10px; border:1px solid #ddd; text-align:left;">Tanlangan Javob</th>' \
                '<th style="padding:10px; border:1px solid #ddd; text-align:center;">Ball</th></tr></thead><tbody>'

        for item in answers_list:
            # item dict ekanligiga ishonch hosil qilamiz
            if isinstance(item, dict):
                html += f"<tr>" \
                        f"<td style='padding:8px; border:1px solid #ddd;'>{item.get('question', '-')}</td>" \
                        f"<td style='padding:8px; border:1px solid #ddd;'>{item.get('selected', '-')}</td>" \
                        f"<td style='padding:8px; border:1px solid #ddd; text-align:center;'>{item.get('score', 0)}</td>" \
                        f"</tr>"

        html += '</tbody></table>'

        # Qo'shimcha: Agar Tahlil (Analysis) qismi bo'lsa, uni ham pastda ko'rsatish mumkin
        if isinstance(data, dict) and data.get('analysis'):
            html += '<h4 style="margin-top:20px;">Tahlil natijalari:</h4>'
            html += '<table style="width:100%; border-collapse: collapse; border: 1px solid #ddd;"><thead><tr style="background:#eef2ff;"><th>Kategoriya</th><th>Ball</th><th>Xulosa</th></tr></thead><tbody>'
            for anal in data['analysis']:
                html += f"<tr><td style='border:1px solid #ddd; padding:5px;'>{anal.get('category')}</td>" \
                        f"<td style='border:1px solid #ddd; padding:5px;'><b>{anal.get('score')}</b></td>" \
                        f"<td style='border:1px solid #ddd; padding:5px;'>{anal.get('conclusion')}</td></tr>"
            html += '</tbody></table>'

        return mark_safe(html)

    formatted_struct.short_description = "Batafsil Natijalar"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


original_each_context = admin.site.each_context


def get_new_context(request):
    """
    Tug'ilgan kunlarni faqat 'Kadrlar' guruhi a'zolariga ko'rsatish.
    Superuserga ko'rsatilmaydi.
    """
    context = original_each_context(request)
    user = request.user

    # 1. RUXSATNI ANIQLASH
    is_kadr_notification_viewer = False

    if user.is_authenticated:
        # O'ZGARISH SHU YERDA:
        # Biz user.is_superuser ni TEKSHIRMAYMIZ.
        # Faqatgina "Kadrlar" guruhida bor bo'lsa True bo'ladi.
        if user.groups.filter(name='Kadrlar').exists():
            is_kadr_notification_viewer = True

    # Context o'zgaruvchisini yangilaymiz
    context['is_kadr_member'] = is_kadr_notification_viewer

    # 2. TUG'ILGAN KUNLAR LOGIKASI (Faqat ruxsati borlarga hisoblanadi)
    if is_kadr_notification_viewer:
        today = timezone.now().date()
        tomorrow = today + timedelta(days=1)

        # Faol xodimlarni olamiz
        active_employees = Employee.objects.filter(status='active', archived=False).exclude(birth_date__isnull=True)

        birthdays_today = []
        birthdays_tomorrow = []

        for emp in active_employees:
            try:
                bday_this_year = emp.birth_date.replace(year=today.year)
            except ValueError:
                # 29-fevral muammosi
                bday_this_year = emp.birth_date.replace(year=today.year, day=28) + timedelta(days=1)

            if bday_this_year == today:
                birthdays_today.append(emp)
            elif bday_this_year == tomorrow:
                birthdays_tomorrow.append(emp)

        context['notify_birthdays_count'] = len(birthdays_today) + len(birthdays_tomorrow)
        context['notify_birthdays_today'] = birthdays_today
        context['notify_birthdays_tomorrow'] = birthdays_tomorrow
    else:
        # Superuser va boshqalar uchun bo'sh
        context['notify_birthdays_count'] = 0
        context['notify_birthdays_today'] = []
        context['notify_birthdays_tomorrow'] = []

    return context


# Funksiyani qayta ulaymiz
admin.site.each_context = get_new_context


@admin.register(OrganizationStructure)
class OrganizationStructureAdmin(admin.ModelAdmin):
    # Biz yaratgan maxsus shablonni ulaymiz
    change_form_template = "admin/kadrlar/org_structure_change_form.html"

    list_display = ('title', 'is_active', 'updated_at')

    # Kadrlar admini va superuser ko'ra oladi
    def has_module_permission(self, request):
        return is_hr_admin(request.user)

    def has_add_permission(self, request):
        return is_hr_admin(request.user)

    def has_change_permission(self, request, obj=None):
        return is_hr_admin(request.user)

    def has_delete_permission(self, request, obj=None):
        return is_hr_admin(request.user)


@admin.register(SimpleStructure)
class SimpleStructureAdmin(DraggableMPTTAdmin):
    # 1. Ro'yxatda nimalar ko'rinsin?
    list_display = (
        'tree_actions',
        'indented_title',
        'layout_display',
        'node_type_display',
        'mapping_info',
        'employee_count_display',
        'order'
    )
    list_display_links = ('indented_title',)

    # 2. Qidiruv va Autocomplete (Katta bazalar uchun qulay)
    search_fields = ('name',)
    autocomplete_fields = ['department', 'employee']

    # 3. Forma ko'rinishi (Guruhlarga bo'lingan)
    fieldsets = (
        ('Tugun Ma\'lumotlari', {
            'fields': ('name', 'parent', 'order')
        }),
        ('Dizayn va Joylashuv (Muhim)', {
            'fields': ('children_layout', 'node_type'),
        }),
        ('Kimni biriktiramiz? (Faqat bittasini tanlang)', {
            'fields': ('employee', 'department'),
        }),
    )

    # --- LIST DISPLAY METODLARI (Ro'yxatni chiroyli qilish uchun) ---

    def layout_display(self, obj):
        """Bolalar qanday joylashishini rangli qilib ko'rsatish"""
        if obj.children_layout == 'vertical':
            return format_html('<span style="color:#d97706; font-weight:bold;">⬇ Vertikal (Ustma-ust)</span>')
        return format_html('<span style="color:#059669;">➡ Gorizontal</span>')

    layout_display.short_description = "Joylashuv"

    def node_type_display(self, obj):
        """Tugun turini rangli bejiklar bilan ko'rsatish"""
        if obj.node_type == 'staff_left':
            return format_html(
                '<span style="background-color:#fee2e2; color:#991b1b; padding:3px 8px; border-radius:12px; font-size:11px; font-weight:bold; border:1px solid #fecaca;">⬅ Chap (Shtat)</span>'
            )
        elif obj.node_type == 'staff_right':
            return format_html(
                '<span style="background-color:#e0f2fe; color:#075985; padding:3px 8px; border-radius:12px; font-size:11px; font-weight:bold; border:1px solid #bae6fd;">➡ O\'ng (Shtat)</span>'
            )
        return format_html('<span style="color:#64748b;">Oddiy</span>')


    node_type_display.short_description = "Turi (Pozitsiya)"

    def mapping_info(self, instance):
        """Kim biriktirilganini ko'rsatish"""
        if instance.employee:
            return format_html(
                f'<span style="color:#333;">👤 {instance.employee.last_name} {instance.employee.first_name}</span>')
        if instance.department:
            return format_html(f'<span style="color:#333; font-weight:bold;">🏢 {instance.department.name}</span>')
        return format_html('<span style="color:#999;">❌ Biriktirilmagan</span>')

    mapping_info.short_description = "Biriktirilgan"

    def employee_count_display(self, instance):
        count = instance.get_employee_count()
        if count > 0:
            return format_html(
                f'<span style="background:#dcfce7; color:#166534; padding:2px 8px; border-radius:10px; font-weight:bold;">{count} nafar</span>')
        return "-"

    employee_count_display.short_description = "Xodimlar"

    # --- URLS va VIEWS (Diagrammani chizish va API uchun) ---

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('visual-chart/', self.admin_site.admin_view(self.visual_chart_view), name='simplestructure_visual'),
            path('api-node-details/<int:node_id>/', self.admin_site.admin_view(self.node_details_api),
                 name='simplestructure_api'),
        ]
        return my_urls + urls

    def visual_chart_view(self, request):
        # Vizual ko'rinish sahifasi
        context = dict(
            self.admin_site.each_context(request),
            nodes=SimpleStructure.objects.all(),
            title="Tashkiliy Tuzilma (Vizual)"
        )
        return render(request, 'admin/kadrlar/simplestructure/chart_view.html', context)

    def node_details_api(self, request, node_id):
        # Modal oynasi uchun JSON qaytaruvchi API
        node = get_object_or_404(SimpleStructure, id=node_id)
        employees = node.get_employees()

        data = []
        for emp in employees:
            # Xodimning o'z lavozimlarini olamiz
            pos_list = ", ".join([p.name for p in emp.positions.all()])

            # Rasmni tekshirish
            if emp.photo:
                photo_url = emp.photo.url
            else:
                photo_url = "/static/img/default-user.png"

            data.append({
                'id': emp.id,  # <--- BU ID BO'LISHI SHART
                'full_name': f"{emp.last_name} {emp.first_name}",
                'position': pos_list,
                'photo': photo_url,
                'degree': emp.get_scientific_degree_display(),
            })

        return JsonResponse({
            'node_name': node.name,
            'employees': data
        })