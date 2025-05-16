'use strict';
{
    const $ = django.jQuery;

    $.fn.djangoAdminCtaWidget = function() {
        $.each(this, function(i, element) {
            const $input = $(element);
            const $scope = $(element).parents('.cta-widget');
            const $appModelSelect = $scope.find('.js-app-model-select');
            const $appObjectSelect = $scope.find('.admin-autocomplete')

            var setData = function() {
                var data = {}
                $scope.find('[data-json-key]').each(function(i) {
                    const value = $(this).is(':checkbox') ? $(this).is(':checked') : $(this).val();
                    data[$(this).data('json-key')] = value;
                });
                $input.val(JSON.stringify(data));
            };

            var loadData = function() {
                var value = $input.val();
                if (value != undefined && value != "") {
                    var data = JSON.parse(value);
                } else {
                    var data = {};
                }
                var initial = {
                    'content_type_id': "",
                    'object_pk': null
                }
                $scope.find('[data-json-key]').each(function(i){
                    initial[$(this).data('json-key')] = $(this).data('json-default') ? $(this).data('json-default') : ''
                });
                var initial_data = $.extend(initial, data);
                $.each(initial_data, function( key, value ) {
                    $scope.find('[data-json-key="'+key+'"]').is(':checkbox') ? $scope.find('[data-json-key="'+key+'"]').attr('checked', value): $scope.find('[data-json-key="'+key+'"]').val(value);
                });

                if($appModelSelect.val() === "") {
                    $appObjectSelect.prop("disabled", true);
                } else {
                    $appObjectSelect.prop("disabled", false);
                }
            };

            loadData();

            $appModelSelect.on('change', _select => {
                if($appModelSelect.val() === "") {
                    $appObjectSelect.prop("disabled", true);
                } else {
                    $appObjectSelect.prop("disabled", false);
                }
                $appObjectSelect.data('select2').results.clear();
                $appObjectSelect.find('option').remove();
                $appObjectSelect.val('').change();
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

            function setCtaUrl() {
                const url = $scope.find('.js-cta-url-group input').val();
                const internal = $scope.find('.js-cta-type-input').is(':checked');
                if (internal) {
                    $scope.find('.js-cta-type').text($appModelSelect.find('option:selected').text());
                    $scope.find('.js-cta-url').text($appObjectSelect.find('option:selected').text());
                    $scope.find('.js-ctad-url').attr('href', null);
                } else {
                    if(url.startsWith('http')) {
                        $scope.find('.js-ctad-url').attr('href', url);
                    } else {
                        $scope.find('.js-ctad-url').attr('href', null);
                    }
                    $scope.find('.js-cta-url').text(url);
                    $scope.find('.js-cta-type').text('Link');
                }
            }

            function handleFieldElementChange(el) {
                var updateText = $(el).data('json-text');
                if (updateText) {
                    var textValue = $(el).is("select") ? $(el).find('option:selected').text() : $(el).val();
                    $scope.find(updateText).text(textValue);
                }
                if ($(el).data('json-key') == 'internal') {
                    if($(el).is(':checked')) {
                        $scope.find(".js-cta-url-group").addClass("d-none");
                        $scope.find(".js-cta-app-group").removeClass("d-none");
                    } else {
                        $scope.find(".js-cta-url-group").removeClass("d-none");
                        $scope.find(".js-cta-app-group").addClass("d-none");
                    }
                }
                setCtaUrl();
                setData();
            }

            // set events
            $scope.find('[data-json-key]').each(function(i) {
                if ($(this).is("input[type='text']")) {
                    $(this).on('change', function(){ handleFieldElementChange(this) }).on('keyup', function(){ handleFieldElementChange(this) });
                } else {
                    $(this).on('change', function(){ handleFieldElementChange(this) });
                }
                handleFieldElementChange(this);
            });


        });
        return this;
    };

    $(function() {
        // Initialize all autocomplete widgets except the one in the template
        // form used when a new formset is added.
        $('[data-cta-init="true"]').not('[name*=__prefix__]').djangoAdminCtaWidget();
    });

    document.addEventListener('formset:added', (event) => {
        $(event.target).find('[data-cta-init="true"]').djangoAdminCtaWidget();
    });

}