from .base import *
from .subject_debt import safe_str, to_float_zero


from .reports.contingent import ContingentReportMixin
from .reports.kurs_swod import KursSwodReportMixin
from .reports.subject_debt_swod import SubjectDebtSwodReportMixin
from .reports.tsch_analiz import TschAnalizReportMixin
from .reports.internal_grant import InternalGrantReportMixin


@admin.register(Hisobot)
class HisobotAdmin(ContingentReportMixin, KursSwodReportMixin, SubjectDebtSwodReportMixin, TschAnalizReportMixin, InternalGrantReportMixin, admin.ModelAdmin):
    search_fields = []
    list_filter = []

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('contingent/', self.admin_site.admin_view(self.contingent_view), name='hisobot_contingent'),
            path('contingent/export/', self.admin_site.admin_view(self.export_contingent_excel), name='hisobot_contingent_export'),

            path('kurs-swod/', self.admin_site.admin_view(self.kurs_swod_view), name='hisobot_kurs_swod'),
            path('kurs-swod/export/', self.admin_site.admin_view(self.export_kurs_swod_excel), name='hisobot_kurs_swod_export'),

            path('subject-debt-swod/', self.admin_site.admin_view(self.subject_debt_swod_view), name='hisobot_subject_debt_swod'),
            path('subject-debt-swod/export/', self.admin_site.admin_view(self.export_subject_debt_swod_excel), name='hisobot_subject_debt_swod_export'),

            path('tsch-analiz/', self.admin_site.admin_view(self.tsch_analiz_view), name='hisobot_tsch_analiz'),
            path('tsch-analiz/export/', self.admin_site.admin_view(self.export_tsch_analiz_excel),
                 name='hisobot_tsch_analiz_export'),

            path('internal-grant/', self.admin_site.admin_view(self.internal_grant_view), name='hisobot_internal_grant'),
            path('internal-grant/export/', self.admin_site.admin_view(self.export_internal_grant_excel), name='hisobot_internal_grant_export'),
        ]
        return my_urls + urls

    def changelist_view(self, request, extra_context=None):
        """
        Hisobot menyusi bosilganda chiqadigan ASOSIY sahifa (4 ta knopkali)
        """
        # 1. MUHIM: Admin saytining global kontekstini olamiz (bunda menyu, user va boshqalar bor)
        context = admin.site.each_context(request)

        # 2. O'zimizning maxsus ma'lumotlarni qo'shamiz
        context.update({
            'title': "Hisobotlar markazi",
            # Bu yerda endi 4 ta sub-menyu linklarini yuboramiz
            'menu_items': [
                {
                    'title': 'Contingent',
                    'url': 'contingent/',
                    'icon': 'fas fa-users',
                    'desc': 'Talabalar kontingenti bo‘yicha hisobot'
                },
                {
                    'title': 'Kurs Swod',
                    'url': 'kurs-swod/',
                    'icon': 'fas fa-list-alt',
                    'desc': 'Kurslar kesimida yig‘ma jild'
                },
                {
                    'title': 'Fan Qarzi Swod',  # --- YANGI QO'SHILGAN QISM ---
                    'url': 'subject-debt-swod/',
                    'icon': 'fas fa-exclamation-circle',
                    'desc': 'Fan qarzdorligi bo\'yicha yig\'ma tahlil'
                },
                {
                    'title': 'TSCH Analiz',
                    'url': 'tsch-analiz/',
                    'icon': 'fas fa-chart-pie',
                    'desc': 'Tahliliy hisobot va monitoring'
                },
                {
                    'title': 'Ichki Grant',
                    'url': 'internal-grant/',
                    'icon': 'fas fa-hand-holding-usd',
                    'desc': 'Universitet granti va chegirmalari'
                },
            ]
        })

        # 3. Agar extra_context kelgan bo'lsa, uni ham qo'shamiz
        if extra_context:
            context.update(extra_context)

        return render(request, "admin/hisobot_main.html", context)


