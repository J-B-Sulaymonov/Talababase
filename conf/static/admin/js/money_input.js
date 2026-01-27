/* static/admin/js/money_input.js */

(function($) {
    'use strict';

    // Raqamni formatlash funksiyasi (1000000 -> 1 000 000)
    function formatMoney(value) {
        if (!value) return '';
        // 1. Faqat raqamlar va nuqtani qoldiramiz (harflarni o'chiramiz)
        var num = value.toString().replace(/[^\d.]/g, '');

        // 2. Butun qismni ajratish (agar nuqta bo'lsa)
        var parts = num.split('.');
        parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, " ");

        // 3. Qayta yig'ish
        return parts.join('.');
    }

    // Inputlarni ishga tushirish
    function initMoneyInputs() {
        $('.money-input').each(function() {
            var $input = $(this);

            // A) Sahifa ochilganda mavjud qiymatni formatlash
            var currentVal = $input.val();
            if (currentVal) {
                $input.val(formatMoney(currentVal));
            }

            // B) Yozish paytida formatlash (Event listener)
            // 'off' eski eventlarni o'chirib, qayta ulanishni oldini oladi
            $input.off('input.money').on('input.money', function() {
                var val = $(this).val();

                // Kursor pozitsiyasini saqlab qolish (qulaylik uchun)
                var selectionStart = this.selectionStart;
                var oldLen = val.length;

                var formatted = formatMoney(val);
                $(this).val(formatted);

                // Kursor joylashuvini to'g'irlash (probel qo'shilganda sakrab ketmasligi uchun)
                var newLen = formatted.length;
                if (selectionStart) {
                    this.setSelectionRange(selectionStart + (newLen - oldLen), selectionStart + (newLen - oldLen));
                }
            });
        });
    }

    // 1. Sahifa to'liq yuklanganda
    $(document).ready(function() {
        initMoneyInputs();
    });

    // 2. Inline (yangi qator) qo'shilganda ham ishlashi uchun
    // Django adminning 'formset:added' hodisasini tinglaymiz
    $(document).on('formset:added', function(event, $row) {
        initMoneyInputs();
    });

})(window.django ? window.django.jQuery : window.jQuery);