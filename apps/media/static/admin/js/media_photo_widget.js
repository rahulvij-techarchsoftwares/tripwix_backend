Dropzone.autoDiscover = false;

(function($, window){
  
  window.dismissEditPopup = function(win, object_id, object) {
    win.close();

    var $mediaItems = $('.media-items-container .media-item[data-photo-id="'+ object_id +'"]');

    $mediaItems.each(function(i, el) {
      var $mediaItem = $(el);

      $mediaItem.find('.preview img').attr('src', object.thumbnail);
      var $info = $mediaItem.find('.info');
      if (object.caption) {
        if($info.length==0){
          $mediaItem.find('.preview').after('<div class="info"><p class="name">' + object.caption + '</p></div>');
        } else {
          $info.find('.name').text(object.caption);
        }
      } else {
        $info.remove();
      }

    });
  }

  function imagePopup(url){
    var url = url + "change/?_popup=1";
    newwindow = window.open(url, "djgalleryplimage", 'height=500,width=700,resizable=yes,scrollbars=yes');
    if (window.focus) {newwindow.focus()}
    return false;
  }

  function handleUploadWidget($widget){
    // handle upload disable on max files
    var maxFiles = $widget.data("maxFiles");
    if(maxFiles != null){
      if($widget.find(".media-items-container .media-item").length >= maxFiles) {
        $widget.addClass("upload-disabled");
        $widget.find(".fileinput-button").attr("disabled", true);
        return;
      }
    }
    $widget.removeClass("upload-disabled");
    $widget.find(".fileinput-button").attr("disabled", false);
  }

  function handleThumbnail($widget){
    $widget.find(".media-items-container .media-item").removeClass("thumbnail").eq(0).addClass("thumbnail");
    //$widget.find(".media-items-container .media-item p.tooltip").text("").eq(0).text("Thumbnail");
  }

  function handleItems($widget, $widgetInput){
    var values = new Array();
    $widget.find(".media-items-container .media-item").each(function(i,el){
      var id = $(el).data("id");
      if(parseInt(id)>0){
          values.push(id);
      }
    });
    $widgetInput.val(values.join(","));
    handleThumbnail($widget);
    handleUploadWidget($widget);
    window.user_changed_input = true;
  }

  function bindEvents($mediaPhotoWidget, $widgetInput) {
    $mediaPhotoWidget.on('click', '.media-item .remove', function onDelete(e) {
      var $deleteButton = $(this);
      $deleteButton.attr('disabled', 'disabled');

      var $mediaItem = $(this).parents('.media-item');
      $mediaItem.data('id', null);
      $mediaItem.addClass('removing');
      setTimeout(function removeMediaItem(){
        $mediaItem.remove();
        handleThumbnail($mediaPhotoWidget);
        handleUploadWidget($mediaPhotoWidget);
      }, 300);
      handleItems($mediaPhotoWidget, $widgetInput);
    });

    $mediaPhotoWidget.on('click', '.media-item .edit', function onEdit(e) {
      e.preventDefault();
      var $mediaItem = $(this).parents('.media-item');
      var changeUrl = $mediaPhotoWidget.data("changeUrl");
      var href = changeUrl + $mediaItem.data("id") + "/";

      imagePopup(href);
      return null;
    });

  }

  function addDataToMediaItem($mediaItem, photoData) {
    $mediaItem.data("id", photoData.id);
    $mediaItem.data("caption", photoData.caption);
    $mediaItem.data("original", photoData.original);
    $mediaItem.data("thumbnail", photoData.thumbnail);
  }

  function handleMediaItem($mediaItem) {
    var photoData = $mediaItem.data();

    $mediaItem.removeClass('dz-image-preview');
    $mediaItem.find('.upload-info, .start').remove();
    $mediaItem.find('img').attr('src', photoData.thumbnail);
    $mediaItem.find('.original').attr('href', photoData.original);
    if(photoData.caption) {
      $mediaItem.find('.info').text(photoData.caption);
    } else {
      $mediaItem.find('.info').remove();
    }
  }

  function handleMediaPhotoEvents($holder, $widget, maxFilesOption){
    $holder.find("li").on('click', function onClick() {
      var $self = $(this);
      var photoData = $self.data();
      if($self.hasClass("selected")){
        $widget.find(".media-items-container li").each(function(i, el) {
          var $el = $(el);
          if($el.data('id') == photoData.id) {
            $el.remove();
            $self.removeClass("selected");
          }
        });
      } else {
        if(maxFilesOption != null) {
          if(maxFilesOption == 1) {
            $widget.find(".media-items-container li").remove();
            $holder.find("li").removeClass("selected");
          } else if (maxFilesOption == $widget.find(".media-items-container li").length) {
            // TODO give some visual feedback of limit reached
            return;
          }
        }

        $self.addClass("selected");
        var $mediaItem = $($widget.data('previewTemplate'));
        addDataToMediaItem($mediaItem, photoData);
        handleMediaItem($mediaItem);
        $widget.find(".media-items-container").append($mediaItem);
      }
    });
  }

  function handleMediaPhotosGallery(options, page){

    var $widget = options.widget;
    var $holder = options.modal.find(".js-photo-wrapper");
    var $paginator = options.modal.find(".js-photo-pagination");
    var values = options.input.val().split(",");
    var maxFiles = options.maxFiles;
    var $photoElementTemplate = $('<li class="media-item"><div class="preview"><img src="" /></div><svg class="selected-item-svg"><use xlink:href="#svg-check"></svg></li>');
    var noPhotosCopy = $widget.data('noPhotosCopy');
    var photosUrl = $widget.data('photosUrl');

    if(page!==undefined){
      photosUrl+="?page="+page;
    }

    $.getJSON(photosUrl, function(resp){

      // unbind events before clearing out
      $holder.find("li").off('click');
      $paginator.find("a").off('click');

      // clear elements
      $holder.empty();
      $paginator.empty();

      $paginator.removeClass('d-none');

      for (var i = 1; i <= resp.paginator.limit; i++) {
        var current = "";
        if(resp.paginator.current==i) { current = "active"; }
        var btn = $('<li class="page-item '+current+'"><a class="page-link" href="#" data-page="'+i+'">'+i+'</a></li>');
        $paginator.append(btn);

        btn.find("a").on('click', function onClick(){
          if($(this).data("page")==resp.paginator.current){return false;}
          handleMediaPhotosGallery(options, $(this).data("page"));
          return false;
        });
      };

      var photos = resp.photos;
      if(photos.length>0){
        for (var i=0; i < photos.length; i++) {
          var photo = $photoElementTemplate.clone();
          var id = new String(photos[i].id);
          if($.inArray(id.toString(),values)>=0){
            photo.addClass("selected");
          }
          addDataToMediaItem(photo, photos[i]);
          photo.find('img').prop("src", photos[i].thumbnail);
          $holder.append(photo);
        };
        handleMediaPhotoEvents($holder, $widget, maxFiles);
      } else {
        $holder.append('<li class="empty-list">'+ noPhotosCopy +'</li>');
        $paginator.addClass('d-none');
      }

    });

  };

  $(document).ready(function(){

    var $mediaPhotoWidgets = $(".media_photo_widget");

    // HANDLES WIDGETS
    $mediaPhotoWidgets.each(function(i, el) {
      var $mediaPhotoWidget = $(el);
      var $widgetParent = $(el).parent();

      // find input
      var $widgetInput = $widgetParent.find("input");

      var widgetData = $mediaPhotoWidget.data();
      var dropzone_element = $mediaPhotoWidget.find('.media-wrapper')[0];

      var previewTemplate = $mediaPhotoWidget.find('.js-preview-template').html();
      $mediaPhotoWidget.data('previewTemplate', previewTemplate);
      $mediaPhotoWidget.find('.js-preview-template').remove();

      var $buttonsActions = $mediaPhotoWidget.find('.buttons-holder');
      var $hasNewFiles = $mediaPhotoWidget.find('.js-has-new-files');

      if ($widgetParent.hasClass('related-widget-wrapper')){
        $widgetParent.removeClass('related-widget-wrapper');
        $widgetParent.addClass("media-photo-widget-wrapper");
      }

      // Default options
      var options = {
        'uploadUrl': null,
        'thumbnailWidth': 180,
        'thumbnailHeight': 120,
        'parallelUploads': 2,
        'maxFilesize': 10, // 10mb set max file size
        'maxFiles': null,
        'acceptedFiles': 'image/*',
        'autoQueue': false,
        'resizeWidth': 2568,
        'csrfToken': $(':input[name="csrfmiddlewaretoken"]').val()
      }

      $.extend(options, widgetData);

      if (options.uploadUrl == null) {

        $mediaPhotoWidget.find('.fileinput-button').remove();
        $hasNewFiles.empty();

      } else {

        var widgetDropzone = new Dropzone(dropzone_element, {
          url: options.uploadUrl,
          thumbnailWidth: options.thumbnailWidth,
          thumbnailHeight: options.thumbnailHeight,
          parallelUploads: options.parallelUploads,
          maxFilesize: options.maxFilesize,
          maxFiles: options.maxFiles,
          acceptedFiles: options.acceptedFiles,
          previewTemplate: previewTemplate,
          autoQueue: options.autoQueue,
          previewsContainer: $(dropzone_element).find(".media-items-container")[0],
          clickable: $buttonsActions.find(".fileinput-button")[0],
          resizeWidth: options.resizeWidth,
          headers: {
            'X-CSRFToken': options.csrfToken
          },
          dragstart(e) {
            this.dragel = e.target;
            return;
          },
          init: function() {
            // overwrite drop event, to enable sortable compatibility
            this.drop = function(e) {
              var dragged = this.dragel;
              this.dragel = null;
              if (!e.dataTransfer) {
                return;
              }
              if(dragged != null || dragged != undefined) {
                if (dragged.classList.contains("media-item")) {
                  return;
                }
              }
              this.emit("drop", e);
          
              // Convert the FileList to an Array
              // This is necessary for IE11
              let files = [];
              for (let i = 0; i < e.dataTransfer.files.length; i++) {
                files[i] = e.dataTransfer.files[i];
              }
          
              // Even if it's a folder, files.length will contain the folders.
              if (files.length) {
                let { items } = e.dataTransfer;
                if (items && items.length && items[0].webkitGetAsEntry != null) {
                  // The browser supports dropping of folders, so handle items instead of files
                  this._addFilesFromItems(items);
                } else {
                  this.handleFiles(files);
                }
              }
          
              this.emit("addedfiles", files);
            }
          }
        });

        widgetDropzone.on("addedfile", function(file) {
          // Hookup the start button
          file.previewElement.querySelector(".start").onclick = function(e) {
            e.preventDefault();
            widgetDropzone.enqueueFile(file);
          };

          $hasNewFiles.removeClass("d-none");
        });

        widgetDropzone.on("removedfile", function(file) {
          handleItems($mediaPhotoWidget, $widgetInput);
        });

        widgetDropzone.on("sending", function(file) {
          // And disable the start button
          file.previewElement.querySelector(".start").setAttribute("disabled", "disabled");
        });

        // On upload success
        widgetDropzone.on("success", function(file, results) {
          var resp = results[0];
          var $mediaItem = $(file.previewElement).clone();

          addDataToMediaItem($mediaItem, resp);
          handleMediaItem($mediaItem);

          $(file.previewElement).before($mediaItem);
          widgetDropzone.removeFile(file);

          handleItems($mediaPhotoWidget, $widgetInput);
          bindEvents($mediaPhotoWidget, $widgetInput);
        });

        widgetDropzone.on("queuecomplete", function(){
          $hasNewFiles.addClass("d-none");
        });
        // Bind main triggers
        $buttonsActions.find('.js-start').on('click', function onClick() {
          widgetDropzone.enqueueFiles(widgetDropzone.getFilesWithStatus(Dropzone.ADDED));
        });

        $buttonsActions.find('.js-cancel').on('click', function onClick() {
          widgetDropzone.removeAllFiles();
        });
      }

      // Handle Modal events
      if($mediaPhotoWidget.find(".media-photo-widget-modal").length>0) {

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

          handleItems($mediaPhotoWidget, $widgetInput);
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

          handleMediaPhotosGallery({
            'modal': $modalElement,
            'widget': $mediaPhotoWidget,
            'input':  $widgetInput,
            'maxFiles': options.maxFiles,
          });
        }

        var $modalElement = $mediaPhotoWidget.find(".media-photo-widget-modal");
        $modalElement.on('click', '[data-dismiss="modal"]', function onClick(event) {
          $(event.target).parents('.modal').trigger('media:hide-modal');
        });

        $modalElement.on('click', function onClick(event) {
          var $modal = $(event.target);
          if($modal.hasClass('modal')) {
            $modalElement.trigger('cms:hide-modal');
          }
        });

        $modalElement.on('media:hide-modal', function(event){
          if(!$('body').hasClass('modal-open')){ return }
          hideModal($(this));
        });

        $modalElement.on('media:show-modal', function(event){
          if($('body').hasClass('modal-open')){ return }
          showModal($(this));
        });

        $mediaPhotoWidget.find('.js-open-photo-gallery').on('click', function onClick(e) {
          var target = $(e.currentTarget).data('target');
          $(target).trigger('media:show-modal');
        });

      }

      new Sortable($mediaPhotoWidget.find(".media-items-container").get(0), {
        swapThreshold: 0.88,
        animation: 55,
        ghostClass: 'sortable-ghost',
        chosenClass: "sortable-chosen",
        dragClass: "sortable-drag",
        onStart: function (evt) {
          $mediaPhotoWidget.find(".media-items-container .media-item").removeClass("thumbnail");
          evt.oldIndex;
        },
        onSort: function (evt) {
          handleItems($mediaPhotoWidget, $widgetInput);
        },
        onUnchoose: function (evt) {
          handleItems($mediaPhotoWidget, $widgetInput);
        },
      });

      // Handle events
      bindEvents($mediaPhotoWidget, $widgetInput);

      // Handle Thumbnail
      handleThumbnail($mediaPhotoWidget);

      handleUploadWidget($mediaPhotoWidget);
    });


  });

})(django.jQuery, window);
