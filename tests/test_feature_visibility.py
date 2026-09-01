"""An identifier attribute, end to end through the real assembly.

Four modules had to change for a VIN to stop being published, and each of them
tests its own half against a stub of the others: stapel-categories proves the
column and the comm payload, stapel-attributes proves the stamp and the
redaction, stapel-listings proves the projections and the serializer against a
stubbed ``categories.features``, stapel-search proves the indexer against a
hand-built document. **Every one of those suites can be green while the fleet
still leaks**, because the thing that has to hold is a property of the SEAM:
the axis is set in one module, stamped in a second, dropped in a third and
refused in a fourth, and nothing in any single repo can observe the chain.

This is the only place the chain exists. Nothing here is stubbed. A real
``Feature`` row carries the visibility, ``categories.features`` hands it over
comm, ``publish_listing`` stamps it into the stored DAO, the HTTP detail read
redacts it, the ``listing.*`` fact travels the in-process bus, stapel-search
pulls the document back through ``listings.search_documents`` and the
assertions are made against the public query surface.

The value under test is the one that was live on the stand:
``JTNBE40K803512345``, the VIN of listing 287.
"""
import pytest

pytestmark = pytest.mark.django_db

VIN = "JTNBE40K803512345"


@pytest.fixture
def category_with_vin(category_tree):
    """The fixture tree, plus a mandatory owner-only VIN on the leaf.

    Mandatory on purpose: the axis is orthogonal to requiredness, and a test
    that hid an OPTIONAL field would not prove the interesting half — that a
    seller is still forced to supply a value nobody else may read.
    """
    from stapel_categories.models import CategoryFeature, Feature

    _root, leaf = category_tree
    vin = Feature.objects.create(
        slug="vin",
        name="VIN, номер кузова или SN",
        config={"type": "string", "minLength": 17, "maxLength": 17},
        mandatory=True,
        visibility="owner",
    )
    CategoryFeature.objects.create(category=leaf, feature=vin, order=1)
    return leaf, vin


@pytest.fixture
def listing_with_vin(category_with_vin, make_listing):
    from stapel_listings.services.publish import publish_listing

    listing = make_listing(
        features_draft={
            "brand": {"type": "string", "value": "apple"},
            "vin": {"type": "string", "value": VIN},
        }
    )
    publish_listing(listing)
    listing.apply_moderation("approved")
    listing.refresh_from_db()
    return listing


def _query(**params):
    from django.test import Client

    response = Client().get("/search/api/v1/query", {"type": "listing", **params})
    assert response.status_code == 200, (response.status_code, response.content[:400])
    return response.json()


# ── the catalogue can say it, and the saying survives the comm boundary ──


def test_the_axis_crosses_the_comm_boundary(category_with_vin):
    """stapel-listings never imports stapel-categories: if `visibility` does
    not survive `categories.features`, the stamp is never applied and every
    downstream defence is defending nothing."""
    from stapel_listings.services.category_schema import get_feature_configs

    leaf, _vin = category_with_vin
    configs = {c["slug"]: c for c in get_feature_configs(str(leaf.pk), use_cache=False)}
    assert configs["vin"]["visibility"] == "owner"
    assert configs["brand"].get("visibility", "public") == "public"


def test_the_stored_value_carries_the_stamp(listing_with_vin):
    vin = next(d for d in listing_with_vin.features if d["slug"] == "vin")
    assert vin["value"] == VIN, "the value is STORED — hiding is not discarding"
    assert vin["visibility"] == "owner"


def test_it_is_absent_from_every_public_projection(listing_with_vin):
    assert "vin" not in listing_with_vin.features_search
    assert "vin" not in [d["slug"] for d in listing_with_vin.features_title]
    assert "vin" not in [d["slug"] for d in listing_with_vin.features_badges]
    # The public sibling still projects, so this is a targeted filter and not
    # a projection that quietly stopped working.
    assert listing_with_vin.features_search["brand"] == ["apple"]


# ── the read surface ──────────────────────────────────────────────────


def test_an_anonymous_detail_read_carries_no_vin(client_for, listing_with_vin):
    response = client_for().get(f"/listings/api/v1/listings/{listing_with_vin.pk}/")
    assert response.status_code == 200
    assert VIN not in response.content.decode()


def test_the_row_is_still_there_as_a_stub(client_for, listing_with_vin):
    """A buyer must be able to see that the field exists and was answered —
    that is what makes «указан продавцом» a sentence worth printing."""
    response = client_for().get(f"/listings/api/v1/listings/{listing_with_vin.pk}/")
    vin = next(d for d in response.json()["features"] if d["slug"] == "vin")
    assert vin["redacted"] is True
    assert vin["present"] is True
    assert "value" not in vin
    # Presence is observed; verification is a claim. Nothing in this fleet
    # runs a VIN check, so the payload must not carry one.
    assert "verification" not in vin


def test_the_owner_reads_their_own_value(client_for, user, listing_with_vin):
    response = client_for(user).get(f"/listings/api/v1/listings/{listing_with_vin.pk}/")
    vin = next(d for d in response.json()["features"] if d["slug"] == "vin")
    assert vin["value"] == VIN


def test_another_signed_in_user_does_not(client_for, other_user, listing_with_vin):
    response = client_for(other_user).get(
        f"/listings/api/v1/listings/{listing_with_vin.pk}/"
    )
    vin = next(d for d in response.json()["features"] if d["slug"] == "vin")
    assert vin["redacted"] is True


# ── the index is an oracle, so it gets its own assertions ─────────────


def test_the_listing_is_indexed_at_all(listing_with_vin):
    """The control for everything below: a test that proves a VIN is not
    findable is worthless if the listing was never in the index."""
    assert _query(q="iPhone")["items"], "precondition: the listing is indexed"


def test_the_vin_is_not_a_filter_axis(listing_with_vin):
    """`?f.vin=<value>` either returns the listing or does not, which is how a
    stranger confirms that this exact advert is that exact car. The whole
    point of the axis is that the question cannot be asked."""
    assert _query(**{"f.vin": VIN})["items"] == []


def test_the_vin_is_not_free_text_either(listing_with_vin):
    """`features_title` feeds the text arm, so a badge attribute's value is
    findable by `q=`. Same oracle, different spelling."""
    assert _query(q=VIN)["items"] == []


def test_the_vin_is_not_an_enumerable_facet(listing_with_vin, category_with_vin):
    """A slug merely ranked out of the panel can be re-admitted by asking for
    it, which would list its values with counts. A hidden one is excluded
    outright and cannot be asked back.

    Scoped to the category, which is how a facet panel is ever actually
    requested: `visibility` is a property of a FeatureDef, and a FeatureDef is
    a property of a category — the same slug can be public in one branch and
    hidden in another, so there is no category-free answer to be had.
    """
    leaf, _vin = category_with_vin
    body = _query(facets="vin", category=str(leaf.pk))
    assert "vin" not in body.get("facets", {})
    assert "vin" not in body.get("facet_meta", {}).get("counted", [])
    # The paired control, in the same call shape: a public sibling asked for
    # the same way IS admitted, so the exclusion is about this feature and not
    # about the request.
    assert "brand" in _query(facets="brand", category=str(leaf.pk)).get("facets", {})


def test_without_a_category_the_panel_discriminates_nothing(listing_with_vin):
    """The honest boundary of the exclusion above, pinned rather than assumed.

    With no category there is no plan, so an explicitly requested slug is
    echoed back with an empty count map — and it is echoed back for a slug
    that has never existed in exactly the same way. A response that is
    identical for a real hidden feature and for a nonsense string confirms
    nothing about any listing, which is the property that makes it not an
    oracle. The values themselves are unreachable regardless: the writer never
    indexed them.
    """
    hidden = _query(facets="vin")["facets"]
    nonsense = _query(facets="no_such_slug_at_all")["facets"]
    assert hidden == {"vin": {}}
    assert nonsense == {"no_such_slug_at_all": {}}
    assert list(hidden.values()) == list(nonsense.values())


def test_a_public_attribute_is_still_all_of_those_things(listing_with_vin):
    """The paired control. Without it, a build that simply stopped indexing
    attributes altogether would pass every test above."""
    assert _query(**{"f.brand": "apple"})["items"], "a public facet must still filter"
