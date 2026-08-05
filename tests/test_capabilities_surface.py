"""Drift gate for the `surface` section of ``docs/capabilities.json``
(discoverability-design.md §1.2) — the third contract question, "is there
already a mechanism for X and what do I call?", after ``axes`` (switch on) and
``extension_points`` (replace).

stapel-classified is a COMPOSITE PRESET (projections-and-composition §3):
plain INSTALLED_APPS/urls/config wiring over the stapel-shop scenario
(categories + listings + reviews) plus stapel-geo, with no permission
classes, no public functions, no capability fields and no templates of its
own. Its ``docs/capabilities.meta.json`` declares ``surface_roots: []`` on
purpose — there is nothing here a product should call INSTEAD of the member
modules. The gate below still runs: it makes sure that stays a stated
decision, not silent absence, and it will fail loudly the moment a real
symbol appears in this module without an explaining intent line.

Honest boundary: the REST of this module's ``capabilities.json`` is still
hand-written (no gate registry, no ``docs/schema.json``), so only
``module``/``version``/``surface`` are gated below.
"""
import json
from pathlib import Path

import pytest

try:
    import stapel_tools  # noqa: F401  (probe: the emitter must be importable)
except ImportError as exc:  # pragma: no cover - environment failure, not a branch
    # NOT pytest.importorskip. A drift gate that skips when its emitter is
    # missing reports `1 skipped`, exits 0, and disappears among a hundred
    # green tests. A gate that cannot run has FAILED; it has not passed.
    raise RuntimeError(
        "capabilities surface drift gate cannot run: stapel-tools is not "
        "importable, and it carries the capabilities emitter this gate "
        "measures drift against. Install it (workspace venv, or `pip install "
        "stapel-tools`) and re-run. This is a hard failure on purpose — a "
        "skipped drift gate is silently no gate."
    ) from exc

from stapel_tools.surface import _stable_json, load_meta, patch_capabilities  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
COMMITTED = REPO / "docs" / "capabilities.json"


def _emitted() -> dict:
    try:
        return patch_capabilities(REPO, load_meta(REPO))
    except SystemExit as exc:  # the LOUD rule — report it, don't bury it
        pytest.fail(f"capabilities emission refused: {exc}", pytrace=False)


def test_no_drift():
    assert COMMITTED.read_text() == _stable_json(_emitted()), (
        "docs/capabilities.json is stale — run `make contract` and commit it"
    )


def test_version_tracks_pyproject():
    import tomllib

    pyproject = tomllib.loads((REPO / "pyproject.toml").read_text())
    assert json.loads(COMMITTED.read_text())["version"] == (
        pyproject["project"]["version"]
    )


def test_surface_is_declared_and_honestly_empty():
    """The composite has nothing to publish yet — that must be a stated
    decision (an empty ``surface_roots`` list in the meta file), not an
    absent one. If this module ever grows its own permission class, gate
    function or template, this test is the one that will need updating
    alongside the meta file — not a signal that something broke."""
    meta = load_meta(REPO)
    assert meta.get("surface_roots") == []
    assert meta.get("surface") == {}
    assert json.loads(COMMITTED.read_text()).get("surface") is None
