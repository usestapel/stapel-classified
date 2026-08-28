# MODULE.md — stapel-classified (agent-facing extension map)

A composite: INSTALLED_APPS/urls/config preset over existing Stapel modules,
plus the cross-domain declarations and the cross-domain READS that no member
is allowed to make.

Members: **shop** (categories + attributes + listings + reviews) + **geo** +
**search** + **moderation**.

**stapel-chat is pinned but is not a member.** Nothing here imports it and
the preset mounts none of it — but since 0.3.2 this composite READS it, so
the pin (`>=0.6`) is load-bearing rather than defensive:
`chat.conversation_participants` (chat 0.6.0) is where a conversation's
parties and its subject come from, and `chat.moderation_content` (chat 0.5.0)
serves a reported message. Mounting chat stays a host's decision; the pin
fixes which chat a deployment that has one must be on. What the preset DOES
declare for it — the `listing` subject type and the block posture — is under
"What the composite declares".

## What a composite may own

The law used to be quoted as "a composite writes no business logic and mounts
no urls". That was never quite what it said — `search_sources.py` has always
been executable, because *this package is the one place that knows both
sides*. Stated properly, and now covering state as well as declarations:

> A composite writes no **member-domain** logic. It MAY own cross-domain
> **join state** — models and comm Functions whose schema is nothing but two
> members' opaque keys plus the minimal glue between them — because no member
> is allowed to hold that join.

`ConversationSubject` passed that test, and 0.3.2 **deleted it anyway**, which
is the more important half of the rule: a composite may own a join *no member
is allowed to hold*, and the day a member can hold it, the composite's copy
stops being a join and becomes a second answer. stapel-chat 0.6.0 can hold it
(`subject_type`/`subject_key`, subject in `direct_key`,
`chat.conversation_participants`), so the table went — model, migration path
and the endpoint that wrote it — rather than being kept in sync. **A
composite's join state is a loan against an upstream gap, and it is repaid by
deletion.** (The migrations package is deleted rather than given a
`DeleteModel`: there is no data path out, so neither expand/contract marker
would be true. The orphan table's `DROP` is an operator step in the 0.3.2
CHANGELOG.)

So this package flips `http=True` in the STAPEL_LIBS registry (a change routed
to stapel-tools), mounts `classified/api/`, owns **no models at all**, and
emits its own contract triad. The members keep every seam they had.

## The conversation header

The product finding: a chat opened in the live classified product was
"unclear with whom, and unclear about what". A messaging engine cannot fix
that and neither can a catalogue.

- **The subject and the parties come from chat** — one batched
  `chat.conversation_participants` for a whole inbox page, then the cards.
  0.2.0-0.3.1 kept them in a `ConversationSubject` table here, append-only and
  many-subjects-per-thread, because chat 0.5.x keyed a direct thread by the
  participant PAIR and one buyer and one seller had exactly one thread
  whatever they discussed. chat 0.6.0 put the subject in `direct_key`; the
  table is deleted and `previous_subjects` with it.
- **`POST conversations` verifies, it does not record.** The listing exists,
  the caller is not its seller, chat agrees the caller is in that thread and
  that its subject is that listing. 200, and nothing written. No block check
  since 0.4.0 — the thread already exists, and that is history.
- **A subject whose owner is not in the thread is RENDERED, not refused**
  (`subject.meta_status: partial`, `meta_reason: subject_owner_not_a_party`).
  Chat cannot refuse it (it may not know what a listing is) and a 404 here
  would hide honest threads; the badge is the closure.
- **`cards.py`** builds the short listing card and the public seller card
  from comm reads only (`listings.search_documents`, `cdn.describe_many`,
  `profiles.public_cards`, `reviews.aggregate`). Its `_base_card` is what
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
`blocked`) and this composite keeps no copy of one — and since **0.4.0** it
keeps no enforcement of one either.

**One door, and it is stapel-chat's.** chat 0.6.1 holds both write doors a
block has to close: opening a direct thread (`create_direct`) and sending
into one. That is the one point every client passes, which a composite
endpoint never was — this package could only guard `POST conversations`, and
it could never touch the send path at all. `BLOCK_ENFORCEMENT` is chat's
axis, chat announces all three of its states at every boot (`chat.W003` /
`E017` / `W004`), and a provider that is present and FAILS answers 503, never
"allowed": an outage is not consent.

**What this composite says about blocking is one value on that axis.**
`preset.SETTINGS_DEFAULTS["STAPEL_CHAT"]["BLOCK_ENFORCEMENT"] = "required"`.
chat's own default is `auto`, right for a generic messaging module that may
ship without stapel-profiles; a classified marketplace runs profiles and
blocks between trading strangers are the point, so the composite raises the
floor. That is product knowledge expressed as a VALUE, not as a second axis —
two switches for one fact is how an operator turns the one they know about
and gets behaviour from the one they do not.

**Deleted in 0.4.0**, on chat 0.6.1's own promise: `blocks.py`, the
`BLOCK_ENFORCEMENT` / `BLOCK_FUNCTION` keys, `checks.check_block_enforcement`
(E001/E002/W001/W002), `services.ContactRefused`, and the error keys
`error.403.classified_contact_refused` /
`error.503.classified_blocks_unavailable`. A deployment that still declares
either moved key under `STAPEL_CLASSIFIED` is told at boot
(`classified.E003`, an Error naming the new address), because AppSettings
cannot see a dead key inside a namespace dict and a declared posture must not
silently stop applying.

The check was not merely redundant, it was doctrinally wrong by the end:
`confirm_listing_conversation` takes a `conversation_id`, so it only ever
runs on a thread that ALREADY EXISTS. That is history, and reading history
must not consult the block provider — answering 503 there put an outage
between a person and their own correspondence, which is exactly what chat
0.6.1 engineered away by consulting the provider on the create branch only.

Blocking never deletes a thread: both sides keep reading what was said, which
is also how a report's evidence stays quotable.

## Testing a deployment with blocks

The preset sets `STAPEL_CHAT["BLOCK_ENFORCEMENT"] = "required"`, so every test
in a consuming project that OPENS a classified conversation needs a REGISTERED
`profiles.relationships` provider or `create_direct` raises
`stapel_chat.blocks.BlockCheckUnavailable`. That is the posture working. It is
also a trap: 0.3.1's own publish job died with 21 red tests for exactly this
reason, and the tempting fix — weaken the posture — is the wrong one every
time.

The harness is not a second enforcer; it is test infrastructure for a fact
**profiles** owns and **chat** enforces. Since 0.4.0 the Function name it
registers under comes from `STAPEL_CHAT["BLOCK_FUNCTION"]`, which is the only
key anything reads.

So the harness ships WITH the module: **`stapel_classified.testing`**, a
pytest plugin. Its `pytest11` entry point loads it for anyone who installs
this package — there is nothing to wire, and **it must not also be named in
`pytest_plugins`** (pytest registers an entry-point plugin under its
entry-point name and a `pytest_plugins` entry under its module name, and the
second one raises `Plugin already registered under a different name`).

```python
from stapel_chat.services import SendRefused

def test_a_blocked_buyer_cannot_open_a_thread(block_provider, buyer, seller):
    block_provider.block(seller, buyer)          # direction as a person acts
    with pytest.raises(SendRefused):
        create_direct(owner=buyer, other_user_id=seller.pk, ...)
```

| Fixture | What it gives you |
|---|---|
| `block_provider` | A working block store, `.block(a, b)` / `.unblock(a, b)` / `.is_blocked(a, b)` / `.set_unavailable()`. Real `UserRelationship` rows where stapel-profiles is **mounted** (`.backend == "profiles"`), an explicit in-memory provider registered under `STAPEL_CHAT["BLOCK_FUNCTION"]` otherwise (`"memory"`). |
| `block` | `block(blocker, blocked)` — the shorthand. |
| `blocks_down` | The provider is registered and FAILING: the 503 case. |
| `no_block_provider` | No block store at all — the state `auto` exists for and `required` refuses to boot in. |

Two things the API keeps apart on purpose, because the module answers them
differently: a provider that is **absent** is a deployment without a block
store (the declared posture decides), and a provider that is **failing** is an
outage (503, always). A fixture that conflated them would let a suite prove
the wrong one.

`memory_block_provider()` is the same thing as a context manager, for a script
or a non-pytest harness. This repo's own suite uses the shipped fixtures
rather than private copies — which is also what keeps them honest.

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
| `STAPEL_CHAT["SUBJECT_TYPES"]` | stapel-chat (`BUILTIN_SUBJECT_TYPES = {}`) | `listing` -> `classified.subject_cards` |
| `STAPEL_CHAT["BLOCK_ENFORCEMENT"]` | stapel-chat (default `auto`) | `required` — see below |

The last two are declared for a module that is **not a member**, which is a
deliberate exception and the only one: a host that mounts chat in a classified
marketplace needs both, and chat could not have defaulted either. Its subject
registry ships empty because `listing` belongs to whoever owns listings, and
without the entry chat refuses `subject_type="listing"` outright (400
`chat_unknown_subject_type`). Its `BLOCK_ENFORCEMENT` defaults to `auto`
because a generic chat may ship without stapel-profiles; **this composite sets
`required`** because a classified marketplace runs profiles and "blocks are
not enforced here" must be a sentence an operator reads, not a default they
inherit. Since 0.4.0 that value is the composite's ENTIRE statement about
blocking — it used to be duplicated by an axis of the same name in
`STAPEL_CLASSIFIED`, which is the two-switches-one-fact defect this release
closed. A host that means it lowers either one knowingly, **there**.

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
- **`chat_message`** — content served by its owner, `chat.moderation_content`
  (stapel-chat 0.5.0). It was **evidence-based** until 0.3.0 because nobody
  served a message at all: the report carried the reporter's own snapshot and
  moderators read it as an attestation, never as a platform read. Now a
  moderator reads the message itself, fetched when the case is opened so an
  edit made after the complaint is visible, and — the thing an attestation
  could never establish — the case names the message's real **author**, which
  is who a Sanction is issued against. Declaring both a `content_function`
  and `evidence` is moderation.E007, so the flag went with the flip; nothing
  migrated, because nothing here ever stored a message.

  Its key is still `<conversation_id>:<message_id>`, and now BOTH halves do
  work. The conversation half is what lets `classified.can_report_message`
  answer off the join table whether the reporter was in the thread at all —
  "only the two people in a conversation may report what was said in it" as a
  server rule, failing CLOSED, unlike moderation's fail-open default for a
  missing callback (right for a public listing, wrong for a private thread).
  The message half is what chat reads, and chat refuses a message quoted
  under a conversation it does not belong to, so the same key is checked
  again on the far side of the seam.

  This is why `stapel-chat>=0.5` is pinned although nothing here imports it
  and the preset mounts none of it: on chat 0.4 the content read has no
  provider and every complaint about a message answers 503. Where a host
  mounts no chat at all, moderation.W006 says so at every boot.

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
| `classified.subject_cards` | `{keys} -> {cards: {key: card}}` | The short listing card, gone ones included. **This is the `card_function` stapel-chat calls for a `listing` subject since its 0.6.0** — the shape was designed against the ask before chat had a registry to name it in, and the upstream landing needed no change here. It is also what this module's own header views use, so one listing has one card everywhere. |
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

### stapel-chat (0.6.1 — all six asks shipped)

1. ~~**A conversation subject.**~~ **Shipped in 0.6.0** — `subject_type` /
   `subject_key` plus a `SUBJECT_TYPES` merge registry with EMPTY built-ins,
   resolved by a batched `card_function`. It landed in the shape written here,
   and `classified.subject_cards` needed no change to be that function.
2. ~~**`direct_key` must include the subject.**~~ **Shipped in 0.6.0.** This
   is the one that let 0.3.2 delete `ConversationSubject`.
3. ~~**A `conversation.created` emit.**~~ **Shipped in 0.6.0.** Not consumed
   here yet: with the subject inside the thread there is nothing left to bind,
   so the event has no work to do in this composite.
4. ~~**`chat.conversation_participants`.**~~ **Shipped in 0.6.0 and adopted** —
   it is where the header's parties and every authorization on this surface
   come from now.
5. ~~**Block enforcement at CREATE, not only at send.**~~ **Shipped in
   0.6.1, and the duplicate door here is deleted in 0.4.0.** It landed in the
   shape written here — the same `blocked_pairs` call, once, on the create
   branch only, refusing with `SendRefused` / `error.403.chat_send_refused`
   (a key that names no block) and letting `BlockCheckUnavailable` travel to
   503. It also brought the distinction this composite had not written down:
   *returning* an existing thread is a read of history and asks the provider
   nothing, so no block-store outage can stand between somebody and their own
   correspondence. That is why the deletion here is a correction and not just
   tidying — see "Blocking".
6. ~~**`chat.moderation_content`.**~~ **Shipped in stapel-chat 0.5.0 and
   adopted in 0.3.0** — the ask is kept here, struck through, because the
   prediction it was written as ("one line of policy, no migration") is worth
   being able to check against what actually happened. It held: the flip was
   two keys in `preset.py`.

### stapel-profiles (0.16.0 — both functions served)

1. **`profiles.relationships`** — `{"pairs": [[a, b], …]} -> {"blocked":
   [[a, b], …]}`, either direction. The block exists in the model and in the
   REST API, and since profiles 0.16.0 a server can read it. The composite's
   preset therefore arms `STAPEL_CHAT["BLOCK_ENFORCEMENT"] = "required"`: a
   deployment without a block provider must say so with `auto`, not inherit a
   silent client-side block. The consumer of the Function is stapel-chat, on
   both doors; this package calls it nowhere since 0.4.0.
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

- ~~**A binding is a claim by the person who makes it.**~~ **Closed in
  0.3.2.** There is no binding to claim: the subject is chat's, membership is
  read from chat, and `POST conversations` verifies both instead of recording
  what a caller said.
- **A subject can still name somebody else's listing.** A client may create a
  thread in chat with `subject_key` pointing at a listing neither party owns;
  chat cannot refuse it (it may not know what a listing is) and this module
  only meets the thread while rendering it. It is therefore rendered with
  `subject.meta_status: partial` / `subject_owner_not_a_party` rather than
  refused — refusing would also hide honest threads (a group room about a
  listing, a listing whose owner changed). What it buys a forger is a public
  listing card next to a badge saying it does not belong to this conversation.
- **A `chat_message` report needs chat in the deployment.** The content read
  is `chat.moderation_content`; where no process serves it, a complaint about
  a message answers 503 rather than falling back to the reporter's word for
  it. That is deliberate — a silent fallback to an attestation would put two
  kinds of "what was said" behind one card — and it is announced at boot
  (moderation.W006), not discovered in the queue.
- **A chat outage is a 503 on this surface, not a thin header.** Every read
  here hangs off `chat.conversation_participants`, and there is no honest
  degraded form: an empty answer is indistinguishable from "you are not a
  party to any of these". Named rather than smoothed over.

## Seams

- `preset.INSTALLED_APPS` / `preset.URL_INCLUDES` / `preset.SETTINGS_DEFAULTS`
  — plain data; a project copies or references them. Override per-project by
  editing the project's own settings, not this package.
- `STAPEL_CLASSIFIED` (`conf.py`) — every read the header makes is a comm
  Function NAME here. No block axis: that one is `STAPEL_CHAT`'s and this
  namespace stopped carrying a copy of it in 0.4.0. No registry either: one
  subject type and one consumer of it, and a merge-registry built before its
  second entry exists documents itself and nothing else.
- `SerializerSeamMixin` / `StapelAPIView` (core's, hoisted in 0.37.0) on
  every view — subclass, set one attribute, remount the URL.
- `search_sources.map_listing` / `listing_source` — replace either in your own
  `STAPEL_SEARCH["SOURCES"]["listing"]` if your product's card or text arm
  differs; the rest of the wiring is unchanged.
- `stapel_classified.testing` — the block harness a consumer's own suite
  needs, shipped rather than reinvented (see "Testing a deployment with
  blocks"). Swap the backend by mounting stapel-profiles or not.
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
