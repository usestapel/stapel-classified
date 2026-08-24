"""The conversation header: what this chat is about, and with whom.

The owner opened the live product's chat and found it "unclear with whom and
about what" — no short listing card, no seller data. Every test here is a
sentence from that finding, run against REAL member modules: a real listing
moved through its real publication pipeline, the real
``listings.search_documents`` behind the card, the real CDN contract shape.
A mock on either side of a seam is exactly what cannot prove a seam.
"""
import uuid

import pytest

from stapel_classified import services
from stapel_classified.models import ConversationSubject

pytestmark = pytest.mark.django_db


def _conv():
    return uuid.uuid4()


def _bind(listing, buyer, conversation=None):
    conversation = conversation or _conv()
    services.bind_listing_conversation(
        conversation_id=conversation,
        listing_key=listing.pk,
        actor_id=buyer.pk,
    )
    return conversation


# ── Binding ──────────────────────────────────────────────────────────


def test_a_conversation_carries_a_resolvable_listing(published_listing, other_user):
    conversation = _bind(published_listing, other_user)

    row = ConversationSubject.objects.get(conversation_id=conversation)
    assert row.subject_type == "listing"
    assert row.subject_key == str(published_listing.pk)
    assert str(row.initiator_id) == str(other_user.pk)
    assert str(row.counterparty_id) == str(published_listing.owner_id)


def test_binding_is_idempotent_and_the_first_writer_owns_the_parties(
    published_listing, other_user, user
):
    """A retry, a second tab, an at-least-once client: one fact either way —
    and a later caller cannot rewrite who the two sides of a thread are."""
    conversation = _bind(published_listing, other_user)
    services.bind_listing_conversation(
        conversation_id=conversation,
        listing_key=published_listing.pk,
        actor_id=other_user.pk,
    )
    assert ConversationSubject.objects.filter(conversation_id=conversation).count() == 1


def test_you_cannot_open_a_buyer_conversation_on_your_own_listing(
    published_listing, user
):
    with pytest.raises(services.OwnListing):
        _bind(published_listing, user)


def test_binding_to_a_listing_nobody_serves_is_refused(other_user):
    with pytest.raises(services.SubjectNotFound):
        services.bind_listing_conversation(
            conversation_id=_conv(), listing_key="999999", actor_id=other_user.pk
        )


# ── The card ─────────────────────────────────────────────────────────


def test_the_header_carries_a_short_card_and_the_seller(
    published_listing, other_user, profiles_double
):
    profiles_double["display_names"][str(published_listing.owner_id)] = "Ada Lovelace"
    conversation = _bind(published_listing, other_user)

    context = services.conversation_context(conversation, viewer_id=other_user.pk)
    card = context["subject"]["listing"]
    assert card["title"] == "Apple iPhone 13 Pro"
    assert card["currency"] == "USD"
    assert str(card["price"]) == "500.00"
    assert card["state"] == "available"
    assert card["location_label"] == "Luxembourg"

    seller = context["counterparty"]
    assert seller["user_id"] == str(published_listing.owner_id)
    assert seller["display_name"] == "Ada Lovelace"
    assert context["viewer_role"] == "buyer"


def test_the_seller_sees_the_buyer_as_the_counterparty(
    published_listing, other_user, user, profiles_double
):
    """One row, two readings. The card a seller opens must not show the
    seller — the counterparty is whoever the reader is not."""
    profiles_double["display_names"][str(other_user.pk)] = "Grace Hopper"
    conversation = _bind(published_listing, other_user)

    context = services.conversation_context(conversation, viewer_id=user.pk)
    assert context["counterparty"]["user_id"] == str(other_user.pk)
    assert context["counterparty"]["display_name"] == "Grace Hopper"
    assert context["viewer_role"] == "seller"


def test_a_sold_listing_still_has_a_header(published_listing, other_user):
    """The moment a buyer is MOST confused is the one a public read hides.

    ``Listing.visible_to`` 404s anything not published — correct for a
    stranger, useless for the person standing in the conversation about it.
    The card answers ``unavailable`` with the real status instead.
    """
    conversation = _bind(published_listing, other_user)
    published_listing.status = "sold"
    published_listing.save(update_fields=["status"])

    card = services.conversation_context(conversation, viewer_id=other_user.pk)[
        "subject"
    ]["listing"]
    assert card["state"] == "unavailable"
    assert card["status"] == "sold"
    assert card["title"] == "Apple iPhone 13 Pro"


def test_a_deleted_listing_answers_gone_rather_than_vanishing(
    published_listing, other_user
):
    conversation = _bind(published_listing, other_user)
    published_listing.delete()  # soft delete — the row keeps existing

    card = services.conversation_context(conversation, viewer_id=other_user.pk)[
        "subject"
    ]["listing"]
    assert card["state"] == "gone"
    assert card["meta_reason"] == "listing_deleted"
    # And the conversation itself is still readable: blocking a thread's
    # header on a deleted listing would delete the conversation from the UI.
    assert card["listing_id"] == str(published_listing.pk)


def test_the_primary_image_carries_cdn_render_metadata(
    make_listing, other_user, cdn_double
):
    from stapel_listings.services.publish import publish_listing

    listing = make_listing(images_draft=["product/abc"])
    publish_listing(listing)
    listing.apply_moderation("approved")
    listing.refresh_from_db()

    cdn_double["items"]["product/abc"] = {
        "mime": "image/webp",
        "width": 1200,
        "height": 800,
        "aspect": 1.5,
        "preview_b64": "data:image/webp;base64,AAAA",
        "preview_kind": "blur",
        "variants": [{"tier": 240, "branch": "w", "url": "u", "width": 240, "height": 160}],
        "meta_status": "ok",
    }
    conversation = _bind(listing, other_user)

    image = services.conversation_context(conversation, viewer_id=other_user.pk)[
        "subject"
    ]["listing"]["image"]
    assert image["ref"] == "product/abc"
    assert image["aspect"] == 1.5
    assert image["preview_kind"] == "blur"
    assert image["variants"][0]["tier"] == 240


def test_an_unreachable_cdn_degrades_the_card_and_never_the_conversation(
    make_listing, other_user
):
    """Degradation is data. No cdn provider is registered in this test."""
    from stapel_listings.services.publish import publish_listing

    listing = make_listing(images_draft=["product/abc"])
    publish_listing(listing)
    listing.apply_moderation("approved")
    listing.refresh_from_db()
    conversation = _bind(listing, other_user)

    card = services.conversation_context(conversation, viewer_id=other_user.pk)[
        "subject"
    ]["listing"]
    assert card["meta_status"] == "partial"
    assert card["meta_reason"] == "cdn_unavailable"
    assert card["image"]["ref"] == "product/abc"
    assert card["title"] == "Apple iPhone 13 Pro"


def test_a_missing_public_profile_is_named_not_blank(published_listing, other_user):
    """No profiles provider at all: the card says WHICH function it wanted."""
    conversation = _bind(published_listing, other_user)

    seller = services.conversation_context(conversation, viewer_id=other_user.pk)[
        "counterparty"
    ]
    assert seller["meta_status"] == "partial"
    assert seller["meta_reason"] == "profile_unavailable"
    assert seller["avatar"] is None
    assert seller["rating"] is None  # never a fabricated zero


def test_a_rating_appears_once_seller_reviews_are_wired(
    published_listing, other_user, user, settings
):
    """Against the REAL stapel-reviews aggregate, not a double.

    The preset ships ``SELLER_RATING_TARGET_TYPE`` empty because THIS
    composite registers reviews about listings, not about sellers. A
    deployment that adds the target sets the key and the stars appear — that
    is the whole seam, and this test is it end to end.
    """
    from stapel_reviews.models import Review

    settings.STAPEL_CLASSIFIED = {"SELLER_RATING_TARGET_TYPE": "seller"}
    Review.objects.create(
        target_type="seller", target_key=str(user.pk), author=other_user, rating=5
    )
    Review.objects.create(
        target_type="seller", target_key=str(user.pk), author=user, rating=4
    )

    conversation = _bind(published_listing, other_user)
    seller = services.conversation_context(conversation, viewer_id=other_user.pk)[
        "counterparty"
    ]
    assert seller["rating"]["count"] == 2
    assert float(seller["rating"]["avg"]) == 4.5


# ── Several subjects in one thread ───────────────────────────────────


def test_one_thread_can_be_about_two_listings(make_listing, other_user):
    """chat 0.4.0's own arithmetic: a direct thread is keyed by the PAIR, so
    one buyer and one seller have exactly one thread whatever they discuss.
    Refusing the second listing would render the wrong card — the defect this
    work exists to fix — so the newest is the header and the rest is history.
    """
    from stapel_listings.services.publish import publish_listing

    first = make_listing()
    second = make_listing(title_draft="Sony WH-1000XM4")
    for listing in (first, second):
        publish_listing(listing)
        listing.apply_moderation("approved")
        listing.refresh_from_db()

    conversation = _conv()
    _bind(first, other_user, conversation)
    _bind(second, other_user, conversation)

    context = services.conversation_context(conversation, viewer_id=other_user.pk)
    assert context["subject"]["listing"]["title"] == "Sony WH-1000XM4"
    assert len(context["previous_subjects"]) == 1
    assert context["previous_subjects"][0]["listing"]["title"] == "Apple iPhone 13 Pro"


# ── Reading rights ───────────────────────────────────────────────────


def test_a_stranger_cannot_read_a_conversation_header(
    published_listing, other_user, db
):
    from django.contrib.auth import get_user_model

    stranger = get_user_model().objects.create(
        username="mallory", email="mallory@example.com"
    )
    conversation = _bind(published_listing, other_user)

    with pytest.raises(services.ConversationNotBound):
        services.conversation_context(conversation, viewer_id=stranger.pk)


def test_an_unbound_conversation_is_a_404(other_user):
    with pytest.raises(services.ConversationNotBound):
        services.conversation_context(_conv(), viewer_id=other_user.pk)


# ── The batch read the inbox makes ───────────────────────────────────


def test_the_inbox_resolves_a_page_in_one_pass(
    make_listing, other_user, profiles_double
):
    from stapel_listings.services.publish import publish_listing

    conversations = []
    for index in range(3):
        listing = make_listing(title_draft=f"Item {index}")
        publish_listing(listing)
        listing.apply_moderation("approved")
        listing.refresh_from_db()
        conversations.append(_bind(listing, other_user))

    contexts = services.conversation_contexts(
        [str(c) for c in conversations] + [str(_conv())], viewer_id=other_user.pk
    )
    assert len(contexts) == 3
    titles = {c["subject"]["listing"]["title"] for c in contexts.values()}
    assert titles == {"Item 0", "Item 1", "Item 2"}


def test_the_batch_is_bounded(make_listing, other_user, settings):
    settings.STAPEL_CLASSIFIED = {"CONTEXT_BATCH_LIMIT": 2}
    assert services.conversation_contexts(
        [str(_conv()) for _ in range(50)], viewer_id=other_user.pk
    ) == {}


# ── The HTTP surface ─────────────────────────────────────────────────


def test_the_api_binds_and_answers_the_header(
    published_listing, other_user, client_for, profiles_double
):
    profiles_double["display_names"][str(published_listing.owner_id)] = "Ada"
    conversation = str(_conv())

    response = client_for(other_user).post(
        "/classified/api/v1/conversations",
        {"conversation_id": conversation, "listing_id": str(published_listing.pk)},
        format="json",
    )
    assert response.status_code == 201, response.data
    assert response.data["subject"]["listing"]["title"] == "Apple iPhone 13 Pro"
    assert response.data["counterparty"]["display_name"] == "Ada"

    read = client_for(other_user).get(f"/classified/api/v1/conversations/{conversation}")
    assert read.status_code == 200
    assert read.data["conversation_id"] == conversation

    batch = client_for(other_user).post(
        "/classified/api/v1/conversations/contexts",
        {"conversation_ids": [conversation, str(_conv())]},
        format="json",
    )
    assert batch.status_code == 200
    assert list(batch.data["items"]) == [conversation]
    assert len(batch.data["missing"]) == 1


def test_the_api_refuses_an_anonymous_caller(published_listing, client_for):
    response = client_for().post(
        "/classified/api/v1/conversations",
        {"conversation_id": str(_conv()), "listing_id": str(published_listing.pk)},
        format="json",
    )
    assert response.status_code in (401, 403)


def test_a_stranger_gets_the_same_404_as_a_nonexistent_thread(
    published_listing, other_user, client_for, db
):
    """Not a 403: a 403 confirms the id names a real thread, and the id is
    the only thing keeping a stranger's conversation unprobed."""
    from django.contrib.auth import get_user_model

    stranger = get_user_model().objects.create(
        username="mallory2", email="mallory2@example.com"
    )
    conversation = _bind(published_listing, other_user)

    mine = client_for(stranger).get(f"/classified/api/v1/conversations/{conversation}")
    nothing = client_for(stranger).get(f"/classified/api/v1/conversations/{_conv()}")
    assert mine.status_code == nothing.status_code == 404
    assert mine.data["localizable_error"] == nothing.data["localizable_error"]
