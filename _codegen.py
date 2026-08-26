"""stapel-classified contract-emission harness (contract-pipeline.md §2-3).

Emits this package's OWN contract triad into ``docs/`` from a single-module
``{classified + core}`` Django instance mounted at the canonical
``/classified/api/v1`` prefix:

  docs/schema.json   drf-spectacular OpenAPI, this module only
  docs/flows.json    generate_flow_docs machine artifact
  docs/errors.json   generate_error_keys registry (the per-module etalon)

A composite emitting a contract is new in 0.2.0 and follows from the same
change: until then this package served no HTTP, so there was nothing to
describe. Its MEMBERS still emit their own — a composite's schema is its own
surface, never the union.

Usage:
    python -m stapel_classified._codegen --out docs        # `make contract`
"""
from __future__ import annotations

import argparse
import os
import sys
from contextlib import contextmanager
from pathlib import Path

#: The packages whose error keys belong in THIS module's contract.
#:
#: The error registry is a process-global map holding every key any imported
#: app registered, so an emitted errors.json is otherwise a function of what
#: else is installed on the emitting machine — the drift that killed
#: stapel-notifications 0.17.0 and 0.17.1 in their publish jobs. This harness
#: mounts only {classified + core} today and so emits only those two, but the
#: guard is what keeps that true when a sibling is added to
#: `_codegen_settings` — and a composite is the module most likely to add one.
#: Foreign keys are real and documented, in their owner's errors.json beside
#: the catalogues that translate them. Here they are noise.
OWNED_ERROR_PACKAGES = frozenset({"stapel_core", "stapel_classified"})


@contextmanager
def scoped_error_registry():
    """Restrict the global error registry to :data:`OWNED_ERROR_PACKAGES`.

    Wrap any emission that reads the registry, so the artifact describes this
    library rather than this machine. Restored on exit: the runtime tests
    still see the full key set, which is what ``/error-keys/`` serves.

    It reaches for core's private maps because core exposes no owner filter
    yet; a ``--owner`` option on ``generate_error_keys`` is the durable home
    for this, and until it exists the scoping lives with the contract it
    protects. (Pattern: stapel-notifications ``_codegen.py``.)
    """
    from stapel_core.django.api import errors as core_errors

    saved_keys = dict(core_errors._GLOBAL_REGISTRY)
    saved_owners = dict(core_errors._OWNER_REGISTRY)
    for code, owner in saved_owners.items():
        if owner is not None and owner not in OWNED_ERROR_PACKAGES:
            core_errors._GLOBAL_REGISTRY.pop(code, None)
            core_errors._OWNER_REGISTRY.pop(code, None)
    try:
        yield
    finally:
        core_errors._GLOBAL_REGISTRY.clear()
        core_errors._GLOBAL_REGISTRY.update(saved_keys)
        core_errors._OWNER_REGISTRY.clear()
        core_errors._OWNER_REGISTRY.update(saved_owners)


def _configure() -> None:
    """Configure + boot the single-module Django instance for emission."""
    # `python -m` prepends cwd to sys.path; strip the repo root the way the
    # flat-layout conftest does, so a top-level module name cannot shadow.
    repo_root = os.path.dirname(os.path.abspath(__file__))
    sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.getcwd()) != repo_root]

    from django.conf import settings

    if not settings.configured:
        from stapel_classified._codegen_settings import settings_kwargs

        settings.configure(**settings_kwargs())

    import django

    django.setup()

    from drf_spectacular.settings import spectacular_settings

    from stapel_classified._codegen_settings import CODEGEN_SCHEMA_PATH_PREFIX

    spectacular_settings.SCHEMA_PATH_PREFIX = CODEGEN_SCHEMA_PATH_PREFIX

    # A real all-modules deployment registers drf-spectacular's JWT-cookie
    # security-scheme extension as a side effect of its dev-only Swagger URLs.
    # A single-module harness has no co-mounted sibling to trigger it, so
    # without this the protected endpoints emit without their `security` entry.
    from stapel_core.django.openapi.swagger import _register_jwt_auth_extension

    _register_jwt_auth_extension()


def _require_python_312() -> None:
    """Abort emission if not running the pinned 3.12 interpreter.

    drf-spectacular renders component descriptions (``Optional[X]`` vs
    ``X | None``) differently across Python minors, so emitting on anything
    but the CI pin produces false diffs against the committed docs/*.json.
    """
    if sys.version_info[:2] != (3, 12):
        got = f"{sys.version_info.major}.{sys.version_info.minor}"
        raise SystemExit(
            f"stapel-classified contract emission ABORTED: running Python {got}, "
            "but contracts must be emitted on Python 3.12 (the CI pin)."
        )


def main(argv: list[str] | None = None) -> int:
    _require_python_312()

    parser = argparse.ArgumentParser(
        prog="stapel-classified-contract",
        description="Emit this module's contract triad into --out, canonical "
        "/classified/api/v1 prefix.",
    )
    parser.add_argument("--out", default="docs", help="Output directory (default: docs).")
    args = parser.parse_args(argv)

    _configure()

    from stapel_tools.codegen import emit_errors, emit_flows, emit_schema

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    paths = emit_schema(out / "schema.json")
    flows = emit_flows(out / "flows.json")
    with scoped_error_registry():
        errors = emit_errors(out / "errors.json")

    print(
        f"stapel-classified contract: {paths} paths, {flows} flows, "
        f"{errors} error keys -> {out}/",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
