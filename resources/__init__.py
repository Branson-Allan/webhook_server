"""Resource registry. Every module here (not starting with '_') that defines
RESOURCE (or a RESOURCES list) becomes a webhook endpoint automatically."""
import importlib
import pkgutil

from models.resource import Resource


def ensure_unique(resources: list[Resource]) -> None:
    seen = set()
    for resource in resources:
        for attr in ("name", "path", "table"):
            marker = (attr, getattr(resource, attr))
            if marker in seen:
                raise ValueError(f"Duplicate resource {attr}: {marker[1]!r}")
            seen.add(marker)


def discover() -> list[Resource]:
    found: list[Resource] = []
    for info in pkgutil.iter_modules(__path__):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{__name__}.{info.name}")
        items = getattr(module, "RESOURCES", None)
        if items is None and hasattr(module, "RESOURCE"):
            items = [module.RESOURCE]
        found.extend(items or [])
    ensure_unique(found)
    return found
