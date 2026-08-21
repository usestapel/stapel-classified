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
