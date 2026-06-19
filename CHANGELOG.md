# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-06-19

### Added

- PyPI packaging: full PEP 621 metadata in `pyproject.toml` with `umail` and
  `umail-mcp` console entry points, optional extras (`outlook`, `yaml`, `api`,
  `mcp`, `all`, `dev`), and a dynamic version sourced from `core.__version__`
- `setup.py` shim and `MANIFEST.in` for legacy tooling and sdist contents
- `umail --version` flag and a `core/py.typed` marker
- macOS bundle builder (`scripts/build_macos_bundle.sh`) producing a relocatable
  bundle with a private venv, `bin/umail` launcher, and LaunchAgent installer
- `publish.yml` workflow: build + verify sdist/wheel, build the macOS bundle,
  publish to PyPI via Trusted Publishing, and attach the bundle to releases
- `INSTALL.md` covering pip install, extras, from-source, and the macOS bundle

## [0.1.0] - 2026-02-11

### Added

- Initial public release as part of the organvm eight-organ system
- Core project structure and documentation
- README with portfolio-quality documentation

[Unreleased]: https://github.com/organvm-iii-ergon/universal-mail--automation/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/organvm-iii-ergon/universal-mail--automation/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/organvm-iii-ergon/universal-mail--automation/releases/tag/v0.1.0
