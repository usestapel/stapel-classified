"""The one table a composite is allowed to own: a cross-domain JOIN.

``ConversationSubject`` says what a chat conversation is ABOUT. stapel-chat
may not know what a listing is; stapel-listings may not know what a
conversation is; so the join lives in the one package that knows both sides —
the same reason ``search_sources`` lives here (projections-and-composition
§3, and MODULE.md "What a composite may own").

**Sunset, deliberately.** stapel-chat 0.4.0 has no subject concept. The day
it ships one (``Conversation.subject_type`` / ``subject_key`` plus a
``SUBJECT_TYPES`` registry — the shape routed to its owner and written down
in MODULE.md), this table is MIGRATED INTO IT AND DELETED. It is not a shadow
copy to be kept in sync; a deletion-cutover is the whole plan, and this
comment is the record of it.

**Append-only, and one conversation may carry several subjects.** That is not
a design preference, it is chat 0.4.0's own arithmetic: a direct thread is
keyed by an order-independent hash of the participant PAIR and uniquely
constrained, so one buyer and one seller can only ever have ONE thread no
matter how many listings they discuss. A binding that refused the second
listing would make the card show the wrong thing — the exact defect this
work exists to fix. So every "contact the seller" is recorded, the newest is
the conversation's current subject, and the rest are its history. When chat's
``direct_key`` includes the subject, each listing gets its own thread and
this table degenerates to one row per conversation on its own.
"""
from __future__ import annotations

import uuid

from django.db import models

#: The only subject type this composite knows. A string rather than an enum
#: because it travels to stapel-chat as an opaque name the day chat grows a
#: subject registry, and an enum here would be a second vocabulary to keep
#: in step with that one.
SUBJECT_TYPE_LISTING = "listing"


class ConversationSubject(models.Model):
    """One "this conversation is about that listing" fact.

    No FK to anything: ``conversation_id`` belongs to stapel-chat's database
    and ``subject_key`` to stapel-listings', and in the 7-service topology
    those are three different databases. Opaque keys across a seam are the
    fleet rule, not a shortcut.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    #: Opaque tenant/area partition, mirroring chat's own ``scope_key``.
    scope_key = models.CharField(max_length=255, blank=True, default="", db_index=True)

    #: stapel-chat's ``Conversation.id``.
    conversation_id = models.UUIDField(db_index=True)

    subject_type = models.CharField(max_length=32, default=SUBJECT_TYPE_LISTING)
    #: stapel-listings' primary key, as a string — the module never parses it.
    subject_key = models.CharField(max_length=255)

    #: Who opened the conversation about this subject (the buyer), and the
    #: subject's owner at binding time (the seller). Both are stored because
    #: the context read is authorized against THIS row: chat 0.4.0 exposes no
    #: comm Function that could answer "is this user a participant", so the
    #: binding is what says who the two parties are. See MODULE.md's
    #: "Known limitations" for exactly what that does and does not buy.
    initiator_id = models.UUIDField(db_index=True)
    counterparty_id = models.UUIDField(db_index=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "classified_conversation_subject"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["conversation_id", "subject_type", "subject_key"],
                name="uniq_conversation_subject",
            ),
        ]
        indexes = [
            models.Index(
                fields=["conversation_id", "-created_at"],
                name="classified_conv_recent",
            ),
        ]

    def __str__(self):
        return f"{self.conversation_id} about {self.subject_type}:{self.subject_key}"

    def other_party(self, user_id) -> str:
        """The party that is not ``user_id`` — the counterparty card's subject."""
        return (
            str(self.counterparty_id)
            if str(user_id) == str(self.initiator_id)
            else str(self.initiator_id)
        )

    def involves(self, user_id) -> bool:
        return str(user_id) in (str(self.initiator_id), str(self.counterparty_id))


__all__ = ["SUBJECT_TYPE_LISTING", "ConversationSubject"]
