"""Drift gate for ``docs/llms.txt`` — the fifth per-module contract artifact
(badge-canon §3), emitted from ``docs/capabilities.json`` by
``stapel_tools.llms_txt`` (``make contract`` / ``make contract-check``).

Scope note: this module has no schema/flows/errors triad emitter and no
capabilities.json emitter either — ``docs/capabilities.json`` here is
HAND-AUTHORED (git log: "author capabilities.json for the stapel-catalog
sweep") and is committed by hand, never regenerated. This test file gates
ONLY ``docs/llms.txt``, which renders deterministically from that committed
capabilities.json — no Django, no subprocess, no regeneration of anything
else.

Regenerate after any change to ``docs/capabilities.json``::

    make contract        # or: python -m stapel_tools.llms_txt . --out docs

then commit ``docs/llms.txt``. Without regenerating, the drift gate below
fails.
"""
from pathlib import Path

import pytest

stapel_tools = pytest.importorskip(
    "stapel_tools",
    reason="stapel-tools is not installed — the llms.txt drift gate needs the "
    "emitter. CI installs it; locally use the workspace venv or "
    "`pip install stapel-tools`.",
)

from stapel_tools.llms_txt import load_inputs, render  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
COMMITTED = REPO / "docs" / "llms.txt"


def test_llms_txt_committed():
    assert COMMITTED.is_file(), (
        "docs/llms.txt is missing — run `make contract` and commit it"
    )


def test_llms_txt_has_no_drift():
    rendered = render(load_inputs(REPO))
    assert COMMITTED.read_text() == rendered, (
        "docs/llms.txt is stale — run `make contract` and commit it"
    )


def test_llms_txt_emission_is_deterministic():
    """Two independent emissions are byte-identical (drift gate is meaningful)."""
    a = render(load_inputs(REPO))
    b = render(load_inputs(REPO))
    assert a == b
