if (!jQuery) {
    jQuery = django.jQuery;
    $ = jQuery;
}

$(document).ready(function () {
    const objectId = $('.nav-link.active').attr('href')?.split('/')[4];
    const activeItems = [];

    $('#property_form').on('submit', function (event) {
        event.preventDefault();

        let csrfToken = $('input[name="csrfmiddlewaretoken"]').val();
        let items = $('.selectize-input .item[data-active="true"]');

        items.each(function () {
            activeItems.push($(this).attr('data-value'));
        });

        $.ajax({
            url: '/update_property_active_amenities/',
            type: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
                'Content-Type': 'application/json;charset=UTF-8'
            },
            data: JSON.stringify({
                property_id: objectId,
                active_amenities: activeItems
            }),
            success: function () {
                $('#property_form').append('<input type="hidden" name="_continue" value="1">');
                event.target.submit();
            },
            error: function (xhr, status, error) {
                console.error('AJAX call failed:', error);
            }
        });
    });
});