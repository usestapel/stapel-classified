# Changelog

## [0.8.2] — 2026-09-02

Patch. `stapel_classified.E004` — the moderation-gate agreement check — and
with it, stapel-moderation's `gate` key stops being inert for listings.

The policy "when does a listing go public relative to its review" is spelled
twice, on purpose, because each module owns its own half: the preset's
`STAPEL_MODERATION["TARGET_TYPES"]["listing"]["gate"]` says what the queue
believes, and stapel-listings 0.13.3's `MODERATION_GATE` says what publish
actually does. Two settings that can disagree is how one half publishes
immediately while the other half still gates — listings `post` / moderation
`pre` puts live content in front of a queue that thinks it screens drafts;
listings `pre` / moderation `post` holds every first publication in
`pending` for a verdict the policy says nothing should wait for, which on a
moderator-less stand is forever. Both directions are silent at runtime and
green in every module's own suite; only the composite can see the seam, so
the composite now fails the boot on it.

Graceful against a stale environment: an installed stapel-listings without
the knob (older than 0.13.3) consumes no `MODERATION_GATE` whatever the host
declares, and the check reads it as the `pre` it actually is instead of the
declared value nothing is reading. The floor moves to `stapel-listings
>=0.13.3` regardless, so a resolvable install always has the real seam.

The preset keeps `gate: "pre"` for listings — flipping a stand to
post-moderation is two settings, changed together, and E004 is what makes
"together" enforceable.

Also in this patch: the preset states `STAPEL_VOCABULARIES
["QUERY_EXPANDER"] = "stapel_search.suggest.query_terms"` — vocabularies
0.1.3's seam, pointed at the fleet's one cross-script normalization layer,
so the composer's brand pickers understand «тимберленд» the way the
type-ahead already does. One layer, consumed, never copied; the composite
test imports the dotted path and runs a real cross-script query through
it, so a rename in either library fails in CI and not in a buyer's
picker. Floors: `stapel-vocabularies>=0.1.3` (the release where the
stated key is real).

## [0.8.1] — 2026-09-02

Patch. Caps and one floor — no code, no model, no migration, no payload.

- `stapel-categories<0.12` -> `<0.13`
- `stapel-listings<0.13` -> `<0.14`
- `stapel-shop>=0.2.14` -> `>=0.2.18`

The shop floor moves WITH the two caps, and that is the whole point: shop
carries its own `stapel-categories<0.12` / `stapel-listings<0.13`, so without
it pip resolves a shop that caps the members back down and the widening above
does nothing, silently. This composite has now recorded that exact shape four
times.

**stapel-categories 0.12.0** adds the two public tree reads a storefront walks
this composite's catalogue with: `roots` (top-level categories without pulling
the whole table) and `by-slug/<slug>` (the storefront's own URL vocabulary
resolved server-side). A composite whose subject is a browsable classified
catalogue cannot hold a fleet under the release that lets the tree be walked
from its first rung — held at `<0.12`, rendering a row of category tiles means
listing every category and filtering client-side, measured on a live stand as
a 15-page, 614 KB walk behind a cold catalogue page.

**stapel-listings 0.13.0** makes `listings_reproject_features` repair a
listing field by field. This composite's own `stapel-listings` block already
calls that command the only way a write-time snapshot becomes true again —
and until 0.13.0 one attribute that no longer validated skipped the whole row,
so every other field kept whatever an older engine left there. Measured: 12
listings stuck on a stale shape for reasons unrelated to the fields broken on
screen. Capping under it keeps the repair this composite depends on
half-working.

Both floors are unchanged: `stapel-categories>=0.11` (`Feature.visibility`)
and `stapel-listings>=0.12.1` (the identifier attribute never leaving the
module).

## 0.8.0 — 2026-09-02

Minor (pre-1.0: minor = breaking). Four member bumps that only mean anything
together, and the one test in the fleet that can observe them doing so.

### The seam, and why it is tested here

A VIN and an IMEI identify a *specific physical unit* rather than describing
it. Publishing one lets a stranger act as that unit's owner; indexing one
turns search into an oracle that confirms which advert it belongs to. Making
that impossible took four modules:

- **stapel-attributes 0.8** added `FeatureDef.visibility` and stamps it onto
  every stored value, so a read path with no schema in hand can still tell.
- **stapel-categories 0.11** gave the catalogue the column to set it in, and
  made `categories.features` carry it across the comm boundary.
- **stapel-listings 0.12** stopped putting the value in the three public
  projections at all, and redacts `features` per viewer on the way out.
- **stapel-search 0.9** stopped indexing, planning, counting and filtering it.

Each of those repos tests its own half against a stub of the others, and
**every one of those suites can be green while the fleet still leaks** — the
property that has to hold is a property of the seam, and no single repo can
observe the chain. `tests/test_feature_visibility.py` is the only place it
exists: a real `Feature` row carries the visibility, `categories.features`
hands it over comm, `publish_listing` stamps it into the stored DAO, the HTTP
detail read redacts it, the bus fact travels, stapel-search pulls the document
back and the assertions are made against the public query surface. Nothing is
stubbed. Every leak assertion has a paired control on a public sibling, so a
build that simply stopped projecting attributes cannot pass.

It also pins the honest half: the redacted stub says the value is `present`,
and carries no `verification`, because nothing in this fleet runs a VIN check.

### Fixed

- **The test harness cached one category's schema for another's.**
  `stapel_listings.services.category_schema` memoizes a category's features
  under its ID; the database is rolled back between tests but LocMem is not,
  and category primary keys are reused after a rollback. One test's schema
  therefore answered the next test's lookup, and the symptom —
  `Feature '<slug>' is not allowed` at publish — appeared only in a full run,
  only in some orders, and never on a re-run of the failing test alone. The
  autouse `_reset_registries` fixture now clears the Django cache.

### Changed

- `stapel-attributes>=0.7,<0.8` -> `>=0.8.1,<0.9`
- `stapel-categories>=0.10,<0.11` -> `>=0.11,<0.12`
- `stapel-listings>=0.11,<0.12` -> `>=0.12.1,<0.13`
- `stapel-search>=0.8.1,<0.9` -> `>=0.9,<0.10`

Every floor moves with its cap, for the reason this file has now given
several times: a fleet able to resolve back onto the older half publishes the
VIN again, and nothing errors while it does.

### Upgrading

Deploying is not enough. Values stored before the axis keep the VIN in their
public projections until `python manage.py listings_reproject_features` has
re-stamped them, and the search index keeps the old terms until
`python manage.py search_rebuild --type listing` has run — in that order.

## 0.7.2 — 2026-09-02

Patch. Two dependency ranges — no code, no model, no migration, no payload.

- `stapel-categories>=0.9,<0.10` -> `>=0.10,<0.11`
- `stapel-search>=0.7,<0.8` -> `>=0.8.1,<0.9`

The two move TOGETHER because either half alone is a no-change, the same
pairing 0.6.2 recorded for the type-ahead itself. categories 0.10.0 grades a
`categories.suggest` hit four ways — `exact` / `prefix` / `word` /
`substring` — where it graded it two; search 0.8 is the module that RANKS on
that grade, and on a board where nearly every leaf is still empty the grade
is the only evidence a ranker has. A deployment resolving back onto
categories 0.9 gets the new ranker with its evidence flattened.

search 0.8 also fixes the facet plan, which is what a SERP on this
composite's own catalogue is made of: it ranked on the author's flags alone,
so on a 59-feature imported leaf a mandatory integer took the last of twelve
budget slots and the whole vocabulary identity chain fell past the cap — a
car buyer offered the body number and nine dealer promotions to filter by,
and not the make. A feature with a bounded option set now outranks one
without.

The floor is 0.8.1 rather than 0.8.0: 0.8.0 shipped with `__version__` still
reading `0.7.0`.

## 0.7.1 — 2026-09-01

Patch. Comments and changelog prose only — no code, dependency range, model or
API change.

The dependency comment explaining why the `stapel-attributes` cap had to move,
and the two changelog passages recounting the same import, named the external
marketplace whose catalogue was imported. They now say what the argument
actually rests on: an imported external catalogue, 2 468 of whose fields are
composites.

## 0.7.0 — 2026-08-31

### A card carries the GALLERY — a SERP row can finally be swiped

`_base_card` projected `images[0]` and threw the rest away, so every surface
built on it — the stored search document, the conversation header — could show
exactly one photo. The card, not the client, was the ceiling: the phone SERP
card in `@stapel/listings-react` has drawn a `<SkinCarousel>` since it shipped,
and the reference design's swipeable strip had one slide on live data because
the projection sent one ref. The detail page peeked correctly the whole time,
because it reads the listing and the listing has always had the gallery.

- **`images` on every classified card.** The seller's own photo order, capped
  at the new `CARD_IMAGES_LIMIT` (10), deduplicated — two identical refs are
  two identical slides. Same object shape as `image` on the header card; plain
  string refs in the stored search card, for the reason below.
- **`image` did not move.** It is `images[0]`, always, and it stays because
  the card travels through stores that never validate it (stapel-search keeps
  it in a JSONField, stapel-chat re-declares it as opaque JSON) and readers
  outside this repo were written against it. Additive on the wire: nothing has
  to be redeployed to keep working, and `images` is there for whoever wants
  the strip. `images: []` and `image: null` are the same fact.
- **The CDN batch is spent primaries-first.** `cdn.describe_many` takes a
  bounded batch and fifty conversations × ten photos is five hundred refs, so
  the flattening is column-major: everybody's first photo before anybody's
  second. A chat inbox — the surface that only ever shows a thumbnail — can no
  longer be starved of one by another card's tenth frame. Still ONE call per
  page of cards; the gallery grew, the fan-out did not. What the budget did not
  reach keeps its ref and says `meta_reason: "not_described"`.
- **The stored search card carries refs, never a render snapshot.** A rebuild
  indexes a corpus and must not ask the CDN once per row, and a snapshot frozen
  into a stored document goes stale the first time the CDN re-encodes anything.
  Unchanged behaviour, now written down in `search_sources._card`.

`CARD_IMAGES_LIMIT` is tuning, not an axis (like `CARD_IMAGE_TIER` and
`CONTEXT_BATCH_LIMIT` beside it): it does not change what the product does to
anyone, only how much of a gallery a glance is worth.

**A deployment must reindex.** Existing search documents keep the card they
were stored with — `stapel_search.services.index_documents` rewrites `card`
only when a document is re-indexed — so the SERP keeps showing one photo until
`manage.py search_rebuild --type listing` has run. The rebuild is not blocked
by the seq guard (equal `seq` re-indexes; only a strictly older one is skipped),
so no listing has to be touched to make it take.

No migration. No member pin moves: this is one projection and its contract.

## 0.6.2 — 2026-08-31

### The type-ahead offers PLACES — pins only, no code

0.6.1 carried the same three pins and never published: `docs/capabilities.json`
was left describing 0.6.0 and the drift gate refused the release — correctly,
since a contract artifact that lags the package it describes is what the gate
is for.

Patch: no model, migration, view, preset or code change. Three lines move so
that a classified deployment can install the pair that makes a search box a
navigation control.

Typing «шорты» on a marketplace has three right answers and none of them is a
string — the leaf sits under men's, under women's and under children's
clothing, and what tells a buyer which one they meant is the ancestor path
and the number of live listings behind it.

- **`stapel-search>=0.6,<0.7` → `>=0.7,<0.8`.** 0.7.0 makes
  `GET /search/api/v1/suggest` answer `categories[]`: the whole ancestor path,
  a count that is the SERP's own count (asserted against `/query`, not
  resembled), and a `category` string ready to paste into the SERP's filter.
  One aggregate over the index does the counting, never one per row.
- **`stapel-categories>=0.8.4,<0.9` → `>=0.9,<0.10`.** 0.9.0 provides
  `categories.suggest`, the comm Function that half depends on. The floor
  moves with the cap by the rule this file applies everywhere else: a
  deployment able to resolve back onto 0.8 gets the endpoint, gets
  `search.W008`, and gets no categories — a declaration that resolves to a
  permanent degradation is a declaration that does nothing.
- **`stapel-shop>=0.2.12` → `>=0.2.14`.** The release that widens shop's own
  `stapel-categories<0.9`. Without it the two lines have no common solution
  and pip resolves categories back under this composite's floor.

Nothing in `preset.py` changes: `CATEGORY_SUGGEST_FUNCTION` defaults to
`categories.suggest`, and in this composite's monolith both halves are in one
process and the in-process comm registry resolves it.

## 0.6.0 — 2026-08-31

### The index holds the word a buyer types, not the slug a form stored

`_title_text` took a title chip's text from `features_search` for every type
except the two vocabulary-backed ones, which carry a `labels` snapshot beside
their codes. An inline `select` has the same shape of problem and had no
snapshot to take, so what reached `text_extra` was the storage value: `b-u`,
`prodayu-svoe`, `bez-defektov`, `gps`. Measured on a live board — the only
listings answering «б/у» were the two that happened to spell it in the
description.

- **`REF_TYPES` is now `LABEL_SNAPSHOT_TYPES`, and `select` is in it.** The set
  was always a statement about the DAO SHAPE — a code in `value`, the copy in
  `labels` — and never about where the copy came from. A vocabulary term and an
  inline option are the same problem for a reader. The rename is why this is a
  minor: the name was in `__all__` and it had become untrue.
- The fallback is unchanged and now covers one more case: a DAO with no
  `labels` — written before the vocabulary answered, or before
  stapel-attributes 0.7.0 taught `select` to snapshot at all — still takes its
  codes rather than dropping the attribute out of the text arm. Every listing
  published before that release is such a row until it is re-projected.
- `features_search` is untouched. Codes are the filter axis; an existing
  `f.condition=b-u` keeps matching, and the panel's captions come from
  stapel-search's `facet_labels`, which is the other end of the same fix.

### The ranges that make the fix reachable

Five members move, and every floor moves with its cap for the reason this
package's dependency block has now recorded six times: a deployment able to
resolve back under the version that carries the behaviour is a deployment
whose declaration does nothing, and pip reports that as a successful install.

`stapel-attributes>=0.7,<0.8` (the write-side label snapshot),
`stapel-listings>=0.11,<0.12` (which declares that range itself and carries
`listings_reproject_features`, the only way a write-time snapshot becomes true
again), `stapel-search>=0.6,<0.7` (price as a filter axis, the cross-script
conformance scenario, and captions for the vocabulary-backed facets),
`stapel-categories>=0.8.4` and `stapel-shop>=0.2.12` — the two cap moves that
the attributes and listings lines have no solution without.

## 0.5.4 — 2026-08-31

Five member floors move. This composite's own surface does not, and no code in
it changed — the whole release is the ranges.

`stapel-moderation>=0.4,<0.5` (was `>=0.3,<0.4`), `stapel-reviews>=0.5,<0.6`
(was `>=0.4,<0.5`), `stapel-chat>=0.6.3` (was `>=0.6.1`), `stapel-shop>=0.2.10`
(was `>=0.2.9`), and in the `test` extra `stapel-profiles>=0.17.0` (was
`>=0.16.0`).

### Three publish runs died on a check this composite is the only place to fail

0.5.1, 0.5.2 and 0.5.3 are tagged, and none of them reached PyPI — which has
stood at 0.4.3 since. All three died the same way, in `test_composite.py`:

```
stapel_core.lifecycle.E001: app 'stapel_moderation' handles the 'user.deleted'
action but registers no handler for 'user.merged'
stapel_core.lifecycle.E001: app 'stapel_reviews' ... (the same)
```

A merge re-parents a user's rows onto the surviving account. An app that knows
only deletion strands them: the rows keep pointing at an id that can no longer
sign in, and no erasure is ever requested for it either. `stapel_core` reports
that silence as an ERROR — subscribing `user.merged` and subscribing an
explicit no-op are both green; saying nothing is not.

The handlers had already shipped — stapel-moderation 0.4.0 and stapel-reviews
0.5.0 are both on PyPI. This composite's ranges were what kept a fleet off
them, and a composite is exactly the place where that shows up, because a
composite is the one build that MOUNTS all of these apps at once and runs
`manage.py check` against a realistic host. Nothing was wrong with the code
here; the declaration was wrong, and the gate said so three times.

- **moderation 0.4**: `user.merged` re-parents reports and decisions.
- **reviews 0.5**: `user.merged` re-parents an author's reviews.
- **chat 0.6.3**: `user.merged` moves a guest's participations, authored
  messages and `assigned_operator` rows onto the survivor. Not caught by the
  gate (a resolver was free to pick 0.7.x and did), but `>=0.6.1` admits two
  releases that fail it — and on those a visitor who wrote to a seller and
  then signed in lost the conversation to a CASCADE.
- **profiles 0.17.0**, in the `test` extra: the suite MOUNTS profiles for the
  block provider, so its floor is under the same gate as the members.
- **shop 0.2.10**: its own reviews cap becomes `<0.6`. Held at 0.2.9 (cap
  `<0.5`) the reviews line above has no solution — the fifth
  `ResolutionImpossible` in this composite's history, and the second one this
  month resolved by releasing the member first.

The floors move with the caps for the usual reason: a fleet able to resolve
back onto a member that fails `manage.py check` is a fleet whose declaration
does nothing. 141 passed.

## 0.5.3 — 2026-08-31

The composite kind reaches the stand. Four member ranges move; this composite's
own surface does not.

`stapel-attributes>=0.6,<0.7` (was `>=0.5.1,<0.6`), `stapel-categories>=0.8.3`
(was `>=0.8.2`), `stapel-listings>=0.10.2` (was `>=0.10`),
`stapel-shop>=0.2.9` (was `>=0.2.8`).

### Why the cap had to move rather than hold

0.5.2 pinned the members whose own caps matched this one — every line said
`stapel-attributes<0.6`, and that was coherent. It was also the wall: **2 468
fields of the imported catalogue corpus are composites** (a wholesale
discount ladder — "from N units, M % off", up to five steps; a
compatible-vehicles table),
and until stapel-attributes 0.6.0 no kind could hold a list of rows, so the
importer counted them and dropped them. A composite whose whole subject is an
imported marketplace catalogue cannot cap a fleet under the release that stops
losing 2 % of every leaf's schema.

So the four lines move together, and the floors move with the caps for the
usual reason: a fleet able to resolve back onto the older member is a fleet
whose declaration does nothing.

- **attributes 0.6**: the `group` type — `config.fields` is a list of full
  feature definitions, the value is a list of rows keyed by child slug, and
  each cell is validated by its child's own type. Nesting depth is 1, a child
  may not be a `header`, and a child may not carry `rules` (the rule engine
  reads a flat map of top-level slugs, so a rule inside a row could never
  fire) — all three enforced, not documented.
- **categories 0.8.3**: the contract triad names `GroupConfig`/`GroupDto`,
  `translation_keys` walks a composite's children (they are not catalog rows,
  so nothing else reaches their names and option labels), and the
  ResolvedFeature gate covers the one config that carries FeatureDefs inside
  it. Held at 0.8.2 — whose own cap is `attributes<0.6` — the line above has
  no solution.
- **listings 0.10.2**: `FeatureDto`/`FeatureDao` name the composite, and the
  module states `attributes>=0.6,<0.7`, the range its committed discriminator
  mapping is actually true for. 0.10.1 named the type while still declaring a
  floor of 0.5, so it fails its own contract test on the range it advertises.
- **shop 0.2.9**: its own attributes cap becomes `<0.7`. Held at 0.2.8 (cap
  `<0.6`) this composite's attributes line has no solution — the same
  `ResolutionImpossible` walked into four times now.

Nothing in this package reads the new type: search skips it (a table has no
single filterable value), and the ranges are the whole coupling.

## 0.5.2 — 2026-08-31

Patch on a patch, one number: `stapel-categories>=0.8.2,<0.9` (was `>=0.8.1`).

The reason is metadata, not behaviour. 0.8.2 is where stapel-categories caps
`stapel-attributes<0.6` instead of `<1.0` — the same cap this composite
declares. Held at 0.8.1, a resolver may install a categories whose own range
admits stapel-attributes 0.6, the release that adds a thirteenth built-in type
(`group`) and moves the discriminator mapping categories emits; categories
0.8.1's own publish run is where that combination first failed.

Everything 0.5.1 says about the categories floor still holds — see below.

## 0.5.1 — 2026-08-31

Patch: the member ranges move, nothing about this composite's surface does.

### `stapel-categories>=0.8.1,<0.9` (was `>=0.7,<0.8`)

Both numbers in that jump are about the catalogue this composite exists to
carry.

**0.8.0** stops keying a catalog re-import on the **slug**. An imported
category's slug is derived from the source catalogue's node path, so when the
source renames a node the slug moves and the node id does not — and under the
old key that re-import read as "one category disappeared, an unrelated one
appeared": it soft-deleted the row holding the listings and created a duplicate
beside it. Matching is `(external_source, external_id)` first now, the slug
only as a fallback for rows with no source id.

**0.8.1** is what makes a full-catalog import finish at all. django-treenode
rebuilt its denormalized tree columns from a `post_save` receiver — one read of
the table plus one `UPDATE` per row — for every row written, and `load_catalog`
writes every record through `save()` by design. A 2901-leaf catalogue import (3444
categories, 14 409 feature rows, 52 488 links) never completed; it is 185 s
now.

The floor moves with the cap for this composite's usual reason: a deployment
free to resolve back under either of those is a deployment whose declaration
does not hold.

### `stapel-shop>=0.2.8,<0.3` (was `>=0.2.6`)

Same rule, one member down. shop 0.2.6 and 0.2.7 both cap
`stapel-categories<0.8`, so a resolver left free to pick either picks a shop
whose own cap contradicts the line above and answers `ResolutionImpossible`.
0.2.8 is the shop release that admits categories 0.8.

The "known, deliberate, and not fixed here" hold that 0.5.0 shipped with is
therefore closed: shop 0.2.7 answered the attributes-v2 half of it and 0.2.8
the categories-0.8 half.

## 0.5.0 — 2026-08-30

Minor, and pre-1.0 house semver reads a minor as breaking. The composite
gains a member: **stapel-vocabularies**. A classified marketplace's catalogue
stops being limited to what fits inline in a category schema.

### Added — `stapel_vocabularies` is a member

The attributes-v2 wave (spec §3) splits a feature's options in two. Small
option sets stay inline in the config, as they always were; a *reference
vocabulary* — 529 phone vendors, 14 962 models, 53 836 car makes — lives in
its own tables and a feature points at it with an `optionsRef`. The L2 module
that owns those tables is stapel-vocabularies 0.1.0, and this composite is
where a classified deployment gets it wired.

- `preset.INSTALLED_APPS` gains `stapel_vocabularies`, **first in the list**;
- `preset.URL_INCLUDES` gains `("vocabularies/", "stapel_vocabularies.urls")`
  — the module bakes `api/v1/` in itself (the reviews/geo/search/moderation
  family), so the public prefix is `/vocabularies/api/v1/…`.

### Why the app is FIRST, and why that is a test rather than a comment

`stapel_vocabularies.ready()` hands stapel-attributes the in-process
`OrmResolver` (`register_vocabulary_resolver`). Without a resolver a
`ref_select` / `ref_hierarchical_select` config **does not validate at all**:
saving such a feature raises `INVALID_CONFIG` "no vocabulary resolver
registered". Django runs `ready()` in `INSTALLED_APPS` order, so every app
that validates a ref-typed config has to come after it — `stapel_categories`
first among them, since `Feature.clean` is exactly that call.

An ordering rule stated only in a comment is one someone re-sorts
alphabetically six months later, so
`tests/test_vocabularies.py::test_vocabularies_loads_before_anything_that_validates_a_ref_config`
asserts the index, and a positive/negative pair asserts the consequence: a
`ref_select` feature naming a real level saves, one naming a level the
vocabulary lacks is refused. The second half matters as much as the first —
a suite that only proved "a resolver is registered" would pass against one
that answers yes to everything.

### Changed — a vocabulary-backed title chip travels as a LABEL

`search_sources._title_text` builds the index's weight-B text arm from the
attributes flagged `show_at_title`. It took every value out of
`features_search`, which is right for every type but the two new ones: their
`features_search` entry is the term **codes**, deliberately, because a code
is the filter axis and must keep matching across a translation.

A code is not a word anybody typed. Rendered on a result row it reads
`iphone-10`; searched for as "iPhone 10" it matched nothing but the free-text
title. So for `ref_select` / `ref_hierarchical_select` the text arm now takes
the DAO's `labels` — the display snapshot listings stores beside the codes at
publish time (listings 0.10.0). Nothing is re-derived and no second read path
is invented: `features_title` is served, it is a DAO list by contract, and
`features_search` still carries the codes untouched into `features_search=`.

Two smaller properties came with it: an empty `labels` (a DAO written before
the vocabulary could answer) falls back to the codes rather than dropping the
attribute out of the text arm, and DAO order is now preserved — the values
used to come out of a `set`, and `text_extra` is compared field by field in
the rebuild-vs-live gate.

### Changed — the pin block

| Package | 0.4.3 | 0.5.0 |
|---|---|---|
| stapel-attributes | *(transitive)* | `>=0.5.1,<0.6` |
| stapel-categories | `>=0.5.6,<0.6` | `>=0.7,<0.8` |
| stapel-listings | `>=0.9,<0.10` | `>=0.10,<0.11` |
| stapel-search | `>=0.2.2,<0.3` | `>=0.3.1,<0.4` |
| stapel-vocabularies | — | `>=0.1,<0.2` |

`stapel-attributes` becomes a **direct** pin. It is an L1 library and not a
Django app (deliberately absent from `INSTALLED_APPS`), and it arrived
transitively until now. It cannot any more: the new member's entire job is to
implement attributes' `VocabularyResolver` protocol, which is 0.5. Left
transitive, a resolver could settle on 0.4.x and the deployment would boot
with `stapel_vocabularies.W001` — the terms API answering normally while
every ref-typed feature refuses to save.

The other three move for the reason this file has moved a cap twice before: a
deployment able to resolve back onto a version without the behaviour the
composite declares is a deployment whose declaration does nothing. categories
0.7 stores and serves the six new `FeatureDef` keys; listings 0.10 makes
requiredness on publish the rule state and carries the ref DAO whole into
`features_title` / `features_badges`; search 0.3.1 maps `ref_select` to a
`term` facet, `ref_hierarchical_select` to a `path` one, and builds no
`closed_options` for a config with an `optionsRef` (a vocabulary is
open-ended for the planner — zero-filling it would invent counts for 14 962
phone models nobody asked about).

**A known blocker, named rather than papered over.** stapel-shop 0.2.6 — the
newest release there is — caps `stapel-categories<0.6`,
`stapel-attributes<0.5` and `stapel-listings<0.10`, so
`pip install stapel-classified==0.5.0` is `ResolutionImpossible` until
stapel-shop ships a cap bump. Lowering the ranges above to satisfy those
stale caps would pin every deployment to a fleet where rules, form metadata
and ref-typed features do not exist at all: the composite would install and
the vertical it declares would not work. The cap bump belongs in the repo
that owns the caps.

### Config

No new key. `STAPEL_VOCABULARIES` is deliberately **not** in
`preset.SETTINGS_DEFAULTS`: every key in that namespace is optional and its
one axis, `REGISTER_RESOLVER`, already defaults to `true` — which is what a
deployment that MOUNTS the vocabularies wants, the process holding the terms
being the one that answers about them. Restating a default only adds a second
place to drift from, so it is held as a gate the way
`AUTO_APPROVE_ON_PUBLISH` is. `RECOMMENDED_ACCESS_ROLES` is unchanged too:
the read surface is `ReadOnlyOrStaff` (anonymous GETs, no writer at all —
loading a catalogue is `manage.py load_vocabulary`), so there is no clearance
for a role table to grant.

### Operator note

A deployment upgrading to 0.5.0 runs `migrate` for the new app's three tables
(`Vocabulary`, `Term`, `TermEdge`) and loads its catalogues with
`manage.py load_vocabulary <fixture.json>`. Until a vocabulary is loaded, a
`ref_select` feature pointing at its slug refuses to save — the loud failure,
and the intended one.

## 0.4.3 — 2026-08-30

### The cap forbade real presence

`stapel-chat>=0.6.1,<0.7` kept every fleet installing this composite below
chat **0.7.0** — the release where a conversation can say whether the OTHER
participant is actually connected.

Until it, a chat header drew "connected" from the READER's own websocket. In a
classified marketplace that tag sat beside the seller's name and read as "the
seller is online"; it never meant that. Fixing it needs `participants[].online`
and `.last_seen_at`, and this cap is what stopped a deployment from having
them: pip refuses the resolution outright rather than warning, so the cap did
not discourage the upgrade, it made it impossible.

`<0.8` now. **The floor deliberately does NOT move.** 0.4.2's floor moved with
its cap because a deployment able to resolve back onto a version without the
guest wall is a deployment whose declared wall does nothing — that reasoning
does not apply here. Nothing in this composite reads presence, and the two
functions it does read are untouched by 0.7.0:
`chat.conversation_participants` (a conversation's parties and its subject)
and `chat.moderation_content` (a reported message). `>=0.6.1` stays
load-bearing for the reason it always was — 0.6.1 is where chat began refusing
a blocked pair the THREAD at `create_direct`, and 0.4.0 deleted this package's
own pre-creation door on that promise.

Nothing in the composite changes shape, and there is no new key, seam or
migration. Chat 0.7.0's two new participant fields are optional in the
schema's `required` list, so a consumer still on 0.6.x reads a 0.7.0 body
unchanged; its one new table is chat's own.

Suite run against stapel-chat 0.7.0 installed: 125 passed.

## 0.4.2 — 2026-08-30

### The caps forbade the guest wall

`stapel-listings>=0.8,<0.9` and `stapel-reviews>=0.2,<0.4` kept every fleet
installing this composite below listings **0.9.0** and reviews **0.4.0** — the
releases where `ALLOW_ANONYMOUS_WRITES` exists at all.

A client fleet already declares
`STAPEL_LISTINGS["ALLOW_ANONYMOUS_WRITES"] = False` and the reviews
equivalent. On the versions these caps admit, no code reads that key: a guest
is a real authenticated user, satisfies `IsAuthenticated`, and can create and
publish a listing and leave a review. The wall is in the settings file and
nowhere else. Confirmed against a running stand.

pip refuses that resolution outright rather than warning, so the caps did not
discourage the upgrade — they made it impossible, and this composite was one
of two walls (the other is `stapel-shop`, which lifts its own in 0.2.6).
`<0.10` and `<0.5` now, and **the floors move with the caps** — `>=0.9` and
`>=0.4` — for the reason 0.4.1 moved the listings floor to 0.8: a deployment
able to resolve back onto a version without the wall is a deployment whose
declared wall does nothing.

`stapel-shop`'s floor moves to 0.2.6 for the same reason. It carried the same
caps, so a fleet resolving shop 0.2.5 would inherit `<0.9`/`<0.4` through it.

Nothing in the composite changes shape. `search_sources.listing_source()`
still reads `stapel_listings.models.INDEXED_STATUSES` by name and the header
still reads `reviews.aggregate`; neither new release touches those. Full
suite green against listings 0.9.0 + reviews 0.4.0 + shop 0.2.6 (125 passed).

## 0.4.1 — 2026-08-28

### The listings cap forbade the security fix

`stapel-listings>=0.5,<0.8` kept every fleet installing this composite below
0.8.0 — the release that stops the status probe handing `owner_id` and
`moderation_status` to anyone for any listing id. Ids are sequential, so that
was an anonymous enumeration oracle over other people's drafts, rejected and
soft-deleted listings. Confirmed against a running stand.

pip refuses that resolution outright rather than warning, so the cap did not
discourage the upgrade — it made it impossible. `<0.9` now, and the **floor
moves to 0.8 with it**: there is no reason to leave a deployment able to
resolve back onto the leak.

`stapel-shop` floor moves to 0.2.5 for the same reason — it carried the same
cap, and a fleet resolving shop 0.2.4 would inherit `<0.8` through it.

## 0.4.0 — 2026-08-28

Minor, and pre-1.0 house semver reads a minor as breaking. Two things leave
this package: a block door that moved to its owner, and the settings keys that
declared it.

### BREAKING — block enforcement is stapel-chat's, and only stapel-chat's

**The defect was two axes for one fact in one deployment.** This package
carried `STAPEL_CLASSIFIED["BLOCK_ENFORCEMENT"]` while its own preset set
`STAPEL_CHAT["BLOCK_ENFORCEMENT"] = "required"`. An operator turned one
switch, the other stayed where it was, and behaviour was decided by the one
they had never heard of. That is not a disagreement between two libraries —
both agree on the posture — it is one fact with two addresses.

stapel-chat 0.6.1 holds **both** write doors a block has to close: opening a
direct thread (`create_direct`) and sending into one. That is the single point
every client passes. This composite could only ever guard its own
`POST conversations`, and it could never touch the send path at all. chat
0.6.1's changelog wrote the promise down — the pre-creation door here "is
deleted by its next patch now that this has shipped" — and MODULE.md ask #5
held the duplication explicitly until then. This is that release.

**Deleted:**

- `stapel_classified/blocks.py` — the whole module (`blocked_pairs`,
  `is_blocked`, `provider_unreachable_reason`, the `ENFORCEMENT_*` vocabulary,
  and the `BlockCheckUnavailable` re-export);
- `STAPEL_CLASSIFIED["BLOCK_ENFORCEMENT"]` and
  `STAPEL_CLASSIFIED["BLOCK_FUNCTION"]` from `conf.DEFAULTS`, and both axes
  from `docs/capabilities.json`;
- `checks.check_block_enforcement` (`E001` / `E002` / `W001` / `W002`) — chat
  announces the same three states as `chat.E018` / `E017` / `W004` / `W003`;
- the block call and `services.ContactRefused` in
  `confirm_listing_conversation`, its 403 handler in `views.py`, and the error
  keys `error.403.classified_contact_refused` and
  `error.503.classified_blocks_unavailable` with their `ru`/`es` catalogues.

**What replaces it is one statement, on the owner's axis:**
`preset.SETTINGS_DEFAULTS["STAPEL_CHAT"]["BLOCK_ENFORCEMENT"] = "required"`,
unchanged and now unduplicated. chat's own default is `auto` — right for a
generic messaging module that may ship without stapel-profiles; a classified
marketplace runs profiles and blocks between trading strangers are the point,
so the composite raises the floor. Product knowledge as a VALUE, not as a
second axis.

### Why the deleted check was wrong, not merely redundant

`confirm_listing_conversation` takes a `conversation_id`: it only ever runs on
a thread that **already exists**. By this fleet's own doctrine an existing
thread is history, and reading history must not consult the block provider.
Until now this endpoint answered `503 classified_blocks_unavailable` when the
provider was down — an outage standing between a person and their own
correspondence, which is precisely what chat 0.6.1 engineered away by
consulting the provider on the create branch only. `tests/test_blocks.py::
test_confirm_still_answers_200_while_the_provider_is_down` pins it.

### The bridge — `stapel_classified.E003`, "this key moved to STAPEL_CHAT"

`AppSettings` does **not** complain about a dead key inside a namespace dict
(its `conf_checks` only see environment variables). So a deployment left with
`STAPEL_CLASSIFIED = {"BLOCK_ENFORCEMENT": "off"}` would silently inherit
chat's `auto` after upgrading: a posture somebody chose on purpose would just
stop applying. Either moved key now raises an **Error** at boot naming its new
address.

### Migration

1. Move any `BLOCK_ENFORCEMENT` / `BLOCK_FUNCTION` you set under
   `STAPEL_CLASSIFIED` to `STAPEL_CHAT`, and delete them here. `manage.py
   check` refuses to boot with `stapel_classified.E003` until you do, hint
   included. A deployment that set neither has nothing to do: the preset
   already arms `required`.
2. Stop handling `error.403.classified_contact_refused` and
   `error.503.classified_blocks_unavailable` in clients — they are gone.
   chat's `error.403.chat_send_refused` (403, naming no block, no direction)
   and `error.503.chat_blocks_unavailable` are the whole refusal vocabulary
   now, and they arrive from chat's surface. `docs/frontend-contract.md` §5
   and §6 are updated.
3. **`stapel-chat>=0.6.1` is load-bearing, not hygiene.** Against 0.6.0 this
   deletion re-opens the hole ask #5 named: a blocked buyer's empty thread
   arriving in the blocker's inbox. The floor is declared in
   `pyproject.toml` and a resolver cannot land you below it.

The shipped pytest harness (`stapel_classified.testing`, `pytest11`) **stays**
— it is not duplicated enforcement, it is test infrastructure for a fact
profiles owns and chat enforces. Re-targeted: the Function name comes from
`STAPEL_CHAT["BLOCK_FUNCTION"]` and `BlockStore.is_blocked` goes through
`stapel_chat.blocks.is_blocked`. Fixture names and behaviour are unchanged.

### Fixed — the composite pinned its fleet to a geo that cannot serve a map

`stapel-geo>=0.2,<0.4` kept every deployment of this composite below 0.4.0,
which is where the server half of the location picker lives: `GET
/geo/api/v1/map/config` (the one call the picker must have) and
`geocoding/resolve`. The visible consequence in a live classified product was
a listing composer with **two raw fields, `latitude` and `longitude`** —
because that is all a product can offer when the geo it is allowed to install
returns coordinates and nothing else.

The cap is now `<0.5`. Nothing in this package imports `stapel_geo`; the
preset only names it in `INSTALLED_APPS` and mounts its URLs
(`preset.py:25,52`), and the test suite deliberately does not install it at
all (`conftest.py:18`). The declared range was the entire coupling, and it was
raised without a comment saying why it was there — unlike the caps beside it.

stapel-geo 0.4.0 also fixes `lang=ru` silently returning English addresses,
which the same fleet was living with.

## 0.3.3 — 2026-08-26

### Fixed — the shipped pytest plugin registered itself twice

**0.3.2 was tagged and never reached PyPI**: its test job died on every Python
version with `ValueError: Plugin already registered under a different name:
stapel_classified.testing`. The new harness is delivered by a `pytest11`
entry point AND was named in this repo's `conftest.py` `pytest_plugins`;
pytest registers an entry-point plugin under its entry-point name and a
`pytest_plugins` entry under its module name, so the second registration of
the same module is a hard error. **0.3.2 does not exist on PyPI — floor on
`>=0.3.3`**; this release is 0.3.2's feature set unchanged (see below) plus
the fix.

It passed locally for the most boring possible reason: the editable install in
the development virtualenv predated the entry point, so only one of the two
registrations happened here. That is the same "green in my venv, red on a
clean runner" shape the sibling-declaration gate was added for in this very
release — which is why the fix is also a gate:
`test_the_shipped_pytest_plugin_is_registered_exactly_once` asserts both
directions (zero registrations silently removes every fixture; two is this
crash).

### Changed — the frontend contract catches up with what shipped

`docs/frontend-contract.md` §5 and §7 still told the react pair to hide the
composer "knowing it is not enforcement" and to expect two calls at §2.1.
Four of the six gaps that section listed are closed (chat 0.6.0: subjects,
subject-aware `direct_key`, `conversation.created`, the participants read;
profiles 0.16.0: the public-profile card), struck rather than deleted so a
reader can check what a routed ask turned into. The one that remains is
named precisely: chat enforces blocks **at send**, not at conversation
create, so `POST /classified/api/v1/conversations` is what refuses a blocked
contact — call it, and do not read chat's 201 as "allowed". §6 gains
`error.503.classified_chat_unavailable`.

## 0.3.2 — 2026-08-26 (tagged, never published — see 0.3.3)

### ⚠️ BREAKING — `ConversationSubject` is deleted, and the header is read from chat

The table this composite owned from 0.2.0 is **gone**, with its model, its
migration and the endpoint that wrote it. It existed for exactly one reason,
stated in its own docstring the day it was written: stapel-chat keyed a direct
thread by the participant PAIR alone, so one buyer and one seller could hold
exactly ONE thread whatever they discussed, and something had to record which
listing each "contact the seller" was about. **stapel-chat 0.6.0 put the
subject into `direct_key`** — each listing gets its own thread — **and shipped
`chat.conversation_participants`**, so a server can ask who is in a thread
instead of keeping a copy. Both asks are struck from MODULE.md. The workaround
was deleted rather than kept in sync, per the alpha policy: no back-compat
shim, no shadow copy, no dual-read window.

**Read this if you are upgrading a live deployment — chat says it loudly and
so does this:**

> **The first subject-bearing contact after the upgrade opens a NEW thread
> beside the pre-subject one.** A buyer and a seller who already correspond
> have a thread whose `direct_key` carries no subject; the next "write to the
> seller" about a listing produces a *second* thread, about that listing.
> Nothing is migrated and nothing is lost — chat's subject-less key is
> byte-identical to the old one, so every existing thread keeps its id, its
> messages and its participants, and it stays the pair's "about nothing in
> particular" thread. Expect users with existing correspondents to see one
> additional thread appear. Adopting the old thread instead would mean
> deciding *which* of its subjects it was really about, and that is a question
> only a product can answer — which is why neither chat nor this module
> answers it.

**The migration path goes with the model.** `stapel_classified/migrations/` is
deleted, not replaced by a `DeleteModel` — this package now has no models and
therefore no migrations, which `test_no_missing_migrations` asserts. A
`DeleteModel` would have had to claim one of two things the expand/contract
gate checks for and neither is true here: `contract-phase` says the code
stopped using the target *a release ago* (it stopped in this one), and
`cutover-phase` requires a data-carrying `RunPython` that moves the rows
somewhere — and there is nowhere to move them TO. Stamping one of those
subjects onto a pre-0.6.0 thread would put a listing's header over a
conversation that predates it, which is the one thing chat's own release notes
refuse to do.

> **Operator step, if you ever ran 0.2.0–0.3.1:** the table is orphaned, not
> dropped — nothing reads or writes it, and Django no longer knows about it.
> Drop it when convenient:
> `DROP TABLE IF EXISTS classified_conversation_subject;`

### Changed — the surface

- **`POST /classified/api/v1/conversations` records nothing, and answers 200
  instead of 201.** It is a **verification** now, not a claim: the listing
  exists, the caller is not its seller, **chat agrees the caller is in that
  thread and that its subject really is that listing**, and no block stands
  between the two. That last-but-one check closes MODULE.md's oldest known
  limitation — "a binding is a claim by the person who makes it" — because
  there is no longer anything for a caller to claim. `scope_key` is gone from
  the request: chat holds the thread's scope and this reads it back.
- **The client flow is one call shorter.** Create the thread in chat WITH its
  subject (`subject_type: "listing"`, `subject_key: "<listing id>"`); chat
  inlines the card via `classified.subject_cards`. See
  `docs/frontend-contract.md` §2.1.
- **`subject.bound_at` and `previous_subjects` are removed** (not emptied). A
  thread is about one thing now; `previous_subjects` was the honest mirror of
  chat's old arithmetic and would have been permanently `[]`.
- **`subject.meta_status` / `meta_reason` are new.** The one hole nothing in
  the fleet can close at creation time — a thread whose subject names a listing
  whose OWNER is not in it — is now *rendered* rather than hidden:
  `partial` / `subject_owner_not_a_party`. Chat may not know what a listing is,
  so it cannot refuse one; this module can only notice while building the
  header, and a 404 there would also hide honest threads.
- **New error key `error.503.classified_chat_unavailable`** (+ ru/es). A chat
  that cannot be asked is a 503, never an empty page: an empty page is
  indistinguishable from "you are not a party to any of these", and a reader
  would take an outage for a permission boundary.
- **`classified.can_report_message` asks chat who is in the thread.** It read
  the binding row before — a copy of chat's membership that nothing could
  refresh. Still fail-closed, and an unreachable chat is a refusal.
- **This package now owns no models at all**, asserted by
  `test_reports.py::test_this_package_owns_no_queue`.

### Added — the composite declares chat's `listing` subject type

`preset.SETTINGS_DEFAULTS["STAPEL_CHAT"]` is new, for a module that is still
**not a member** (nothing here imports it, `URL_INCLUDES` mounts none of it) —
but a host that mounts chat in a classified marketplace needs two things chat
could not have defaulted:

- **`SUBJECT_TYPES["listing"] → classified.subject_cards`.** Chat's registry
  ships EMPTY on purpose (`listing` belongs to whoever owns listings), and
  without this entry chat refuses `subject_type="listing"` with 400
  `chat_unknown_subject_type`.
- **`BLOCK_ENFORCEMENT: "required"`.** **chat's own default is `auto`** —
  right for a generic chat that may ship without stapel-profiles. **This
  composite sets `required` deliberately**, the same posture its own
  `STAPEL_CLASSIFIED["BLOCK_ENFORCEMENT"]` has had since 0.3.1: a classified
  marketplace runs profiles, blocks between strangers who trade are the point,
  and "no block store here" must be a sentence an operator reads rather than a
  default they inherit. A host that means it can lower either one knowingly.

Note that chat 0.6.0 enforces blocks **at send**, not at conversation
creation, so a blocked pair can still end up with an empty thread; this
composite's own check is what refuses the contact before that. Closing it
properly needs the same check inside chat's `create_direct` — routed upstream
in MODULE.md.

### Fixed — the suite runs against real providers, which is why 0.3.1 never published

0.3.1's publish job died: with `BLOCK_ENFORCEMENT` defaulting to `required`,
21 tests raised `BlockCheckUnavailable` because the harness registered no
`profiles.relationships` provider, and `test_composite` failed on a `channels`
import nothing had declared. **Both were the harness, and both are fixed as
mechanisms rather than as settings.**

- **stapel_profiles is MOUNTED in `conftest.py`**, the way chat and moderation
  already were. A block in these tests is a real `UserRelationship` row read
  back by profiles' real provider; the `profiles.display_names` and
  `profiles.relationships` doubles are deleted. A suite that registers a
  double for the module it is proving a seam against proves only that the
  double agrees with itself. The default posture is unchanged and now asserted
  (`test_required_is_the_default_and_this_harness_meets_it`); only the three
  tests that assert the *no-provider* posture construct it, explicitly, with
  the `no_block_provider` fixture. `classified.W001` is correspondingly no
  longer expected in `test_system_checks_report_no_errors` — the harness is in
  the enforcing state now, and that flip is what the check exists to announce.
- **`[project.optional-dependencies].test` + `tests/test_test_dependencies.py`**
  (ported from stapel-chat 0.5.1, which closed this defect class): every
  sibling the suite needs is declared in `pyproject.toml`, and a gate parses
  the suite and fails if the two disagree. It is extended here to catch
  packages the suite MOUNTS as strings in `INSTALLED_APPS` and never imports —
  which is most of a composite's dependencies, and exactly what `channels`
  arrived through. Both workflows install `-e ".[test]"` and set
  `STAPEL_TEST_STRICT_SIBLINGS=1`, so a missing declared sibling fails instead
  of skipping quietly.

### Changed — pins

- **`stapel-chat>=0.6,<0.7`** (was `>=0.5,<0.6`) — now load-bearing: this
  composite READS chat.
- **`stapel-core>=0.45`** (was `>=0.43`) — chat 0.6.0's floor; a composite's
  pin block exists to fix a combination that installs.
- **`stapel-reviews>=0.2,<0.4` is pinned DIRECTLY** — `preset.INSTALLED_APPS`
  mounts it and the seller rating reads `reviews.aggregate`, and it was
  reaching this package only transitively through stapel-shop. The new
  sibling-declaration gate is what noticed.

## 0.3.1 — 2026-08-24

- stapel-profiles 0.16.0 serves `profiles.relationships` and `profiles.public_cards`, so the two settings this
  module reserved for them stop being placeholders: `BLOCK_ENFORCEMENT` defaults to `required` (the flip MODULE.md
  promised for the first release after the provider shipped) and `PUBLIC_PROFILE_FUNCTION` defaults to
  `profiles.public_cards`. A deployment without profiles sets `auto` / `""` explicitly.
- **Upgrade order:** stapel-profiles to >= 0.16.0 FIRST (rebuild the profiles service), then classified. On a
  deployment whose profiles service still runs 0.15.x, `manage.py check` refuses to boot with `classified.E002`
  naming the floor — a refused deploy, not a dead "write to the seller" button in production. Over a bus
  transport the boot check cannot see a stale remote provider (core's probe says so): there the first contact
  attempt answers 503 with the floor named, so confirm the profiles floor is DEPLOYED, not merely pinned.

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
