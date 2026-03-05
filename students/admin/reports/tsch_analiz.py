from ..base import *
from ..subject_debt import safe_str, to_float_zero


class TschAnalizReportMixin:
    def tsch_analiz_view(self, request):
        # 1. Barcha mavjud o'quv yillari
        all_years = AcademicYear.objects.all().order_by('-name')
        active_year = AcademicYear.objects.filter(is_active=True).first()

        # 2. URL parametrlar
        selected_year_ids = request.GET.getlist('year')
        active_tab = request.GET.get('active_tab', 'TabKunduzgi')
        view_mode = request.GET.get('view_mode', 'separate')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        if not selected_year_ids:
            if active_year:
                selected_year_ids = [str(active_year.id)]
            elif all_years.exists():
                selected_year_ids = [str(all_years.first().id)]
            else:
                selected_year_ids = []

        selected_year_ids_int = [int(x) for x in selected_year_ids if str(x).isdigit()]

        forms_config = {
            'kunduzgi': {'courses': [1, 2, 3, 4], 'label': "Kunduzgi"},
            'sirtqi': {'courses': [1, 2, 3, 4, 5], 'label': "Sirtqi"},
        }

        reports_list = []

        # STATISTIKA UCHUN O'ZGARUVCHILAR
        global_reasons_map = defaultdict(int)
        du_reasons_map = defaultdict(int)
        student_reasons_map = defaultdict(int)
        global_initiator_map = defaultdict(int)
        global_total_lost_cnt = 0
        du_total_cnt = 0
        student_total_cnt = 0

        initiator_labels = dict(Order.TschChoices.choices)

        # --- AGAR UMUMIY BO'LSA, MA'LUMOTNI SHU YERDA YIG'AMIZ ---
        is_combined = (view_mode == 'general')
        combined_storage = {'kunduzgi': {}, 'sirtqi': {}} if is_combined else None

        for year_id in selected_year_ids:
            target_admission_year = AcademicYear.objects.filter(id=year_id).first()
            if not target_admission_year:
                continue

            # Joriy kursni hisoblash (Faqat alohida rejimda ishlatiladi)
            current_course_num = 0
            if not is_combined and active_year and target_admission_year:
                try:
                    act_y = int(active_year.name[:4])
                    adm_y = int(target_admission_year.name[:4])
                    current_course_num = act_y - adm_y + 1
                except:
                    pass

            # Yillarni tartiblash
            sorted_years = list(AcademicYear.objects.filter(name__gte=target_admission_year.name).order_by('name'))
            course_year_map = {}
            for i in range(1, 6):
                if (i - 1) < len(sorted_years):
                    course_year_map[i] = sorted_years[i - 1].id
                else:
                    course_year_map[i] = None

            # 1-kursga qabul qilinganlar (Kogorta)
            cohort_qs = StudentHistory.objects.filter(
                academic_year=target_admission_year,
                course_year=1
            ).select_related('student', 'group__specialty')

            cohort_ids = list(cohort_qs.values_list('student_id', flat=True))

            if cohort_ids:
                all_history = StudentHistory.objects.filter(student_id__in=cohort_ids)
                history_map = {(h.student_id, h.course_year): h for h in all_history}

                # Shartnomalar va To'lovlar
                all_contracts = Contract.objects.filter(student_id__in=cohort_ids).values('student_id',
                                                                                          'academic_year_id').annotate(
                    sum_amount=Sum('amount'))
                contract_map = {(c['student_id'], c['academic_year_id']): (c['sum_amount'] or 0) for c in all_contracts}

                all_payments = Payment.objects.filter(contract__student_id__in=cohort_ids).values(
                    'contract__student_id', 'contract__academic_year_id').annotate(sum_pay=Sum('amount'))
                payment_map = {(p['contract__student_id'], p['contract__academic_year_id']): (p['sum_pay'] or 0) for p
                               in all_payments}

                # Ketganlar buyruqlari
                expulsion_orders_qs = Order.objects.filter(student_id__in=cohort_ids).filter(
                    Q(order_type__name__icontains="chetlash") |
                    Q(order_type__name__icontains="chiqarish") |
                    Q(order_type__name__icontains="safidan") |
                    Q(order_type__name__icontains="expel")
                )

                # --- SANA BO'YICHA FILTERLASH ---
                if start_date:
                    expulsion_orders_qs = expulsion_orders_qs.filter(order_date__gte=start_date)
                if end_date:
                    expulsion_orders_qs = expulsion_orders_qs.filter(order_date__lte=end_date)
                # --------------------------------

                lost_map = defaultdict(list)
                for o in expulsion_orders_qs.values('student_id', 'order_date'):
                    lost_map[o['student_id']].append(o['order_date'])

                graduated_students = set(
                    Student.objects.filter(id__in=cohort_ids, status='graduated').values_list('id', flat=True))

                # STATISTIKA YIG'ISH (Bu qism doimiy ishlayveradi)
                orders_data = expulsion_orders_qs.values('tsch_reason', 'tsch_by_whom')
                for item in orders_data:
                    raw_reason = item['tsch_reason']
                    initiator_code = item['tsch_by_whom']
                    reason_name = str(raw_reason).strip().capitalize() if raw_reason and str(
                        raw_reason).strip() else "Sababi ko'rsatilmagan"

                    global_reasons_map[reason_name] += 1
                    global_total_lost_cnt += 1

                    initiator_label = initiator_labels.get(initiator_code, initiator_code) or "Ko'rsatilmagan"
                    global_initiator_map[initiator_label] += 1

                    if initiator_code == Order.TschChoices.DU:
                        du_reasons_map[reason_name] += 1
                        du_total_cnt += 1
                    elif initiator_code == Order.TschChoices.STUDENTS:
                        student_reasons_map[reason_name] += 1
                        student_total_cnt += 1

                # --- ASOSIY MA'LUMOT YIG'ISH ---
                current_storage = combined_storage if is_combined else {'kunduzgi': {}, 'sirtqi': {}}

                for h in cohort_qs:
                    if not h.group or not h.group.specialty: continue
                    form_key = h.education_form
                    if form_key not in current_storage: continue

                    spec_name = h.group.specialty.name
                    st_id = h.student_id

                    if spec_name not in current_storage[form_key]:
                        courses_list = forms_config[form_key]['courses']
                        current_storage[form_key][spec_name] = {
                            c: {'count': 0, 'amount': 0, 'lost': 0, 'lost_amount': 0, 'lost_ids': []}
                            for c in courses_list
                        }
                        current_storage[form_key][spec_name]['grad'] = {'graduated': 0, 'failed': 0}

                    previous_lost = False
                    target_courses = forms_config[form_key]['courses']

                    for course in target_courses:
                        if previous_lost: break
                        mapped_year_id = course_year_map.get(course)

                        # Mantiq: 1-kursda hamma bor. Keyingi kurslarda bazada bo'lsa bor.
                        is_present = False
                        if course == 1:
                            is_present = True
                        else:
                            hist = history_map.get((st_id, course))
                            contract_amt = 0
                            if mapped_year_id:
                                contract_amt = contract_map.get((st_id, mapped_year_id), 0)

                            if hist or contract_amt > 0:
                                is_present = True

                            # Fallback (Active yil uchun)
                            if not is_present and active_year and mapped_year_id == active_year.id:
                                if h.student.status == 'active' and h.student.course_year == course:
                                    is_present = True

                        if is_present:
                            cell = current_storage[form_key][spec_name][course]

                            c_amt = 0
                            if mapped_year_id:
                                c_amt = contract_map.get((st_id, mapped_year_id), 0)
                                cell['amount'] += c_amt

                            # Ketganlik tekshiruvi (faqat order bor bo'lsa)
                            is_lost_this_year = False
                            if mapped_year_id:
                                try:
                                    ac_obj = next((y for y in sorted_years if y.id == mapped_year_id), None)
                                    if ac_obj:
                                        y_start = int(ac_obj.name[:4])
                                        d_start = date(y_start, 9, 1)
                                        d_end = date(y_start + 1, 8, 31)
                                        if st_id in lost_map:
                                            # Bu yerda lost_map allaqachon sana bo'yicha filtrlangan
                                            for ld in lost_map[st_id]:
                                                if d_start <= ld <= d_end:
                                                    is_lost_this_year = True
                                                    p_amt = payment_map.get((st_id, mapped_year_id), 0)
                                                    actual_loss = max(0, c_amt - p_amt)

                                                    cell['lost'] += 1
                                                    cell['lost_amount'] += actual_loss
                                                    cell['lost_ids'].append(st_id)
                                                    break
                                except:
                                    pass

                            if is_lost_this_year:
                                previous_lost = True
                            else:
                                cell['count'] += 1

                    if st_id in graduated_students:
                        current_storage[form_key][spec_name]['grad']['graduated'] += 1

            # --- AGAR ALOHIDA REJIM BO'LSA, DARHOL JADVALNI YASAYMIZ ---
            if not is_combined:
                year_report = {
                    'year_name': target_admission_year.name,
                    'current_course': current_course_num,
                    'kunduzgi': self._process_storage_to_rows(current_storage['kunduzgi'], 'kunduzgi', forms_config),
                    'sirtqi': self._process_storage_to_rows(current_storage['sirtqi'], 'sirtqi', forms_config)
                }
                reports_list.append(year_report)

        # --- LOOP TUGADI. AGAR UMUMIY BO'LSA, ENDI JADVAL YASAYMIZ ---
        if is_combined:
            combined_report = {
                'year_name': "Tanlangan yillar (Jami)",
                'current_course': 0,
                'kunduzgi': self._process_storage_to_rows(combined_storage['kunduzgi'], 'kunduzgi', forms_config),
                'sirtqi': self._process_storage_to_rows(combined_storage['sirtqi'], 'sirtqi', forms_config)
            }
            if combined_report['kunduzgi']['rows'] or combined_report['sirtqi']['rows']:
                reports_list.append(combined_report)

        # Statistikalar
        def prepare_stat(data_map, total_count):
            stat_list = []
            for r_name, count in data_map.items():
                stat_list.append({
                    'name': r_name, 'count': count,
                    'percent': (count / total_count * 100) if total_count > 0 else 0
                })
            stat_list.sort(key=lambda x: x['count'], reverse=True)
            return stat_list

        reasons_stat = prepare_stat(global_reasons_map, global_total_lost_cnt)
        du_reasons_stat = prepare_stat(du_reasons_map, du_total_cnt)
        student_reasons_stat = prepare_stat(student_reasons_map, student_total_cnt)
        initiator_stat = prepare_stat(global_initiator_map, global_total_lost_cnt)

        context = admin.site.each_context(request)
        context.update({
            'title': "TSCH Analiz (Kogorta)",
            'all_years': all_years,
            'selected_year_ids': selected_year_ids_int,
            'reports_list': reports_list,
            'active_tab': active_tab,
            'view_mode': view_mode,
            'start_date': start_date,
            'end_date': end_date,
            'reasons_stat': reasons_stat,
            'du_reasons_stat': du_reasons_stat,
            'student_reasons_stat': student_reasons_stat,
            'initiator_stat': initiator_stat,
            'stats_totals': {'du': du_total_cnt, 'student': student_total_cnt, 'global': global_total_lost_cnt}
        })
        return render(request, 'admin/reports/tsch_analiz.html', context)

    # --- YORDAMCHI FUNKSIYA (Rowlarni yasash uchun) ---
    def _process_storage_to_rows(self, specs_data, f_key, forms_config):
        if not specs_data:
            return {'rows': [], 'grand_total': None, 'global_stats': None}

        rows = []
        idx = 1
        target_courses = forms_config[f_key]['courses']

        grand_total = {
            'courses': {c: {'count': 0, 'amount': 0, 'lost': 0, 'display_lost_amt': 0} for c in target_courses},
            'grad': {'graduated': 0}
        }

        for spec, data in sorted(specs_data.items()):
            row = {'index': idx, 'spec': spec, 'cells': [], 'grad': {}}

            for c in target_courses:
                current_data = data[c]

                # Mantiq: count - bu hozirda Active bo'lganlar (yoki shu kursni bitirganlar).
                # Lost - bu shu kurs davomida ketganlar.
                # Demak, kurs boshida: total_at_start = Active + Lost
                total_at_start = current_data['count'] + current_data['lost']
                lost_cnt = current_data['lost']

                percent = (lost_cnt / total_at_start * 100) if total_at_start > 0 else 0

                cell = {
                    'count': total_at_start,  # Talaba soni (boshlanishida)
                    'amount': current_data['amount'],
                    'show_loss': True,
                    'lost': lost_cnt,
                    'lost_amount': current_data['lost_amount'],
                    'percent': percent,
                    'lost_ids': current_data['lost_ids']
                }
                row['cells'].append(cell)

                grand_total['courses'][c]['count'] += cell['count']
                grand_total['courses'][c]['amount'] += cell['amount']
                grand_total['courses'][c]['lost'] += cell['lost']
                grand_total['courses'][c]['display_lost_amt'] += cell['lost_amount']

            grad_cnt = data['grad']['graduated']
            row['grad'] = {'graduated': grad_cnt}
            grand_total['grad']['graduated'] += grad_cnt

            rows.append(row)
            idx += 1

        grand_total_list = [grand_total['courses'][c] for c in target_courses]

        gl_contract = sum(grand_total['courses'][c]['amount'] for c in target_courses)
        gl_lost = sum(grand_total['courses'][c]['display_lost_amt'] for c in target_courses)

        return {
            'rows': rows,
            'grand_total': {'cells': grand_total_list, 'grad': grand_total['grad']},
            'global_stats': {
                'total_contract': gl_contract,
                'total_lost': gl_lost,
                'lost_percent': (gl_lost / gl_contract * 100) if gl_contract > 0 else 0
            }
        }

    def export_tsch_analiz_excel(self, request):
        selected_year_ids = request.GET.getlist('year')
        selected_parts = request.GET.getlist('parts')
        view_mode = request.GET.get('view_mode', 'separate')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        # Agar yil tanlanmagan bo'lsa, active yilni olamiz
        if not selected_year_ids:
            active_year = AcademicYear.objects.filter(is_active=True).first()
            if active_year:
                selected_year_ids = [str(active_year.id)]
            else:
                selected_year_ids = []

        # Excel yaratish
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "TSCH Analiz"
        ws.sheet_view.showGridLines = False

        # --- STYLES (DIZAYN) ---
        fill_header = PatternFill("solid", fgColor="E9ECEF")
        fill_course = PatternFill("solid", fgColor="CED4DA")
        fill_grad = PatternFill("solid", fgColor="D4EDDA")
        fill_loss = PatternFill("solid", fgColor="FFEBEE")

        font_header = Font(bold=True, color="495057", size=10)
        font_grad_title = Font(bold=True, color="155724", size=10)
        font_loss = Font(bold=True, color="C62828")
        font_bold = Font(bold=True)
        font_white_bold = Font(bold=True, color="FFFFFF", size=14)

        fill_dark_blue = PatternFill("solid", fgColor="2C3E50")

        border = Border(left=Side(style='thin', color='DEE2E6'), right=Side(style='thin', color='DEE2E6'),
                        top=Side(style='thin', color='DEE2E6'), bottom=Side(style='thin', color='DEE2E6'))

        align_center = Alignment(horizontal='center', vertical='center', wrap_text=True)
        money_fmt = '#,##0'

        current_row = 1

        # Statistika uchun global o'zgaruvchilar
        global_reasons_map = defaultdict(int)
        global_initiator_map = defaultdict(int)
        global_total_lost_cnt = 0
        global_du_reasons = defaultdict(int)
        global_student_reasons = defaultdict(int)
        global_du_cnt = 0
        global_st_cnt = 0

        # --- UMUMIY REJIM UCHUN YIG'UVCHI O'ZGARUVCHI ---
        general_storage = {
            'kunduzgi': {},
            'sirtqi': {}
        }

        # Qaysi formalar kerakligini aniqlaymiz
        forms_to_export = []
        if 'kunduzgi' in selected_parts: forms_to_export.append(('kunduzgi', [1, 2, 3, 4]))
        if 'sirtqi' in selected_parts: forms_to_export.append(('sirtqi', [1, 2, 3, 4, 5]))

        # --- YILLAR BO'YICHA LOOP ---
        for year_id in selected_year_ids:
            target_year = AcademicYear.objects.filter(id=year_id).first()
            if not target_year: continue

            # Yordamchi ma'lumotlarni tayyorlash
            sorted_years = list(AcademicYear.objects.filter(name__gte=target_year.name).order_by('name'))
            course_year_map = {i: (sorted_years[i - 1].id if (i - 1) < len(sorted_years) else None) for i in
                               range(1, 6)}

            # Kogortani olish (1-kursga kirganlar)
            cohort_qs = StudentHistory.objects.filter(academic_year=target_year, course_year=1).select_related(
                'student', 'group__specialty')
            cohort_ids = list(cohort_qs.values_list('student_id', flat=True))

            if not cohort_ids:
                if view_mode == 'separate' and forms_to_export:
                    ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=10)
                    ws.cell(row=current_row, column=1, value=f"Qabul yili: {target_year.name} - Ma'lumot yo'q")
                    current_row += 2
                continue

            all_history = StudentHistory.objects.filter(student_id__in=cohort_ids)
            history_map = {(h.student_id, h.course_year): h for h in all_history}

            # Kontraktlar
            all_contracts = Contract.objects.filter(student_id__in=cohort_ids).values('student_id',
                                                                                      'academic_year_id').annotate(
                s=Sum('amount'))
            contract_map = {(c['student_id'], c['academic_year_id']): (c['s'] or 0) for c in all_contracts}

            # To'lovlar
            all_payments = Payment.objects.filter(contract__student_id__in=cohort_ids).values('contract__student_id',
                                                                                              'contract__academic_year_id').annotate(
                sum_pay=Sum('amount'))
            payment_map = {(p['contract__student_id'], p['contract__academic_year_id']): (p['sum_pay'] or 0) for p in
                           all_payments}

            # Buyruqlar (Ketganlar)
            expulsion_orders = Order.objects.filter(student_id__in=cohort_ids).filter(
                Q(order_type__name__icontains="chetlash") | Q(order_type__name__icontains="chiqarish") |
                Q(order_type__name__icontains="safidan") | Q(order_type__name__icontains="expel")
            )

            # --- SANA BO'YICHA FILTERLASH ---
            if start_date:
                expulsion_orders = expulsion_orders.filter(order_date__gte=start_date)
            if end_date:
                expulsion_orders = expulsion_orders.filter(order_date__lte=end_date)
            # --------------------------------

            # Statistika yig'ish (Ikkala rejimda ham ishlayveradi)
            for order in expulsion_orders:
                r = str(order.tsch_reason).strip().capitalize() if order.tsch_reason else "Sababi ko'rsatilmagan"
                w = order.tsch_by_whom
                global_reasons_map[r] += 1
                global_total_lost_cnt += 1
                label = dict(Order.TschChoices.choices).get(w, w) or "Ko'rsatilmagan"
                global_initiator_map[label] += 1
                if w == 'du':
                    global_du_reasons[r] += 1
                    global_du_cnt += 1
                elif w == 'student':
                    global_student_reasons[r] += 1
                    global_st_cnt += 1

            # Ketgan sanalar xaritasi
            lost_map = defaultdict(list)
            for o in expulsion_orders.values('student_id', 'order_date'):
                lost_map[o['student_id']].append(o['order_date'])

            graduated_students = set(
                Student.objects.filter(id__in=cohort_ids, status='graduated').values_list('id', flat=True))

            # --- MA'LUMOTLARNI HISOBLASH (FORMALAR KESIMIDA) ---
            for f_key, courses_list in forms_to_export:

                # Agar SEPARATE bo'lsa, Sarlavha yozamiz
                if view_mode == 'separate':
                    ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=20)
                    title_cell = ws.cell(row=current_row, column=1,
                                         value=f"Qabul yili: {target_year.name} ({f_key.upper()})")
                    title_cell.font = font_white_bold
                    title_cell.fill = fill_dark_blue
                    title_cell.alignment = align_center
                    current_row += 2

                    current_row = self._draw_excel_headers(ws, current_row, courses_list, fill_course, fill_grad,
                                                           fill_header, font_header, font_grad_title, font_loss, border,
                                                           align_center)

                # HISOBLASH LOGIKASI
                temp_grouped = {}  # Bu yil uchun lokal

                for h in cohort_qs:
                    if h.education_form != f_key: continue
                    spec = h.group.specialty.name
                    st_id = h.student_id

                    if spec not in temp_grouped:
                        temp_grouped[spec] = {c: {'cnt': 0, 'amt': 0, 'lost_cnt': 0, 'lost_amt': 0} for c in
                                              courses_list}
                        temp_grouped[spec]['grad'] = 0

                    prev_lost = False
                    for c in courses_list:
                        if prev_lost: break
                        y_id = course_year_map.get(c)
                        exists = False
                        if c == 1:
                            exists = True
                        else:
                            if (st_id, c) in history_map:
                                exists = True
                            elif y_id and (st_id, y_id) in contract_map:
                                exists = True

                        if exists:
                            c_amt = contract_map.get((st_id, y_id), 0) if y_id else 0
                            is_lost_this_year = False

                            if y_id:
                                try:
                                    ac_obj = next((y for y in sorted_years if y.id == y_id), None)
                                    if ac_obj:
                                        ystart = int(ac_obj.name[:4])
                                        d1, d2 = date(ystart, 9, 1), date(ystart + 1, 8, 31)
                                        if st_id in lost_map:
                                            for ld in lost_map[st_id]:
                                                if d1 <= ld <= d2:
                                                    is_lost_this_year = True
                                                    p_amt = payment_map.get((st_id, y_id), 0)
                                                    actual_loss = max(0, c_amt - p_amt)

                                                    temp_grouped[spec][c]['lost_cnt'] += 1
                                                    temp_grouped[spec][c]['lost_amt'] += actual_loss
                                                    temp_grouped[spec][c]['amt'] += c_amt
                                                    prev_lost = True
                                                    break
                                except:
                                    pass

                            if not is_lost_this_year:
                                temp_grouped[spec][c]['cnt'] += 1  # Active count
                                temp_grouped[spec][c]['amt'] += c_amt

                    if st_id in graduated_students: temp_grouped[spec]['grad'] += 1

                # --- AGAR SEPARATE BO'LSA - DARHOL YOZAMIZ ---
                if view_mode == 'separate':
                    current_row = self._write_excel_rows(ws, current_row, temp_grouped, courses_list, border, font_loss,
                                                         font_grad_title, font_bold, money_fmt, align_center)
                    current_row += 2  # Yillar orasida joy tashlash

                # --- AGAR GENERAL BO'LSA - YIG'AMIZ ---
                else:
                    target_store = general_storage[f_key]
                    for spec, data in temp_grouped.items():
                        if spec not in target_store:
                            target_store[spec] = {c: {'cnt': 0, 'amt': 0, 'lost_cnt': 0, 'lost_amt': 0} for c in
                                                  courses_list}
                            target_store[spec]['grad'] = 0

                        target_store[spec]['grad'] += data['grad']
                        for c in courses_list:
                            s_cell = target_store[spec][c]
                            d_cell = data[c]
                            s_cell['cnt'] += d_cell['cnt']
                            s_cell['amt'] += d_cell['amt']
                            s_cell['lost_cnt'] += d_cell['lost_cnt']
                            s_cell['lost_amt'] += d_cell['lost_amt']

        # --- AGAR GENERAL REJIM BO'LSA - ENDI YOZAMIZ ---
        if view_mode == 'general':
            # Sarlavha (Bir marta)
            ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=20)
            title_cell = ws.cell(row=current_row, column=1, value="Tanlangan yillar bo'yicha YIG'MA hisobot")
            title_cell.font = font_white_bold
            title_cell.fill = fill_dark_blue
            title_cell.alignment = align_center
            current_row += 2

            for f_key, courses_list in forms_to_export:
                data_map = general_storage[f_key]
                if not data_map: continue

                # Sarlavha (Kunduzgi/Sirtqi)
                ws.cell(row=current_row, column=1, value=f"{f_key.upper()} TA'LIM").font = Font(bold=True, size=12)
                current_row += 1

                # Headerlar
                current_row = self._draw_excel_headers(ws, current_row, courses_list, fill_course, fill_grad,
                                                       fill_header, font_header, font_grad_title, font_loss, border,
                                                       align_center)

                # Qatorlar
                current_row = self._write_excel_rows(ws, current_row, data_map, courses_list, border, font_loss,
                                                     font_grad_title, font_bold, money_fmt, align_center)
                current_row += 2

        # --- YIG'MA STATISTIKA (PASTKI QISM) ---
        if 'stats' in selected_parts and (global_total_lost_cnt > 0):
            if current_row == 1: current_row = 1
            ws.cell(row=current_row, column=1, value="YIG'MA STATISTIKA").font = Font(bold=True, size=14);
            current_row += 2

            def draw_stat_table(title, data_map, total, start_col, r_start):
                r = r_start
                ws.merge_cells(start_row=r, start_column=start_col, end_row=r, end_column=start_col + 2)
                cell = ws.cell(row=r, column=start_col, value=title);
                cell.font = font_bold;
                cell.alignment = align_center;
                cell.fill = PatternFill("solid", fgColor="E9ECEF");
                cell.border = border;
                r += 1
                headers = ["Sabab", "Soni", "Ulushi"]
                for i, h in enumerate(headers):
                    cell = ws.cell(row=r, column=start_col + i, value=h);
                    cell.font = font_bold;
                    cell.border = border;
                    cell.alignment = align_center
                r += 1
                sorted_items = sorted(data_map.items(), key=lambda x: x[1], reverse=True)
                for k, v in sorted_items:
                    ws.cell(row=r, column=start_col, value=k).border = border
                    ws.cell(row=r, column=start_col + 1, value=v).border = border
                    pct = (v / total * 100) if total > 0 else 0
                    ws.cell(row=r, column=start_col + 2, value=f"{pct:.1f}%").border = border;
                    r += 1
                ws.cell(row=r, column=start_col, value="JAMI").font = font_bold;
                ws.cell(row=r, column=start_col).border = border
                ws.cell(row=r, column=start_col + 1, value=total).font = font_bold;
                ws.cell(row=r, column=start_col + 1).border = border
                ws.cell(row=r, column=start_col + 2, value="100%").font = font_bold;
                ws.cell(row=r, column=start_col + 2).border = border

            draw_stat_table("1. DU tashabbusi", global_du_reasons, global_du_cnt, 2, current_row)
            draw_stat_table("2. Talaba tashabbusi", global_student_reasons, global_st_cnt, 6, current_row)
            current_row += max(len(global_du_reasons), len(global_student_reasons)) + 5
            draw_stat_table("3. Tashabbuskor bo'yicha", global_initiator_map, global_total_lost_cnt, 6, current_row)
            draw_stat_table("4. Barcha sabablar", global_reasons_map, global_total_lost_cnt, 2, current_row)

        # Ustun kengliklari
        ws.column_dimensions['A'].width = 5;
        ws.column_dimensions['B'].width = 30
        for i in range(3, 150): ws.column_dimensions[get_column_letter(i)].width = 13

        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        fname = f'TSCH_Analiz_{view_mode}.xlsx'
        response['Content-Disposition'] = f'attachment; filename={fname}'
        wb.save(response)
        return response

    # --- YORDAMCHI METOD: JADVAL HEADERLARINI CHIZISH ---
    def _draw_excel_headers(self, ws, current_row, courses_list, fill_course, fill_grad, fill_header, font_header,
                            font_grad_title, font_loss, border, align_center):
        # HEADER QATOR 1: KURSLAR
        col_ptr = 3
        for c_num in courses_list:
            ws.merge_cells(start_row=current_row, start_column=col_ptr, end_row=current_row, end_column=col_ptr + 4)
            cell = ws.cell(row=current_row, column=col_ptr, value=f"{c_num}-KURS")
            cell.fill = fill_course;
            cell.alignment = align_center;
            cell.border = border
            col_ptr += 5

        # Bitiruv Header
        ws.merge_cells(start_row=current_row, start_column=col_ptr, end_row=current_row + 1, end_column=col_ptr)
        c_grad = ws.cell(row=current_row, column=col_ptr, value="BITIRGANLAR\nSONI")
        c_grad.fill = fill_grad;
        c_grad.font = font_grad_title;
        c_grad.alignment = align_center;
        c_grad.border = border

        # Asosiy Headerlar
        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row + 1, end_column=1)
        ws.cell(row=current_row, column=1, value="№").alignment = align_center;
        ws.cell(row=current_row, column=1).border = border
        ws.merge_cells(start_row=current_row, start_column=2, end_row=current_row + 1, end_column=2)
        ws.cell(row=current_row, column=2, value="Ta'lim yo'nalishi").alignment = align_center;
        ws.cell(row=current_row, column=2).border = border

        current_row += 1

        # HEADER QATOR 2: USTUN NOMALARI
        headers = []
        for _ in courses_list:
            headers.extend(["Talaba soni", "Ketgan soni", "Foizi", "Shartnoma", "Yo'qotilgan summa"])

        for i, h in enumerate(headers, 3):
            cell = ws.cell(row=current_row, column=i, value=h)
            cell.fill = fill_header;
            cell.font = font_header;
            cell.alignment = align_center;
            cell.border = border
            if "Ketgan" in h or "Yo'qotilgan" in h or "Foiz" in h: cell.font = font_loss

        return current_row + 1

    # --- YORDAMCHI METOD: MA'LUMOTLARNI YOZISH ---
    def _write_excel_rows(self, ws, current_row, temp_grouped, courses_list, border, font_loss, font_grad_title,
                          font_bold, money_fmt, align_center):
        idx = 1
        grand_totals = defaultdict(int)

        for spec, data in sorted(temp_grouped.items()):
            ws.cell(row=current_row, column=1, value=idx).border = border
            ws.cell(row=current_row, column=2, value=spec).border = border
            col = 3

            for c in courses_list:
                d = data[c]
                total_students_in_year = d['cnt'] + d['lost_cnt']

                # 1. Talaba soni (Jami)
                ws.cell(row=current_row, column=col, value=total_students_in_year).border = border
                grand_totals[col] += total_students_in_year
                col += 1
                # 2. Ketgan soni
                cell = ws.cell(row=current_row, column=col, value=d['lost_cnt'])
                cell.border = border;
                cell.font = font_loss
                grand_totals[col] += d['lost_cnt']
                col += 1
                # 3. Foizi
                pct = (d['lost_cnt'] / total_students_in_year * 100) if total_students_in_year > 0 else 0
                cell = ws.cell(row=current_row, column=col, value=f"{pct:.1f}%")
                cell.border = border;
                cell.font = font_loss
                col += 1
                # 4. Shartnoma summasi
                cell = ws.cell(row=current_row, column=col, value=d['amt'])
                cell.border = border;
                cell.number_format = money_fmt
                grand_totals[col] += d['amt']
                col += 1
                # 5. Yo'qotilgan summa
                cell = ws.cell(row=current_row, column=col, value=d['lost_amt'])
                cell.border = border;
                cell.number_format = money_fmt;
                cell.font = font_loss
                grand_totals[col] += d['lost_amt']
                col += 1

            # Bitiruv ustuni
            cell = ws.cell(row=current_row, column=col, value=data['grad'])
            cell.border = border;
            cell.font = font_grad_title
            grand_totals[col] += data['grad']

            idx += 1
            current_row += 1

        # FOOTER (JAMI)
        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=2)
        ws.cell(row=current_row, column=1, value="JAMI:").alignment = Alignment(horizontal='right', vertical='center');
        ws.cell(row=current_row, column=1).font = font_bold

        col = 3
        for _ in courses_list:
            # Soni
            ws.cell(row=current_row, column=col, value=grand_totals[col]).border = border;
            ws.cell(row=current_row, column=col).font = font_bold;
            col += 1
            # Ketgan
            ws.cell(row=current_row, column=col, value=grand_totals[col]).border = border;
            ws.cell(row=current_row, column=col).font = font_bold;
            col += 1
            # Foiz
            total_st = grand_totals[col - 2]
            total_ls = grand_totals[col - 1]
            t_pct = (total_ls / total_st * 100) if total_st > 0 else 0
            ws.cell(row=current_row, column=col, value=f"{t_pct:.1f}%").border = border;
            ws.cell(row=current_row, column=col).font = font_loss;
            col += 1
            # Shartnoma
            c_amt = ws.cell(row=current_row, column=col, value=grand_totals[col])
            c_amt.border = border;
            c_amt.font = font_bold;
            c_amt.number_format = money_fmt;
            col += 1
            # Yo'q summa
            l_amt = ws.cell(row=current_row, column=col, value=grand_totals[col])
            l_amt.border = border;
            l_amt.font = font_loss;
            l_amt.number_format = money_fmt;
            col += 1

        # Grad Jami
        g_cell = ws.cell(row=current_row, column=col, value=grand_totals[col])
        g_cell.border = border;
        g_cell.font = font_grad_title

        return current_row + 1

