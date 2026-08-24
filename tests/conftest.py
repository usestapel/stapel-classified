"""Fixtures shared by the composite's integration tests.

Everything here builds real rows in real member modules and moves them
through their real services. A composite's only claim is that the members
meet correctly, and a mock on either side of a seam is exactly the thing
that cannot prove it (integration-seam defects: every fleet bug so far has
been a divergence at a seam whose two halves were green in isolation).
"""
from decimal import Decimal

import pytest


@pytest.fixture(autouse=True)
def _reset_registries():
    """Clear per-process caches the modules keep across tests."""
    from stapel_search import facets

    facets.reset_path_degradation()
    yield


@pytest.fixture
def user(db):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.create(username="seller", email="seller@example.com")


@pytest.fixture
def other_user(db):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.create(username="buyer", email="buyer@example.com")


@pytest.fixture
def category_tree(db):
    """``electronics > phones`` with one string feature on the parent.

    The feature sits on the ancestor on purpose: it exercises inheritance in
    ``categories.features`` and it is what the facet plan is built from.
    """
    from stapel_categories.models import Category, CategoryFeature, Feature

    root = Category.objects.create(name="Electronics", slug="electronics")
    leaf = Category.objects.create(name="Phones", slug="phones", tn_parent=root)
    brand = Feature.objects.create(
        slug="brand", name="Brand", config={"type": "string"}
    )
    CategoryFeature.objects.create(category=root, feature=brand, order=0)
    return root, leaf


@pytest.fixture
def make_listing(db, user, category_tree):
    """Build a draft listing in the leaf category. Publishing is the test's."""
    from stapel_listings.models import Listing

    _root, leaf = category_tree

    def _make(**overrides):
        fields = {
            "owner": user,
            "category_id": str(leaf.pk),
            "language": "en",
            "currency": "USD",
            "title_draft": "Apple iPhone 13 Pro",
            "description_draft": "An excellent phone in mint condition.",
            "price_draft": Decimal("500.00"),
            "lat_draft": Decimal("49.611600"),
            "lon_draft": Decimal("6.131900"),
            "geohash_draft": "u0ubw2mtzz",
            "location_label_draft": "Luxembourg",
            "features_draft": {"brand": {"type": "string", "value": "apple"}},
        }
        fields.update(overrides)
        return Listing.objects.create(**fields)

    return _make


@pytest.fixture
def published_listing(make_listing):
    """A listing all the way to PUBLISHED, through the real pipeline.

    Publishing requests moderation (``listing.submitted``) and the verdict is
    what promotes it — which is the composite's own wiring, so the fixture
    goes through it rather than assigning ``status`` behind its back.
    """
    from stapel_listings.services.publish import publish_listing

    listing = make_listing()
    publish_listing(listing)
    listing.apply_moderation("approved")
    listing.refresh_from_db()
    return listing


# ── API + comm harness for the conversation surface ──────────────────


@pytest.fixture(autouse=True)
def _reset_comm_functions():
    """Restore the Function registry around every test.

    Snapshot-and-restore rather than clear: this package REGISTERS its own
    providers at ``ready()`` (``classified.subject_cards``,
    ``classified.seller_content``), and clearing outright would unregister
    them for every later test.
    """
    from stapel_core.comm.registry import function_registry

    providers = dict(function_registry._providers)
    schemas = dict(function_registry._schemas)
    yield
    function_registry._providers.clear()
    function_registry._providers.update(providers)
    function_registry._schemas.clear()
    function_registry._schemas.update(schemas)


@pytest.fixture
def client_for():
    """``client_for(user)`` — a fresh authenticated client per actor.

    Per actor rather than one shared client: a conversation has two sides and
    re-authenticating one handle silently changes who every earlier one is.
    """
    from rest_framework.test import APIClient

    def _make(user=None):
        client = APIClient()
        if user is not None:
            client.force_authenticate(user=user)
        return client

    return _make


@pytest.fixture
def cdn_double():
    """A ``cdn.describe_many`` double whose answer a test controls."""
    from stapel_core.comm import function

    state = {"items": {}, "missing": [], "calls": []}

    @function("cdn.describe_many")
    def _describe(payload):
        state["calls"].append(payload)
        refs = payload.get("refs") or []
        return {
            "items": {r: state["items"][r] for r in refs if r in state["items"]},
            "missing": [r for r in refs if r in state["missing"]],
        }

    return state


@pytest.fixture
def profiles_double():
    """``profiles.display_names`` — the only public-profile read the fleet has."""
    from stapel_core.comm import function

    state = {"display_names": {}}

    @function("profiles.display_names")
    def _names(payload):
        wanted = [str(u) for u in (payload.get("user_ids") or [])]
        return {
            "display_names": {
                u: state["display_names"][u] for u in wanted if u in state["display_names"]
            }
        }

    return state


@pytest.fixture
def blocks_double(settings):
    """The routed-upstream ``profiles.relationships`` provider, in-process.

    Registering it is how a test puts the composite into the state the fleet
    will be in once stapel-profiles ships the function: blocks enforced, not
    merely declared.
    """
    from stapel_core.comm import function

    state = {"blocked": set(), "fail": False}

    @function("profiles.relationships")
    def _relationships(payload):
        if state["fail"]:
            raise RuntimeError("profiles is down")
        pairs = payload.get("pairs") or []
        return {
            "blocked": [
                [a, b] for a, b in pairs if frozenset((str(a), str(b))) in state["blocked"]
            ]
        }

    return state
