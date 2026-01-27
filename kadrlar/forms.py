from django import forms
from .models import Employee, QuizAnswer


class EmployeeAuthForm(forms.Form):
    pid = forms.CharField(
        label="JSHSHIR (PINFL)",
        max_length=14,
        min_length=14,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'JSHSHIR raqamini kiriting...',
            'pattern': '\d{14}',
            'title': "14 ta raqamdan iborat bo'lishi kerak"
        })
    )

    def clean_pid(self):
        pid = self.cleaned_data.get('pid')
        # Faqat "active" statusdagi xodimlarni qidiramiz
        if not Employee.objects.filter(pid=pid, status='active').exists():
            raise forms.ValidationError("Ushbu JSHSHIR bilan faol xodim topilmadi yoki ma'lumot xato.")
        return pid


class DynamicQuizForm(forms.Form):
    def __init__(self, *args, **kwargs):
        questions = kwargs.pop('questions')
        super().__init__(*args, **kwargs)

        for question in questions:
            # Har bir savol uchun javob variantlarini olamiz
            answers = question.answers.all()
            # Variantlar: (id, "A) Javob matni")
            choices = [(ans.id, f"{ans.text}") for ans in answers]

            # Dinamik maydon qo'shamiz
            # required=True -> Hamma savolga javob berish majburiy
            self.fields[f'question_{question.id}'] = forms.ChoiceField(
                label=question.text,
                choices=choices,
                widget=forms.RadioSelect,  # Radio tugma shaklida
                required=True,
                error_messages={'required': "Iltimos, ushbu savolga javob belgilang!"}
            )