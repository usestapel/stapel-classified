"""stapel-classified — Composite: classified ads — shop + geo + search + moderation.

A composite lib writes NO business logic (projections-and-composition §3):
it is an INSTALLED_APPS/urls/config preset over existing Stapel modules,
plus — where two domain-blind engines need to meet — the cross-domain
declarations neither of them is allowed to write. The member modules stay
domain-blind; the composite is the one place allowed to know both sides.

Two such declarations live here:

- ``search_sources`` — the ``listing`` corpus for stapel-search, whose own
  source registry is empty by design;
- ``preset.SETTINGS_DEFAULTS["STAPEL_MODERATION"]`` — the ``listing`` and
  ``review`` target policies for stapel-moderation, whose target registry is
  likewise empty by design.

``preset`` is plain data and importable without Django settings;
``search_sources`` needs the app registry (it reads listings' own
``INDEXED_STATUSES``) and is therefore resolved lazily, by dotted path, the
way stapel-search's overlay resolves every source entry.
"""

__all__ = ["preset", "search_sources"]
