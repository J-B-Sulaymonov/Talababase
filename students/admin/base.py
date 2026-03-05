from itertools import groupby
from django.db.models.functions import Coalesce, TruncMonth, Lower
import json
from openpyxl.utils import get_column_letter
from collections import defaultdict
import re
import openpyxl
from import_export.widgets import DateWidget, ForeignKeyWidget, NumberWidget, Widget
from django.core.exceptions import ObjectDoesNotExist
from datetime import datetime, date, timedelta
from django.utils.safestring import mark_safe
from django import forms
from django.core.exceptions import ValidationError
from import_export.admin import ImportExportModelAdmin, ImportExportMixin
from decimal import Decimal, ROUND_HALF_UP
from django.db.models import Count, Prefetch, ExpressionWrapper
from django.db.models import (
    Sum, F, OuterRef, Subquery, Exists, Q, Value, Case, When, DecimalField
)
from django.http import HttpResponse, QueryDict, JsonResponse

from io import BytesIO
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from import_export import resources, fields
from students.models import (
    Country, Region, District,
    Specialty, Group, Student,
    Contract, Payment, Order, OrderType,
    AcademicYear, SubjectDebt, PerevodRate, Subject, Hisobot, StudentHistory,SubjectRate
)
from django.urls import path, reverse
from django.shortcuts import render
from django.contrib import admin

from django import forms

# 1. Maxsus pul maydoni (Probellarni tozalab qabul qiladi)
class MoneyField(forms.DecimalField):
    def to_python(self, value):
        if value in self.empty_values:
            return None
        if isinstance(value, str):
            # 1. Oddiy probelni olib tashlash
            value = value.replace(' ', '')
            # 2. MUHIM: JS formatlashdan kelgan maxsus probelni (\xa0) olib tashlash
            value = value.replace('\xa0', '')
            # 3. Vergulni olib tashlash
            value = value.replace(',', '')
        return super().to_python(value)

    def prepare_value(self, value):
        # Agar qiymat bazadan kelsa, uni shundayligicha qaytaramiz.
        # Formatlashni JS bajaradi.
        return super().prepare_value(value)

# 2. Contract (Shartnoma) uchun Form
class ContractForm(forms.ModelForm):
    # Shartnoma summasi
    amount = MoneyField(
        label="Shartnoma summasi",
        widget=forms.TextInput(attrs={'class': 'money-input', 'style': 'font-weight: bold; font-size: 1.1em; width: 150px;'})
    )
    # Grant summasi (Siz so'ragan joy)
    grant_amount = MoneyField(
        label="Grant summasi",
        required=False,
        widget=forms.TextInput(attrs={'class': 'money-input', 'style': 'width: 150px;'})
    )

    class Meta:
        model = Contract
        fields = '__all__'

class SubjectRateForm(forms.ModelForm):
    amount = MoneyField(
        label="Kontrakt narxi",
        widget=forms.TextInput(attrs={'class': 'money-input', 'style': 'font-weight: bold; font-size: 1.1em; width: 200px;'})
    )

    class Meta:
        model = SubjectRate
        fields = '__all__'

class PerevodRateForm(forms.ModelForm):
    # amount maydoniga "money-input" klassini beramiz
    amount = MoneyField(
        label="1 kredit narxi",
        widget=forms.TextInput(attrs={'class': 'money-input', 'style': 'font-weight: bold; font-size: 1.1em; width: 200px;'})
    )

    class Meta:
        model = PerevodRate
        fields = '__all__'

# 3. Payment (To'lov) uchun Form
class PaymentForm(forms.ModelForm):
    amount = MoneyField(
        label="To'lov summasi",
        widget=forms.TextInput(attrs={'class': 'money-input', 'style': 'font-weight: bold; color: green;'})
    )

    class Meta:
        model = Payment
        fields = '__all__'

# 4. Fan qarzlari uchun Form
class SubjectDebtForm(forms.ModelForm):
    amount = MoneyField(label="Qarzdorlik", required=False, widget=forms.TextInput(attrs={'class': 'money-input'}))
    amount_summ = MoneyField(label="To'lov", required=False, widget=forms.TextInput(attrs={'class': 'money-input'}))

    class Meta:
        model = SubjectDebt
        fields = '__all__'


def students_general_view(request):
    models_links = [
        {"title": "Yo'nalishlar", "subtitle": "Specialty", "url": reverse('admin:students_specialty_changelist'), "icon": "fas fa-graduation-cap"},
        {"title": "Guruhlar",      "subtitle": "Group",     "url": reverse('admin:students_group_changelist'),     "icon": "fas fa-users"},
        {"title": "Davlatlar",     "subtitle": "Country",   "url": reverse('admin:students_country_changelist'),   "icon": "fas fa-globe"},
        {"title": "Viloyatlar",    "subtitle": "Region",    "url": reverse('admin:students_region_changelist'),    "icon": "fas fa-map"},
        {"title": "Tumanlar",      "subtitle": "District",  "url": reverse('admin:students_district_changelist'),  "icon": "fas fa-map-marker-alt"},
        {"title": "Buyruq turlari","subtitle": "OrderType", "url": reverse('admin:students_ordertype_changelist'), "icon": "fas fa-file-signature"},
        {"title": "Buyruqlar",     "subtitle": "Order",     "url": reverse('admin:students_order_changelist'),     "icon": "fas fa-clipboard-list"},
        {"title": "Shartnomalar",  "subtitle": "Contract",  "url": reverse('admin:students_contract_changelist'),  "icon": "fas fa-file-contract"},
        {"title": "To'lovlar",     "subtitle": "Payment",   "url": reverse('admin:students_payment_changelist'),   "icon": "fas fa-money-bill-wave"},
        {"title": "O'quv yillari", "subtitle": "AcademicYear","url": reverse('admin:students_academicyear_changelist'),"icon": "fas fa-calendar-alt"},
        {"title": "Fanlar",        "subtitle": "Subject",   "url": reverse('admin:students_subject_changelist'),   "icon": "fas fa-book"},
        {"title": "Fan qarzlari",  "subtitle": "SubjectDebt","url": reverse('admin:students_subjectdebt_changelist'),"icon": "fas fa-exclamation-triangle"},
        {"title": "Perevod stavkasi","subtitle":"PerevodRate","url": reverse('admin:students_perevodrate_changelist'),"icon":"fas fa-credit-card"},
        {"title": "Fan stavkasi (DU)", "subtitle": "SubjectRate", "url": reverse('admin:students_subjectrate_changelist'), "icon": "fas fa-tags"},
    ]

    # MUHIM: admin.site.each_context bilan global admin kontekstini olish
    context = admin.site.each_context(request)
    # keyin o'zimiz uchun kerakli qiymatlarni qo'shamiz
    context.update({
        'title': "Umumiy bloklar",
        'models_links': models_links,
    })

    return render(request, 'admin/students/general.html', context)

original_get_urls = admin.site.get_urls

def get_urls():
    custom_urls = [
        path('students/general/', admin.site.admin_view(students_general_view), name='students_general'),

    ]
    return custom_urls + original_get_urls()

admin.site.get_urls = get_urls

