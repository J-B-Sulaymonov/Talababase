from ..base import *
from ..subject_debt import safe_str, to_float_zero


class ContingentReportMixin:
    def export_contingent_excel(self, request):
        # 1. FILTRLARNI QABUL QILISH (contingent_view bilan bir xil)
        if request.GET:
            selected_statuses = request.GET.getlist('status')
            selected_forms = request.GET.getlist('form')
            selected_date = request.GET.get('date')
        else:
            selected_statuses = ['active']
            selected_forms = []
            selected_date = ''

        if not selected_statuses and not request.GET:
            selected_statuses = ['active']

        # 2. QUERYSET (contingent_view bilan bir xil mantiq)
        qs = Student.objects.select_related('group', 'group__specialty')

        if selected_forms:
            qs = qs.filter(education_form__in=selected_forms)

        if selected_date:
            qs = qs.filter(created_at__date__lte=selected_date)
            last_order_date_qs = Order.objects.filter(student=OuterRef('pk')).order_by('-order_date').values(
                'order_date')[:1]
            qs = qs.annotate(real_exit_date=Subquery(last_order_date_qs))

            status_conditions = Q()
            date_check = Q(real_exit_date__lte=selected_date) | Q(real_exit_date__isnull=True)

            if 'active' in selected_statuses:
                condition_still_active = Q(status='active')
                condition_was_active = Q(status__in=['expelled', 'graduated', 'academic'],
                                         real_exit_date__gt=selected_date)
                status_conditions |= (condition_still_active | condition_was_active)
            if 'expelled' in selected_statuses:
                status_conditions |= Q(status='expelled') & date_check
            if 'graduated' in selected_statuses:
                status_conditions |= Q(status='graduated') & date_check
            if 'academic' in selected_statuses:
                status_conditions |= Q(status='academic') & date_check

            if status_conditions:
                qs = qs.filter(status_conditions)
        else:
            if selected_statuses:
                qs = qs.filter(status__in=selected_statuses)

        # 3. MA'LUMOTLARNI YIG'ISH
        data_map = {}
        total_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 'total': 0}
        form_totals = {
            'kunduzgi': {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 'total': 0},
            'sirtqi': {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 'total': 0},
            'kechki': {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 'total': 0},
        }

        grouped_data = qs.values('group__specialty__name', 'education_form', 'course_year').annotate(
            count=Count('id')).order_by('group__specialty__name')

        for item in grouped_data:
            spec_name = item['group__specialty__name'] or "Noma'lum yo'nalish"
            form = item['education_form']
            course = item['course_year']
            count = item['count']

            if spec_name not in data_map: data_map[spec_name] = {}
            if form not in data_map[spec_name]: data_map[spec_name][form] = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0,
                                                                             'row_total': 0}

            if course in [1, 2, 3, 4, 5]:
                data_map[spec_name][form][course] += count
                data_map[spec_name][form]['row_total'] += count
                total_counts[course] += count
                total_counts['total'] += count
                if form in form_totals:
                    form_totals[form][course] += count
                    form_totals[form]['total'] += count

        # 4. EXCEL YARATISH
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Kontingent"
        ws.sheet_view.showGridLines = False

        # --- STYLES ---
        header_font = Font(bold=True, color="FFFFFF", size=11)
        header_fill = PatternFill("solid", fgColor="2C3E50")

        # Badge ranglari (HTMLdagi kabi)
        fill_kunduzgi = PatternFill("solid", fgColor="E8F5E9")  # Yashilroq
        font_kunduzgi = Font(color="2E7D32", bold=True)

        fill_sirtqi = PatternFill("solid", fgColor="E3F2FD")  # Ko'kroq
        font_sirtqi = Font(color="1565C0", bold=True)

        fill_kechki = PatternFill("solid", fgColor="FFF3E0")  # Zarg'aldoq
        font_kechki = Font(color="EF6C00", bold=True)

        footer_fill = PatternFill("solid", fgColor="ECF0F1")
        footer_font = Font(bold=True, color="2C3E50")

        grand_total_fill = PatternFill("solid", fgColor="2C3E50")
        grand_total_font = Font(bold=True, color="FFFFFF", size=12)

        thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'),
                             bottom=Side(style='thin'))
        align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
        align_left = Alignment(horizontal="left", vertical="center", wrap_text=True)

        # --- SARLAVHA ---
        current_date_str = selected_date if selected_date else datetime.now().strftime("%d.%m.%Y")
        ws.merge_cells('A1:I1')
        title_cell = ws['A1']
        title_cell.value = f"Talabalar kontingenti hisoboti ({current_date_str})"
        title_cell.font = Font(bold=True, size=14, color="2C3E50")
        title_cell.alignment = align_center

        # --- JADVAL BOSHI ---
        headers = ["№", "Ta'lim yo'nalishi", "Ta'lim shakli", "1-kurs", "2-kurs", "3-kurs", "4-kurs", "5-kurs", "Jami"]
        row_num = 3

        for col_idx, header in enumerate(headers, 1):
            cell = ws.cell(row=row_num, column=col_idx)
            cell.value = header
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = align_center
            cell.border = thin_border

            # Kengliklar
            col_letter = cell.column_letter
            if col_idx == 2:
                ws.column_dimensions[col_letter].width = 40
            elif col_idx == 3:
                ws.column_dimensions[col_letter].width = 15
            elif col_idx == 1:
                ws.column_dimensions[col_letter].width = 5
            else:
                ws.column_dimensions[col_letter].width = 10

        # --- DATA ROWS ---
        row_num += 1
        counter = 1
        form_priority = {'kunduzgi': 1, 'sirtqi': 2, 'kechki': 3}

        for spec_name, forms in data_map.items():
            sorted_forms = sorted(forms.items(), key=lambda item: form_priority.get(item[0], 10))
            start_row = row_num

            for form_name, counts in sorted_forms:
                # 1. Index va Nomi (keyinroq merge qilinadi)
                ws.cell(row=row_num, column=1).value = counter
                ws.cell(row=row_num, column=2).value = spec_name

                # 2. Ta'lim shakli (Rangli badge effekti)
                form_cell = ws.cell(row=row_num, column=3)
                form_cell.value = form_name.capitalize()
                form_cell.alignment = align_center

                if form_name == 'kunduzgi':
                    form_cell.fill = fill_kunduzgi
                    form_cell.font = font_kunduzgi
                elif form_name == 'sirtqi':
                    form_cell.fill = fill_sirtqi
                    form_cell.font = font_sirtqi
                elif form_name == 'kechki':
                    form_cell.fill = fill_kechki
                    form_cell.font = font_kechki

                # 3. Raqamlar
                courses = [1, 2, 3, 4, 5, 'row_total']
                for i, c_key in enumerate(courses, 4):
                    val = counts[c_key]
                    c_cell = ws.cell(row=row_num, column=i)
                    c_cell.value = val if val > 0 else ""
                    c_cell.alignment = align_center

                    # Jami ustuni
                    if c_key == 'row_total':
                        c_cell.font = Font(bold=True)
                        c_cell.fill = PatternFill("solid", fgColor="F8F9FA")

                # Borderni barcha kataklarga qo'yish
                for c in range(1, 10):
                    ws.cell(row=row_num, column=c).border = thin_border
                    if c == 1: ws.cell(row=row_num, column=c).alignment = align_center
                    if c == 2: ws.cell(row=row_num, column=c).alignment = align_left

                row_num += 1

            # Merge qilish (Spec va Index)
            if len(sorted_forms) > 1:
                end_row = row_num - 1
                ws.merge_cells(start_row=start_row, start_column=1, end_row=end_row, end_column=1)
                ws.merge_cells(start_row=start_row, start_column=2, end_row=end_row, end_column=2)

                # Vertical center qilish merge qilingan kataklarni
                ws.cell(row=start_row, column=1).alignment = align_center
                ws.cell(row=start_row, column=2).alignment = align_left

            counter += 1

        # --- FOOTER (Jami qatorlari) ---
        def write_footer_row(label, data_dict, fill_style=footer_fill, font_style=footer_font):
            nonlocal row_num
            ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=2)
            label_cell = ws.cell(row=row_num, column=1)
            label_cell.value = label
            label_cell.alignment = Alignment(horizontal="right", vertical="center")

            # Style apply loop
            for c in range(1, 10):
                cell = ws.cell(row=row_num, column=c)
                cell.fill = fill_style
                cell.font = font_style
                cell.border = thin_border

            # Form nomi
            if "Kunduzgi" in label:
                f_cell = ws.cell(row=row_num, column=3, value="Kunduzgi")
                f_cell.font = font_kunduzgi
                f_cell.fill = fill_kunduzgi
            elif "Sirtqi" in label:
                f_cell = ws.cell(row=row_num, column=3, value="Sirtqi")
                f_cell.font = font_sirtqi
                f_cell.fill = fill_sirtqi
            elif "Kechki" in label:
                f_cell = ws.cell(row=row_num, column=3, value="Kechki")
                f_cell.font = font_kechki
                f_cell.fill = fill_kechki

            # Raqamlar
            for i, c_key in enumerate([1, 2, 3, 4, 5, 'total'], 4):
                val = data_dict[c_key]
                ws.cell(row=row_num, column=i).value = val
                ws.cell(row=row_num, column=i).alignment = align_center

            row_num += 1

        write_footer_row("Jami:", form_totals['kunduzgi'])
        write_footer_row("Jami:", form_totals['sirtqi'])

        # Kechki bor bo'lsa
        if form_totals['kechki']['total'] > 0:
            write_footer_row("Jami:", form_totals['kechki'])

        # Grand Total
        ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=3)
        gt_label = ws.cell(row=row_num, column=1, value="UMUMIY JAMI:")
        gt_label.alignment = Alignment(horizontal="right", vertical="center")

        for c in range(1, 10):
            cell = ws.cell(row=row_num, column=c)
            cell.fill = grand_total_fill
            cell.font = grand_total_font
            cell.border = thin_border
            # Values
            if c >= 4:
                idx = c - 3
                if c == 9:
                    key = 'total'
                else:
                    key = idx
                cell.value = total_counts[key]
                cell.alignment = align_center

        # --- RESPONSE ---
        filename = f"Kontingent_{current_date_str}.xlsx"
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        wb.save(response)
        return response

    def contingent_view(self, request):
        # --- 1. FILTRLARNI QABUL QILISH ---
        if request.GET:
            selected_statuses = request.GET.getlist('status')
            selected_forms = request.GET.getlist('form')
            selected_date = request.GET.get('date')
        else:
            # Default: Hech narsa tanlanmasa faqat Active
            selected_statuses = ['active']
            selected_forms = []
            selected_date = ''

        # Agar status tanlanmagan bo'lsa, default active qilamiz (logika ishlashi uchun)
        if not selected_statuses and not request.GET:
            selected_statuses = ['active']

        # --- 2. QUERYSET TUZISH ---
        qs = Student.objects.select_related('group', 'group__specialty')

        # Filter: Ta'lim shakli (o'zgarmas bo'lgani uchun oddiy filter)
        if selected_forms:
            qs = qs.filter(education_form__in=selected_forms)

        # --- MUHIM QISM: SANA VA STATUS MANTIGI ---
        if selected_date:
            # 1. Avval shu sanagacha bazaga kiritilganlarni olamiz
            qs = qs.filter(created_at__date__lte=selected_date)

            # 2. Har bir talabaning ENG SO'NGGI buyruq sanasini aniqlaymiz.
            # Biz taxmin qilamizki, status o'zgarishiga sabab bo'lgan narsa - bu oxirgi buyruq.
            last_order_date_qs = Order.objects.filter(
                student=OuterRef('pk')
            ).order_by('-order_date').values('order_date')[:1]

            qs = qs.annotate(real_exit_date=Subquery(last_order_date_qs))

            # 3. Murakkab Status Filteri (Tarixiy tiklash)
            status_conditions = Q()

            # A) Agar foydalanuvchi "ACTIVE" (O'qiydi) ni so'rasa:
            if 'active' in selected_statuses:
                # Mantiq:
                # 1. Hozir ham statusi 'active' bo'lsa -> Olamiz.
                # 2. Hozir statusi 'expelled'/'graduated'/'academic' bo'lsa,
                #    LEKIN buyruq sanasi tanlangan sanadan KEYIN bo'lsa -> Demak o'sha kuni u hali Active edi -> Olamiz.

                condition_still_active = Q(status='active')

                # Hozir no-aktiv, lekin o'sha paytda aktiv bo'lganlar (Buyrug'i keyin chiqqan)
                condition_was_active = Q(
                    status__in=['expelled', 'graduated', 'academic'],
                    real_exit_date__gt=selected_date
                )

                # Ikkalasini birlashtiramiz
                status_conditions |= (condition_still_active | condition_was_active)

            # B) Agar foydalanuvchi "EXPELLED" (Chetlashtirilgan) ni so'rasa:
            if 'expelled' in selected_statuses:
                # Mantiq: Hozir statusi 'expelled' VA buyruq sanasi o'sha sanadan oldin yoki teng bo'lsa.
                # Agar bugun chetlashtirsam, kechagi sanada bu shart bajarilmaydi (to'g'ri ishlaydi).
                status_conditions |= Q(status='expelled', real_exit_date__lte=selected_date)

            # C) Boshqa statuslar (Bitirgan va h.k.)
            if 'graduated' in selected_statuses:
                status_conditions |= Q(status='graduated', real_exit_date__lte=selected_date)

            if 'academic' in selected_statuses:
                status_conditions |= Q(status='academic', real_exit_date__lte=selected_date)

            # D) "Hammasi" (Jami) tanlansa yoki hech narsa tanlanmasa
            # Yuqoridagi shartlar ishlatiladi. Agar status_conditions bo'sh bo'lmasa, filterlaymiz.
            if status_conditions:
                qs = qs.filter(status_conditions)

        else:
            # SANA YO'Q BO'LSA - ODDIY STATUS FILTER (Hozirgi holat)
            if selected_statuses:
                qs = qs.filter(status__in=selected_statuses)

        # --- 3. MA'LUMOTLARNI YIG'ISH (Eski kod bilan bir xil) ---
        data_map = {}
        total_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 'total': 0}
        form_totals = {
            'kunduzgi': {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 'total': 0},
            'sirtqi': {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 'total': 0},
            'kechki': {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 'total': 0},
        }

        # Optimallashtirish: annotate qilingan queryni ishlatamiz
        grouped_data = qs.values(
            'group__specialty__name',
            'education_form',
            'course_year'
        ).annotate(count=Count('id')).order_by('group__specialty__name')

        for item in grouped_data:
            spec_name = item['group__specialty__name'] or "Noma'lum yo'nalish"
            form = item['education_form']
            course = item['course_year']
            count = item['count']

            if spec_name not in data_map:
                data_map[spec_name] = {}
            if form not in data_map[spec_name]:
                data_map[spec_name][form] = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 'row_total': 0}

            if course in [1, 2, 3, 4, 5]:
                data_map[spec_name][form][course] += count
                data_map[spec_name][form]['row_total'] += count
                total_counts[course] += count
                total_counts['total'] += count
                if form in form_totals:
                    form_totals[form][course] += count
                    form_totals[form]['total'] += count

        # --- 4. VIEW TAYYORLASH ---
        report_data = []
        counter = 1
        form_priority = {'kunduzgi': 1, 'sirtqi': 2, 'kechki': 3}

        for spec_name, forms in data_map.items():
            rows = []
            sorted_forms = sorted(forms.items(), key=lambda item: form_priority.get(item[0], 10))
            for form_name, counts in sorted_forms:
                rows.append({
                    'form': form_name,
                    'c1': counts[1], 'c2': counts[2], 'c3': counts[3],
                    'c4': counts[4], 'c5': counts[5], 'total': counts['row_total']
                })
            report_data.append({'index': counter, 'spec_name': spec_name, 'rows': rows, 'rowspan': len(rows)})
            counter += 1

        context = admin.site.each_context(request)
        context.update({
            'title': "Talabalar kontingenti",
            'report_data': report_data,
            'total_counts': total_counts,
            'form_totals': form_totals,
            'current_date': selected_date if selected_date else datetime.now().strftime("%Y-%m-%d"),
            'filter_options': {
                'statuses': Student.StatusChoices.choices,
                'forms': Student.EducationFormChoices.choices,
            },
            'selected_filters': {
                'status': selected_statuses,
                'form': selected_forms,
                'date': selected_date
            }
        })
        return render(request, "admin/reports/contingent.html", context)

