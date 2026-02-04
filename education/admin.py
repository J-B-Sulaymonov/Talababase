from django.urls import path
from django.http import JsonResponse
from django.contrib import admin
from django.db.models import Sum, Q
from students.models import Group
from .models import EducationPlan, PlanSubject, Workload, Stream, SubGroup
from django import forms


@admin.register(SubGroup)
class SubGroupAdmin(admin.ModelAdmin):
    # Ro'yxatda ko'rinishi
    list_display = ('name', 'group', )

    # Qidiruv (Guruh nomi yoki guruhcha nomi bo'yicha)
    search_fields = ('group__name', 'name')

    # Filtrlash (Yo'nalish va O'quv yili bo'yicha)
    list_filter = ('name',)

    # Tartiblash
    ordering = ('group__name', 'name')



class PlanSubjectInline(admin.TabularInline):
    model = PlanSubject
    extra = 0
    min_num = 0

    fields = (
        'subject',
        'total_hours',
        'lecture_hours',
        'practice_hours',
        'lab_hours',
        'seminar_hours',
        'semester',
        'semester_time',
        'subject_type',
        'credit',
    )

    autocomplete_fields = ['subject']

    class Media:
        css = {
            'all': ('admin/css/custom_inline.css',)
        }


@admin.register(EducationPlan)
class EducationPlanAdmin(admin.ModelAdmin):

    list_display = (
        'name_display',
        'specialty',
        'academic_year',
        'course',
        'get_total_credits',
        'created_at'
    )
    list_filter = ('academic_year', 'specialty', 'course')
    search_fields = ('specialty__name', 'academic_year__name')

    inlines = [PlanSubjectInline]
    save_on_top = True
    list_per_page = 20

    def name_display(self, obj):
        return str(obj)

    name_display.short_description = "Reja nomi"

    def get_total_credits(self, obj):
        """Rejadagi barcha fanlar kreditlari yig'indisi"""
        # Sum credits from related subjects
        total = obj.subjects.aggregate(Sum('credit'))['credit__sum']
        return total or 0

    get_total_credits.short_description = "Jami Kredit"


@admin.register(PlanSubject)
class PlanSubjectAdmin(admin.ModelAdmin):
    list_display = ('subject', 'education_plan', 'semester', 'credit')
    search_fields = ('subject__name', 'education_plan__specialty__name')
    list_filter = ('education_plan__course', 'education_plan__academic_year')

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        return queryset, use_distinct


class StreamInline(admin.TabularInline):
    model = Stream
    extra = 0
    show_change_link = True

    # Maydonlar ketma-ketligi
    fields = ('name', 'lesson_type', 'teacher', 'groups', 'sub_groups')

    autocomplete_fields = ['teacher']

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        # 1. Widgetni SELECT ga o'zgartirish
        if db_field.name in ["groups", "sub_groups"]:
            # CheckboxSelectMultiple o'rniga SelectMultiple ishlatamiz
            # style orqali o'lchamini to'g'irlaymiz
            kwargs['widget'] = forms.SelectMultiple(attrs={
                'style': 'width: 250px; height: 120px;',
                'class': 'browser-default'  # Ba'zi mavzularda chiroyli ko'rinish uchun
            })

        # 2. Filtrlash logikasi (Eski kod o'zgarishsiz qoladi)
        if request.resolver_match.kwargs.get('object_id'):
            workload_id = request.resolver_match.kwargs.get('object_id')
            try:
                workload = Workload.objects.get(pk=workload_id)

                if db_field.name == "groups":
                    kwargs["queryset"] = workload.groups.all().order_by('name')

                if db_field.name == "sub_groups":
                    kwargs["queryset"] = SubGroup.objects.filter(
                        group__in=workload.groups.all()
                    ).select_related('group').order_by('group__name', 'name')

            except Workload.DoesNotExist:
                pass
        else:
            if db_field.name in ["groups", "sub_groups"]:
                kwargs["queryset"] = Group.objects.none()

        return super().formfield_for_manytomany(db_field, request, **kwargs)


# --------------------------------------------------------------------------
# 2. WORKLOAD FORM (Sizning kodingiz asosida)
# --------------------------------------------------------------------------
class WorkloadAdminForm(forms.ModelForm):
    class Meta:
        model = Workload
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Queryset filtrlash logikasi (Sizdagi eski kod bilan bir xil)
        if self.data:
            self.fields['plan_subjects'].queryset = PlanSubject.objects.all()
            self.fields['groups'].queryset = Group.objects.all()
        elif self.instance.pk:
            if self.instance.subject:
                self.fields['plan_subjects'].queryset = PlanSubject.objects.filter(
                    subject=self.instance.subject
                ).select_related('education_plan', 'education_plan__specialty')

            # Guruhlarni filtrlash
            saved_plans = self.instance.plan_subjects.all()
            if saved_plans.exists():
                spec_ids = saved_plans.values_list('education_plan__specialty', flat=True).distinct()
                self.fields['groups'].queryset = Group.objects.filter(specialty__in=spec_ids).order_by('name')
            else:
                self.fields['groups'].queryset = Group.objects.none()
        else:
            self.fields['plan_subjects'].queryset = PlanSubject.objects.none()
            self.fields['groups'].queryset = Group.objects.none()


# --------------------------------------------------------------------------
# 3. WORKLOAD ADMIN (To'liq yig'ilgan)
# --------------------------------------------------------------------------
@admin.register(Workload)
class WorkloadAdmin(admin.ModelAdmin):
    form = WorkloadAdminForm

    # --------------------------------------------------------
    # 1. JADVAL KO'RINISHI (LIST DISPLAY)
    # --------------------------------------------------------
    list_display = ('subject', 'get_specialty_names', 'get_group_names', 'calculate_total_hours')

    search_fields = ('subject__name',)
    autocomplete_fields = ['subject']

    # Inline (Patoklarni qo'shish qismi)
    inlines = [StreamInline]

    class Media:
        js = ('admin/js/workload.js',)
        css = {
            'all': ('admin/css/workload_custom.css',)
        }

    # --------------------------------------------------------
    # 2. BAZA OPTIMIZATSIYASI (N+1 MUAMMOSINI YECHISH)
    # --------------------------------------------------------
    def get_queryset(self, request):
        """
        Admin panelda har bir qator uchun alohida so'rov yubormaslik uchun
        guruhlar va ularning yo'nalishlarini oldindan 'join' qilamiz.
        """
        qs = super().get_queryset(request)
        return qs.prefetch_related('groups', 'groups__specialty')

    # --------------------------------------------------------
    # 3. JADVAL UCHUN YANGI USTUNLAR
    # --------------------------------------------------------
    def get_specialty_names(self, obj):
        """Fan qaysi yo'nalishlarga o'tilayotganini chiqaradi"""
        # Guruhlarning yo'nalishlarini yig'ib, takrorlanmas (set) qilamiz
        specialties = set()
        for group in obj.groups.all():
            if hasattr(group, 'specialty') and group.specialty:
                specialties.add(group.specialty.name)

        return ", ".join(specialties)

    get_specialty_names.short_description = "Yo'nalishlar"

    def get_group_names(self, obj):
        """Guruhlar nomlarini vergul bilan ajratib chiqaradi"""
        # Guruh nomlarini ro'yxatga olamiz
        groups = [group.name for group in obj.groups.all()]
        return ", ".join(groups)

    get_group_names.short_description = "Guruhlar"

    # --------------------------------------------------------
    # 4. CUSTOM URL VA AJAX VIEWS (ESKISI BILAN BIR XIL)
    # --------------------------------------------------------
    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('ajax/get-plans/', self.admin_site.admin_view(self.get_plans_view), name='ajax_get_plans'),
            path('ajax/get-groups/', self.admin_site.admin_view(self.get_groups_view), name='ajax_get_groups'),
        ]
        return my_urls + urls

    def get_plans_view(self, request):
        """Fan tanlanganda rejalarni qaytaruvchi AJAX"""
        subject_id = request.GET.get('subject_id')
        results = []
        if subject_id:
            plans = PlanSubject.objects.filter(subject_id=subject_id).select_related('education_plan',
                                                                                     'education_plan__specialty')
            for p in plans:
                results.append({
                    'id': str(p.id),
                    'text': f"{p.education_plan.specialty.name} | {p.semester}-sem | {p.education_plan.academic_year}"
                })
        return JsonResponse({'results': results})

    def get_groups_view(self, request):
        """Rejalar tanlanganda guruhlarni qaytaruvchi AJAX"""
        plan_ids_str = request.GET.get('plan_ids', '')
        results = []

        if plan_ids_str:
            plan_ids = [x for x in plan_ids_str.split(',') if x.isdigit()]
            if plan_ids:
                selected_plans = PlanSubject.objects.filter(id__in=plan_ids).select_related('education_plan')
                filter_q = Q()
                for ps in selected_plans:
                    spec_id = ps.education_plan.specialty_id
                    filter_q |= Q(specialty_id=spec_id)

                if filter_q:
                    groups = Group.objects.filter(filter_q).distinct().order_by('name')
                    for g in groups:
                        results.append({'id': str(g.id), 'text': g.name})

        return JsonResponse({'results': results})