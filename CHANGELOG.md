# Changelog

## [Unreleased]

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
