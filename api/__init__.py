"""HTTP API for universal-mail--automation.

A thin FastAPI surface over the existing engine. It never bypasses the
protected-sender gate: triage runs through the engine's gate AND an independent
audit observer, and the API asserts no-violations at the boundary (fail-closed).
"""

__version__ = "0.1.0"
