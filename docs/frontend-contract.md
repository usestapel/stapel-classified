# stapel-classified — the contract the default chat skin builds against

> Written for the agent building the classified pair in the stapel-react
> monorepo (the chat screen, the conversation list, the report dialog and
> the block affordance). This is the server side of "with whom, and about
> what". Backend version: **stapel-classified 0.2.0**, alongside
> **stapel-chat 0.4.0** and **stapel-moderation 0.2.0**.

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

The button on a listing page. **Two steps, in this order**, because
stapel-chat 0.4.0 has no server-side create hook (see §7):

```js
// 1. chat creates (or returns) the direct thread
const conv = await post("/chat/api/v1/conversations", {
  kind: "direct", participant_ids: [sellerId],
});

// 2. classified records what it is about, and answers the header
const header = await post("/classified/api/v1/conversations", {
  conversation_id: conv.id,
  listing_id: String(listingId),
});
```

Request:

```jsonc
{
  "conversation_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",  // from chat
  "listing_id": "412",
  "scope_key": ""            // optional; mirror chat's scope_key if you use one
}
```

`201` answers the **full header** (§3) — render it immediately, do not make a
second call.

Idempotent: the same `(conversation, listing)` pair posted twice is one fact,
and the first writer's parties stand. Retry freely.

Refusals:

| Status | `localizable_error` | What the UI does |
|---|---|---|
| `400` | `error.400.classified_own_listing` | Hide the button on your own listing; this is the belt-and-braces case. |
| `404` | `error.404.classified_listing_not_found` | The listing was deleted between page load and click. Say so; do not open an empty chat. |
| `403` | `error.403.classified_contact_refused` | "This seller cannot be contacted." **Do not** say "you are blocked" or "they blocked you" — the server deliberately does not tell you which, and neither should the UI (§6). |
| `503` | `error.503.classified_blocks_unavailable` | Retryable. The block store could not be asked, and the server refuses rather than guessing. Offer "try again". |

### 2.2 `GET /classified/api/v1/conversations/{conversation_id}` — one header

For the open thread. Answers §3, or `404`
`error.404.classified_conversation_not_found` — which is **also** what a
conversation you are not a party of answers, and what a conversation nobody
ever bound answers. The three are indistinguishable on purpose: a 403 would
confirm that an id names a real thread.

A conversation with no binding is a legitimate state (a support thread, a
thread created before 0.2.0). Render the chat without a header rather than an
error page.

### 2.3 `POST /classified/api/v1/conversations/contexts` — a page of headers

For the conversation list. One call per page, never one per row.

```jsonc
// request
{ "conversation_ids": ["3fa85f64-…", "b1d2…", "…"] }   // ≤ 50 (CONTEXT_BATCH_LIMIT)

// response
{
  "items": { "3fa85f64-…": { /* header, §3 */ } },
  "missing": ["b1d2…"]     // unbound, or not yours — same meaning, see 2.2
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
    "bound_at": "2026-08-24T10:00:00+00:00",
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
    "meta_status": "partial",
    "meta_reason": "profile_unavailable"
  },
  "previous_subjects": [ /* same shape as `subject`, newest first */ ]
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

### 3.3 `meta_status` on the counterparty

`partial` + `profile_unavailable` is the **expected** answer in today's
fleet: no service publishes a public-profile comm read yet (§7), so the card
carries the display name and the rating and says the rest is missing. Render
initials in place of the avatar and omit member-since. Do **not** treat it as
an error, and do not fetch the profile REST endpoint yourself to fill it —
the day the function ships, the same payload arrives complete.

### 3.4 `previous_subjects` — why a thread can have two listings

chat 0.4.0 keys a direct thread by the participant **pair**, so one buyer and
one seller have exactly one thread however many listings they discuss. The
newest binding is the header; the rest are here, newest first.

Render the current subject in the header. If `previous_subjects` is
non-empty, a small "also discussed" affordance is enough. When chat ships
subject-aware threads (§7) this array goes empty on its own — build for both.

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
| `chat_message` | **`"<conversation_id>:<message_id>"`** | `evidence` (§4.3) |

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

### 4.3 Reporting a message needs the message

Nobody in the fleet serves a chat message's content — stapel-chat stores it
and publishes no read for it — so the report carries **your snapshot** of it:

```jsonc
{
  "target_type": "chat_message",
  "target_key": "3fa85f64-5717-4562-b3fc-2c963f66afa6:9c1e…",
  "reason_code": "off_platform_payment",
  "evidence": {
    "text": "Send the deposit to my card, we settle off-site.",
    "author_id": "5cc26b64-…",     // take it from the header's counterparty!
    "conversation_id": "3fa85f64-…",
    "sent_at": "2026-08-24T10:00:00+00:00"
  }
}
```

Three rules:

1. **`target_key` is composite** — `conversation_id:message_id`. Without the
   conversation the server cannot tell whether you were even in the thread,
   and the check that only the two parties may report a message runs off it.
   A bare message id answers `403 error.403.moderation_cannot_report`.
2. **`author_id` comes from the header's `counterparty.user_id`**, not from
   whatever your local message cache says. A direct thread has two people and
   you are one of them, so the author of a message you are reporting is the
   other one — take the server-derived value.
3. **Send the message text.** An `evidence`-less report answers
   `404 error.404.moderation_target_not_found`: there is nothing for a
   moderator to look at. Keep it small — the whole blob is bounded (8 KB by
   default) and an oversized one is **refused**, not truncated
   (`400 error.400.moderation_evidence_invalid`).

Evidence is rendered to moderators as an attestation ("reported as"), never
as content the platform read. Say so in the dialog: it is your quote.

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
- **Do not enforce in the client only.** Today the *message send* path in
  chat is not yet block-aware (§7), so a client that merely hides the compose
  box is the whole enforcement. Hide it — and know that it is a stopgap, not
  the guarantee.

## 6. Failure vocabulary, in one place

| Status | Key | Retryable | Copy |
|---|---|---|---|
| 400 | `error.400.classified_own_listing` | no | "This is your own listing" |
| 403 | `error.403.classified_contact_refused` | no | "This seller cannot be contacted" |
| 404 | `error.404.classified_listing_not_found` | no | "This listing no longer exists" |
| 404 | `error.404.classified_conversation_not_found` | no | render the chat with no header |
| 503 | `error.503.classified_blocks_unavailable` | **yes** | "Try again in a moment" |

Every error body is core's envelope: `{"localizable_error": "<key>", …}`.
Translate by key; never show the English string a server sent.

## 7. What is NOT here yet, and what the skin must not fake

These are routed upstream and named so the pair can build against the shape
that is coming instead of inventing its own:

| Gap | Owner | What the skin does today |
|---|---|---|
| Conversation subject in chat itself (`subject_type`/`subject_key`, subject in `direct_key`, a `SUBJECT_TYPES` registry with a `card_function`) | stapel-chat | Two calls at §2.1, and `previous_subjects` for the shared-thread case. |
| `conversation.created` event / a server-side create function | stapel-chat | The client creates in chat, then binds here. Do not try to bind from a server. |
| Block enforcement on message send | stapel-chat + stapel-profiles | Hide the composer for a blocked pair, knowing it is not enforcement. |
| A public-profile comm read (avatar, member-since, seller type) | stapel-profiles | Initials placeholder; `meta_reason: "profile_unavailable"`. |
| A chat message content read | stapel-chat | Reporter-supplied `evidence` (§4.3). |
| Seller ratings | deployment | `rating: null` unless the deployment registers a seller review target. |

Never paper over one of these by reading another service's REST from a
component and pretending the field arrived. A missing field says which
function is missing and why; that is a routed ask, and a UI that hides it
removes the only pressure that closes it.
