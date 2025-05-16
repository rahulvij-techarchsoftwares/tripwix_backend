(function($, window){

function dismissEditPopup(win,object_id,object)
{   
    win.close();
}

$(document).ready(function(){

    $(".media_photo_widget").closest(".related-widget-wrapper").find(".related-links").remove();

    var photo_element = $('<li><span></span><img src="" /></li>');
    function handle_thumbnail(widget){
        widget.find(".media-items-container li:not(.template-upload)").removeClass("thumbnail").eq(0).addClass("thumbnail");
        widget.find(".media-items-container li p.tooltip").text("").eq(0).text("Thumbnail");
    }

    function handle_upload_ui(widget){
        if(widget.find(".template-upload").length>0){
          widget.find('.has_new_files').removeClass("hide");
        } else {
          widget.find('.has_new_files').addClass("hide");
        }
    }
    // GETS THE CORRECT IMAGES AND UPDATES THE INPUT WITH THE RAW IDs
    function handle_items(widget){
        var values = new Array();
        widget.find(".media-items-container li").each(function(i,el){
            var id = $(el).data("rel");
            if(parseInt(id)>0){
                values.push(id);
            }
        });
        widget.data("input").val(values.join(","));
        handle_thumbnail(widget);
        window.user_changed_input = true;
    }
    
    function handle_sortable(widget){
        widget.find(".media-items-container").sortable("destroy").sortable({
            distance: 20,
            onDragStart: function($item, container, _super, event) {
              widget.find(".media-items-container li").removeClass("thumbnail");
              _super($item, container);
            },
            onDrop: function($item, container, _super, event) {
              handle_thumbnail(widget);
              handle_items(widget);
              _super($item, container);
            }
        });
    }
    
    function imagePopup(url){
        newwindow = window.open(url+"?_popup=1", "djgalleryplimage", 'height=500,width=700,resizable=yes,scrollbars=yes');
        if (window.focus) {newwindow.focus()}
        return false;
    }

    function on_remove(e){
      e.preventDefault();
      var photo = $(this).closest("li");
      var widget = $(this).closest(".media_photo_widget");
      unbind_events(photo);
      photo.data("rel","0").animate({opacity:0},300,function(){$(this).remove();handle_thumbnail(widget);});
      handle_items(widget);
      return false;
    }

    function on_edit(e){
      e.preventDefault();
      var photo = $(this).closest("li");
      var widget = $(this).closest(".media_photo_widget");
      var new_url = "/admin/cms_media/mediaphoto/";
      if(widget.data("changeurl")){
        new_url = widget.data("changeurl");
      }
      var href = new_url+photo.data("rel")+"/";
      imagePopup(href);
      return false;
    }

    function bind_events($el){
      $el.on('click', '.edit', on_edit);
      $el.on('click', '.remove', on_remove);
    }

    function unbind_events($el){
      $el.off('click', '.edit', on_edit);
      $el.off('click', '.remove', on_remove);
    }

    bind_events($(".media_photo_widget .media-items-container li"));
    
    // HANDLE GALLERY PHOTOS EVENTS
    function handle_photos(holder,widget){
        holder.find("li").click(function(){
            var id = $(this).data("id");
            var img_src = $(this).find("img").prop("src");
            if($(this).hasClass("selected")){
                $(this).removeClass("selected");
                var item = widget.find(".media-items-container li[data-rel="+id+"]");
                unbind_events(item);
                item.remove();
            } else {
                $(this).addClass("selected");
                var new_photo = $('<li data-rel="'+id+'"><p class="tooltip"></p><img src="'+img_src+'" /><div class="btn_container"><span class="dragger"></span><a class="edit" href="#"></a><a class="remove" href="#"></a></div></li>');
                widget.find(".media-items-container").append(new_photo);
                bind_events(new_photo);
            }
        });
    }
    
    // HANDLE LOAD OF PHOTOS
    var request_photos = function(modal, p){
      var data = modal.data();
      var widget = data.widget;
      var input = widget.data("input");
      var no_image_text = widget.data("no-image-text");
      var values = input.val().split(",");
      var holder = modal.find(".photo_wrapper");
      var paginator = modal.find(".photo_pagination");
      var uri = data.uri;
      if(p!==undefined){
        uri+="?page="+p;
      }
      $.getJSON(uri, function(data){
        holder.empty();
        paginator.empty();

        for (var i = 1; i <= data.paginator.limit; i++) {
          var current = "";
          if(data.paginator.current==i){
            current = "active";
          }
          var btn = $('<li class="'+current+'"><a href="#" data-page="'+i+'">'+i+'</a></li>');
          paginator.append(btn);

          btn.find("a").click(function(){
            if($(this).data("page")==data.paginator.current){return false;}
            request_photos(modal, $(this).data("page"));
            return false;
          });
        };


        var photos = data.photos;
        if(photos.length>0){
          for (var i=0; i < photos.length; i++) {
              var photo = photo_element.clone();
              var id = new String(photos[i].id);
              if($.inArray(id.toString(),values)>=0){
                  photo.addClass("selected");
              }
              photo.data("id",id.toString());
              photo.find('img').prop("src",photos[i].thumbnail);
              holder.append(photo);
          };
          handle_photos(holder,widget);
        } else {
          holder.append('<div class="empty-list">'+no_image_text+'</div>');
          paginator.hide();
        }
      });
    };

    // HANDLES WIDGETS
    $(".media_photo_widget").each(function(i,el){
        var widget = $(el);

        var module = widget.closest(".module.row");
        if(module.find(".form-group").length==1){
          widget.addClass("modular");
        }


        var modal = widget.find(".media_photo_modal");
        widget.find(".media_photo_modal").data("widget", widget);
        widget.data("input", widget.next());
        widget.data("input").hide();

        modal.on('show.bs.modal', function (e) {
          request_photos($(this));
        });
        modal.on('hide.bs.modal', function (e) {
          handle_items($(this).data("widget"));
        });


        var new_url = "/admin/cms_media/mediaphoto/upload/";
        if(widget.data("uploadurl")){
          new_url = widget.data("uploadurl");
        }
        widget.find(".choose_images").click(function(){
           widget.find(".media_photo_modal").modal("show");
           return false;
        });
        handle_sortable(widget);
        handle_thumbnail(widget);

        /* FILE UPLOAD */
        var max_size = 2000000;
        widget.fileupload({
            url: new_url,
            sequentialUploads: true,
            maxFileSize: max_size,
            dataType: 'json',
            autoUpload: false,
            acceptFileTypes: /(\.|\/)(gif|jpe?g|png)$/i,
            disableImageResize: /Android(?!.*Chrome)|Opera/.test(window.navigator.userAgent),
            previewMaxWidth: widget.data("width"),
            previewMaxHeight: widget.data("height"),
            filesContainer: widget.find(".media-items-container"),
            dropZone: widget.find(".media-wrapper")
        }).bind("fileuploadfinished", function(o, data){
            handle_items(widget);
            handle_upload_ui(widget);
        }).bind("fileuploadcompleted", function(o, data){
            bind_events(data.context);
        }).bind("fileuploadadded", function(o, data){
            handle_upload_ui(widget);
        }).bind("fileuploadstopped", function(o){
            handle_upload_ui(widget);
        })


    });

});

})(jQuery, window);