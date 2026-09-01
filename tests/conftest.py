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
    """Clear per-process caches the modules keep across tests.

    The Django cache is one of them, and it matters more than it looks.
    ``stapel_listings.services.category_schema`` memoizes a category's
    features under its ID; the database is rolled back between tests but
    LocMem is not, and category primary keys are REUSED after a rollback. So
    one test's schema answers the next test's lookup for a numerically equal
    but entirely unrelated category, and the symptom is
    ``Feature '<slug>' is not allowed`` at publish — a failure that appears
    only in a full run, only in some orders, and never when you re-run the one
    test to investigate it. In production the same key is advanced by a
    ``category.changed`` fact; here nothing advances it, because nothing
    changed as far as the cache can tell.
    """
    from django.core.cache import cache

    from stapel_search import facets

    facets.reset_path_degradation()
    cache.clear()
    yield
    cache.clear()


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


# The block fixtures (`block`, `blocks_down`, `no_block_provider`) come from
# `stapel_classified.testing`, the plugin this module ships for every
# deployment that installs it — see the root conftest. This suite uses the
# shipped harness rather than a private copy, which is also how the harness
# stays honest: it is exercised by the module's own tests.


@pytest.fixture
def display_name():
    """Give a user a display name, through stapel-profiles' own write path.

    There is no ``profiles.display_names`` double any more, and there must not
    be: stapel_profiles is mounted in this harness (see the root conftest), it
    serves that Function itself, and core's registry allows exactly one
    provider per name. A double would have been this suite asserting its own
    idea of profiles while the real one sat next to it unused.
    """
    from stapel_profiles.models import get_profile_model

    def _set(user, name):
        profile, _ = get_profile_model().objects.get_or_create(user_id=user.pk)
        profile.display_name = name
        profile.save(update_fields=["display_name"])
        return profile

    return _set


# ── Real chat threads ────────────────────────────────────────────────


@pytest.fixture
def thread():
    """``thread(buyer, seller, listing)`` — a real direct conversation in chat.

    Created through ``stapel_chat.services.create_direct`` with the subject,
    which is the call a client makes. Since chat 0.6.0 the subject is part of
    a direct thread's identity, so this is also what makes two listings
    between the same two people two different threads — the arithmetic that
    used to force this composite to keep its own many-subjects table.
    """
    from stapel_chat.services import create_direct

    def _make(owner, other, listing=None, *, subject_key=None, scope_key=""):
        key = str(subject_key if subject_key is not None else listing.pk)
        return create_direct(
            owner=owner,
            other_user_id=other.pk,
            scope_key=scope_key,
            subject_type="listing",
            subject_key=key,
        )

    return _make
