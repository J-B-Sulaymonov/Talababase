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

        console.log("🎯 Tanlangan grant turi:", value);

        // 🔹 "Imtiyoz yo‘q" bo‘lsa — yashiramiz
        if (value === "none" || value === "") {
            [grantDateField, grantPercentField, grantAmountField].forEach(f => f && (f.style.display = "none"));
            return;
        }

        // 🔹 Aks holda ko‘rsatamiz
        [grantDateField, grantPercentField, grantAmountField].forEach(f => f && (f.style.display = ""));

        // 🔸 Foizni aniqlash
        let percent = 0;
        if (value === "CR") {
            percent = 50;
            if (percentInput) {
                percentInput.value = 50;
                percentInput.readOnly = true;
            }
        } else if (value === "MT") {
            percent = 30;
            if (percentInput) {
                percentInput.value = 30;
                percentInput.readOnly = true;
            }
        } else if (value === "IH") {
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
        const contractAmount = parseFloat((contractAmountInput?.value || "").replace(/[^\d.]/g, "")) || 0;
        const grantSum = Math.round(((contractAmount/2) * percent) / 100);

        if (amountInput) {
            if (grantSum > 0) {
                amountInput.value = grantSum;
                amountInput.style.color = "#28a745"; // yashil rangda ko‘rsatish
                amountInput.style.fontWeight = "bold";
            } else {
                amountInput.value = "";
                amountInput.style.color = "";
                amountInput.style.fontWeight = "";
            }
        }

        console.log(`💰 Hisoblandi: ${contractAmount} * ${percent}% = ${grantSum}`);
    }

    // 🔸 Select2 yoki oddiy change uchun kuzatuvchi
    const select2Container = inlineRow.querySelector(".select2");
    if (select2Container) {
        const observer = new MutationObserver(updateFields);
        observer.observe(select2Container, { childList: true, subtree: true });
    }

    grantTypeSelect.addEventListener("change", updateFields);
    grantPercentField?.querySelector("input")?.addEventListener("input", updateFields);
    contractAmountInput?.addEventListener("input", updateFields);

    // 🔹 Dastlabki holatni ishga tushiramiz
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
        console.log("✅ Grant inline skript ishga tushdi");

        const mainContainer = document.querySelector("#content-main");
        if (mainContainer) {
            const observer = new MutationObserver(() => initAllGrantInlines());
            observer.observe(mainContainer, { childList: true, subtree: true });
        }
    }, 100);
});