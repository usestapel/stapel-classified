"""The two moderation target types, end to end against real targets.

stapel-moderation ships ``BUILTIN_TARGET_TYPES = {}``: it knows what a case
is and nothing about what a listing or a review is. The composite declares
both, and the one claim its own unit tests cannot make — "resolving a case
changes the target" — is exactly what can be checked here, because both
consumers are in the process.
"""
import pytest

pytestmark = pytest.mark.django_db


def _publish(listing):
    from stapel_listings.services.publish import publish_listing

    publish_listing(listing)
    return listing


# ── the declaration ──────────────────────────────────────────────────


def test_both_target_types_resolve_with_a_content_function():
    from stapel_moderation.registry import resolve_policy

    listing = resolve_policy("listing")
    assert listing["gate"] == "pre"
    assert listing["content_function"] == "listings.moderation_content"
    assert listing["id_field"] == "listing_id"
    assert listing["verdict_event"] == "moderation.completed"
    assert listing["notification_types"] == {"content_blocked": "listing_blocked"}

    review = resolve_policy("review")
    assert review["gate"] == "post"
    assert review["content_function"] == "reviews.moderation_content"
    assert review["id_field"] == "review_id"
    assert review["media"] is False


def test_no_profile_target_is_declared():
    """A target whose content function nobody serves is a W006, not a plan.

    stapel-profiles is not a member of this composite, so declaring
    ``profile`` would put a policy in the registry pointing at
    ``profiles.moderation_content`` — unreachable, and the exact
    "declared but not connected" shape this module exists to catch.

    ``seller`` is NOT that. It is the marketplace's own notion of a
    counterparty and this package serves its content itself
    (``classified.seller_content``), which is the whole difference: the
    content function has a provider in the process.
    """
    from stapel_moderation.registry import get_target_types

    declared = set(get_target_types())
    assert declared == {"listing", "review", "seller", "chat_message"}
    assert "profile" not in declared


def test_the_seller_target_serves_its_own_content():
    from stapel_core.comm import call, function_unreachable_reason
    from stapel_moderation.registry import resolve_policy

    policy = resolve_policy("seller")
    assert policy["content_function"] == "classified.seller_content"
    assert policy["id_field"] == "seller_id"
    # Declared and CONNECTED: the provider is this package.
    assert not function_unreachable_reason("classified.seller_content")

    answer = call("classified.seller_content", {"seller_id": "u-1"})
    # The seller authors their own storefront — this is what makes
    # "you cannot report yourself" answerable without trusting a client.
    assert answer["author_id"] == "u-1"


def test_the_chat_message_target_is_evidence_based():
    """No module in the fleet serves a chat message's content, so a report
    carries the reporter's snapshot — stapel-moderation 0.2.0's evidence
    seam, which exists for exactly this shape of target."""
    from stapel_moderation.registry import resolve_policy

    policy = resolve_policy("chat_message")
    assert policy["evidence"] is True
    assert policy["content_function"] == ""
    # A message cannot be taken down by anyone but chat, and chat consumes no
    # verdict: the consequence of a case about a message is a Sanction.
    assert policy["verdict_event"] is None


def test_the_marketplace_reasons_merge_over_the_universal_ones():
    """An open registry, exercised: the vertical's codes ride on top of the
    shipped taxonomy, and the shipped ones are still there."""
    from stapel_moderation.registry import get_reasons, reasons_for_target

    reasons = get_reasons()
    assert reasons["prohibited_item"]["severity"] == 4
    assert reasons["already_sold"]["severity"] == 0
    assert "spam" in reasons  # the built-in taxonomy survives the merge

    listing = set(reasons_for_target("listing"))
    assert {"prohibited_item", "misleading_price", "already_sold"} <= listing
    # A complaint about goods has no meaning against a person.
    assert "misleading_price" not in set(reasons_for_target("seller"))
    assert "impersonation" in set(reasons_for_target("seller"))


def test_both_content_functions_are_reachable():
    from stapel_core.comm import function_unreachable_reason

    assert not function_unreachable_reason("listings.moderation_content")
    assert not function_unreachable_reason("reviews.moderation_content")


def test_intake_topics_are_subscribed():
    """Declaring a target type is what wires its intake — no host code.

    ``register_target_type`` / ``ready()`` subscribe every ``intake_events``
    topic, so the composite's two policies are the whole configuration.
    """
    from stapel_core.comm.registry import action_registry

    for topic in ("listing.submitted", "reviews.review.published"):
        assert action_registry.handlers(topic), topic


def test_review_reason_allowlist_is_a_subset_of_the_taxonomy():
    """Every reason offered for a review exists, and the dropped two do not.

    A reason code the registry does not know is moderation.E006 — a complaint
    form option that always answers 400.
    """
    from stapel_moderation.registry import get_reasons, reasons_for_target

    known = set(get_reasons())
    offered = set(reasons_for_target("review"))
    assert offered <= known
    assert {"wrong_category", "counterfeit"} & offered == set()
    assert "spam" in offered

    # A listing keeps the whole taxonomy, minus the system verdict reasons.
    listing_offered = set(reasons_for_target("listing"))
    assert {"wrong_category", "counterfeit"} <= listing_offered
    assert "screening_unavailable" not in listing_offered


# ── listing: submit -> case -> verdict -> the listing moves ──────────


def test_publishing_opens_a_pre_publication_case(make_listing):
    """``listing.submitted`` is the intake, and it is the composite that said
    so. Nothing in this test calls into stapel-moderation."""
    from stapel_moderation.models import Case, CaseOrigin

    listing = _publish(make_listing())

    case = Case.objects.get(target_type="listing", target_key=str(listing.pk))
    assert case.origin == CaseOrigin.SUBMISSION
    listing.refresh_from_db()
    # gate="pre": nothing is public until a verdict arrives.
    assert listing.status == "pending"


def test_a_report_on_a_listing_round_trips_to_a_case(published_listing, other_user):
    """Report -> case -> verdict -> the LISTING is blocked.

    The full loop across three modules: moderation reads the target through
    ``listings.moderation_content`` (which is how it learns who the author
    is, and therefore who a sanction would be about), the verdict is emitted
    as ``moderation.completed``, and stapel-listings' own consumer applies
    it. Nothing here touches ``Listing.status`` directly.
    """
    from stapel_moderation import services as moderation
    from stapel_moderation.models import CaseOrigin, CaseState

    report, case = moderation.submit_report(
        target_type="listing",
        target_key=str(published_listing.pk),
        reporter_id=other_user.pk,
        reason_code="counterfeit",
    )
    # The listing already carries a case from its own submission, so the
    # complaint JOINS it rather than opening a second one — one target, one
    # audit trail, whatever the door.
    assert case.origin == CaseOrigin.SUBMISSION
    assert case.target_type == "listing"
    # The content read is what identified the author — the sanction ladder
    # and the statement of reasons both hang off it.
    assert str(case.subject_user_id) == str(published_listing.owner_id)
    assert report.reason_code == "counterfeit"

    moderation.resolve_case(case, decision="rejected", reason_code="counterfeit")

    case.refresh_from_db()
    assert case.state == CaseState.RESOLVED

    published_listing.refresh_from_db()
    assert published_listing.status == "blocked"
    assert published_listing.moderation_status == "rejected"


def test_a_verdict_on_a_listing_also_leaves_the_search_index(published_listing, other_user):
    """One verdict, two consumers: the listing is blocked AND unfindable.

    This is the composite's whole reason to exist in one assertion — three
    modules that each know only their own half, agreeing without any of them
    importing another.
    """
    from django.test import Client

    from stapel_moderation import services as moderation

    _report, case = moderation.submit_report(
        target_type="listing",
        target_key=str(published_listing.pk),
        reporter_id=other_user.pk,
        reason_code="counterfeit",
    )
    moderation.resolve_case(case, decision="rejected", reason_code="counterfeit")

    body = Client().get("/search/api/v1/query", {"type": "listing"}).json()
    assert body["items"] == []


# ── listings 0.5.0: a live re-publish rides the moderation axis alone ─


def test_a_live_republish_stays_visible_while_rescreened(published_listing):
    """Editing a PUBLISHED listing must not repeat the pre-0.5.0 takedown.

    listings 0.5.0 (CHANGELOG): re-publishing a live listing keeps
    ``status == "published"`` — only ``moderation_status`` moves back to
    ``pending`` — so the edit stays visible while a fresh case is worked,
    instead of the listing silently vanishing from every public read for as
    long as re-moderation takes. Both consumers in this composite (search's
    ``visible_statuses`` and this test's own read of ``Listing.status``) see
    the same thing: still there.
    """
    from django.test import Client

    from stapel_listings.services.publish import publish_listing
    from stapel_moderation.models import Case, OPEN_STATES

    published_listing.title_draft = "Apple iPhone 13 Pro Max"
    publish_listing(published_listing)
    published_listing.refresh_from_db()

    # The lifecycle did not move — only the moderation axis did.
    assert published_listing.status == "published"
    assert published_listing.moderation_status == "pending"

    # A fresh case was opened (the submission case was already RESOLVED by
    # the `published_listing` fixture's own approval) and it is still live.
    case = Case.objects.get(
        target_type="listing", target_key=str(published_listing.pk), state__in=OPEN_STATES
    )
    assert case.state in OPEN_STATES

    # Still findable: the search source's `visible_statuses` is built from
    # `INDEXED_STATUSES`, and `published` never left it.
    body = Client().get("/search/api/v1/query", {"type": "listing"}).json()
    assert {item["key"] for item in body["items"]} == {str(published_listing.pk)}


def test_a_rejecting_verdict_on_a_republish_still_takes_it_down(published_listing):
    """The re-publish itself is not the takedown — a rejecting verdict is.

    Continuing the scenario above: once the fresh case resolves ``rejected``,
    the listing goes down through the same ``published -> blocked`` edge a
    report-driven takedown uses, and both consumers (status, search) agree
    again.
    """
    from django.test import Client

    from stapel_listings.services.publish import publish_listing
    from stapel_moderation import services as moderation
    from stapel_moderation.models import Case, CaseState, OPEN_STATES

    publish_listing(published_listing)
    published_listing.refresh_from_db()
    assert published_listing.status == "published"  # still up, per the test above

    case = Case.objects.get(
        target_type="listing", target_key=str(published_listing.pk), state__in=OPEN_STATES
    )
    moderation.resolve_case(case, decision="rejected", reason_code="counterfeit")
    case.refresh_from_db()
    assert case.state == CaseState.RESOLVED

    published_listing.refresh_from_db()
    assert published_listing.status == "blocked"
    assert published_listing.moderation_status == "rejected"

    body = Client().get("/search/api/v1/query", {"type": "listing"}).json()
    assert body["items"] == []


def test_dismissing_a_report_leaves_the_listing_alone(published_listing, other_user):
    from stapel_moderation import services as moderation

    _report, case = moderation.submit_report(
        target_type="listing",
        target_key=str(published_listing.pk),
        reporter_id=other_user.pk,
        reason_code="spam",
    )
    moderation.resolve_case(case, decision="dismissed")

    published_listing.refresh_from_db()
    assert published_listing.status == "published"


# ── review: publish -> case -> verdict -> the review is hidden ───────


def test_a_review_round_trips_to_a_case_and_back(published_listing, other_user):
    """The same loop on the other target type, with the other consumer.

    Post-moderation: the review is live from the start and the verdict is a
    takedown. That the two target names stay disjoint is what keeps this
    verdict off the listing that shares its key.
    """
    from stapel_moderation import services as moderation
    from stapel_moderation.models import Case
    from stapel_reviews import services as reviews

    review = reviews.create_review(
        target_type="listing",
        target_key=str(published_listing.pk),
        author=other_user,
        rating=1,
        body="Total nonsense, ignore this seller.",
    )
    assert review.status == "published"

    # reviews.review.published is the declared intake for the review type.
    case = Case.objects.get(target_type="review", target_key=str(review.pk))

    moderation.resolve_case(case, decision="rejected", reason_code="offensive")

    review.refresh_from_db()
    assert review.status == "hidden"

    # And the listing that shares nothing but a numeric key is untouched.
    published_listing.refresh_from_db()
    assert published_listing.status == "published"
