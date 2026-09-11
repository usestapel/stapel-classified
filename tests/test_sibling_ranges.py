"""The sibling-range policy, pinned so a future tighter cap fails CI.

Architect's ruling, 2026-09-11:

    A COMPOSITE library depends on its `stapel-*` siblings with a floor and
    `<1.0` only; compatibility with a new sibling minor is proven by the
    composite's own CI installing the NEWEST sibling in range, and by the
    fleet's joint-resolution gate before any image build — not by a cap.

Why the rule needs a gate rather than a comment: this package holds no logic
of its own, only a combination of member versions, and for four releases
running the combination was the WALL. `<0.23` on stapel-categories, `<0.5` on
stapel-vocabularies and `<0.7` on stapel-reviews each answered a fleet image
build with `ResolutionImpossible`, and each cost a cap-only release of this
package AND of stapel-shop before anything could be built. The house pre-1.0
rule — minor = breaking — still governs LEAF libraries, which is where a cap
buys something: a leaf caps a dependency it actually calls. A composite calls
nothing; capping every sibling at the next minor only guarantees that the
composite expires the moment any one of eleven siblings ships a minor.

So the upper bound stops being an assertion about compatibility and the CI
`newest-siblings` leg starts being one. This test keeps the two from drifting
apart: reinstate a tighter cap and it fails here, with the ruling's sentence.
"""
import tomllib
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.version import Version

REPO = Path(__file__).resolve().parent.parent

RULING = (
    "A composite library depends on its stapel-* siblings with a floor and "
    "<1.0 only; compatibility with a new sibling minor is proven by the "
    "composite's own CI installing the newest sibling within range and by "
    "the fleet's joint-resolution gate before any image build, not by a cap."
)


def _pyproject() -> dict:
    """The source file, not installed metadata.

    `importlib.metadata` describes whatever the editable install last
    recorded, which can lag an edit by an arbitrary amount; the file is what
    the release publishes and therefore what the fleet will have to resolve.
    """
    return tomllib.loads((REPO / "pyproject.toml").read_text())


def _sibling_requirements() -> list[tuple[str, Requirement]]:
    """Every `stapel-*` requirement in the file, runtime and extras alike.

    Extras are included on purpose: `pip install -e ".[test]"` reaches for
    stapel-tools, stapel-profiles and stapel-realtime, and a cap there stops
    a contributor's install exactly as hard as one in `dependencies`.
    """
    project = _pyproject()["project"]
    found: list[tuple[str, Requirement]] = []
    groups: list[tuple[str, list[str]]] = [
        ("dependencies", project.get("dependencies") or [])
    ]
    for extra, specs in (project.get("optional-dependencies") or {}).items():
        groups.append((f"optional-dependencies.{extra}", specs))

    for where, specs in groups:
        for spec in specs:
            req = Requirement(spec)
            if req.name.lower().replace("_", "-").startswith("stapel-"):
                found.append((where, req))
    return found


def test_the_file_actually_declares_siblings():
    """Guard against a gate that measures nothing.

    Every assertion below is a loop over the requirements; a parse that found
    none would pass all of them while proving nothing at all.
    """
    siblings = _sibling_requirements()
    assert len(siblings) >= 5, (
        "found only %d stapel-* requirements in pyproject.toml — the parse is "
        "broken, so the rest of this module proves nothing" % len(siblings)
    )


@pytest.mark.parametrize(
    "where,req",
    [(w, r) for w, r in _sibling_requirements()],
    ids=[f"{w}:{r.name}" for w, r in _sibling_requirements()],
)
def test_sibling_upper_bound_is_one_zero(where: str, req: Requirement):
    """`>=<floor>,<1.0` — one floor, one ceiling, and the ceiling is 1.0."""
    uppers = [s for s in req.specifier if s.operator in ("<", "<=")]
    exacts = [s for s in req.specifier if s.operator in ("==", "===", "~=")]

    assert not exacts, (
        f"{where}: '{req}' pins {req.name} to an exact version. {RULING}"
    )
    assert len(uppers) == 1, (
        f"{where}: '{req}' declares {len(uppers)} upper bounds on {req.name}; "
        f"exactly one, `<1.0`, is the policy. {RULING}"
    )

    bound = uppers[0]
    assert bound.operator == "<" and Version(bound.version) == Version("1.0"), (
        f"{where}: '{req}' caps {req.name} at `{bound}`, tighter than the "
        f"policy's `<1.0`. {RULING}"
    )


@pytest.mark.parametrize(
    "where,req",
    [(w, r) for w, r in _sibling_requirements()],
    ids=[f"{w}:{r.name}" for w, r in _sibling_requirements()],
)
def test_sibling_has_a_floor(where: str, req: Requirement):
    """The floor is the half of the range that still carries information.

    Widening the ceiling does not make the range meaningless: a floor says
    which sibling release first held the surface this composite mounts, and
    the comments beside each line in `pyproject.toml` are the argument for it.
    An unbounded-below `<1.0` would let a resolver answer with 0.1.
    """
    floors = [s for s in req.specifier if s.operator in (">=", ">")]
    assert len(floors) == 1, (
        f"{where}: '{req}' declares {len(floors)} lower bounds on {req.name}; "
        "a sibling range is exactly one floor and `<1.0`."
    )
