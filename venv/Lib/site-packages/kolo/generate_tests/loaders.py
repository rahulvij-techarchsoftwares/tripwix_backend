from importlib import import_module


def import_string(path):
    module_path, _sep, filter_name = path.rpartition(".")
    module = import_module(module_path)
    return getattr(module, filter_name)
