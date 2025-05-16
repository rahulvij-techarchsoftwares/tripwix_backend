import json
import operator
from collections import OrderedDict
from datetime import datetime, timedelta
from functools import reduce
from itertools import groupby

import six
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib import admin
from django.contrib.admin import helpers
from django.contrib.admin.utils import unquote
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models, transaction
from django.db.models import Count, F, Func, IntegerField, Q, TextField, Value
from django.db.models.functions import Cast, Coalesce
from django.forms import ImageField, Textarea
from django.forms.formsets import all_valid
from django.http import Http404, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404
from django.template.defaultfilters import linebreaksbr
from django.template.response import TemplateResponse
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.encoding import force_str
from django.utils.html import escape, escapejs, format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_protect
from django_admin_kubi.widgets import TinyMceEditorWidget

from apps.core.utils import generate_calendar, get_month_start_end
from apps.hostify.models import PropertyCalendar
from apps.media.models import MediaPhoto
from apps.media.widgets import ImageWidget

from .admin_filters import (
    CommunityConfigFilter,
    DateRangeFilter,
    LocationConfigFilter,
    MaxGuestsConfigFilter,
    PropertyBedroomsConfigFilter,
    PropertyTypeConfigFilter,
    TypologyConfigFilter,
)
from .forms import (
    PropertyAmenitiesForm,
    PropertyChangeForm,
    PropertyDetailsForm,
    PropertyGroupForm,
    PropertyLocationForm,
    PropertyMediaForm,
    PropertyRelatedForm,
    RateForm,
)
from .managers import PropertyQuerysetManager
from .models import (
    Ambassador,
    Amenity,
    AmenityCategory,
    Detail,
    DetailCategory,
    DetailCategorySection,
    DetailOption,
    Property,
    PropertyBedroomsConfig,
    PropertyBedroomsConfigBedType,
    PropertyCategory,
    PropertyDetailValues,
    PropertyDivision,
    PropertyDivisionExtra,
    PropertyDivisionType,
    PropertyGroup,
    PropertyGroupDetails,
    PropertyManager,
    PropertyMediaPhoto,
    PropertyOwnership,
    PropertyRatingScore,
    PropertyTax,
    PropertyType,
    PropertyTypology,
    Rate,
)
from .tasks import fetch_images_from_google_drive
from .utils import get_publication_status, get_sync_status
from .widgets import SimpleSelectizeMultipleWidget, SlugWidget

csrf_protect_m = method_decorator(csrf_protect)


class RelationAdmin(admin.ModelAdmin):
    add_form_template = "admin/relation_base_form.html"
    change_form_template = "admin/relation_base_form.html"

    nav_bar = ()

    def get_nav_bar(self, request, obj=None):
        return self.nav_bar

    def render_change_form(
        self,
        request,
        context,
        add=False,
        change=False,
        form_url="",
        obj=None,
        template=None,
    ):
        context.update(
            {
                "nav_bar": self.get_nav_bar(request, obj=obj),
                "opts_nav": self.model._meta,
            }
        )
        render_response = super(RelationAdmin, self).render_change_form(request, context, add, change, form_url, obj)
        if template:
            render_response.template_name = template
        return render_response

    # Clean response
    def clean_response(self, request, obj):
        """
        Determines the HttpResponse for this stage.
        """
        opts = obj._meta

        verbose_name = opts.verbose_name

        if obj._deferred:
            opts_ = opts.proxy_for_model._meta
            verbose_name = opts_.verbose_name

        msg = 'The %(name)s "%(obj)s" was changed successfully.' % {
            "name": force_str(verbose_name),
            "obj": force_str(obj),
        }

        self.message_user(request, "%s  %s" % (msg, "You may edit it again below."))
        return HttpResponseRedirect(request.path)

    def render_clean_form(
        self,
        request,
        context,
        add=False,
        change=False,
        form_url="",
        obj=None,
        template="admin/relation_base_form.html",
    ):
        opts = self.model._meta
        context.update(
            {
                "add": add,
                "change": change,
                "has_add_permission": self.has_add_permission(request),
                "has_change_permission": self.has_change_permission(request, obj),
                "has_delete_permission": False,
                "has_file_field": True,  # FIXME - this should check if form or formsets have a FileField,
                "has_absolute_url": hasattr(self.model, "get_absolute_url"),
                "form_url": mark_safe(form_url),
                "opts": opts,
                "content_type_id": ContentType.objects.get_for_model(self.model).id,
                "save_as": self.save_as,
                "save_on_top": self.save_on_top,
                "nav_bar": self.get_nav_bar(request, obj=obj),
                "opts_nav": self.model._meta,
            }
        )

        return TemplateResponse(request, template, context, current_app=self.admin_site.name)


class PropertyDivisionInline(admin.TabularInline):
    model = PropertyDivision
    extra = 1
    readonly_fields = ("name",)
    template = "admin/edit_inline/division_tabular.html"
    formfield_overrides = {
        models.CharField: {"widget": Textarea(attrs={'cols': 40, 'rows': 4})},
        models.ManyToManyField: {"widget": SimpleSelectizeMultipleWidget},
    }

    fieldsets = (
        (
            None,
            {
                "fields": ("division_type", "name", "description", "extra"),
                "description": "",
            },
        ),
    )

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        form_field = super().formfield_for_manytomany(db_field, request, **kwargs)
        form_field.help_text = ""
        return form_field

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.select_related("division_type").order_by("division_type__name").distinct()
        return queryset


class PropertyBedroomsConfigInline(admin.TabularInline):
    model = PropertyBedroomsConfig
    extra = 1

    fieldsets = (
        (
            None,
            {
                "fields": ("division", "number", "bed_type"),
                "description": "",
            },
        ),
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = (
            PropertyBedroomsConfig.objects.prefetch_related(
                'division',
            )
            .annotate(
                division_name=Func(
                    F('division__name'),
                    Value(r'^(\w+).*$'),
                    Value(r'\1'),
                    Value('g'),
                    function='REGEXP_REPLACE',
                    output_field=TextField(),
                ),
                division_number=Coalesce(
                    Cast(
                        Func(
                            F('division__name'),
                            Value(r'.*?(\d+)$'),
                            Value(r'\1'),
                            Value('g'),
                            function='REGEXP_REPLACE',
                            output_field=TextField(),
                        ),
                        IntegerField(),
                    ),
                    Value(0),
                ),
            )
            .order_by('division_name', 'division_number')
            .distinct()
        )
        return queryset

    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
        if db_field.name == 'division':
            path = request.path
            path_parts = path.split('/')
            try:
                property_object_id = path_parts[-3]
            except IndexError:
                property_object_id = None

            if property_object_id:
                kwargs['queryset'] = (
                    PropertyDivision.objects.filter(property_object_id=property_object_id)
                    .annotate(
                        division_name=Func(
                            F('name'),
                            Value(r'^(\w+).*$'),
                            Value(r'\1'),
                            Value('g'),
                            function='REGEXP_REPLACE',
                            output_field=TextField(),
                        ),
                        division_number=Coalesce(
                            Cast(
                                Func(
                                    F('name'),
                                    Value(r'.*?(\d+)$'),
                                    Value(r'\1'),
                                    Value('g'),
                                    function='REGEXP_REPLACE',
                                    output_field=TextField(),
                                ),
                                IntegerField(),
                            ),
                            Value(0),
                        ),
                    )
                    .order_by('division_name', 'division_number')
                    .distinct()
                )

            else:
                kwargs['queryset'] = PropertyDivision.objects.none()

        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class PropertyReviewInline(admin.TabularInline):
    model = PropertyRatingScore
    extra = 1


class RateInline(admin.TabularInline):
    model = Rate
    form = RateForm
    extra = 1


class PropertyCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "slug")
    ordering = ("name",)


class PropertyAdmin(RelationAdmin):
    autocomplete_fields = ['ambassador']
    form = PropertyChangeForm
    formfield_overrides = {
        models.TextField: {"widget": TinyMceEditorWidget(attrs={"rows": 4, "cols": 40})},
    }

    get_publication_status.admin_order_field = "is_active"
    get_sync_status.short_description = _("Sync Status")
    get_sync_status.admin_order_field = "sync_status"

    fieldsets = (
        (
            None,
            {
                "fields": (
                    ("name", "reference"),
                    "title",
                    "content",
                    "default_price",
                    "tax_id",
                    "is_featured",
                    "item_o",
                ),
            },
        ),
        (
            "Type of Property",
            {
                "fields": (
                    "property_type",
                    "typology",
                    "property_category",
                ),
                "description": "Define what typology this property fits in to.",
            },
        ),
        (
            "Search Engine",
            {
                "classes": ("collapse",),
                "fields": (
                    "slug",
                    "seo_title",
                    "seo_description",
                ),
                "description": "Set up the property title, meta description and handle. These help define how this object shows up on search engines.",
            },
        ),
        (
            "Commissions",
            {
                "fields": (
                    (
                        "ownership",
                        "manager",
                    ),
                    ("commission", "commission_type"),
                ),
                "description": "You can set you commission rates for this property.",
            },
        ),
        (
            "Notes",
            {
                "fields": ("note",),
                "description": "Important information about this property.",
            },
        ),
        (
            _("Hostify Synchronization"),
            {
                "fields": (
                    "hostify_id",
                    "ready_to_sync",
                ),
                "description": "Control how this property is synchronized with Hostify.",
            },
        ),
        (
            "Publication Approval",
            {
                "fields": (("is_active", "publication_date", "publication_end_date"),),
                "description": "Control how this property can be seen on your frontend.",
            },
        ),
    )

    list_filter = (
        LocationConfigFilter,
        CommunityConfigFilter,
        PropertyTypeConfigFilter,
        TypologyConfigFilter,
        PropertyBedroomsConfigFilter,
        MaxGuestsConfigFilter,
        ('hostify_calendars__date', DateRangeFilter),
        "is_active",
    )

    list_select_related = ("property_type", "location")

    list_display = (
        "get_thumbnail",
        "reference",
        "title",
        "property_type",
        "location",
        get_publication_status,
        get_sync_status,
        "item_o",
    )
    list_editable = ("item_o",)

    list_display_links = ("get_thumbnail", "reference")
    list_per_page = 15
    readonly_fields = ("slug", "get_sales_content")
    search_fields = ("name", "title", "reference", "address", "hostify_id")
    actions = ["action_fetch_photos"]
    objects = PropertyQuerysetManager()
    change_form_template = "admin/property_change_form.html"

    inlines = []
    # Others
    list_display_last = ()

    # Defaults
    testimonial_installed = False
    _property_group = None

    class Media:
        js = (
            'tinymce/tinymce.min.js',
            'admin/js/tinymce.init.js',
        )

    def get_sales_content(self, obj):
        from django_admin_kubi.widgets import TinyMceEditorWidget

        return TinyMceEditorWidget().render('content', obj.content)

    get_sales_content.short_description = 'Formatted Content Preview'
    get_sales_content.allow_tags = True

    @admin.display(description="Thumbnail")
    def get_thumbnail(self, obj):
        try:
            thumbnail_url = obj.get_thumbnail_url()
        except AttributeError:
            thumbnail_url = None
        if thumbnail_url:
            return format_html('<img src="%s">' % thumbnail_url)
        thumb_static = static("admin/images/no_thumb.png")
        return format_html('<img src="{thumb_static}" width="60">', thumb_static=thumb_static)

    @admin.action(description="Fetch photos")
    def action_fetch_photos(self, request, queryset):
        property_ids = list(queryset.values_list("id", flat=True))
        for property_id in property_ids:
            fetch_images_from_google_drive.delay(property_id)
        self.message_user(request, "Fetching photos from google drive")

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super(PropertyAdmin, self).get_readonly_fields(request, obj=obj)
        if obj:
            if not request.user.has_perms(['properties.can_publish_property']):
                readonly_fields += ("is_active", "publication_date", "publication_end_date")
            if not request.user.is_superuser:
                readonly_fields += ("hostify_id",)
        return readonly_fields

    def get_fieldsets(self, request, obj=None):
        fieldsets = super(PropertyAdmin, self).get_fieldsets(request, obj=obj)
        if not obj:
            return self.fieldsets

        disables = getattr(settings, "PROPERTIES_ADMIN_DEFAULT_FIELDSETS", [])

        count = 0
        for fieldset in fieldsets:
            if count == 0:
                if request.user and not request.user.has_perms(["properties.change_property"]):
                    fieldset[1]["fields"] = (
                        ('name', 'reference'),
                        'title',
                        'get_sales_content',
                        'default_price',
                        'tax_id',
                        'is_featured',
                        'item_o',
                    )
                else:
                    fieldset[1]["fields"] = (
                        ('name', 'reference'),
                        'title',
                        'content',
                        'default_price',
                        'tax_id',
                        'is_featured',
                        'item_o',
                    )
            count += 1
            fieldset_name = fieldset[0]
            if not fieldset_name:
                fieldset_name = "Configuration"
            fieldset_name = str(fieldset_name)

            if fieldset_name in disables:
                for key, value in disables[fieldset_name].iteritems():
                    count = 0
                    for item in fieldsets:
                        if item[0] == key:
                            fieldsets.pop(count)
                            break
                        count += 1

        return fieldsets

    def get_list_filter(self, request):
        """
        Returns a sequence containing the fields to be displayed as filters in
        the right sidebar of the changelist page.
        """
        return self.list_filter

    def get_search_fields(self, request):
        """
        Returns a sequence containing the fields to be searched whenever
        somebody submits a search query.
        """
        return self.search_fields

    def get_queryset(self, request):
        qs = super(PropertyAdmin, self).get_queryset(request)

        qs = qs.select_related("property_category", "property_type", "location", "property_group", "typology")

        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs

    def get_list_display(self, request):
        list_display = self.list_display
        return list_display

    def changeform_view(self, request, object_id=None, form_url=None, extra_context=None):
        extra_context = extra_context or {}
        extra_context['has_sync_permission'] = request.user.is_superuser or request.user.has_perms(
            ['properties.can_sync_property']
        )
        extra_context["frontend_url"] = settings.FRONTOFFICE_URL
        return super().changeform_view(request, object_id, form_url, extra_context)

    def has_relation_permission(self, user, model, action):
        content_type = ContentType.objects.get_for_model(model)
        return user.has_perms([f'{content_type.app_label}.{action}_{content_type.model}'])

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser or request.user.has_perms(['properties.delete_property']):
            return True
        return False

    def get_current_property_group(self, request):
        if self._property_group:
            return self._property_group

        try:
            self._property_group = PropertyGroup.objects.get(sale_type="r")
        except Exception:
            raise Exception("Create a Propertygroup Rental")

        return self._property_group

    # METHODS
    def get_urls(self):
        from django.urls import re_path

        info = self.model._meta.app_label, self.model._meta.model_name

        my_urls = [
            re_path(
                r"^(\d+)/sync/$",
                self.admin_site.admin_view(self.property_sync_view),
                name="%s_%s_sync" % info,
            ),
            re_path(
                r"^(\d+)/media/$",
                self.admin_site.admin_view(self.property_media_view),
                name="%s_%s_media" % info,
            ),
            re_path(
                r"^(\d+)/location/$",
                self.admin_site.admin_view(self.property_location_view),
                name="%s_%s_location" % info,
            ),
            re_path(
                r"^(\d+)/construction/$",
                self.admin_site.admin_view(self.property_construction_view),
                name="%s_%s_construction" % info,
            ),
            re_path(
                r"^(\d+)/bedrooms/$",
                self.admin_site.admin_view(self.property_bedrooms_view),
                name="%s_%s_bedrooms" % info,
            ),
            re_path(
                r"^(\d+)/related/$",
                self.admin_site.admin_view(self.property_related_view),
                name="%s_%s_related" % info,
            ),
            re_path(
                r"^(\d+)/review/$",
                self.admin_site.admin_view(self.property_review_rating),
                name="%s_%s_review" % info,
            ),
            re_path(
                r"^(\d+)/d/([-_\w]+)/$",
                self.admin_site.admin_view(self.property_detail_view),
                name="%s_%s_detail" % info,
            ),
            re_path(
                r"^(\d+)/rates/$",
                self.admin_site.admin_view(self.property_rates_view),
                name="%s_%s_rates" % info,
            ),
            # AJAX for related properties
            re_path(
                r"^properties-ajax/$",
                self.admin_site.admin_view(self.properties_ajax_view),
                name="%s_%s_propertiesajax" % info,
            ),
            re_path(
                r"^(\d+)/hostify-calendar/$",
                self.admin_site.admin_view(self.property_hostify_calendar_view),
                name="%s_%s_hostify-calendar" % info,
            ),
            re_path(
                r"^(\d+)/amenities/$",
                self.admin_site.admin_view(self.property_amenities_view),
                name="%s_%s_amenities" % info,
            ),
        ]

        other_urls = list()

        return other_urls + my_urls + super(PropertyAdmin, self).get_urls()

    def get_nav_bar(self, request, obj=None, **kwargs):
        # DEFAULTs NAV
        default_nav = [
            {"reverse": "amenities", "label": "Amenities", "icon": "fa-tags"},
            {"reverse": "media", "label": "Media", "icon": "fa-camera"},
            {"reverse": "location", "label": "Location", "icon": "fa-map-marker"},
            {"reverse": "construction", "label": "Construction", "icon": "fa-home"},
            {"reverse": "bedrooms", "label": "Bedrooms", "icon": "fa-bed"},
            {"reverse": "related", "label": "Related", "icon": "fa-cubes"},
            {"reverse": "review", "label": "Review", "icon": "fa-star"},
            {"reverse": "rates", "label": "Rates", "icon": "fa-dollar-sign"},
            {"reverse": "hostify-calendar", "label": "Hostify Calendar", "icon": "fa-calendar"},
        ]

        if "default_nav" in kwargs:
            default_nav.extend(kwargs["default_nav"])

        # ! DEFAULTs NAV

        output_nav = []

        object_id = None
        if obj:
            property_group = obj.property_group
            object_id = obj.pk
        else:
            property_group = self.get_current_property_group(request)

        info = self.model._meta.app_label, self.model._meta.model_name
        url_name = "admin:%s_%s_detail" % info

        # All categories
        all_categories = DetailCategory.objects.exclude(slug="media").values("icon", "slug", "name").order_by("item_o")

        # Avaiable categories
        categories = (
            property_group.details_queryset()
            .values(
                "section__category",
                "section__category__icon",
                "section__category__slug",
                "section__category__name",
            )
            .annotate(total=Count("section__category"))
            .order_by("section__category__item_o")
        )

        for category in all_categories:
            for cat in categories:
                if cat["section__category__slug"] == category["slug"]:
                    slug = cat["section__category__slug"]
                    label = cat["section__category__name"]
                    icon = cat["section__category__icon"]
                    if object_id:
                        output_nav.append(
                            {
                                "url": reverse(url_name, args=(object_id, slug)),
                                "label": label,
                                "icon": icon,
                            }
                        )
                    else:
                        output_nav.append({"url": "#", "label": label, "icon": icon, "disabled": True})
                    break

        # Check for default nav bar items
        counter = 0
        for def_nav in default_nav:
            in_outnav = False

            for out_nav in output_nav:
                # Check for Defaults REVERSE
                if "reverse" in def_nav and "reverse" in out_nav and out_nav["reverse"] == def_nav["reverse"]:
                    in_outnav = True

                # Check for Defaults RELATION
                elif "relation" in def_nav and "relation" in out_nav and out_nav["relation"] == def_nav["relation"]:
                    in_outnav = True

                if in_outnav:
                    # Check if as Icon - If not apply the default icon
                    if "icon" in out_nav and "icon" in def_nav:
                        if not out_nav["icon"] or out_nav["icon"] == "":
                            out_nav["icon"] = def_nav["icon"]
                    break

            if not in_outnav:
                output_nav.insert(counter, def_nav)

            counter += 1

        return output_nav

    def save_model(self, request, obj, form, change):
        if not change:
            obj.property_group = self.get_current_property_group(request)
        super().save_model(request, obj, form, change)

    def get_detail_fieldsets(self, obj, category):
        fields = (
            obj.property_group.details_queryset()
            .filter(section__category=category)
            .values(
                "section",
                "section__name",
                "section__description",
                "detail__detail_type",
                "detail__slug",
                "sort_order",
            )
            .order_by("section", "sort_order", "detail__sort_order")
        )

        for key, group in groupby(fields, lambda x: x["section"]):
            section_name = ""
            section_description = ""
            # field_group = SortedDict()
            field_group = OrderedDict()
            for fields in group:
                section_name = fields["section__name"]
                section_description = fields["section__description"]
                if section_description:
                    section_description = linebreaksbr(section_description)

                field_name = "detail_%s" % fields["detail__slug"].replace("-", "_")

                if fields["sort_order"] not in field_group:
                    field_group[fields["sort_order"]] = list()
                field_group[fields["sort_order"]].append(field_name)

            fset = (
                section_name,
                {
                    "fields": [fields for key, fields in six.iteritems(field_group)],
                    "description": section_description,
                },
            )

            yield fset

    def get_relation_view_permission(self, request, model):
        return self.has_relation_permission(request.user, model, "view")

    def get_relation_change_permission(self, request, model):
        return self.has_relation_permission(request.user, model, "change")

    @csrf_protect_m
    def property_sync_view(self, request, property_id, form_url="", extra_context=None):
        model = self.model
        opts = model._meta
        obj = self.get_object(request, unquote(str(property_id)))

        if not (
            request.user.is_superuser
            or (self.has_change_permission(request, obj) and request.user.has_perms(['properties.can_sync_property)']))
        ):
            raise PermissionDenied

        if obj is None:
            raise Http404(
                "%(name)s object with primary key %(key)r does not exist."
                % {"name": force_str(opts.verbose_name), "key": escape(property_id)}
            )

        if not obj.ready_to_sync:
            return JsonResponse({"success": False, "message": "Property is not ready to sync"}, status=400)
        obj.sync_changes_with_hostify()
        return JsonResponse({"success": True})

    @csrf_protect_m
    @transaction.atomic
    def property_rates_view(self, request, property_id, form_url="", extra_context=None):
        model = Rate
        opts = model._meta
        obj = self.get_object(request, unquote(str(property_id)))

        if obj is None:
            raise Http404(
                "%(name)s object with primary key %(key)r does not exist."
                % {"name": force_str(opts.verbose_name), "key": escape(property_id)}
            )

        if not self.get_relation_view_permission(request, model):
            raise PermissionDenied

        can_change = self.get_relation_change_permission(request, model)

        if request.method == "POST" and can_change:
            if request.headers.get('X-HTTP-Method-Override') == 'PUT':
                rate_id = request.POST.get("id")
                rate = get_object_or_404(Rate, pk=rate_id)
                form = RateForm(request.POST, instance=rate)
                if form.is_valid():
                    rate.property.save()
                    updated_rate = form.save()
                    return JsonResponse(
                        {
                            "id": updated_rate.id,
                            "from_date": updated_rate.from_date,
                            "to_date": updated_rate.to_date,
                            "season": updated_rate.season,
                            "minimum_nights": updated_rate.minimum_nights,
                            "website_sales_value": updated_rate.website_sales_value,
                            "success": True,
                        }
                    )
                else:
                    return JsonResponse({"success": False, "errors": form.errors}, status=400)
            elif request.headers.get('X-HTTP-Method-Override') == 'DELETE':
                if not self.has_delete_permission(request, obj):
                    raise PermissionDenied

                rate_id = request.POST.get("id")
                rate = get_object_or_404(Rate, pk=rate_id)
                property = rate.property
                rate.delete()
                property.save()
                return JsonResponse({"success": True})
            else:
                form = RateForm(request.POST, property=obj)
                if form.is_valid():
                    new_rate = form.save(commit=False)
                    new_rate.property = obj
                    new_rate.save()
                    new_rate.property.save()
                    return JsonResponse(
                        {
                            "id": new_rate.id,
                            "from_date": new_rate.from_date,
                            "to_date": new_rate.to_date,
                            "season": new_rate.season,
                            "minimum_nights": new_rate.minimum_nights,
                            "website_sales_value": new_rate.website_sales_value,
                            "success": True,
                        }
                    )
                else:
                    return JsonResponse({"success": False, "errors": form.errors}, status=400)

        else:
            form = RateForm(property=obj)
        readonly_fields = []
        if not can_change:
            for field_name, field in form.fields.items():
                field.disabled = True
                field.widget.attrs['readonly'] = True
                readonly_fields.append(field_name)

        rates = Rate.objects.filter(property=obj).order_by('-from_date', '-id')

        from_date = request.GET.get('from_date')
        to_date = request.GET.get('to_date')
        season = request.GET.get('season')

        if from_date:
            rates = rates.filter(to_date__gte=from_date)
        if to_date:
            rates = rates.filter(from_date__lte=to_date)
        if season:
            rates = rates.filter(season=season)

        paginator = Paginator(rates, 10)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        today = timezone.now().date()
        use_today = False
        rates_data = list(rates.values('id', 'from_date', 'to_date', 'season', 'minimum_nights', 'website_sales_value'))
        rates_json = json.dumps(rates_data, cls=DjangoJSONEncoder)
        latest_selected_from_date = rates.order_by('-from_date').first()
        if not latest_selected_from_date or latest_selected_from_date.from_date < today:
            use_today = True
        latest_selected_to_date = rates.order_by('-to_date').first()
        adminForm = helpers.AdminForm(
            form, [(None, {'fields': form.base_fields})], {}, readonly_fields, model_admin=self
        )
        media = self.media + adminForm.media

        context = {
            "title": "Rates",
            "adminform": adminForm,
            "object": obj,
            "opts": Property._meta,
            'can_change': can_change,
            "app_label": Property._meta.app_label,
            "media": media,
            "page_obj": page_obj,
            "paginator": paginator,
            "inline_admin_formsets": [],
            "original": obj,
            "is_popup": False,
            'latest_from_date': (
                f'{latest_selected_from_date.from_date:%Y-%m-%d}' if latest_selected_from_date else None
            ),
            'latest_to_date': f'{latest_selected_to_date.to_date:%Y-%m-%d}' if latest_selected_to_date else None,
            "season_choices": Rate._meta.get_field('season').choices,
            "rates_json": rates_json,
            "filters": {"from_date": from_date, "to_date": to_date, "season": season},
        }
        if use_today:
            context['latest_to_date'] = f'{today - timedelta(days=1):%Y-%m-%d}'
        context.update(extra_context or {})
        return self.render_change_form(
            request,
            context,
            change=can_change,
            obj=obj,
            form_url=form_url,
            template="admin/property_rates.html",
        )

    # DETAIL

    @csrf_protect_m
    @transaction.atomic
    def property_detail_view(self, request, object_id, slug, form_url="", extra_context=None):
        model = PropertyDetailValues
        opts = model._meta

        obj = self.get_object(request, unquote(object_id))

        if obj is None:
            raise Http404(
                "%(name)s object with primary key %(key)r does not exist."
                % {"name": force_str(opts.verbose_name), "key": escape(object_id)}
            )

        if not self.get_relation_view_permission(request, model):
            raise PermissionDenied

        can_change = self.get_relation_change_permission(request, model)

        try:
            category = DetailCategory.objects.get(slug=unquote(slug))
        except ObjectDoesNotExist:
            raise Http404(
                "%(name)s object with slug %(key)r does not exist." % {"name": "Category", "key": escape(slug)}
            )

        ModelForm = PropertyDetailsForm

        details_fieldset = []
        readonly_fields = []

        for fieldset in self.get_detail_fieldsets(obj, category):
            if category.slug == 'web':
                details_fieldset = [
                    (
                        None,
                        {
                            'fields': ('tagline', 'ambassador'),
                            'description': """
                            Set tagline and ambassador for this property.
                            </br>
                            </br>
                            <h3>Warning! Editing this field will also change the link to the live Web page on Tripwix.com.</h3>
                            """,
                        },
                    ),
                ]
            details_fieldset.append(fieldset)

        if len(details_fieldset) > 0:
            lst = list(details_fieldset[0])
            lst[0] = None
            details_fieldset[0] = tuple(lst)

        formsets = []
        if request.method == "POST" and can_change:
            form = ModelForm(
                data=request.POST,
                instance=obj,
                category=category,
                enable_change_vat_input=request.user.has_perms(['properties.can_change_vat_rate']),
            )
            if form.is_valid():
                new_object = self.save_form(request, form, change=can_change)
                self.save_model(request, new_object, form, True)
                self.save_related(request, form, formsets, True)
                change_message = self.construct_change_message(request, form, formsets)
                self.log_change(request, new_object, change_message)
                return self.response_change(request, new_object)

        else:
            form = ModelForm(
                instance=obj,
                category=category,
                enable_change_vat_input=request.user.has_perms(['properties.can_change_vat_rate']),
            )

        adminForm = helpers.AdminForm(form, details_fieldset, {}, readonly_fields, model_admin=self)
        media = self.media + adminForm.media

        context = {
            "title": category.name,
            "adminform": adminForm,
            "object_id": object_id,
            "can_change": can_change,
            "original": obj,
            "is_popup": False,
            "media": media,
            "inline_admin_formsets": [],
            "errors": helpers.AdminErrorList(form, formsets),
            "app_label": opts.app_label,
        }
        context.update(extra_context or {})
        return self.render_change_form(
            request,
            context,
            change=can_change,
            obj=obj,
            form_url=form_url,
            template=self.change_form_template,
        )

    # MEDIA
    @csrf_protect_m
    @transaction.atomic
    def property_media_view(self, request, object_id, form_url="", extra_context=None):
        model = PropertyMediaPhoto
        opts = model._meta

        obj = self.get_object(request, unquote(object_id))

        if obj is None:
            raise Http404(
                "%(name)s object with primary key %(key)r does not exist."
                % {"name": force_str(opts.verbose_name), "key": escape(object_id)}
            )

        if not self.get_relation_view_permission(request, model):
            raise PermissionDenied

        can_change = self.get_relation_change_permission(request, model)

        try:
            category = DetailCategory.objects.get(slug="media")
        except ObjectDoesNotExist:
            category = None

        ModelForm = PropertyMediaForm

        readonly_fields = []

        media_fieldset = [
            (
                "Photos",
                {
                    "fields": (
                        "photos",
                        "standard_photos_url",
                    ),
                    "description": "Upload images for this property.",
                },
            )
        ]

        if category:
            fieldsets = self.get_detail_fieldsets(obj, category)
            if not can_change:
                for fieldset in fieldsets:
                    for field_name in fieldset[1]['fields']:
                        if isinstance(field_name, tuple) or isinstance(field_name, list):
                            readonly_fields.extend(field_name)
                        else:
                            readonly_fields.append(field_name)

            for fieldset in fieldsets:
                media_fieldset.append(fieldset)

        formsets = []
        if request.method == "POST" and can_change:
            form = ModelForm(
                data=request.POST, files=request.FILES, instance=obj, category=category, disabled=not can_change
            )
            if form.is_valid():
                new_object = self.save_form(request, form, change=can_change)
                self.save_model(request, new_object, form, True)
                self.save_related(request, form, formsets, True)
                change_message = self.construct_change_message(request, form, formsets)
                self.log_change(request, new_object, change_message)
                return self.response_change(request, new_object)

        else:
            form = ModelForm(instance=obj, category=category, disabled=not can_change)

        adminForm = helpers.AdminForm(form, media_fieldset, {}, readonly_fields, model_admin=self)
        media = self.media + adminForm.media

        context = {
            "title": "Media",
            "adminform": adminForm,
            "readonly_image_widget": not can_change,
            "object_id": object_id,
            "original": obj,
            "can_change": can_change,
            "is_popup": False,
            "media": media,
            "inline_admin_formsets": [],
            "errors": helpers.AdminErrorList(form, formsets),
            "app_label": opts.app_label,
        }
        context.update(extra_context or {})
        return self.render_change_form(
            request,
            context,
            change=can_change,
            obj=obj,
            form_url=form_url,
            template=self.change_form_template,
        )

    @csrf_protect_m
    @transaction.atomic
    def property_bedrooms_view(self, request, object_id, form_url="", extra_context=None):
        model = PropertyBedroomsConfig
        opts = model._meta

        obj = self.get_object(request, unquote(object_id))

        if obj is None:
            raise Http404(
                "%(name)s object with primary key %(key)r does not exist."
                % {"name": force_str(opts.verbose_name), "key": escape(object_id)}
            )

        if not self.get_relation_view_permission(request, model):
            raise PermissionDenied

        can_change = self.get_relation_change_permission(request, model)

        ModelForm = self.get_form(request, obj)
        form = ModelForm(instance=obj)
        if request.method == "POST" and can_change:
            formsets, inline_instances = self._create_formsets(request, obj, change=can_change)
            if all_valid(formsets):
                for formset in formsets:
                    self.save_formset(request, form, formset, change=can_change)
                change_message = self.construct_change_message(request, form, formsets)
                self.log_change(request, obj, change_message)
                obj.save()
                return self.response_change(request, obj)

        else:
            formsets, inline_instances = self._create_formsets(request, obj, change=can_change)

        readonly_fields = []
        if not can_change:
            for field_name, field in form.fields.items():
                field.disabled = True
                field.widget.attrs['readonly'] = True
                readonly_fields.append(field_name)

        adminForm = helpers.AdminForm(form, [], {}, readonly_fields=readonly_fields, model_admin=self)
        media = self.media + adminForm.media

        inline_formsets = self.get_inline_formsets(request, formsets, inline_instances, obj)
        for inline_formset in inline_formsets:
            media = self.media + inline_formset.media

        context = {
            "title": "Bedrooms",
            "adminform": adminForm,
            "object_id": object_id,
            'can_change': can_change,
            "original": obj,
            "is_popup": False,
            "media": media,
            "inline_admin_formsets": inline_formsets,
            "errors": helpers.AdminErrorList(form, formsets),
            "app_label": opts.app_label,
        }
        context.update(extra_context or {})
        return self.render_change_form(
            request,
            context,
            change=can_change,
            obj=obj,
            form_url=form_url,
            template=self.change_form_template,
        )

    # LOCATION
    @csrf_protect_m
    @transaction.atomic
    def property_location_view(self, request, object_id, form_url="", extra_context=None):
        model = self.model
        opts = model._meta

        obj = self.get_object(request, unquote(object_id))

        if obj is None:
            raise Http404(
                "%(name)s object with primary key %(key)r does not exist."
                % {"name": force_str(opts.verbose_name), "key": escape(object_id)}
            )

        if not self.get_relation_view_permission(request, model):
            raise PermissionDenied

        can_change = self.get_relation_change_permission(request, model)

        ModelForm = PropertyLocationForm

        location_fields = (
            "location",
            "sublocation",
        )

        location_fieldset = [
            (
                _("Location Filters"),
                {
                    "fields": (('country', 'city'),),
                    "description": "Filter destinations by country and city.",
                    "classes": ("collapse", "collapsable"),
                },
            ),
            (
                None,
                {
                    "fields": (location_fields, "address"),
                    "description": "Define where this property is located.",
                },
            ),
            (
                _("GPS Location"),
                {
                    "fields": ("gps_coordinates_manual", "point"),
                    "description": _("Define the GPS coordinates for this property."),
                },
            ),
        ]

        formsets = []
        if request.method == "POST" and can_change:
            form = ModelForm(data=request.POST, instance=obj)
            if form.is_valid():
                new_object = self.save_form(request, form, change=can_change)
                self.save_model(request, new_object, form, True)
                self.save_related(request, form, formsets, True)
                change_message = self.construct_change_message(request, form, formsets)
                self.log_change(request, new_object, change_message)
                return self.response_change(request, new_object)

        else:
            form = ModelForm(instance=obj)

        readonly_fields = []

        adminForm = helpers.AdminForm(form, location_fieldset, {}, readonly_fields=readonly_fields, model_admin=self)
        media = self.media + adminForm.media

        context = {
            "title": "Location",
            "adminform": adminForm,
            'can_change': can_change,
            "object_id": object_id,
            "original": obj,
            "is_popup": False,
            "media": media,
            "inline_admin_formsets": [],
            "errors": helpers.AdminErrorList(form, formsets),
            "app_label": opts.app_label,
        }
        context.update(extra_context or {})
        return self.render_change_form(
            request,
            context,
            change=can_change,
            obj=obj,
            form_url=form_url,
            template=self.change_form_template,
        )

    #
    @csrf_protect_m
    @transaction.atomic
    def property_related_view(self, request, object_id, form_url="", extra_context=None, **kwargs):
        model = self.model
        opts = model._meta

        obj = self.get_object(request, unquote(object_id))

        if obj is None:
            raise Http404(
                "%(name)s object with primary key %(key)r does not exist."
                % {"name": force_str(opts.verbose_name), "key": escape(object_id)}
            )

        if not self.get_relation_view_permission(request, model):
            raise PermissionDenied

        can_change = self.get_relation_change_permission(request, model)

        ModelForm = PropertyRelatedForm
        if "form" in kwargs:
            ModelForm = kwargs["form"]

        related_fieldset = [
            (
                None,
                {
                    "classes": ("related",),
                    "fields": ("related",),
                    "description": "Related Properties",
                },
            ),
        ]
        if "fieldsets" in kwargs:
            related_fieldset = kwargs["fieldsets"]

        try:
            category = DetailCategory.objects.get(slug="related")
        except ObjectDoesNotExist:
            category = None

        formsets = []
        if request.method == "POST" and can_change:
            form = ModelForm(data=request.POST, instance=obj, category=category)
            if form.is_valid():
                new_object = self.save_form(request, form, change=can_change)
                self.save_model(request, new_object, form, True)
                self.save_related(request, form, formsets, True)
                change_message = self.construct_change_message(request, form, formsets)
                self.log_change(request, new_object, change_message)
                return self.response_change(request, new_object)
        else:
            form = ModelForm(instance=obj, category=category)

        readonly_fields = []
        if not can_change:
            for field_name, field in form.fields.items():
                field.disabled = True
                field.widget.attrs['readonly'] = True
                readonly_fields.append(field_name)

        adminForm = helpers.AdminForm(form, related_fieldset, {}, readonly_fields=readonly_fields, model_admin=self)
        media = self.media + adminForm.media

        context = {
            "title": "Related",
            "adminform": adminForm,
            "object_id": object_id,
            'can_change': can_change,
            "original": obj,
            "is_popup": False,
            "media": media,
            "inline_admin_formsets": [],
            "errors": helpers.AdminErrorList(form, formsets),
            "app_label": opts.app_label,
        }
        context.update(extra_context or {})
        return self.render_change_form(
            request,
            context,
            change=can_change,
            obj=obj,
            form_url=form_url,
            template=self.change_form_template,
        )

    # Amenities
    @csrf_protect_m
    @transaction.atomic
    def property_amenities_view(self, request, object_id, form_url="", extra_context=None, **kwargs):
        model = Amenity
        opts = model._meta

        obj = self.get_object(request, unquote(object_id))

        if obj is None:
            raise Http404(
                "%(name)s object with primary key %(key)r does not exist."
                % {"name": force_str(opts.verbose_name), "key": escape(object_id)}
            )

        if not self.get_relation_view_permission(request, model):
            raise PermissionDenied

        can_change = self.get_relation_change_permission(request, model)

        ModelForm = PropertyAmenitiesForm
        if "form" in kwargs:
            ModelForm = kwargs["form"]

        amenities_fieldset = [
            (
                None,
                {
                    "classes": ("amenities",),
                    "fields": ("amenities",),
                    "description": "Property Amenities",
                },
            ),
        ]

        formsets = []
        if request.method == "POST" and can_change:
            form = ModelForm(data=request.POST, instance=obj)
            if form.is_valid():
                new_object = self.save_form(request, form, change=can_change)
                self.save_model(request, new_object, form, True)
                self.save_related(request, form, formsets, True)
                change_message = self.construct_change_message(request, form, formsets)
                self.log_change(request, new_object, change_message)
                return self.response_change(request, new_object)
        else:
            form = ModelForm(instance=obj)

        readonly_fields = []
        if not can_change:
            for field_name, field in form.fields.items():
                field.disabled = True
                field.widget.attrs['readonly'] = True
                readonly_fields.append(field_name)
        adminForm = helpers.AdminForm(form, amenities_fieldset, {}, readonly_fields, model_admin=self)
        media = self.media + adminForm.media

        context = {
            "title": "Amenities",
            "adminform": adminForm,
            "object_id": object_id,
            "original": obj,
            'can_change': can_change,
            "is_popup": False,
            "media": media,
            "inline_admin_formsets": [],
            "errors": helpers.AdminErrorList(form, formsets),
            "app_label": opts.app_label,
        }
        context.update(extra_context or {})
        return self.render_change_form(
            request,
            context,
            change=can_change,
            obj=obj,
            form_url=form_url,
            template=self.change_form_template,
        )

    # Construction
    @csrf_protect_m
    @transaction.atomic
    def property_construction_view(self, request, object_id, form_url="", extra_context=None):
        model = PropertyDivision
        opts = model._meta
        obj = self.get_object(request, unquote(object_id))

        if obj is None:
            raise Http404(
                "%(name)s object with primary key %(key)r does not exist."
                % {"name": force_str(opts.verbose_name), "key": escape(object_id)}
            )

        if not self.get_relation_view_permission(request, model):
            raise PermissionDenied

        can_change = self.get_relation_change_permission(request, model)

        # PropertyDivisionInline
        ModelForm = PropertyDetailsForm
        construction_fieldset = []

        try:
            category = DetailCategory.objects.get(slug="construction")
        except ObjectDoesNotExist:
            category = None

        if category:
            for fieldset in self.get_detail_fieldsets(obj, category):
                construction_fieldset.append(fieldset)

            if len(construction_fieldset) > 0:
                lst = list(construction_fieldset[0])
                lst[0] = None
                construction_fieldset[0] = tuple(lst)

        if request.method == "POST" and can_change:
            form = ModelForm(data=request.POST, instance=obj, category=category)
            if form.is_valid():
                form_validated = True
                new_object = self.save_form(request, form, change=can_change)
            else:
                form_validated = False
                new_object = form.instance

            formsets, inline_instances = self._create_formsets(request, new_object, change=can_change)
            if all_valid(formsets) and form_validated:
                new_object = self.save_form(request, form, change=can_change)
                self.save_model(request, new_object, form, True)
                self.save_related(request, form, formsets, True)
                change_message = self.construct_change_message(request, form, formsets)
                obj.reorganize_divisions()
                self.log_change(request, new_object, change_message)
                return self.response_change(request, new_object)

        else:
            form = ModelForm(instance=obj, category=category)
            formsets, _ = self._create_formsets(request, obj, change=can_change)
            inline_instances = self.get_inline_instances(request, obj)

        readonly_fields = []
        if not can_change:
            for field_name, field in form.fields.items():
                field.disabled = True
                field.widget.attrs['readonly'] = True
                readonly_fields.append(field_name)

        adminForm = helpers.AdminForm(
            form, construction_fieldset, {}, readonly_fields=readonly_fields, model_admin=self
        )
        media = self.media + adminForm.media

        inline_formsets = self.get_inline_formsets(request, formsets, inline_instances, obj)
        for inline_formset in inline_formsets:
            media = media + inline_formset.media

        context = {
            "title": "Construction",
            "adminform": adminForm,
            "object_id": object_id,
            'can_change': can_change,
            "original": obj,
            "is_popup": False,
            "media": media,
            "inline_admin_formsets": inline_formsets,
            "errors": helpers.AdminErrorList(form, formsets),
            "app_label": opts.app_label,
        }
        context.update(extra_context or {})
        return self.render_change_form(
            request,
            context,
            change=can_change,
            obj=obj,
            form_url=form_url,
            template=self.change_form_template,
        )

    @csrf_protect_m
    @transaction.atomic
    def property_review_rating(self, request, object_id, form_url="", extra_context=None):
        model = PropertyRatingScore
        opts = model._meta

        obj = self.get_object(request, unquote(object_id))

        if obj is None:
            raise Http404(
                "%(name)s object with primary key %(key)r does not exist."
                % {"name": force_str(opts.verbose_name), "key": escape(object_id)}
            )

        if not self.get_relation_view_permission(request, model):
            raise PermissionDenied

        can_change = self.get_relation_change_permission(request, model)

        ModelForm = self.get_form(request, obj)
        form = ModelForm(instance=obj)
        if request.method == "POST" and can_change:
            formsets, inline_instances = self._create_formsets(request, obj, change=can_change)
            if all_valid(formsets):
                for formset in formsets:
                    self.save_formset(request, form, formset, change=can_change)
                change_message = self.construct_change_message(request, form, formsets)
                self.log_change(request, obj, change_message)
                obj.save()
                return self.response_change(request, obj)
        else:
            formsets, inline_instances = self._create_formsets(request, obj, change=can_change)

        readonly_fields = []
        if not can_change:
            for field_name, field in form.fields.items():
                field.disabled = True
                field.widget.attrs['readonly'] = True
                readonly_fields.append(field_name)

        adminForm = helpers.AdminForm(form, [], {}, readonly_fields=readonly_fields, model_admin=self)
        media = self.media + adminForm.media

        inline_formsets = self.get_inline_formsets(request, formsets, inline_instances, obj)
        for inline_formset in inline_formsets:
            media = self.media + inline_formset.media

        context = {
            "title": "Review",
            "adminform": adminForm,
            "object_id": object_id,
            'can_change': can_change,
            "original": obj,
            "is_popup": False,
            "media": media,
            "inline_admin_formsets": inline_formsets,
            "errors": helpers.AdminErrorList(form, formsets),
            "app_label": opts.app_label,
        }
        context.update(extra_context or {})
        return self.render_change_form(
            request,
            context,
            change=can_change,
            obj=obj,
            form_url=form_url,
            template=self.change_form_template,
        )

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context)
        return response

    def properties_ajax_view(self, request):
        if not request.is_ajax():
            raise Http404

        results = self.model.objects.filter()
        limit = request.GET.get("limit", 20)
        fetch = request.GET.get("fetch", None)
        term = request.GET.get("term", None)

        if term:
            term = term.lstrip()

        if fetch:
            # Fetch current Data
            fetch_list = unquote(fetch).split(",")
            fetch_list = filter(None, fetch_list)
            results = results.filter(pk__in=fetch_list).order_by("title")

        elif term:
            query_group = list()
            for nt in term.split():
                query_list = [
                    Q(name__icontains=nt),
                    Q(reference__icontains=nt),
                ]
                query_group.append(reduce(operator.or_, query_list))

            results = (
                results.select_related(
                    "property_group",
                    "property_type",
                    "property_category",
                    "typology",
                    "location",
                    "sublocation",
                )
                .filter(reduce(operator.and_, query_group))
                .distinct()
            )

            results = results[:limit]
        else:
            results = results.order_by("title")[:limit]

        output = list()

        for obj in results:
            output.append(
                {
                    "pk": obj.pk,
                    "id": obj.pk,
                    "name": "%s" % obj.name,
                    "title": "%s" % obj.title,
                    "location": "%s" % obj.location if obj.location else "",
                    "sublocation": "%s" % obj.sublocation if obj.sublocation else "",
                    "reference": "%s" % obj.reference,
                    "thumbnail": obj.get_thumbnail(),
                    "thumbnail_url": obj.thumbnail_url,
                }
            )

        return HttpResponse(json.dumps(output), content_type="application/json")

    def property_hostify_calendar_view(self, request, property_id, form_url="", extra_context=None):
        model = PropertyCalendar
        opts = model._meta
        obj = self.get_object(request, unquote(str(property_id)))

        if obj is None:
            raise Http404(
                "%(name)s object with primary key %(key)r does not exist."
                % {"name": force_str(opts.verbose_name), "key": escape(property_id)}
            )

        if not self.get_relation_view_permission(request, model):
            raise PermissionDenied

        current_month_start, current_month_end = get_month_start_end()
        can_change = self.get_relation_change_permission(request, model)

        from_date = datetime.strptime(
            request.GET.get('from_date', datetime.strftime(current_month_start, "%Y-%m-%d")) + " 00:00:00",
            "%Y-%m-%d %H:%M:%S",
        )
        to_date = from_date + relativedelta(months=1) - timedelta(days=1)

        calendars = PropertyCalendar.objects.filter(property=obj, date__range=(from_date, to_date)).order_by('date')
        ModelForm = PropertyDetailsForm
        form = ModelForm(instance=obj)

        readonly_fields = []
        if not can_change:
            for field_name, field in form.fields.items():
                field.disabled = True
                field.widget.attrs['readonly'] = True
                readonly_fields.append(field_name)

        adminForm = helpers.AdminForm(form, [], {}, readonly_fields=readonly_fields, model_admin=self)

        calendars_per_day = {calendar.date.day: calendar for calendar in calendars}

        context = {
            "title": "Hostify Calendar",
            "adminform": adminForm,
            "object": obj,
            "opts": Property._meta,
            'can_change': can_change,
            "app_label": Property._meta.app_label,
            "inline_admin_formsets": [],
            "original": obj,
            "is_popup": False,
            "calendars": calendars_per_day,
            "current_month": from_date.strftime("%B %Y"),
            "previous_month": (from_date - relativedelta(months=1)).strftime("%Y-%m-%d"),
            "next_month": (from_date + relativedelta(months=1)).strftime("%Y-%m-%d"),
            "filters": {"from_date": from_date, "to_date": to_date},
            "month_days": generate_calendar(from_date),
        }
        context.update(extra_context or {})
        return self.render_change_form(
            request,
            context,
            change=can_change,
            obj=obj,
            form_url=form_url,
            template="admin/property_calendar.html",
        )

    def get_inline_instances(self, request, obj=None):
        inline_instances = []
        inlines = []
        if request.path.endswith("/construction/"):
            inlines += [
                PropertyDivisionInline,
            ]
        elif request.path.endswith("/bedrooms/"):
            inlines += [
                PropertyBedroomsConfigInline,
            ]
        elif request.path.endswith("/review/"):
            inlines += [
                PropertyReviewInline,
            ]
        for inline_class in inlines:
            inline = inline_class(self.model, self.admin_site)
            inline_instances.append(inline)

        return super().get_inline_instances(request, obj=obj) + inline_instances

    def get_inline_formsets(self, request, formsets, inline_instances, obj=None):
        # Check edit permissions on parent model
        can_edit_parent = self.has_change_permission(request, obj) if obj else self.has_add_permission(request)

        inline_admin_formsets = []

        # Ensure formsets and inline_instances are properly paired
        if len(formsets) != len(inline_instances):
            return inline_admin_formsets

        for inline, formset in zip(inline_instances, formsets):
            fieldsets = list(inline.get_fieldsets(request, obj))
            readonly = list(inline.get_readonly_fields(request, obj))

            if can_edit_parent:
                has_add_permission = inline.has_add_permission(request, obj)
                has_change_permission = inline.has_change_permission(request, obj)
                has_delete_permission = inline.has_delete_permission(request, obj)
            else:
                # Disable all edit-permissions for read-only view
                has_add_permission = has_change_permission = has_delete_permission = False
                formset.extra = formset.max_num = 0

            has_view_permission = inline.has_view_permission(request, obj)
            prepopulated = dict(inline.get_prepopulated_fields(request, obj))

            inline_admin_formset = helpers.InlineAdminFormSet(
                inline,
                formset,
                fieldsets,
                prepopulated,
                readonly,
                model_admin=self,
                has_add_permission=has_add_permission,
                has_change_permission=has_change_permission,
                has_delete_permission=has_delete_permission,
                has_view_permission=has_view_permission,
            )

            inline_admin_formsets.append(inline_admin_formset)

        return inline_admin_formsets


class PropertyGroupDetailsInline(admin.TabularInline):
    model = PropertyGroupDetails
    extra = 1


class PropertyGroupAdmin(RelationAdmin):
    formfield_overrides = {
        models.SlugField: {"widget": SlugWidget},
    }

    list_display = (
        "name",
        "slug",
        "in_search",
    )
    list_display_links = ("name",)
    list_editable = ("in_search",)

    list_filter = [
        "in_search",
    ]
    search_fields = (
        "name",
        "slug",
    )

    add_form_template = "admin/property_group_change_form.html"
    change_form_template = "admin/property_group_change_form.html"

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "description",
                    "sale_type",
                ),
                "description": "Write a name and description that suits best this property group.",
            },
        ),
        (
            "Settings & Details",
            {
                "classes": ("settings",),
                "fields": (
                    "in_search",
                    "price_ranges",
                    (
                        "sort_order_be",
                        "sort_order_fe",
                    ),
                ),
                "description": 'You can set how property assigned to this "group" behave, and which details define them.',
            },
        ),
        (
            "Search Engine",
            {
                "classes": ("collapse",),
                "fields": (
                    "seo_title",
                    "seo_description",
                    "seo_keywords",
                    "slug",
                ),
                "description": "Set up the page title, meta description and handle. These help define how this object shows up on search engines.",
            },
        ),
    )

    prepopulated_fields = {"slug": ("name",)}
    inlines = []

    def __init__(self, model, admin_site):
        super(PropertyGroupAdmin, self).__init__(model, admin_site)
        self.property_seo_admin = None

    def get_urls(self):
        from django.urls import re_path

        urls = super(PropertyGroupAdmin, self).get_urls()
        info = self.model._meta.app_label, self.model._meta.model_name

        other_urls = [
            re_path(
                r"^(\d+)/details/$",
                self.admin_site.admin_view(self.details_view),
                name="%s_%s_details" % info,
            ),
        ]

        return other_urls + urls

    def get_nav_bar(self, request, obj=None, **kwargs):
        default_nav = [
            {"reverse": "details", "label": "Details", "icon": "fa-list"},
        ]

        return default_nav

    def get_inline_instances(self, request, obj=None):
        inline_instances = []
        inlines = []

        if request.path.endswith("/details/"):
            inlines.append(PropertyGroupDetailsInline)

        for inline_class in inlines:
            inline = inline_class(self.model, self.admin_site)
            if request:
                if not (
                    inline.has_add_permission(request, obj)
                    or inline.has_change_permission(request)
                    or inline.has_delete_permission(request)
                ):
                    continue
                if not inline.has_add_permission(request, obj):
                    inline.max_num = 0
            inline_instances.append(inline)

        return super(PropertyGroupAdmin, self).get_inline_instances(request, obj=obj) + inline_instances

    # Render Custom View
    @csrf_protect_m
    @transaction.atomic
    def custom_view(self, request, object_id, form_url="", extra_context=None):
        model = self.model
        opts = model._meta

        obj = self.get_object(request, unquote(object_id))

        if not self.has_change_permission(request, obj):
            raise PermissionDenied

        if obj is None:
            raise Http404(
                "%(name)s object with primary key %(key)r does not exist."
                % {"name": force_str(opts.verbose_name), "key": escape(object_id)}
            )

        ModelForm = PropertyGroupForm

        details_fieldset = []

        if request.method == "POST":
            form = ModelForm(data=request.POST, instance=obj)
            if form.is_valid():
                form_validated = True
                new_object = self.save_form(request, form, change=True)
            else:
                form_validated = False
                new_object = form.instance

            formsets, inline_instances = self._create_formsets(request, new_object, change=True)
            if all_valid(formsets) and form_validated:
                new_object = self.save_form(request, form, change=True)
                self.save_model(request, new_object, form, True)
                self.save_related(request, form, formsets, True)
                change_message = self.construct_change_message(request, form, formsets)
                self.log_change(request, new_object, change_message)
                return self.response_change(request, new_object)

        else:
            form = ModelForm(instance=obj)
            formsets, inline_instances = self._create_formsets(request, obj, change=True)

        adminForm = helpers.AdminForm(form, details_fieldset, {}, (), model_admin=self)
        media = self.media + adminForm.media

        inline_formsets = self.get_inline_formsets(request, formsets, inline_instances, obj)
        for inline_formset in inline_formsets:
            media = media + inline_formset.media

        context = {
            "adminform": adminForm,
            "object_id": object_id,
            "original": obj,
            "is_popup": False,
            "media": media,
            "inline_admin_formsets": inline_formsets,
            "errors": helpers.AdminErrorList(form, formsets),
            "app_label": opts.app_label,
        }
        context.update(extra_context or {})
        return self.render_change_form(
            request,
            context,
            change=True,
            obj=obj,
            form_url=form_url,
            template=self.change_form_template,
        )

    # Details
    def details_view(self, request, object_id, form_url="", extra_context=None):
        obj = self.get_object(request, unquote(object_id))
        new_extra_context = {
            "title": "Details",
        }

        try:
            new_extra_context["tagline"] = obj.tagline
            new_extra_context["ambassador"] = obj.ambassador

        except AttributeError:
            new_extra_context["tagline"] = None
            new_extra_context["ambassador"] = None

        new_extra_context.update(extra_context or {})
        return self.custom_view(request, object_id, form_url=form_url, extra_context=new_extra_context)

    # Documents
    def legal_documents_view(self, request, object_id, form_url="", extra_context=None):
        new_extra_context = {
            "title": "Legal Documents",
        }
        new_extra_context.update(extra_context or {})
        return self.custom_view(request, object_id, form_url=form_url, extra_context=new_extra_context)

    class Media:
        js = ("ckeditor/ckeditor.js",)
        css = {
            "screen": ("css/tabbed_translation_fields.css",),
        }


class TypologyAdmin(admin.ModelAdmin):
    exclude = ("item_o",)
    list_display = ("__str__", "slug", "item_o")
    list_display_links = ("__str__",)
    list_editable = ("item_o",)
    search_fields = (
        "name",
        "slug",
    )

    prepopulated_fields = {"slug": ("name",)}

    class Media:
        js = (
            "js/force_jquery.js",
            "js/tabbed_translation_fields.js",
            "ckeditor/ckeditor.js",
        )
        css = {
            "screen": ("css/tabbed_translation_fields.css",),
        }


class DetailOptionInlineAdmin(admin.TabularInline):
    model = DetailOption
    exclude = ("sort_order",)
    change_form_template = "admin/detail_option_change_form.html"
    prepopulated_fields = {"slug": ("name",)}
    list_filter = [
        "detail",
    ]
    list_display = ("__str__", "slug", "detail")

    class Media:
        js = ("js/force_jquery.js",)


class DetailAdmin(admin.ModelAdmin):
    inlines = (DetailOptionInlineAdmin,)
    exclude = ("sort_order",)
    list_filter = [
        "detail_type",
        "in_search",
    ]
    list_display = (
        "__str__",
        "slug",
        "in_search",
    )
    list_editable = ("in_search",)  # 'sort_order',
    change_form_template = "admin/detail_change_form.html"
    prepopulated_fields = {"slug": ("name",)}

    initial_values_fields = (
        "initial_text_value",
        "initial_bool_value",
        "initial_description_value",
        "initial_number_value",
        "initial_integer_value",
        "initial_date_value",
        "initial_time_value",
    )
    default_fields = (
        (
            "name",
            "slug",
        ),
        "help_text",
        "detail_type",
        "unit",
        "initial_text_value",
        "initial_description_value",
        "initial_number_with_value_type_selector_value",
        "admin_related_opts_permissions",
    )

    fieldsets = ((None, {"fields": default_fields + ("in_search",), "description": ""}),)

    def get_order_field(self):
        return "sort_order"

    class Media:
        js = ("js/force_jquery.js",)


class DetailCategorySectionAdmin(admin.ModelAdmin):
    exclude = ("item_o",)
    list_display = (
        "get_name",
        "slug",
    )
    prepopulated_fields = {"slug": ("name",)}

    def get_name(self, obj):
        name = obj.__str__()

        if hasattr(obj, "category"):
            out = "[....] %s" % name
            if obj.category and obj.category.icon:
                out = '<i class="fa %s fa-fw fa-lg"></i> %s' % (obj.category.icon, name)

        return out

    get_name.short_description = "Detail Category Section"
    get_name.allow_tags = True

    class Media:
        js = ("js/force_jquery.js",)


class DetailCategoryAdmin(admin.ModelAdmin):
    exclude = ("item_o",)
    list_display = (
        "get_name",
        "slug",
    )
    prepopulated_fields = {"slug": ("name",)}

    def get_name(self, obj):
        name = "%s" % obj.name
        out = "[....] %s" % name
        if obj.icon:
            out = '<i class="fa %s fa-fw fa-lg"></i> %s' % (obj.icon, name)
        return out

    get_name.short_description = "Detail Category"
    get_name.allow_tags = True

    class Media:
        js = ("js/force_jquery.js",)


class MediaPhotoAdmin(admin.ModelAdmin):
    formfield_overrides = {
        models.ImageField: {"widget": ImageWidget},
    }

    list_display = ("pk", "caption", "date_taken", "view_count", "admin_thumbnail")
    search_fields = [
        "caption",
    ]
    list_per_page = 10

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "caption",
                    "image",
                )
            },
        ),
        (
            "Visibility",
            {
                "classes": ("collapse",),
                "fields": ("crop_from",),
                "description": "Control how this photo is crop-ed.",
            },
        ),
    )

    class Media:
        js = (
            "js/force_jquery.js",
            "js/tabbed_translation_fields.js",
        )
        css = {
            "screen": ("css/tabbed_translation_fields.css",),
        }

    def get_urls(self):
        from django.urls import re_path

        info = self.model._meta.app_label, self.model._meta.model_name
        urls = super(MediaPhotoAdmin, self).get_urls()

        my_urls = [
            re_path(
                r"^ajax/get/$",
                self.admin_site.admin_view(self.ajax_get, cacheable=False),
                name="%s_%s_get_photos" % info,
            ),
            re_path(
                r"^ajax/photo/$",
                self.admin_site.admin_view(self.ajax_photo_get, cacheable=False),
                name="%s_%s_get_photo" % info,
            ),
            re_path(
                r"^upload/$",
                self.admin_site.admin_view(self.upload, cacheable=False),
                name="%s_%s_upload" % info,
            ),
        ]
        other_urls = list()
        return other_urls + my_urls + urls

    def response_change(self, request, obj):
        pk_value = obj._get_pk_val()
        if "_popup" in request.POST:
            return HttpResponse(
                "<!DOCTYPE html><html><head><title></title></head><body>"
                '<script type="text/javascript">opener.dismissEditPopup(window, "%s", "%s");</script></body></html>'
                % (escape(pk_value), escapejs(obj))  # escape() calls force_unicode.
            )

        return super(MediaPhotoAdmin, self).response_change(request, obj)

    def upload(self, request):
        # return the data to the uploading plugin

        if request.method == "POST":
            file = request.FILES["file"]
            response_data = {
                "name": str(file.name),
                "size": file.size,
                "type": file.content_type,
                "rev": "Photo",
            }

            if file and file.size > 0:
                try:
                    image = ImageField()
                    image.clean(file)
                except Exception:
                    # if a "bad" file is found we just skip it.
                    raise Http404()

                photo = self.model(image=file)
                photo.save()

                response_data["delete_url"] = ""
                # specify the delete type - must be POST for csrf
                response_data["delete_type"] = "POST"

                response_data["id"] = photo.id
                if hasattr(photo, "admin_photo_thumbnail"):
                    response_data["thumbnail"] = photo.admin_photo_thumbnail()
                else:
                    response_data["thumbnail"] = photo.admin_thumbnail()

                # generate the json data
                response_data = json.dumps([response_data])
                # response type
                response_type = "application/json"

                if "text/html" in request.META["HTTP_ACCEPT"]:
                    response_type = "text/html"

                # return the data to the uploading plugin
                return HttpResponse(response_data, content_type=response_type)

        raise Http404()

    def ajax_photo_get(self, request):
        if request.method == "GET":
            photo = self.model.objects.get(pk=request.GET.get("id"))
            photo = photo.to_json()
            return HttpResponse(json.dumps(photo), content_type="application/json")
        raise Http404()

    def ajax_get(self, request):
        photos = list()
        photos_list = self.model.objects.filter()
        paginator = Paginator(photos_list, request.GET.get("limit", 25))

        page = request.GET.get("page")
        try:
            paged_photos = paginator.page(page)
        except PageNotAnInteger:
            paged_photos = paginator.page(1)
        except EmptyPage:
            paged_photos = paginator.page(paginator.num_pages)

        for photo in paged_photos:
            photos.append(photo.to_json())

        output = {
            "photos": photos,
            "paginator": {
                "current": paged_photos.number,
                "limit": paged_photos.paginator.num_pages,
            },
        }
        return HttpResponse(json.dumps(output), content_type="application/json")


class PropertyMediaPhotoAdmin(MediaPhotoAdmin):
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "caption",
                    "alt_text",
                    "image",
                    "is_synched",
                )
            },
        ),
        (
            "Visibility",
            {
                "classes": ("collapse",),
                "fields": ("crop_from",),
                "description": "Control how this photo is crop-ed.",
            },
        ),
    )


class AmenityAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "item_o",
    )
    list_select_related = ["category"]
    list_editable = ("item_o",)
    list_filter = ("category",)
    list_display_links = ("name",)
    search_fields = (
        "name",
        "slug",
    )

    prepopulated_fields = {"slug": ("name",)}

    def get_ajax_add_url(self):
        Model = self.model
        all_objects = Model.objects.values("pk", "name")
        return all_objects


class AmenityCategoryAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
    )
    prepopulated_fields = {"slug": ("name",)}


class PropertyOwnershipAdmin(admin.ModelAdmin):
    list_display = ('name', 'country', 'account_id')
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ('account_id',)
    search_fields = ('name', 'email', 'account_id')


class PropertyManagerAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'account_id')
    ordering = ('name',)
    search_fields = (
        'name',
        'email',
        'account_id',
    )

    readonly_fields = ('account_id',)


class AmbassadorAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ['name', 'description']


class PropertyTaxAdmin(admin.ModelAdmin):
    list_display = ('property', 'created_at', 'updated_at')
    search_fields = ('property__name', 'property__reference')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


admin.site.register(Ambassador, AmbassadorAdmin)
admin.site.register(AmenityCategory, AmenityCategoryAdmin)
admin.site.register(Amenity, AmenityAdmin)
admin.site.register(Property, PropertyAdmin)
admin.site.register(PropertyTypology, TypologyAdmin)
admin.site.register(PropertyType)
admin.site.register(PropertyGroup, PropertyGroupAdmin)
admin.site.register(Detail, DetailAdmin)
admin.site.register(DetailCategorySection, DetailCategorySectionAdmin)
admin.site.register(DetailCategory, DetailCategoryAdmin)
admin.site.register(MediaPhoto, MediaPhotoAdmin)
admin.site.register(PropertyMediaPhoto, PropertyMediaPhotoAdmin)
admin.site.register(PropertyOwnership, PropertyOwnershipAdmin)
admin.site.register(PropertyTax, PropertyTaxAdmin)
admin.site.register(PropertyBedroomsConfigBedType)
admin.site.register(PropertyDivisionType)
admin.site.register(PropertyDivisionExtra)
admin.site.register(PropertyManager, PropertyManagerAdmin)
admin.site.register(PropertyCategory, PropertyCategoryAdmin)
