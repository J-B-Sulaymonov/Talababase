from django.utils import timezone
from datetime import timedelta
from mptt.admin import DraggableMPTTAdmin
from kadrlar.models import SimpleStructure
from django.http import HttpResponse, JsonResponse
from django.utils.safestring import mark_safe
import json
from django.db import models
from django.utils.html import format_html
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import path, reverse
from django.utils.http import urlencode
from django.db.models import Q
from django.contrib.auth import get_user_model
from django import forms
from django.template.response import TemplateResponse
from django.contrib import admin


try:
    from nested_admin import NestedModelAdmin, NestedStackedInline, NestedTabularInline
except ImportError:
    # Fallback agar kutubxona bo'lmasa
    NestedModelAdmin = admin.ModelAdmin
    NestedStackedInline = admin.StackedInline
    NestedTabularInline = admin.TabularInline

from kadrlar.models import (
    Department, Employee, Document, Order,
    Teacher, TeacherAvailability, Weekday, TimeSlot, Quiz, QuizQuestion, QuizAnswer, QuizResultKey, QuizPermission,
    QuizResult, QuizScoringRule, QuizScoringInfo, ArchivedEmployee, Position, OrganizationStructure
)

User = get_user_model()



def is_hr_admin(user):
    """Foydalanuvchi Kadrlar bo'limi yoki Superuser ekanligini tekshiradi."""
    return user.is_superuser or user.groups.filter(name='Kadrlar').exists()


def is_edu_admin(user):
    """Foydalanuvchi O'quv bo'limi yoki Superuser ekanligini tekshiradi."""
    return user.is_superuser or user.groups.filter(name='OquvBolimi').exists()


def kadrlar_structure_view(request):
    """
    YANGI: Faqat Struktura modellarini ko'rsatuvchi ichki dashboard.
    """
    user = request.user
    # Ruxsatni tekshirish (Faqat HR yoki Superuser)
    if not is_hr_admin(user):
        return render(request, 'admin/login.html') # Yoki 403 error

    models_links = []

    models_links.append({
        "title": "Xodimlar Strukturasi",
        "subtitle": "Tugunlar, bo'limlar va xodimlarni bog'lash",
        "url": reverse('admin:kadrlar_simplestructure_changelist'),
        "icon": "fas fa-sitemap",
    })
    models_links.append({
        "title": "Qo'lda structura yasash",
        "subtitle": "Interaktiv tuzilma yaratish va tahrirlash",
        "url": reverse('admin:kadrlar_organizationstructure_changelist'),
        "icon": "fas fa-project-diagram",
    })

    context = {
        'title': "Tashkiliy Tuzilma Sozlamalari",
        'models_links': models_links,
        'stats': {}, # Bu yerda statistika shart emas
        **admin.site.each_context(request),
    }
    # Xuddi general.html shablonidan foydalanaveramiz, chunki tuzilishi bir xil
    return render(request, 'admin/kadrlar/general.html', context)

def kadrlar_general_view(request):
    user = request.user

    def get_qs(model):
        if is_hr_admin(user) or is_edu_admin(user):
            return model.objects.all()
        if model == Teacher:
            return model.objects.filter(employee__department__head_manager=user)
        return model.objects.none()

    teacher_qs = get_qs(Teacher).filter(employee__archived=False)

    # Statistika yig'ish
    stats = {
        'teacher_approved': teacher_qs.filter(schedule_approved=True).count(),
        'teacher_total': teacher_qs.count(),
        'order_total': Order.objects.count() if is_hr_admin(user) else 0,

        # --- QUIZ STATISTIKASI ---
        'quiz_active': Quiz.objects.filter(is_active=True).count(),
        'quiz_total': Quiz.objects.count(),
        'permissions_active': QuizPermission.objects.filter(is_active=True).count(),
        'results_total': QuizResult.objects.count(),
    }

    models_links = []

    # 1. O'qituvchilar
    models_links.append({
        "title": "O'qituvchilar",
        "subtitle": f"Tasdiqlangan: {stats['teacher_approved']} / {stats['teacher_total']}",
        "url": reverse('admin:kadrlar_teacher_changelist'),
        "icon": "fas fa-chalkboard-teacher",
    })
    # 2. HR Admin uchun bo'limlar
    if is_hr_admin(user):
        # --- YANGI: BO'LIMLAR VA KAFEDRALAR ---
        dept_count = Department.objects.count()
        models_links.append({
            "title": "Bo'limlar va Kafedralar",
            "subtitle": f"Jami: {dept_count} ta",
            "url": reverse('admin:kadrlar_department_changelist'),
            "icon": "fas fa-sitemap",  # Estetik ikonka
        })
        models_links.append({
            "title": "Struktura",
            "subtitle": "Diagramma va Tuzilma sozlamalari",
            "url": reverse('admin:kadrlar_structure_subview'),  # Pastda URL nomini belgilaymiz
            "icon": "fas fa-network-wired",
        })
        # ---------------------------------------
        # --- YANGI: LAVOZIMLAR ---
        pos_count = Position.objects.count()
        models_links.append({
            "title": "Lavozimlar (Shtat)",
            "subtitle": f"Jami: {pos_count} ta",
            "url": reverse('admin:kadrlar_position_changelist'),
            "icon": "fas fa-user-tag",  # Ikonka: User Tag
        })
        models_links.append({
            "title": "Buyruqlar",
            "subtitle": f"Jami: {stats['order_total']}",
            "url": reverse('admin:kadrlar_order_changelist'),
            "icon": "fas fa-file-signature",
        })

        doc_count = Document.objects.count()
        models_links.append({
            "title": "Hujjatlar",
            "subtitle": f"Jami: {doc_count} ta fayl",
            "url": reverse('admin:kadrlar_document_changelist'),
            "icon": "fas fa-folder-open",
        })

        archived_count = Employee.objects.filter(archived=True).count()
        models_links.append({
            "title": "Arxiv (Bo'shaganlar)",
            "subtitle": f"Jami: {archived_count} nafar",
            "url": reverse('admin:kadrlar_archivedemployee_changelist'),
            "icon": "fas fa-archive",
        })

    # --- 3. QUIZ BO'LIMLARI ---
    if is_hr_admin(user):
        # A) Quizlar (Testlar)
        models_links.append({
            "title": "Testlar (Quiz)",
            "subtitle": f"Faol: {stats['quiz_active']} / Jami: {stats['quiz_total']}",
            "url": reverse('admin:kadrlar_quiz_changelist'),
            "icon": "fas fa-clipboard-list",
        })

        # B) Testga Ruxsatlar
        models_links.append({
            "title": "Testga ruxsatlar",
            "subtitle": f"Ochiq ruxsatlar: {stats['permissions_active']}",
            "url": reverse('admin:kadrlar_quizpermission_changelist'),
            "icon": "fas fa-unlock-alt",
        })

        # C) Test Natijalari
        models_links.append({
            "title": "Test Natijalari",
            "subtitle": f"Topshirilgan: {stats['results_total']}",
            "url": reverse('admin:kadrlar_quizresult_changelist'),
            "icon": "fas fa-chart-pie",
        })


    context = {
        'title': "Kadrlar Bo'limi Boshqaruv Paneli",
        'models_links': models_links,
        'stats': stats,
        **admin.site.each_context(request),
    }
    return render(request, 'admin/kadrlar/general.html', context)


original_get_urls = admin.site.get_urls


def get_urls():
    custom_urls = [path('kadrlar/general/', admin.site.admin_view(kadrlar_general_view), name='kadrlar_general'),
                   path('kadrlar/structure-settings/', admin.site.admin_view(kadrlar_structure_view),
                        name='kadrlar_structure_subview'),
                   ]
    return custom_urls + original_get_urls()


admin.site.get_urls = get_urls



# O'ZGARISH: NestedStackedInline -> admin.StackedInline
class DocumentInline(admin.StackedInline):
    model = Document
    extra = 0
    fields = ('doc_type', 'file', 'number')

    def has_change_permission(self, request, obj=None):
        if obj and obj.approved and not is_hr_admin(request.user):
            return False
        return True

    def has_add_permission(self, request, obj=None):
        if obj and obj.approved and not is_hr_admin(request.user):
            return False
        return True

    def has_delete_permission(self, request, obj=None):
        if obj and obj.approved and not is_hr_admin(request.user):
            return False
        return True


# O'ZGARISH: NestedStackedInline -> admin.StackedInline
class OrderInline(admin.StackedInline):
    model = Order
    extra = 0
    fields = ('number', 'order_type', 'date', 'document')
    verbose_name = "Buyruq"
    verbose_name_plural = "Buyruqlar"

    def has_add_permission(self, request, obj):
        return is_hr_admin(request.user)

    def has_change_permission(self, request, obj=None):
        return is_hr_admin(request.user)

    def has_delete_permission(self, request, obj=None):
        return is_hr_admin(request.user)


class TeacherAvailabilityInline(admin.StackedInline):
    model = TeacherAvailability
    extra = 0
    max_num = 7
    verbose_name = "Bo'sh vaqt"
    verbose_name_plural = "O'qituvchining bo'sh vaqtlari"

    formfield_overrides = {
        models.ManyToManyField: {'widget': forms.CheckboxSelectMultiple},
    }

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "weekday":
            kwargs["empty_label"] = "Kunni tanlang"
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    # --- RUXSATLAR ---
    def get_readonly_fields(self, request, obj=None):
        # HR uchun hamma narsa readonly
        if is_hr_admin(request.user):
            return ['weekday', 'timeslots']
        return []

    def has_add_permission(self, request, obj=None):
        if is_hr_admin(request.user):
            return False
        if obj and obj.schedule_approved and not is_edu_admin(request.user):
            return False
        return True

    def has_change_permission(self, request, obj=None):
        if is_hr_admin(request.user):
            return True  # Ko'rish uchun ruxsat, lekin readonly bo'ladi
        if obj and obj.schedule_approved and not is_edu_admin(request.user):
            return False
        return True

    def has_delete_permission(self, request, obj=None):
        if is_hr_admin(request.user):
            return False
        if obj and obj.schedule_approved and not is_edu_admin(request.user):
            return False
        return True


