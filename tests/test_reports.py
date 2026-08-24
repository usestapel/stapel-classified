"""Complaints from a marketplace, landing in the queue that already exists.

Four things a user of a classified product must be able to report: a listing,
a review, a SELLER and a MESSAGE. The first two were already declared here;
the last two are what this wave adds, and each needed a different answer
because the fleet serves their content differently:

- a **seller** has no ``profiles.moderation_content`` anywhere — so this
  composite serves the marketplace-shaped answer itself (display name,
  rating, the seller's own id as author);
- a **message** is served by its owner since stapel-chat 0.5.0
  (``chat.moderation_content``), keyed by this composite's
  ``<conversation_id>:<message_id>``, and only the two people in the thread
  may file one. It was evidence-based until then — the reporter's own
  snapshot, stamped unverified — because nobody served a message at all.

And one negative claim, asserted rather than promised: this package holds no
queue of its own.
"""
import uuid

import pytest

from stapel_classified import services

pytestmark = pytest.mark.django_db


def _bind(listing, buyer):
    conversation = uuid.uuid4()
    services.bind_listing_conversation(
        conversation_id=conversation, listing_key=listing.pk, actor_id=buyer.pk
    )
    return conversation


def _thread(listing, buyer, seller, *, body="Send the deposit to my card."):
    """A REAL chat thread about ``listing``, bound here, one message in it.

    The message is the SELLER's, so the buyer reporting it is not reporting
    themselves. Returns the conversation, the message, and the composite key
    a report names it by.
    """
    from stapel_chat import services as chat

    conversation = chat.create_direct(owner=buyer, other_user_id=seller.pk)
    services.bind_listing_conversation(
        conversation_id=conversation.id, listing_key=listing.pk, actor_id=buyer.pk
    )
    message = chat.post_message(conversation=conversation, sender=seller, body=body)
    return conversation, message, f"{conversation.id}:{message.id}"


# ── There is exactly one queue, and it is moderation's ───────────────


def test_this_package_owns_no_queue():
    """A composite that grew its own Case table would be the second answer to
    "where do complaints live" — the defect stapel-moderation was built to
    end. The join table is the only model here."""
    from django.apps import apps

    models = {m.__name__ for m in apps.get_app_config("classified").get_models()}
    assert models == {"ConversationSubject"}


# ── Reporting a listing (already declared, still true) ───────────────


def test_a_listing_report_opens_a_case_with_the_marketplace_reason(
    published_listing, other_user
):
    from stapel_moderation import services as moderation

    report, case = moderation.submit_report(
        target_type="listing",
        target_key=str(published_listing.pk),
        reporter_id=other_user.pk,
        reason_code="prohibited_item",
    )
    assert case.target_type == "listing"
    assert case.severity == 4
    assert str(case.subject_user_id) == str(published_listing.owner_id)
    assert report.evidence == {}  # a served target needs no attestation


# ── Reporting a seller ───────────────────────────────────────────────


def test_a_seller_report_reads_the_seller_from_this_package(
    published_listing, other_user, user, profiles_double
):
    from stapel_moderation import services as moderation

    profiles_double["display_names"][str(user.pk)] = "Ada Lovelace"
    _report, case = moderation.submit_report(
        target_type="seller",
        target_key=str(user.pk),
        reporter_id=other_user.pk,
        reason_code="impersonation",
        description="Claims to be the official store.",
    )
    assert case.target_type == "seller"
    # The subject came from the content function, not from anything the
    # reporter sent — which is what stops a complaint from naming a stranger.
    assert str(case.subject_user_id) == str(user.pk)

    content = moderation.fetch_content("seller", str(user.pk))
    assert content.title == "Ada Lovelace"
    assert content.author_id == str(user.pk)


def test_you_cannot_report_yourself_as_a_seller(published_listing, user):
    from stapel_moderation import services as moderation

    with pytest.raises(moderation.OwnContent):
        moderation.submit_report(
            target_type="seller",
            target_key=str(user.pk),
            reporter_id=user.pk,
            reason_code="fraud",
            description="…",
        )


# ── Reporting a chat message ─────────────────────────────────────────


def test_a_party_may_report_a_message_and_the_platform_reads_it(
    published_listing, other_user, user
):
    """The composite key travels whole, and what comes back is the message.

    Both halves matter and both are used: this package answers WHO may file
    off the conversation half, and chat answers WHAT was said off the message
    half — under chat's own id spelling, ``message_id``.
    """
    from stapel_moderation import services as moderation

    conversation, message, target_key = _thread(published_listing, other_user, user)

    report, case = moderation.submit_report(
        target_type="chat_message",
        target_key=target_key,
        reporter_id=other_user.pk,
        reason_code="off_platform_payment",
    )
    assert case.target_type == "chat_message"
    # No attestation: a served target needs none, and moderation refuses one
    # (see the next test).
    assert report.evidence == {}
    # What an attestation could never establish: the case names the message's
    # real author, which is who a Sanction can be issued against.
    assert str(case.subject_user_id) == str(user.pk)

    content = moderation.fetch_content("chat_message", target_key)
    assert content.text == "Send the deposit to my card."
    assert content.author_id == str(user.pk)
    assert content.extra["conversation_id"] == str(conversation.id)
    # A platform read, not a quote: nothing here is stamped unverified.
    assert "source" not in content.extra

    # And it is read LIVE — an edit after the complaint is what a moderator
    # sees, which is the whole reason the content is fetched and not stored.
    from stapel_chat import services as chat

    chat.edit_message(message=message, editor=user, body="Ignore that, sorry.")
    assert moderation.fetch_content("chat_message", target_key).text == (
        "Ignore that, sorry."
    )


def test_a_snapshot_is_refused_now_that_the_message_itself_is_served(
    published_listing, other_user, user
):
    """The inverse of what this test asserted while the target was
    evidence-based: a reporter's snapshot next to a live content function is
    a second, staler answer, and moderation refuses it rather than keeping
    two versions of what was said (``moderation_evidence_invalid``)."""
    from stapel_moderation import services as moderation

    _conversation, _message, target_key = _thread(published_listing, other_user, user)

    with pytest.raises(ValueError, match="evidence_invalid"):
        moderation.submit_report(
            target_type="chat_message",
            target_key=target_key,
            reporter_id=other_user.pk,
            reason_code="off_platform_payment",
            evidence={"text": "what I say they said"},
        )


def test_a_message_quoted_under_the_wrong_conversation_is_not_the_target(
    published_listing, other_user, user
):
    """Both halves of the composite key must agree.

    The reporter IS a party of the conversation they named, so this package
    lets the report through — and chat still refuses, because the message is
    not in that thread. Mislabelling somebody else's thread buys nothing.
    """
    from stapel_chat import services as chat
    from stapel_moderation import services as moderation

    _conversation, message, _key = _thread(published_listing, other_user, user)
    other_thread = chat.create_group(owner=other_user)
    services.bind_listing_conversation(
        conversation_id=other_thread.id,
        listing_key=published_listing.pk,
        actor_id=other_user.pk,
    )

    with pytest.raises(moderation.TargetNotFound):
        moderation.submit_report(
            target_type="chat_message",
            target_key=f"{other_thread.id}:{message.id}",
            reporter_id=other_user.pk,
            reason_code="spam",
        )


def test_an_outsider_cannot_report_a_message_from_a_thread_they_are_not_in(
    published_listing, other_user, db
):
    """The whole reason a message's moderation key carries its conversation.

    moderation's fail-open default for a missing ``can_report`` is right for
    a public listing and wrong for a private thread — so the policy names a
    callback, and this package is the only one in the fleet that can answer
    it.
    """
    from django.contrib.auth import get_user_model
    from stapel_moderation import services as moderation

    stranger = get_user_model().objects.create(
        username="mallory3", email="mallory3@example.com"
    )
    conversation = _bind(published_listing, other_user)

    with pytest.raises(moderation.CannotReport):
        moderation.submit_report(
            target_type="chat_message",
            target_key=f"{conversation}:{uuid.uuid4()}",
            reporter_id=stranger.pk,
            reason_code="spam",
        )


def test_a_malformed_or_unbound_message_key_fails_closed(other_user):
    from stapel_moderation import services as moderation

    for target_key in (
        "not-a-composite-key",
        f"{uuid.uuid4()}:{uuid.uuid4()}",  # a conversation nobody bound
    ):
        with pytest.raises(moderation.CannotReport):
            moderation.submit_report(
                target_type="chat_message",
                target_key=target_key,
                reporter_id=other_user.pk,
                reason_code="spam",
            )


def test_a_message_chat_has_no_copy_of_is_a_404_not_a_503(
    published_listing, other_user
):
    """A deleted, erased or invented message is GONE, not unavailable.

    chat raises its ``MessageNotFound`` (a ``LookupError`` — the
    ``*.moderation_content`` family's spelling), and moderation must tell
    that apart from "the owner could not answer", or a reporter is told their
    target does not exist because a sibling service restarted.
    """
    from stapel_moderation import services as moderation

    conversation = _bind(published_listing, other_user)
    with pytest.raises(moderation.TargetNotFound):
        moderation.submit_report(
            target_type="chat_message",
            target_key=f"{conversation}:{uuid.uuid4()}",
            reporter_id=other_user.pk,
            reason_code="spam",
        )


def test_the_report_and_the_block_are_two_calls_and_neither_undoes_the_other(
    published_listing, other_user, user, blocks_double
):
    """A report usually accompanies a block. They stay separate acts against
    separate owners — moderation queues the complaint, profiles records the
    boundary — and the thread survives both."""
    from stapel_moderation import services as moderation

    conversation, _message, target_key = _thread(published_listing, other_user, user)
    moderation.submit_report(
        target_type="chat_message",
        target_key=target_key,
        reporter_id=other_user.pk,
        reason_code="harassment",
        description="Threats.",
    )
    blocks_double["blocked"].add(frozenset((str(other_user.pk), str(user.pk))))

    context = services.conversation_context(conversation.id, viewer_id=other_user.pk)
    assert context["subject"]["listing"]["title"] == "Apple iPhone 13 Pro"


# ── The taxonomy a client renders ────────────────────────────────────


def test_the_policy_disclosure_offers_the_marketplace_reasons(client_for):
    """The reason list a report form draws comes from moderation's public
    disclosure, narrowed per target type — no second list to keep in step."""
    response = client_for().get("/moderation/api/v1/policy?target_type=listing")
    assert response.status_code == 200
    codes = {r["code"] for r in response.data["reasons"]}
    assert {"prohibited_item", "misleading_price", "already_sold"} <= codes
    assert "impersonation" not in codes  # listing-inapplicable, per the policy
