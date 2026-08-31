"""The conversation header: what this chat is about, and with whom.

The owner opened the live product's chat and found it "unclear with whom and
about what" — no short listing card, no seller data. Every test here is a
sentence from that finding, run against REAL member modules: a real listing
moved through its real publication pipeline, a real stapel-chat thread carrying
a real subject, the real ``listings.search_documents`` behind the card, the
real profiles behind the person. A mock on either side of a seam is exactly
what cannot prove a seam.

Since 0.3.2 the subject and the parties are read from chat rather than from a
table this package kept, so the threads below are created by calling chat the
way a client does.
"""
import uuid

import pytest

from stapel_classified import services

pytestmark = pytest.mark.django_db


def _conv():
    return uuid.uuid4()


def _confirm(conversation, listing, buyer):
    return services.confirm_listing_conversation(
        conversation_id=conversation.id,
        listing_key=listing.pk,
        actor_id=buyer.pk,
    )


def _publish(listing):
    from stapel_listings.services.publish import publish_listing

    publish_listing(listing)
    listing.apply_moderation("approved")
    listing.refresh_from_db()
    return listing


# ── Confirming a contact ─────────────────────────────────────────────


def test_a_conversation_carries_a_resolvable_listing(
    published_listing, other_user, user, thread
):
    context = _confirm(thread(other_user, user, published_listing), published_listing, other_user)

    assert context["subject"]["type"] == "listing"
    assert context["subject"]["key"] == str(published_listing.pk)
    assert context["subject"]["meta_status"] == "ok"
    assert context["counterparty"]["user_id"] == str(published_listing.owner_id)


def test_confirming_twice_is_the_same_answer_and_creates_nothing(
    published_listing, other_user, user, thread
):
    """A retry, a second tab, an at-least-once client: one answer either way.

    Idempotence used to be a database constraint here (one row per
    conversation+subject, first writer wins). It is now a property of the call
    having no side effect at all — the thread is chat's and this only reads it.
    """
    conversation = thread(other_user, user, published_listing)
    first = _confirm(conversation, published_listing, other_user)
    second = _confirm(conversation, published_listing, other_user)
    assert first == second


def test_you_cannot_open_a_buyer_conversation_on_your_own_listing(
    published_listing, user, other_user, thread
):
    with pytest.raises(services.OwnListing):
        _confirm(thread(user, other_user, published_listing), published_listing, user)


def test_a_contact_about_a_listing_nobody_serves_is_refused(other_user, user, thread):
    with pytest.raises(services.SubjectNotFound):
        services.confirm_listing_conversation(
            conversation_id=_conv(), listing_key="999999", actor_id=other_user.pk
        )


def test_a_conversation_chat_does_not_have_is_refused(
    published_listing, other_user
):
    with pytest.raises(services.ConversationNotBound):
        services.confirm_listing_conversation(
            conversation_id=_conv(),
            listing_key=published_listing.pk,
            actor_id=other_user.pk,
        )


def test_a_thread_about_another_listing_is_not_this_contact(
    make_listing, published_listing, other_user, user, thread
):
    """The claim that 0.3.x could not check, now checked.

    Until 0.3.2 the caller TOLD this module which listing a thread was about
    and the module wrote it down. Chat stores the subject now, so a request
    naming a different listing than the thread carries is a 404 rather than a
    relabelling of somebody's conversation.
    """
    other = _publish(make_listing(title_draft="Sony WH-1000XM4"))
    conversation = thread(other_user, user, published_listing)

    with pytest.raises(services.ConversationNotBound):
        _confirm(conversation, other, other_user)


def test_an_outsider_cannot_confirm_a_thread_they_are_not_in(
    published_listing, other_user, user, thread, db
):
    from django.contrib.auth import get_user_model

    stranger = get_user_model().objects.create(
        username="mallory0", email="mallory0@example.com"
    )
    conversation = thread(other_user, user, published_listing)

    with pytest.raises(services.NotAParty):
        _confirm(conversation, published_listing, stranger)


# ── The card ─────────────────────────────────────────────────────────


def test_the_header_carries_a_short_card_and_the_seller(
    published_listing, other_user, user, thread, display_name
):
    display_name(user, "Ada Lovelace")
    conversation = thread(other_user, user, published_listing)

    context = services.conversation_context(conversation.id, viewer_id=other_user.pk)
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
    published_listing, other_user, user, thread, display_name
):
    """One thread, two readings. The header a seller opens must not show the
    seller — the counterparty is whoever the reader is not."""
    display_name(other_user, "Grace Hopper")
    conversation = thread(other_user, user, published_listing)

    context = services.conversation_context(conversation.id, viewer_id=user.pk)
    assert context["counterparty"]["user_id"] == str(other_user.pk)
    assert context["counterparty"]["display_name"] == "Grace Hopper"
    assert context["viewer_role"] == "seller"


def test_a_sold_listing_still_has_a_header(published_listing, other_user, user, thread):
    """The moment a buyer is MOST confused is the one a public read hides.

    ``Listing.visible_to`` 404s anything not published — correct for a
    stranger, useless for the person standing in the conversation about it.
    The card answers ``unavailable`` with the real status instead.
    """
    conversation = thread(other_user, user, published_listing)
    published_listing.status = "sold"
    published_listing.save(update_fields=["status"])

    card = services.conversation_context(conversation.id, viewer_id=other_user.pk)[
        "subject"
    ]["listing"]
    assert card["state"] == "unavailable"
    assert card["status"] == "sold"
    assert card["title"] == "Apple iPhone 13 Pro"


def test_a_deleted_listing_answers_gone_rather_than_vanishing(
    published_listing, other_user, user, thread
):
    conversation = thread(other_user, user, published_listing)
    published_listing.delete()  # soft delete — the row keeps existing

    context = services.conversation_context(conversation.id, viewer_id=other_user.pk)
    card = context["subject"]["listing"]
    assert card["state"] == "gone"
    assert card["meta_reason"] == "listing_deleted"
    # And the conversation itself is still readable: blocking a thread's
    # header on a deleted listing would delete the conversation from the UI.
    assert card["listing_id"] == str(published_listing.pk)
    # A gone listing has no owner to be a party — the card already says so,
    # and the subject must not ALSO cry "owner not a party" about it.
    assert context["subject"]["meta_status"] == "ok"


def test_a_thread_whose_subject_belongs_to_neither_party_says_so(
    make_listing, other_user, user, thread, db
):
    """The one hole nothing in the fleet can close at creation time.

    Chat may not know what a listing is, so it cannot refuse a thread whose
    subject names a listing belonging to a third party. This module can only
    notice while rendering — so it renders, and says the header is degraded
    rather than showing a stranger's listing as if it were this contact's.
    """
    from django.contrib.auth import get_user_model

    outsider = get_user_model().objects.create(
        username="third", email="third@example.com"
    )
    listing = _publish(make_listing())  # owned by `user`
    conversation = thread(other_user, outsider, listing)

    context = services.conversation_context(conversation.id, viewer_id=other_user.pk)
    assert context["subject"]["meta_status"] == "partial"
    assert context["subject"]["meta_reason"] == "subject_owner_not_a_party"
    # It still renders: the card, and the person actually in the thread.
    assert context["subject"]["listing"]["title"] == "Apple iPhone 13 Pro"
    assert context["counterparty"]["user_id"] == str(outsider.pk)


def test_the_primary_image_carries_cdn_render_metadata(
    make_listing, other_user, user, thread, cdn_double
):
    listing = _publish(make_listing(images_draft=["product/abc"]))

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
    conversation = thread(other_user, user, listing)

    image = services.conversation_context(conversation.id, viewer_id=other_user.pk)[
        "subject"
    ]["listing"]["image"]
    assert image["ref"] == "product/abc"
    assert image["aspect"] == 1.5
    assert image["preview_kind"] == "blur"
    assert image["variants"][0]["tier"] == 240


def test_every_photo_in_the_gallery_carries_cdn_render_metadata(
    make_listing, other_user, user, thread, cdn_double
):
    """The gallery, not only its first frame — and in one call, not per photo.

    A header shows one thumbnail today, so the reason this is asserted here is
    the OTHER reader of the same builder: a SERP row that swipes. One builder
    means a card cannot describe three photos in search and one in chat.
    """
    refs = ["product/a", "product/b", "product/c"]
    listing = _publish(make_listing(images_draft=refs))
    for index, ref in enumerate(refs):
        cdn_double["items"][ref] = {
            "mime": "image/webp",
            "width": 1200,
            "height": 800,
            "aspect": 1.5,
            "preview_b64": f"data:image/webp;base64,{index}",
            "preview_kind": "blur",
            "variants": [
                {"tier": 240, "branch": "w", "url": "u", "width": 240, "height": 160}
            ],
            "meta_status": "ok",
        }
    conversation = thread(other_user, user, listing)

    card = services.conversation_context(conversation.id, viewer_id=other_user.pk)[
        "subject"
    ]["listing"]
    assert [image["ref"] for image in card["images"]] == refs
    assert all(image["aspect"] == 1.5 for image in card["images"])
    assert card["images"][2]["preview_b64"].endswith("2")
    # One answer, not two: the singular key IS the first element.
    assert card["image"] == card["images"][0]
    assert card["meta_status"] == "ok"
    # And one CDN round trip for the whole gallery, not one per photo.
    assert len(cdn_double["calls"]) == 1
    assert cdn_double["calls"][0]["refs"] == refs


def test_a_photo_the_cdn_does_not_know_degrades_that_slide_only(
    make_listing, other_user, user, thread, cdn_double
):
    """Degradation is per image and it is data — the rest of the strip draws."""
    listing = _publish(make_listing(images_draft=["product/a", "product/gone"]))
    cdn_double["items"]["product/a"] = {"aspect": 1.5, "meta_status": "ok"}
    cdn_double["missing"].append("product/gone")
    conversation = thread(other_user, user, listing)

    card = services.conversation_context(conversation.id, viewer_id=other_user.pk)[
        "subject"
    ]["listing"]
    assert card["images"][0]["meta_status"] == "ok"
    assert card["images"][1]["meta_status"] == "missing"
    assert card["images"][1]["ref"] == "product/gone"
    assert card["meta_status"] == "partial"
    assert card["meta_reason"] == "image_unknown_ref"


def test_an_unreachable_cdn_degrades_the_card_and_never_the_conversation(
    make_listing, other_user, user, thread
):
    """Degradation is data. No cdn provider is registered in this test."""
    listing = _publish(make_listing(images_draft=["product/abc"]))
    conversation = thread(other_user, user, listing)

    card = services.conversation_context(conversation.id, viewer_id=other_user.pk)[
        "subject"
    ]["listing"]
    assert card["meta_status"] == "partial"
    assert card["meta_reason"] == "cdn_unavailable"
    assert card["image"]["ref"] == "product/abc"
    # Every slide keeps its ref and says why it has no numbers — a strip that
    # cannot measure itself is still a strip a person can swipe.
    assert [image["ref"] for image in card["images"]] == ["product/abc"]
    assert card["images"][0]["meta_reason"] == "cdn_unavailable"
    assert card["title"] == "Apple iPhone 13 Pro"


def test_a_person_who_has_typed_no_name_is_still_a_person(
    published_listing, other_user, user, thread
):
    """profiles is mounted and answers; the seller simply has no display name.

    Not `partial`: the card is complete, it is the person who is blank. A
    frontend renders initials — the contract says so — and nothing here
    invents a placeholder name.
    """
    conversation = thread(other_user, user, published_listing)

    seller = services.conversation_context(conversation.id, viewer_id=other_user.pk)[
        "counterparty"
    ]
    assert seller["user_id"] == str(user.pk)
    assert seller["display_name"] == ""
    assert seller["avatar"] is None
    assert seller["rating"] is None  # never a fabricated zero


def test_a_rating_appears_once_seller_reviews_are_wired(
    published_listing, other_user, user, thread, settings
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

    conversation = thread(other_user, user, published_listing)
    seller = services.conversation_context(conversation.id, viewer_id=other_user.pk)[
        "counterparty"
    ]
    assert seller["rating"]["count"] == 2
    assert float(seller["rating"]["avg"]) == 4.5


# ── One thread per listing, which is the whole point of 0.3.2 ────────


def test_two_listings_between_the_same_two_people_are_two_threads(
    make_listing, other_user, user, thread
):
    """The arithmetic that used to force a many-subjects table, inverted.

    Through chat 0.5.x a direct thread was keyed by the participant PAIR, so
    one buyer and one seller had exactly ONE thread whatever they discussed;
    this composite kept every binding and rendered the newest, with the rest
    as `previous_subjects`. chat 0.6.0 put the subject into `direct_key`, so
    the second listing is its own thread with its own header — and
    `previous_subjects` is gone rather than always empty.
    """
    first = _publish(make_listing())
    second = _publish(make_listing(title_draft="Sony WH-1000XM4"))

    one = thread(other_user, user, first)
    two = thread(other_user, user, second)
    assert one.id != two.id

    contexts = services.conversation_contexts(
        [str(one.id), str(two.id)], viewer_id=other_user.pk
    )
    assert {c["subject"]["listing"]["title"] for c in contexts.values()} == {
        "Apple iPhone 13 Pro",
        "Sony WH-1000XM4",
    }
    assert "previous_subjects" not in contexts[str(one.id)]


def test_a_thread_about_nothing_in_particular_has_no_classified_header(
    other_user, user, db
):
    """chat's own category, not an error.

    Every conversation created before chat 0.6.0 is one of these, and a
    generic chat opens them forever. This composite has nothing to say about
    them, so they are absent from its answer rather than rendered blank.
    """
    from stapel_chat.services import create_direct

    conversation = create_direct(owner=other_user, other_user_id=user.pk)

    assert services.conversation_contexts(
        [str(conversation.id)], viewer_id=other_user.pk
    ) == {}
    with pytest.raises(services.ConversationNotBound):
        services.conversation_context(conversation.id, viewer_id=other_user.pk)


# ── Reading rights ───────────────────────────────────────────────────


def test_a_stranger_cannot_read_a_conversation_header(
    published_listing, other_user, user, thread, db
):
    from django.contrib.auth import get_user_model

    stranger = get_user_model().objects.create(
        username="mallory", email="mallory@example.com"
    )
    conversation = thread(other_user, user, published_listing)

    with pytest.raises(services.ConversationNotBound):
        services.conversation_context(conversation.id, viewer_id=stranger.pk)


def test_a_conversation_nobody_has_is_a_404(other_user):
    with pytest.raises(services.ConversationNotBound):
        services.conversation_context(_conv(), viewer_id=other_user.pk)


# ── When chat itself cannot be asked ─────────────────────────────────


def test_an_unreachable_chat_is_a_503_and_never_an_empty_inbox(
    other_user, settings
):
    """The one seam here with no degraded form.

    An empty page would be indistinguishable from "you are not a party to any
    of these" — a permission answer. A reader would take a chat outage for a
    boundary, which is the silent-degradation shape this fleet keeps paying
    for.
    """
    settings.STAPEL_CLASSIFIED = {
        "CONVERSATION_PARTICIPANTS_FUNCTION": "chat.nobody_serves_this"
    }
    with pytest.raises(services.ChatUnavailable):
        services.conversation_contexts([str(_conv())], viewer_id=other_user.pk)


def test_the_api_turns_an_unreachable_chat_into_a_503(
    other_user, client_for, settings
):
    settings.STAPEL_CLASSIFIED = {
        "CONVERSATION_PARTICIPANTS_FUNCTION": "chat.nobody_serves_this"
    }
    response = client_for(other_user).post(
        "/classified/api/v1/conversations/contexts",
        {"conversation_ids": [str(_conv())]},
        format="json",
    )
    assert response.status_code == 503
    assert response.data["localizable_error"] == "error.503.classified_chat_unavailable"


# ── The batch read the inbox makes ───────────────────────────────────


def test_the_inbox_resolves_a_page_in_one_pass(
    make_listing, other_user, user, thread
):
    conversations = []
    for index in range(3):
        listing = _publish(make_listing(title_draft=f"Item {index}"))
        conversations.append(thread(other_user, user, listing))

    contexts = services.conversation_contexts(
        [str(c.id) for c in conversations] + [str(_conv())], viewer_id=other_user.pk
    )
    assert len(contexts) == 3
    titles = {c["subject"]["listing"]["title"] for c in contexts.values()}
    assert titles == {"Item 0", "Item 1", "Item 2"}


def test_the_batch_is_bounded(other_user, settings):
    settings.STAPEL_CLASSIFIED = {"CONTEXT_BATCH_LIMIT": 2}
    assert services.conversation_contexts(
        [str(_conv()) for _ in range(50)], viewer_id=other_user.pk
    ) == {}


# ── The HTTP surface ─────────────────────────────────────────────────


def test_the_api_confirms_and_answers_the_header(
    published_listing, other_user, user, thread, client_for, display_name
):
    display_name(user, "Ada")
    conversation = str(thread(other_user, user, published_listing).id)

    response = client_for(other_user).post(
        "/classified/api/v1/conversations",
        {"conversation_id": conversation, "listing_id": str(published_listing.pk)},
        format="json",
    )
    # 200, not 201: nothing is created here any more.
    assert response.status_code == 200, response.data
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
    published_listing, other_user, user, thread, client_for, db
):
    """Not a 403: a 403 confirms the id names a real thread, and the id is
    the only thing keeping a stranger's conversation unprobed."""
    from django.contrib.auth import get_user_model

    stranger = get_user_model().objects.create(
        username="mallory2", email="mallory2@example.com"
    )
    conversation = thread(other_user, user, published_listing).id

    mine = client_for(stranger).get(f"/classified/api/v1/conversations/{conversation}")
    nothing = client_for(stranger).get(f"/classified/api/v1/conversations/{_conv()}")
    assert mine.status_code == nothing.status_code == 404
    assert mine.data["localizable_error"] == nothing.data["localizable_error"]
