"""Blocking, enforced at the server — and the three states it can be in.

The block itself is stapel-profiles' (``UserRelationship``, status
``blocked``); since profiles 0.16.0 a server can consult it through
``profiles.relationships``, and this composite asks at the one place a
classified contact begins. These tests pin the posture axis, what each state
does, and the one thing that must never happen (an outage reading as consent).

**Nothing here is a double.** stapel_profiles is mounted in this harness, so a
block is a real relationship row and the answer comes from profiles' real
provider. Through 0.3.1 this file registered its own ``profiles.relationships``
and asserted against it — a suite proving that its own fixture agreed with
itself, which is precisely the seam defect the fleet keeps shipping. The
default posture is ``required``, so a suite that could not reach a real
provider was not testing this module's default at all.
"""
import pytest

from stapel_classified import blocks, services

pytestmark = pytest.mark.django_db


def _contact(conversation, listing, actor):
    return services.confirm_listing_conversation(
        conversation_id=conversation.id,
        listing_key=listing.pk,
        actor_id=actor.pk,
    )


# ── required: the state a deployment with profiles is in ─────────────


def test_with_a_provider_a_block_refuses_contact(
    published_listing, other_user, user, thread, block
):
    block(user, other_user)  # the seller blocked the buyer

    with pytest.raises(services.ContactRefused):
        _contact(thread(other_user, user, published_listing), published_listing, other_user)


def test_the_block_bites_in_either_direction(published_listing, other_user, user, block):
    """A seller who blocked a buyer and a buyer who blocked a seller produce
    the same silence. Direction is stored (one row, one author) and never
    answered: naming the block turns a quiet boundary into a notification."""
    block(user, other_user)
    assert blocks.is_blocked(other_user.pk, user.pk)
    assert blocks.is_blocked(user.pk, other_user.pk)


def test_an_unblocked_pair_is_let_through(published_listing, other_user, user, thread):
    context = _contact(
        thread(other_user, user, published_listing), published_listing, other_user
    )
    assert context["subject"]["key"] == str(published_listing.pk)
    assert context["viewer_role"] == "buyer"


# ── the failure that must not be silent ──────────────────────────────


def test_a_provider_that_fails_answers_503_not_allowed(
    published_listing, other_user, user, thread, blocks_down
):
    """An outage is not consent.

    A registered provider that raises is the one case where "let them
    through" would be indistinguishable from "nobody blocked anybody" — and
    it is exactly the shape that made a live product poll for months while
    its sockets were "done".
    """
    with pytest.raises(blocks.BlockCheckUnavailable):
        _contact(thread(other_user, user, published_listing), published_listing, other_user)


def test_the_api_turns_that_into_a_503(
    published_listing, other_user, user, thread, client_for, blocks_down
):
    conversation = thread(other_user, user, published_listing)
    response = client_for(other_user).post(
        "/classified/api/v1/conversations",
        {
            "conversation_id": str(conversation.id),
            "listing_id": str(published_listing.pk),
        },
        format="json",
    )
    assert response.status_code == 503
    assert response.data["localizable_error"] == "error.503.classified_blocks_unavailable"


def test_the_api_refusal_does_not_say_who_blocked_whom(
    published_listing, other_user, user, thread, client_for, block
):
    block(user, other_user)
    conversation = thread(other_user, user, published_listing)
    response = client_for(other_user).post(
        "/classified/api/v1/conversations",
        {
            "conversation_id": str(conversation.id),
            "listing_id": str(published_listing.pk),
        },
        format="json",
    )
    assert response.status_code == 403
    assert response.data["localizable_error"] == "error.403.classified_contact_refused"
    body = str(response.data).lower()
    assert "block" not in body


# ── auto / required / off ────────────────────────────────────────────


def test_with_no_provider_contact_proceeds_and_the_check_says_so(
    settings, published_listing, other_user, user, thread, no_block_provider
):
    """No provider registered: this deployment HAS no block store.

    Refusing every contact instead would take a marketplace offline over a
    module it chose not to deploy — so contact proceeds, and `manage.py check`
    prints W001 at every boot. The rule is "never degrade SILENTLY", not
    "never degrade". This is the ONE posture that has to be constructed now
    (profiles is mounted), and constructing it is the honest way to assert it.
    """
    from stapel_classified.checks import check_block_enforcement

    settings.STAPEL_CLASSIFIED = {"BLOCK_ENFORCEMENT": "auto"}
    context = _contact(
        thread(other_user, user, published_listing), published_listing, other_user
    )
    assert context["subject"]["key"] == str(published_listing.pk)
    assert [w.id for w in check_block_enforcement(None)] == ["stapel_classified.W001"]


def test_required_without_a_provider_is_a_boot_error(settings, no_block_provider):
    from stapel_classified.checks import check_block_enforcement

    settings.STAPEL_CLASSIFIED = {"BLOCK_ENFORCEMENT": "required"}
    findings = check_block_enforcement(None)
    assert [f.id for f in findings] == ["stapel_classified.E002"]


def test_required_without_a_provider_refuses_contact_at_runtime(
    published_listing, other_user, user, thread, settings, no_block_provider
):
    """Declared required and not there: 503, never a quiet pass."""
    settings.STAPEL_CLASSIFIED = {"BLOCK_ENFORCEMENT": "required"}
    with pytest.raises(blocks.BlockCheckUnavailable):
        _contact(thread(other_user, user, published_listing), published_listing, other_user)


def test_required_with_a_provider_is_clean(settings):
    from stapel_classified.checks import check_block_enforcement

    settings.STAPEL_CLASSIFIED = {"BLOCK_ENFORCEMENT": "required"}
    assert check_block_enforcement(None) == []


def test_required_is_the_default_and_this_harness_meets_it():
    """The default posture, asserted against the real registry.

    0.3.1 flipped the default to "required" and its release died here: with
    no provider in the harness, most of the suite raised
    ``BlockCheckUnavailable``. The fix was the harness, not the default —
    which only means something if a test says the default is still required
    and that this deployment satisfies it.
    """
    from stapel_classified.conf import DEFAULTS, classified_settings

    assert DEFAULTS["BLOCK_ENFORCEMENT"] == blocks.ENFORCEMENT_REQUIRED
    assert classified_settings.BLOCK_ENFORCEMENT == blocks.ENFORCEMENT_REQUIRED
    assert blocks.provider_unreachable_reason() == ""


def test_off_is_a_disclosed_statement(published_listing, other_user, user, settings, block):
    from stapel_classified.checks import check_block_enforcement

    settings.STAPEL_CLASSIFIED = {"BLOCK_ENFORCEMENT": "off"}
    block(user, other_user)

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
    published_listing, other_user, user, thread, block, display_name
):
    """Blocking someone must not silently destroy the history with them.

    The refusal is about NEW contact; an existing thread keeps rendering, so
    both sides can still read what was said (and quote it in a report, which
    is usually what a block is accompanied by).
    """
    display_name(user, "Seller")
    conversation = thread(other_user, user, published_listing)
    block(user, other_user)

    context = services.conversation_context(conversation.id, viewer_id=other_user.pk)
    assert context["subject"]["listing"]["title"] == "Apple iPhone 13 Pro"
    assert context["counterparty"]["display_name"] == "Seller"


# ── The harness this module ships to its consumers ───────────────────


def test_the_shipped_fixtures_use_the_real_provider_where_profiles_is_mounted(
    block_provider,
):
    """`stapel_classified.testing` picks the honest backend by itself.

    A deployment with profiles gets real `UserRelationship` rows; one without
    gets a stated in-memory provider. The choice is not a preference — a suite
    that mocked the module it is proving a seam against would prove nothing,
    and a suite with no provider at all cannot run this module's default
    posture.
    """
    from stapel_classified.testing import profiles_is_mounted

    assert profiles_is_mounted()
    assert block_provider.backend == "profiles"


def test_the_memory_backend_answers_the_same_questions(
    published_listing, other_user, user, thread, no_block_provider
):
    """The branch THIS suite does not take, exercised anyway.

    A consumer without stapel-profiles runs on the in-memory provider, and an
    unexercised fallback is how a shipped harness rots. `no_block_provider`
    frees the Function name first — core's registry allows exactly one
    provider per name, which is the same reason there are no doubles here.
    """
    from stapel_classified import blocks
    from stapel_classified.testing import memory_block_provider

    with memory_block_provider() as store:
        assert store.backend == "memory"
        assert not blocks.is_blocked(other_user.pk, user.pk)

        store.block(user, other_user)
        assert blocks.is_blocked(other_user.pk, user.pk)  # either direction
        with pytest.raises(services.ContactRefused):
            _contact(thread(other_user, user, published_listing), published_listing, other_user)

        store.unblock(user, other_user)
        assert not blocks.is_blocked(other_user.pk, user.pk)

        # And an outage is still not consent.
        store.set_unavailable(True)
        with pytest.raises(blocks.BlockCheckUnavailable):
            blocks.is_blocked(other_user.pk, user.pk)

    # Unregistered on exit: the block store is the deployment's, not a test's.
    assert blocks.provider_unreachable_reason()
