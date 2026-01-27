function toggleFieldsForInline(inlineRow) {
    if (!inlineRow) return;

    const orderTypeSelect = inlineRow.querySelector('[id$="-order_type"]');
    const tschField = inlineRow.querySelector(".field-tsch_reason");
    const appDateField = inlineRow.querySelector(".field-application_date");
    const docDateField = inlineRow.querySelector(".field-document_taken_date");
    const izohField = inlineRow.querySelector(".field-notes");

    function getSelectedText() {
        if (!orderTypeSelect) return "";
        const option = orderTypeSelect.options[orderTypeSelect.selectedIndex];
        if (option && option.text) return option.text.trim().toLowerCase();
        const rendered = inlineRow.querySelector(".select2-selection__rendered");
        if (rendered) return rendered.textContent.trim().toLowerCase();
        return "";
    }

    // 🔹 Labelga faqat * belgisi qizil rangda qo‘shish
    function updateRequiredMark(field, isRequired) {
        if (!field) return;
        const label = field.querySelector("label");
        if (!label) return;

        // avvalgi * belgini olib tashlaymiz
        label.innerHTML = label.textContent.replace(/\s*\*$/, "").trim();

        if (isRequired) {
            label.innerHTML = `${label.textContent.trim()} <span style="color:#d9534f">*</span>`;
        }
    }

    function toggle() {
        const text = getSelectedText();

        const isExpulsion = text.includes("safidan chiqarish");
        const isRestore = text.includes("qayta tiklash");
        const isAdmission = text.includes("safiga qabul qilish");

        // 🔸 TSCH sababi — faqat safidan chiqarishda
        if (tschField) {
            const input = tschField.querySelector("input, textarea");
            tschField.style.display = isExpulsion ? "" : "none";
            if (input) {
                if (isExpulsion) {
                    input.setAttribute("required", "required");
                    updateRequiredMark(tschField, true);
                } else {
                    input.removeAttribute("required");
                    updateRequiredMark(tschField, false);
                }
            }
        }

        // 🔸 Ariza sanasi — chiqarish yoki tiklashda majburiy
        if (appDateField) {
            const input = appDateField.querySelector("input");
            appDateField.style.display = (isExpulsion || isRestore) ? "" : "none";
            if (input) {
                if (isExpulsion || isRestore) {
                    input.setAttribute("required", "required");
                    updateRequiredMark(appDateField, true);
                } else {
                    input.removeAttribute("required");
                    updateRequiredMark(appDateField, false);
                }
            }
        }

        // 🔸 Hujjat olib ketilgan sanasi — faqat safidan chiqarishda (majburiy emas)
        if (docDateField) {
            const input = docDateField.querySelector("input");
            docDateField.style.display = isExpulsion ? "" : "none";
            if (input) input.removeAttribute("required");
            updateRequiredMark(docDateField, false);
        }

        // 🔸 Izoh — hech qachon majburiy emas
        if (izohField) {
            const textarea = izohField.querySelector("textarea");
            if (textarea) textarea.removeAttribute("required");
            updateRequiredMark(izohField, false);
        }

        // 🔸 Talabalar safiga qabul qilishda — hammasi yashirin
        if (isAdmission) {
            [tschField, appDateField, docDateField].forEach((f) => {
                if (!f) return;
                f.style.display = "none";
                const input = f.querySelector("input, textarea");
                if (input) input.removeAttribute("required");
                updateRequiredMark(f, false);
            });
        }
    }

    const select2Container = inlineRow.querySelector(".select2");
    if (select2Container) {
        const observer = new MutationObserver(toggle);
        observer.observe(select2Container, { childList: true, subtree: true });
    }

    orderTypeSelect?.addEventListener("change", toggle);
    setTimeout(toggle, 700);
}

function initAllInlines() {
    document.querySelectorAll(".dynamic-order_set, .inline-related").forEach((inlineRow) => {
        toggleFieldsForInline(inlineRow);
    });
}

document.addEventListener("formset:added", (e) => {
    toggleFieldsForInline(e.target);
});

window.addEventListener("load", () => {
    setTimeout(() => {
        initAllInlines();
        const mainContainer = document.querySelector("#content-main");
        if (mainContainer) {
            const observer = new MutationObserver(() => initAllInlines());
            observer.observe(mainContainer, { childList: true, subtree: true });
        }
    }, 50);
});

document.addEventListener("submit", function (e) {
    const form = e.target.closest("form");
    if (!form) return;

    let valid = true;
    form.querySelectorAll(".dynamic-order_set, .inline-related").forEach((inlineRow) => {
        const orderTypeSelect = inlineRow.querySelector('[id$="-order_type"]');
        if (!orderTypeSelect) return;

        const text = orderTypeSelect.options[orderTypeSelect.selectedIndex]?.text?.trim()?.toLowerCase() || "";
        const tsch = inlineRow.querySelector('[id$="-tsch_reason"]');
        const app = inlineRow.querySelector('[id$="-application_date"]');

        if ((text.includes("safidan chiqarish") || text.includes("qayta tiklash")) && app && !app.value.trim()) {
            app.reportValidity();
            app.scrollIntoView({ behavior: "smooth", block: "center" });
            valid = false;
        }

        if (text.includes("safidan chiqarish") && tsch && !tsch.value.trim()) {
            tsch.reportValidity();
            tsch.scrollIntoView({ behavior: "smooth", block: "center" });
            valid = false;
        }
    });

    if (!valid) {
        e.preventDefault();
        alert("⚠️ Iltimos, kerakli maydonlarni to‘ldiring!");
    }
});
