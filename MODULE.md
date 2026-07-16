# MODULE.md — stapel-classified (agent-facing extension map)

A composite: INSTALLED_APPS/urls/config preset over existing Stapel modules
(no glue of its own yet — the app slot is reserved).
It writes NO business logic and mounts NO urls of its own (`http=False`,
`django_app=True` in STAPEL_LIBS — the app slot exists for glue).

## Seams

- `preset.INSTALLED_APPS` / `preset.URL_INCLUDES` / `preset.SETTINGS_DEFAULTS`
  — plain data; a project copies or references them. Override per-project by
  editing the project's own settings, not this package.
- Member modules keep ALL their own seams (each module's MODULE.md).
- Composition changes (add/remove a member) = a MINOR bump of this package
  (pre-1.0 house semver: minor = breaking).
