(function ($) {
    $(document).ready(function () {
        var contractField = $('#id_contract');
        var infoBox = $('<div id="contract-info-bar" style="display: none;"></div>');
        $('.field-contract').append(infoBox);

        function formatMoney(amount) {
            return new Intl.NumberFormat('ru-RU').format(amount);
        }

        function updateContractInfo() {
            var contractId = contractField.val();
            if (contractId) {
                $.ajax({
                    url: '../get-contract-info/',
                    data: { 'contract_id': contractId },
                    dataType: 'json',
                    success: function (data) {
                        var discountHtml = '';
                        if (data.discount_amount > 0) {
                            discountHtml = `
                                <div class="metric-item">
                                    <span class="m-label" style="color: #ff9800;">Chegirma</span>
                                    <span class="m-value v-discount" style="color: #ff9800;">${formatMoney(data.discount_amount)}</span>
                                </div>
                            `;
                        }

                        var debtLabel = data.debt < 0 ? "Ortiqcha to'lov" : 'Qarz';
                        var debtStyle = data.debt < 0 ? 'style="color: #20c997;"' : '';

                        var html = `
                            <div class="student-name-section">
                                <span style="font-size: 1.2em;">🎓</span> ${data.student_name}
                            </div>
                            <div class="finance-metrics">
                                <div class="metric-item">
                                    <span class="m-label">Shartnoma summasi</span>
                                    <span class="m-value v-contract">${formatMoney(data.contract_amount)}</span>
                                </div>
                                ${discountHtml}
                                <div class="metric-item">
                                    <span class="m-label">To'langan</span>
                                    <span class="m-value v-paid">${formatMoney(data.paid_amount)}</span>
                                </div>
                                <div class="metric-item">
                                    <span class="m-label" ${debtStyle}>${debtLabel}</span>
                                    <span class="m-value v-debt" ${debtStyle}>${formatMoney(Math.abs(data.debt))}</span>
                                </div>
                            </div>
                        `;
                        infoBox.html(html).slideDown();
                    },
                    error: function () { infoBox.hide(); }
                });
            } else { infoBox.slideUp(); }
        }

        contractField.on('change', function () { updateContractInfo(); });
        if (contractField.val()) { updateContractInfo(); }
    });
})(django.jQuery);