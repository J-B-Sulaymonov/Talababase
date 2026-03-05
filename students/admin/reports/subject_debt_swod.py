from ..base import *
from ..subject_debt import safe_str, to_float_zero


class SubjectDebtSwodReportMixin:
    def _get_subject_debt_swod_data(self, request):
        """
        Ma'lumotlarni yig'ish: Yil (Multi), Sana, Fan holati va boshqa filtrlar bilan.
        """
        # --- 1. FILTRLARNI OLISH ---

        # A) O'QUV YILI (Multi-select)
        all_years_qs = AcademicYear.objects.all().order_by('-name')
        selected_years_str = request.GET.getlist('year')

        target_years = []
        # Agar URLda year parametri bo'lmasa -> BARCHASINI olamiz
        if not request.GET.get('year') and not request.GET.get('status'):
            # (Sahifa yangi ochilganda)
            target_years = [y.id for y in all_years_qs]
            selected_years_str = [str(y.id) for y in all_years_qs]
        else:
            # Agar filtr ishlatilgan bo'lsa
            if selected_years_str:
                target_years = [int(y) for y in selected_years_str if y.isdigit()]
            else:
                # Filtr bosilib, hech narsa tanlanmasa
                target_years = []

        # B) FAN HOLATI (Yopilgan/Yopilmagan)
        selected_subject_status = request.GET.get('subject_status', 'all')

        # C) SANA (Tarixiy holat)
        limit_date_str = request.GET.get('date')
        limit_date_obj = None
        if limit_date_str:
            try:
                limit_date_obj = datetime.strptime(limit_date_str, "%Y-%m-%d").date()
            except ValueError:
                pass

        # D) BOSHQA FILTRLAR
        if request.GET:
            selected_forms = request.GET.getlist('form')
            selected_courses = request.GET.getlist('course')
            selected_statuses = request.GET.getlist('status') if 'status' in request.GET else []
        else:
            selected_forms = []
            selected_courses = []
            selected_statuses = ['active']

        # --- 2. QUERYSET (Prefetch bilan) ---

        # SubjectDebt ni filtrlaymiz
        debt_qs = SubjectDebt.objects.filter(academic_year__id__in=target_years).select_related('subject')

        # Fan holati bo'yicha filtr
        if selected_subject_status == 'closed':
            debt_qs = debt_qs.filter(status='yopildi')
        elif selected_subject_status == 'open':
            debt_qs = debt_qs.filter(status__in=['yopilmadi', 'jarayonda'])

        # Prefetch
        debt_prefetch = Prefetch(
            'subjectdebt_set',
            queryset=debt_qs,
            to_attr='current_debts'
        )

        qs = Student.objects.select_related('group', 'group__specialty').prefetch_related(debt_prefetch)

        # Talabalarni filtrlash
        if selected_statuses: qs = qs.filter(status__in=selected_statuses)
        if selected_forms: qs = qs.filter(education_form__in=selected_forms)
        if selected_courses:
            try:
                cl = [int(c) for c in selected_courses if str(c).isdigit()]
                if cl: qs = qs.filter(course_year__in=cl)
            except ValueError:
                pass

        # --- 3. HISOBLASH VA GURUHLASH ---
        data_map = {}
        grand_total = {
            'count': 0, 'debtors_count': 0, 'debt_subject_count': 0,
            'contract': 0, 'paid': 0, 'debt': 0
        }

        for student in qs:
            spec_name = student.group.specialty.name if student.group and student.group.specialty else "Noma'lum"
            form = student.education_form
            course = student.course_year

            st_calc = 0
            st_paid = 0
            st_debt = 0
            student_subjects_details = []

            # Har bir talabaning qarzlarini aylanamiz
            if hasattr(student, 'current_debts'):
                for debt_obj in student.current_debts:
                    amount = debt_obj.amount or 0
                    real_paid = debt_obj.amount_summ or 0
                    p_date = debt_obj.payment_date

                    # Tarixiy mantiq (Vaqt bo'yicha orqaga qaytish)
                    current_paid = real_paid
                    if limit_date_obj:
                        # Agar to'lov sanasi limit_date dan keyin bo'lsa -> To'lanmagan deb hisoblaymiz
                        if p_date and p_date > limit_date_obj:
                            current_paid = 0
                        # Agar to'lov sanasi yo'q bo'lsa (lekin pul bor bo'lsa), ehtiyotkorlik bilan yondashamiz
                        # (Hozircha o'zgarishsiz qoldiramiz)

                    rem = max(0, amount - current_paid)

                    st_calc += amount
                    st_paid += current_paid
                    st_debt += rem

                    student_subjects_details.append({
                        'subject': debt_obj.subject.name,
                        'amount': amount,
                        'paid': current_paid,
                        'debt': rem,
                        'is_closed': debt_obj.status == 'yopildi'
                    })

            # Map strukturasini tuzish
            if spec_name not in data_map: data_map[spec_name] = {}
            if form not in data_map[spec_name]: data_map[spec_name][form] = {}
            if course not in data_map[spec_name][form]:
                data_map[spec_name][form][course] = {
                    'count': 0, 'debtors_count': 0, 'debt_subject_count': 0,
                    'debt_subject_names': set(),
                    'contract': 0, 'paid': 0, 'debt': 0,
                    'debtor_students_list': []
                }

            item = data_map[spec_name][form][course]

            # Summalarni qo'shish
            item['count'] += 1
            grand_total['count'] += 1
            item['contract'] += st_calc
            grand_total['contract'] += st_calc
            item['paid'] += st_paid
            grand_total['paid'] += st_paid
            item['debt'] += st_debt
            grand_total['debt'] += st_debt

            # Agar qarz bo'lsa yoki "Yopilmagan" filtri tanlanganda qarz bo'lmasa ham
            # ro'yxatga qo'shish kerakmi? SWOD moliya haqida.
            # Shuning uchun faqat moliyaviy qarzi borlarni (st_debt > 0) "Qarzdor" deb hisoblaymiz.
            if st_debt > 0:
                item['debtors_count'] += 1
                grand_total['debtors_count'] += 1

                item['debtor_students_list'].append({
                    'full_name': student.full_name,
                    'hemis_id': student.student_hemis_id,
                    'total_debt': st_debt,
                    'subjects': student_subjects_details
                })

                # Qarzdor fanlarni sanash (faqat moliyaviy qarzi bor fanlar)
                open_subjects = [s['subject'] for s in student_subjects_details if s['debt'] > 0]
                if open_subjects:
                    cnt = len(open_subjects)
                    item['debt_subject_count'] += cnt
                    grand_total['debt_subject_count'] += cnt
                    item['debt_subject_names'].update(open_subjects)

        # --- 4. DATA TAYYORLASH ---
        report_data = []
        counter = 1
        form_priority = {'kunduzgi': 1, 'sirtqi': 2, 'kechki': 3}

        for spec_name, forms in sorted(data_map.items()):
            rows = []
            for form_name, courses in sorted(forms.items(), key=lambda x: form_priority.get(x[0], 10)):
                sub = {
                    'count': 0, 'debtors_count': 0, 'debt_subject_count': 0,
                    'contract': 0, 'paid': 0, 'debt': 0,
                    'debt_subject_names': set(),
                    'debtor_students_list': []
                }
                for course_num, vals in sorted(courses.items()):
                    vals['row_id'] = f"row_{counter}_{form_name}_{course_num}"
                    vals['debt_subjects_str'] = ", ".join(sorted(vals['debt_subject_names']))

                    rows.append({'form': form_name, 'course': f"{course_num}-kurs", 'vals': vals, 'is_total': False})

                    # Subtotal
                    for k in ['count', 'debtors_count', 'debt_subject_count', 'contract', 'paid', 'debt']:
                        sub[k] += vals[k]
                    sub['debt_subject_names'].update(vals['debt_subject_names'])
                    sub['debtor_students_list'].extend(vals['debtor_students_list'])

                sub['row_id'] = f"row_{counter}_{form_name}_total"
                sub['debt_subjects_str'] = ", ".join(sorted(sub['debt_subject_names']))
                rows.append({'form': form_name, 'course': 'Jami', 'vals': sub, 'is_total': True})

            report_data.append({'index': counter, 'spec_name': spec_name, 'rows': rows, 'rowspan': len(rows)})
            counter += 1

        return {
            'report_data': report_data,
            'grand_total': grand_total,
            'selected_years': selected_years_str,
            'limit_date': limit_date_str,
            'selected_subject_status': selected_subject_status,
            'years': all_years_qs,
            'forms': Student.EducationFormChoices.choices,
            'courses': [str(i) for i in range(1, 6)],
            'statuses': Student.StatusChoices.choices,
            'selected_forms': selected_forms,
            'selected_courses': selected_courses,
            'selected_statuses': selected_statuses
        }

    def subject_debt_swod_view(self, request):
        data = self._get_subject_debt_swod_data(request)
        grand_total = data['grand_total']

        # Footer foizlari
        grand_total_percent = {}
        total_contract = float(grand_total['contract'])

        if total_contract > 0:
            total_paid = float(grand_total['paid'])
            total_debt = float(grand_total['debt'])

            paid_raw = (total_paid / total_contract) * 100
            grand_total_percent['paid'] = f"{paid_raw:.1f}%"

            if paid_raw <= 100:
                debt_float = 100.0 - paid_raw
                grand_total_percent['debt'] = f"{debt_float:.1f}%"
            else:
                debt_raw = (total_debt / total_contract) * 100
                grand_total_percent['debt'] = f"{debt_raw:.1f}%"
        else:
            grand_total_percent['paid'] = "0.0%"
            grand_total_percent['debt'] = "0.0%"

        context = admin.site.each_context(request)
        context.update({
            'title': "Fan Qarzlari Swod Hisoboti",
            'report_data': data['report_data'],
            'grand_total': data['grand_total'],
            'grand_total_percent': grand_total_percent,
            'filter_options': {
                'years': data['years'],
                'forms': data['forms'],
                'courses': [(i, f"{i}-kurs") for i in range(1, 6)],
                'statuses': data['statuses']
            },
            'selected_filters': {
                'year': data['selected_years'],
                'form': data['selected_forms'],
                'course': data['selected_courses'],
                'status': data['selected_statuses'],
                'date': data['limit_date'],
                'subject_status': data['selected_subject_status'],
            },
            'current_date': datetime.now().strftime("%d.%m.%Y")
        })
        return render(request, "admin/reports/subject_debt_swod.html", context)

    def export_subject_debt_swod_excel(self, request):
        data = self._get_subject_debt_swod_data(request)
        report_data = data['report_data']
        grand_total = data['grand_total']

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Fan Qarzlari"
        ws.sheet_view.showGridLines = False

        # Styles
        header_fill = PatternFill('solid', fgColor='2C3E50')
        header_font = Font(bold=True, color='FFFFFF', name='Calibri', size=10)

        fill_green_head = PatternFill('solid', fgColor='1E8449')
        fill_blue_head = PatternFill('solid', fgColor='2874A6')
        fill_red_head = PatternFill('solid', fgColor='C0392B')

        fill_green_cell = PatternFill('solid', fgColor='D4EFDF')
        fill_blue_cell = PatternFill('solid', fgColor='D6EAF8')
        fill_red_cell = PatternFill('solid', fgColor='FADBD8')

        fill_total_row = PatternFill('solid', fgColor='ECF0F1')
        font_total = Font(bold=True, name='Calibri', size=10)

        thin_border = Border(left=Side(style='thin', color='AAAAAA'),
                             right=Side(style='thin', color='AAAAAA'),
                             top=Side(style='thin', color='AAAAAA'),
                             bottom=Side(style='thin', color='AAAAAA'))
        align_center = Alignment(horizontal='center', vertical='center', wrap_text=True)
        money_fmt = '#,##0'

        # HEADER
        headers = [
            ('A', '№', 1, 2),
            ('B', "Ta'lim yo'nalishi", 1, 2),
            ('C', "Shakl", 1, 2),
            ('D', "Kurs", 1, 2),
            ('E', "Jami\nTalaba", 1, 2),
            ('F', "Qarzdor\nTalaba", 1, 2),
            ('G', "Qarzdor\nFanlar", 1, 2),
            ('H', "Hisoblangan\nQarz", 1, 2),
            ('I', "To'langan\nSumma", 1, 2),
            ('J', "Qoldiq\nQarz", 1, 2),
        ]

        for col_char, text, colspan, rowspan in headers:
            cell = ws[f"{col_char}2"]
            cell.value = text
            cell.font = header_font;
            cell.fill = header_fill;
            cell.alignment = align_center;
            cell.border = thin_border

            if "Hisoblangan" in text: cell.fill = fill_green_head
            if "To'langan" in text: cell.fill = fill_blue_head
            if "Qoldiq" in text: cell.fill = fill_red_head

            col_idx = openpyxl.utils.column_index_from_string(col_char)
            if col_idx == 2:
                ws.column_dimensions['B'].width = 40
            elif col_idx >= 8:
                ws.column_dimensions[col_char].width = 18
            else:
                ws.column_dimensions[col_char].width = 12

        current_row = 4
        for item in report_data:
            start_row = current_row
            ws.cell(row=current_row, column=1, value=item['index']).alignment = align_center
            ws.cell(row=current_row, column=2, value=item['spec_name']).alignment = Alignment(horizontal='left',
                                                                                              vertical='center',
                                                                                              wrap_text=True)

            for row_data in item['rows']:
                vals = row_data['vals']
                is_total = row_data.get('is_total')
                font = font_total if is_total else Font(name='Calibri')
                bg = fill_total_row if is_total else PatternFill(fill_type=None)

                for c in range(1, 11):
                    cell = ws.cell(row=current_row, column=c)
                    cell.border = thin_border
                    cell.font = font
                    if is_total: cell.fill = bg
                    if c > 2: cell.alignment = align_center

                ws.cell(row=current_row, column=3, value=row_data['form'] if not is_total else "Jami")
                ws.cell(row=current_row, column=4, value=row_data['course'] if not is_total else "-")
                ws.cell(row=current_row, column=5, value=vals['count'])

                d_cell = ws.cell(row=current_row, column=6, value=vals['debtors_count'])
                if vals['debtors_count'] > 0: d_cell.font = Font(bold=True, color='C0392B')

                ws.cell(row=current_row, column=7, value=vals['debt_subject_count'])

                c_cell = ws.cell(row=current_row, column=8, value=vals['contract']);
                c_cell.number_format = money_fmt
                p_cell = ws.cell(row=current_row, column=9, value=vals['paid']);
                p_cell.number_format = money_fmt
                db_cell = ws.cell(row=current_row, column=10, value=vals['debt']);
                db_cell.number_format = money_fmt

                if is_total:
                    c_cell.fill = fill_green_cell
                    p_cell.fill = fill_blue_cell
                    db_cell.fill = fill_red_cell

                current_row += 1

            if item['rowspan'] > 1:
                ws.merge_cells(start_row=start_row, start_column=1, end_row=current_row - 1, end_column=1)
                ws.merge_cells(start_row=start_row, start_column=2, end_row=current_row - 1, end_column=2)
                ws.cell(row=start_row, column=1).alignment = align_center
                ws.cell(row=start_row, column=2).alignment = Alignment(horizontal='left', vertical='center',
                                                                       wrap_text=True)

        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=4)
        ws.cell(row=current_row, column=1, value="UMUMIY JAMI").alignment = Alignment(horizontal='right')

        for c in range(1, 5):
            ws.cell(row=current_row, column=c).fill = header_fill;
            ws.cell(row=current_row, column=c).font = header_font;
            ws.cell(row=current_row, column=c).border = thin_border

        totals = [grand_total['count'], grand_total['debtors_count'], grand_total['debt_subject_count'],
                  grand_total['contract'], grand_total['paid'], grand_total['debt']]
        for idx, val in enumerate(totals, 5):
            cell = ws.cell(row=current_row, column=idx, value=val)
            cell.font = header_font;
            cell.fill = header_fill;
            cell.alignment = align_center;
            cell.border = thin_border
            if idx >= 8: cell.number_format = money_fmt

        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename=Fan_Qarzi_{datetime.now().strftime("%Y-%m-%d")}.xlsx'
        wb.save(response)
        return response

