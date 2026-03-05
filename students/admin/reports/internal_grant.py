from ..base import *
from ..subject_debt import safe_str, to_float_zero


class InternalGrantReportMixin:
    def internal_grant_view(self, request):
        # 1. BARCHA OPTIONLARNI OLISH
        all_years = AcademicYear.objects.all().order_by('-name')
        all_groups = Group.objects.select_related('specialty').all().order_by('name')
        grant_types = Contract.GrantTypeChoices.choices[1:]
        courses = [(1, '1-kurs'), (2, '2-kurs'), (3, '3-kurs'), (4, '4-kurs'), (5, '5-kurs')]

        # 2. URL PARAMETRLARNI OLISH
        selected_years = request.GET.getlist('year')
        selected_grant_types = request.GET.getlist('grant_type')
        selected_courses = request.GET.getlist('course')
        selected_groups = request.GET.getlist('group')
        selected_date = request.GET.get('date')  # <--- YANGI: Sana parametri

        # Default yil
        if not selected_years and not request.GET:
            active_year = AcademicYear.objects.filter(is_active=True).first()
            if active_year:
                selected_years = [str(active_year.id)]

        # 3. QUERYSET TAYYORLASH
        # Faqat granti bor shartnomalar
        qs = Contract.objects.exclude(grant_type='none').select_related(
            'student', 'student__group', 'student__group__specialty', 'academic_year'
        )

        # --- FILTRLAR ---
        if selected_years:
            qs = qs.filter(academic_year_id__in=selected_years)

        if selected_grant_types:
            qs = qs.filter(grant_type__in=selected_grant_types)

        if selected_courses:
            try:
                c_ints = [int(c) for c in selected_courses]
                qs = qs.filter(student__course_year__in=c_ints)
            except ValueError:
                pass

        if selected_groups:
            qs = qs.filter(student__group_id__in=selected_groups)

        # --- YANGI: SANA BO'YICHA FILTR ---
        # Agar sana tanlangan bo'lsa, faqat o'sha sanagacha berilgan grantlarni ko'rsatamiz.
        # Bizda grant_date bor, agar u bo'sh bo'lsa contract_date ga qaraymiz.
        if selected_date:
            qs = qs.filter(
                Q(grant_date__lte=selected_date) |
                Q(grant_date__isnull=True, contract_date__lte=selected_date)
            )

        # 4. STATISTIKA HISOBLASH
        total_students = qs.count()
        total_grant_sum = qs.aggregate(sum=Sum('grant_amount'))['sum'] or 0

        # A) Grant turlari bo'yicha
        by_type_raw = qs.values('grant_type').annotate(
            count=Count('id'),
            sum=Sum('grant_amount')
        ).order_by('-sum')

        by_type_stats = []
        grant_choices = dict(Contract.GrantTypeChoices.choices)

        for item in by_type_raw:
            g_code = item['grant_type']
            by_type_stats.append({
                'code': g_code,
                'name': grant_choices.get(g_code, g_code),
                'count': item['count'],
                'sum': item['sum'],
                'percent': (item['count'] / total_students * 100) if total_students > 0 else 0
            })

        # B) Batafsil ro'yxat va Yo'nalishlar
        detailed_list = []
        spec_stats = {}

        for contract in qs:
            student = contract.student
            spec_name = student.group.specialty.name if student.group and student.group.specialty else "Noma'lum"
            g_type_display = contract.get_grant_type_display()

            detailed_list.append({
                'full_name': student.full_name,
                'hemis_id': student.student_hemis_id,
                'group': student.group.name if student.group else "-",
                'spec': spec_name,
                'course': student.course_year,
                'grant_type': g_type_display,
                'percent': contract.grant_percent,
                'grant_amount': contract.grant_amount,
                'contract_amount': contract.amount
            })

            if spec_name not in spec_stats:
                spec_stats[spec_name] = {'count': 0, 'sum': 0}
            spec_stats[spec_name]['count'] += 1
            spec_stats[spec_name]['sum'] += (contract.grant_amount or 0)

        sorted_spec_stats = sorted(spec_stats.items(), key=lambda x: x[1]['sum'], reverse=True)

        # 5. CONTEXT
        context = admin.site.each_context(request)
        context.update({
            'title': "Ichki Grant va Chegirmalar Tahlili",
            'stats': {'total_students': total_students, 'total_sum': total_grant_sum},
            'by_type_stats': by_type_stats,
            'sorted_spec_stats': sorted_spec_stats,
            'detailed_list': detailed_list,

            # Filter options
            'years': all_years,
            'grant_types': grant_types,
            'all_groups': all_groups,
            'courses': courses,

            # Selected values
            'selected_years': [str(x) for x in selected_years],
            'selected_grant_types': selected_grant_types,
            'selected_courses': [str(x) for x in selected_courses],
            'selected_groups': [str(x) for x in selected_groups],
            'selected_date': selected_date,  # <--- Templatega qaytarish

            'current_date': datetime.now().strftime("%d.%m.%Y")
        })

        return render(request, "admin/reports/internal_grant.html", context)

    def export_internal_grant_excel(self, request):
        # Parametrlarni list sifatida olish
        selected_years = request.GET.getlist('year')
        selected_grant_types = request.GET.getlist('grant_type')
        selected_courses = request.GET.getlist('course')
        selected_groups = request.GET.getlist('group')

        qs = Contract.objects.exclude(grant_type='none').select_related(
            'student', 'student__group', 'student__group__specialty', 'academic_year'
        )

        if selected_years:
            qs = qs.filter(academic_year_id__in=selected_years)
        if selected_grant_types:
            qs = qs.filter(grant_type__in=selected_grant_types)
        if selected_courses:
            try:
                c_ints = [int(c) for c in selected_courses]
                qs = qs.filter(student__course_year__in=c_ints)
            except ValueError:
                pass
        if selected_groups:
            qs = qs.filter(student__group_id__in=selected_groups)

        # Excel yaratish
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Ichki Grantlar"
        ws.sheet_view.showGridLines = False

        # Styles
        header_font = Font(bold=True, color="FFFFFF", size=11)
        header_fill = PatternFill("solid", fgColor="2C3E50")
        border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'),
                        bottom=Side(style='thin'))
        align_center = Alignment(horizontal='center', vertical='center', wrap_text=True)
        money_fmt = '#,##0'

        headers = ["№", "F.I.SH", "ID", "Guruh", "Yo'nalish", "Kurs", "Grant Turi", "Foiz", "Chegirma Summasi",
                   "Asl Kontrakt"]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.font = header_font;
            cell.fill = header_fill;
            cell.alignment = align_center;
            cell.border = border
            w = 15
            if "F.I.SH" in h: w = 35
            if "Yo'nalish" in h: w = 30
            if "Guruh" in h: w = 15
            if "№" in h: w = 5
            ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = w

        row = 2
        total_grant = 0

        for idx, contract in enumerate(qs, 1):
            st = contract.student
            spec = st.group.specialty.name if st.group and st.group.specialty else "-"

            data = [
                idx, st.full_name, st.student_hemis_id, st.group.name if st.group else "-", spec,
                st.course_year, contract.get_grant_type_display(),
                f"{contract.grant_percent}%" if contract.grant_percent else "-",
                contract.grant_amount, contract.amount
            ]
            if contract.grant_amount: total_grant += contract.grant_amount

            for col_idx, val in enumerate(data, 1):
                cell = ws.cell(row=row, column=col_idx, value=val)
                cell.border = border
                if col_idx in [9, 10]: cell.number_format = money_fmt
                if col_idx not in [2, 4, 5]: cell.alignment = align_center

            row += 1

        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=8)
        total_label = ws.cell(row=row, column=1, value="JAMI CHIQIM (GRANT):")
        total_label.font = Font(bold=True, size=12);
        total_label.alignment = Alignment(horizontal='right')
        total_val = ws.cell(row=row, column=9, value=total_grant)
        total_val.font = Font(bold=True, size=12, color="C0392B");
        total_val.number_format = money_fmt;
        total_val.alignment = align_center;
        total_val.border = border

        filename = f"Ichki_Grant_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        wb.save(response)
        return response