/* Fayl: contract_grant_standalone.js (Final Version)
   Vazifasi: Grant turi o'zgarganda maydonlarni ochish va hisoblash.
   Yechim: Eventlar ishlamasa ham, "Interval" orqali o'zgarishni ushlab qoladi.
*/

(function($) {
    'use strict';

    $(document).ready(function() {
        const $typeSelect = $('#id_grant_type');

        // Agar bu sahifada grant select bo'lmasa, to'xtaymiz
        if ($typeSelect.length === 0) return;

        // Oxirgi ko'rgan qiymatimizni saqlab turamiz
        let lastValue = $typeSelect.val();

        // --- ASOSIY FUNKSIYA ---
        function updateGrantState() {
            // Elementlarni yangidan topamiz (xatolik bo'lmasligi uchun)
            const $amountInput = $('#id_amount');
            const $percentInput = $('#id_grant_percent');
            const $resultInput = $('#id_grant_amount');

            // Yashirilishi kerak bo'lgan qatorlar
            const $rows = $('.field-grant_date, .field-grant_percent, .field-grant_amount');

            const val = $typeSelect.val();

            // 1. Agar Grant turi "yo'q" yoki bo'sh bo'lsa -> YASHIRAMIZ
            if (!val || val === 'none') {
                $rows.hide();
                if ($resultInput.val() !== '') $resultInput.val(''); // Faqat kerak bo'lsa tozalar
                if ($percentInput.length) $percentInput.prop('readonly', false);
                return;
            }

            // 2. Aks holda -> KO'RSATAMIZ
            $rows.show();

            // 3. Foizni aniqlash
            let percent = 0;
            if (val === 'CR') {
                // O'ZGARTIRILDI: Iqtidorli talabalar - 25%
                percent = 25;
                $percentInput.val(25).prop('readonly', true);
            } else if (val === 'MT') {
                // O'ZGARTIRILDI: Faol talabalar - 15%
                percent = 15;
                $percentInput.val(15).prop('readonly', true);
            } else {
                // Qo'lda kiritish (QH, QB, XM, IH va boshqalar)
                $percentInput.prop('readonly', false);
                percent = parseFloat($percentInput.val()) || 0;
                if (percent > 100) percent = 100;
            }

            // 4. Summani hisoblash
            let rawAmount = $amountInput.val() || "0";
            let contractAmount = parseFloat(rawAmount.replace(/\s/g, '').replace(/[^\d.]/g, "")) || 0;

            if (contractAmount > 0) {
                let grantSum = Math.round((contractAmount * percent) / 100);

                // Formatlash
                let formatted = grantSum.toLocaleString('ru-RU');

                // Agar qiymat o'zgargan bo'lsa, yangilaymiz (loopga tushmaslik uchun)
                if ($resultInput.val() !== formatted) {
                    $resultInput.val(formatted);
                }

                // Dizayn
                $resultInput.css({
                    'background-color': '#f9f9f9',
                    'color': '#28a745',
                    'font-weight': 'bold'
                }).prop('readonly', true);
            } else {
                $resultInput.val('');
            }
        }

        // ==========================================
        // 1. STANDARD EVENTLAR
        // ==========================================
        $typeSelect.on('change select2:select', function() {
            lastValue = $(this).val();
            updateGrantState();
        });

        $('#id_amount, #id_grant_percent').on('input keyup', function() {
            updateGrantState();
        });

        // ==========================================
        // 2. "QUTQARUVCHI" INTERVAL (Dirty Check)
        // ==========================================
        // Har 500ms (yarim sekund) da tekshiradi: Select o'zgardimi?
        setInterval(function() {
            const currentVal = $typeSelect.val();
            // Agar avvalgi qiymatdan farq qilsa -> Hisoblashni ishga tushir
            if (currentVal !== lastValue) {
                console.log("🔄 Avtomatik aniqlash: Grant turi o'zgardi ->", currentVal);
                lastValue = currentVal;
                updateGrantState();
            }
        }, 500);

        // Sahifa yuklanganda bir marta ishlatamiz
        setTimeout(updateGrantState, 200);
    });

})(window.django ? window.django.jQuery : window.jQuery);