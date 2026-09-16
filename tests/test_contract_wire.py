"""Every response body the contract declares is a body the views actually send.

``docs/schema.json`` is emitted from the views' ``@extend_schema``
annotations, and an annotation is a CLAIM: it says what the view returns, and
the generator has no way to check it against the method body.
``tests/test_contract.py`` compares the committed document against a FRESH
EMISSION of the same annotations — it proves the file is not stale, and
nothing else, because both sides come from the claim. stapel-alerts 0.2.0
shipped ``GET /issues`` declared as ``Issue[]`` while the wire carried
``{count, offset, limit, results}``: the drift gate was green and the
frontend pair rendered ``undefined``.

This is the gate the generator cannot be: it performs every operation the
committed schema declares with a JSON response body, and validates the body
it gets against the schema it was promised. It is worth more in a COMPOSITE
than anywhere else: not one field of these bodies comes from a row this
package owns. The card is assembled in ``cards.py`` out of what
``listings.search_documents``, ``cdn.describe_many``,
``chat.conversation_participants`` and ``profiles.*`` answered, as plain
dicts, and the dataclass DTO the contract is generated from is a separate
statement about the same shape. Nothing but this file compares the two.

Rules this file holds itself to:

* an operation with a declared JSON response and no entry in ``RECIPES``
  FAILS LOUDLY — a gate that quietly covers three of four rows is the family
  of green that proves nothing;
* a path parameter the gate cannot fill fails at the point of substitution,
  naming the operation;
* the operations that genuinely cannot be driven in-process are listed by
  name in ``UNDRIVABLE`` with a one-line reason each. That list is asserted
  to be exactly current: a stale entry, or a missing reason, fails;
* a collection that comes back empty fails in the populated pass — an empty
  array validates against any item schema and an empty map against any
  ``additionalProperties``, so an empty answer is a check that looked at
  nothing. Here that is asserted down a DOTTED PATH
  (``subject.listing.images``), because every interesting collection in this
  contract is nested two levels inside the body;
* every operation is driven a SECOND time in its emptiest legal state
  (``EMPTY_STATE``): a listing with no gallery and no price, a counterparty
  with no profile row, a batch whose ids are all strangers'. Every null
  finding in the first wave of this gate was there.

Nothing here is mocked across a seam. The listing goes through
``publish_listing`` and a real moderation verdict, the thread is a real
stapel-chat direct conversation, the counterparty is a real stapel-profiles
row. The one double is ``cdn.describe_many``, which is a comm Function no
module in this harness serves — the same stand-in the suite's own
``cdn_double`` fixture is, and the card's ``cdn_unavailable`` branch is
driven without it.

Runs on every interpreter: it reads the committed schema and never emits.

THE MOUNT. ``codegen_urls.py`` mounts ``classified/api/`` →
``stapel_classified.urls``, which contributes ``v1/``. ``tests/urls.py``
mounts the whole preset, whose first entry is the identical
``("classified/api/", "stapel_classified.urls")`` — so this module's suite
has always been looking where the document points, unlike five of the first
eight libraries in this wave. The emission mount is declared here rather than
borrowed, so ``test_every_declared_path_resolves_under_this_urlconf`` fails
at the one moment it is cheap to fix: when somebody changes a mount.

What it found on its first run: 3 of 3 operations driven, 0 red. The claims
this module makes about its own wire are honest in both states, including
every ``nullable`` one — ``counterparty`` absent, ``rating`` absent,
``price`` null, ``image`` null with ``images`` empty, ``meta_reason`` null on
an undegraded card. ``test_the_gate_is_not_blind`` proves that is a finding
rather than a gate that never looked: it re-validates every driven body
against ``{"type": "string"}`` and requires all of them to fail.
"""
import copy
import json
import re
import uuid
from decimal import Decimal
from pathlib import Path

import jsonschema
import pytest
from django.test import override_settings
from django.urls import include, path as url_path
from rest_framework.test import APIClient

REPO = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((REPO / "docs" / "schema.json").read_text())

#: The mount the contract is emitted at, reproduced for the test client
#: (``codegen_urls.py``: ``classified/api/`` → ``stapel_classified.urls``,
#: which contributes ``v1/``).
urlpatterns = [
    url_path("classified/api/", include("stapel_classified.urls")),
]

pytestmark = [pytest.mark.django_db, pytest.mark.urls(__name__)]

V1 = "/classified/api/v1"

#: An opaque CDN ref, the shape ``Listing.images`` stores (``<type>/<hash>``).
IMAGE_REF = "product/wire-contract-1"


@pytest.fixture(autouse=True)
def _media_root(tmp_path):
    """Nothing here writes files today; pin the root so nothing ever does.

    ``MEDIA_ROOT`` is unset in this harness's settings, so it defaults to the
    working directory — in stapel-auth that put a data export into the
    checkout, where under a flat package layout a stray directory also
    shadowed a real submodule.
    """
    with override_settings(MEDIA_ROOT=str(tmp_path)):
        yield


# ─────────────────────────────────────────────────────────────────────────────
# The contract side: what the document declares
# ─────────────────────────────────────────────────────────────────────────────


def _json_schema(node):
    """OpenAPI 3.0 → JSON Schema, for the divergence that matters here.

    OAS 3.0 spells "may be null" as ``nullable: true`` beside a ``type`` — or
    beside an ``allOf`` wrapping a ``$ref``, which is how ``subject``,
    ``counterparty``, ``listing``, ``image`` and ``rating`` are all emitted.
    JSON Schema has no such keyword and would refuse the null, which is the
    value every one of those answers in the state this gate most wants to
    ask about. Everything else drf-spectacular emits here (``$ref``,
    ``required``, ``additionalProperties``) is JSON Schema as written.
    """
    if isinstance(node, list):
        return [_json_schema(item) for item in node]
    if not isinstance(node, dict):
        return node
    rebuilt = {k: _json_schema(v) for k, v in node.items() if k != "nullable"}
    if node.get("nullable"):
        return {"anyOf": [rebuilt, {"type": "null"}]}
    return rebuilt


def _validator(response_schema):
    root = copy.deepcopy(response_schema)
    root["components"] = copy.deepcopy(SCHEMA["components"])
    return jsonschema.Draft202012Validator(_json_schema(root))


def _operations():
    """Every ``(method, path, 2xx code, JSON body schema)`` the contract declares."""
    ops = []
    for path, methods in SCHEMA["paths"].items():
        for method, op in methods.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            for code, response in op.get("responses", {}).items():
                body = (
                    response.get("content", {})
                    .get("application/json", {})
                    .get("schema")
                )
                if body is not None and code.startswith("2"):
                    ops.append((method.upper(), path, int(code), body))
    return sorted(ops, key=lambda o: (o[1], o[0], o[2]))


OPERATIONS = _operations()


# ─────────────────────────────────────────────────────────────────────────────
# The wire side: harness — real rows in real member modules
# ─────────────────────────────────────────────────────────────────────────────


def _unique(prefix):
    return f"{prefix}{uuid.uuid4().hex[:10]}"


def make_user():
    from django.contrib.auth import get_user_model

    return get_user_model().objects.create(
        username=_unique("wire_"), email=f"{_unique('wire-')}@example.com"
    )


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def category_tree():
    """``electronics > phones`` with one string feature on the ancestor.

    The feature sits on the parent on purpose — that is what a published
    listing's ``features_draft`` is validated against.
    """
    from stapel_categories.models import Category, CategoryFeature, Feature

    root = Category.objects.create(name="Electronics", slug=_unique("electronics-"))
    leaf = Category.objects.create(name="Phones", slug=_unique("phones-"), tn_parent=root)
    brand = Feature.objects.create(
        slug=_unique("brand-"), name="Brand", config={"type": "string"}
    )
    CategoryFeature.objects.create(category=root, feature=brand, order=0)
    return leaf, brand.slug


def published_listing(owner, *, images=(), price=Decimal("500.00")):
    """A listing all the way to PUBLISHED, through the real pipeline.

    Publishing requests moderation and the verdict is what promotes it, so
    the fixture goes through both rather than assigning ``status`` behind
    the module's back.
    """
    from stapel_listings.models import Listing
    from stapel_listings.services.publish import publish_listing

    leaf, brand = category_tree()
    listing = Listing.objects.create(
        owner=owner,
        category_id=str(leaf.pk),
        language="en",
        currency="USD",
        title_draft="Apple iPhone 13 Pro",
        description_draft="An excellent phone in mint condition.",
        price_draft=price,
        lat_draft=Decimal("49.611600"),
        lon_draft=Decimal("6.131900"),
        geohash_draft="u0ubw2mtzz",
        location_label_draft="Luxembourg",
        features_draft={brand: {"type": "string", "value": "apple"}},
        images_draft=list(images),
    )
    publish_listing(listing)
    listing.apply_moderation("approved")
    listing.refresh_from_db()
    return listing


def thread_about(buyer, seller, listing):
    """A real stapel-chat direct conversation carrying the listing subject."""
    from stapel_chat.services import create_direct

    return create_direct(
        owner=buyer,
        other_user_id=seller.pk,
        scope_key="",
        subject_type="listing",
        subject_key=str(listing.pk),
    )


def give_display_name(user, name):
    """A real stapel-profiles row — the module serves the Function itself."""
    from stapel_profiles.models import get_profile_model

    profile, _ = get_profile_model().objects.get_or_create(user_id=user.pk)
    profile.display_name = name
    profile.save(update_fields=["display_name"])
    return profile


def describe_images(**snapshot):
    """Register a ``cdn.describe_many`` provider for the rest of the test.

    No module in this harness serves it, so without this the card takes its
    ``cdn_unavailable`` branch — which the empty-state recipes drive on
    purpose. The suite's own ``_reset_comm_functions`` fixture restores the
    registry afterwards.

    A name has exactly one provider, and ``test_the_gate_is_not_blind``
    re-drives every recipe inside a single test — so a previous registration
    is stood down rather than collided with.
    """
    from stapel_core.comm import function
    from stapel_core.comm.registry import function_registry

    function_registry._providers.pop("cdn.describe_many", None)

    @function("cdn.describe_many")
    def _describe(payload):
        refs = payload.get("refs") or []
        return {"items": {ref: dict(snapshot) for ref in refs}, "missing": []}

    return _describe


def full_snapshot():
    """Every optional ``CardImageDTO`` field carrying a real value.

    The declared shape is nullable top to bottom, so a populated pass that
    leaves them null has looked at the null branch twice and the other one
    never.
    """
    return dict(
        mime="image/jpeg",
        ext="jpg",
        bytes=204800,
        width=1200,
        height=900,
        aspect=1.3333,
        square=False,
        animated=False,
        preview_b64="AAAA",
        preview_kind="blurhash",
        variants=[{"name": "thumb", "width": 320}],
        meta_status="ok",
        meta_reason=None,
    )


# ─────────────────────────────────────────────────────────────────────────────
# The recipe table
# ─────────────────────────────────────────────────────────────────────────────


class Call:
    """Performs one declared operation, and refuses to guess a path parameter."""

    def __init__(self, method, path):
        self.method = method
        self.path = path

    def __call__(self, client, params=None, data=None, query="", **extra):
        url = self.path
        for name, value in (params or {}).items():
            url = url.replace("{%s}" % name, str(value))
        assert "{" not in url, (
            f"{self.method} {self.path}: a path parameter this gate does not "
            "know how to fill — teach its recipe, or the operation goes unchecked"
        )
        send = getattr(client, self.method.lower())
        if self.method in ("GET", "DELETE"):
            return send(url + query, **extra)
        return send(url + query, data if data is not None else {}, format="json", **extra)


#: How to perform each operation the contract declares with a JSON response
#: body, keyed by ``(METHOD, path template)``. A recipe returns the response it
#: produced, or a list of ``(label, response)`` pairs when one operation has
#: more than one answering state worth asking.
RECIPES = {}

#: The same operations again, in the emptiest state the contract still has to
#: describe: no gallery, no price, no profile row, no rating, and a batch
#: whose ids belong to somebody else.
EMPTY_STATE = {}


def recipe(method, path, table=None):
    def register(fn):
        target = RECIPES if table is None else table
        key = (method, V1 + path)
        assert key not in target, f"duplicate recipe for {method} {path}"
        target[key] = fn
        return fn

    return register


def empty_state(method, path):
    return recipe(method, path, table=EMPTY_STATE)


#: Operations that cannot be driven in-process, by name and with the reason.
#: A short, visible list is acceptable here; a silent skip is not.
#:
#: EMPTY. Every member this surface reads through is installed in this
#: harness and answers for real; the one Function nothing serves
#: (``cdn.describe_many``) is a declared seam, wired here the way a
#: deployment wires it.
UNDRIVABLE: dict = {}

#: Collections that must actually carry a row in the populated pass, named by
#: DOTTED PATH because every one of them is nested inside the body. An empty
#: array validates against any item schema and an empty map against any
#: ``additionalProperties``, so a populated run that leaves one empty looked
#: at nothing at all.
POPULATED_COLLECTIONS = {
    ("POST", V1 + "/conversations"): ("subject.listing.images",),
    ("GET", V1 + "/conversations/{conversation_id}"): ("subject.listing.images",),
    ("POST", V1 + "/conversations/contexts"): ("items", "missing"),
}


def _dig(body, dotted):
    node = body
    for part in dotted.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


# ── confirming a contact ─────────────────────────────────────────────────────


@recipe("POST", "/conversations")
def _confirm(call):
    buyer, seller = make_user(), make_user()
    give_display_name(seller, "Ada Lovelace")
    listing = published_listing(seller, images=[IMAGE_REF])
    conversation = thread_about(buyer, seller, listing)
    describe_images(**full_snapshot())
    return call(
        client_for(buyer),
        data={"conversation_id": str(conversation.id), "listing_id": str(listing.pk)},
    )


@empty_state("POST", "/conversations")
def _confirm_empty(call):
    """A listing with no gallery and no price, a seller with no profile row.

    ``image`` is null, ``images`` is empty, ``price`` is null, the seller
    card comes back ``partial`` with no ``rating`` and no ``member_since`` —
    the five nullable claims of this shape, all at once.
    """
    buyer, seller = make_user(), make_user()
    listing = published_listing(seller, images=[], price=None)
    conversation = thread_about(buyer, seller, listing)
    return call(
        client_for(buyer),
        data={"conversation_id": str(conversation.id), "listing_id": str(listing.pk)},
    )


# ── one conversation's header ────────────────────────────────────────────────


@recipe("GET", "/conversations/{conversation_id}")
def _context(call):
    """The same thread read from both ends: the buyer's header names the
    seller as the counterparty, the seller's names the buyer."""
    buyer, seller = make_user(), make_user()
    give_display_name(seller, "Ada Lovelace")
    give_display_name(buyer, "Grace Hopper")
    listing = published_listing(seller, images=[IMAGE_REF])
    conversation = thread_about(buyer, seller, listing)
    describe_images(**full_snapshot())
    return [
        (
            "the buyer's reading",
            call(client_for(buyer), params={"conversation_id": conversation.id}),
        ),
        (
            "the seller's reading",
            call(client_for(seller), params={"conversation_id": conversation.id}),
        ),
    ]


@empty_state("GET", "/conversations/{conversation_id}")
def _context_empty(call):
    """Two kinds of empty: a bare listing with no CDN behind it (every image
    field null, ``meta_reason`` naming why), and a listing that is GONE —
    the state a card exists to express and a public read cannot."""
    buyer, seller = make_user(), make_user()
    bare = published_listing(seller, images=[IMAGE_REF], price=None)
    bare_thread = thread_about(buyer, seller, bare)

    removed = published_listing(seller, images=[])
    removed_thread = thread_about(buyer, seller, removed)
    removed.delete()  # soft delete — the row stays, the document stops

    client = client_for(buyer)
    return [
        (
            "no CDN behind the gallery",
            call(client, params={"conversation_id": bare_thread.id}),
        ),
        (
            "the listing is gone",
            call(client, params={"conversation_id": removed_thread.id}),
        ),
    ]


# ── the inbox batch ──────────────────────────────────────────────────────────


@recipe("POST", "/conversations/contexts")
def _contexts(call):
    """One page of an inbox: two threads the caller is in, plus an id that is
    somebody else's — which comes back under ``missing`` rather than as a
    403, because a 403 would confirm the id names a real thread."""
    buyer, seller = make_user(), make_user()
    give_display_name(seller, "Ada Lovelace")
    first = published_listing(seller, images=[IMAGE_REF])
    second = published_listing(seller, images=[IMAGE_REF])
    mine = [
        thread_about(buyer, seller, first).id,
        thread_about(buyer, seller, second).id,
    ]
    stranger = make_user()
    theirs = thread_about(stranger, seller, published_listing(seller)).id
    describe_images(**full_snapshot())
    return call(
        client_for(buyer),
        data={"conversation_ids": [str(cid) for cid in [*mine, theirs]]},
    )


@empty_state("POST", "/conversations/contexts")
def _contexts_empty(call):
    """Two kinds of empty: a page of ids that are all strangers' (``items``
    is ``{}`` and every id is ``missing``), and a page holding exactly one
    row that itself carries nothing optional — an empty map says nothing
    about the value schema, so the second branch is where the check lands."""
    buyer, seller = make_user(), make_user()
    stranger = make_user()
    theirs = thread_about(stranger, seller, published_listing(seller)).id

    bare = published_listing(seller, images=[], price=None)
    mine = thread_about(buyer, seller, bare).id

    client = client_for(buyer)
    return [
        ("every id is somebody else's", call(client, data={"conversation_ids": [str(theirs)]})),
        ("one row carrying nothing optional",
         call(client, data={"conversation_ids": [str(mine)]})),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# The gate
# ─────────────────────────────────────────────────────────────────────────────


#: Operations whose declared body the wire does not send, with the defect and
#: its owner. ``strict=True``: a fixed entry fails until it is deleted, so a
#: finding can be neither forgotten nor quietly kept.
#:
#: EMPTY, and that is the finding rather than the absence of one: 3 of 3
#: operations answer the shape they declare, in both states. The mechanism
#: stays because the next wave will need it.
KNOWN_MISMATCHES: dict = {}


def test_the_contract_declares_something_to_check():
    assert OPERATIONS, "docs/schema.json declares no JSON responses at all"


def test_every_declared_path_resolves_under_this_urlconf():
    """The suite must be looking where the document describes.

    Five of the first eight libraries this gate was written for had a
    committed contract that nothing had ever driven, because the test urlconf
    mounted somewhere the document does not describe: one mounted a different
    prefix AND one segment short, one mounted the paths bare, one mounted a
    doubled segment, one mounted less than the emission did. In every case
    the operations were "covered" by a file that could not have reached a
    single one of them.

    Classified is not one of them — ``tests/urls.py`` mounts the preset,
    whose first entry is the same ``classified/api/`` prefix
    ``codegen_urls.py`` uses — and this assertion is what keeps saying so. A
    missing recipe already fails loudly; this fails when the MOUNT is wrong,
    which no per-operation check can see, because when the mount is wrong
    every operation is equally and silently unreachable.
    """
    from django.urls import Resolver404, resolve

    # Resolution cares about the SHAPE of a segment, and a urlconf may use
    # several converters — uuid, int, slug. A path counts as reachable if any
    # one shape resolves: the question here is whether the mount exists, not
    # whether a particular id does.
    candidates = (
        "00000000-0000-4000-8000-000000000000",
        "1",
        "a-slug",
    )

    unreachable = []
    for _method, path, _code, _schema in OPERATIONS:
        for value in candidates:
            try:
                resolve(re.sub(r"\{[^}]+\}", value, path))
                break
            except Resolver404:
                continue
        else:
            unreachable.append(path)

    assert not unreachable, (
        "these declared paths do not resolve under this module's urlconf, so "
        "nothing here can be driving them — the mount is wrong, not the "
        "recipes:\n  " + "\n  ".join(sorted(set(unreachable)))
    )


def test_every_declared_operation_is_driven_or_named_undrivable():
    """No operation is covered by silence, and no entry outlives its operation."""
    declared = {(method, path) for method, path, _code, _schema in OPERATIONS}
    covered = set(RECIPES) | set(UNDRIVABLE)

    missing = sorted(declared - covered)
    assert not missing, (
        "operations with a declared JSON response body and no recipe:\n"
        + "\n".join(f"  {m} {p}" for m, p in missing)
    )
    stale = sorted(covered - declared)
    assert not stale, (
        "recipes/exclusions for operations the contract no longer declares:\n"
        + "\n".join(f"  {m} {p}" for m, p in stale)
    )
    both = sorted(set(RECIPES) & set(UNDRIVABLE))
    assert not both, f"driven AND excluded: {both}"
    for key, reason in UNDRIVABLE.items():
        assert reason and reason.strip(), f"{key} is excluded with no reason"

    stale_collections = sorted(set(POPULATED_COLLECTIONS) - declared)
    assert not stale_collections, (
        f"nested-collection expectations for undeclared operations: {stale_collections}"
    )


def test_every_operation_is_also_driven_in_its_emptiest_state():
    """A populated answer cannot say what a field holds when there is nothing.

    Every null finding in the first wave of this gate was on the empty state.
    Every operation here answers the same header shape, and every nullable
    claim in it is null exactly when a listing has no gallery, no price and
    its seller no profile — so all three are required to have an empty-state
    recipe, not only the read.
    """
    declared = {(m, p) for m, p, _c, _s in OPERATIONS}
    missing = sorted(declared - set(EMPTY_STATE))
    assert not missing, (
        "operations driven only against a populated database — the state "
        "where every null claim in this gate's history was found is "
        "unchecked:\n" + "\n".join(f"  {m} {p}" for m, p in missing)
    )
    stale = sorted(set(EMPTY_STATE) - declared)
    assert not stale, f"empty-state recipes for undeclared operations: {stale}"


def test_every_known_mismatch_is_still_declared_and_explained():
    """A recorded defect must name a live operation and carry its reason.

    Without this, an operation that is renamed or removed leaves an entry that
    silences nothing and reads like a known problem forever.
    """
    declared = {(method, path) for method, path, _code, _schema in OPERATIONS}
    for key, reason in KNOWN_MISMATCHES.items():
        assert key in declared, (
            f"{key} is recorded as a known mismatch but the contract no longer "
            "declares it — delete the entry"
        )
        assert reason and reason.strip(), f"{key} is recorded with no reason"


def _labelled(result):
    """A recipe answers with one response, or with labelled branches."""
    if isinstance(result, list):
        return result
    return [("", result)]


def _drive(table, method, path, code, body_schema, *, expect_rows):
    perform = table.get((method, path))
    assert perform is not None, (
        f"{method} {path} declares a response body and has no recipe — an "
        "unchecked operation is a schema nobody proves. Teach RECIPES, or "
        "name it in UNDRIVABLE with a reason."
    )

    for label, response in _labelled(perform(Call(method, path))):
        where = f"{method} {path}" + (f" [{label}]" if label else "")
        assert response.status_code == code, (
            f"{where}: expected the declared {code}, got "
            f"{response.status_code}: {response.content[:400]}"
        )

        body = response.json()
        errors = sorted(
            _validator(body_schema).iter_errors(body), key=lambda e: list(e.path)
        )
        assert not errors, (
            f"{where} answers a body the contract does not describe:\n"
            + "\n".join(f"  at {list(e.path) or '<root>'}: {e.message}" for e in errors[:10])
            + f"\n  body: {json.dumps(body)[:600]}"
        )

        # An empty list validates against any item schema, and an empty map
        # against any additionalProperties, so a collection must actually
        # carry a row for the check to have looked at anything.
        if expect_rows:
            if isinstance(body, list):
                assert body, f"{where}: the declared list came back empty"
            for dotted in POPULATED_COLLECTIONS.get((method, path), ()):
                assert _dig(body, dotted), (
                    f"{where}: the declared collection {dotted!r} came back "
                    "empty, so nothing in it was checked"
                )


@pytest.mark.parametrize(
    "method,path,code,body_schema",
    OPERATIONS,
    ids=[f"{m} {p}" for m, p, _c, _s in OPERATIONS],
)
def test_the_wire_matches_the_declared_response(method, path, code, body_schema, request):
    if (method, path) in UNDRIVABLE:
        pytest.skip(f"excluded by name: {UNDRIVABLE[(method, path)]}")

    if (method, path) in KNOWN_MISMATCHES:
        request.node.add_marker(
            pytest.mark.xfail(
                strict=True,
                reason=f"{method} {path}: {KNOWN_MISMATCHES[(method, path)]}",
            )
        )

    _drive(RECIPES, method, path, code, body_schema, expect_rows=True)


_EMPTY_OPERATIONS = [
    (method, path, code, schema)
    for method, path, code, schema in OPERATIONS
    if (method, path) in EMPTY_STATE
]


@pytest.mark.parametrize(
    "method,path,code,body_schema",
    _EMPTY_OPERATIONS,
    ids=[f"{m} {p}" for m, p, _c, _s in _EMPTY_OPERATIONS],
)
def test_the_wire_matches_the_declared_response_when_there_is_nothing_there(
    method, path, code, body_schema, request
):
    """The same claim, asked in the state where the nulls live."""
    if (method, path) in KNOWN_MISMATCHES:
        request.node.add_marker(
            pytest.mark.xfail(
                strict=True,
                reason=f"{method} {path}: {KNOWN_MISMATCHES[(method, path)]}",
            )
        )

    _drive(EMPTY_STATE, method, path, code, body_schema, expect_rows=False)


def test_the_gate_is_not_blind():
    """A canary: swap a declared schema for one the wire cannot satisfy.

    Everything above can be green for two reasons — the claims are honest, or
    the check never looks at the body. This tells them apart by validating a
    real response against ``{"type": "string"}``: every operation here answers
    an object, so every one of them must fail. If any passes, the validation
    in ``_drive`` is not reaching the received body and this whole file proves
    nothing. With ``KNOWN_MISMATCHES`` empty this covers the entire declared
    surface.
    """
    honest = [
        (method, path, code)
        for method, path, code, _schema in OPERATIONS
        if (method, path) not in KNOWN_MISMATCHES and (method, path) not in UNDRIVABLE
    ]
    assert honest, "nothing left to canary"

    survivors = []
    for method, path, code in honest:
        try:
            _drive(RECIPES, method, path, code, {"type": "string"}, expect_rows=False)
        except AssertionError:
            continue
        survivors.append(f"{method} {path}")
    assert not survivors, (
        "these operations passed validation against {'type': 'string'} — the "
        "gate is not looking at the body it received:\n  " + "\n  ".join(survivors)
    )
