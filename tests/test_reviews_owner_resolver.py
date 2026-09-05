"""``listing_owner_key`` — the `listing` owner resolver stapel-reviews'
registry calls for `STAPEL_REVIEWS["TARGET_TYPES"]["listing"]["owner_key_for"]``
(preset.py). Unit-level: the comm call is stubbed, because the three branches
that matter (found / not-an-int / unknown listing) never touch it, one of
them by construction.
"""


def test_resolves_the_owner_of_a_real_listing(monkeypatch):
    from stapel_classified.reviews import listing_owner_key

    def fake_call(name, payload):
        assert name == "listings.status"
        assert payload == {"listing_id": 610}
        return {"listing_id": 610, "owner_id": "u-42", "status": "active"}

    monkeypatch.setattr("stapel_core.comm.call", fake_call)
    assert listing_owner_key("610") == "u-42"


def test_a_non_integer_key_never_reaches_comm(monkeypatch):
    from stapel_classified.reviews import listing_owner_key

    def fail_call(name, payload):
        raise AssertionError("must not call comm for a non-integer key")

    monkeypatch.setattr("stapel_core.comm.call", fail_call)
    assert listing_owner_key("not-a-listing-id") is None


def test_an_unknown_listing_answers_none_not_a_raise(monkeypatch):
    from stapel_classified.reviews import listing_owner_key

    def missing_call(name, payload):
        raise LookupError("listing 610 not found")

    monkeypatch.setattr("stapel_core.comm.call", missing_call)
    assert listing_owner_key("610") is None
