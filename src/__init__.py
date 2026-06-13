"""
Realm Fabric — grid-based agent simulation engine.

Public API: import from ``realm_fabric`` (``Session``, ``GameProfile``, …).
``src.*`` modules are used by the CLI and tests; prefer ``realm_fabric`` in apps.
"""

try:
    from importlib.metadata import version as _pkg_version

    __version__ = _pkg_version("realm-fabric")
except Exception:
    __version__ = "0.3.0"

__all__ = ["__version__"]
