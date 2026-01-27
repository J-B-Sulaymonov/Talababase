(function () {
    console.log("🟢 contract_grant_auto.js yuklandi (JS only, real readonly)1111111111111111");

    const $jq = window.django?.jQuery || window.jQuery;

    function getFieldWrapper(field) {
        if (!field) return null;
        return (
            field.closest('.form-row') ||
            field.closest('.fieldBox') ||
            field.closest('.form-group') ||
            field.parentElement
        );
    }

    function makeReadOnlyStrong(input) {
        if (!input) return;
        input.setAttribute("readonly", "readonly");
        input.style.pointerEvents = "none";
        input.style.userSelect = "none";
        input.style.caretColor = "transparent";
        input.style.cursor = "not-allowed";
        input.tabIndex = -1;
        input.addEventListener("keydown", e => e.preventDefault());
        input.addEventListener("keypress", e => e.preventDefault());
        input.addEventListener("paste", e => e.preventDefault());
        input.addEventListener("focus", e => input.blur());
    }

    function updateGrantFields(prefix) {
        const typeSelect = document.getElementById(prefix + '-grant_type');
        const percentInput = document.getElementById(prefix + '-grant_percent');
        const dateField = document.getElementById(prefix + '-grant_date');
        const amountField = document.getElementById(prefix + '-grant_amount');
        const contractAmount = document.getElementById(prefix + '-amount');

        if (!typeSelect || !percentInput) return;

        const dateWrap = getFieldWrapper(dateField);
        const percentWrap = getFieldWrapper(percentInput);
        const amountWrap = getFieldWrapper(amountField);

        const val = typeSelect.value || "none";

        if (val === 'none') {
            [dateWrap, percentWrap, amountWrap].forEach(w => w && (w.style.display = 'none'));
            return;
        } else {
            [dateWrap, percentWrap, amountWrap].forEach(w => w && (w.style.display = ''));
        }

        if (val === 'CR') {
            percentInput.value = 50;
            percentInput.readOnly = true;
        } else if (val === 'MT') {
            percentInput.value = 30;
            percentInput.readOnly = true;
        } else if (val === 'IH') {
            percentInput.readOnly = false;
        }

        amount = parseFloat((contractAmount?.value || '').replace(/[^\d.]/g, '')) || 0;
        const percent = Math.min(parseFloat(percentInput.value || 0), 100);

        if (val === 'IH' && percent > 100) {
            alert("⚠️ Grant foizi 100% dan oshmasligi kerak!");
            percentInput.value = 100;
        }

        // ✅ 1 semestr uchun hisoblash (yillik summaning yarmi)
        const grantSum = Math.round(((amount / 2) * percent) / 100) || 0;

        if (amountField) {
            if (amountField.tagName === 'INPUT') {
                amountField.value = grantSum ? grantSum.toLocaleString('uz-UZ') : '';
                makeReadOnlyStrong(amountField); // 🔒 kuchli himoya
                amountField.style.backgroundColor = '#f9f9f9';
                amountField.style.color = '#28a745';
                amountField.style.fontWeight = 'bold';
            } else {
                amountField.textContent = grantSum ? grantSum.toLocaleString('uz-UZ') : '-';
                amountField.style.color = '#28a745';
                amountField.style.fontWeight = 'bold';
            }
        }

        console.log(`💰 Hisoblandi (1 semestr): (${amount} / 2) * ${percent}% = ${grantSum}`);
    }

    function attachEvents(select) {
        const prefix = select.id.replace('-grant_type', '');
        if (select.dataset.grantAttached === "true") return;
        select.dataset.grantAttached = "true";

        console.log("✅ Event ulandi:", prefix);

        select.addEventListener('change', () => updateGrantFields(prefix));

        if ($jq && $jq.fn && $jq.fn.select2) {
            $jq(select).on('select2:select', () => updateGrantFields(prefix));
        }

        const percent = document.getElementById(prefix + '-grant_percent');
        const amount = document.getElementById(prefix + '-amount');

        if (percent) percent.addEventListener('input', () => updateGrantFields(prefix));
        if (amount) amount.addEventListener('input', () => updateGrantFields(prefix));

        updateGrantFields(prefix);

        // 🔁 Jazzmin yangilaganda readonly holatni saqlash
        const observer = new MutationObserver(() => {
            const amountField = document.getElementById(prefix + '-grant_amount');
            if (amountField) makeReadOnlyStrong(amountField);
        });
        const row = select.closest('.inline-related');
        if (row) observer.observe(row, { childList: true, subtree: true });
    }

    function scanAndAttach() {
        const selects = document.querySelectorAll('select[id$="-grant_type"]');
        if (selects.length === 0) {
            console.log("⏳ Inline hali yuklanmagan, 300ms kutilyapti...");
            setTimeout(scanAndAttach, 300);
            return;
        }
        console.log(`🔍 ${selects.length} ta grant_type select topildi`);
        selects.forEach(attachEvents);
    }

    document.addEventListener('DOMContentLoaded', () => {
        console.log("📦 DOM tayyor");
        scanAndAttach();
    });

    window.addEventListener('load', () => {
        console.log("🕐 Window loaded (fallback)");
        scanAndAttach();
    });
})();
