"""Blocking, enforced at the server — and the three states it can be in.

The block itself is stapel-profiles' (``UserRelationship``, status
``blocked``). What the fleet never had is a way for a SERVER to consult it:
profiles publishes four comm Functions and none answers "is there a block
between these two", so today every block in the fleet is enforced by a client
hiding a button. These tests pin the classified half of the closure — the
posture axis, what each state does, and the one thing that must never happen
(an outage reading as consent).
"""
import uuid

import pytest

from stapel_classified import blocks, services

pytestmark = pytest.mark.django_db


def _pair(a, b):
    return frozenset((str(a.pk), str(b.pk)))


# ── auto: the state the fleet is actually in ─────────────────────────


def test_with_no_provider_contact_proceeds_and_the_check_says_so(
    settings, published_listing, other_user
):
    """No provider registered: this deployment HAS no block store.

    Refusing every contact instead would take a marketplace offline over a
    function nobody in the fleet has written yet — so contact proceeds, and
    `manage.py check` prints W001 at every boot. The rule is "never degrade
    SILENTLY", not "never degrade".
    """
    from stapel_classified.checks import check_block_enforcement

    settings.STAPEL_CLASSIFIED = {"BLOCK_ENFORCEMENT": "auto"}
    services.bind_listing_conversation(
        conversation_id=uuid.uuid4(),
        listing_key=published_listing.pk,
        actor_id=other_user.pk,
    )
    assert [w.id for w in check_block_enforcement(None)] == ["stapel_classified.W001"]


def test_with_a_provider_a_block_refuses_contact(
    published_listing, other_user, user, blocks_double
):
    blocks_double["blocked"].add(_pair(other_user, user))

    with pytest.raises(services.ContactRefused):
        services.bind_listing_conversation(
            conversation_id=uuid.uuid4(),
            listing_key=published_listing.pk,
            actor_id=other_user.pk,
        )


def test_the_block_bites_in_either_direction(
    published_listing, other_user, user, blocks_double
):
    """A seller who blocked a buyer and a buyer who blocked a seller produce
    the same silence. Direction is never reported: naming the block turns a
    quiet boundary into a notification."""
    blocks_double["blocked"].add(frozenset((str(user.pk), str(other_user.pk))))
    assert blocks.is_blocked(other_user.pk, user.pk)
    assert blocks.is_blocked(user.pk, other_user.pk)


def test_an_unblocked_pair_is_let_through(published_listing, other_user, blocks_double):
    row = services.bind_listing_conversation(
        conversation_id=uuid.uuid4(),
        listing_key=published_listing.pk,
        actor_id=other_user.pk,
    )
    assert row.pk is not None


# ── the failure that must not be silent ──────────────────────────────


def test_a_provider_that_fails_answers_503_not_allowed(
    published_listing, other_user, blocks_double
):
    """An outage is not consent.

    A registered provider that raises is the one case where "let them
    through" would be indistinguishable from "nobody blocked anybody" — and
    it is exactly the shape that made a live product poll for months while
    its sockets were "done".
    """
    blocks_double["fail"] = True

    with pytest.raises(blocks.BlockCheckUnavailable):
        services.bind_listing_conversation(
            conversation_id=uuid.uuid4(),
            listing_key=published_listing.pk,
            actor_id=other_user.pk,
        )


def test_the_api_turns_that_into_a_503(
    published_listing, other_user, client_for, blocks_double
):
    blocks_double["fail"] = True
    response = client_for(other_user).post(
        "/classified/api/v1/conversations",
        {
            "conversation_id": str(uuid.uuid4()),
            "listing_id": str(published_listing.pk),
        },
        format="json",
    )
    assert response.status_code == 503
    assert response.data["localizable_error"] == "error.503.classified_blocks_unavailable"


def test_the_api_refusal_does_not_say_who_blocked_whom(
    published_listing, other_user, user, client_for, blocks_double
):
    blocks_double["blocked"].add(_pair(other_user, user))
    response = client_for(other_user).post(
        "/classified/api/v1/conversations",
        {
            "conversation_id": str(uuid.uuid4()),
            "listing_id": str(published_listing.pk),
        },
        format="json",
    )
    assert response.status_code == 403
    assert response.data["localizable_error"] == "error.403.classified_contact_refused"
    body = str(response.data).lower()
    assert "block" not in body


# ── required / off ───────────────────────────────────────────────────


def test_required_without_a_provider_is_a_boot_error(settings):
    from stapel_classified.checks import check_block_enforcement

    settings.STAPEL_CLASSIFIED = {"BLOCK_ENFORCEMENT": "required"}
    findings = check_block_enforcement(None)
    assert [f.id for f in findings] == ["stapel_classified.E002"]


def test_required_without_a_provider_refuses_contact_at_runtime(
    published_listing, other_user, settings
):
    """Declared required and not there: 503, never a quiet pass."""
    settings.STAPEL_CLASSIFIED = {"BLOCK_ENFORCEMENT": "required"}
    with pytest.raises(blocks.BlockCheckUnavailable):
        services.bind_listing_conversation(
            conversation_id=uuid.uuid4(),
            listing_key=published_listing.pk,
            actor_id=other_user.pk,
        )


def test_required_with_a_provider_is_clean(settings, blocks_double):
    from stapel_classified.checks import check_block_enforcement

    settings.STAPEL_CLASSIFIED = {"BLOCK_ENFORCEMENT": "required"}
    assert check_block_enforcement(None) == []


def test_off_is_a_disclosed_statement(
    published_listing, other_user, user, settings, blocks_double
):
    from stapel_classified.checks import check_block_enforcement

    settings.STAPEL_CLASSIFIED = {"BLOCK_ENFORCEMENT": "off"}
    blocks_double["blocked"].add(_pair(other_user, user))

    # It really is off — the block does not bite…
    assert not blocks.is_blocked(other_user.pk, user.pk)
    # …and the deployment is told, at every boot.
    assert [w.id for w in check_block_enforcement(None)] == ["stapel_classified.W002"]


def test_an_unknown_posture_is_refused(settings):
    from stapel_classified.checks import check_block_enforcement

    settings.STAPEL_CLASSIFIED = {"BLOCK_ENFORCEMENT": "sometimes"}
    assert [f.id for f in check_block_enforcement(None)] == ["stapel_classified.E001"]


# ── what a block is NOT ──────────────────────────────────────────────


def test_a_block_does_not_delete_the_thread(
    published_listing, other_user, user, blocks_double, profiles_double
):
    """Blocking someone must not silently destroy the history with them.

    The refusal is about NEW contact; an existing thread keeps rendering, so
    both sides can still read what was said (and quote it in a report, which
    is usually what a block is accompanied by).
    """
    conversation = uuid.uuid4()
    services.bind_listing_conversation(
        conversation_id=conversation,
        listing_key=published_listing.pk,
        actor_id=other_user.pk,
    )
    blocks_double["blocked"].add(_pair(other_user, user))

    context = services.conversation_context(conversation, viewer_id=other_user.pk)
    assert context["subject"]["listing"]["title"] == "Apple iPhone 13 Pro"
