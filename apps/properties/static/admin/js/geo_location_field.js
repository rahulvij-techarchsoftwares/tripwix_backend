function parseCoordinates(position,zoom){
    var coordinates = position.toString();
    coordinates= coordinates.replace("(","");
    coordinates = coordinates.replace(")","");
    return coordinates+","+zoom;
}
$(document).ready(function(){
    var geocoder = new google.maps.Geocoder();
    $(".geo_location_field_gmap").each(function(i,el){
        var infowindow,
            marker,
            set_marker = false,
            map,
            self = $(el),
            map_el = self.find(".gmap"),
            set_btn = self.find(".gmap_set_location");
            
            set_btn.hide();
        
        var info = self.find(".gmap_info"),
            id = map_el.attr("id"),
            field = self.next();

            field.hide();

        var latlng = null,
            zoom = 2;
        
        var setPosition = function(position){
            zoom = map.getZoom();
            field.val(parseCoordinates(position,zoom));
            info.find(".lat").html(position.lat());
            info.find(".lng").html(position.lng());
            info.find(".zoom").html(zoom);
        };
        
        var setMarker = function(position){
            setPosition(position);
            marker.setPosition(position);
        };
        
        set_btn.click(function(){
            setMarker(map.getCenter());
            return false;
        });
        
        self.find(".gmap_address").autocomplete({
            select: function(event,ui){
                var pos = ui.item.position;
                var lct = ui.item.locType;
                var bounds = ui.item.bounds;
                if (bounds){
                    map.fitBounds(bounds);
                    setMarker(ui.item.latlng);
                }
            },
            source: function(request, response){
                geocoder.geocode( {'address': request.term }, function(results, status) {
                    if (status == google.maps.GeocoderStatus.OK) {
                        var searchLoc = results[0].geometry.location;
                        var lat = results[0].geometry.location.lat();
                        var lng = results[0].geometry.location.lng();
                        var latlng = new google.maps.LatLng(lat, lng);
                        var bounds = results[0].geometry.bounds;

                        geocoder.geocode({'latLng': latlng}, function(results1, status1) {
                            if (status1 == google.maps.GeocoderStatus.OK) {
                                if (results1[1]) {
                                    response($.map(results1, function(loc) {
                                        var lat = loc.geometry.location.lat();
                                        var lng = loc.geometry.location.lng();
                                        return {
                                            label  : loc.formatted_address,
                                            value  : loc.formatted_address,
                                            bounds : loc.geometry.bounds,
                                            latlng : new google.maps.LatLng(lat, lng)
                                        }
                                    }));
                                }
                            }
                        });
                    }
                });
            }
        });
        
        if(field.val()!=""){
            var coordinates = field.val().split(",");
            if(coordinates.length==3){
                latlng = new google.maps.LatLng(coordinates[0], coordinates[1]);
                zoom = parseInt(coordinates[2]);
            }
            set_marker = true;
        }
        if(latlng==null){
            var latlng = new google.maps.LatLng(0, 0);
        }
        var mapOptions = {
            zoom: zoom,
            center: latlng,
            mapTypeId: google.maps.MapTypeId.ROADMAP
        };
        
        
        map_el.width(580).height(300);
        map = new google.maps.Map(document.getElementById(id), mapOptions);
        google.maps.event.addListenerOnce(map, 'tilesloaded', function(){
            marker = new google.maps.Marker({
                map: map,
                draggable:true
            });
            if(set_marker){
                setPosition(latlng);
                marker.setPosition(latlng);
            }
            infowindow = new google.maps.InfoWindow({
                content: 'The position has been set!'
            });
            google.maps.event.addListener(marker, 'dragend', function(){
                var position = marker.getPosition();
                map.panTo(position);
                setPosition(position);
                infowindow.open(map,marker);
            });
            set_btn.show();
        });
        
        google.maps.event.addListener(map, 'zoom_changed', function(event) {
            if(marker.getPosition()!=undefined){
                setPosition(marker.getPosition());
            }
        });
        
    });
    
    
});