# Changelog

## [0.1.4] - 2026-08-02

### Added
- `docs/llms.txt` — the fifth contract artifact, an agent-sized slice of the
  hand-authored `docs/capabilities.json`, wired into a new `make contract` /
  `make contract-check` (badge-canon §3). `docs/capabilities.json`'s
  `version` field brought back in sync with `pyproject.toml` (it had drifted
  to 0.1.2 across the 0.1.3 release).
- Canonical `ci.yml` with coverage, `codecov.yml`, Python 3.14 classifier,
  badge canon in README (truncated to license + status — this module has
  never published to PyPI).

## [0.1.2] - 2026-07-17

Fleet follow-up to stapel-core 0.12.0 (legacy shim sweep). Member pins
(`stapel-shop` 0.1.2, `stapel-geo` 0.3.2) already fit this composite's
existing ceilings. Suite green.

### Changed
- `stapel-core` ceiling `<0.12` → `<0.13`.

## [0.1.1] - 2026-07-17

### Fixed
- `stapel-geo` pin was still `>=0.2,<0.3` — stale since geo's v2 redesign
  released as 0.3.0 (pre-1.0 minor = breaking); widened to `>=0.2,<0.4`.
  Classified's own code only mounts `stapel_geo.urls`/`INSTALLED_APPS`
  (never touches geo internals directly — confirmed against this repo's
  own `conftest.py`, which doesn't even install `stapel_geo` for the unit
  harness), so the wider range is safe. Unrelated to core 0.11, but
  without it `pip install .` couldn't resolve at all.

### Changed
- `stapel-core` ceiling raised `>=0.10,<0.11` → `>=0.10,<0.12` (core 0.11
  fleet re-pin). Suite green as-is.

## [0.1.0] - 2026-07-16

### Added

- Initial composite (projections-and-composition §3): pyproject pins over
  the member modules, `preset` (INSTALLED_APPS/urls/STAPEL_* defaults),
  AppConfig app slot, minimal tests.
