/* static/admin/js/calculate_hours.js */
(function($) {
    'use strict';

    // 1. jQuery borligini tekshiramiz
    if (typeof $ === 'undefined' || $ === null) {
        console.error("XATOLIK: jQuery topilmadi! Skript to'xtatildi.");
        return;
    }

    $(document).ready(function() {
        console.log("Autocalc skripti muvaffaqiyatli ishga tushdi!");

        // 2. Kuzatiladigan maydonlar (inputlar)
        var selectors = 'input[id$="-lecture_hours"], input[id$="-practice_hours"], input[id$="-lab_hours"], input[id$="-seminar_hours"]';

        // 3. Hodisani biriktirish (Event Delegation)
        $(document).on('input keyup change', selectors, function() {
            var $row = $(this).closest('tr'); // O'zgarish bo'lgan qatorni topamiz

            // Har bir katakdagi qiymatni olamiz (bo'sh bo'lsa 0)
            var lecture = parseFloat($row.find('input[id$="-lecture_hours"]').val()) || 0;
            var practice = parseFloat($row.find('input[id$="-practice_hours"]').val()) || 0;
            var lab = parseFloat($row.find('input[id$="-lab_hours"]').val()) || 0;
            var seminar = parseFloat($row.find('input[id$="-seminar_hours"]').val()) || 0;

            // Yig'indini hisoblaymiz
            var total = lecture + practice + lab + seminar;

            // Natijani yozamiz
            var $totalField = $row.find('input[id$="-total_hours"]');
            $totalField.val(total);

            // Vizual effekt (ishlayotganini bilish uchun)
            $totalField.css('font-weight', 'bold');
        });
    });

// Quyidagi qator jQueryni topish uchun eng ishonchli usul:
// Agar django.jQuery bo'lsa o'shani oladi, bo'lmasa oddiy jQuery (window.jQuery) ni oladi.
})(window.django && window.django.jQuery ? window.django.jQuery : (window.jQuery || window.$));