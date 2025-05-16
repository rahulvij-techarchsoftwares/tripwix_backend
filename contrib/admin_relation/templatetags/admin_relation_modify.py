from __future__ import unicode_literals

from django import template
from django.contrib.admin.templatetags.admin_modify import submit_row
from django.urls import reverse
from django.utils.encoding import force_str

register = template.Library()


@register.inclusion_tag('admin/relation/breadcrumbs.html', takes_context=True)
def relation_admin_breadcrumbs(context):
    request = context['request']
    opts = context['opts']
    root = {
        'opts': request.relation_admin.root['admin'].opts,
        'name': request.relation_admin.root['object']._meta.app_config.verbose_name,
        'url': reverse(
            'admin:app_list',
            kwargs={'app_label': request.relation_admin.root['object']._meta.app_label},
        ),
    }

    breadcrumbs = []
    view_args = list(request.relation_admin.view_args)

    i = 0
    relation_admin_parents = request.relation_admin.parents[::-1]

    for parent in relation_admin_parents:
        adm = parent['admin']
        obj = parent['object']

        breadcrumbs.extend(
            [
                {
                    'name': obj._meta.verbose_name_plural,
                    'url': adm.reverse_url('changelist', *view_args[:i]),
                    'has_change_permission': adm.has_change_permission(request),
                },
                {
                    'name': force_str(obj),
                    'url': adm.reverse_url('change', *view_args[: i + 1]),
                    'has_change_permission': adm.has_change_permission(request, obj),
                },
            ]
        )
        i += 1

    return {
        'root': root,
        'breadcrumbs': breadcrumbs,
        'opts': opts,
    }


@register.inclusion_tag('admin/relation/navigation.html', takes_context=True)
def relation_admin_navigation(context):
    request = context['request']

    if hasattr(request, 'root_relation_admin'):
        # because this is the root show Configuration button + navbar
        root_relation_admin = request.root_relation_admin

        relation_admin_data = {
            'is_root': True,
            'back_url': None,
            'show_back_url': False,
            'show_nav_bar': root_relation_admin.has_relation_admins,
            'parent_object': None,
            'nav_bar': root_relation_admin.root['nav_bar'],
            'changeform_url': root_relation_admin.changeform_url,
        }
    elif hasattr(request, 'relation_admin'):
        # need to check if this admin is a leaf
        relation_admin = request.relation_admin
        is_changelist_view = relation_admin.changelist_url == request.path

        relation_admin_data = {
            'is_root': False,
            'back_url': relation_admin.changelist_url,
            'show_back_url': not is_changelist_view,
            'show_nav_bar': True if is_changelist_view else relation_admin.has_relation_admins,
            'parent_object': relation_admin.parent['object'],
            'nav_bar': relation_admin.parent['nav_bar'],
            'changeform_url': relation_admin.changeform_url,
        }
    else:
        relation_admin_data = {}

    default_context = {'path': request.path, 'opts': context['opts']}
    default_context.update(relation_admin_data)
    return default_context


@register.simple_tag(takes_context=True)
def relation_admin_url(context, viewname, *args, **kwargs):
    relation_admin = context['request'].relation_admin
    view_args = relation_admin.base_url_args[:-1] if relation_admin.object_id else relation_admin.base_url_args
    return reverse(
        'admin:%s_%s' % (relation_admin.base_viewname, viewname),
        args=view_args + list(args),
        kwargs=kwargs,
    )


@register.inclusion_tag('admin/relation/submit_line.html', takes_context=True)
def relation_admin_submit_row(context):
    ctx = submit_row(context)
    ctx.update({'request': context['request']})
    return ctx
