from importlib import import_module
from typing import List

from kolo.generate_tests.queries import DjangoField


class Factory:
    def __init__(
        self,
        module: str,
        model: str,
        factory: str,
        fields: List[DjangoField],
        variable_name: str,
    ):
        self.module = module
        self.model = model
        self.factory = factory
        self.fields = fields
        self.variable_name = variable_name


def import_factory(factory_path):
    try:
        module_path, factory_name = factory_path.rsplit(".", 1)
    except ValueError:
        raise ImportError(f"Could not import `{factory_path}`.")

    module = import_module(module_path)
    return getattr(module, factory_name)


def import_factories(config):
    factory_configs = config.get("test_generation", {}).get("factories", {})
    factories = {}
    for factory_config in factory_configs:
        factory_path = factory_config["path"]
        factory = import_factory(factory_path)
        factory_config["factory"] = factory
        factory_config["name"] = factory.__name__
        model = factory._meta.model
        model_path = f"{model.__name__}"
        factories[model_path] = factory_config
    return factories


def filter_defaults(fields, factory_class):
    filtered = []
    for field in fields:
        name = field.name
        try:
            value = getattr(factory_class, name)
        except AttributeError:
            filtered.append(field)
            continue

        if field.value_repr == repr(value):
            continue
        filtered.append(field)
    return filtered


def build_factory(model, config):
    if config.get("pk", False):
        fields = [model.primary_key]
        fields.extend(model.fields)
    else:
        fields = model.fields

    factory_class = config["factory"]
    fields = filter_defaults(fields, factory_class)

    factory = Factory(
        module=factory_class.__module__,
        model=model.model,
        factory=config["name"],
        fields=fields,
        variable_name=model.variable_name,
    )
    return factory


def build_factories(fixtures, configs):
    factories = []
    for create_model in fixtures:
        model = create_model.model
        try:
            config = configs[model]
        except KeyError:
            factories.append(create_model)
            continue

        factory = build_factory(create_model, config)
        factories.append(factory)
    return factories
