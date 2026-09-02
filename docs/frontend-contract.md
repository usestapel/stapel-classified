# stapel-classified — the contract the default chat skin builds against

> Written for the agent building the classified pair in the stapel-react
> monorepo (the chat screen, the conversation list, the report dialog and
> the block affordance). This is the server side of "with whom, and about
> what". Backend version: **stapel-classified 0.3.2**, alongside
> **stapel-chat 0.6.0**, **stapel-profiles 0.16.0** and
> **stapel-moderation 0.3.0**.

## 0. Why this document exists

The owner opened the live product's chat and could not tell **who** he was
talking to or **what** the conversation was about. Both halves are real gaps
and neither belongs to the chat engine: stapel-chat may not know what a
listing is, and stapel-listings may not know what a conversation is. The join
lives here, and so does the header built from it.

Default skins ARE the product, so this is not a set of endpoints a product
may choose to wire. A classified chat screen that does not render the header
below is the screen the owner opened.

What the pair must be able to do with no product-specific code:

1. open a conversation and show **what it is about** — the listing's title,
   price, primary image and whether it is still for sale;
2. show **who** the other person is — display name, avatar, rating,
   member-since, seller or private;
3. start a conversation from a listing page ("write to the seller");
4. report a listing, a seller and a single message, with a reason list that
   comes from the server;
5. block someone, and see the block actually hold.

## 1. Mount and versioning

The host mounts `path("classified/api/", include("stapel_classified.urls"))`:

```
/classified/api/v1/…
```

Take the prefix as configuration (default `/classified/`). No trailing slash
on the conversation routes: `…/conversations` is the endpoint,
`…/conversations/` is a 404.

Three calls, all authenticated (JWT cookie, like every other member surface).
There is no public route here — a conversation header names two people and
what they are trading.

## 2. The three calls

### 2.1 `POST /classified/api/v1/conversations` — "write to the seller"

The button on a listing page. **The subject goes to CHAT now** (0.3.2, with
stapel-chat 0.6.0): a direct thread's identity includes what it is about, so
the thread is created about the listing rather than labelled afterwards.

```js
// 1. chat creates (or returns) the direct thread ABOUT this listing
const conv = await post("/chat/api/v1/conversations", {
  kind: "direct",
  participant_ids: [sellerId],
  subject_type: "listing",
  subject_key: String(listingId),
});

// 2. classified confirms the contact and answers the full header
const header = await post("/classified/api/v1/conversations", {
  conversation_id: conv.id,
  listing_id: String(listingId),
});
```

Step 2 is a **check**, not a write: it is where the listing's existence, the
"not your own listing" rule and the **block** are enforced, and it answers the
header so you do not need a third call. Chat's own 201 already inlines the
listing card (chat resolves it through `classified.subject_cards`), so a skin
that only needs the card can render from step 1 while step 2 is in flight —
but do not treat the thread as open until step 2 answers 200, because that is
where a refused contact is refused.

Request:

```jsonc
{
  "conversation_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",  // from chat
  "listing_id": "412"
}
```

`200` (**not 201** — nothing is created here since 0.3.2) answers the **full
header** (§3).

Safe to repeat: it records nothing, so a retry or a second tab is the same
answer. `scope_key` is gone from the request — chat holds the thread's scope
and this reads it back.

**One buyer + one seller + two listings = two threads.** Chat keys a direct
thread by the pair AND the subject, so "write to the seller" about a second
listing opens a second conversation rather than landing in the first one's.
A pair that was already talking before their deployment upgraded to chat 0.6.0
keeps that older thread as an "about nothing in particular" one, and the first
subject-bearing contact appears NEXT TO it — expect users to see one extra
row, once.

Refusals:

| Status | `localizable_error` | What the UI does |
|---|---|---|
| `400` | `error.400.classified_own_listing` | Hide the button on your own listing; this is the belt-and-braces case. |
| `404` | `error.404.classified_listing_not_found` | The listing was deleted between page load and click. Say so; do not open an empty chat. |
| `404` | `error.404.classified_conversation_not_found` | Chat has no such thread, you are not in it, or its subject is a different listing. Same answer for all three, on purpose (§2.2). |
| `503` | `error.503.classified_chat_unavailable` | Retryable. Chat could not be asked who is in the thread. **Never render an empty header as "no subject"** — that is a different fact. |

### 2.2 `GET /classified/api/v1/conversations/{conversation_id}` — one header

For the open thread. Answers §3, or `404`
`error.404.classified_conversation_not_found` — which is **also** what a
conversation you are not a party of answers, and what a conversation with no
listing subject answers. The three are indistinguishable on purpose: a 403
would confirm that an id names a real thread.

A conversation with **no subject** is a legitimate, permanent state — a
support thread, a group room, and every direct thread created before the
deployment moved to chat 0.6.0. Render the chat without a header rather than
an error page.

`503` `error.503.classified_chat_unavailable` is different and must not be
smoothed into the 404: it means chat could not be asked at all. Retry.

### 2.3 `POST /classified/api/v1/conversations/contexts` — a page of headers

For the conversation list. One call per page, never one per row.

```jsonc
// request
{ "conversation_ids": ["3fa85f64-…", "b1d2…", "…"] }   // ≤ 50 (CONTEXT_BATCH_LIMIT)

// response
{
  "items": { "3fa85f64-…": { /* header, §3 */ } },
  "missing": ["b1d2…"]     // no listing subject, or not yours — see 2.2
}
```

Page it against chat's own conversation list, which is anchor-paginated and
already carries `stream_key` / `socket_path` per row. The classified header
is a **decoration of that row**, not a second source of rows: chat owns the
list, its order and its unread counts.

## 3. The header payload

```jsonc
{
  "conversation_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "scope_key": "",
  "viewer_role": "buyer",              // or "seller" — who YOU are here
  "subject": {
    "type": "listing",
    "key": "412",
    "meta_status": "ok",               // "partial" -> read meta_reason
    "meta_reason": null,
    "listing": {
      "listing_id": "412",
      "title": "Apple iPhone 13 Pro",
      "price": "500.00",               // a STRING; never a float
      "currency": "USD",
      "location_label": "Luxembourg",
      "published_at": "2026-08-20T09:00:00+00:00",
      "status": "published",           // the catalogue's own lifecycle word
      "moderation_status": "approved",
      "state": "available",            // available | unavailable | gone
      "owner_id": "5cc26b64-…",
      "url": "",                       // "" unless the deployment set a template
      "image": {
        "ref": "product/9f3a…",        // opaque CDN ref
        "mime": "image/webp", "ext": "webp", "bytes": 91234,
        "width": 1200, "height": 800, "aspect": 1.5,
        "square": false, "animated": false,
        "preview_b64": "data:image/webp;base64,…",
        "preview_kind": "blur",
        "variants": [{ "tier": 240, "branch": "w", "url": "…",
                       "width": 240, "height": 160 }],
        "meta_status": "ok", "meta_reason": null
      },
      "images": [ /* the gallery, same object shape, images[0] === image */ ],
      "meta_status": "ok", "meta_reason": null
    }
  },
  "counterparty": {
    "user_id": "5cc26b64-…",
    "display_name": "Ada Lovelace",
    "avatar": null,
    "member_since": null,
    "seller_type": "",                 // "" | "private" | "business" (see §7)
    "rating": { "avg": 4.8, "count": 12 },   // or null — never a fabricated zero
    "url": "",
    "meta_status": "ok",
    "meta_reason": null
  }
}
```

### 3.1 `state` is the field this whole surface exists for

| `state` | Means | The skin shows |
|---|---|---|
| `available` | live and for sale | the normal card |
| `unavailable` | exists, not live — `sold`, `paused`, `expired`, `blocked`, `archived` (read `status` for which) | the card, dimmed, with the status as a badge: **"Sold"**, **"No longer available"** |
| `gone` | deleted; `title` and `price` are empty | "This listing was removed" in the card's place |

A public listing read (`GET /listings/api/v1/listings/{id}`) answers **404**
for everything that is not published. That is correct for a stranger and
useless for the person standing in the conversation about it — which is
exactly when a buyer is most confused. **Never fall back to the public read
to fill this card.**

Also distinguish the two `meta_reason`s on a card:
`listing_deleted` (the listing is really gone) vs `catalogue_unavailable`
(the catalogue could not be asked — retry, do not tell the user it was
deleted).

### 3.2 The image is the chat attachment contract

`image` carries the same fields, with the same meanings, as a stapel-chat
attachment — same CDN, same `cdn.describe_many` answer. So reuse the
attachment renderer:

- reserve the box from `aspect` **before** the bytes land (no reflow);
- paint `preview_b64` as the placeholder; `preview_kind` tells you what it
  depicts and is known even before a preview exists;
- build a `srcset` from `variants`;
- `image: null` means the listing has no picture. `meta_status: "missing"`
  with `meta_reason: "unknown_ref"` means the CDN does not know this ref —
  draw the empty-image placeholder, not a broken one.

### 3.2.1 `images` is the gallery; `image` is its first frame

Since 0.7.0 the card carries **`images`** — the seller's own photo order,
capped at `CARD_IMAGES_LIMIT` (10 by default) — in exactly the object shape
described above. `image` did not move and did not change meaning: it is
`images[0]`, so a client written before the gallery existed keeps working and
a client drawing a swipeable strip has something to draw.

- `images: []` and `image: null` are the same fact: this listing has no
  picture.
- A batch that outruns the CDN's `describe_many` budget spends it on every
  card's FIRST photo before anybody's second, so a thumbnail is never starved
  by another card's tenth frame. What did not fit keeps its `ref` and says
  `meta_reason: "not_described"` — measurable enough to link, not enough to
  reserve a box for.
- **The stored SEARCH card carries plain string refs, not these objects.** A
  rebuild indexes a whole corpus and must not ask the CDN once per row, and a
  render snapshot frozen into a stored document goes stale the first time the
  CDN re-encodes anything. Resolve those refs the way you resolve any other
  CDN ref.

### 3.3 `meta_status` on the counterparty

`ok` is the normal answer where stapel-profiles >= 0.16.0 is deployed.
`partial` + `profile_unavailable` means the profile service could not be
asked: the card still carries what is known and says the rest is missing.
Render initials in place of the avatar and omit member-since. Do **not** treat
it as an error, and do not fetch the profile REST endpoint yourself to fill it.

An empty `display_name` is **not** a degradation — it is a person who has
typed no name. Render initials; never invent a placeholder.

### 3.4 `subject.meta_status` — a subject that is not this conversation's

`partial` + `subject_owner_not_a_party` means the thread names a listing whose
**owner is not in it**. Nothing can refuse that at creation time (chat may not
know what a listing is), so the server renders it and says so rather than
showing a stranger's listing as if it were what these two are discussing.

Show the card, and a quiet marker beside it — "this listing does not belong to
this conversation" — never a silent header. `previous_subjects` and
`subject.bound_at` were removed in 0.3.2: a thread is about one thing now.

## 4. Reporting — moderation's surface, with this composite's targets

Reports do **not** go through stapel-classified. They go to the queue that
already exists, in stapel-moderation, and this composite declares the four
target types and the marketplace reason codes that make a classified
complaint expressible.

### 4.1 The reason list comes from the server

```
GET /moderation/api/v1/policy?target_type=listing        // public, no auth
```

```jsonc
{
  "reasons": [
    { "code": "prohibited_item", "severity": 4, "requires_description": false,
      "label_key": "moderation.reason.prohibited_item.label",
      "description_key": "moderation.reason.prohibited_item.description",
      "policy_clause": "" }
  ],
  "rules": [ … ], "automated_means": { … }, "human_review": { … }
}
```

**Never hardcode the reason list.** It is an open registry: a deployment adds
`counterfeit_luxury` or drops `already_sold` in its own settings, and a
hardcoded list becomes a form whose options answer 400. Fetch per target
type, render `label_key` through the i18n catalogue, and make the description
field required exactly when `requires_description` is true.

The four target types and what they take:

| `target_type` | `target_key` | Extra |
|---|---|---|
| `listing` | the listing id | — |
| `review` | the review id | — |
| `seller` | the seller's user id | — |
| `chat_message` | **`"<conversation_id>:<message_id>"`** | — (§4.3) |

### 4.2 Filing one

```
POST /moderation/api/v1/reports/
```

```jsonc
{
  "target_type": "listing",
  "target_key": "412",
  "reason_code": "prohibited_item",
  "description": "",          // required iff the reason says so
  "good_faith": true          // the DSA Art. 16(2)(d) checkbox; default false
}
```

`201 {"accepted": true, "report_id": "…", "case_ref": "3fa85f64"}` — show
`case_ref` as "your reference", it is what support quotes back.

Refusals worth their own copy: `409 error.409.moderation_already_reported`
("you already reported this"), `400 error.400.moderation_own_content`,
`403 error.403.moderation_cannot_report`.

### 4.3 Reporting a message is just the key

**Changed in classified 0.3.0 — if you built the evidence dialog described
here before, delete it.** stapel-chat 0.5.0 serves the message
(`chat.moderation_content`), so the platform reads it itself and a report is
the same shape as every other one:

```jsonc
{
  "target_type": "chat_message",
  "target_key": "3fa85f64-5717-4562-b3fc-2c963f66afa6:9c1e…",
  "reason_code": "off_platform_payment"
}
```

Two rules:

1. **`target_key` is composite** — `conversation_id:message_id`. Both halves
   are used: without the conversation the server cannot tell whether you were
   even in the thread, and the check that only the two parties may report a
   message runs off it (a bare message id answers
   `403 error.403.moderation_cannot_report`); the message half is what chat
   reads, and a message quoted under a conversation it does not belong to
   answers `404 error.404.moderation_target_not_found`.
2. **Send no `evidence`.** It is now refused —
   `400 error.400.moderation_evidence_invalid` — because a snapshot beside a
   live read is a second, staler answer to what was said. There is nothing
   for the user to copy, paste or attach: drop the field, and with it the
   "author_id from the header's counterparty" step the old flow needed.

Two consequences worth putting in the dialog copy: a moderator sees the
message **as it is when they open the case** (an edit made after you report
is what they read), and a message deleted or erased before then answers
`404` — a tombstone is gone, not blank, and a moderation case is not the one
place erased text survives.

## 5. Blocking

The block itself belongs to stapel-profiles:

```
POST   /profiles/api/v1/{user_id}/block
POST   /profiles/api/v1/{user_id}/unblock
GET    /profiles/api/v1/me/blocked
GET    /profiles/api/v1/{user_id}/relationship
```

What this composite adds is that the block **holds on the server**: a blocked
pair cannot open a new conversation about a listing (§2.1, `403`).

UI rules:

- **Report and block are two separate acts.** They usually happen together —
  offer "block this user" as a checkbox in the report dialog if you like, but
  issue two calls and report each outcome separately. Neither undoes the
  other.
- **A block never deletes a thread.** Both sides keep reading what was said —
  which is also how a report's evidence stays quotable. Do not remove the
  conversation from the list; mark it.
- **Never disclose direction.** The refusal does not say who blocked whom,
  and the copy must not either.
- **The server enforces it, and the server is stapel-chat — one door, not
  two.** chat refuses a blocked pair the THREAD at creation (0.6.1) and every
  SEND (0.6.0), both with 403 `error.403.chat_send_refused`. This composite
  stopped checking in 0.4.0: its own `POST conversations` refusal
  (`error.403.classified_contact_refused`) and its 503
  (`error.503.classified_blocks_unavailable`) are **gone**, and a client must
  no longer handle either key. Hiding the composer is a courtesy so a user
  does not type into a refusal; it is not the enforcement, and a client that
  skips it changes nothing about what the server allows.
- **A 503 from the check is not "allowed".** chat's
  `error.503.chat_blocks_unavailable` means the block store could not be
  asked. Offer a retry; never fall through to sending.
- **An outage never hides a thread you already have.** chat asks the block
  provider only when a thread is being CREATED, and `POST
  /classified/api/v1/conversations` asks it not at all — so a block-store
  outage cannot stand between somebody and their own correspondence.

## 5b. Engagement on a card, and where a suggestion leads

Two things a storefront cannot assemble correctly from the search answer
alone. Both are seams this composite owns, because it is the module that
registers listings as a stapel-search source.

### 5b.1 The per-viewer overlay — `GET /listings/api/v1/listings/engagement?ids=…`

A SERP card comes out of the SEARCH index. That index cannot carry either
per-viewer flag — `viewed` and `is_favorited` are a property of the READER,
not of the listing — and it must not carry `view_count`, which moves far
faster than a document re-indexed on a listing event. So the grid draws the
cards from search and asks listings, ONCE for the whole page, for the three
things that are about the person looking.

```
GET /listings/api/v1/listings/engagement?ids=412,413,414
{"items": {"412": {"view_count": 37, "viewed": true,  "is_favorited": false},
           "413": {"view_count":  4, "viewed": false, "is_favorited": true}}}
```

- `AllowAny`. `view_count` is public, and both per-viewer flags answer
  `null` for a guest — so this is the SAME request signed in or not, and a
  guest's grid is not a second code path.
- `viewed` / `is_favorited` are THREE-STATE: `true`, `false`, `null`. `null`
  is "not knowable for this reader", which is a different sentence from "no".
  Grey out a card on `true`; render nothing different on `null`.
- An id with no listing is simply ABSENT from `items` — do not read a missing
  key as zeros.
- Capped at `STAPEL_LISTINGS["ENGAGEMENT_BATCH_LIMIT"]` ids (100) per call:
  one page of cards, not a crawl of the board.
- The same three fields are already ON the card and detail serializers of
  the listings REST reads (`GET /listings/api/v1/listings/…`). This endpoint
  exists for the grid that does NOT come from there.

Opening a listing detail (`GET /listings/api/v1/listings/{id}/`) is what
COUNTS a view — the client does not post anything. `viewed` on that response
is the state BEFORE the open, so the read that first sees a listing answers
`false` and the next one answers `true`.

### 5b.2 A suggestion carries its own destination

Every row of `GET /search/api/v1/suggest` now says what its `count` counted
and which page that count describes:

```json
{"name": "Автомобили", "category": "141/151", "count": 2,
 "count_scope": "category", "query": {"category": "141/151"}}
```

- `count_scope: "category"` — a NAME row (`match` exact/prefix/word/substring)
  or a `vector` row. It is a PLACE, and its count ignores the typed text.
- `count_scope: "query_in_category"` — a goods-driven row (`match:
  "listings"`), offered because documents matching the query live there. Its
  count is already text-conditioned.
- `query` is the exact `/query` parameter set the count was computed for.
  **Send it verbatim** (plus your own `type`/`lang`/paging) when the buyer
  follows the row.

Assembling those parameters yourself re-opens the defect this exists to
close: a storefront that appended the typed text to every row's link sent a
place row's honest «2» to a page filtered by BOTH, and the page was empty —
no listing under «Одежда, обувь, аксессуары» spells the category's own name.

## 6. Failure vocabulary, in one place

| Status | Key | Retryable | Copy |
|---|---|---|---|
| 400 | `error.400.classified_own_listing` | no | "This is your own listing" |
| 404 | `error.404.classified_listing_not_found` | no | "This listing no longer exists" |
| 404 | `error.404.classified_conversation_not_found` | no | render the chat with no header |
| 503 | `error.503.classified_chat_unavailable` | **yes** | "Try again in a moment" — and never as "no header": chat could not be asked at all |

Every error body is core's envelope: `{"localizable_error": "<key>", …}`.
Translate by key; never show the English string a server sent.

## 7. What is NOT here yet, and what the skin must not fake

These are routed upstream and named so the pair can build against the shape
that is coming instead of inventing its own:

Four of the six gaps this section listed at 0.3.0 are **closed** — chat 0.6.0
shipped subjects, subject-aware `direct_key`, `conversation.created` and a
participants read; profiles 0.16.0 shipped the public-profile card. The
consequences are in §2.1 and §3.3, and the entries are struck rather than
deleted so a reader can check what a routed ask actually turned into.

| Gap | Owner | What the skin does today |
|---|---|---|
| ~~Conversation subject in chat itself~~ | stapel-chat | **Shipped (0.6.0)** — pass `subject_type`/`subject_key` to chat's create (§2.1). `previous_subjects` is gone. |
| ~~`conversation.created` / server-side create~~ | stapel-chat | **Shipped (0.6.0).** The client still creates the thread; there is nothing to bind afterwards. |
| ~~A public-profile comm read~~ | stapel-profiles | **Shipped (0.16.0)** — `avatar`, `member_since`, `seller_type` arrive where profiles is deployed. Initials remain the renderer for an empty `display_name` (§3.3). |
| **Block enforcement when a conversation is CREATED** | stapel-chat | Chat enforces blocks on every SEND since 0.6.0 — the half no client can bypass. It does not check at create, so a blocked buyer can still open an empty thread that appears in the blocker's inbox; `POST /classified/api/v1/conversations` (§2.1) is what refuses that, and only for clients that call it. **Call it.** Do not treat chat's 201 as "the contact is allowed". |
| Seller ratings | deployment | `rating: null` unless the deployment registers a seller review target. |

Never paper over one of these by reading another service's REST from a
component and pretending the field arrived. A missing field says which
function is missing and why; that is a routed ask, and a UI that hides it
removes the only pressure that closes it.
