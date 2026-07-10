"""Load custom memory modules from filesystem paths or uploaded source (V0.4.6)."""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from campaign_rpg_engine.memory_modules.base import MemoryModule

MAX_MODULE_SOURCE_BYTES = 256_000

ModuleFactory = Callable[..., MemoryModule]


@dataclass(frozen=True)
class CustomModuleMetadata:
    module_id: str
    label: str
    description: str
    create_agent_options: list[dict[str, Any]]
    source_path: Path
    filename: str


def _load_module_from_path(path: Path) -> Any:
    if not path.is_file():
        raise ValueError(f"Memory module path is not a file: {path}")
    if path.suffix.lower() != ".py":
        raise ValueError(f"Memory module must be a .py file (got {path.name!r}).")

    source = path.read_text(encoding="utf-8")
    if len(source.encode("utf-8")) > MAX_MODULE_SOURCE_BYTES:
        raise ValueError(
            f"Memory module source exceeds {MAX_MODULE_SOURCE_BYTES} bytes."
        )

    module_name = f"realm_custom_memory_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Could not load memory module from {path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def parse_custom_memory_module(path: Path) -> tuple[str, ModuleFactory, CustomModuleMetadata]:
    """Load a .py file and extract module id, factory, and catalog metadata."""
    loaded = _load_module_from_path(path)

    module_id = getattr(loaded, "MODULE_ID", None)
    if not module_id or not isinstance(module_id, str):
        raise ValueError(
            f"Memory module {path} must define MODULE_ID = \"your_module_id\"."
        )
    module_id = module_id.strip()
    if not module_id:
        raise ValueError("MODULE_ID must not be empty.")

    factory = getattr(loaded, "create_module", None)
    if factory is None or not callable(factory):
        raise ValueError(
            f"Memory module {path} must define create_module(**config) -> MemoryModule."
        )

    label = str(getattr(loaded, "MODULE_LABEL", module_id.replace("_", " ").title()))
    description = str(getattr(loaded, "MODULE_DESCRIPTION", ""))
    options = getattr(loaded, "CREATE_AGENT_OPTIONS", None)
    if options is None:
        options_list: list[dict[str, Any]] = []
    elif isinstance(options, list):
        options_list = list(options)
    else:
        raise ValueError("CREATE_AGENT_OPTIONS must be a list when provided.")

    metadata = CustomModuleMetadata(
        module_id=module_id,
        label=label,
        description=description,
        create_agent_options=options_list,
        source_path=path.resolve(),
        filename=path.name,
    )
    return module_id, factory, metadata


def write_module_source_to_cache(
    source: str,
    *,
    module_id: str,
    filename: str,
    cache_dir: Path,
) -> Path:
    """Persist uploaded source under cache_dir/{module_id}.py."""
    if len(source.encode("utf-8")) > MAX_MODULE_SOURCE_BYTES:
        raise ValueError(
            f"Memory module source exceeds {MAX_MODULE_SOURCE_BYTES} bytes."
        )
    cache_dir.mkdir(parents=True, exist_ok=True)
    dest = cache_dir / f"{module_id}.py"
    dest.write_text(source, encoding="utf-8")
    return dest
