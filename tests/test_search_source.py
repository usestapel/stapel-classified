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
        # A place, because stapel-listings 0.16 refuses to publish without
        # one (REQUIRE_LOCATION_ON_PUBLISH).
        lat_draft="49.6116",
        lon_draft="6.1319",
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


def test_a_live_edit_republish_never_leaves_the_index(published_listing):
    """listings 0.5.0: re-publishing a LIVE listing is not a takedown.

    Before 0.5.0, ``publish_listing`` on an already-published listing set
    ``status = pending`` past the FSM — no event, so the index never learned
    and just kept serving a stale document — and even a fixed indexer would
    have had nothing to invalidate on. Now the promoted content is visible
    immediately (``status`` stays ``published``; only ``moderation_status``
    goes back to ``pending``), so the listing must stay in the index across
    the whole re-publish, and the edited content must be what is served —
    not the pre-edit snapshot the takedown story would have frozen.
    """
    published_listing.title_draft = "Apple iPhone 13 Pro Max — mint, unlocked"
    from stapel_listings.services.publish import publish_listing

    publish_listing(published_listing)
    published_listing.refresh_from_db()

    assert published_listing.status == "published"
    assert published_listing.moderation_status == "pending"

    body = _query()
    assert _keys(body) == {str(published_listing.pk)}
    assert body["items"][0]["card"]["title"] == "Apple iPhone 13 Pro Max — mint, unlocked"


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


# ── the gallery a result row can swipe ───────────────────────────────
#
# The projection was the ceiling, not the client: `_card` stored `images[0]`
# and nothing else, so a SERP row had exactly one photo however swipeable the
# card drawing it was. These run the whole real path — publish, the
# `listing.published` fact, the pull over `listings.search_documents`, the
# stored document, the HTTP query — because the claim is about what a result
# row CARRIES, and only the far end of that path can answer it.


def _publish_with(make_listing, refs):
    from stapel_listings.services.publish import publish_listing

    listing = make_listing(images_draft=list(refs))
    publish_listing(listing)
    listing.apply_moderation("approved")
    listing.refresh_from_db()
    return listing


@pytest.mark.parametrize("count", [1, 3, 10])
def test_a_result_row_carries_the_whole_gallery(make_listing, count):
    refs = [f"product/photo-{i}" for i in range(count)]
    listing = _publish_with(make_listing, refs)

    hit = _query()["items"][0]
    assert hit["key"] == str(listing.pk)
    # Order is the seller's own, and it is preserved: photo one is the one
    # they put first, which is the one the strip opens on.
    assert hit["card"]["images"] == refs


@pytest.mark.parametrize("count", [1, 3, 10])
def test_the_singular_key_still_answers_for_every_client_that_reads_it(
    make_listing, count
):
    """`image` did not move: it is `images[0]`, described the same way.

    The card travels through stores that never validate it — stapel-search
    keeps it in a JSONField, stapel-chat re-declares it as opaque JSON — so a
    key removed here is a client rendering nothing until it is redeployed.
    """
    refs = [f"product/photo-{i}" for i in range(count)]
    _publish_with(make_listing, refs)

    card = _query()["items"][0]["card"]
    assert card["image"] == card["images"][0] == refs[0]


def test_a_listing_with_no_photo_carries_an_empty_gallery(published_listing):
    card = _query()["items"][0]["card"]
    assert card["images"] == []
    assert card["image"] is None


def test_the_gallery_is_capped_so_a_stored_card_cannot_grow_without_bound(
    make_listing,
):
    """A card is a glance. Photo eleven is a reason to open the listing."""
    from stapel_classified.conf import classified_settings

    limit = int(classified_settings.CARD_IMAGES_LIMIT)
    refs = [f"product/photo-{i}" for i in range(limit + 2)]
    _publish_with(make_listing, refs)

    assert _query()["items"][0]["card"]["images"] == refs[:limit]


def test_one_ref_twice_is_one_slide(make_listing):
    """A carousel that repeats a picture reads as a broken carousel."""
    _publish_with(make_listing, ["product/a", "product/b", "product/a"])

    assert _query()["items"][0]["card"]["images"] == ["product/a", "product/b"]


def test_the_stored_card_carries_refs_and_never_a_render_snapshot(make_listing):
    """The rebuild path must not fan out to the CDN once per row.

    The conversation header merges `cdn.describe_many` over its cards because
    it renders one header now; a snapshot frozen into a stored document goes
    stale the first time the CDN re-encodes anything, and a rebuild that asked
    per row would make a corpus-sized reindex a corpus-sized CDN load.
    """
    _publish_with(make_listing, ["product/a", "product/b"])

    card = _query()["items"][0]["card"]
    assert card["images"] == ["product/a", "product/b"]
    assert all(isinstance(ref, str) for ref in card["images"])


# ── which refs a bounded describe batch spends itself on ─────────────


def test_a_bounded_describe_batch_buys_every_primary_before_any_second():
    """Column-major, and the reason is the chat inbox.

    `cdn.describe_many` takes a bounded batch. Fifty conversations each
    carrying ten photos is five hundred refs, so something is left out — and
    the honest order to leave it out in is everybody's first photo before
    anybody's second. Row-major would spend the budget on the first cards'
    galleries and leave the last header with no thumbnail at all, which is
    the surface that only ever shows a thumbnail.
    """
    from stapel_classified.cards import _refs_to_describe

    cards = {
        "1": {"images": ["a1", "a2", "a3"]},
        "2": {"images": ["b1", "b2"]},
        "3": {"images": ["c1"]},
    }
    assert _refs_to_describe(cards, 4) == ["a1", "b1", "c1", "a2"]
    # Nothing is asked about twice, and the budget is a ceiling, not a target.
    assert _refs_to_describe(cards, 99) == ["a1", "b1", "c1", "a2", "b2", "a3"]
    assert _refs_to_describe({}, 10) == []


# ── the spec summary line a storefront list card draws ───────────────
#
# A SERP row shows one short line of attributes under the title — «2015 ·
# 120 000 км» — and it reads it off the STORED card: a result page has no
# category schema in hand and no budget for a hydration hop per row. Until
# 0.10.9 the stored card carried title/price/currency/location/images/
# published_at and nothing else, so that line was blank on every row of every
# board while both halves of the answer already existed.


def _publish_car(user, *, features: dict, defs: list[tuple[str, dict, dict]]):
    """A published car listing in its own category, and its search document.

    *defs* is ``[(slug, config, flags)]`` — the category's feature definitions,
    authored in order. *features* is the draft's own values.
    """
    from decimal import Decimal

    from stapel_categories.models import Category, CategoryFeature, Feature
    from stapel_core.comm import call
    from stapel_listings.models import Listing
    from stapel_listings.services.publish import publish_listing

    category = Category.objects.create(name="Cars", slug="cars-summary-line")
    for order, (slug, config, flags) in enumerate(defs):
        CategoryFeature.objects.create(
            category=category,
            feature=Feature.objects.create(
                slug=slug, name=slug.title(), config=config, **flags
            ),
            order=order,
        )
    listing = Listing.objects.create(
        owner=user,
        category_id=str(category.pk),
        language="en",
        title_draft="A car",
        description_draft="A perfectly ordinary car.",
        price_draft=Decimal("100.00"),
        lat_draft="49.6116",
        lon_draft="6.1319",
        features_draft=features,
    )
    publish_listing(listing)
    listing.apply_moderation("approved")

    key = str(listing.pk)
    return key, call("listings.search_documents", {"keys": [key]})[key]


def test_the_card_carries_a_spec_summary_line_for_a_listing_with_features(
    db, user
):
    """Every element a card prints, with the OWNER's card contract on it.

    `label` / `unit` / `presentation` are
    `stapel_listings.services.features.decorate_card_elements` — called, never
    reimplemented — so the line a search hit draws and the line the listing's
    own API draws are one rule with one bug surface. `presentation` is what
    stops a card from printing «Кирпичный · 3 · 9»: a bare numeric caption is
    `name_value` («Year 2015») unless it has a unit, and then it is
    `value_unit` («120000 км»).
    """
    from stapel_classified.search_sources import map_listing

    key, payload = _publish_car(
        user,
        features={
            "year": {"type": "int", "value": 2015},
            "kilometrage": {"type": "int", "value": 120000},
        },
        defs=[
            ("year", {"type": "int"}, {"show_at_title": True}),
            (
                "kilometrage",
                {"type": "int", "postfix": "km"},
                {"show_at_title": True},
            ),
        ],
    )

    line = map_listing({**payload, "key": key}).card["features_title"]

    assert [element["slug"] for element in line] == ["year", "kilometrage"]
    assert line[0]["label"] == "2015"
    # No unit on the DAO, so the number needs its feature's name beside it or
    # the card prints a bare «2015» nobody can read.
    assert line[0]["presentation"] == "name_value"
    assert line[0]["name"] == "Year"
    assert "unit" not in line[0]
    # A unit IS the caption's context, so the name is not repeated.
    assert line[1]["label"] == "120000"
    assert line[1]["unit"] == "km"
    assert line[1]["presentation"] == "value_unit"


def test_the_card_carries_badges_the_owner_serves(db, user):
    """`features_badges` travels the same rule and the same call.

    The mapper's contract is "whatever the owner serves plus `key`", so the
    badge list is projected from the document exactly as the title line is —
    one function over both, and the card badge contract on every element of
    each. `show_as_badge` on a closed select is the case a card draws as a
    chip rather than as part of the summary line.
    """
    from stapel_classified.search_sources import map_listing

    key, payload = _publish_car(
        user,
        features={"condition": {"type": "select", "value": ["b-u"]}},
        defs=[
            (
                "condition",
                {
                    "type": "select",
                    "options": [
                        {"value": "b-u", "label": "Used"},
                        {"value": "new", "label": "New"},
                    ],
                },
                {"show_as_badge": True},
            )
        ],
    )
    document = {**payload, "key": key}
    # The owner stamps the badge column on the listing; a document that does
    # not serve it yet projects an empty list rather than a wrong one.
    from stapel_listings.models import Listing

    document.setdefault("features_badges", Listing.objects.get(pk=key).features_badges)

    (badge,) = map_listing(document).card["features_badges"]
    assert badge["slug"] == "condition"
    # The CAPTION, not the code. `b-u` on a chip is the storage slug printed
    # at a buyer, which is the defect this contract exists to close.
    assert badge["label"] == "Used"
    assert badge["presentation"] == "value"


def test_a_listing_without_features_projects_an_empty_line(published_listing):
    """Both keys are always present, and empty is a sentence a card renders.

    A missing KEY makes a client test for the field's existence; an empty
    list says "this listing has nothing for that line", which is what the
    card draws as no line at all.
    """
    card = _query()["items"][0]["card"]

    assert card["features_title"] == []
    assert card["features_badges"] == []
