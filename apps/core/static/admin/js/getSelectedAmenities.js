$(document).ready(function () {
    const objectId = $('.nav-link.active').attr('href')?.split('/')[4];

    if (objectId) {
        $.ajax({
            url: '/get_property_active_amenities/' + objectId + '/',
            type: 'GET',
            success: function (response) {
                const activeAmenities = response;

                $('.selectize-input .item').each(function () {
                    const dataValue = $(this).attr('data-value');

                    if (activeAmenities.active_amenities.includes(parseInt(dataValue)) ||
                        activeAmenities.active_amenities.includes(dataValue)) {
                        $(this)
                            .attr('data-active', 'true')
                            .addClass('active');
                    }
                });
            },
            error: function (xhr, status, error) {
                console.error('Failed to load active amenities:', error);
            }
        });
    } else {
        console.error('objectId is not defined');
    }
});