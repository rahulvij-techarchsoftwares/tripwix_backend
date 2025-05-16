def get_model_object_by_pk(model_class=None, obj_pk=None):
    if model_class and obj_pk:
        try:
            return model_class.objects.get(pk=obj_pk)
        except model_class.DoesNotExist:
            pass
    return None


def get_attrs_by_unit(unit):
    return {"data-unit": unit, 'unit': unit}


def format_field_slug(field_slug):
    return "%s" % field_slug.replace("-", "_")


def get_component_fields_gen(collection_object):
    qs = (
        collection_object.collection_type.components.select_related('component')
        .prefetch_related('component__component_fields', 'component__component_fields__field')
        .all()
    )
    for collection_type_components in qs:
        component = collection_type_components.component
        for component_fields in component.component_fields.all():
            # concatenate so we can use the same block in the same template
            field_slug = f'b{collection_type_components.pk}-{component_fields.slug}'
            yield component_fields.field, format_field_slug(
                field_slug
            ), component_fields, component, collection_type_components.pk
