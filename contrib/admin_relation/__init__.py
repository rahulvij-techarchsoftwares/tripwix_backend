from __future__ import unicode_literals

import inspect
import json
from collections import OrderedDict
from functools import update_wrapper
from urllib.parse import quote as urlquote

import six
from django.contrib import admin, messages
from django.contrib.admin.actions import delete_selected
from django.contrib.admin.options import IS_POPUP_VAR, TO_FIELD_VAR
from django.contrib.admin.utils import quote, unquote
from django.db import transaction
from django.forms.models import _get_foreign_key
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.response import SimpleTemplateResponse
from django.urls import Resolver404, get_script_prefix, include, path, re_path, resolve, reverse
from django.utils.decorators import method_decorator
from django.utils.encoding import force_str
from django.utils.functional import cached_property
from django.utils.html import format_html
from django.utils.http import urlencode
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_protect
from six.moves.urllib.parse import parse_qsl, urlparse, urlunparse

from .views.main import RelationAdminChangeList

csrf_protect_m = method_decorator(csrf_protect)

__all__ = (
    'RelationAdmin',
    'RootRelationAdmin',
    'RelationAdminMixin',
    'RootRelationAdminMixin',
    'RelationAdminChangeList',
    'RelationAdminHelper',
)


class RelationAdminHelper(object):
    def __init__(self, relation_admin, request, view_args, object_id=None):
        self.parents = []
        self.lookup_kwargs = {}
        self.instances = OrderedDict()
        self.object_id = object_id
        self.view_args = view_args
        self.base_viewname = relation_admin.get_base_viewname()
        self.has_relation_admins = bool(relation_admin.get_relation_admin_instances())
        self.changelist_args = view_args[:-1] if self.object_id else view_args
        self.changelist_url = relation_admin.reverse_url('changelist', *self.changelist_args)
        self.load_tree(relation_admin, request)
        if self.changelist_args and self.parent:
            changeform_url = self.parent['admin'].reverse_url('change', *self.changelist_args)
        else:
            changeform_url = None
        self.changeform_url = changeform_url

    def load_tree(self, relation_admin, request):
        parent_admin = relation_admin.parent_admin
        fk_lookup = relation_admin.fk_name

        i = 2 if self.object_id else 1
        while parent_admin:
            obj = relation_admin.get_parent_instance(self.view_args[i * -1])
            self.parents.append(
                {
                    'admin': parent_admin,
                    'object': obj,
                    'nav_bar': parent_admin.handle_nav_bar(request, obj=obj),
                }
            )
            self.lookup_kwargs[fk_lookup] = obj
            self.instances[relation_admin.fk_name] = obj

            relation_admin = parent_admin
            parent_admin = getattr(relation_admin, 'parent_admin', None)
            if parent_admin:
                fk_lookup = '%s__%s' % (fk_lookup, relation_admin.fk_name)

            i += 1

    @cached_property
    def parent(self):
        return self.parents[0]

    @cached_property
    def root(self):
        return self.parents[-1]

    @cached_property
    def parent_instance(self):
        return self.parent['object']

    @cached_property
    def base_url_args(self):
        return [unquote(arg) for arg in self.view_args]


class RootRelationAdminHelper(object):
    def __init__(self, root_relation_admin, request, obj=None):
        self.object = obj
        self.object_id = obj.id if obj else None
        self.nav_bar = root_relation_admin.handle_nav_bar(request, obj=obj)
        self.has_relation_admins = bool(root_relation_admin.get_relation_admin_instances())
        if obj:
            changeform_url = root_relation_admin.reverse_url('change', obj.id)
        else:
            changeform_url = root_relation_admin.reverse_url('add')
        self.changeform_url = changeform_url

    @cached_property
    def parent(self):
        return None

    @cached_property
    def root(self):
        return {'object': self.object, 'nav_bar': self.nav_bar}

    @cached_property
    def parent_instance(self):
        return None

    @cached_property
    def base_url_args(self):
        return []


class RelationAdminBase(object):
    relation_admins = None

    def get_relation_admin_instances(self):
        return [modeladmin_class(self.model, self) for modeladmin_class in self.relation_admins or []]

    def get_relation_admin_urls(self):
        urlpatterns = []

        for modeladmin in self.relation_admin_instances:
            rx = r'^(.+)/%s/' % modeladmin.model._meta.model_name
            urlpatterns += [re_path(rx, include(modeladmin.urls))]

        return urlpatterns

    def get_relation_admin_instance(self, request, relation_admin_class):
        for modeladmin in self.relation_admin_instances:
            if isinstance(modeladmin, relation_admin_class) and modeladmin.has_change_permission(request):
                return modeladmin
        return False

    def get_nav_bar(self, request, obj=None):
        nav_bar = (modeladmin_class for modeladmin_class in self.relation_admins or [])
        return nav_bar

    def handle_relation_nav_bar_item(self, request, item, relation_admin_class, obj=None):
        relation_admin_instance = self.get_relation_admin_instance(request, relation_admin_class)
        if not relation_admin_instance:
            return None
        if item.get('icon') is None and hasattr(relation_admin_instance.model, 'Menu'):
            icon = relation_admin_instance.model.Menu.icon
            item.update(dict(icon=icon))
        if item.get('label') is None:
            item.update(dict(label=relation_admin_instance.model._meta.verbose_name_plural))
        if obj:
            url_args = relation_admin_instance.get_base_url_args(request) or [obj.pk]
            url_args = url_args[:-1] if len(url_args) > 1 else url_args
            item.update(dict(url=relation_admin_instance.reverse_url('changelist', *url_args)))

        return item

    def handle_reverse_nav_bar_item(self, request, item, viewname, obj=None):
        if not hasattr(self, 'reverse_url'):
            return None

        if item.get('label') is None:
            item.update(dict(label=viewname))
        args = ()
        if item.get('args', False) and obj:
            args = (obj.id,)

        item.update(dict(url=self.reverse_url(viewname, *args)))

        return item

    def handle_nav_bar_item(self, request, item, obj=None):
        url = None
        label = None
        default_item = dict(url=url, label=label)
        relation_admin_class = None
        reverse_viewname = None
        if isinstance(item, str):
            return dict(label=item)
        elif inspect.isclass(item) and issubclass(item, RelationAdminBase):
            relation_admin_class = item
        elif isinstance(item, dict) and 'relation' in item.keys():
            relation_admin_class = item.get('relation', None)
            default_item.update(item)
        elif isinstance(item, dict) and 'reverse' in item.keys():
            reverse_viewname = item.get('reverse', None)
            default_item.update(item)

        if relation_admin_class:
            return self.handle_relation_nav_bar_item(request, default_item, relation_admin_class, obj=obj)
        elif reverse_viewname:
            return self.handle_reverse_nav_bar_item(request, default_item, reverse_viewname, obj=obj)
        elif isinstance(item, dict):
            default_item.update(item)

        return default_item

    def handle_nav_bar(self, request, obj=None):
        for nav_item in self.get_nav_bar(request, obj):
            item = self.handle_nav_bar_item(request, nav_item, obj)
            if item:
                yield item


class RelationAdminMixin(RelationAdminBase):
    model = None
    fk_name = None

    change_list_template = 'admin/relation/change_list.html'
    change_form_template = 'admin/relation/change_form.html'
    delete_confirmation_template = 'admin/relation/delete_confirmation.html'
    delete_selected_confirmation_template = 'admin/relation/delete_selected_confirmation.html'
    object_history_template = 'admin/relation/object_history.html'
    relation_admin_helper_class = RelationAdminHelper

    def __init__(self, parent_model, parent_admin):
        self.parent_model = parent_model
        self.parent_admin = parent_admin
        if self.fk_name is None:
            self.fk_name = _get_foreign_key(parent_model, self.model).name

        super(RelationAdminMixin, self).__init__(self.model, parent_admin.admin_site)

        self.relation_admin_instances = self.get_relation_admin_instances()

    def get_relation_admin_helper(self, request, view_args, object_id=None):
        return self.relation_admin_helper_class(self, request, view_args, object_id=object_id)

    def get_model_perms(self, request):
        return super(RelationAdminMixin, self).get_model_perms(request)

    def get_actions(self, request):
        actions = super(RelationAdminMixin, self).get_actions(request)

        def relation_admin_delete_selected(modeladmin, req, qs):
            response = delete_selected(modeladmin, req, qs)
            if response:
                response.context_data.update(self.context_add_parent_data(request))
            return response

        if 'delete_selected' in actions:
            actions['delete_selected'] = (
                relation_admin_delete_selected,
                'delete_selected',
                actions['delete_selected'][2],
            )

        return actions

    def get_changelist(self, request, **kwargs):
        super().get_changelist(request, **kwargs)
        return RelationAdminChangeList

    def get_urls(self):
        def wrap(view):
            def wrapper(*args, **kwargs):
                return self.admin_site.admin_view(view)(*args, **kwargs)

            return update_wrapper(wrapper, view)

        base_viewname = self.get_base_viewname()

        urlpatterns = [
            path('', include(self.get_relation_admin_urls())),
            re_path(r'^$', wrap(self.changelist_view), name='%s_changelist' % base_viewname),
            re_path(r'^add/$', wrap(self.add_view), name='%s_add' % base_viewname),
            re_path(r'^(.+)/history/$', wrap(self.history_view), name='%s_history' % base_viewname),
            re_path(r'^(.+)/delete/$', wrap(self.delete_view), name='%s_delete' % base_viewname),
            re_path(r'^(.+)/change/$', wrap(self.change_view), name='%s_change' % base_viewname),
        ]

        urlpatterns = urlpatterns
        return urlpatterns

    def get_queryset(self, request):
        lookup_kwargs = request.relation_admin.lookup_kwargs
        return super(RelationAdminMixin, self).get_queryset(request).filter(**lookup_kwargs)

    def save_model(self, request, obj, form, change):
        for fk_field, instance in request.relation_admin.instances.items():
            if fk_field in self.model._meta._forward_fields_map.keys():
                setattr(obj, fk_field, instance)
        super(RelationAdminMixin, self).save_model(request, obj, form, change)

    def get_base_viewname(self):
        if hasattr(self.parent_admin, 'get_base_viewname'):
            base_viewname = self.parent_admin.get_base_viewname()
        else:
            base_viewname = '%s_%s' % (
                self.parent_model._meta.app_label,
                self.parent_model._meta.model_name,
            )

        return '%s_%s' % (base_viewname, self.model._meta.model_name)

    def reverse_url(self, viewname, *args, **kwargs):
        return reverse(
            'admin:%s_%s' % (self.get_base_viewname(), viewname),
            args=args,
            kwargs=kwargs,
            current_app=self.admin_site.name,
        )

    def get_base_url_args(self, request):
        if hasattr(request, 'relation_admin'):
            return request.relation_admin.base_url_args
        return []

    def context_add_parent_data(self, request, context=None):
        context = context or {}
        parent_instance = request.relation_admin.parent_instance
        context.update({'parent_instance': parent_instance, 'parent_opts': parent_instance._meta})
        return context

    def get_parent_instance(self, parent_id):
        return get_object_or_404(self.parent_model, pk=unquote(parent_id))

    def get_preserved_filters(self, request):
        match = request.resolver_match
        if self.preserve_filters and match:
            current_url = '%s:%s' % (match.app_name, match.url_name)
            changelist_url = 'admin:%s_changelist' % self.get_base_viewname()
            if current_url == changelist_url:
                preserved_filters = request.GET.urlencode()
            else:
                preserved_filters = request.GET.get('_changelist_filters')

            if preserved_filters:
                return urlencode({'_changelist_filters': preserved_filters})
        return ''

    def add_preserved_filters(self, context, url, popup=False, to_field=None):
        opts = context.get('opts')
        preserved_filters = context.get('preserved_filters')

        parsed_url = list(urlparse(url))
        parsed_qs = dict(parse_qsl(parsed_url[4]))
        merged_qs = dict()

        if opts and preserved_filters:
            preserved_filters = dict(parse_qsl(preserved_filters))

            match_url = '/%s' % url.partition(get_script_prefix())[2]
            try:
                match = resolve(match_url)
            except Resolver404:
                pass
            else:
                current_url = '%s:%s' % (match.app_name, match.url_name)
                changelist_url = 'admin:%s_changelist' % self.get_base_viewname()
                if changelist_url == current_url and '_changelist_filters' in preserved_filters:
                    preserved_filters = dict(parse_qsl(preserved_filters['_changelist_filters']))

            merged_qs.update(preserved_filters)

        if popup:
            from django.contrib.admin.options import IS_POPUP_VAR

            merged_qs[IS_POPUP_VAR] = 1
        if to_field:
            from django.contrib.admin.options import TO_FIELD_VAR

            merged_qs[TO_FIELD_VAR] = to_field

        merged_qs.update(parsed_qs)

        parsed_url[4] = urlencode(merged_qs)
        return urlunparse(parsed_url)

    @csrf_protect_m
    def changelist_view(self, request, *args, **kwargs):
        extra_context = kwargs.get('extra_context')
        request.relation_admin = RelationAdminHelper(self, request, args)
        extra_context = self.context_add_parent_data(request, extra_context)
        return super(RelationAdminMixin, self).changelist_view(request, extra_context)

    def add_view(self, request, *args, **kwargs):
        form_url, extra_context = kwargs.get('form_url', ''), kwargs.get('extra_context')
        request.relation_admin = RelationAdminHelper(self, request, args)
        extra_context = self.context_add_parent_data(request, extra_context)
        return super(RelationAdminMixin, self).add_view(request, form_url, extra_context)

    def change_view(self, request, *args, **kwargs):
        form_url, extra_context = kwargs.get('form_url', ''), kwargs.get('extra_context')
        object_id = args[-1]
        request.relation_admin = RelationAdminHelper(self, request, args, object_id=object_id)
        extra_context = self.context_add_parent_data(request, extra_context)
        return super(RelationAdminMixin, self).change_view(request, object_id, form_url, extra_context)

    @csrf_protect_m
    @transaction.atomic
    def delete_view(self, request, *args, **kwargs):
        extra_context = kwargs.get('extra_context')
        object_id = args[-1]
        request.relation_admin = RelationAdminHelper(self, request, args, object_id=object_id)
        extra_context = self.context_add_parent_data(request, extra_context)
        return super(RelationAdminMixin, self).delete_view(request, object_id, extra_context)

    def history_view(self, request, *args, **kwargs):
        extra_context = kwargs.get('extra_context')
        object_id = args[-1]
        request.relation_admin = RelationAdminHelper(self, request, args, object_id=object_id)
        extra_context = self.context_add_parent_data(request, extra_context)
        return super(RelationAdminMixin, self).history_view(request, object_id, extra_context)

    def response_add(self, request, obj, post_url_continue=None):
        opts = obj._meta
        pk_value = obj._get_pk_val()
        preserved_filters = self.get_preserved_filters(request)
        url_args = self.get_base_url_args(request)

        if "_saveasnew" in request.POST:
            url_args = url_args[:-1]

        obj_url = self.reverse_url('change', *url_args + [quote(pk_value)])

        if self.has_change_permission(request, obj):
            obj_repr = format_html('<a href="{}">{}</a>', urlquote(obj_url), obj)
        else:
            obj_repr = force_str(obj)

        msg_dict = {
            'name': force_str(opts.verbose_name),
            'obj': obj_repr,
        }

        if IS_POPUP_VAR in request.POST:
            to_field = request.POST.get(TO_FIELD_VAR)
            if to_field:
                attr = str(to_field)
            else:
                attr = obj._meta.pk.attname
            value = obj.serializable_value(attr)
            popup_response_data = json.dumps({'value': six.text_type(value), 'obj': six.text_type(obj)})
            return SimpleTemplateResponse('admin/popup_response.html', {'popup_response_data': popup_response_data})

        elif "_continue" in request.POST or (
            "_saveasnew" in request.POST and self.save_as_continue and self.has_change_permission(request, obj)
        ):
            msg = format_html(_('The {name} "{obj}" was added successfully. You may edit it again below.'), **msg_dict)
            self.message_user(request, msg, messages.SUCCESS)
            if post_url_continue is None:
                post_url_continue = obj_url
            post_url_continue = self.add_preserved_filters(
                {'preserved_filters': preserved_filters, 'opts': opts}, post_url_continue
            )
            return HttpResponseRedirect(post_url_continue)

        elif "_addanother" in request.POST:
            msg = format_html(
                _('The {name} "{obj}" was added successfully. You may add another {name} below.'), **msg_dict
            )
            self.message_user(request, msg, messages.SUCCESS)
            redirect_url = request.path
            redirect_url = self.add_preserved_filters(
                {'preserved_filters': preserved_filters, 'opts': opts}, redirect_url
            )
            return HttpResponseRedirect(redirect_url)

        else:
            msg = format_html(_('The {name} "{obj}" was added successfully.'), **msg_dict)
            self.message_user(request, msg, messages.SUCCESS)
            return self.response_post_save_add(request, obj)

    def response_change(self, request, obj):
        if IS_POPUP_VAR in request.POST:
            to_field = request.POST.get(TO_FIELD_VAR)
            attr = str(to_field) if to_field else obj._meta.pk.attname
            value = request.resolver_match.args[0]
            new_value = obj.serializable_value(attr)
            popup_response_data = json.dumps(
                {
                    'action': 'change',
                    'value': six.text_type(value),
                    'obj': six.text_type(obj),
                    'new_value': six.text_type(new_value),
                }
            )
            return SimpleTemplateResponse('admin/popup_response.html', {'popup_response_data': popup_response_data})

        opts = self.model._meta
        preserved_filters = self.get_preserved_filters(request)

        msg_dict = {
            'name': force_str(opts.verbose_name),
            'obj': format_html('<a href="{}">{}</a>', urlquote(request.path), obj),
        }
        if "_continue" in request.POST:
            msg = format_html(
                _('The {name} "{obj}" was changed successfully. You may edit it again below.'), **msg_dict
            )
            self.message_user(request, msg, messages.SUCCESS)
            redirect_url = request.path
            redirect_url = self.add_preserved_filters(
                {'preserved_filters': preserved_filters, 'opts': opts}, redirect_url
            )
            return HttpResponseRedirect(redirect_url)

        elif "_saveasnew" in request.POST:
            msg = format_html(_('The {name} "{obj}" was added successfully. You may edit it again below.'), **msg_dict)
            self.message_user(request, msg, messages.SUCCESS)
            redirect_url = self.reverse_url('change', *self.get_base_url_args(request))
            redirect_url = self.add_preserved_filters(
                {'preserved_filters': preserved_filters, 'opts': opts}, redirect_url
            )
            return HttpResponseRedirect(redirect_url)

        elif "_addanother" in request.POST:
            msg = format_html(
                _('The {name} "{obj}" was changed successfully. You may add another {name} below.'), **msg_dict
            )
            self.message_user(request, msg, messages.SUCCESS)
            redirect_url = self.reverse_url('add', *self.get_base_url_args(request)[:-1])
            redirect_url = self.add_preserved_filters(
                {'preserved_filters': preserved_filters, 'opts': opts}, redirect_url
            )
            return HttpResponseRedirect(redirect_url)

        else:
            msg = format_html(_('The {name} "{obj}" was changed successfully.'), **msg_dict)
            self.message_user(request, msg, messages.SUCCESS)
        return self.response_post_save_change(request, obj)

    def response_post_save_add(self, request, obj):
        opts = self.model._meta
        if self.has_change_permission(request, None):
            post_url = self.reverse_url('changelist', *self.get_base_url_args(request))
            preserved_filters = self.get_preserved_filters(request)
            post_url = self.add_preserved_filters({'preserved_filters': preserved_filters, 'opts': opts}, post_url)
        else:
            post_url = reverse('admin:index', current_app=self.admin_site.name)
        return HttpResponseRedirect(post_url)

    def response_post_save_change(self, request, obj):
        opts = self.model._meta

        if self.has_change_permission(request, None):
            post_url = self.reverse_url('changelist', *self.get_base_url_args(request)[:-1])
            preserved_filters = self.get_preserved_filters(request)
            post_url = self.add_preserved_filters({'preserved_filters': preserved_filters, 'opts': opts}, post_url)
        else:
            post_url = reverse('admin:index', current_app=self.admin_site.name)
        return HttpResponseRedirect(post_url)

    def response_delete(self, request, obj_display, obj_id):
        opts = self.model._meta

        if IS_POPUP_VAR in request.POST:
            popup_response_data = json.dumps({'action': 'delete', 'value': str(obj_id)})
            return SimpleTemplateResponse('admin/popup_response.html', {'popup_response_data': popup_response_data})

        self.message_user(
            request,
            _('The %(name)s "%(obj)s" was deleted successfully.')
            % {'name': force_str(opts.verbose_name), 'obj': force_str(obj_display)},
            messages.SUCCESS,
        )

        if self.has_change_permission(request, None):
            post_url = self.reverse_url('changelist', *self.get_base_url_args(request)[:-1])
            preserved_filters = self.get_preserved_filters(request)
            post_url = self.add_preserved_filters({'preserved_filters': preserved_filters, 'opts': opts}, post_url)
        else:
            post_url = reverse('admin:index', current_app=self.admin_site.name)
        return HttpResponseRedirect(post_url)


class RootRelationAdminMixin(RelationAdminBase):
    change_form_template = 'admin/relation/root_change_form.html'

    def __init__(self, *args, **kwargs):
        super(RootRelationAdminMixin, self).__init__(*args, **kwargs)
        self.relation_admin_instances = self.get_relation_admin_instances()

    def get_urls(self):
        return self.get_relation_admin_urls() + super(RootRelationAdminMixin, self).get_urls()

    def reverse_url(self, viewname, *args, **kwargs):
        info = self.model._meta.app_label, self.model._meta.model_name, viewname
        return reverse('admin:%s_%s_%s' % info, args=args, kwargs=kwargs, current_app=self.admin_site.name)

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        request.root_relation_admin = RootRelationAdminHelper(self, request, obj=obj)
        return super(RelationAdminBase, self).render_change_form(
            request, context, add=add, change=change, form_url=form_url, obj=obj
        )


class RelationAdmin(RelationAdminMixin, admin.ModelAdmin):
    pass


class RootRelationAdmin(RootRelationAdminMixin, admin.ModelAdmin):
    pass
