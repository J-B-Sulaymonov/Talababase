document.addEventListener('DOMContentLoaded', function() {
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
    $(document).on('change', '#id_subject', function() {
        const subjectId = $(this).val();

        if (!subjectId) {
            clearFilterHorizontal('id_plan_subjects');
            clearFilterHorizontal('id_groups');
            return;
        }

        $.ajax({
            url: URL_GET_PLANS,
            data: { 'subject_id': subjectId },
            success: function(data) {
                // Avval guruhlarni tozalaymiz (chunki fan o'zgardi)
                clearFilterHorizontal('id_groups');
                // Keyin yangi rejalarni yuklaymiz
                updateFilterHorizontalOptions('id_plan_subjects', data.results);
            },
            error: function(err) {
                console.error("Xatolik (Plans):", err);
            }
        });
    });

    // 2. REJALAR O'ZGARISHI (Guruhlarni yangilash)
    // Tugmalar bosilganda yoki optionlarga double-click qilinganda
    const triggers = '#id_plan_subjects_add_link, #id_plan_subjects_remove_link, #id_plan_subjects_add_all_link, #id_plan_subjects_remove_all_link';

    $(document).on('click', triggers, function() {
        setTimeout(fetchGroupsBySelectedPlans, 300);
    });

    // Double click hodisasi (SelectBox.js ba'zan buni o'zi handle qiladi, lekin baribir qo'shib qo'yamiz)
    $(document).on('dblclick', '#id_plan_subjects_from option, #id_plan_subjects_to option', function(){
        setTimeout(fetchGroupsBySelectedPlans, 300);
    });

    function fetchGroupsBySelectedPlans() {
        const selectedPlanIds = [];
        // O'ng tomondagi optionlarni olamiz
        $('#id_plan_subjects_to option').each(function() {
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
            success: function(data) {
                updateFilterHorizontalOptions('id_groups', data.results);
            },
            error: function(err) {
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

        // SelectBox obyekti borligini tekshiramiz
        if (typeof SelectBox === 'undefined' || !SelectBox.cache[fromId]) {
            console.warn("SelectBox topilmadi yoki init qilinmadi:", fieldName);
            return;
        }

        // 1. O'ng tomonda allaqachon tanlangan ID larni olamiz
        const selectedIds = [];
        $('#' + toId + ' option').each(function() {
            selectedIds.push($(this).val());
        });

        // 2. Keshni tozalaymiz (DOM ga tegmaymiz, .empty() QILMANG!)
        SelectBox.cache[fromId] = [];

        // 3. Yangi itemlarni keshga qo'shamiz
        items.forEach(function(item) {
            const strId = String(item.id);
            // Agar u allaqachon o'ng tomonda bo'lmasa, chapga qo'shamiz
            if (!selectedIds.includes(strId)) {
                SelectBox.add_to_cache(fromId, {
                    value: strId,
                    text: item.text,
                    displayed: 1
                });
            }
        });

        // 4. Ekranni yangilaymiz (Redisplay o'zi DOM ni tozalab yangilaydi)
        SelectBox.redisplay(fromId);
    }

    function clearFilterHorizontal(fieldName) {
        const fromId = fieldName + '_from';

        if (typeof SelectBox !== 'undefined' && SelectBox.cache[fromId]) {
            // Keshni tozalaymiz
            SelectBox.cache[fromId] = [];
            // Ekranni yangilaymiz
            SelectBox.redisplay(fromId);
        } else {
            // Agar SelectBox ishlamasa, oddiy yo'l bilan tozalaymiz
            $('#' + fromId).empty();
        }
    }
});