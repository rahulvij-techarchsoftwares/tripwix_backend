from datetime import timedelta
from decimal import Decimal
from functools import lru_cache
from typing import Any, Dict

import click

from .db import SchemaNotFoundError, load_schema_for_commit_sha
from .git import COMMIT_SHA


def get_schema():
    from django.apps import apps

    schema = {}
    for config in apps.get_app_configs():
        for model in config.get_models():
            schema[model._meta.db_table] = model_schema(model)
    return schema


def verbose_name(model):
    from django.utils.text import camel_case_to_spaces

    return camel_case_to_spaces(model.__name__).replace(" ", "_")


def model_schema(model):
    from django.contrib.contenttypes.fields import GenericForeignKey

    fields: Dict[str, Any] = {}
    schema = {
        "model_module": model.__module__,
        "model_name": model.__qualname__,
        "verbose_name": verbose_name(model),
        "fields": fields,
    }
    for field in model._meta.get_fields():
        try:
            column = field.column
        except AttributeError:
            # `ForeignObjectRel`
            continue

        if column is None:
            # `GenericRelation` or `GenericForeignKey`
            if isinstance(field, GenericForeignKey):
                fields[field.name] = gfk_schema(field)
            continue
        fields[column] = field_schema(field)

    return schema


def has_unique(field):
    if getattr(field, "_unique", False):
        return True

    meta = field.model._meta
    for fields in meta.unique_together:
        if field.name in fields:
            return True

    from django.db.models import UniqueConstraint

    for constraint in meta.constraints:
        if isinstance(constraint, UniqueConstraint) and field.name in constraint.fields:
            return True

    return False


def field_schema(field):
    from django.db.models.fields import NOT_PROVIDED

    field_class = type(field)
    schema = {
        "field_attname": field.attname,
        "field_name": field.name,
        "null": field.null,
        "primary_key": field.primary_key,
        "auto_created": field.auto_created,
        "is_relation": field.is_relation,
        "django_field": f"{field_class.__module__}.{field_class.__qualname__}",
        "has_unique": has_unique(field),
        "gfk_content_type_field": None,
        "gfk_object_id_field": None,
    }
    if field.default is not NOT_PROVIDED and not callable(field.default):
        schema["default"] = field_default(field.default)
    if hasattr(field, "auto_now"):
        schema["auto_now"] = field.auto_now
        schema["auto_now_add"] = field.auto_now_add
    if field.is_relation:
        schema["related_model"] = field.related_model._meta.db_table
        schema["related_pk"] = field.related_model._meta.pk.name

    return schema


def gfk_schema(field):
    return {
        "auto_created": field.auto_created,
        "django_field": "django.contrib.contenttypes.fields.GenericForeignKey",
        "field_attname": None,
        "field_name": field.name,
        "gfk_content_type_field": field.ct_field,
        "gfk_object_id_field": field.fk_field,
        "has_unique": has_unique(field),
        "is_relation": field.is_relation,
        "null": None,
        "primary_key": False,
        "related_model": None,
        "related_pk": None,
    }


def field_default(default):
    from django.db.models import Choices

    if isinstance(default, Choices):
        default = {
            "value": default._value_,
            "name": default._name_,
            "label": default.label,
            "choices_name": type(default).__qualname__,
            "choices_module": type(default).__module__,
        }
    elif isinstance(default, Decimal):
        default = {
            "value": str(default),
            "type": "Decimal",
        }
    elif isinstance(default, timedelta):
        default = {
            "value": {
                "days": default.days,
                "seconds": default.seconds,
                "microseconds": default.microseconds,
            },
            "type": "timedelta",
        }
    else:
        default = {"value": default}
    return default


SCHEMA_NOT_FOUND_WARNING = """\
Warning: Could not find a Django schema for commit: {0}.

Falling back to the current commit's schema.

For more reliable results, run `kolo store-django-model-schema` from {0}
then retry this command.
"""


@lru_cache(maxsize=None)
def get_schema_for_commit(commit_sha, db_path, use_saved_schemas):
    if not use_saved_schemas or commit_sha == COMMIT_SHA:
        return get_schema()

    try:
        return load_schema_for_commit_sha(db_path, commit_sha)
    except SchemaNotFoundError:
        click.echo(SCHEMA_NOT_FOUND_WARNING.format(commit_sha), err=True)
        return get_schema()
