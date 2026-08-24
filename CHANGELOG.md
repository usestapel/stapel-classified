# Changelog

## [Unreleased]

## [0.3.0] — 2026-08-24

### ⚠️ BREAKING — a reported message is READ now, not quoted

`chat_message` was **evidence-based**: nobody in the fleet served a message's
content, so a report carried the reporter's own screenshot and a moderator
read it stamped `source: evidence, verified: false`. **stapel-chat 0.5.0
shipped `chat.moderation_content`**, and this composite's own MODULE.md had
already written down what to do about it. Done:

```diff
 "chat_message": {
-    "evidence": True,
+    "id_field": "message_id",
+    "content_function": "chat.moderation_content",
```

No migration — nothing here ever stored a message. What changes is what a
moderator sees: the message itself, fetched when the case is looked at (so an
edit made after the complaint is visible), and its real **author** — which an
attestation could never establish and which is who a `Sanction` is issued
against. Declaring both a `content_function` and `evidence` is
moderation.E007, so the flag went with the flip.

**Breaking twice over**, hence a minor under this fleet's pre-1.0 semver:

- `submit_report(target_type="chat_message", evidence=…)` is now **refused**
  (`400 moderation_evidence_invalid`). A snapshot beside a live content
  function is a second, staler answer to "what was said".
- A deployment must have **stapel-chat 0.5+** serving that function, or every
  complaint about a message answers 503. There is deliberately no silent
  fallback to an attestation; where no process serves the read,
  moderation.W006 says so at every boot.

**The composite key does more work, not less.** `<conversation_id>:<message_id>`
still travels whole, now under chat's own id spelling (`message_id`). This
package answers WHO may file off the conversation half — the fail-closed
`classified.can_report_message`, off the join table nobody else holds — and
chat refuses a message quoted under a conversation it does not belong to, so
the same key is checked again on the far side of the seam.

### Changed

- `stapel-chat>=0.5,<0.6` — a new pin on a package this composite neither
  imports nor mounts. See MODULE.md: it fixes which chat a deployment that
  has one must be on, so a 503 in the moderation queue becomes a resolver
  error instead.
- `stapel-moderation>=0.2,<0.4` → `>=0.3,<0.4`. A chat message is the first
  target here whose content is PRIVATE, and 0.3.0 is where `can_view_content`
  is asked on behalf of the moderator actually looking (it passed
  `actor_id=None` before) and where the card's `content` is a declared field
  of the contract instead of a key grafted onto the response.

### Tests

The harness now mounts **stapel_chat + stapel_realtime** (with a real channel
layer and origin allowlist, because mounting chat brings its deployment
checks E010-E014 with it). Doubling `chat.moderation_content` was the obvious
cheaper move and is exactly what `tests/conftest.py`'s own opening paragraph
forbids: a mock on either side of a seam cannot prove the seam. So the report
tests now build a real conversation and a real message through chat's
services and report THAT — the composite key round-trips through chat's
splitter, a live edit is what the second read returns, a message quoted under
the wrong thread is `TargetNotFound`, and a message chat has no copy of is a
404 rather than a 503. 101 → 103 tests, green.

## [0.2.1] — 2026-08-24

### Changed — the moderation pin admits 0.3

`stapel-moderation>=0.2,<0.3` → `<0.4`. moderation 0.3.0 shipped hours after
0.2.0 (the case card's `content` becomes a declared field of the DTO instead
of a key grafted onto the response, `can_view_content` finally receives the
asking moderator's id, and four refusals that could never be produced start
mapping to their own keys). Nothing this composite calls changed, and the
whole composite suite — 101 tests, every member co-installed — is green
against 0.3.0.

Pre-1.0 house semver reads a minor as breaking, so `<0.3` was the honest pin
to publish 0.2.0 under. Leaving it there for a day would have made a project
that wants moderation 0.3.0 unable to install this composite at all, which is
a resolver conflict manufactured out of caution rather than evidence.


## [0.2.0] — 2026-08-24

The owner opened the live product's chat and could not tell **who** he was
talking to or **what** the conversation was about — no short listing card, no
seller data. Neither half belongs to the chat engine (stapel-chat may not
know what a listing is) or to the catalogue (stapel-listings may not know
what a conversation is). This release is the join, and everything that hangs
off it.

### Changed — what a composite may own (the founding law, restated)

Until now this package wrote no code but `search_sources.py` and served no
HTTP. The law was never "no code": `search_sources` exists because *this
package is the one place that knows both sides*. Restated, and now applying
to state as well as to declarations:

> A composite writes no member-domain logic. It MAY own cross-domain JOIN
> state — models and comm Functions whose schema is nothing but two members'
> opaque keys and the minimal glue between them — because no member is
> allowed to hold that join.

Consequences: `http=True` in the STAPEL_LIBS registry (a change routed to
stapel-tools), one mounted surface (`classified/api/`), one migration, and
this module now emits its own contract triad + capabilities like every other.

### Added

**`ConversationSubject`** (migration `0001_initial`) — `(conversation_id,
subject_type, subject_key, initiator_id, counterparty_id, scope_key)`. No FK
to anything: in the 7-service topology those keys live in three different
databases. **Append-only, several subjects per conversation allowed**, which
is chat 0.4.0's own arithmetic rather than a preference: a direct thread is
keyed by the participant PAIR and uniquely constrained, so one buyer and one
seller have exactly one thread however many listings they discuss. Refusing
the second listing would render the wrong card — the very defect this closes.
**Marked for deletion**: when stapel-chat ships native subjects this table is
migrated into it and dropped, not kept as a shadow.

**Three endpoints** under `/classified/api/v1/`, all authenticated:

- `POST conversations` — bind a chat conversation to the listing it is about
  and answer the header. Idempotent per `(conversation, listing)`; the first
  writer's parties stand.
- `GET conversations/{id}` — one header. A conversation you are not a party
  of answers the same 404 as one that does not exist: a 403 would confirm the
  id names a real thread.
- `POST conversations/contexts` — a bounded page of headers for the inbox, in
  two comm reads rather than one round trip per row.

**The short listing card**, with the field this whole wave exists for:
`state` = `available` / `unavailable` (sold, paused, expired, blocked —
`status` says which) / `gone` (deleted). The public listing read 404s
everything that is not published, which is correct for a stranger and useless
for the person standing in the conversation about it — and that is exactly
when a buyer is most confused. The card also carries the primary image's CDN
render metadata (`aspect`, `preview_b64`, `preview_kind`, `variants`), the
same contract stapel-chat uses for an attachment, so one picture has one
answer.

**The public seller card** — display name, avatar ref, member-since, seller
type, rating. Never more of a person than their public profile. Today the
fleet publishes no public-profile comm read, so the card answers
`meta_status: "partial"`, `meta_reason: "profile_unavailable"` and names what
is missing instead of leaving a blank.

**Two more moderation target types**, both declared here because only this
package knows the vertical:

- `seller` — content served by this composite itself
  (`classified.seller_content`: the display name and rating a marketplace
  shows in public, with the seller's own id as `author_id`, which is what
  makes "you cannot report yourself" answerable without trusting a client);
- `chat_message` — **evidence-based** (stapel-moderation 0.2.0): nobody in
  the fleet serves a chat message's content, so the report carries the
  reporter's snapshot. Its key is `<conversation_id>:<message_id>` and its
  `can_report` is `classified.can_report_message`, which fails CLOSED — only
  the two people in the thread may complain about what was said in it, and
  this package holds the only table in the fleet that can answer who they are.

**Marketplace reason codes** merged over moderation's universal taxonomy:
`prohibited_item`, `misleading_price`, `already_sold`, `impersonation`. An
open registry, so a deployment adds or removes one in its own settings.

**Server-side block enforcement** at the one place a classified conversation
begins. The block itself stays stapel-profiles' (`UserRelationship`) — this
composite keeps no copy and asks. `BLOCK_ENFORCEMENT` is `auto` /
`required` / `off`, and the state a deployment is actually in is printed at
every `manage.py check` (`classified.W001` / `E002` / `W002`) rather than
assumed. A provider that is present and FAILS answers 503, never "allowed":
an outage is not consent.

**`STAPEL_CLASSIFIED`** settings namespace (`conf.py`, CONFIG.MD), **five
error keys** with ru/es catalogues, **three comm Functions**
(`classified.subject_cards` — the shape a subject-aware stapel-chat will name
as its `card_function` — `classified.seller_content`,
`classified.can_report_message`), and this module's own contract emission
(`_codegen.py`, `_capabilities.py`, `codegen_urls.py`, `make contract`).

### Dependencies

- `stapel-moderation>=0.2,<0.3` — the evidence-based target type.
- `stapel-core>=0.43` — the hoisted `SerializerSeamMixin` / `StapelAPIView`.

### Known limitation (stated, not hidden)

**The binding is a claim by the person who makes it.** chat 0.4.0 exposes no
comm Function that could answer "is this user a participant", so a bind
records the caller as one party and the listing's owner as the other, and the
context read is authorized against that row. Forging one needs the
conversation's UUID (which only its participants hold) and buys the forger
nothing but a public listing card and a public seller card. It is closed the
moment chat ships either a participants read or native subjects — the shape
routed to its owner and written down in MODULE.md.


## [0.1.8] — 2026-08-24

### Changed — pins admit `stapel-listings` 0.7 (the geohash-stamp fix)

`stapel-listings>=0.5,<0.7` → `<0.8`. This is the release that lets a fleet
carry **listings 0.7.1** — `Listing.save()` now stamps `geohash`/
`geohash_draft` via `geo.geohash_encode`, plus the one-time
`listings_backfill_geohash` management command for rows written before the
fix. Until now every listing carried `geohash=""`, so search 0.2.2's
geohash prefilter (0.1.7's own reason for existing) had nothing to
prefilter against and every geo-filtered query fell back to a full box
scan — correct, not fast.

`search_sources.listing_source()` still reads `stapel_listings.models.
INDEXED_STATUSES` by name and 0.7.x does not touch it; 0.7.0's only change
was an additive route (`GET my/listings/`) this composite does not call.
This composite's own `stapel-shop` pin (`>=0.2.3,<0.3`) is unchanged — shop
0.2.4 (which itself widens to admit listings 0.7) satisfies it without a
bump here. Verified in a clean venv on released listings 0.7.1: full
composite suite green (50 passed).

## [0.1.7] — 2026-08-24

### Changed — pins admit `stapel-search` 0.2.2 (the geo prefilter fix)

`stapel-search>=0.1,<0.2` → `>=0.2.2,<0.3`. The postgres search backend was
ANDing `geohash LIKE 'prefix%'` unconditionally while listings carry an
empty geohash, so radius search returned *fewer* results the closer you
searched (live: radius=50km → 0 results, radius=500km → 3, nearest actually
11.67km away). 0.2.2 fixes the prefilter; this release is what lets a fleet
carry it instead of the broken 0.1.x line. Verified in a clean venv on
released search 0.2.2 (installed over the shared workspace venv's existing
member versions): full composite suite green (50 passed), no new `pip
check` conflicts introduced by the search pin.

Note: v0.1.6 was tagged and pushed but never published — its CI run failed
the contract drift gate (`docs/capabilities.json`/README/llms.txt still
read 0.1.5) before the publish job could start, so nothing reached PyPI
under that tag. This release regenerates the contract artifacts via `make
contract` and carries the same search-pin change forward as 0.1.7.

## [0.1.5] — 2026-08-23

### Changed — pins admit `stapel-listings` 0.6 (the authz fix) via `stapel-shop` 0.2.3

`stapel-listings>=0.5,<0.6` → `<0.7`; `stapel-shop>=0.2.2` → `>=0.2.3` (the
shop release whose own pin stopped walling listings 0.6 out). This is what
lets a fleet carry listings 0.6.2 — four authorization holes closed on the
listing surface — instead of 0.5.0. The `listing` search source still reads
`INDEXED_STATUSES` by name and nothing in 0.6.x renames it; verified in a
clean venv on released shop 0.2.3 + listings 0.6.2 + reviews 0.3.0 (search
and moderation from their v0.1.0 tags, as the fleet installs them): full
suite green, `pip check` clean.

Every member resolves from PyPI now (stapel-search 0.1.0, stapel-moderation
0.1.0 published 2026-08-23), so the `pip install git+...` fallback is gone
from `ci.yml` and this is the first release whose `requires_dist` names the
composite that actually ships — the 0.1.4 wheel still read `stapel-shop<0.2`
and knew neither search nor moderation.

### Added — search and moderation are members

`stapel-classified` = shop (categories + attributes + listings + reviews) +
geo + **search** + **moderation**. `INSTALLED_APPS` gains `stapel_search` and
`stapel_moderation` (after the modules whose facts they subscribe to — both
wire their subscribers from their own `ready()`), and `URL_INCLUDES` gains
`search/` and `moderation/`.

**The `listing` search source** (`stapel_classified/search_sources.py`) — the
first executable glue this package has carried. stapel-search ships
`BUILTIN_SOURCES = {}` and stapel-listings knows nothing about an index; the
composite is the only place allowed to know both, so it declares
`STAPEL_SEARCH["SOURCES"]["listing"]`:

- pulls through `listings.search_documents` (live) and
  `listings.search_export` (rebuild/drift), the same builder on both sides;
- invalidated by `listing.published` / `listing.updated` / `listing.removed`,
  which are treated as *signals* — the pulled document's own `status` decides
  visibility, never the event name;
- fills title/body, `text_extra` from the title-flagged attributes,
  `price_base`/`price`/`currency`, `lat`/`lon`/`geohash`, `language`,
  `published_at`, `owner_key`, `category_id` and the stored result card;
- reads `visible_statuses` from `stapel_listings.models.INDEXED_STATUSES`
  rather than copying it, so a lifecycle state added upstream cannot leave the
  index's idea of "live" behind;
- leaves `category_path` to stapel-search, which now has a real
  `categories.path` provider (below).

**The two moderation target types.** `STAPEL_MODERATION["TARGET_TYPES"]`
declares `listing` (gate `pre`, intake `listing.submitted`, content
`listings.moderation_content`, `listing_blocked` letter) and `review` (gate
`post`, intake `reviews.review.published`, content
`reviews.moderation_content`, no letter, no media, and a reason list without
`wrong_category`/`counterfeit` — a review has no category, and a
counterfeit-goods complaint belongs on the listing where a verdict can
actually remove the goods). `profile` is deliberately absent: stapel-profiles
is not a member, so a policy for it would name a content function nobody
serves — `moderation.W006`, the exact defect that module exists to catch.

`preset.RECOMMENDED_ACCESS_ROLES` names the moderator clearances (§8 of the
moderation spec) as a constant that is **not** merged into
`SETTINGS_DEFAULTS`: a role table is a host's org chart, and a comment cannot
be tested.

Notification routing needs no entry here — stapel-notifications 0.14.0 already
ships `listing_blocked` (with `reason_label` + `appeal_url`) and the three
`moderation.*` types as built-in routing. The composite only names which type
each target uses.

### Added — the tests that are only possible here

10 → 42. A composite's single claim is that its members meet correctly, and a
mock on either side of a seam is the one thing that cannot prove it. Nothing
below is mocked:

- `manage.py check` over a *realistic* host (real middleware, real templates,
  the preset's own URLconf): **zero errors**, and the only two warnings
  allowed are properties of the harness (`access.W005` — no stapel-auth, so no
  step-up factor; `blacklist.W002` — LocMemCache). Every member's cross-module
  system check runs there: `moderation.E004/E005/W006` over the target
  policies, `search.W001/W006` over the source registry and the category-path
  provider, core's mount canon over the URLconf.
- publish → index → query: a listing published through `publish_listing`
  appears in `/search/api/v1/query`, is found by title and by body text, is
  cut by a geo radius, and carries its card and `promoted` marker.
- takedown → gone: `apply_moderation("rejected")` moves the listing
  `published → blocked`, which emits `listing.removed`, which empties the
  search answer. Nothing in that test calls into stapel-search.
- report → case → verdict → target: a complaint on a live listing joins its
  existing case, identifies the author through
  `listings.moderation_content`, and a `rejected` verdict blocks the listing
  *and* drops it from the index — three modules agreeing without one importing
  another. The same loop on a review ends with the review `hidden` and the
  listing that shares its numeric key untouched.
- facets end to end: two listings in a leaf category, the facet plan built
  from the parent's inherited `brand` feature via `categories.features`,
  correct counts, and `f.brand=apple` narrowing to one.
- category rollup: a filter on the PARENT category finds the child's listing
  and the answer carries no `degraded: ["category_rollup"]`.
- rebuild parity: `search_rebuild` off `listings.search_export` lands the
  identical row the live signal did.
- the shop cross-target gate, extended: with a real verdict producer in the
  process, the two consumers' `MODERATION_TARGET_TYPE` names must not only
  differ from each other but must both exist as keys of the moderation
  registry — a consumer whose name is absent never gets a verdict at all.
- `makemigrations --check` across every member together.

### Fixed — the preset mounted two members outside the URL canon

`categories/` and `listings/` produced `/categories/v1/...` and
`/listings/v1/...`: both modules contribute only the `v1/` segment and expect
`<mod>/api/`, so `stapel_core.mounts.E004` rejected **40** patterns. Nobody
had noticed because `manage.py check` had never been run against this preset.
Now `categories/api/` and `listings/api/`, and the system-check suite is a
test.

### Changed — dependency pins

| Pin | Was | Now | Why |
|---|---|---|---|
| `stapel-core` | `>=0.10,<1.0` | `>=0.32,<1.0` | the floor stapel-moderation requires; the old one let a resolver pick a core from before half these mechanisms existed |
| `stapel-shop` | `>=0.1,<0.2` | `>=0.2.2,<0.3` | shop 0.2.2 widens its own `stapel-listings` pin to admit 0.5, which is the follow-up below |
| `stapel-categories` | (transitive) | `>=0.5.6,<0.6` | **direct**, above shop's floor: `categories.path` arrived in 0.5.6 and the search rollup is answered by it |
| `stapel-listings` | (transitive, capped `<0.5` via shop 0.2.1) | `>=0.5,<0.6` | **direct**, for the same shape of reason as categories: `search_sources.listing_source()` imports `stapel_listings.models.INDEXED_STATUSES` by name, so this composite's own idea of "visible" is read straight off it |
| `stapel-search` | — | `>=0.1,<0.2` | new member |
| `stapel-moderation` | — | `>=0.1,<0.2` | new member |

**The 0.4→0.5 follow-up named in the previous entry is now closed.** Listings
0.5.0 changed re-publishing a live listing from a silent takedown
(`status` assigned straight to `pending`, past the FSM, no event) to riding
the moderation axis alone: `status` stays `published`, only
`moderation_status` moves back to `pending`, and a rejecting verdict removes
the listing through the same `published → blocked` edge a report-driven
takedown uses. Verified end to end in this composite, not just read off the
listings CHANGELOG — a live listing re-published through `publish_listing`
stays in `Listing.objects.published()` *and* in the search answer while its
fresh case is open, and only a `rejected` verdict empties both
(`tests/test_search_source.py::test_a_live_edit_republish_never_leaves_the_index`,
`tests/test_moderation_targets.py::test_a_live_republish_stays_visible_while_rescreened`,
`tests/test_moderation_targets.py::test_a_rejecting_verdict_on_a_republish_still_takes_it_down`).
Nothing else in 0.5.0 touches this composite: `search_sources.py`'s
`visible_statuses` already read `INDEXED_STATUSES` by reference rather than
copying it, so `published` staying indexed during re-screening required no
code change here — only the pin, and the tests that pin the new promise.

### Known limitation — attribute facets are terms, not ranges

`listings.search_documents` serves `features_search` (`{slug: [values]}`) and
not the stapel-attributes DAO list, so the mapper takes stapel-search's
declared fallback (`ACCEPT_FEATURES_SEARCH`). Consequence, stated rather than
absorbed: every attribute lands as a *term*, so `r.<slug>` range filters over
listing attributes do not work, `hex_color`'s `simple` axis and unit context
are lost, and lists are flattened. Closing it is one field in listings'
document builder (`build_search_document` → also serve `features`) plus
swapping `features_search=` for `features=` in the mapper. Range filters on
`price_base` are unaffected — that one is a first-class index field.

## [0.1.4] - 2026-08-02

### Added
- `docs/llms.txt` — the fifth contract artifact, an agent-sized slice of the
  hand-authored `docs/capabilities.json`, wired into a new `make contract` /
  `make contract-check` (badge-canon §3). `docs/capabilities.json`'s
  `version` field brought back in sync with `pyproject.toml` (it had drifted
  to 0.1.2 across the 0.1.3 release).
- Canonical `ci.yml` with coverage, `codecov.yml`, Python 3.14 classifier,
  badge canon in README (truncated to license + status — this module has
  never published to PyPI).

## [0.1.2] - 2026-07-17

Fleet follow-up to stapel-core 0.12.0 (legacy shim sweep). Member pins
(`stapel-shop` 0.1.2, `stapel-geo` 0.3.2) already fit this composite's
existing ceilings. Suite green.

### Changed
- `stapel-core` ceiling `<0.12` → `<0.13`.

## [0.1.1] - 2026-07-17

### Fixed
- `stapel-geo` pin was still `>=0.2,<0.3` — stale since geo's v2 redesign
  released as 0.3.0 (pre-1.0 minor = breaking); widened to `>=0.2,<0.4`.
  Classified's own code only mounts `stapel_geo.urls`/`INSTALLED_APPS`
  (never touches geo internals directly — confirmed against this repo's
  own `conftest.py`, which doesn't even install `stapel_geo` for the unit
  harness), so the wider range is safe. Unrelated to core 0.11, but
  without it `pip install .` couldn't resolve at all.

### Changed
- `stapel-core` ceiling raised `>=0.10,<0.11` → `>=0.10,<0.12` (core 0.11
  fleet re-pin). Suite green as-is.

## [0.1.0] - 2026-07-16

### Added

- Initial composite (projections-and-composition §3): pyproject pins over
  the member modules, `preset` (INSTALLED_APPS/urls/STAPEL_* defaults),
  AppConfig app slot, minimal tests.
