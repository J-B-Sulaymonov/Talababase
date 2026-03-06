document.addEventListener('DOMContentLoaded', function () {
    const $ = django.jQuery;
    console.log("Workload JS V9.2 (Stable SelectBox) yuklandi.");

    function getAjaxPrefix() {
        const path = window.location.pathname;
        if (path.indexOf('/add/') !== -1) return '../';
        else if (path.indexOf('/change/') !== -1) return '../../';
        return '';
    }

    const prefix = getAjaxPrefix();
    const URL_GET_PLANS = prefix + 'ajax/get-plans/';
    const URL_GET_GROUPS = prefix + 'ajax/get-groups/';

    // 1. FAN (Subject) O'ZGARISHI
    $(document).on('change', '#id_subject', function () {
        const subjectId = $(this).val();

        if (!subjectId) {
            clearFilterHorizontal('id_plan_subjects');
            clearFilterHorizontal('id_groups');
            return;
        }

        $.ajax({
            url: URL_GET_PLANS,
            data: { 'subject_id': subjectId },
            success: function (data) {
                // Avval guruhlarni tozalaymiz (chunki fan o'zgardi)
                clearFilterHorizontal('id_groups');
                // Keyin yangi rejalarni yuklaymiz
                updateFilterHorizontalOptions('id_plan_subjects', data.results);
            },
            error: function (err) {
                console.error("Xatolik (Plans):", err);
            }
        });
    });

    // 2. REJALAR O'ZGARISHI (Guruhlarni yangilash) - ENG XAVFSIZ USUL
    // Biz bevosita sahifada doim mavjud bo'lgan form-group blokini kuzatamiz.
    // Ichidagi barcha <select> va <option> larning dinamik o'zgarishlarini (click, dblclick, arrow tugmalar)
    // brauzerning eng quyi qavatidan (MutationObserver) tutamiz.

    const containerNode = document.querySelector('.field-plan_subjects');
    if (containerNode) {
        let updateTimer;
        const observer = new MutationObserver(function (mutations) {
            // Faqat o'zgarishlar Select qutilsiga tegishli bo'lsa ishlaydi
            clearTimeout(updateTimer);
            updateTimer = setTimeout(fetchGroupsBySelectedPlans, 300);
        });

        // childList true va subtree true qilib butun blokni kuzatamiz
        observer.observe(containerNode, { childList: true, subtree: true });
    }

    // Zaxira uchun asosiy select change event
    $(document).on('change', '#id_plan_subjects', function () {
        setTimeout(fetchGroupsBySelectedPlans, 300);
    });

    function fetchGroupsBySelectedPlans() {
        const selectedPlanIds = [];
        // O'ng tomondagi optionlarni olamiz
        $('#id_plan_subjects_to option').each(function () {
            selectedPlanIds.push($(this).val());
        });

        // Agar hech narsa tanlanmagan bo'lsa, guruhlarni tozalaymiz
        if (selectedPlanIds.length === 0) {
            clearFilterHorizontal('id_groups');
            return;
        }

        $.ajax({
            url: URL_GET_GROUPS,
            data: { 'plan_ids': selectedPlanIds.join(',') },
            success: function (data) {
                console.log("URL_GET_GROUPS success, fetched items:", data.results);
                updateFilterHorizontalOptions('id_groups', data.results);
            },
            error: function (err) {
                console.error("Xatolik (Groups):", err);
            }
        });
    }

    // ----------------------------------------------------------------
    // YORDAMCHI FUNKSIYALAR (TUZATILGAN QISMI)
    // ----------------------------------------------------------------

    function updateFilterHorizontalOptions(fieldName, items) {
        const fromId = fieldName + '_from';
        const toId = fieldName + '_to';

        if (typeof SelectBox === 'undefined' || !SelectBox.cache[fromId]) {
            console.warn("SelectBox asosi topilmadi:", fieldName);
            return;
        }

        const selectedIds = [];
        const toBox = document.getElementById(toId);
        if (toBox) {
            for (let i = 0; i < toBox.options.length; i++) {
                selectedIds.push(toBox.options[i].value);
            }
        }

        // Yangi kesh yaratamiz
        const newCache = [];
        items.forEach(function (item) {
            const strId = String(item.id);
            if (!selectedIds.includes(strId)) {
                newCache.push({ value: strId, text: item.text, displayed: 1 });
            }
        });

        // Keshni to'g'ridan-to'g'ri almashtiramiz va redisplay qilamiz
        SelectBox.cache[fromId] = newCache;
        try {
            SelectBox.redisplay(fromId);
        } catch (e) {
            console.warn("SelectBox redisplay xatosi:", e);
        }

        // Ikonkalarni yangilash (agar mavjud bo'lsa)
        if (typeof SelectFilter !== 'undefined') {
            try {
                SelectFilter.refresh_icons('id_' + fieldName);
            } catch (e) { }
        }
    }

    function clearFilterHorizontal(fieldName) {
        const fromId = fieldName + '_from';

        if (typeof SelectBox !== 'undefined' && SelectBox.cache && SelectBox.cache[fromId]) {
            SelectBox.cache[fromId] = [];
            try {
                SelectBox.redisplay(fromId);
            } catch (e) { }

            if (typeof SelectFilter !== 'undefined') {
                try {
                    SelectFilter.refresh_icons('id_' + fieldName);
                } catch (e) { }
            }
        }
    }
});