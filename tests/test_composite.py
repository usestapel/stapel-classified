"""Composite-level checks: the preset is coherent, every member mounts, the
whole assembly passes its own system checks, and the two cross-member
invariants that only exist once these modules are co-installed hold.
"""
import pytest

from stapel_classified import preset


def test_preset_is_coherent():
    # The composite's own app slot is present (glue must live in
    # INSTALLED_APPS — STAPEL_LIBS grabli 5.8) and prefixes are unique.
    assert "stapel_classified" in preset.INSTALLED_APPS
    prefixes = [p for p, _ in preset.URL_INCLUDES]
    assert len(prefixes) == len(set(prefixes))
    # Since 0.2.0 the composite DOES mount a surface of its own: the
    # conversation-subject join no member is allowed to hold. It is mounted
    # under `<mod>/api/` like the members that contribute only `v1/`.
    mine = [p for p, m in preset.URL_INCLUDES if m.startswith("stapel_classified")]
    assert mine == ["classified/api/"]
    # Every mounted module is an installed app (or a nested urlconf of one).
    for _prefix, module in preset.URL_INCLUDES:
        assert module.rsplit(".", 1)[0] in preset.INSTALLED_APPS


def test_search_and_moderation_are_members():
    assert "stapel_search" in preset.INSTALLED_APPS
    assert "stapel_moderation" in preset.INSTALLED_APPS
    mounted = dict((m, p) for p, m in preset.URL_INCLUDES)
    assert mounted["stapel_search.urls"] == "search/"
    assert mounted["stapel_moderation.urls"] == "moderation/"


def test_every_mount_is_canonical():
    """Each member's public paths land under ``/<mod>/api/v1/...``.

    stapel-categories and stapel-listings contribute only ``v1/`` and expect
    to be mounted under ``<mod>/api/``; the rest bake ``api/v1/`` in. Getting
    that wrong is not a style question — ``stapel_core.mounts.E004`` refuses
    to boot a module mounted outside its canonical sub-surfaces, and this
    preset carried that error for both of them until now.
    """
    from django.urls import get_resolver

    paths = [str(pattern.pattern) for pattern in get_resolver().url_patterns]
    for prefix, module in preset.URL_INCLUDES:
        if module.startswith("stapel_geo"):
            continue  # not installed in this harness (GDAL)
        assert prefix in paths
    from django.urls import reverse

    # One resolvable endpoint per new member, proving the prefix composes.
    assert reverse("search-query").startswith("/search/api/v1/")
    assert reverse("moderation-reports").startswith("/moderation/api/v1/")


def test_app_config_mounts():
    from django.apps import apps

    cfg = apps.get_app_config("classified")
    assert cfg.name == "stapel_classified"


def test_system_checks_report_no_errors():
    """``manage.py check`` on a realistic host — the composite's boot gate.

    Not a smoke test: nearly every member ships system checks that only fire
    when it is co-installed with the module it names (moderation.E004/E005/
    W006 over the target policies, search.W001/W006 over the source registry
    and the category-path provider, core's mount canon over the URLconf).
    Booting them together is the only way to run them.

    Three warnings are expected here and are properties of the harness, not
    of the composite: ``access.W005`` (no stapel-auth, so no step-up factor),
    ``blacklist.W002`` (LocMemCache) and ``chat.W001`` (one scope, because a
    marketplace is not multi-tenant). Anything else — and any ERROR at all —
    fails.

    ``classified.W001`` was expected here until 0.3.2 and must now be ABSENT:
    stapel_profiles is mounted, so this host has the block provider its
    ``BLOCK_ENFORCEMENT="required"`` demands. That flip is the whole point of
    the check — it is how a deployment learns which of the two states it is
    in, and the harness is now in the enforcing one.
    """
    from django.core.checks import Error, run_checks

    findings = run_checks()
    errors = [f for f in findings if isinstance(f, Error)]
    assert errors == [], [str(f) for f in errors]

    unexpected = [
        f for f in findings
        if f.id not in (
            "stapel_core.access.W005",
            "stapel_core.blacklist.W002",
            # Declared statements, each announced on purpose:
            #   moderation.W006 — `seller` and `chat_message` consume no
            #     verdict topic, because nothing in the fleet applies a
            #     verdict to an account or to a message; their consequence is
            #     a Sanction. The check exists so that is a decision, not a
            #     forgotten key.
            #   chat.W001 — every conversation lives in the single default
            #     scope. A marketplace is not multi-tenant, so that is the
            #     right answer here and stapel-workspaces is deliberately not
            #     in this host.
            "stapel_moderation.W006",
            "stapel_chat.W001",
        )
    ]
    assert unexpected == [], [str(f) for f in unexpected]

    # …and the one that IS expected must actually be there: a check that
    # stopped firing would leave the same silence it was written to break.
    ids = {f.id for f in findings}
    assert "stapel_moderation.W006" in ids
    # The block posture is enforced, not merely declared — and it is asserted
    # on the ONE axis that owns it since 0.4.0: chat's. No W003 ("no block
    # store here"), no W004 ("blocks are off"), no E017 ("required and
    # missing"), because the preset arms `required` and profiles answers.
    # And no E003: nothing in this host still declares the moved keys.
    assert not {
        "stapel_chat.W003",
        "stapel_chat.W004",
        "stapel_chat.E017",
        "stapel_classified.E003",
    } & ids


def test_moderation_verdicts_are_not_crossed_between_members():
    """Three members now share the one target-generic verdict topic.

    stapel-listings and stapel-reviews each subscribe to
    ``moderation.completed`` and each decides "is this mine?" by its own
    ``MODERATION_TARGET_TYPE``. With stapel-moderation installed the producer
    is real, so a third name enters the picture: the keys of
    ``STAPEL_MODERATION["TARGET_TYPES"]``. All three must line up — a
    consumer whose name is absent from the registry never gets a verdict, and
    two consumers sharing a name would apply a review takedown to a listing
    with the same key.
    """
    from stapel_core.comm.registry import action_registry
    from stapel_listings.conf import listings_settings
    from stapel_moderation.registry import get_target_types
    from stapel_reviews.conf import reviews_settings

    assert len(action_registry.handlers("moderation.completed")) >= 2

    listing_name = listings_settings.MODERATION_TARGET_TYPE
    review_name = reviews_settings.MODERATION_TARGET_TYPE
    assert listing_name != review_name

    registered = set(get_target_types())
    assert {listing_name, review_name} <= registered


def test_listings_does_not_auto_approve_its_own_submissions():
    """With a moderation module installed, listings must not be the gate.

    ``AUTO_APPROVE_ON_PUBLISH`` exists for deployments with no moderation at
    all. Left on here, every submission would be approved on the way in and
    the pre-publication queue would exist and never hold anything — a queue
    that is empty for the wrong reason looks exactly like one that works.
    """
    from stapel_listings.conf import listings_settings

    assert listings_settings.AUTO_APPROVE_ON_PUBLISH is False


def test_recommended_access_roles_are_a_recommendation_only():
    """The role table is named, and deliberately not applied.

    A composite that installed staff mandates would be handing out clearance
    a deployment never asked for; a composite that mentioned them only in a
    comment could not be checked. Named constant, not merged.
    """
    assert set(preset.RECOMMENDED_ACCESS_ROLES) == {"moderator", "ts_lead"}
    assert preset.RECOMMENDED_ACCESS_ROLES["ts_lead"]["apps"]["moderation"] == "high"
    assert "STAPEL_ACCESS" not in preset.SETTINGS_DEFAULTS


def test_projection_declaration_registered_and_valid():
    """The shop glue projection still resolves LOCAL in the wider composite."""
    from stapel_core.comm.projections import (
        projection_registry,
        resolve_mode,
        validate_registry,
    )

    proj = projection_registry.get("shop.listing_review_summary")
    assert proj.live_query == "reviews.aggregates_by_keys"
    assert resolve_mode(proj) == "local"
    validate_registry()


@pytest.mark.django_db
def test_no_missing_migrations():
    """Every member's models match its committed migrations, together."""
    from io import StringIO

    from django.core.management import call_command

    out = StringIO()
    call_command("makemigrations", "--check", "--dry-run", stdout=out, stderr=out)
