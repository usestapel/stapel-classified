# MODULE.md — stapel-classified (agent-facing extension map)

A composite: INSTALLED_APPS/urls/config preset over existing Stapel modules,
plus the cross-domain declarations — and, since 0.2.0, the cross-domain JOIN
STATE — that no member is allowed to write.

Members: **shop** (categories + attributes + listings + reviews) + **geo** +
**search** + **moderation**.

## What a composite may own

The law used to be quoted as "a composite writes no business logic and mounts
no urls". That was never quite what it said — `search_sources.py` has always
been executable, because *this package is the one place that knows both
sides*. Stated properly, and now covering state as well as declarations:

> A composite writes no **member-domain** logic. It MAY own cross-domain
> **join state** — models and comm Functions whose schema is nothing but two
> members' opaque keys plus the minimal glue between them — because no member
> is allowed to hold that join.

`ConversationSubject` passes that test exactly: stapel-chat may not know what
a listing is, stapel-listings may not know what a conversation is, and the
row is three ids and a timestamp. Anything with domain semantics of its own
still fails it and belongs in a member.

So 0.2.0 flips `http=True` in the STAPEL_LIBS registry (a change routed to
stapel-tools), mounts `classified/api/`, carries one migration, and emits its
own contract triad. The members keep every seam they had.

## The conversation header (0.2.0)

The product finding: a chat opened in the live classified product was
"unclear with whom, and unclear about what". A messaging engine cannot fix
that and neither can a catalogue.

- **`ConversationSubject`** — `(conversation_id, subject_type, subject_key,
  initiator_id, counterparty_id, scope_key)`, append-only, no FKs.
  **Marked for deletion**: when stapel-chat ships native subjects this table
  is migrated into it and dropped (deletion-cutover), never kept as a shadow.
- **Several subjects per conversation are legal**, because chat 0.4.0 keys a
  direct thread by the participant PAIR: one buyer and one seller have
  exactly one thread whatever they discuss. Newest = the header, the rest =
  `previous_subjects`. Refusing the second listing would render the wrong
  card, which is the defect this closes.
- **`cards.py`** builds the short listing card and the public seller card
  from comm reads only (`listings.search_documents`, `cdn.describe_many`,
  `profiles.display_names`, `reviews.aggregate`). Its `_base_card` is what
  `search_sources._card` also uses — one definition of "the card", so a
  search hit and a chat header cannot disagree.
- **`state`: `available` / `unavailable` / `gone`.** The public listing read
  404s everything not published; that is right for a stranger and useless for
  the person in the conversation about it, which is exactly when a buyer is
  most confused. `listings.search_documents` serves every status, so the card
  can say "sold" — and a key it does not serve is a listing that was deleted.
- **Degradation is data.** Every enrichment may be unreachable and each names
  itself in `meta_status` / `meta_reason` (`cdn_unavailable`,
  `profile_unavailable`, `catalogue_unavailable`, `listing_deleted`). A chat
  never fails to open because a rating service blinked.

The frontend half is `docs/frontend-contract.md` — the document the default
skins build against, endpoint by endpoint and field by field.

## Blocking

The block belongs to **stapel-profiles** (`UserRelationship`, status
`blocked`) and this composite keeps no copy of one. What it adds is that the
block HOLDS on the server, at the one place a classified conversation begins
(`POST conversations` → 403). `BLOCK_ENFORCEMENT` is an axis with three
states and the deployment is told at every boot which one it is in
(`classified.W001` / `E002` / `W002`) — the rule is "never degrade
*silently*", which is stapel-chat's lesson, not "never degrade". A provider
that is present and FAILS answers 503, never "allowed": an outage is not
consent.

Blocking never deletes a thread: both sides keep reading what was said, which
is also how a report's evidence stays quotable.

## What the composite declares

Two members ship deliberately EMPTY registries, because neither is allowed to
know what a listing or a review is. This package is the one place that knows
both sides, so it is where they meet:

| Registry | Owner | Entry declared here |
|---|---|---|
| `STAPEL_SEARCH["SOURCES"]` | stapel-search (`BUILTIN_SOURCES = {}`) | `listing` -> `stapel_classified.search_sources.listing_source` |
| `STAPEL_MODERATION["TARGET_TYPES"]` | stapel-moderation (`BUILTIN_TARGET_TYPES = {}`) | `listing`, `review`, `seller`, `chat_message` |
| `STAPEL_MODERATION["REASONS"]` | stapel-moderation (non-empty builtins) | `prohibited_item`, `misleading_price`, `already_sold`, `impersonation` |
| `STAPEL_REVIEWS["TARGET_TYPES"]` | stapel-reviews (`BUILTIN_TARGET_TYPES = {}`) | `listing` |
| `shop.listing_review_summary` | stapel-shop | the reviews->listings rating projection |

### The `listing` search source

`stapel_classified/search_sources.py` is the only executable glue in this
package: `listings.search_documents` / `listings.search_export` in,
`SearchDocumentInput` out, invalidated by `listing.published` /
`listing.updated` / `listing.removed`. Registering it is also what wires the
subscribers — a host writes no signal handler.

Two properties worth knowing before you extend it:

- **`visible_statuses` is read from `stapel_listings.models.INDEXED_STATUSES`**,
  not copied. A lifecycle state added upstream cannot leave the index's idea
  of "live" behind.
- **Facets come from `features_search`, not from stapel-attributes DAOs.**
  `listings.search_documents` does not serve the DAO list, so the mapper takes
  stapel-search's declared fallback (`ACCEPT_FEATURES_SEARCH`). The loss is
  real: every attribute lands as a *term*, so `r.<slug>` range filters over
  listing attributes do not work and `hex_color`'s `simple` axis and unit
  context are gone. Closing it is one field in listings' document builder plus
  dropping `features_search=` for `features=` here.

### The four moderation target types

`listing` is **pre**-publication (`listing.submitted` opens the case, nothing
is public until the verdict) and `review` is **post** (published on arrival, a
verdict is a takedown). Both name their owner's `*.moderation_content` under
that owner's own id spelling (`listing_id` / `review_id`).

`seller` and `chat_message` arrived in 0.2.0, and they needed different
answers because the fleet serves their content differently:

- **`seller`** — content served by THIS package
  (`classified.seller_content`): the display name and rating a marketplace
  shows in public, with the seller's own id as `author_id`, which is what
  makes "you cannot report your own content" answerable without trusting
  anything a client sent. `verdict_event` is explicitly `None`: nothing in
  the fleet applies a verdict to an account, and the consequence of a case
  about a person is a `Sanction`, which moderation issues itself against
  core's cross-service blacklist.
- **`chat_message`** — **evidence-based** (stapel-moderation 0.2.0). Nobody
  serves a chat message's content and nowhere in the fleet is one stored that
  this package could reach, so the report carries the reporter's own snapshot
  and it is rendered to moderators as an attestation, never as a platform
  read. Its key is `<conversation_id>:<message_id>` — the composite key is
  not decoration: with the conversation in it, `classified.can_report_message`
  can answer off the join table whether the reporter was in the thread at
  all, which turns "only the two people in a conversation may report what was
  said in it" into a server rule. It fails CLOSED, unlike moderation's
  fail-open default for a missing callback (right for a public listing, wrong
  for a private thread).

`profile` is deliberately still absent: stapel-profiles is not a member and
serves no `profiles.moderation_content`, so a policy for it would point at a
content function nobody serves. `seller` is not that — it is the
marketplace's own notion of a counterparty and the content function has a
provider in the process.

`preset.RECOMMENDED_ACCESS_ROLES` names the moderator clearances the module
documents. It is NOT merged into `SETTINGS_DEFAULTS` — a role table is a host's
org chart, and a composite that installed one would hand out staff mandates a
deployment never asked for.

## Comm surface (0.2.0)

**Provides** (`schemas/functions/`):

| Name | Answers | Why it exists |
|---|---|---|
| `classified.subject_cards` | `{keys} -> {cards: {key: card}}` | The short listing card, gone ones included. **This is the shape a subject-aware stapel-chat will name as its `card_function`** — designed against that ask, and already what this module's own views use, so the upstream landing adds nothing here. |
| `classified.seller_content` | `{seller_id} -> *.moderation_content shape` | The `seller` target type's content. |
| `classified.can_report_message` | `{reporter_id, target_type, target_key} -> {allowed}` | The `chat_message` target type's `can_report`. Fail-closed. |

**Calls** (by name, never imported): `listings.search_documents`,
`cdn.describe_many`, `profiles.display_names`, `reviews.aggregate`, and
`profiles.relationships` for the block. Every one of them is a settings key
in `STAPEL_CLASSIFIED`, so a deployment repoints one without a fork.

**Emits**: nothing. A binding is not a fleet-wide fact — no module consumes
it, and an event nobody subscribes to is the "declared but not connected"
shape this composite's own tests fail on.

## What this composite needs and nobody serves yet

Routed asks, written down so they are shapes to build against rather than
gaps to paper over. Each has a working, honest behaviour in the meantime.

### stapel-chat (0.4.0 today)

1. **A conversation subject.** `Conversation.subject_type` / `subject_key` —
   an opaque pair chat never parses (moderation's `(target_type, target_key)`
   idiom), plus a `SUBJECT_TYPES` merge registry with EMPTY built-ins whose
   policy names a `card_function`. Chat resolves it by comm, batched keys →
   cards exactly like `cdn.describe_many`, and inlines the card in the
   conversation payload. `classified.subject_cards` is that function already.
2. **`direct_key` must include the subject.** Today it hashes the participant
   pair alone and is uniquely constrained among direct threads, so one buyer
   and one seller can hold exactly ONE thread whatever they discuss. Until it
   changes, `previous_subjects` is the honest mirror of that reality.
3. **A `conversation.created` emit.** Chat announces messages and support
   assignment and nothing when a conversation appears, so the binding cannot
   be written server-side and the client has to do it in two calls.
4. **`chat.conversation_participants` (or any participants read).** Without
   it no server can verify that a binder is in the thread — see *Known
   limitations*.
5. **Block enforcement at send.** A block that only stops NEW conversations
   is half a block; the send path is chat's.
6. **`chat.moderation_content`.** With it, `chat_message` stops being
   evidence-based and becomes one line of policy — no migration here,
   because nothing here stores a message.

### stapel-profiles (0.15.0 today)

1. **`profiles.relationships`** — `{"pairs": [[a, b], …]} -> {"blocked":
   [[a, b], …]}`, either direction. The block exists in the model and in the
   REST API; no server in the fleet can read it, which makes every block in
   the fleet client-side today. `BLOCK_ENFORCEMENT` defaults to `auto`
   because of that, and **flips to `required` in the first release after this
   function ships** — recorded here rather than left to memory.
2. **`profiles.public_cards`** — `{user_ids} -> {profiles: {id: {display_name,
   avatar, member_since, seller_type}}}`. Until then the counterparty card is
   `partial` with `profile_unavailable`, and the frontend contract says to
   render initials.

### stapel-tools

`STAPEL_LIBS["classified"]` must become `http=True` with
`url_prefix="classified/api/"` (it reads `http=False, url_prefix=None`), and
its `pin` needs 0.2.0. A generated project otherwise installs the app and
mounts nothing.

## Known limitations (stated, not hidden)

- **A binding is a claim by the person who makes it.** chat 0.4.0 exposes no
  participants read, so `bind_listing_conversation` records the caller as one
  party and the listing's owner as the other, and every context read is
  authorized against that row. Forging one requires the conversation's UUID —
  which only its participants hold — and buys the forger a public listing
  card and a public seller card, i.e. what the listing page already shows.
  What it does buy is mislabelling somebody else's thread, and that closes
  the day chat can answer who is in one.
- **`chat_message` evidence is an attestation.** The composite key narrows
  WHO may file (a party of the thread), which is the strongest available
  answer; the message text and its author remain what the reporter says they
  saw, and moderation renders them as such.
- **The seller card is `partial` in every deployment today.** See the routed
  ask above; the payload names the missing function rather than leaving a
  blank a client would have to guess about.

## Seams

- `preset.INSTALLED_APPS` / `preset.URL_INCLUDES` / `preset.SETTINGS_DEFAULTS`
  — plain data; a project copies or references them. Override per-project by
  editing the project's own settings, not this package.
- `STAPEL_CLASSIFIED` (`conf.py`) — every read the header makes is a comm
  Function NAME here, plus the block-enforcement axis. No registry: one
  subject type and one consumer of it, and a merge-registry built before its
  second entry exists documents itself and nothing else.
- `SerializerSeamMixin` / `StapelAPIView` (core's, hoisted in 0.37.0) on
  every view — subclass, set one attribute, remount the URL.
- `search_sources.map_listing` / `listing_source` — replace either in your own
  `STAPEL_SEARCH["SOURCES"]["listing"]` if your product's card or text arm
  differs; the rest of the wiring is unchanged.
- Member modules keep ALL their own seams (each module's MODULE.md).
- Composition changes (add/remove a member) = a MINOR bump of this package
  (pre-1.0 house semver: minor = breaking).

## Mount canon

`stapel-classified` (its own surface, 0.2.0), `stapel-categories` and
`stapel-listings` contribute only the `v1/` segment and are mounted under
`<mod>/api/`; `stapel-reviews`, `geo`, `search` and
`moderation` bake `api/v1/` in themselves and are mounted at `<mod>/`. Both
shapes end at `/<mod>/api/v1/...`, which is what `stapel_core.mounts.E004`
requires. `tests/test_composite.py` runs the whole system-check suite against
the preset's own URLconf, so a mount that drifts fails here.

## Host actions this composite does not take

- **`STAPEL_ACCESS["ROLES"]`** — see `RECOMMENDED_ACCESS_ROLES` above.
- **`STAPEL_GDPR["DATA_OWNERS"]`** — add `"moderation"` (and bump
  `DATA_OWNERS_VERSION`) if you run stapel-gdpr; moderation stores complaint
  text and complainant identities, and the erasure closure never completes
  without the declaration (`moderation.W005` / `gdpr.E002`).
- **`STAPEL_MODERATION["APPEAL_URL_TEMPLATE"]`** — empty by default, and an
  empty appeal link is what DSA Art. 17 notices.
- **A screener** — `SCREEN_ENABLED` is on by default and
  `ON_SCREENING_FAILURE="hold"`, so with no LLM provider configured every
  submission queues for a human rather than publishing unscreened.
