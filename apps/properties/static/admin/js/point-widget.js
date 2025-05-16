(function($) {

function GoolgeMapWidget(options) {
    this.map = null;
    this.marker = null;
    this.wkt_f = new Wkt.Wkt();
    this.geocoder = new google.maps.Geocoder();
    this._geo_cache = {};
    this._last_result = null;
    // Default options
    this.options = {
        map_options: {
        	zoom: 12,
        	center: new google.maps.LatLng(0, 0),
        	mapTypeId: google.maps.MapTypeId.ROADMAP,
        	scrollwheel: false
        },
        map_srid: 4326,
        default_zoom: 2,
    };

    // Altering using user-provided options
    for (var property in options) {
        if (options.hasOwnProperty(property)) {
            this.options[property] = options[property];
        }
    }

    this.map = this.create_map();

    this.$el = $("#"+this.options.id+"_div_map");
    this.$field = $("#"+this.options.id);

    var _self = this;
    this.$addressDropdown = this.$el.find(".dropdown-menu");
	this.$addressDropdown.parent().on('show.bs.dropdown', function(){
		var value = _self.$address.val();
    	_self.fetch_geocoder(value);
	});


    this.$address = this.$el.find(".address-search-input").on("keydown", function(e){
    	switch(e.keyCode) {
	        // ignore navigational & special keys
	        case 13: // return
	            e.preventDefault();
	            if(!_self.$addressDropdown.parent().hasClass("open")){
	            	_self.$addressDropdown.dropdown('toggle');
	        	}
	            return false;
	        default:
	            break;
	    }
    });

    var real_address_field = $("body :input[type='text']").filter(":visible").filter(":input[name='address']");
    if(real_address_field.length>0){
    	if(this.$field.val().length==0){
    		this.$address.val(real_address_field.val());
    	}
    	real_address_field.on("keyup", function(){
    		if(_self.$field.val().length==0){
    			_self.$address.val(real_address_field.val());
    		}
    	});
    }

    this.$setBtn = this.$el.find(".set_position").on("click", function(e){
      e.preventDefault();
      var latLng = _self.map.getCenter();
      _self.set_position(latLng);
      _self.$setBtn.prop("disabled", true);
      _self.$clearBtn.prop("disabled", false);
      _self.$seeMapBtn.prop("disabled", false);
    });

    this.$clearBtn = this.$el.find(".clear_position").on("click", function(e){
      e.preventDefault();
      _self.$field.val("");
      _self.marker.setMap(null);
      _self.$clearBtn.prop("disabled", true);
      _self.$setBtn.prop("disabled", false);
      _self.$seeMapBtn.prop("disabled", true);
    });

    this.$seeMapBtn = this.$el.find(".open_map").on("click", function(e) {
      e.preventDefault();
      console.log(_self);
      var lat = _self.marker.position.lat();
      var lng = _self.marker.position.lng();
      var zoom = _self.map.zoom;
      var url = 'https://maps.google.com/?q=' + lat + ',' + lng + '&ll=' + lat + ',' + lng + '&z=' + zoom;
      window.open(url, '_blank');
    });

    var value = this.$field.val();
    var set_marker = false;
    if (value) {
    	var wkt = this.read_wkt(value);
    	this.marker = wkt.toObject();
    	this.map.setCenter(this.marker.position);
    	set_marker = true;
    } else {
    	this.marker = new google.maps.Marker();
    	this.map.setZoom(this.options.default_zoom);
		this.$setBtn.prop("disabled", false);
	}

    google.maps.event.addListener(this.map, 'center_changed', function(){
    	_self.$setBtn.prop("disabled", false);
   	});


    google.maps.event.addListenerOnce(this.map, 'tilesloaded', function(){
    	if(set_marker){
    		_self.$clearBtn.prop("disabled", false);
    		_self.marker.setMap(_self.map);
    	}
    	_self.marker.setOptions({"draggable": true});
    	google.maps.event.addListener(_self.marker, 'dragend', function(e){
            var position = e.latLng;
            _self.set_position(position);
            //infowindow.open(map,marker);
        });
    });

}

GoolgeMapWidget.prototype.show_results = function(results) {
	var _self = this;
	_self._last_result = results;
	_self.clear_results();
	for (var i=0; i < results.length; i++) {
        var option = '<li><a tabindex="-1" href="#'+results[i].value+'" data-index="'+i+'"><i class="text-danger fa fa-map-marker"></i>&nbsp;&nbsp;'+results[i].label+'</a></li>';
        _self.$addressDropdown.append(option);
    };

    _self.$addressDropdown.find("li a").on("click", function(e){
    	e.preventDefault();
    	if(!confirm(_self.$el.data("confirm"))){
            return false;
        }
    	var result = _self._last_result[$(this).data("index")];
    	_self.set_position(result.latlng);
    });

};

GoolgeMapWidget.prototype.set_results = function(value, results) {
    this._geo_cache[value] = results;
    this.show_results(results);
};

GoolgeMapWidget.prototype.clear_results = function() {
	var _self = this;
	_self.$addressDropdown.find("li a").off("click");
	_self.$addressDropdown.find("li").remove();
};

GoolgeMapWidget.prototype.no_results = function() {
	var _self = this;
	_self.clear_results();
	_self.$addressDropdown.append('<li class="disabled"><a><i class="fa fa-warning"></i> '+_self.$el.data("noresults")+'</a></li>');
};

GoolgeMapWidget.prototype.fetch_geocoder = function(value) {
	var _self = this;
	// UNREGISTER EVENTS
	_self.clear_results();
	_self.$addressDropdown.append('<li class="disabled"><a><i class="fa fa-spin fa-spinner"></i> '+_self.$el.data("search")+'...</a></li>')
	if(value.length<2){
		_self.no_results();
		return false;
	}

	if(_self._geo_cache[value]!==undefined){
        _self.set_results(value, _self._geo_cache[value]);
        return false;
    }
    _self.geocoder.geocode( {'address': value }, function(results, status) {
        if (status == google.maps.GeocoderStatus.OK) {
            _self.set_results(value, $.map(results, function(loc) {
                var lat = loc.geometry.location.lat();
                var lng = loc.geometry.location.lng();
                return {
                    label  : loc.formatted_address,
                    value  : loc.formatted_address,
                    bounds : loc.geometry.bounds,
                    latlng : new google.maps.LatLng(lat, lng)
                }
            }));
        } else if(status == google.maps.GeocoderStatus.ZERO_RESULTS){
        	_self.no_results();
        }
    });
};

GoolgeMapWidget.prototype.create_map = function() {
	return new google.maps.Map(document.getElementById(this.options.map_id), this.options.map_options);
};

GoolgeMapWidget.prototype.get_ewkt = function(marker) {
	var wkt = new Wkt.Wkt();
    wkt.fromObject(marker);
    return "SRID=" + this.options.map_srid + ";" + wkt.write();
};

GoolgeMapWidget.prototype.read_wkt = function(wkt) {
    var prefix = 'SRID=' + this.options.map_srid + ';'
    if (wkt.indexOf(prefix) === 0) {
        wkt = wkt.slice(prefix.length);
    }
    return this.wkt_f.read(wkt);
};

GoolgeMapWidget.prototype.write_wkt = function(feat) {
    window.user_changed_input = true;
    document.getElementById(this.options.id).value = this.get_ewkt(feat);
};

GoolgeMapWidget.prototype.set_position = function(latLng) {
	this.map.panTo(latLng);
	this.marker.setPosition(latLng);
	this.marker.setMap(this.map);
	this.write_wkt(this.marker);
	this.$setBtn.prop("disabled", true);
};
window.GoolgeMapWidget = GoolgeMapWidget;
})(django.jQuery);
