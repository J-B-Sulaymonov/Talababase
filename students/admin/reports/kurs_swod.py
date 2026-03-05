from ..base import *
from ..subject_debt import safe_str, to_float_zero


class KursSwodReportMixin:
    def _get_kurs_swod_data(self, request):
        # --- 1. FILTRLAR ---
        all_years_qs = AcademicYear.objects.all().order_by('-name')
        selected_year = request.GET.get('year')
        target_years = []

        if selected_year:
            target_years = [selected_year]
        else:
            active_year = AcademicYear.objects.filter(is_active=True).first()
            if active_year:
                selected_year = str(active_year.id)
                target_years = [str(active_year.id)]

        limit_date = request.GET.get('limit_date')

        if request.GET:
            selected_forms = request.GET.getlist('form')
            selected_courses = request.GET.getlist('course')
            selected_statuses = request.GET.getlist('status') if 'status' in request.GET else []
        else:
            selected_forms = []
            selected_courses = []
            selected_statuses = ['active']

        # --- 2. QUERYSET ---
        qs = Student.objects.select_related('group', 'group__specialty')

        if selected_statuses: qs = qs.filter(status__in=selected_statuses)
        if selected_forms: qs = qs.filter(education_form__in=selected_forms)
        if selected_courses:
            try:
                cl = [int(c) for c in selected_courses if str(c).isdigit()]
                if cl: qs = qs.filter(course_year__in=cl)
            except ValueError:
                pass

        # --- 3. ANNOTATSIYA (O'ZGARTIRILDI) ---
        # Grant summasini shartnoma summasidan ayirib tashlaymiz
        contract_subquery = Contract.objects.filter(
            student=OuterRef('pk'),
            academic_year__id__in=target_years,
            contract_type='contract'
        ).values('student').annotate(
            real_total=Sum(
                F('amount') - Coalesce(F('grant_amount'), Value(Decimal('0')))
            )
        ).values('real_total')

        payment_filters = Q(
            contract__student=OuterRef('pk'),
            contract__academic_year__id__in=target_years,
            contract__contract_type='contract'
        )
        if limit_date: payment_filters &= Q(payment_date__lte=limit_date)

        payment_subquery = Payment.objects.filter(payment_filters).values('contract__student').annotate(
            total=Sum('amount')
        ).values('total')

        qs = qs.annotate(
            contract_sum=Coalesce(Subquery(contract_subquery), Value(Decimal(0))),
            paid_sum=Coalesce(Subquery(payment_subquery), Value(Decimal(0)))
        )

        # --- 4. HISOBLASH ---
        data_map = {}
        grand_total = {'count': 0, 'p0': 0, 'p1_24': 0, 'p25': 0, 'p26_49': 0, 'p50': 0, 'p51_74': 0, 'p75': 0,
                       'p76_99': 0, 'p100': 0, 'contract': 0, 'paid': 0, 'debt': 0}

        patok_configs = [
            {'id': 1, 'date': '1-oktabr', 'percent': 0.25, 'label': '25%'},
            {'id': 2, 'date': '1-yanvar', 'percent': 0.50, 'label': '50%'},
            {'id': 3, 'date': '1-mart', 'percent': 0.75, 'label': '75%'},
            {'id': 4, 'date': '1-may', 'percent': 1.00, 'label': '100%'},
        ]
        patok_stats = [
            {'id': p['id'], 'date': p['date'], 'label': p['label'], 'target_percent': int(p['percent'] * 100),
             'total_contract': 0, 'target_amount': 0, 'paid_amount': 0, 'debt_amount': 0} for p in patok_configs]

        for student in qs:
            spec_name = student.group.specialty.name if student.group and student.group.specialty else "Noma'lum"
            form = student.education_form
            course = student.course_year

            c_sum = int(student.contract_sum) # Bu yerda endi (Contract - Grant) keladi
            p_sum = int(student.paid_sum)
            debt = max(0, c_sum - p_sum)

            # Patok Logikasi
            prev_tgt, prev_paid = 0, 0
            for i, p_conf in enumerate(patok_configs):
                cur_tgt = int(c_sum * p_conf['percent'])
                this_tgt = cur_tgt - prev_tgt

                cur_paid = min(p_sum, cur_tgt)
                this_paid = cur_paid - prev_paid
                this_debt = max(0, this_tgt - this_paid)

                patok_stats[i]['total_contract'] += c_sum
                patok_stats[i]['target_amount'] += this_tgt
                patok_stats[i]['paid_amount'] += this_paid
                patok_stats[i]['debt_amount'] += this_debt

                prev_tgt, prev_paid = cur_tgt, cur_paid

            # Percent
            percent = round((p_sum / c_sum * 100), 1) if c_sum > 0 else 0
            if c_sum <= 0 and p_sum == 0:
                # Agar kontrakt 0 bo'lsa (grant 100% bo'lsa), talaba 100% to'lagan hisoblanadi
                 percent = 100 # yoki 0, vaziyatga qarab. Lekin qarz yo'q.

            # Map to structure
            if spec_name not in data_map: data_map[spec_name] = {}
            if form not in data_map[spec_name]: data_map[spec_name][form] = {}
            if course not in data_map[spec_name][form]:
                data_map[spec_name][form][course] = {'count': 0, 'p0': 0, 'p1_24': 0, 'p25': 0, 'p26_49': 0, 'p50': 0,
                                                     'p51_74': 0, 'p75': 0, 'p76_99': 0, 'p100': 0, 'contract': 0,
                                                     'paid': 0, 'debt': 0}

            item = data_map[spec_name][form][course]
            for k, v in [('count', 1), ('contract', c_sum), ('paid', p_sum), ('debt', debt)]:
                item[k] += v
                grand_total[k] += v

            p_key = 'p0'
            if percent <= 0:
                p_key = 'p0'
            elif 0 < percent < 25:
                p_key = 'p1_24'
            elif 25 <= percent < 26:
                p_key = 'p25'
            elif 26 <= percent < 50:
                p_key = 'p26_49'
            elif 50 <= percent < 51:
                p_key = 'p50'
            elif 51 <= percent < 75:
                p_key = 'p51_74'
            elif 75 <= percent < 76:
                p_key = 'p75'
            elif 76 <= percent < 100:
                p_key = 'p76_99'
            else:
                p_key = 'p100'

            item[p_key] += 1
            grand_total[p_key] += 1

        # Final Report List
        report_data = []
        counter = 1
        form_priority = {'kunduzgi': 1, 'sirtqi': 2, 'kechki': 3}

        for spec_name, forms in sorted(data_map.items()):
            rows = []
            for form_name, courses in sorted(forms.items(), key=lambda x: form_priority.get(x[0], 10)):
                sub = {'count': 0, 'p0': 0, 'p1_24': 0, 'p25': 0, 'p26_49': 0, 'p50': 0, 'p51_74': 0, 'p75': 0,
                       'p76_99': 0, 'p100': 0, 'contract': 0, 'paid': 0, 'debt': 0}
                for course_num, vals in sorted(courses.items()):
                    rows.append({'form': form_name, 'course': f"{course_num}-kurs", 'vals': vals, 'is_total': False})
                    for k in sub: sub[k] += vals[k]
                rows.append({'form': form_name, 'course': 'Jami', 'vals': sub, 'is_total': True})

            report_data.append({'index': counter, 'spec_name': spec_name, 'rows': rows, 'rowspan': len(rows)})
            counter += 1

        return {
            'report_data': report_data,
            'grand_total': grand_total,
            'patok_stats': patok_stats,
            'selected_year': selected_year,
            'limit_date': limit_date,
            'years': all_years_qs,
            'forms': Student.EducationFormChoices.choices,
            'courses': [str(i) for i in range(1, 6)],
            'statuses': Student.StatusChoices.choices,
            'selected_forms': selected_forms,
            'selected_courses': selected_courses,
            'selected_statuses': selected_statuses
        }

    def kurs_swod_view(self, request):
        data = self._get_kurs_swod_data(request)
        grand_total = data['grand_total']

        # --- FOIZLARNI HISOBLASH (YANGILANGAN) ---
        grand_total_percent = {}
        total_count = grand_total['count']
        total_contract = grand_total['contract']

        # 1. Talabalar soni bo'yicha foizlar
        keys_count = ['p0', 'p1_24', 'p25', 'p26_49', 'p50', 'p51_74', 'p75', 'p76_99', 'p100']
        for key in keys_count:
            if total_count > 0:
                percent = (grand_total[key] / total_count) * 100
                grand_total_percent[key] = f"{percent:.1f}%"
            else:
                grand_total_percent[key] = "0.0%"

        # 2. Summalar bo'yicha foizlar (MANTIQ O'ZGARTIRILDI)
        if total_contract > 0:
            # A) To'lov foizini hisoblaymiz va 1 xonagacha yaxlitlaymiz
            paid_raw = (grand_total['paid'] / total_contract) * 100
            paid_str = f"{paid_raw:.1f}"
            paid_float = float(paid_str)

            # B) Qarz foizini hisoblaymiz
            # Agar to'lov 100% dan oshmagan bo'lsa, qarzni [100 - to'lov] qilib olamiz.
            # Bu vizual xatolikni (100.1%) yo'qotadi.
            if paid_float <= 100:
                debt_float = 100.0 - paid_float
                debt_str = f"{debt_float:.1f}"
            else:
                # Agar ortiqcha to'lov bo'lsa (masalan 105%), qarzni o'z holicha hisoblaymiz
                debt_raw = (grand_total['debt'] / total_contract) * 100
                debt_str = f"{debt_raw:.1f}"

            grand_total_percent['paid'] = f"{paid_str}%"
            grand_total_percent['debt'] = f"{debt_str}%"
        else:
            grand_total_percent['paid'] = "0.0%"
            grand_total_percent['debt'] = "0.0%"

        context = admin.site.each_context(request)
        context.update({
            'title': "Kontrakt Swod Hisoboti",
            'report_data': data['report_data'],
            'grand_total': data['grand_total'],
            'grand_total_percent': grand_total_percent,
            'patok_stats': data['patok_stats'],
            'filter_options': {
                'years': data['years'],
                'forms': data['forms'],
                'courses': [(i, f"{i}-kurs") for i in range(1, 6)],
                'statuses': data['statuses']
            },
            'selected_filters': {
                'year': data['selected_year'],
                'form': data['selected_forms'],
                'course': data['selected_courses'],
                'status': data['selected_statuses'],
                'limit_date': data['limit_date']
            },
            'current_date': datetime.now().strftime("%d.%m.%Y")
        })
        return render(request, "admin/reports/kurs_swod.html", context)

    def export_kurs_swod_excel(self, request):
        # 1. Ma'lumotlarni olish
        data = self._get_kurs_swod_data(request)
        report_data = data['report_data']
        grand_total = data['grand_total']
        patok_stats = data['patok_stats']

        # 2. Excel yaratish
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Kontrakt Swod"
        ws.sheet_view.showGridLines = False

        # --- STYLES (DIZAYN) ---
        header_fill = PatternFill('solid', fgColor='2C3E50')
        header_font = Font(bold=True, color='FFFFFF', name='Calibri', size=10)

        # Headerdagi maxsus ranglar
        fill_green_head = PatternFill('solid', fgColor='1E8449')
        fill_blue_head = PatternFill('solid', fgColor='2874A6')
        fill_red_head = PatternFill('solid', fgColor='C0392B')

        # Katakchalar fon ranglari (Jami qatorlar uchun)
        fill_green_cell = PatternFill('solid', fgColor='D4EFDF')
        fill_blue_cell = PatternFill('solid', fgColor='D6EAF8')
        fill_red_cell = PatternFill('solid', fgColor='FADBD8')

        # Yangi foiz qatori uchun ranglar
        fill_pct_label = PatternFill('solid', fgColor='D6EAF8')  # Och ko'k fon label uchun
        fill_pct_cell = PatternFill('solid', fgColor='EBF5FB')  # Juda och ko'k fon raqamlar uchun

        fill_total_row = PatternFill('solid', fgColor='ECF0F1')
        font_total = Font(bold=True, name='Calibri', size=10)

        thin_border = Border(left=Side(style='thin', color='AAAAAA'),
                             right=Side(style='thin', color='AAAAAA'),
                             top=Side(style='thin', color='AAAAAA'),
                             bottom=Side(style='thin', color='AAAAAA'))

        align_center = Alignment(horizontal='center', vertical='center', wrap_text=True)
        align_left = Alignment(horizontal='left', vertical='center', wrap_text=True)
        align_right = Alignment(horizontal='right', vertical='center')

        money_fmt = '#,##0'

        # =========================================================
        # 1. PATOKLAR (YONMA-YON)
        # =========================================================
        patok_colors = ['F39C12', '3498DB', '9B59B6', '27AE60']

        # Asosiy sarlavha
        ws.merge_cells('B1:Q1')
        ws['B1'] = "To'lov Rejasi (Patoklar bo'yicha tahlil)"
        ws['B1'].font = Font(bold=True, size=14, color='2C3E50')
        ws['B1'].alignment = align_center

        # Patoklar boshlanish joyi
        start_row = 3
        base_col = 2  # B ustunidan boshlanadi
        block_width = 4  # Har bir patok 4 ta ustun egallaydi

        for idx, stat in enumerate(patok_stats):
            col_start = base_col + (idx * block_width)
            col_end = col_start + block_width - 1
            current_r = start_row

            # A) Header
            cell = ws.cell(row=current_r, column=col_start)
            ws.merge_cells(start_row=current_r, start_column=col_start, end_row=current_r, end_column=col_end)
            cell.value = f"{stat['id']}-Patok ({stat['label']}) | {stat['date']}"
            cell.fill = PatternFill('solid', fgColor=patok_colors[idx])
            cell.font = Font(bold=True, color='FFFFFF')
            cell.alignment = align_center
            cell.border = thin_border
            current_r += 1

            # B) Body
            metrics = [
                (f"Reja ({stat['target_percent']}%):", stat['target_amount']),
                ("Qoplangan qismi:", stat['paid_amount']),
                ("Muddati o'tgan qarz:", stat['debt_amount'])
            ]

            for label, val in metrics:
                l_cell = ws.cell(row=current_r, column=col_start)
                ws.merge_cells(start_row=current_r, start_column=col_start, end_row=current_r, end_column=col_start + 1)
                l_cell.value = label
                l_cell.alignment = align_left
                l_cell.font = Font(color='555555', size=9)
                l_cell.border = thin_border

                v_cell = ws.cell(row=current_r, column=col_start + 2)
                ws.merge_cells(start_row=current_r, start_column=col_start + 2, end_row=current_r, end_column=col_end)
                v_cell.value = val
                v_cell.number_format = money_fmt
                v_cell.alignment = align_right
                v_cell.font = Font(bold=True, size=10)
                v_cell.border = thin_border

                if "Qoplangan" in label: v_cell.font = Font(bold=True, color='27AE60', size=10)
                if "qarz" in label: v_cell.font = Font(bold=True, color='E74C3C', size=10)
                current_r += 1

        # =========================================================
        # 2. ASOSIY JADVAL HEADERS
        # =========================================================
        table_start_row = 9

        # 1-Qator Headerlari
        headers = [
            ('A', '№', 1, 2),
            ('B', "Ta'lim yo'nalishi", 1, 2),
            ('C', "Shakl", 1, 2),
            ('D', "Kurs", 1, 2),
            ('E', "Talaba\nsoni", 1, 2),
            ('F', "To'lov foizlari (talabalar soni)", 9, 1),
            ('O', "Jami Shartnoma", 1, 2),
            ('P', "To'langan Summa", 1, 2),
            ('Q', "Qarzdorlik", 1, 2),
        ]

        for col_char, text, colspan, rowspan in headers:
            cell = ws[f"{col_char}{table_start_row}"]
            cell.value = text
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = align_center
            cell.border = thin_border

            if "Shartnoma" in text: cell.fill = fill_green_head
            if "To'langan" in text: cell.fill = fill_blue_head
            if "Qarzdorlik" in text: cell.fill = fill_red_head

            if colspan > 1 or rowspan > 1:
                col_idx = openpyxl.utils.column_index_from_string(col_char)
                ws.merge_cells(
                    start_row=table_start_row, start_column=col_idx,
                    end_row=table_start_row + rowspan - 1, end_column=col_idx + colspan - 1
                )

        # 2-Qator Headerlari (Foizlar)
        percents = ["0%", "1-24%", "25%", "26-49%", "50%", "51-74%", "75%", "76-99%", "100%"]
        start_col_idx = 6
        for p in percents:
            cell = ws.cell(row=table_start_row + 1, column=start_col_idx)
            cell.value = p
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = align_center
            cell.border = thin_border
            start_col_idx += 1

        # =========================================================
        # 3. JADVAL BODY
        # =========================================================
        current_row = table_start_row + 2

        for item in report_data:
            spec_start_row = current_row

            cell_idx = ws.cell(row=current_row, column=1, value=item['index'])
            cell_idx.alignment = align_center
            cell_idx.border = thin_border
            cell_idx.font = Font(bold=True)

            cell_name = ws.cell(row=current_row, column=2, value=item['spec_name'])
            cell_name.alignment = align_left
            cell_name.border = thin_border
            cell_name.font = Font(bold=True)

            for row_data in item['rows']:
                is_total = row_data.get('is_total', False)
                vals = row_data['vals']

                row_font = font_total if is_total else Font(name='Calibri', size=10)
                row_fill = fill_total_row if is_total else PatternFill(fill_type=None)

                cols = [
                    (3, row_data['form'] if not is_total else "Jami"),
                    (4, row_data['course'] if not is_total else "-"),
                    (5, vals['count']),
                    (6, vals['p0']), (7, vals['p1_24']), (8, vals['p25']),
                    (9, vals['p26_49']), (10, vals['p50']), (11, vals['p51_74']),
                    (12, vals['p75']), (13, vals['p76_99']), (14, vals['p100']),
                    (15, vals['contract']), (16, vals['paid']), (17, vals['debt'])
                ]

                for col_idx, val in cols:
                    cell = ws.cell(row=current_row, column=col_idx)
                    cell.value = val if val != 0 else ""

                    if col_idx in [15, 16, 17] and val != "":
                        cell.value = val
                        cell.number_format = money_fmt

                    cell.font = row_font
                    cell.fill = row_fill
                    cell.border = thin_border
                    cell.alignment = align_center

                    if is_total:
                        if col_idx == 15: cell.fill = fill_green_cell
                        if col_idx == 16: cell.fill = fill_blue_cell
                        if col_idx == 17: cell.fill = fill_red_cell

                current_row += 1

            if item['rowspan'] > 1:
                ws.merge_cells(start_row=spec_start_row, start_column=1, end_row=current_row - 1, end_column=1)
                ws.merge_cells(start_row=spec_start_row, start_column=2, end_row=current_row - 1, end_column=2)

        # =========================================================
        # 4. FOOTER - RAQAMLAR (UMUMIY JAMI)
        # =========================================================
        cell_label = ws.cell(row=current_row, column=4, value="UMUMIY JAMI:")
        cell_label.font = header_font
        cell_label.fill = header_fill
        cell_label.alignment = align_right

        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=4)
        for c in range(1, 5):
            c_tmp = ws.cell(row=current_row, column=c)
            c_tmp.fill = header_fill
            c_tmp.border = thin_border

        cols_total = [
            (5, grand_total['count']),
            (6, grand_total['p0']), (7, grand_total['p1_24']), (8, grand_total['p25']),
            (9, grand_total['p26_49']), (10, grand_total['p50']), (11, grand_total['p51_74']),
            (12, grand_total['p75']), (13, grand_total['p76_99']), (14, grand_total['p100']),
            (15, grand_total['contract']), (16, grand_total['paid']), (17, grand_total['debt'])
        ]

        for col_idx, val in cols_total:
            cell = ws.cell(row=current_row, column=col_idx)
            cell.value = val
            if col_idx >= 15: cell.number_format = money_fmt
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = align_center
            cell.border = thin_border

        # =========================================================
        # 5. FOOTER - FOIZLAR (YANGI QO'SHILDI)
        # =========================================================
        current_row += 1

        cell_label_pct = ws.cell(row=current_row, column=4, value="FOIZ KO'RSATGICHI:")
        cell_label_pct.font = Font(bold=True, italic=True, color='2C3E50')
        cell_label_pct.fill = fill_pct_label
        cell_label_pct.alignment = align_right

        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=4)
        for c in range(1, 5):
            c_tmp = ws.cell(row=current_row, column=c)
            c_tmp.fill = fill_pct_label
            c_tmp.border = thin_border

        total_cnt = grand_total['count']
        total_sum = grand_total['contract']

        # Oddiy foiz hisoblash funksiyasi
        def get_pct_val(val, total):
            if total > 0:
                return (val / total) * 100
            return 0.0

        # To'lov va Qarz foizlarini maxsus hisoblash
        paid_pct_val = get_pct_val(grand_total['paid'], total_sum)
        paid_pct_str = f"{paid_pct_val:.1f}"
        paid_pct_float = float(paid_pct_str)

        if paid_pct_float <= 100:
            debt_pct_str = f"{100.0 - paid_pct_float:.1f}"
        else:
            debt_pct_val = get_pct_val(grand_total['debt'], total_sum)
            debt_pct_str = f"{debt_pct_val:.1f}"

        cols_percent = [
            (5, "100%"),
            (6, f"{get_pct_val(grand_total['p0'], total_cnt):.1f}%"),
            (7, f"{get_pct_val(grand_total['p1_24'], total_cnt):.1f}%"),
            (8, f"{get_pct_val(grand_total['p25'], total_cnt):.1f}%"),
            (9, f"{get_pct_val(grand_total['p26_49'], total_cnt):.1f}%"),
            (10, f"{get_pct_val(grand_total['p50'], total_cnt):.1f}%"),
            (11, f"{get_pct_val(grand_total['p51_74'], total_cnt):.1f}%"),
            (12, f"{get_pct_val(grand_total['p75'], total_cnt):.1f}%"),
            (13, f"{get_pct_val(grand_total['p76_99'], total_cnt):.1f}%"),
            (14, f"{get_pct_val(grand_total['p100'], total_cnt):.1f}%"),
            (15, "100%"),
            (16, f"{paid_pct_str}%"),  # To'lov
            (17, f"{debt_pct_str}%")  # Qarz (To'g'irlangan)
        ]

        for col_idx, val in cols_percent:
            cell = ws.cell(row=current_row, column=col_idx)
            cell.value = val
            cell.font = Font(bold=True, italic=True)
            cell.fill = fill_pct_cell  # Juda och ko'k fon
            cell.alignment = align_center
            cell.border = thin_border

        # =========================================================
        # 6. USTUN KENGLIKLARI
        # =========================================================
        dims = {
            'A': 5, 'B': 40, 'C': 12, 'D': 10, 'E': 8,
            'F': 11, 'G': 11, 'H': 11, 'I': 11,
            'J': 11, 'K': 11, 'L': 11, 'M': 11,
            'N': 11, 'O': 18, 'P': 18, 'Q': 18
        }
        for col, width in dims.items():
            ws.column_dimensions[col].width = width

        # =========================================================
        # 7. RESPONSE
        # =========================================================
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response[
            'Content-Disposition'] = f'attachment; filename=Kontrakt_Swod_{datetime.now().strftime("%Y-%m-%d")}.xlsx'
        wb.save(response)
        return response

