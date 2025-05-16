
function getSyncScriptParams() {
	var scripts = document.getElementsByTagName('script');
	var lastScript = scripts[scripts.length-1];
	return {
	    app_name : lastScript.getAttribute('data-app-label'),
	    model_name : lastScript.getAttribute('data-model-name')
	};
}

var opts = getSyncScriptParams();

$(function () {

	var app_name = opts['app_name'];
	var model_name = opts['model_name'];

    // Fix django admin relation urls..
    // eg: /properties_/property/ -->  /properties_sale/saleproperty/
    $('.nav-tabs.main-content-nav > li > a, a.addlink, .breadcrumb > li > a, .results > table > tbody > tr > th > a, .app-legal_documents > #main-container > #main-content > #content > form > .btn-toolbar > .btn-group > .btn.btn-inverse').each( function( index, element ){
        var url = $(this).attr('href');
        var parts = url.split('/');
        parts = parts.filter(function(e){return e});
        // console.log( parts );

        if (parts[1] != opts['app_name']){
            url = url.replace('/'+parts[1]+'/', '/'+opts['app_name']+'/');
        }
        if (parts[2] != opts['model_name']){
            url = url.replace('/'+parts[2]+'/', '/'+opts['model_name']+'/');
        }

        $(this).attr('href', url);

        if($(this).find('.fa').hasClass('disabled')){
            $(this).closest('li').addClass('disabled');
        }
    });
});
