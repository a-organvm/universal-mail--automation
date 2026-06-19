"""Platform-facing receivers for the storefront that sells mail-automation seats.

Currently a single module, :mod:`platform.checkout`, which receives the
``license-issued`` webhook and persists the granted license for the local engine
to read (see ``core/license.py``).
"""
