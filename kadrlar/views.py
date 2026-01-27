from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponseForbidden
from .models import Quiz, QuizPermission, QuizResult, Employee, QuizAnswer, QuizScoringRule, QuizScoringInfo
from .forms import EmployeeAuthForm, DynamicQuizForm


def quiz_login_view(request, quiz_id):
    """ 1-qadam: JSHSHIR orqali kirish """
    quiz = get_object_or_404(Quiz, id=quiz_id, is_active=True)

    if request.method == 'POST':
        form = EmployeeAuthForm(request.POST)
        if form.is_valid():
            pid = form.cleaned_data['pid']
            employee = Employee.objects.get(pid=pid)

            # Ruxsatni tekshirish
            permission = QuizPermission.objects.filter(employee=employee, quiz=quiz).first()

            if not permission:
                messages.error(request, "Sizga ushbu testni topshirishga ruxsat berilmagan.")
            elif not permission.is_active:
                messages.warning(request, "Siz ushbu testni allaqachon topshirgansiz.")
            else:
                # Sessiyaga ma'lumot yozamiz va testga o'tkazamiz
                request.session['quiz_employee_id'] = employee.id
                request.session['quiz_id'] = quiz.id
                return redirect('kadrlar:quiz_process', quiz_id=quiz.id)
    else:
        form = EmployeeAuthForm()

    return render(request, 'admin/kadrlar/quiz/login.html', {'form': form, 'quiz': quiz})


def quiz_process_view(request, quiz_id):
    employee_id = request.session.get('quiz_employee_id')
    sess_quiz_id = request.session.get('quiz_id')

    if not employee_id or sess_quiz_id != quiz_id:
        return redirect('kadrlar:quiz_login', quiz_id=quiz_id)

    employee = get_object_or_404(Employee, id=employee_id)
    quiz = get_object_or_404(Quiz, id=quiz_id)

    permission = get_object_or_404(QuizPermission, employee=employee, quiz=quiz)
    if not permission.is_active:
        return HttpResponseForbidden("Ruxsat yopilgan. Natijangiz qabul qilingan.")

    questions = quiz.questions.all().order_by('order')

    if request.method == 'POST':
        form = DynamicQuizForm(request.POST, questions=questions)
        if form.is_valid():
            results_struct = []
            question_scores = {}
            total_score = 0

            # 1. Javoblarni yig'ish
            for question in questions:
                field_name = f'question_{question.id}'
                selected_answer_id = form.cleaned_data.get(field_name)
                selected_answer = QuizAnswer.objects.get(id=selected_answer_id)

                item = {
                    "question": question.text,
                    "selected": f"{selected_answer.symbol}) {selected_answer.text}",
                    "score": selected_answer.score
                }
                results_struct.append(item)
                question_scores[question.order] = selected_answer.score
                total_score += selected_answer.score

            # 2. KATEGORIYALAR BO'YICHA TAHLIL (QuizScoringRule)
            analysis_result = []
            rules = QuizScoringRule.objects.filter(quiz=quiz)
            category_names = set(rules.values_list('category_name', flat=True))

            for cat_name in category_names:
                cat_rules = rules.filter(category_name=cat_name)
                first_rule = cat_rules.first()

                if not first_rule.related_questions:
                    continue

                try:
                    target_orders = [int(x.strip()) for x in first_rule.related_questions.split(',') if
                                     x.strip().isdigit()]
                except ValueError:
                    target_orders = []

                cat_current_score = 0
                for order in target_orders:
                    cat_current_score += question_scores.get(order, 0)

                cat_conclusion = "Izoh topilmadi"
                for rule in cat_rules:
                    if rule.min_score <= cat_current_score <= rule.max_score:
                        cat_conclusion = rule.conclusion
                        break

                analysis_result.append({
                    "category": cat_name,
                    "score": cat_current_score,
                    "conclusion": cat_conclusion
                })

            # =======================================================
            # 3. UMUMIY BALL XULOSASI (YANGI: QuizScoringInfo)
            # =======================================================
            overall_conclusion = "Umumiy xulosa topilmadi"
            # Umumiy ball qaysi oraliqqa tushishini qidiramiz
            scoring_infos = QuizScoringInfo.objects.filter(quiz=quiz)
            for info in scoring_infos:
                if info.min_score <= total_score <= info.max_score:
                    overall_conclusion = info.conclusion
                    break

            # 4. YAKUNIY JSON
            final_json_data = {
                "answers": results_struct,  # Savol-javoblar
                "analysis": analysis_result,  # Kategoriya tahlili
                "overall_conclusion": overall_conclusion  # <-- YANGI QO'SHILDI
            }

            QuizResult.objects.create(
                quiz=quiz,
                employee=employee,
                struct=final_json_data,
                total_score=total_score
            )

            permission.is_active = False
            permission.save()

            request.session.pop('quiz_employee_id', None)
            request.session.pop('quiz_id', None)

            # Eslatma: Success page endi shunchaki tasdiqlash uchun xizmat qiladi
            return render(request, 'admin/kadrlar/quiz/success.html', {
                'score': total_score,
                'employee': employee,
                'overall_conclusion': overall_conclusion
            })
    else:
        form = DynamicQuizForm(questions=questions)

    return render(request, 'admin/kadrlar/quiz/process.html', {
        'form': form,
        'quiz': quiz,
        'employee': employee
    })