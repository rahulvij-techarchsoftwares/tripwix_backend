(function () {
  var jQuery = django.jQuery || jQuery || $;
  jQuery(function ($) {

    function extendConfig(options, key, config, new_name) {
      if (new_name == undefined) {
        new_name = key;
      }
      if (options.hasOwnProperty(key)) {
        config[new_name] = options[key];
      }
    }

    $('[data-selectize="true"]').each(function (i, el) {

      var $selectizeElement = $(el);

      var selectizeRender = undefined;
      var $selectizeRender = $('#' + $selectizeElement.prop('id') + "_selectize_render");
      if ($selectizeRender.length > 0) {
        selectizeRender = eval('(' + $selectizeRender.html() + ')');
      }

      var parent_wrapper = $selectizeElement.parents('.related-widget-wrapper');
      if (parent_wrapper.length > 0) {
        parent_wrapper.removeClass('related-widget-wrapper').addClass('selectize-wrapper');
        parent_wrapper.find('.related-widget-wrapper-link').remove();
      }

      var options = $selectizeElement.data();

      var error_message = options.errorMessage
      if (error_message == undefined) {
        error_message = 'Ups, something went wrong, could not add item.';
      }

      var config = {
        'copyClassesToDropdown': false
      }

      extendConfig(options, 'valueField', config);
      extendConfig(options, 'labelField', config);
      extendConfig(options, 'create', config);
      extendConfig(options, 'persist', config);
      extendConfig(options, 'maxItems', config, 'max_items');
      extendConfig(options, 'sortField', config);

      if (options.hasOwnProperty('onInitialize')) {
        config['onInitialize'] = function () { eval(options['onInitialize']); }
      }
      if (options.hasOwnProperty('onChange')) {
        config['onChange'] = function (value) { eval(options['onChange']); }
      }
      if (options.hasOwnProperty('searchField')) {
        config['searchField'] = eval('(' + options['searchField'] + ')');
      }
      if (options.hasOwnProperty('searchField')) {
        config['searchField'] = eval('(' + options['searchField'] + ')');
      }

      if (selectizeRender !== undefined) {
        config['render'] = selectizeRender;
      }

      if (options.loadUrl != null || options.loadUrl != undefined) {
        config['load'] = function (query, callback) {
          if (!options.hasOwnProperty('preload')) {
            if (!query.length) return callback();
          }
          var element_extra_data = $selectizeElement.data('load-extra-data');
          if (element_extra_data) { var extra_data = eval(element_extra_data); } else { var extra_data = {}; }
          $.ajax({
            url: options.loadUrl,
            type: 'GET',
            dataType: 'json',
            data: {
              ...extra_data,
              term: query,
            },
            error: function () {
              callback();
            },
            success: function (res) {
              callback(res);
            }
          });
        }
      }

      if (options.hasOwnProperty('preload')) {
        config['preload'] = 'focus'
        config['loadThrottle'] = 50
      }
      if (options.addUrl != null || options.addUrl != undefined) {
        config['create'] = function (input, callback) {
          var csrf_token = $(":input[name='csrfmiddlewaretoken']").val();
          $.ajax({
            url: options.addUrl,
            type: 'POST',
            dataType: 'json',
            data: {
              input: input,
              csrfmiddlewaretoken: csrf_token
            },
            error: function () {
              alert(error_message);
              callback();
            },
            success: function (res) {
              callback(res);
            }
          });
        }
      }

      $selectizeElement.selectize(config);

    });

  });
}());