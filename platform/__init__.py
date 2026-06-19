"""Top-level ``platform`` package for the universal-mail SaaS layer.

⚠️  This package shares its name with the Python standard-library ``platform``
module. Because the project root is on ``sys.path`` (see ``pyproject.toml``'s
``pythonpath = ["."]``), a bare ``import platform`` can resolve to THIS package
instead of the stdlib module. Many third-party libraries (uvicorn, httpx,
setuptools, …) rely on ``platform.system()`` / ``platform.uname()`` at import
time, so to avoid breaking them this ``__init__`` transparently re-exports the
genuine standard-library module's public API. The project's SaaS REST entrypoint
lives in :mod:`platform.saas_runner`.

The submodule is also importable directly from its file path (the test-suite
loads it that way), which keeps it independent of import order between this
package and the stdlib module.
"""

from __future__ import annotations

import importlib.machinery as _machinery
import importlib.util as _util
import os as _os
import sys as _sys
import sysconfig as _sysconfig

__all__: list = []


def _load_stdlib_platform():
    """Load the genuine stdlib ``platform`` module, never this shadowing package.

    Searches only the interpreter's standard-library directories (explicitly
    excluding this package's own directory) so the lookup cannot recurse back
    into us. Returns the module, or ``None`` if it cannot be located.
    """
    self_dir = _os.path.dirname(_os.path.abspath(__file__))
    # The repo root contains THIS package, so a lookup there would re-discover us
    # (infinite recursion); exclude it and our own directory.
    excluded = {self_dir, _os.path.dirname(self_dir)}
    # Prefer the interpreter's declared standard-library directories; fall back
    # to every other sys.path entry. The fallback makes the lookup robust on
    # unusual layouts (embedded / zipped stdlib).
    candidates = [
        _sysconfig.get_paths().get("stdlib"),
        _sysconfig.get_paths().get("platstdlib"),
        *_sys.path,
    ]
    search = []
    for p in candidates:
        if not p:
            continue
        ap = _os.path.abspath(p)
        if ap in excluded or ap in search:
            continue
        search.append(ap)
    spec = _machinery.PathFinder.find_spec("platform", search)
    if spec is None or spec.loader is None:
        return None
    module = _util.module_from_spec(spec)
    # Register under a private name so it never clobbers this package, and so the
    # stdlib module's own lazy caches live on its own module object.
    _sys.modules.setdefault("_stdlib_platform", module)
    spec.loader.exec_module(module)
    return module


_stdlib = _load_stdlib_platform()
if _stdlib is not None:
    __all__ = list(getattr(_stdlib, "__all__", []))
    # Re-export every public name. Copied callables keep their original
    # ``__globals__`` (the stdlib module dict), so their internal caches and
    # cross-references resolve against the real module, not this package.
    for _name in dir(_stdlib):
        if _name.startswith("_"):
            continue
        globals()[_name] = getattr(_stdlib, _name)
