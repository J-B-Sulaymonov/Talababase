function toggleGrantFields(inlineRow) {
    if (!inlineRow) return;

    const grantTypeSelect = inlineRow.querySelector('[id$="-grant_type"]');
    const grantDateField = inlineRow.querySelector(".field-grant_date");
    const grantPercentField = inlineRow.querySelector(".field-grant_percent");
    const grantAmountField = inlineRow.querySelector(".field-grant_amount");
    const contractAmountInput = inlineRow.querySelector('[id$="-amount"]');

    if (!grantTypeSelect) return;

    function updateFields() {
        const value = grantTypeSelect.value || "";
        const grantDateInput = grantDateField?.querySelector("input");
        const percentInput = grantPercentField?.querySelector("input");
        const amountInput = grantAmountField?.querySelector("input");

        // 🔹 "Imtiyoz yo‘q" bo‘lsa — yashiramiz
        if (value === "none" || value === "") {
            [grantDateField, grantPercentField, grantAmountField].forEach(f => f && (f.style.display = "none"));
            if (amountInput) amountInput.value = ""; // Tozalab qo'yamiz
            return;
        }

        // 🔹 Aks holda ko‘rsatamiz
        [grantDateField, grantPercentField, grantAmountField].forEach(f => f && (f.style.display = ""));

        // 🔸 Foizni aniqlash
        let percent = 0;

        if (value === "CR") {
            // O'ZGARTIRILDI: Rag'batlantirish - 25%
            percent = 25;
            if (percentInput) {
                percentInput.value = 25;
                percentInput.readOnly = true;
            }
        } else if (value === "MT") {
            // O'ZGARTIRILDI: Ma'naviyat - 15%
            percent = 15;
            if (percentInput) {
                percentInput.value = 15;
                percentInput.readOnly = true;
            }
        } else if (value === "IH" || value === "QH" || value === "QB" || value === "XM") {
            // O'ZGARTIRILDI: XM va IH qo'shildi
            // 🔹 Qo'lda kiritiladigan foizlar
            if (percentInput) {
                percentInput.readOnly = false;
                percent = parseFloat(percentInput.value || 0);

                if (percent > 100) {
                    alert("⚠️ Grant foizi 100% dan oshmasligi kerak!");
                    percentInput.value = 100;
                    percent = 100;
                }
            }
        }

        // 🔹 Grant summasini hisoblash
        // Kontrakt summasidagi probellarni olib tashlab hisoblaymiz
        const contractAmount = parseFloat((contractAmountInput?.value || "").replace(/\s/g, '').replace(/[^\d.]/g, "")) || 0;

        // (Summa * foiz) / 100
        const grantSum = Math.round((contractAmount * percent) / 100);

        if (amountInput) {
            if (grantSum > 0) {
                // 1. Raqamni formatlash (1 500 000 ko'rinishida)
                amountInput.value = grantSum.toLocaleString('ru-RU');

                // 2. Vizual ko'rinish
                amountInput.style.color = "#28a745"; // Yashil
                amountInput.style.fontWeight = "bold";

                // 3. Qat'iy bloklash (faqat ko'rish uchun)
                amountInput.setAttribute("readonly", "readonly");
                amountInput.style.backgroundColor = "#f9f9f9"; // Och kulrang fon
                amountInput.style.cursor = "default"; // Sichqoncha belgisi o'zgarmaydi

                // Foydalanuvchi chalg'imasligi uchun fokusni o'chiramiz
                amountInput.onfocus = function() { this.blur(); };
            } else {
                amountInput.value = "";
                amountInput.style.backgroundColor = "";
            }
        }
    }

    // 🔸 Kuzatuvchilar (Observers)
    const select2Container = inlineRow.querySelector(".select2");
    if (select2Container) {
        const observer = new MutationObserver(updateFields);
        observer.observe(select2Container, { childList: true, subtree: true });
    }

    grantTypeSelect.addEventListener("change", updateFields);
    grantPercentField?.querySelector("input")?.addEventListener("input", updateFields);
    contractAmountInput?.addEventListener("input", updateFields);

    // 🔹 Dastlabki holat
    setTimeout(updateFields, 100);
}

// 🔹 Barcha inline-larga qo‘llash
function initAllGrantInlines() {
    document.querySelectorAll(".dynamic-contract_set, .inline-related").forEach((inlineRow) => {
        toggleGrantFields(inlineRow);
    });
}

// 🔹 Inline qo‘shilganda ham ishlaydi
document.addEventListener("formset:added", (e) => {
    toggleGrantFields(e.target);
});

// 🔹 Sahifa yuklanganda hammasini ishga tushirish
window.addEventListener("load", () => {
    setTimeout(() => {
        initAllGrantInlines();
        const mainContainer = document.querySelector("#content-main");
        if (mainContainer) {
            const observer = new MutationObserver(() => initAllGrantInlines());
            observer.observe(mainContainer, { childList: true, subtree: true });
        }
    }, 100);
});