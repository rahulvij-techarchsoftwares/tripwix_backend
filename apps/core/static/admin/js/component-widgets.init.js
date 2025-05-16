'use strict';
{
    const $ = django.jQuery;

    $.fn.djangoAdminComponentWidget = function() {
        $.each(this, function(i, element) {
            const $componentWidgetField = $(element);
            console.log($componentWidgetField);
        });
        return this;
    };

    $(function() {
        // Initialize all autocomplete widgets except the one in the template
        // form used when a new formset is added.
        $('[data-component-widget]').not('[name*=__prefix__]').djangoAdminComponentWidget();
    });

}