"""Per-module contract triad + capabilities + drift gate (contract-pipeline.md §2-3).

Until 0.2.0 this module served no HTTP and owned no state, so it had no triad
at all and ``docs/capabilities.json`` was hand-authored — which was honest for
a package whose whole content was INSTALLED_APPS and a settings dict. It now
serves ``/classified/api/v1`` (the conversation↔listing join no member is
allowed to hold), so it emits what every other module emits, from a
single-module ``{classified + core}`` instance mounted at the canonical
prefix.

A composite's schema is its OWN surface, never the union of its members' —
each member emits its own, and this file asserts the boundary rather than
trusting it.

stapel-classified is not mounted in stapel-example-monolith, so there is no
aggregate slice to diff against for byte-identity; standalone validation
(contract-pipeline.md §9 fallback) substitutes.

Regenerate after any change to a serializer / view / url / error key / axis::

    make contract

then commit ``docs/{schema,flows,errors,capabilities,llms.txt}`` and README.md.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

_PY = sys.version_info[:2]
if _PY != (3, 12):
    _GOT = f"{_PY[0]}.{_PY[1]}"
    pytest.skip(
        "stapel-classified contract tests require Python 3.12 (the CI pin) — "
        f"running {_GOT}. drf-spectacular renders component descriptions "
        "(Optional[X] vs X | None) differently across Python minors, so a "
        "drift check emitted under any other one produces false diffs.",
        allow_module_level=True,
    )

try:
    import stapel_tools  # noqa: F401  (probe: the emitter must be importable)
except ImportError as exc:  # pragma: no cover - environment failure, not a branch
    # NOT pytest.importorskip. A drift gate that skips when its emitter is
    # missing reports `1 skipped`, exits 0, and disappears among a hundred
    # green tests — making "the tool is absent" indistinguishable from "there
    # is no drift". A gate that cannot run has FAILED; it has not passed.
    raise RuntimeError(
        "the contract drift gate cannot run: stapel-tools is not importable, "
        "and it carries the emitters this gate measures drift against. CI "
        "installs it; locally use the workspace venv. This is a hard failure "
        "on purpose — a skipped drift gate is silently no gate."
    ) from exc

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs"
TRIAD = ("schema.json", "flows.json", "errors.json")
ARTIFACTS = TRIAD + ("capabilities.json", "llms.txt")


def _emit(out_dir: Path) -> None:
    for module in ("stapel_classified._codegen", "stapel_classified._capabilities"):
        subprocess.run(
            [sys.executable, "-m", module, "--out", str(out_dir)],
            cwd=str(REPO),
            check=True,
            capture_output=True,
        )
    # llms.txt renders from the REAL committed docs/capabilities.json (same as
    # `make contract-check`), so this step also catches a stale llms.txt
    # independently of the loop above.
    subprocess.run(
        [sys.executable, "-m", "stapel_tools.llms_txt", ".", "--out", str(out_dir)],
        cwd=str(REPO),
        check=True,
        capture_output=True,
    )


def test_contract_artifacts_committed():
    for name in ARTIFACTS:
        assert (DOCS / name).is_file(), f"missing docs/{name} — run `make contract`"
    assert (DOCS / "capabilities.meta.json").is_file(), (
        "missing docs/capabilities.meta.json — the curated layer is "
        "hand-written and committed, not generated"
    )


def test_contract_has_no_drift(tmp_path):
    _emit(tmp_path)
    for name in ARTIFACTS:
        assert (DOCS / name).read_bytes() == (tmp_path / name).read_bytes(), (
            f"docs/{name} drifted — run `make contract` and commit docs/{name}"
        )


def test_emission_is_deterministic(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    _emit(a)
    _emit(b)
    for name in ARTIFACTS:
        assert (a / name).read_bytes() == (b / name).read_bytes()


def test_paths_carry_canonical_prefix():
    schema = json.loads((DOCS / "schema.json").read_text())
    assert schema["paths"], "schema has no paths"
    assert all(p.startswith("/classified/api/v1/") for p in schema["paths"])


def test_the_schema_is_this_package_and_not_the_composite():
    """The boundary a composite is easiest to get wrong.

    Emitting the whole preset here would put stapel-listings' endpoints in
    stapel-classified's contract, and a client generated from it would call
    the catalogue through the wrong package's version number.
    """
    schema = json.loads((DOCS / "schema.json").read_text())
    assert set(schema["paths"]) == {
        "/classified/api/v1/conversations",
        "/classified/api/v1/conversations/contexts",
        "/classified/api/v1/conversations/{conversation_id}",
    }


def test_every_operation_is_authenticated():
    """There is no public route here. A conversation header names two people
    and what they are trading; the closest thing to a public read in this
    domain is the listing page, which is stapel-listings' to serve."""
    schema = json.loads((DOCS / "schema.json").read_text())
    missing = []
    for path, operations in schema["paths"].items():
        for method, op in operations.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            security = op.get("security") or []
            if not any("JWTCookieAuth" in entry for entry in security):
                missing.append(f"{method.upper()} {path}")
    assert not missing, f"operations missing JWTCookieAuth security: {missing}"


def test_flows_are_empty_no_flow_step_annotations():
    flows = json.loads((DOCS / "flows.json").read_text())
    assert flows == [], (
        "docs/flows.json is non-empty but no @flow_step annotation exists in "
        "stapel_classified — investigate before assuming [] is still correct"
    )


def _all_refs(obj) -> set:
    return set(re.findall(r'"#/components/schemas/([^"]+)"', json.dumps(obj)))


def test_schema_refs_are_self_contained():
    schema = json.loads((DOCS / "schema.json").read_text())
    comps = schema.get("components", {}).get("schemas", {})
    seen: set = set()
    stack = list(_all_refs(schema["paths"]))
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        if name in comps:
            stack.extend(_all_refs(comps[name]))
    dangling = seen - set(comps)
    assert not dangling, f"dangling $ref(s) with no component definition: {dangling}"


def test_the_card_is_typed_field_by_field():
    """The frontend contract is only as good as the schema behind it: a card
    emitted as a free-form object would make ``docs/frontend-contract.md`` the
    only description of it, and prose is not a type."""
    comps = json.loads((DOCS / "schema.json").read_text())["components"]["schemas"]
    for name in ("ListingCardDTO", "SellerCardDTO", "CardImageDTO", "SubjectDTO"):
        assert name in comps, f"{name} is missing from the emitted components"
    listing = comps["ListingCardDTO"]["properties"]
    assert {"state", "status", "price", "currency", "image", "images"} <= set(listing)
    # The gallery is typed as a LIST OF THE SAME image, not as a free-form
    # array: a client that renders `image` must be able to render every frame
    # of `images` with the identical renderer, and that is what makes the two
    # keys one answer instead of two.
    assert listing["images"]["type"] == "array"
    assert listing["images"]["items"]["$ref"].endswith("/CardImageDTO")


def test_errors_json_describes_this_library_not_this_machine():
    """The emitted key set must not depend on what else the venv has.

    The error registry is process-global, so every imported app's keys land in
    it; an emission that copied them out would produce a different artifact on
    a workspace machine than on a clean runner — and a drift gate that fails
    for a reason nobody changed. stapel-notifications died in its publish job
    twice on exactly this, which is where `_codegen.scoped_error_registry`
    comes from.
    """
    from stapel_classified._codegen import OWNED_ERROR_PACKAGES

    keys = json.loads((DOCS / "errors.json").read_text())
    owners = {k.get("owner") for k in keys}
    assert owners <= set(OWNED_ERROR_PACKAGES) | {None}, sorted(
        o for o in owners if o and o not in OWNED_ERROR_PACKAGES
    )
    # …and this module's own keys really are in there.
    codes = {k["code"] for k in keys}
    assert "error.503.classified_chat_unavailable" in codes


# --- capabilities.json content sanity (capability-config.md §2) ---------------


def _capabilities() -> dict:
    return json.loads((DOCS / "capabilities.json").read_text())


def test_capabilities_axes_are_the_settings_that_change_the_deal():
    """Three axes, and each changes what the product does to people: who
    answers who is in a conversation, how much of a seller the card may show,
    and whether sellers carry a rating. Batch limits, timeouts and image tiers
    are tuning and deliberately absent — and so is block enforcement, which is
    stapel-chat's axis and appears in stapel-chat's capabilities (0.4.0)."""
    axes = {a["key"]: a for a in _capabilities()["axes"]}
    assert set(axes) == {
        "CONVERSATION_PARTICIPANTS_FUNCTION",
        "PUBLIC_PROFILE_FUNCTION",
        "SELLER_RATING_TARGET_TYPE",
    }
    for axis in axes.values():
        # Behavioral, not gating: they change behavior, never which
        # operations exist.
        assert axis["gates"]["operations"] == []
        assert axis["curated"]["business_label"]


def test_the_block_posture_is_published_on_the_one_axis_that_owns_it():
    """A capabilities document is what a reader trusts about a deployment's
    posture. Two documents each claiming an axis for the same fact is worse
    than one: it is how an operator sets the switch nothing reads."""
    from stapel_classified import preset

    axes = {a["key"]: a for a in _capabilities()["axes"]}
    assert not [key for key in axes if key.startswith("BLOCK_")]
    assert preset.SETTINGS_DEFAULTS["STAPEL_CHAT"]["BLOCK_ENFORCEMENT"] == "required"
    assert axes["PUBLIC_PROFILE_FUNCTION"]["default"] == "profiles.public_cards"


def test_version_tracks_pyproject():
    import tomllib

    pyproject = tomllib.loads((REPO / "pyproject.toml").read_text())
    assert _capabilities()["version"] == pyproject["project"]["version"]


# --- README.md — the sixth artifact (tracker #257) ---------------------------


def test_readme_is_assembled_and_has_no_drift():
    from stapel_tools.readme import load_inputs as readme_load_inputs
    from stapel_tools.readme import render as readme_render
    from stapel_tools.readme import static_languages

    inputs = readme_load_inputs(REPO)
    languages = static_languages(REPO)
    assert languages == ["en"], "expected exactly the English static body docs/readme.md"
    assert (REPO / "README.md").read_text() == readme_render(
        REPO, inputs, "en", languages
    ), (
        "README.md drifted — run `make contract` and commit README.md "
        "(edit prose in docs/readme.md, never README.md itself)"
    )
