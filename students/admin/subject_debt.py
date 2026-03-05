from .base import *


# =============================================================================
# 📊 FAN QARZLARI ADMIN (SubjectDebtAdmin + Filters + Utils)
# =============================================================================

def safe_str(v):
    if v is None:
        return ""
    try:
        return str(v)
    except Exception:
        return ""

def to_float_zero(v):
    if v is None or v == "":
        return 0.0
    if isinstance(v, Decimal):
        return float(v)
    try:
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).replace(" ", "").replace(",", "")
        return float(s) if s != "" else 0.0
    except Exception:
        return 0.0


class SubjectDebtEducationFormFilter(admin.SimpleListFilter):
    title = "Ta'lim shakli"
    parameter_name = 'student_education_form'

    def lookups(self, request, model_admin):
        # Student modelidagi variantlarni olib kelamiz
        return Student.EducationFormChoices.choices

    def queryset(self, request, queryset):
        if self.value():
            # SubjectDebt -> Student -> education_form bo'yicha filterlash
            return queryset.filter(student__education_form=self.value())
        return queryset

class SubjectDebtCourseFilter(admin.SimpleListFilter):
    title = "Kurs"
    parameter_name = 'student_course'

    def lookups(self, request, model_admin):
        # 1 dan 5 gacha kurslarni chiqarish
        return [(i, f"{i}-kurs") for i in range(1, 6)]

    def queryset(self, request, queryset):
        if self.value():
            # SubjectDebt -> Student -> course_year bo'yicha filterlash
            return queryset.filter(student__course_year=self.value())
        return queryset


class SubjectDebtStudentStatusFilter(admin.SimpleListFilter):
    title = "Talaba statusi"
    parameter_name = 'student_status_custom'

    def lookups(self, request, model_admin):
        return (
            ('all', "Barcha talabalar"),      # Hammasini ko'rish uchun variant
            ('active', "O'qiydi"),            # Default variant
            ('academic', "Akademik ta'tilda"),
            ('expelled', "Chetlashtirilgan"),
            ('graduated', "Bitirgan"),
        )

    def choices(self, cl):
        # Bu metod admin panelda filterni chizib beradi.
        # Agar URL da hech narsa tanlanmagan bo'lsa (self.value() is None),
        # 'active' ni tanlangan (selected) qilib ko'rsatamiz.
        for lookup, title in self.lookup_choices:
            selected = (self.value() == str(lookup)) or (self.value() is None and lookup == 'active')
            yield {
                'selected': selected,
                'query_string': cl.get_query_string({self.parameter_name: lookup}, []),
                'display': title,
            }

    def queryset(self, request, queryset):
        # Agar URL parametri bo'sh bo'lsa -> Default: 'active'
        if self.value() is None or self.value() == 'active':
            return queryset.filter(student__status='active')
        elif self.value() == 'all':
            return queryset  # Hech qanday filtrsiz hammasini qaytaradi
        else:
            # Boshqa variantlar (expelled, academic, graduated)
            return queryset.filter(student__status=self.value())


@admin.register(SubjectDebt)
class SubjectDebtAdmin(admin.ModelAdmin):
    # Shablon manzili
    change_list_template = "admin/students/student/subjectdebt_change_list.html"
    form = SubjectDebtForm

    list_display = (
        'get_student_name',
        'get_subject_name',
        'semester',
        'credit',
        'get_debt_type_display_custom',
        'get_amount_display',
        'get_paid_display',
        'get_diff_display',
        'get_status_display',
    )

    # --- FILTERLAR RO'YXATI ---
    list_filter = (
        SubjectDebtStudentStatusFilter,  # <--- YANGI DEFAULT FILTER (Eng birinchida)
        'debt_type',
        'academic_year',
        'status',  # Fan qarzdorligi statusi (Yopildi/Yopilmadi)
        'semester',
        SubjectDebtCourseFilter,  # Kurs bo'yicha (custom)
        SubjectDebtEducationFormFilter  # Ta'lim shakli bo'yicha (custom)
    )

    search_fields = ('student__full_name', 'subject__name', 'student__student_hemis_id')
    autocomplete_fields = ['student', 'subject', 'academic_year', 'contract']
    list_per_page = 50
    readonly_fields = ['amount']

    class Media:
        js = (
            'admin/js/jquery.init.js',
            'admin/js/disable_text_input_and_open_lookup.js',
            'admin/js/money_input.js',
        )

    # --- STATISTIKA (FOOTER QISMI) ---
    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context)
        if not hasattr(response, 'context_data') or 'cl' not in response.context_data:
            return response

        cl = response.context_data['cl']
        qs = cl.queryset  # Bu yerda filterlangan queryset keladi (status bo'yicha ham)

        total_count = qs.count()
        metrics = qs.aggregate(
            jami_qarz=Sum('amount'),
            jami_tolov=Sum('amount_summ')
        )

        total_debt = metrics['jami_qarz'] or 0
        total_paid = metrics['jami_tolov'] or 0
        remaining = total_debt - total_paid

        response.context_data['footer_stats'] = {
            'total_count': total_count,
            'total_debt': total_debt,
            'total_paid': total_paid,
            'remaining': remaining
        }
        return response

    # --- DISPLAY METODLARI ---
    @admin.display(description="Talaba", ordering='student__full_name')
    def get_student_name(self, obj):
        group_name = obj.student.group.name if obj.student.group else "Guruhsiz"
        # Talaba statusiga qarab rangni o'zgartirish (ixtiyoriy vizual qo'shimcha)
        status_color = "#2c3e50"
        if obj.student.status == 'expelled':
            status_color = "#c0392b"  # Qizil
        elif obj.student.status == 'graduated':
            status_color = "#27ae60"  # Yashil

        return format_html(
            '<div style="line-height: 1.2;">'
            '<span style="font-weight:bold; color:{}; font-size:14px;">{}</span><br>'
            '<span class="group-badge">{}</span>'
            '</div>',
            status_color, obj.student.full_name, group_name
        )

    @admin.display(description="Fan", ordering='subject__name')
    def get_subject_name(self, obj):
        return format_html('<span style="font-weight:500; color:#34495e;">{}</span>', obj.subject.name)

    @admin.display(description="Turi", ordering='debt_type')
    def get_debt_type_display_custom(self, obj):
        if obj.debt_type == 'du':
            return format_html('<span class="status-badge" style="background:#e3f2fd; color:#0d47a1;">DU</span>')
        return format_html('<span class="status-badge" style="background:#fff3e0; color:#e65100;">Perevod</span>')

    @admin.display(description="Hisoblangan", ordering='amount')
    def get_amount_display(self, obj):
        return f"{obj.amount:,.0f}".replace(",", " ") if obj.amount else "0"

    @admin.display(description="To'langan", ordering='amount_summ')
    def get_paid_display(self, obj):
        val = obj.amount_summ or 0
        color = "#2c3e50" if val > 0 else "#b2bec3"
        return format_html('<span style="color:{};">{}</span>', color, f"{val:,.0f}".replace(",", " "))

    @admin.display(description="Qoldiq")
    def get_diff_display(self, obj):
        diff = (obj.amount or 0) - (obj.amount_summ or 0)
        if diff <= 0:
            return format_html('<span style="color: #0ca678; font-weight: bold;">✓</span>')
        return format_html('<span class="status-badge badge-danger">{}</span>', f"{diff:,.0f}".replace(",", " "))

    @admin.display(description="Holati", ordering='status')
    def get_status_display(self, obj):
        if obj.status == 'yopildi':
            return format_html('<span class="status-badge badge-success">Yopildi</span>')
        elif obj.status == 'jarayonda':
            return format_html('<span class="status-badge badge-info" style="color: #fff; background-color: #17a2b8;">Jarayonda</span>')
        return format_html('<span class="status-badge badge-warning">! Yopilmadi</span>')

    # --- EXPORT EXCEL QISMI ---
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('export-excel/', self.admin_site.admin_view(self.export_excel), name='subjectdebt_export_excel'),
        ]
        return custom_urls + urls

    def export_excel(self, request):
        # 1. Filtrlarni qo'llash (Admin paneldagi joriy filtrlar asosida)
        qs_from_form = request.POST.get('changelist_qs')
        if qs_from_form:
            if qs_from_form.startswith('?'):
                qs_from_form = qs_from_form[1:]
            request.GET = QueryDict(qs_from_form)

        try:
            # get_changelist_instance filtrlarni (shu jumladan bizning yangi status filterini) qo'llaydi
            cl = self.get_changelist_instance(request)
            queryset = cl.get_queryset(request)
        except Exception:
            queryset = self.get_queryset(request)

        # 2. Tartiblash va optimizatsiya
        queryset = queryset.select_related('student', 'student__group', 'subject') \
            .order_by('student__full_name', 'student__id')

        # 3. Tanlangan ustunlar
        selected_fields = request.POST.getlist('fields')

        # Config: (Sarlavha, ValueFunc, MergeQilishKerakmi?)
        field_config = {
            'student__full_name': ("F.I.Sh.", lambda o: o.student.full_name, True),
            'student__phone_number': ("Telefon", lambda o: o.student.phone_number, True),
            'student__group__name': ("Guruh", lambda o: o.student.group.name if o.student.group else "", True),
            'student__education_form': ("Ta'lim shakli", lambda o: o.student.get_education_form_display(), True),
            'student__course_year': ("Kurs", lambda o: str(o.student.course_year), True),
            'semester': ("Semestr", lambda o: str(o.semester), True),

            # Fanlar (O'ng taraf - Merge qilinmaydi)
            'subject__name': ("Fan nomi", lambda o: o.subject.name, False),
            'credit': ("Kredit", lambda o: o.credit, False),
            'amount': ("Hisoblangan summa", lambda o: o.amount, False),
            'amount_summ': ("To'langan summa", lambda o: o.amount_summ, False),
            'debt_type': ("Qarz turi", lambda o: o.get_debt_type_display(), False),
            'status': ("Status", lambda o: o.get_status_display(), False),
        }

        order_list = [
            'student__full_name', 'student__phone_number', 'student__group__name',
            'student__education_form', 'student__course_year', 'semester',
            'subject__name', 'credit', 'amount', 'amount_summ',
            'debt_type', 'status'
        ]

        final_fields = [f for f in order_list if f in selected_fields] if selected_fields else order_list

        # 4. Excel yaratish
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Fan Qarzlari"

        # Dizayn
        header_font = Font(bold=True, color="FFFFFF", size=10)
        header_fill = PatternFill("solid", fgColor="2C3E50")
        center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
        thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'),
                             bottom=Side(style='thin'))

        headers = [field_config[f][0] for f in final_fields]
        headers.extend(["Jami hisoblangan", "Jami qarz"])

        ws.append(headers)
        for col_num, _ in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center_align
            cell.border = thin_border

        ws.row_dimensions[1].height = 30

        # 5. GURUHLASH LOGIKASI
        data_rows = list(queryset)
        grouped_data = groupby(data_rows, key=lambda x: x.student.id)

        current_row = 2

        for student_id, debts in grouped_data:
            debts_list = list(debts)

            # Jami hisoblar
            total_calc = sum(d.amount or 0 for d in debts_list)
            total_paid = sum(d.amount_summ or 0 for d in debts_list)
            total_debt = total_calc - total_paid

            start_row = current_row

            for i, obj in enumerate(debts_list):
                row_data = []
                for f in final_fields:
                    val = field_config[f][1](obj)
                    row_data.append(val if val is not None else "")

                # Jami ustunlar (Faqat 1-qatorga qiymat yozamiz)
                if i == 0:
                    row_data.append(total_calc)
                    row_data.append(total_debt)
                else:
                    row_data.append("")
                    row_data.append("")

                # Yozish
                for c_idx, val in enumerate(row_data, 1):
                    cell = ws.cell(row=current_row, column=c_idx)
                    cell.value = val
                    cell.border = thin_border
                    cell.alignment = center_align
                    if isinstance(val, (int, float)):
                        cell.number_format = '#,##0'

                current_row += 1

            # MERGE LOGIKASI
            if len(debts_list) > 1:
                end_row = current_row - 1

                # Chap ustunlar merge
                for col_idx, field_key in enumerate(final_fields, 1):
                    if field_config[field_key][2]:  # is_left == True (Merge qilinadigan ustun)
                        ws.merge_cells(start_row=start_row, start_column=col_idx, end_row=end_row, end_column=col_idx)

                # Jami ustunlar merge
                total_col = len(headers) - 1
                debt_col = len(headers)
                ws.merge_cells(start_row=start_row, start_column=total_col, end_row=end_row, end_column=total_col)
                ws.merge_cells(start_row=start_row, start_column=debt_col, end_row=end_row, end_column=debt_col)

        # Avto kenglik
        for col in ws.columns:
            max_len = 0
            col_letter = col[0].column_letter
            for cell in col:
                try:
                    if len(str(cell.value)) > max_len: max_len = len(str(cell.value))
                except:
                    pass
            ws.column_dimensions[col_letter].width = min(max_len + 3, 50)

        output = BytesIO()
        wb.save(output)
        output.seek(0)

        filename = f"Qarzdorlik_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
        response = HttpResponse(output.getvalue(),
                                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
