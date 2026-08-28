"""Blocking across the composite stack — one door, and it is stapel-chat's.

The block itself is stapel-profiles' (``UserRelationship``, status
``blocked``); since profiles 0.16.0 a server can consult it through
``profiles.relationships``; and since stapel-chat 0.6.1 chat holds **both**
write doors a block has to close — opening a direct thread and sending into
one. This composite kept a pre-creation door of its own until 0.4.0 and no
longer does: what it keeps is one statement of product knowledge, the value
``STAPEL_CHAT["BLOCK_ENFORCEMENT"] = "required"`` in its preset.

So this file stopped asserting a posture of this package's own. It asserts
that the assembled composite ARMS chat's axis, and that the refusal lands
where chat puts it. Two axes for one fact was the defect: an operator turned
the one they knew about, the other stayed where it was, and behaviour was
decided by the one they had never heard of.

**Nothing here is a double.** stapel_profiles is mounted in this harness, so a
block is a real relationship row and the answer comes from profiles' real
provider — see the root conftest for why a suite that mocked either side of a
seam would prove nothing about it.
"""
import pytest
from stapel_chat.blocks import BlockCheckUnavailable
from stapel_chat.services import SendRefused

from stapel_classified import preset, services

pytestmark = pytest.mark.django_db


def _contact(conversation, listing, actor):
    return services.confirm_listing_conversation(
        conversation_id=conversation.id,
        listing_key=listing.pk,
        actor_id=actor.pk,
    )


def _confirm_over_http(client_for, actor, conversation, listing):
    return client_for(actor).post(
        "/classified/api/v1/conversations",
        {
            "conversation_id": str(conversation.id),
            "listing_id": str(listing.pk),
        },
        format="json",
    )


# ── required: the state this composite's preset puts a deployment in ──


def test_a_block_refuses_the_thread_through_the_composite_stack(
    published_listing, other_user, user, thread, block
):
    """The refusal in its new place.

    Through 0.3.x this raised ``services.ContactRefused`` from this package's
    own contact endpoint — a door that only covered clients which used it,
    and which could never cover the send path. chat 0.6.1 refuses at
    ``create_direct``, the one point every client passes, so a blocked buyer
    now never gets the thread at all.
    """
    block(user, other_user)  # the seller blocked the buyer

    with pytest.raises(SendRefused):
        thread(other_user, user, published_listing)


def test_the_block_bites_in_either_direction(published_listing, other_user, user, block):
    """A seller who blocked a buyer and a buyer who blocked a seller produce
    the same silence. Direction is stored (one row, one author) and never
    answered: naming the block turns a quiet boundary into a notification."""
    from stapel_chat import blocks

    block(user, other_user)
    assert blocks.is_blocked(other_user.pk, user.pk)
    assert blocks.is_blocked(user.pk, other_user.pk)


def test_an_unblocked_pair_is_let_through(published_listing, other_user, user, thread):
    context = _contact(
        thread(other_user, user, published_listing), published_listing, other_user
    )
    assert context["subject"]["key"] == str(published_listing.pk)
    assert context["viewer_role"] == "buyer"


# ── the failure that must not be silent, and the read it must not block ──


def test_a_new_thread_is_refused_while_the_provider_is_down(
    published_listing, other_user, user, thread, blocks_down
):
    """An outage is not consent.

    A registered provider that raises is the one case where "let them
    through" would be indistinguishable from "nobody blocked anybody" — and
    it is exactly the shape that made a live product poll for months while
    its sockets were "done". chat answers 503 on its own surface.
    """
    with pytest.raises(BlockCheckUnavailable):
        thread(other_user, user, published_listing)


def test_confirm_still_answers_200_while_the_provider_is_down(
    published_listing, other_user, user, thread, client_for, block_provider
):
    """The test that pins the deletion.

    ``confirm_listing_conversation`` takes a ``conversation_id``: it only ever
    runs on a thread that ALREADY EXISTS, which is history. Until 0.4.0 this
    package asked the block provider here anyway and answered 503 when it was
    down — an outage standing between a person and their own correspondence,
    which is precisely what chat 0.6.1 engineered away by consulting the
    provider on the create branch only. The check was not redundant, it was
    doctrinally wrong, and it is gone.
    """
    conversation = thread(other_user, user, published_listing)
    block_provider.set_unavailable(True)

    response = _confirm_over_http(
        client_for, other_user, conversation, published_listing
    )
    assert response.status_code == 200
    assert response.data["subject"]["key"] == str(published_listing.pk)


def test_confirm_does_not_refuse_a_blocked_pair_that_already_has_history(
    published_listing, other_user, user, thread, client_for, block
):
    """A block refuses NEW contact; it never takes back what was already said.

    The thread exists, then one of them blocks the other. Reading the header
    of that thread — which is all this endpoint does — keeps working for both
    sides. Neither can add to it: chat's send path still refuses.
    """
    conversation = thread(other_user, user, published_listing)
    block(user, other_user)

    response = _confirm_over_http(
        client_for, other_user, conversation, published_listing
    )
    assert response.status_code == 200


# ── the posture, on the one axis that owns it ────────────────────────


def test_the_preset_arms_chats_axis_and_that_is_the_only_statement():
    """The composite's whole contribution to blocking, in one assertion.

    chat's own default is ``auto``, right for a generic messaging module that
    may ship without stapel-profiles. A classified marketplace runs profiles
    and blocks between trading strangers are the point, so the composite
    raises the floor — as a VALUE on chat's axis, never as an axis of its own.
    """
    from stapel_classified.conf import DEFAULTS

    assert preset.SETTINGS_DEFAULTS["STAPEL_CHAT"]["BLOCK_ENFORCEMENT"] == "required"
    assert not [key for key in DEFAULTS if key.startswith("BLOCK_")]


def test_with_no_provider_contact_proceeds_and_chats_check_says_so(
    settings, published_listing, other_user, user, thread, client_for,
    no_block_provider,
):
    """``auto`` with no provider registered: this deployment HAS no block store.

    Refusing every contact instead would take a marketplace offline over a
    module it chose not to deploy — so a thread opens, the header renders, and
    ``manage.py check`` prints chat's W003 at every boot. The rule is "never
    degrade SILENTLY", not "never degrade".
    """
    from stapel_chat.checks import check_block_enforcement

    settings.STAPEL_CHAT = {
        **preset.SETTINGS_DEFAULTS["STAPEL_CHAT"],
        "BLOCK_ENFORCEMENT": "auto",
    }
    conversation = thread(other_user, user, published_listing)
    response = _confirm_over_http(
        client_for, other_user, conversation, published_listing
    )

    assert response.status_code == 200
    assert [w.id for w in check_block_enforcement(None)] == ["stapel_chat.W003"]


def test_a_block_key_left_in_this_namespace_is_a_boot_error(settings):
    """E003 — the bridge that keeps the move from being silent.

    AppSettings does not complain about a dead key inside a namespace dict
    (its conf_checks only see environment variables), so a deployment that
    declared ``STAPEL_CLASSIFIED = {"BLOCK_ENFORCEMENT": "off"}`` would
    silently inherit chat's ``auto`` after upgrading: a posture somebody chose
    on purpose would just stop applying.
    """
    from stapel_classified.checks import check_block_keys_moved

    settings.STAPEL_CLASSIFIED = {"BLOCK_ENFORCEMENT": "off"}
    findings = check_block_keys_moved(None)
    assert [f.id for f in findings] == ["stapel_classified.E003"]
    # The hint names the new address, not just the fact of a move.
    assert "STAPEL_CHAT['BLOCK_ENFORCEMENT']" in findings[0].msg
    assert "STAPEL_CHAT['BLOCK_ENFORCEMENT']" in findings[0].hint

    settings.STAPEL_CLASSIFIED = {"BLOCK_FUNCTION": "profiles.relationships"}
    assert [f.id for f in check_block_keys_moved(None)] == ["stapel_classified.E003"]

    # A namespace that moved on is clean, and so is one that was never set.
    settings.STAPEL_CLASSIFIED = {"CONTEXT_BATCH_LIMIT": 10}
    assert check_block_keys_moved(None) == []


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
    gets a stated in-memory provider registered under
    ``STAPEL_CHAT["BLOCK_FUNCTION"]``. The choice is not a preference — a
    suite that mocked the module it is proving a seam against would prove
    nothing, and a suite with no provider at all cannot run the posture the
    preset sets.
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
    from stapel_chat import blocks
    from stapel_classified.testing import memory_block_provider

    with memory_block_provider() as store:
        assert store.backend == "memory"
        assert not blocks.is_blocked(other_user.pk, user.pk)

        store.block(user, other_user)
        assert blocks.is_blocked(other_user.pk, user.pk)  # either direction
        with pytest.raises(SendRefused):
            thread(other_user, user, published_listing)

        store.unblock(user, other_user)
        assert not blocks.is_blocked(other_user.pk, user.pk)

        # And an outage is still not consent.
        store.set_unavailable(True)
        with pytest.raises(BlockCheckUnavailable):
            blocks.is_blocked(other_user.pk, user.pk)

    # Unregistered on exit: the block store is the deployment's, not a test's.
    assert blocks.provider_unreachable_reason()
