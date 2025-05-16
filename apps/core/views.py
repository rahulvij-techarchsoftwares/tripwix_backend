from django.apps import apps
from django.contrib.admin.views.autocomplete import AutocompleteJsonView
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import FieldDoesNotExist, PermissionDenied
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters
from django.views.generic.edit import FormView

from .forms import OtpSetupForm


class AppsAutocompleteJsonView(AutocompleteJsonView):
    def get_queryset(self):
        """Return queryset based on ModelAdmin.get_search_results()."""
        qs = self.model_admin.get_queryset(self.request)
        qs, search_use_distinct = self.model_admin.get_search_results(self.request, qs, self.term)
        if search_use_distinct:
            qs = qs.distinct()
        return qs

    def process_request(self, request):
        """
        Validate request integrity, extract and return request parameters.
        Since the subsequent view permission check requires the target model
        admin, which is determined here, raise PermissionDenied if the
        requested app or model are malformed.
        Raise Http404 if the target model admin is not configured properly with
        search_fields.
        """
        term = request.GET.get("term", "")
        try:
            app_label = request.GET["app_label"]
            model_name = request.GET["model_name"]
        except KeyError as e:
            raise PermissionDenied from e

        # Retrieve objects from parameters.
        try:
            remote_model = apps.get_model(app_label, model_name)
        except LookupError as e:
            raise PermissionDenied from e

        try:
            model_admin = self.admin_site._registry[remote_model]
        except KeyError as e:
            raise PermissionDenied from e

        search_fields = model_admin.get_search_fields(request)
        # Validate suitability of objects.
        if not search_fields:
            raise Http404("%s must have search_fields for the autocomplete_view." % type(model_admin).__qualname__)

        source_field = None
        to_field_name = remote_model._meta.pk.attname
        to_field_name = remote_model._meta.get_field(to_field_name).attname
        if not model_admin.to_field_allowed(request, to_field_name):
            raise PermissionDenied

        return term, model_admin, source_field, to_field_name


class OtpSetupView(FormView):
    form_class = OtpSetupForm
    template_name = "admin/two_factor_setup.html"
    extra_context = None

    @method_decorator(sensitive_post_parameters())
    @method_decorator(csrf_protect)
    @method_decorator(never_cache)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def form_valid(self, form):
        """Security check complete."""
        return HttpResponseRedirect(reverse_lazy('admin:login'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_site = get_current_site(self.request)
        context.update(
            {
                "site": current_site,
                "site_name": current_site.name,
                **(self.extra_context or {}),
            }
        )
        return context
