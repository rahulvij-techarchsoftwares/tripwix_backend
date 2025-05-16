(function($) {
    function hideModal($target) {
      $backdrop = $target.data('backdrop');
      $backdrop.removeClass('show');
      $target.removeClass('show');
      setTimeout(function() {
        $target.removeAttr('style');
        $target.css({'display': 'none'});
        $backdrop.remove();
        $('body').removeClass('modal-open').removeAttr('style');
      }, 200);
    }
  
    function showModal($target) {
      $target.css({'display': 'block', 'paddingRight': '15px'});
      $backdrop = $('<div class="modal-backdrop fade"></div>');
      $target.data('backdrop', $backdrop);
      $('body').addClass('modal-open').css({'paddingRight': '15px'}).append($backdrop);
      setTimeout(function() {
        $backdrop.addClass('show');
        $target.addClass('show');
      }, 10);
    }
  
  
    $('[data-toggle="modal"]').on('click', function onToggleClick(e){
      e.preventDefault();
      var target = $(e.currentTarget).data('target');
      $(target).trigger('cms:show-modal')
    });
  
    var modalElementTargets = [];
    $('[data-toggle="modal"]').each(function(i, el) {
      var target = $(el).data('target');
      if(modalElementTargets.indexOf(target)<0) {
        modalElementTargets.push(target);
      }
    });
  
    for (var i = modalElementTargets.length - 1; i >= 0; i--) {
  
      var $modalElement = $(modalElementTargets[i]);
      $modalElement.on('click', '[data-dismiss="modal"]', function onClick(event) {
        $(event.target).parents('.modal').trigger('cms:hide-modal');
      });
  
      $modalElement.on('click', function onClick(event) {
        var $modal = $(event.target);
        if($modal.hasClass('modal')) {
          $modalElement.trigger('cms:hide-modal');
        }
      });
  
      $modalElement.on('cms:hide-modal', function(event){
        if(!$('body').hasClass('modal-open')){ return }
        hideModal($(this));
      });
  
      $modalElement.on('cms:show-modal', function(event){
        if($('body').hasClass('modal-open')){ return }
        showModal($(this));
      });
  
    }
  
  
  
  })(django.jQuery);
  