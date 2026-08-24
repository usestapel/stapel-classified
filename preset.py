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
#
# Since 0.2.0 the composite mounts a surface of its OWN (`classified/api/`):
# the conversation↔listing join and the cards read off it, which no member is
# allowed to hold. Its STAPEL_LIBS entry therefore reads `http=True` — a
# registry change routed to stapel-tools, see MODULE.md.
#
# stapel-classified, stapel-categories and stapel-listings contribute only
# the ``v1/`` segment and expect the host to mount them under
# ``<mod>/api/`` (api-versioning.md
# §2, §6); stapel-reviews, geo, search and moderation bake ``api/v1/`` in
# themselves. Mounting the first two at a bare ``<mod>/`` produced
# ``/listings/v1/...``, which stapel-core's own mounts.E004 rejects — 40
# errors from one prefix, and `manage.py check` was never run against this
# preset until search and moderation arrived.
URL_INCLUDES = [
    ("classified/api/", "stapel_classified.urls"),
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
        # The complaint taxonomy is universal and stapel-moderation ships a
        # non-empty one; these are the codes a MARKETPLACE needs on top, and
        # they are declared here rather than upstream for the same reason the
        # target types are: only this package knows the vertical. The registry
        # merges over the built-ins, so a deployment adds its own without an
        # upstream patch and removes one of these with `None`.
        "REASONS": {
            # A thing that may not be sold at all — weapons, medicines,
            # wildlife. The highest severity in the marketplace set, because
            # unlike a bad photo it is the platform's own legal exposure.
            "prohibited_item": {
                "severity": 4,
                "requires_description": False,
                "applies_to": ["listing"],
            },
            # A price that is not the price: bait figures, "from 1", a part
            # sold as the whole. Cheap to file, cheap to check, and the most
            # common complaint in every classified product there has been.
            "misleading_price": {
                "severity": 1,
                "requires_description": False,
                "applies_to": ["listing"],
            },
            # Still listed, no longer for sale. Severity 0: it is a catalogue
            # hygiene signal, not misconduct, and queueing it as one would
            # bury the reports that are.
            "already_sold": {
                "severity": 0,
                "requires_description": False,
                "applies_to": ["listing"],
            },
            # Pretending to be a shop, a brand or another member. Aimed at
            # the two targets where identity is the product.
            "impersonation": {
                "severity": 3,
                "requires_description": True,
                "applies_to": ["seller", "chat_message"],
            },
        },
        # stapel-moderation is target-generic and ships an EMPTY
        # BUILTIN_TARGET_TYPES; this is the one place that knows what a
        # listing and a review are (moderation spec §16.8).
        #
        # `profile` is deliberately NOT here: stapel-profiles is not a member
        # of this composite and serves no `profiles.moderation_content`, so a
        # policy for it would be a declared target with an unreachable
        # content function — moderation.W006, and the exact "declared but not
        # connected" defect the module exists to catch. `seller` is a
        # different thing and IS here: it is the marketplace's own notion of
        # a counterparty, and this composite serves its content itself.
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
            "seller": {
                # Post: a seller is live and a verdict sanctions them. There
                # is no verdict TOPIC, because no module in the fleet applies
                # a verdict to an account — the consequence of a case about a
                # seller is a Sanction, which stapel-moderation issues itself
                # against core's cross-service blacklist. Explicit None is a
                # statement (moderation.W006 announces it) rather than an
                # omission.
                "gate": "post",
                "intake_events": [],
                "id_field": "seller_id",
                # Served by THIS package (functions.py): the display name and
                # rating a marketplace shows in public, with the seller's own
                # id as author_id so "you cannot report yourself" holds
                # without trusting a client.
                "content_function": "classified.seller_content",
                "verdict_event": None,
                "notification_types": {},
                # A person is not a listing: `wrong_category`, `counterfeit`
                # and `misleading_price` are complaints about goods, and the
                # place a verdict can remove goods is the listing.
                "reasons": [
                    "spam",
                    "offensive",
                    "harassment",
                    "fraud",
                    "illegal",
                    "personal_data",
                    "off_platform_payment",
                    "impersonation",
                    "other",
                ],
                # No pictures to screen — a seller card is a name and a
                # number.
                "media": False,
            },
            "chat_message": {
                # Served by stapel-chat since its 0.5.0. Until then this was
                # EVIDENCE-BASED — the reporter's own snapshot, stamped
                # unverified, because no module in the fleet served a
                # message's content. `chat.moderation_content` ends that: a
                # moderator reads the message itself, as it is at the moment
                # the case is opened, edits included, and the author it names
                # is what a sanction can be hung on. Declaring BOTH a
                # content_function and `evidence` is moderation.E007, so the
                # flag goes with the flip; nothing migrates, because nothing
                # here ever stored a message.
                #
                # The id spelling is chat's own (`message_id`), and the VALUE
                # stays this composite's composite key
                # `<conversation_id>:<message_id>` — chat splits it and
                # refuses a message quoted under somebody else's
                # conversation, so the key that makes `can_report` answerable
                # below is also checked on the read.
                "gate": "post",
                "intake_events": [],
                "id_field": "message_id",
                "content_function": "chat.moderation_content",
                # Only the two people in the thread may complain about what
                # was said in it. moderation's default for a missing callback
                # is fail-OPEN, which is right for a public listing and wrong
                # for a private conversation — and this composite is the only
                # package in the fleet that can answer the question at all,
                # because it holds the conversation↔parties join.
                "can_report": "classified.can_report_message",
                # Nothing to send a verdict to: a message cannot be taken
                # down by anyone but chat, which consumes no verdict. The
                # consequence of a case about a message is a Sanction on its
                # author, exactly as for `seller`.
                "verdict_event": None,
                "notification_types": {},
                "reasons": [
                    "spam",
                    "offensive",
                    "harassment",
                    "fraud",
                    "illegal",
                    "adult",
                    "personal_data",
                    "off_platform_payment",
                    "impersonation",
                    "other",
                ],
                # A message's attachments travel as opaque CDN KEYS, not
                # bytes: feeding them to a vision screener would only buy a
                # refusal.
                "media": False,
            },
        },
    },
    # The composite's own namespace. Everything in it is either an axis or a
    # comm Function name — see conf.py for why there is no registry here.
    "STAPEL_CLASSIFIED": {
        # The seller rating shown in a conversation header. Empty in the
        # shipped preset because THIS composite registers reviews about
        # `listing`, not about sellers: a deployment that adds a `seller`
        # reviews target sets this to that name and the stars appear. A name
        # declared here without the reviews target behind it would be a
        # rating that is always null and a lookup that always misses.
        "SELLER_RATING_TARGET_TYPE": "",
    },
}
