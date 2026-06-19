# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `platform/saas_runner.py`: multi-tenant SaaS REST entrypoint accepting
  `(token, provider, query, license)`, applying a safety-gated triage and
  returning a JSON report. Adds a per-tier sliding-window request rate limiter
  (`TierRateLimiter`) keyed by token — distinct from the monthly volume quota in
  `api.metering`. Exposes `POST /v1/saas/triage` and `GET /v1/saas/limits`.
- Platinum Sprint: CI/CD workflow, standardized badge row, ADR documentation
- Initial CHANGELOG following Keep a Changelog format

## [0.1.0] - 2026-02-11

### Added

- Initial public release as part of the organvm eight-organ system
- Core project structure and documentation
- README with portfolio-quality documentation

[Unreleased]: https://github.com/organvm-iii-ergon/universal-mail--automation/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/organvm-iii-ergon/universal-mail--automation/releases/tag/v0.1.0
