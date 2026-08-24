"""Complaints from a marketplace, landing in the queue that already exists.

Four things a user of a classified product must be able to report: a listing,
a review, a SELLER and a MESSAGE. The first two were already declared here;
the last two are what this wave adds, and each needed a different answer
because the fleet serves their content differently:

- a **seller** has no ``profiles.moderation_content`` anywhere — so this
  composite serves the marketplace-shaped answer itself (display name,
  rating, the seller's own id as author);
- a **message** has no owner at all: stapel-chat stores it and serves nothing,
  so the report carries the reporter's attestation (stapel-moderation 0.2.0's
  evidence seam) and only the two people in the thread may file one.

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


def test_a_party_may_report_a_message_with_their_own_snapshot(
    published_listing, other_user, user
):
    from stapel_moderation import services as moderation

    conversation = _bind(published_listing, other_user)
    target_key = f"{conversation}:{uuid.uuid4()}"

    report, case = moderation.submit_report(
        target_type="chat_message",
        target_key=target_key,
        reporter_id=other_user.pk,
        reason_code="off_platform_payment",
        evidence={
            "text": "Send the deposit to my card, we settle off-site.",
            "author_id": str(user.pk),
            "conversation_id": str(conversation),
        },
    )
    assert case.target_type == "chat_message"
    assert report.evidence["text"].startswith("Send the deposit")

    content = moderation.fetch_content("chat_message", target_key)
    # Marked as an attestation, always: nobody in the fleet can confirm who
    # wrote a message no service serves.
    assert content.extra["source"] == "evidence"
    assert content.extra["verified"] is False


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
            evidence={"text": "whatever"},
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
                evidence={"text": "whatever"},
            )


def test_a_message_report_with_no_snapshot_is_refused(
    published_listing, other_user
):
    """An evidence-based target with no attestation has nothing to show a
    moderator, and 404 is the honest answer: nothing is down, there is
    nothing to look at."""
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

    conversation = _bind(published_listing, other_user)
    moderation.submit_report(
        target_type="chat_message",
        target_key=f"{conversation}:{uuid.uuid4()}",
        reporter_id=other_user.pk,
        reason_code="harassment",
        description="Threats.",
        evidence={"text": "…", "author_id": str(user.pk)},
    )
    blocks_double["blocked"].add(frozenset((str(other_user.pk), str(user.pk))))

    context = services.conversation_context(conversation, viewer_id=other_user.pk)
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
