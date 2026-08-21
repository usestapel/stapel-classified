"""The `listing` search source, end to end through the real pipeline.

stapel-search knows nothing about listings and stapel-listings knows nothing
about an index; the declaration that joins them lives in this repo, so this
is the only place the join can be proved. Nothing here is mocked: a listing
is published through ``publish_listing``, the ``listing.*`` fact travels the
in-process bus, stapel-search pulls the document back over
``listings.search_documents``, and the assertion is made against the HTTP
query surface.
"""
from decimal import Decimal

import pytest

pytestmark = pytest.mark.django_db


def _query(**params):
    from django.test import Client

    response = Client().get("/search/api/v1/query", {"type": "listing", **params})
    assert response.status_code == 200, (response.status_code, response.content[:400])
    return response.json()


def _keys(body):
    return {item["key"] for item in body["items"]}


# ── the declaration ──────────────────────────────────────────────────


def test_source_is_registered_and_resolves():
    from stapel_search.registry import get_source

    spec = get_source("listing")
    assert spec.content_function == "listings.search_documents"
    assert spec.export_function == "listings.search_export"
    assert spec.key_fields[0] == "listing_id"


def test_visible_statuses_follow_listings_own_definition():
    """The index's idea of "live" is listings', not a copy of it.

    A lifecycle state added upstream must not leave the index behind; the
    spec's word for the alternative is a "declared but not connected" seam.
    """
    from stapel_listings.models import INDEXED_STATUSES
    from stapel_search.registry import get_source

    assert get_source("listing").visible_statuses == frozenset(
        str(status) for status in INDEXED_STATUSES
    )


def test_invalidation_signals_are_subscribed():
    """Registering the source is what wires the subscriber — no host code."""
    from stapel_core.comm.registry import action_registry

    for topic in ("listing.published", "listing.updated", "listing.removed"):
        assert action_registry.handlers(topic), topic


def test_both_source_functions_are_reachable():
    from stapel_core.comm import function_unreachable_reason

    assert not function_unreachable_reason("listings.search_documents")
    assert not function_unreachable_reason("listings.search_export")


# ── the mapper ───────────────────────────────────────────────────────


def test_mapper_shapes_a_real_listings_document(published_listing):
    """Every field the composite fills, against the owner's real payload."""
    from stapel_core.comm import call

    from stapel_classified.search_sources import map_listing

    key = str(published_listing.pk)
    payload = call("listings.search_documents", {"keys": [key]})[key]
    doc = map_listing({**payload, "key": key})

    assert doc.doc_type == "listing"
    assert doc.doc_key == key
    assert doc.status == "published"
    assert doc.language == "en"
    assert doc.owner_key == str(published_listing.owner_id)
    assert doc.category_id == str(published_listing.category_id)
    assert doc.title == "Apple iPhone 13 Pro"
    assert doc.body.startswith("An excellent phone")
    assert doc.features_search == {"brand": ["apple"]}
    assert doc.price_base == Decimal("500.00")
    assert doc.lat == Decimal("49.611600") and doc.lon == Decimal("6.131900")
    assert doc.geohash == published_listing.geohash
    assert doc.card["title"] == "Apple iPhone 13 Pro"
    assert doc.card["location_label"] == "Luxembourg"
    # Prices and coordinates leave listings as strings; a float would round a
    # price on the wire, so the mapper reconstitutes Decimals, not floats.
    assert isinstance(doc.price_base, Decimal)
    # seq is the owner's own ordering token (unix ms of updated_at), so a
    # snapshot row and a live event for one listing are comparable.
    assert doc.seq == int(published_listing.updated_at.timestamp() * 1000)
    # category_path is left to stapel-search + categories.path — a path
    # guessed here would be a second ancestry model next to the real tree.
    assert doc.category_path == ()


def test_mapper_carries_title_attributes_into_the_text_arm(db, user, category_tree):
    """A value flagged ``show_at_title`` is findable as weight-B text.

    ``features_title`` is a list of DAOs; ``features_search`` is listings'
    own extraction of the searchable values out of those same DAOs. The
    mapper intersects them rather than re-deriving values from DAOs, so this
    is the test that the intersection actually yields something.
    """
    from decimal import Decimal

    from stapel_categories.models import Category, CategoryFeature, Feature
    from stapel_core.comm import call
    from stapel_listings.models import Listing
    from stapel_listings.services.publish import publish_listing

    category = Category.objects.create(name="Cars", slug="cars")
    CategoryFeature.objects.create(
        category=category,
        feature=Feature.objects.create(
            slug="make", name="Make", config={"type": "string"}, show_at_title=True
        ),
        order=0,
    )
    listing = Listing.objects.create(
        owner=user,
        category_id=str(category.pk),
        language="en",
        title_draft="A car",
        description_draft="A perfectly ordinary car.",
        price_draft=Decimal("100.00"),
        features_draft={"make": {"type": "string", "value": "apple"}},
    )
    publish_listing(listing)
    listing.apply_moderation("approved")

    key = str(listing.pk)
    payload = call("listings.search_documents", {"keys": [key]})[key]

    from stapel_classified.search_sources import map_listing

    assert map_listing({**payload, "key": key}).text_extra == ("apple",)


# ── publish -> index -> query ────────────────────────────────────────


def test_publishing_a_listing_makes_it_findable(published_listing):
    body = _query()
    assert _keys(body) == {str(published_listing.pk)}

    hit = body["items"][0]
    assert hit["card"]["title"] == "Apple iPhone 13 Pro"
    # DSA Art. 26: every item carries the marker, including a false one.
    assert hit["promoted"] is False


def test_text_search_finds_by_title_and_by_body(published_listing):
    assert _keys(_query(q="iPhone")) == {str(published_listing.pk)}
    assert _keys(_query(q="mint")) == {str(published_listing.pk)}
    assert _query(q="unobtainium")["items"] == []


def test_geo_radius_cuts_by_distance(published_listing):
    near = _query(lat="49.6116", lon="6.1319", radius_km="10")
    assert _keys(near) == {str(published_listing.pk)}
    far = _query(lat="52.5200", lon="13.4050", radius_km="10")
    assert far["items"] == []


def test_a_takedown_removes_it_from_the_answer(published_listing):
    """The verdict path, not a direct write: ``published -> blocked``.

    listings 0.4.0 added the state and the edge precisely so a takedown emits
    ``listing.removed`` and the index learns for free. That is the claim
    being checked here — nothing calls into stapel-search.
    """
    published_listing.apply_moderation("rejected")
    assert _query()["items"] == []


def test_republishing_restores_it(published_listing):
    published_listing.apply_moderation("rejected")
    assert _query()["items"] == []
    published_listing.refresh_from_db()
    published_listing.apply_moderation("approved")
    assert _keys(_query()) == {str(published_listing.pk)}


# ── categories.path: the rollup that used to be degraded ─────────────


def test_category_rollup_is_no_longer_degraded(published_listing, category_tree):
    """A filter on the PARENT category finds the child's listing.

    Until stapel-categories 0.5.6 nothing in the fleet answered
    ``categories.path``: ``category_path`` collapsed to one segment, every
    answer carried ``degraded: ["category_rollup"]`` and this query returned
    nothing. The provider is a member of this composite, so the composite is
    where the closure is proved.
    """
    root, leaf = category_tree

    exact = _query(category=f"{root.pk}/{leaf.pk}")
    assert _keys(exact) == {str(published_listing.pk)}
    assert "category_rollup" not in exact["degraded"]

    rollup = _query(category=str(root.pk))
    assert _keys(rollup) == {str(published_listing.pk)}
    assert "category_rollup" not in rollup["degraded"]

    from stapel_search.models import SearchDocument

    row = SearchDocument.objects.get(doc_type="listing", doc_key=str(published_listing.pk))
    assert row.category_path == [str(root.pk), str(leaf.pk)]


# ── facets over the category's own feature schema ────────────────────


def test_facet_filter_over_a_category_feature(published_listing, category_tree, make_listing):
    """Counting and filtering by ``brand``, end to end and in process.

    The facet plan is built from ``categories.features`` for the requested
    category (inherited features included — ``brand`` lives on the parent),
    the values come from the listing's own ``features_search``, and the
    filter goes through the configured engine. Three modules and no mock.
    """
    other = make_listing(
        title_draft="Samsung Galaxy",
        features_draft={"brand": {"type": "string", "value": "samsung"}},
    )
    from stapel_listings.services.publish import publish_listing

    publish_listing(other)
    other.apply_moderation("approved")

    root, leaf = category_tree
    # The category filter is a PREFIX over the root->leaf path, so a bare
    # leaf id is not a path: the facet plan is built from the LAST segment.
    panel = _query(category=f"{root.pk}/{leaf.pk}")
    assert _keys(panel) == {str(published_listing.pk), str(other.pk)}
    assert panel["facets"]["brand"] == {"apple": 1, "samsung": 1}, panel["facets"]
    assert "brand" in panel["facet_meta"]["counted"]

    narrowed = _query(**{"category": f"{root.pk}/{leaf.pk}", "f.brand": "apple"})
    assert _keys(narrowed) == {str(published_listing.pk)}


# ── the snapshot half of the seam ────────────────────────────────────


def test_rebuild_from_the_export_snapshot_agrees_with_the_live_path(published_listing):
    """``search_rebuild`` reads ``listings.search_export`` and lands the same
    document the live signal did — the two halves cannot disagree, because
    the mapper and the owner's builder are each single-definition."""
    from stapel_search.models import SearchDocument
    from stapel_search.services import rebuild

    before = SearchDocument.objects.get(
        doc_type="listing", doc_key=str(published_listing.pk)
    )
    fields = {
        "title": before.title,
        "category_path": list(before.category_path or []),
        "facet_terms": list(before.facet_terms or []),
        "price_base": before.price_base,
    }

    SearchDocument.objects.all().delete()
    report = rebuild("listing")
    assert report.indexed == 1, report

    after = SearchDocument.objects.get(
        doc_type="listing", doc_key=str(published_listing.pk)
    )
    assert {
        "title": after.title,
        "category_path": list(after.category_path or []),
        "facet_terms": list(after.facet_terms or []),
        "price_base": after.price_base,
    } == fields
    assert _keys(_query()) == {str(published_listing.pk)}


# ── the wire-shape conversions, including the branches a happy path skips ──


@pytest.mark.parametrize(
    "raw, expected",
    [
        (None, None),
        ("", None),
        ("not-a-price", None),  # a malformed value is absent, never 0.00
        ("12.50", Decimal("12.50")),
    ],
)
def test_decimal_conversion_is_total(raw, expected):
    from stapel_classified.search_sources import _decimal

    assert _decimal(raw) == expected


def test_datetime_conversion_passes_through_an_already_parsed_value():
    """Both callers exist: the live pull sends ISO strings, but a host
    replacing the content Function may hand over datetimes already."""
    from datetime import datetime, timezone

    from stapel_classified.search_sources import _datetime

    when = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert _datetime(when) is when
    assert _datetime("") is None
    assert _datetime("2026-01-01T00:00:00+00:00") == when
