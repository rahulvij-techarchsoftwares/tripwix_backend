# -*- coding: utf-8 -*-
from django.contrib.admin.views.main import SEARCH_VAR
from django.template import Library
from django.utils.safestring import mark_safe

register = Library()


def get_model_icon_overwrites(model):
    model_name = model.__name__
    if model_name == "User":
        return "fa-user"
    if model_name == "Group":
        return "fa-group"
    if model_name == "Tag":
        return "fa-tags"
    return None


@register.simple_tag(takes_context=True)
def get_context(context, item):
    if item and item in context:
        return context[item]
    return


@register.simple_tag
def breadcrumbs_icon(options):
    model = None
    icon = "fa-default"
    if isinstance(options, models.Model):
        model = options
    elif hasattr(options, 'model'):
        model = options.model
    if model and get_model_icon_overwrites(model):
        icon = get_model_icon_overwrites(model)
    if model and hasattr(model, 'Menu'):
        if hasattr(model.Menu, 'icon'):
            icon = model.Menu.icon
    return mark_safe('<span class="breadcrumb-icon"><i class="fa %s"></i></span>' % icon)


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)
