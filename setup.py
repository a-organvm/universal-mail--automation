#!/usr/bin/env python3
"""Legacy setuptools shim.

All package metadata lives in ``pyproject.toml`` (PEP 621). This file only
exists so that legacy tooling and ``pip install -e .`` against older pip
versions keep working. Modern builds should use ``python -m build``.
"""

from setuptools import setup

if __name__ == "__main__":
    setup()
