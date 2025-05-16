if(typeof django !== 'undefined'){

    (function ($) {
        "use strict";

        var jQuery = $;

        jQuery.expr[':'].parents = function(a, i, m) {
            return jQuery(a).parents(m[3]).length < 1;
        };

        jQuery(function($){
            var TranslationField = function (options) {
                this.el = options.el;
                this.cls = options.cls;
                this.id = '';
                this.origFieldname = '';
                this.lang = '';
                this.groupId = '';

                this.init = function () {
                    var clsBits = this.cls.substring(
                        TranslationField.cssPrefix.length, this.cls.length).split('-');
                    this.origFieldname = clsBits[0];
                    this.lang = clsBits[1];
                    this.id = $(this.el).attr('id');
                    this.groupId = this.buildGroupId();
                };

                this.buildGroupId = function () {
                    /**
                     * Returns a unique group identifier with respect to the admin's way
                     * of handling inline field name attributes. Essentially that's the
                     * translation field id without the language prefix.
                     *
                     * Examples ('id parameter': 'return value'):
                     *
                     *  'id_name_de':
                     *      'id_name'
                     *  'id_name_zh_tw':
                     *      'id_name'
                     *  'id_name_set-2-name_de':
                     *      'id_name_set-2-name'
                     *  'id_name_set-2-name_zh_tw':
                     *      'id_name_set-2-name'
                     *  'id_name_set-2-0-name_de':
                     *      'id_name_set-2-0-name'
                     *  'id_name_set-2-0-name_zh_tw':
                     *      'id_name_set-2-0-name'
                     *  'id_news-data2-content_type-object_id-0-name_de':
                     *      'id_news-data2-content_type-object_id-0-name'
                     *  'id_news-data2-content_type-object_id-0-name_zh_cn':
                     *      id_news-data2-content_type-object_id-0-name'
                     *  'id_news-data2-content_type-object_id-0-1-name_de':
                     *      'id_news-data2-content_type-object_id-0-1-name'
                     *  'id_news-data2-content_type-object_id-0-1-name_zh_cn':
                     *      id_news-data2-content_type-object_id-0-1-name'
                     */
                    // TODO: We should be able to simplify this, the modeltranslation specific
                    // field classes are already build to be easily splitable, so we could use them
                    // to slice off the language code.
                    var idBits = this.id.split('-'),
                        idPrefix = 'id_' + this.origFieldname;
                    if (idBits.length === 3) {
                        // Handle standard inlines
                        idPrefix = idBits[0] + '-' + idBits[1] + '-' + idPrefix;
                    } else if (idBits.length === 4) {
                        // Handle standard inlines with model used by inline more than once
                        idPrefix = idBits[0] + '-' + idBits[1] + '-' + idBits[2] + '-' + idPrefix;
                    } else if (idBits.length === 6) {
                        // Handle generic inlines
                        idPrefix = idBits[0] + '-' + idBits[1] + '-' + idBits[2] + '-' +
                            idBits[3] + '-' + idBits[4] + '-' + this.origFieldname;
                    } else if (idBits.length === 7) {
                        // Handle generic inlines with model used by inline more than once
                        idPrefix = idBits[0] + '-' + idBits[1] + '-' + idBits[2] + '-' +
                            idBits[3] + '-' + idBits[4] + '-' + idBits[5] + '-' + this.origFieldname;
                    }
                    return idPrefix;
                };

                this.init();
            };
            TranslationField.cssPrefix = 'mt-field-';

            var TranslationFieldGrouper = function (options) {
                this.$fields = options.$fields;
                this.groupedTranslations = {};

                this.init = function () {
                    // Handle fields inside collapsed groups as added by zinnia
                    this.$fields = this.$fields.add('fieldset.collapsed .mt');

                    this.groupedTranslations = this.getGroupedTranslations();
                };

                this.getGroupedTranslations = function () {
                    /**
                     * Returns a grouped set of all model translation fields.
                     * The returned datastructure will look something like this:
                     *
                     * {
                     *     'id_name_de': {
                     *         'en': HTMLInputElement,
                     *         'de': HTMLInputElement,
                     *         'zh_tw': HTMLInputElement
                     *     },
                     *     'id_name_set-2-name': {
                     *         'en': HTMLTextAreaElement,
                     *         'de': HTMLTextAreaElement,
                     *         'zh_tw': HTMLTextAreaElement
                     *     },
                     *     'id_news-data2-content_type-object_id-0-name': {
                     *         'en': HTMLTextAreaElement,
                     *         'de': HTMLTextAreaElement,
                     *         'zh_tw': HTMLTextAreaElement
                     *     }
                     * }
                     *
                     * The keys are unique group identifiers as returned by
                     * TranslationField.buildGroupId() to handle inlines properly.
                     */
                    var self = this,
                        cssPrefix = TranslationField.cssPrefix;
                    this.$fields.each(function (idx, el) {
                        $.each($(el).attr('class').split(' '), function(idx, cls) {
                            if (cls.substring(0, cssPrefix.length) === cssPrefix) {
                                var tfield = new TranslationField({el: el, cls: cls});
                                if (!self.groupedTranslations[tfield.groupId]) {
                                    self.groupedTranslations[tfield.groupId] = {};
                                }
                                self.groupedTranslations[tfield.groupId][tfield.lang] = el;
                            }
                        });
                    });
                    return this.groupedTranslations;
                };

                this.init();
            };

            function createTabs(groupedTranslations) {
                var tabs = [];
                $.each(groupedTranslations, function (groupId, lang) {
                    var tabsContainer = $('<div class="translation-tabs"></div>'),
                        tabsList = $('<ul class="tabs-handler"></ul>'),
                        insertionPoint;
                    tabsContainer.append(tabsList);
                    $.each(lang, function (lang, el) {
                        var container = $(el).closest('.form-row'),
                            label = $('label', container),
                            fieldLabel = container.find('label'),
                            tabId = 'tab_' + $(el).attr('id'),
                            panel,
                            tab;
                        // Remove language and brackets from field label, they are
                        // displayed in the tab already.
                        if (fieldLabel.html()) {
                            fieldLabel.html(fieldLabel.html().replace(/ \[.+\]/, ''));
                        }
                        if (!insertionPoint) {
                            insertionPoint = {
                                'insert': container.prev().length ? 'after' :
                                    container.next().length ? 'prepend' : 'append',
                                'el': container.prev().length ? container.prev() : container.parent()
                            };
                        }
                        container.find('script').remove();
                        panel = $('<div class="tabs-content" id="' + tabId + '"></div>').append(container);
                        tab = $('<li' + (label.hasClass('required') ? ' class="required"' : '') +
                                '><a href="#' + tabId + '">' + lang.replace('_', '-') + '</a></li>');
                        tabsList.append(tab);
                        tabsContainer.append(panel);
                    });
                    insertionPoint.el[insertionPoint.insert](tabsContainer);

                    /// CREATE TABS
                    tabsContainer.find(".tabs-content").hide();
                    tabsContainer.find(".tabs-handler li a").click(function(){
                        tabsContainer.find(".tabs-handler li").removeClass("active");
                        $(this).parent().addClass("active");
                        tabsContainer.find(".tabs-content").hide();
                        tabsContainer.find($(this).attr("href")).show();
                        return false;
                    });
                    tabsContainer.find(".tabs-handler li a").eq(0).click();

                    tabs.push(tabsContainer);
                });
                return tabs;
            }

            var MainSwitch = {
                languages: [],
                $select: $('<select>'),

                init: function(groupedTranslations, tabs) {
                    if(tabs.length==0){ return false; }
                    var self = this;
                    $.each(groupedTranslations, function (id, languages) {
                        $.each(languages, function (lang) {
                            if ($.inArray(lang, self.languages) < 0) {
                                self.languages.push(lang);
                            }
                        });
                    });
                    $.each(this.languages, function (idx, language) {
                        self.$select.append($('<option value="' + idx + '">' +
                                            language.replace('_', '-') + '</option>'));
                    });
                    this.update(tabs);
                    $('#content').find('h1').append('&nbsp;').append(self.$select);
                },

                update: function(tabs) {
                    var self = this;
                    this.$select.change(function () {
                        $.each(tabs, function (idx, tab) {
                            tab.find(".tabs-handler li a").eq(parseInt(self.$select.val(), 10)).click();
                        });
                    });
                },

                activateTab: function(tabs) {
                    var self = this;
                    $.each(tabs, function (idx, tab) {
                        try { //jquery ui => 1.10 api changed, we keep backward compatibility
                            tab.tabs('select', parseInt(self.$select.val(), 10));
                        } catch(e) {
                            tab.tabs('option', 'active', parseInt(self.$select.val(), 10));
                        }
                    });
                }
            };

            if ($('body').hasClass('change-form')) {
                var grouper = new TranslationFieldGrouper({
                    $fields: $('.mt').filter(':input').filter(':parents(.tabular)')
                });

                MainSwitch.init(grouper.groupedTranslations, createTabs(grouper.groupedTranslations));

                $('body').ajaxComplete(function() {
                    var ajax_grouper = new TranslationFieldGrouper({
                        $fields: $('#composer_form_cover .mt').filter(':input').filter(':parents(.tabular)')
                    });
                    createTabs(ajax_grouper.groupedTranslations);
                });
            }

        });
    }(django.jQuery));
    }