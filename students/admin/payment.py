from .base import *


# =============================================================================
# 💰 TO'LOV ADMIN (PaymentResource + PaymentAdmin)
# =============================================================================

class PaymentResource(resources.ModelResource):
    # 1. Shartnoma ID sini bog'lash (Eski kod)
    contract = fields.Field(
        column_name='contract_id',
        attribute='contract',
        widget=ForeignKeyWidget(Contract, field='id')
    )

    # 2. Asosiy maydonlar (Eski kod)
    amount = fields.Field(column_name='amount', attribute='amount')
    payment_date = fields.Field(column_name='payment_date', attribute='payment_date')

    # --- YANGI QO'SHILGAN MAYDONLAR (EXPORT UCHUN) ---

    # 3. O'quv yili
    academic_year = fields.Field(
        column_name="O'quv yili",
        attribute='contract__academic_year__name',
        readonly=True
    )

    # 4. Kursi
    student_course = fields.Field(
        column_name="Kurs",
        attribute='contract__student__course_year',
        readonly=True
    )

    # 5. Status (Display - chiroyli ko'rinishda olish uchun dehydrate ishlatamiz)
    student_status = fields.Field(
        column_name="Status",
        readonly=True
    )

    # 6. Yo'nalish (Guruh orqali olinadi)
    specialty = fields.Field(
        column_name="Yo'nalish",
        readonly=True
    )

    class Meta:
        model = Payment
        # Export qilinadigan barcha ustunlar ro'yxati
        fields = (
            'id',
            'contract',
            'academic_year',  # <--- Qo'shildi
            'specialty',  # <--- Qo'shildi
            'student_course',  # <--- Qo'shildi
            'student_status',  # <--- Qo'shildi
            'amount',
            'payment_date',
            'description'
        )

        # Exceldagi ustunlar ketma-ketligi
        export_order = (
            'id',
            'contract',
            'academic_year',
            'specialty',
            'student_course',
            'student_status',
            'amount',
            'payment_date',
            'description'
        )

    # --- YANGI MAYDONLARNI HISOBLASH METODLARI ---

    def dehydrate_student_status(self, payment):
        """Talabaning statusini (active, expelled emas, "O'qiydi" deb) chiqarish"""
        if payment.contract and payment.contract.student:
            return payment.contract.student.get_status_display()
        return ""

    def dehydrate_specialty(self, payment):
        """Talabaning yo'nalishini guruh orqali topish"""
        try:
            return payment.contract.student.group.specialty.name
        except AttributeError:
            return ""

    def skip_row(self, instance, original, row, import_validation_errors=None):
        """
        Bo'sh qatorlarni yoki ma'lumoti chala qatorlarni tashlab ketish.
        """
        if not row.get('amount'):
            return True
        if not row.get('contract_id'):
            return True
        return super().skip_row(instance, original, row, import_validation_errors)


@admin.register(Payment)
class PaymentAdmin(ImportExportModelAdmin):
    resource_class = PaymentResource
    form = PaymentForm
    list_display = ('contract', 'payment_date', 'amount')
    list_filter = ('payment_date',)
    search_fields = ('contract__student__full_name', 'contract__contract_number','id','payment_date')
    autocomplete_fields = ['contract']

    class Media:
        js = (
            'admin/js/jquery.init.js',
            'admin/js/money_input.js',
            'admin/js/payment_contract_info.js',  # <--- YANGI JS FAYL
        )
        css = {
            'all': ('admin/css/payment_info.css',)  # Ixtiyoriy: chiroyli ko'rinish uchun
        }

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('get-contract-info/', self.admin_site.admin_view(self.get_contract_info_view),
                 name='payment_get_contract_info'),
        ]
        return custom_urls + urls



    def get_contract_info_view(self, request):
        contract_id = request.GET.get('contract_id')
        if not contract_id:
            return JsonResponse({'error': 'ID topilmadi'}, status=400)

        try:
            contract = Contract.objects.get(id=contract_id)

            # 1. Hisob-kitoblar
            total_amount = contract.amount
            discount_amount = contract.grant_amount or 0
            
            final_contract_amount = total_amount - discount_amount
            paid_amount = Payment.objects.filter(contract=contract).aggregate(sum=Sum('amount'))['sum'] or 0
            debt = final_contract_amount - paid_amount


            return JsonResponse({
                'contract_amount': float(total_amount),
                'discount_amount': float(discount_amount),
                'paid_amount': float(paid_amount),
                'debt': float(debt),
                'student_name': contract.student.full_name
            })
        except Contract.DoesNotExist:
            print(f"❌ Terminal: {contract_id} IDli shartnoma topilmadi!")
            return JsonResponse({'error': 'Shartnoma topilmadi'}, status=404)
