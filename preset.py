"""Preset for the "classified" scenario — plain data, importable without
Django settings (projections-and-composition §3).

Scenario: location-bound classified ads — the shop composite (categories +
attributes + listings + reviews) plus geo, search and moderation. Listing
coordinates are the listing's own fields, not a projection.

A generated project (stapel-assemble … --libs classified) gets the
same wiring from the STAPEL_LIBS registry; this module is the single source
a hand-written settings.py/urls.py copies from instead.
"""

# Dotted app paths, in mount order. L1 libraries (stapel-attributes) are pip
# dependencies, NOT Django apps — deliberately absent here.
#
# Order matters twice over: stapel_search's ready() wires one Action
# subscriber per registered source and stapel_moderation's ready() wires one
# per target type's intake_events, so both must load AFTER the modules whose
# facts they listen to.
INSTALLED_APPS = [
    "stapel_categories",
    "stapel_listings",
    "stapel_reviews",
    "stapel_shop",
    "stapel_geo",
    "stapel_search",
    "stapel_moderation",
    "stapel_classified",
]

# (url_prefix, urlconf_module) — mount each one with
#   path(prefix, include(module))
# The composite itself mounts NO urls (http=False): it only carries glue.
# stapel-categories and stapel-listings contribute only the ``v1/`` segment
# and expect the host to mount them under ``<mod>/api/`` (api-versioning.md
# §2, §6); stapel-reviews, geo, search and moderation bake ``api/v1/`` in
# themselves. Mounting the first two at a bare ``<mod>/`` produced
# ``/listings/v1/...``, which stapel-core's own mounts.E004 rejects — 40
# errors from one prefix, and `manage.py check` was never run against this
# preset until search and moderation arrived.
URL_INCLUDES = [
    ("categories/api/", "stapel_categories.urls"),
    ("listings/api/", "stapel_listings.urls"),
    ("reviews/", "stapel_reviews.urls"),
    ("geo/", "stapel_geo.urls"),
    ("search/", "stapel_search.urls"),
    ("moderation/", "stapel_moderation.urls"),
]

# Recommended per-app clearance for the moderation console (moderation spec
# §8). NOT merged into SETTINGS_DEFAULTS and not applied by anything here: a
# role table is a host's org chart, and a composite that installed one would
# be handing out staff mandates a deployment never asked for. Copy it into
# your own STAPEL_ACCESS. The shape is what makes the point — a moderator is
# staff inside the moderation app and an ordinary user everywhere else.
RECOMMENDED_ACCESS_ROLES = {
    "moderator": {"clearance": "low", "apps": {"moderation": "mid"}},
    "ts_lead": {"clearance": "mid", "apps": {"moderation": "high"}},
}

# Scenario defaults for STAPEL_<MOD> settings dicts. Merge them into the
# project's settings, e.g.:
#   from stapel_classified import preset
#   STAPEL_REVIEWS = {**preset.SETTINGS_DEFAULTS.get("STAPEL_REVIEWS", {})}
SETTINGS_DEFAULTS = {
    "STAPEL_REVIEWS": {
        # reviews is target-generic and ships an EMPTY TARGET_TYPES registry;
        # the composite is the place that knows both sides, so the scenario
        # default targets the catalog's listings out of the box.
        "TARGET_TYPES": {
            "listing": {
                "moderation": "post",
                "one_per_author": True,
                "allow_response": True,
                # Host policy callbacks (comm Functions) are None by default:
                # any authenticated user may review. Register and name your
                # own "can_review"/"can_moderate" Functions to restrict.
            },
        },
    },
    # NOTE there is no STAPEL_LISTINGS entry. The one key that matters for
    # this scenario — AUTO_APPROVE_ON_PUBLISH — already defaults to False in
    # stapel-listings, i.e. "wait for a verdict", so restating it here would
    # only add a second place to drift from. The composite holds it as a
    # GATE instead (tests/test_composite.py): with stapel-moderation
    # installed, listings must not approve its own submissions, or the
    # pre-publication queue would exist and never hold anything.
    "STAPEL_SEARCH": {
        # stapel-search ships BUILTIN_SOURCES = {} — it knows nothing about
        # listings. The overlay is {doc_type: dotted path}, resolved and
        # called per entry, so the composite declares the one corpus it has.
        "SOURCES": {
            "listing": "stapel_classified.search_sources.listing_source",
        },
    },
    "STAPEL_MODERATION": {
        # stapel-moderation is target-generic and ships an EMPTY
        # BUILTIN_TARGET_TYPES; this is the one place that knows what a
        # listing and a review are (moderation spec §16.8).
        #
        # `profile` is deliberately NOT here: stapel-profiles is not a member
        # of this composite and serves no `profiles.moderation_content`, so a
        # policy for it would be a declared target with an unreachable
        # content function — moderation.W006, and the exact "declared but not
        # connected" defect the module exists to catch.
        "TARGET_TYPES": {
            "listing": {
                # Pre-publication: a submitted listing waits for a verdict.
                # listing.submitted is emitted on entry to `pending`, and the
                # verdict is what moves it to published or blocked.
                "gate": "pre",
                "intake_events": ["listing.submitted"],
                # The *.moderation_content family takes the owner's own id
                # name, not a generic target_key (listings 0.4.0).
                "id_field": "listing_id",
                "content_function": "listings.moderation_content",
                "verdict_event": "moderation.completed",
                # `listing_blocked` is a stapel-notifications built-in whose
                # 0.14.0 copy carries reason_label + appeal_url — the two
                # variables DSA Art. 17 needs. Nothing to register here; if
                # stapel-notifications is not installed at all, no letter is
                # sent and moderation.E005 stays silent by design.
                "notification_types": {"content_blocked": "listing_blocked"},
            },
            "review": {
                # Post-publication: reviews go live and moderation can take
                # them down. That mirrors STAPEL_REVIEWS["TARGET_TYPES"]
                # above, where reviews about listings are "post" — one
                # policy, spelled in both registries because each module owns
                # its own half of it.
                "gate": "post",
                "intake_events": ["reviews.review.published"],
                "id_field": "review_id",
                "content_function": "reviews.moderation_content",
                "verdict_event": "moderation.completed",
                # No letter: reviews has no notification type in the fleet,
                # and an unregistered name here would be moderation.E005.
                # Explicitly empty is a statement, not an omission.
                "notification_types": {},
                # A review is an opinion, not an offer. `wrong_category` has
                # no meaning without a category and `counterfeit` is a claim
                # about goods — that complaint belongs on the listing, where
                # a verdict can actually remove the goods. Everything else in
                # the universal taxonomy applies unchanged.
                "reasons": [
                    "spam",
                    "offensive",
                    "harassment",
                    "fraud",
                    "illegal",
                    "adult",
                    "personal_data",
                    "off_platform_payment",
                    "other",
                ],
                # No media on a review in this composite: screening images
                # that do not exist would only cost prompt cache hits.
                "media": False,
            },
        },
    },
}
