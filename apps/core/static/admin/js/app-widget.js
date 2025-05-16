'use strict';
{
    const $ = django.jQuery;

    $.fn.djangoAdminAppWidget = function() {
        $.each(this, function(i, element) {
            const $appModelSelect = $(element).parents('.app-widget').find('.js-app-model-select');
            const $appObjectSelect = $(element);
            const $appInput = $(element).parents('.app-widget').find('.js-app-input');
            const $appContentField = $(element).data("content-field") ? $(element).parents('form').find(':input[name="'+$(element).data("content-field")+'"]') : null;
            const $appObjectField = $(element).data("object-field") ? $(element).parents('form').find(':input[name="'+$(element).data("object-field")+'"]') : null;

            function setInputValue() {
                var data = {
                    'content_type_id': $appModelSelect.val(),
                    'object_pk': $(element).val()
                }

                $appContentField ? $appContentField.val(data['content_type_id']) : null;
                $appObjectField ? $appObjectField.val(data['object_pk']): null;
                $appInput.val(JSON.stringify(data));
            }

            function loadInputData() {
                let initialData = {
                    'content_type_id': "",
                    'object_pk': null
                }
                try {
                    $.extend(initialData, JSON.parse($appInput.val()));
                } catch(e) {
                    // error handle
                }

                $appObjectSelect.val(initialData['object_pk']);

                if ($appModelSelect.find('option[value="' + initialData['content_type_id'] + '"]').length) {
                    $appModelSelect.val(initialData['content_type_id']);
                }

                if($appModelSelect.val() === "") {
                    $appObjectSelect.prop("disabled", true);
                } else {
                    $appObjectSelect.prop("disabled", false);
                }
            }

            $appModelSelect.on('change', _select => {
                if($appModelSelect.val() === "") {
                    $appObjectSelect.prop("disabled", true);
                } else {
                    $appObjectSelect.prop("disabled", false);
                }
                $appObjectSelect.data('select2').results.clear();
                $appObjectSelect.find('option').remove();
                $appObjectSelect.val('').change();

                setInputValue();
            });

            // load data
            loadInputData();

            $appObjectSelect.on('change', _select => {
                setInputValue();
            });

            $appObjectSelect.select2({
                ajax: {
                    data: (params) => {
                        const appModelSelected = $appModelSelect.find(":selected");
                        return {
                            term: params.term,
                            page: params.page,
                            app_label: appModelSelected.data('app-label'),
                            model_name: appModelSelected.data('model-name'),
                        };
                    }
                }
            });
        });
        return this;
    };

    $(function() {
        // Initialize all autocomplete widgets except the one in the template
        // form used when a new formset is added.
        $('[data-apptize="true"]').not('[name*=__prefix__]').djangoAdminAppWidget();
    });

    document.addEventListener('formset:added', (event) => {
        $(event.target).find('[data-apptize="true"]').djangoAdminAppWidget();
    });
}