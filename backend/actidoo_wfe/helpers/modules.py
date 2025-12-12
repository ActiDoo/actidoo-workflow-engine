import importlib
import pkgutil


def import_submodules(from_module_name):
    """Import all submodules of a module, recursively."""
    module = importlib.import_module(from_module_name)

    if hasattr(module, "__path__"):
        # If it has a __path__ attribute, it's a package, so use pkgutil.walk_packages
        for loader, module_name, is_pkg in pkgutil.walk_packages(
            module.__path__, module.__name__ + "."
        ):
            importlib.import_module(module_name)


def env_from_module(from_module_name):
    # get a handle on the module
    mdl = importlib.import_module(from_module_name)

    # is there an __all__?  if so respect it
    if "__all__" in mdl.__dict__:
        names = mdl.__dict__["__all__"]
    else:
        # otherwise we import all names that don't begin with _
        names = [x for x in mdl.__dict__ if not x.startswith("_")]

    # now drag them in
    return {k: getattr(mdl, k) for k in names}
