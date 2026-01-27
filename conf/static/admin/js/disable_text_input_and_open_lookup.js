document.addEventListener('DOMContentLoaded', function() {
    // Find all raw id inputs (Django admin adds class raw-id-field)
    document.querySelectorAll('input.raw-id-field').forEach(function(input) {
        // Block manual typing but keep it focusable/clickable
        input.setAttribute('readonly', true);
        input.style.cursor = 'pointer';
        // Slight visual hint (optional)
        input.style.backgroundColor = '#f9f9f9';

        // Try to find the related lookup anchor near this input
        // 1) nearest parent container with an anchor.related-lookup
        var lookup = input.closest('.related-widget-wrapper') ?
                     input.closest('.related-widget-wrapper').querySelector('a.related-lookup') :
                     null;

        // 2) fallback: sibling anchor
        if (!lookup) {
            var sib = input.nextElementSibling;
            if (sib && sib.classList && sib.classList.contains('related-lookup')) {
                lookup = sib;
            }
        }

        // 3) broader fallback: any related-lookup anchor that mentions this field id in onclick
        if (!lookup) {
            lookup = document.querySelector('a.related-lookup[onclick*="' + input.id + '"]') || null;
        }

        // 4) last resort: first related-lookup on the same row
        if (!lookup) {
            const row = input.closest('tr') || input.closest('.form-row') || input.parentNode;
            if (row) lookup = row.querySelector('a.related-lookup');
        }

        if (lookup) {
            // When clicking the input, trigger the lookup link (open popup/search)
            input.addEventListener('click', function(e) {
                e.preventDefault();
                // Trigger the anchor's click
                lookup.click();
            });
            // Optional: also open on Enter key (ux)
            input.addEventListener('keydown', function(e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    lookup.click();
                }
            });
        } else {
            // If no lookup found, keep it readonly (no popup available)
            // console.warn('Related lookup not found for', input);
        }
    });
});
