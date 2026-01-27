/* static/admin/js/contract_grant_auto_summ.js */

(function($) {
    'use strict';

    // === 1. GLOBAL HISOBLASH MANTIGI ===
    // Bu funksiya barcha qatorlarni aylanib chiqib, to'g'ri hisob-kitob qiladi
    function recalculateAll() {
        // Barcha qatorlarni olamiz
        const rows = document.querySelectorAll(".dynamic-contract_set, .inline-related");

        // 0-BOSQICH: Har bir o'quv yili uchun "Asosiy Kontrakt Summasi"ni aniqlash
        // Mantiq: Bir yilda bir nechta qator bo'lsa, eng katta summa - asosiy hisoblanadi (boshqalar 0 bo'lsa ham).
        const maxContractByYear = {};

        rows.forEach(row => {
            if (row.classList.contains("empty-form")) return;
            const yearSelect = row.querySelector('[id$="-academic_year"]');
            const amountInput = row.querySelector('[id$="-amount"]');

            if (yearSelect && amountInput) {
                const yearId = yearSelect.value;
                // Summani tozalab olish (probellarni olib tashlash)
                const val = parseFloat(amountInput.value.replace(/\s/g, '').replace(/[^\d.]/g, "")) || 0;

                if (yearId) {
                    if (!maxContractByYear[yearId] || val > maxContractByYear[yearId]) {
                        maxContractByYear[yearId] = val;
                    }
                }
            }
        });

        const priorityGrantsByYear = {}; // Yil bo'yicha "Qabul/Hayit" summalari

        // --- 1-BOSQICH: "Qabul" (QB) va "Qurbon Hayiti" (QH) ni hisoblash ---
        rows.forEach(row => {
            if (row.classList.contains("empty-form")) return;

            const typeSelect = row.querySelector('[id$="-grant_type"]');
            const yearSelect = row.querySelector('[id$="-academic_year"]');
            const percentInput = row.querySelector('[id$="-grant_percent"] input') || row.querySelector('[id$="-grant_percent"]');
            const grantAmountInput = row.querySelector('[id$="-grant_amount"] input') || row.querySelector('[id$="-grant_amount"]');

            if (!typeSelect || !yearSelect) return;

            const type = typeSelect.value;
            const yearId = yearSelect.value;
            const percent = parseFloat(percentInput?.value || 0);

            // MUHIM: Kontrakt summasini inputdan emas, yil bo'yicha aniqlangan "Asosiy summa"dan olamiz
            const baseContractAmount = maxContractByYear[yearId] || 0;

            // Faqat Priority (QB, QH)
            if (type === "QB" || type === "QH") {
                // Ular har doim to'liq summadan hisoblanadi
                const grantSum = Math.round((baseContractAmount * percent) / 100);

                if (grantAmountInput) {
                    grantAmountInput.value = grantSum.toLocaleString('ru-RU'); // 1 000 000 format
                    styleInput(grantAmountInput, true);
                }

                // Yil bo'yicha bazaga yozib qo'yamiz (boshqa grantlar ayirib tashlashi uchun)
                if (yearId) {
                    priorityGrantsByYear[yearId] = (priorityGrantsByYear[yearId] || 0) + grantSum;
                }
            }
        });

        // --- 2-BOSQICH: Boshqa barcha grantlarni hisoblash ---
        rows.forEach(row => {
            if (row.classList.contains("empty-form")) return;

            const typeSelect = row.querySelector('[id$="-grant_type"]');
            const yearSelect = row.querySelector('[id$="-academic_year"]');
            const percentInput = row.querySelector('[id$="-grant_percent"] input') || row.querySelector('[id$="-grant_percent"]');
            const grantAmountInput = row.querySelector('[id$="-grant_amount"] input') || row.querySelector('[id$="-grant_amount"]');

            if (!typeSelect || !yearSelect) return;

            const type = typeSelect.value;
            const yearId = yearSelect.value;
            const percent = parseFloat(percentInput?.value || 0);

            // Yana "Asosiy summa"ni olamiz
            const baseContractAmount = maxContractByYear[yearId] || 0;

            // QB, QH va bo'shlarni o'tkazib yuboramiz (ular 1-bosqichda yoki shart emas)
            if (type === "QB" || type === "QH" || type === "none" || type === "") {
                if (type === "none" || type === "") {
                    if (grantAmountInput) {
                        grantAmountInput.value = "";
                        styleInput(grantAmountInput, false);
                    }
                }
                return;
            }

            // --- ASOSIY MANTIQ: Asosiy Kontrakt - (QB/QH grant summasi) ---
            const deduction = priorityGrantsByYear[yearId] || 0;
            const baseAmount = Math.max(0, baseContractAmount - deduction); // Manfiy bo'lib ketmasin

            const grantSum = Math.round((baseAmount * percent) / 100);

            if (grantAmountInput) {
                grantAmountInput.value = grantSum.toLocaleString('ru-RU');
                styleInput(grantAmountInput, true);
            }
        });
    }

    // Inputni chiroyli qilish funksiyasi
    function styleInput(input, isActive) {
        if (isActive) {
            input.style.color = "#28a745";
            input.style.fontWeight = "bold";
            input.setAttribute("readonly", "readonly");
            input.style.backgroundColor = "#f9f9f9";
            input.style.cursor = "default";
            // Event loopdan qochish uchun onfocusni o'chiramiz
            input.onfocus = function() { this.blur(); };
        } else {
            input.style.color = "";
            input.style.fontWeight = "";
            input.style.backgroundColor = "";
            input.removeAttribute("readonly");
            input.onfocus = null;
        }
    }

    // === 2. SIZNING FUNKSIYANGIZ (Moslashtirilgan) ===
    function toggleGrantFields(inlineRow) {
        if (!inlineRow) return;

        const grantTypeSelect = inlineRow.querySelector('[id$="-grant_type"]');
        const grantDateField = inlineRow.querySelector(".field-grant_date");
        const grantPercentField = inlineRow.querySelector(".field-grant_percent");
        const grantAmountField = inlineRow.querySelector(".field-grant_amount");

        // Elementlarni to'g'ri olish
        const percentInput = grantPercentField?.querySelector("input") || grantPercentField?.querySelector("input[type=number]");
        const amountInput = grantAmountField?.querySelector("input");

        // Hisoblashga kerakli boshqa polalar
        const contractAmountInput = inlineRow.querySelector('[id$="-amount"]');
        const yearSelect = inlineRow.querySelector('[id$="-academic_year"]');

        if (!grantTypeSelect) return;

        // UI ni yangilash va Hisob-kitobni chaqirish
        function updateFieldsAndCalculate() {
            const value = grantTypeSelect.value || "";

            // 🔹 1. Ko'rsatish/Yashirish
            if (value === "none" || value === "") {
                [grantDateField, grantPercentField, grantAmountField].forEach(f => f && (f.style.display = "none"));
                if (percentInput) percentInput.value = "";
                if (amountInput) amountInput.value = "";
            } else {
                [grantDateField, grantPercentField, grantAmountField].forEach(f => f && (f.style.display = ""));

                // 🔹 2. Avto-Foizlar
                if (percentInput) {
                    if (value === "CR") { // Iqtidorli
                        percentInput.value = 25;
                        percentInput.readOnly = true;
                    } else if (value === "MT") { // Faol
                        percentInput.value = 15;
                        percentInput.readOnly = true;
                    } else {
                        // Boshqa turlar uchun ruchnoy kiritishga ruxsat
                        if (percentInput.hasAttribute('readonly')) {
                             percentInput.readOnly = false;
                        }
                    }
                }
            }

            // 🔹 3. GLOBAL HISOBLASHNI CHAQIRISH
            recalculateAll();
        }

        // 🔸 Listenerlar (Kuzatuvchilar)
        grantTypeSelect.addEventListener("change", updateFieldsAndCalculate);

        // Boshqa maydonlar o'zgarganda ham qayta hisoblaymiz
        if (contractAmountInput) contractAmountInput.addEventListener("input", recalculateAll);
        if (yearSelect) yearSelect.addEventListener("change", recalculateAll);
        if (percentInput) percentInput.addEventListener("input", recalculateAll);

        // Select2 (Django admin ko'pincha Select2 ishlatadi)
        const select2Container = inlineRow.querySelector(".select2");
        if (select2Container) {
            const observer = new MutationObserver(updateFieldsAndCalculate);
            observer.observe(select2Container, { childList: true, subtree: true });
        }

        // Dastlabki holat
        updateFieldsAndCalculate();
    }

    // === 3. ISHGA TUSHIRISH ===
    function initAllGrantInlines() {
        document.querySelectorAll(".dynamic-contract_set, .inline-related").forEach((inlineRow) => {
            toggleGrantFields(inlineRow);
        });
        recalculateAll(); // Bir marta to'liq hisoblab olamiz
    }

    // Inline qo‘shilganda
    // Standart DOM eventi
    document.addEventListener("formset:added", (e) => {
        toggleGrantFields(e.target);
        recalculateAll();
    });

    // Django jQuery eventi (Ishonchliroq)
    if (typeof django !== 'undefined' && django.jQuery) {
        django.jQuery(document).on('formset:added', function(event, $row) {
             const rowElement = ($row && $row.length) ? $row[0] : $row;
             if (rowElement) {
                 toggleGrantFields(rowElement);
                 recalculateAll();
             }
        });
    }

    // Sahifa yuklanganda
    window.addEventListener("load", () => {
        setTimeout(() => {
            initAllGrantInlines();

            // MutationObserver bilan kuzatish (ba'zi admin temalar uchun)
            const mainContainer = document.querySelector("#content-main");
            if (mainContainer) {
                const observer = new MutationObserver(() => initAllGrantInlines());
                observer.observe(mainContainer, { childList: true, subtree: true });
            }
        }, 200);
    });

})(window.django ? window.django.jQuery : window.jQuery);