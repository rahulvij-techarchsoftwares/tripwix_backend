!function () {
	"use strict";

	var jQuery = $;

	jQuery(function ($) {

		var Visibility = {
			active_field: null,
			pub_date_field: null,
			pub_end_date_field: null,
			widget: $("#visibility-widget"),
			clear_pub_date: $('.visibility-widget-clear_pub_date'),
			clear_pub_end_date: $('.visibility-widget-clear_pub_end_date'),
			init: function (options) {
				options = $.extend({
					'active': 'is_active',
					'pub_date': 'publication_date',
					'pub_end_date': 'publication_end_date'
				}, options);

				this.active_field = $(".field-" + options.active);
				this.pub_date_field = $(".field-" + options.pub_date);
				this.pub_end_date_field = $(".field-" + options.pub_end_date);

				// hide is_active checkbox
				// $("input#id_is_active").addClass("hide");
				this.active_field.append(this.widget).find("div").eq(0).hide();
				this.widget.show().removeClass("hide");
				if (this.pub_date_field.length > 0) {
					this.pub_date_field.hide();
					// ADD CLEARABLE
					this.pub_date_field.find(".help").append(this.clear_pub_date);
				} else {
					this.clear_pub_date.remove();
					this.widget.find(".visibility-widget-pub_date").remove();
				}
				if (this.pub_end_date_field.length > 0) {
					this.pub_end_date_field.hide();
					// ADD CLEARABLE
					this.pub_end_date_field.find(".help").append(this.clear_pub_end_date);
				} else {
					this.clear_pub_end_date.remove();
					this.widget.find(".visibility-widget-pub_end_date").remove();
				}

				// FIRE EVENTS
				this.events();

				if (this.pub_date_field.length > 0) {
					if (this.pub_date_field.hasClass("errors") || this.pub_date_field.hasClass("has-error")) {
						this.widget.find(".visibility-widget-pub_date").click();
					}
				}
				if (this.pub_end_date_field.length > 0) {
					if (this.pub_end_date_field.hasClass("errors") || this.pub_end_date_field.hasClass("has-error")) {
						this.widget.find(".visibility-widget-pub_end_date").click();
					}
					if (this.pub_end_date_field.find(":input").val() != "") {
						this.widget.find(".visibility-widget-pub_end_date").click();
					}
				}
			},
			toDate: function (date_string) {
				var a = date_string.split(/[^0-9]/);
				if (a.length < 5) {
					return null;
				}
				var secs = a[5];
				if (secs == undefined) {
					secs = "0";
				}
				return new Date(a[0], a[1] - 1, a[2], a[3], a[4], secs);
			},
			onPubDate: function () {
				var text_value = [];
				$.each(this.pub_date_field.find(":input[type!='hidden']"), function (i, el) {
					text_value.push($(el).val());
				});
				var string_date = text_value.join(" ");

				var date = this.toDate(string_date);
				if (date == null) {
					return;
				}

				this.widget.find(".visibility-widget-visible .info span").text(string_date);
				this.widget.find(".visibility-widget-hidden .info span").text(string_date);

				if (!this.is_active()) {
					this.widget.find(".visibility-widget-hidden :input").prop("checked", true);
					return false;
				}

				if (this.toDate(string_date) > new Date()) {
					//FUTURE
					this.widget.find(".visibility-widget-hidden :input").prop("checked", true);
					this.widget.find(".visibility-widget-visible .info").hide();
					this.widget.find(".visibility-widget-hidden .info").show();

				} else {
					//PAST
					this.widget.find(".visibility-widget-visible :input").prop("checked", true);
					this.widget.find(".visibility-widget-visible .info").show();
					this.widget.find(".visibility-widget-hidden .info").hide();
				}
			},
			open_pub_date: function () {
				this.active_field.find(":input").eq(0).prop("checked", true);
				this.widget.find(".visibility-widget-pub_date").hide();
				if (this.widget.find(".visibility-widget-hidden :input").is(":checked")) {
					this.pub_date_field.find(":input[type!='hidden']").eq(0).val("");
				}
				this.pub_date_field.show();
			},
			close_pub_date: function () {
				this.widget.find(".visibility-widget-pub_date").show();
				this.pub_date_field.find(":input[type!='hidden']").eq(0).val("");
				this.pub_date_field.find(":input[type!='hidden']").eq(1).val("");
				this.pub_date_field.hide();
			},
			clear_date: function () {
				this.active_field.find(":input").eq(0).prop("checked", false);
				this.widget.find(".visibility-widget-hidden :input").prop("checked", true);
				this.widget.find(".visibility-widget-visible .info").hide();
				this.widget.find(".visibility-widget-hidden .info").hide();
				this.set_pub_date(new Date());
				this.close_pub_date();
			},
			set_date: function () {
				this.active_field.find(":input").eq(0).prop("checked", true);
				this.set_pub_date(new Date());
				this.onPubDate();
			},
			set_pub_date: function (date) {
				var date_val = date.getFullYear() + "-" + (date.getMonth() + 1) + "-" + date.getDate();
				var time_val = date.getHours() + ":" + date.getMinutes() + ":" + date.getSeconds();
				this.pub_date_field.find(":input[type!='hidden']").eq(0).val(date_val);
				this.pub_date_field.find(":input[type!='hidden']").eq(1).val(time_val);
			},
			open_pub_end_date: function () {
				this.widget.find(".visibility-widget-pub_end_date").hide();
				this.pub_end_date_field.show();
			},
			close_pub_end_date: function () {
				this.pub_end_date_field.find(":input[type!='hidden']").val("");
				this.widget.find(".visibility-widget-pub_end_date").show();
				this.pub_end_date_field.hide();
			},
			events: function () {

				var self = this;

				this.widget.find(".visibility-widget-visible .info").hide();
				this.widget.find(".visibility-widget-hidden .info").hide();

				this.onPubDate();

				this.widget.find(".visibility-widget-pub_date").on("click", function () {
					self.open_pub_date();
					return false;
				});

				this.widget.find(".visibility-widget-pub_end_date").on("click", function () {
					self.open_pub_end_date();
					return false;
				});

				this.clear_pub_date.on('click', function () {
					self.clear_date();
					return false;
				});

				this.clear_pub_end_date.on('click', function () {
					self.close_pub_end_date();
					return false;
				});

				if (this.pub_date_field.length > 0) {
					this.pub_date_field.find(":input").on("focus", function () { self.onPubDate(); });
					this.pub_date_field.find(":input").on("blur", function () { self.onPubDate(); });
					this.pub_date_field.find(":input").on("change", function () { self.onPubDate(); });
				}

				this.widget.find(":input").on("change", function () {
					if ($(this).val() == "1") {
						self.set_date();
					} else {
						self.clear_date();
					}
				});
			},
			is_active: function () {
				return this.active_field.find(":input").is(":checked");
			}
		};


		Visibility.init();

	});
}(django.jQuery);