// static/admin/js/trace_select2_init.js
(function($){
    if (!django || !django.jQuery) {
        console.warn("trace_select2_init: django.jQuery not found");
        return;
    }
    var $ = django.jQuery;

    // Saqlab qo'yamiz
    var originalSelect2 = $.fn.select2;

    // Oʻzgartiramiz: chaqirilganda console.trace bilan qayd etamiz
    $.fn.select2 = function() {
        try {
            // faqat yangi elementlar uchun chiqaramiz (agar allaqachon init bo'lgan bo'lsa, class bo'ladi)
            this.each(function(i, el){
                var $el = $(el);
                var already = $el.hasClass('select2-hidden-accessible') || $el.data('select2-init-traced');
                if (!already) {
                    $el.data('select2-init-traced', true);
                    console.groupCollapsed("[TRACE select2 init] element:", el, " name=", el.name || el.id || "(no-name)");
                    console.log("element info:", {
                        id: el.id,
                        name: el.name,
                        classes: el.className,
                        href: window.location.href,
                        timestamp: new Date().toISOString()
                    });
                    // Print stack trace to see which JS file called this
                    console.trace("select2 init stack trace");
                    console.groupEnd();
                }
            });
        } catch (err) {
            console.error("trace_select2_init error:", err);
        }

        // chaqirilgandan so'ng asl funksiyani bajarish
        return originalSelect2.apply(this, arguments);
    };

    // Qo'shimcha: har bir .admin-autocomplete uchun hover/onclick da trace yuborish mumkin
    $(document).on('click', '.admin-autocomplete', function(){
        var el = this;
        console.log("[TRACE] admin-autocomplete clicked:", el, new Date().toISOString());
        // Network tabda qaysi requestlar keyin kelayotganini ko'rish uchun foydali
    });

})(window.jQuery || (window.django && window.django.jQuery));
