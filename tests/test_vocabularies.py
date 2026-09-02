"""stapel-vocabularies as a member of this composite.

The module is L2 and self-contained: its own suite proves its terms API, its
loader and its two resolvers. What only THIS repo can prove is the assembly —
that the app is mounted at all, that it is mounted early enough for its
``ready()`` to have registered a resolver before anything validates a
ref-typed feature config, that its read surface lands on the canonical
prefix, and that a vocabulary-backed value survives the whole
categories -> listings -> search chain with its display half intact.

Every one of those is an integration-seam claim. Nothing here is mocked: the
vocabulary is real rows, the feature is a real ``Feature``, the listing goes
through ``publish_listing``, and the assertion is made on what the mapper
hands stapel-search.
"""
import pytest

from stapel_classified import preset

pytestmark = pytest.mark.django_db


# ── the preset ───────────────────────────────────────────────────────


def test_vocabularies_is_a_member():
    assert "stapel_vocabularies" in preset.INSTALLED_APPS
    mounted = dict((module, prefix) for prefix, module in preset.URL_INCLUDES)
    assert mounted["stapel_vocabularies.urls"] == "vocabularies/"


def test_the_preset_wires_the_query_expander_to_the_search_layer():
    """One normalization layer, consumed, never copied (vocabularies 0.1.3).

    Standalone, the term search matches literally; in THIS composite both
    libraries are installed by construction, so the preset points the
    QUERY_EXPANDER seam at stapel-search\'s variant expansion — the same
    dictionaries the type-ahead uses. The dotted path is asserted to
    IMPORT and to answer the seam\'s contract on a real cross-script query,
    so a rename in either library fails here and not in a buyer\'s picker.
    """
    from django.utils.module_loading import import_string

    dotted = preset.SETTINGS_DEFAULTS["STAPEL_VOCABULARIES"]["QUERY_EXPANDER"]
    expander = import_string(dotted)
    variants = expander("айфон", "ru")
    assert "iphone" in variants


def test_vocabularies_loads_before_anything_that_validates_a_ref_config():
    """The order constraint, asserted rather than left in a comment.

    ``stapel_vocabularies.ready()`` is what registers the in-process
    ``OrmResolver`` with stapel-attributes. Without a resolver a ``ref_select``
    config does not validate at all — ``validate_feature_config`` raises
    INVALID_CONFIG "no vocabulary resolver registered" — so any app whose own
    ``ready()`` or system checks touch a ref-typed config must come after it.
    stapel_categories owns ``Feature.clean``, which is exactly that call, and
    it is the first such app in the list.
    """
    apps = preset.INSTALLED_APPS
    assert apps.index("stapel_vocabularies") < apps.index("stapel_categories")
    # And it is first overall, so a member added later inherits the guarantee
    # instead of having to rediscover it.
    assert apps[0] == "stapel_vocabularies"


def test_the_mount_is_canonical_and_bakes_its_own_api_v1():
    """``/vocabularies/api/v1/...`` — the prefix ``stapel_core.mounts.E004``
    requires, reached the way the preset actually mounts it.

    stapel-vocabularies is in the family that carries ``api/v1/`` in its own
    ``urls.py`` (like reviews, geo, search and moderation), so the preset
    mounts it at a bare ``vocabularies/``. Getting that wrong is not a style
    question: mounted at ``vocabularies/api/`` it would serve
    ``/vocabularies/api/api/v1/...``, and E004 refuses to boot.
    """
    from django.urls import reverse

    assert reverse("vocabularies-list") == "/vocabularies/api/v1/vocabularies/"
    assert reverse(
        "vocabularies-terms", kwargs={"slug": "phones"}
    ) == "/vocabularies/api/v1/vocabularies/phones/terms/"


def test_the_composites_own_emission_mount_is_untouched():
    """``codegen_urls`` stays this package's OWN surface, member-free.

    A composite's contract is what IT serves, never the union of its members'
    — each member emits its own. Adding a member must not add a path to
    ``docs/schema.json`` here, and the emission URLconf is where that would
    happen first.
    """
    from stapel_classified import codegen_urls

    assert [str(p.pattern) for p in codegen_urls.urlpatterns] == ["classified/api/"]


# ── the resolver seam ────────────────────────────────────────────────


def test_the_app_registered_the_in_process_resolver():
    """``REGISTER_RESOLVER`` is held as a GATE, not restated in the preset.

    The default is True and this composite MOUNTS the vocabularies, so the
    process holding the terms is the one that answers about them. The state
    the preset must never be in is the other one — that is
    ``stapel_vocabularies.W002``, and turning the axis off here would produce
    it: every ref_select feature refusing to save while
    ``GET /vocabularies/api/v1/...`` lists the very same terms.
    """
    from stapel_attributes.vocabularies import get_vocabulary_resolver
    from stapel_vocabularies.conf import flag
    from stapel_vocabularies.resolver import OrmResolver

    assert flag("REGISTER_RESOLVER") is True
    assert isinstance(get_vocabulary_resolver(), OrmResolver)


# ── a vocabulary, and the feature that points at it ──────────────────


@pytest.fixture
def phones_vocabulary(db):
    """One level, two terms — the smallest thing a ``ref_select`` can name."""
    from stapel_vocabularies.models import Term, Vocabulary

    vocabulary = Vocabulary.objects.create(
        slug="phones",
        name="Phone vendors",
        levels=[{"name": "Vendor"}],
        term_count=2,
    )
    for sort, (code, label) in enumerate((("apple", "Apple"), ("nokia", "Nokia"))):
        Term.objects.create(
            vocabulary=vocabulary, level="Vendor", code=code, label=label, sort=sort
        )
    return vocabulary


def _ref_config(level="Vendor"):
    return {
        "type": "ref_select",
        "optionsRef": {"vocabulary": "phones", "level": level},
        "minSelected": 0,
        "maxSelected": 1,
    }


def test_a_ref_select_config_validates_under_the_composite(phones_vocabulary):
    """``Feature.clean`` -> ``validate_feature_config`` -> the live resolver.

    This is the whole point of the member: on a deployment without it the
    same save raises INVALID_CONFIG "no vocabulary resolver registered", and
    the catalogue could not hold a vocabulary-backed feature at all.
    """
    from stapel_categories.models import Feature

    feature = Feature(slug="vendor", name="Vendor", config=_ref_config())
    feature.full_clean()  # must not raise
    feature.save()
    assert Feature.objects.get(pk=feature.pk).feature_type == "ref_select"


def test_a_config_naming_a_level_the_vocabulary_lacks_is_refused(phones_vocabulary):
    """The resolver is consulted for real, not merely present.

    A check that only proved "a resolver is registered" would pass against one
    that answers yes to everything; this is the negative half.
    """
    from django.core.exceptions import ValidationError

    from stapel_categories.models import Feature

    with pytest.raises(ValidationError) as excinfo:
        Feature(slug="vendor", name="Vendor", config=_ref_config("Nope")).full_clean()
    assert "Nope" in str(excinfo.value)


def test_a_config_naming_an_unknown_vocabulary_is_refused(phones_vocabulary):
    from django.core.exceptions import ValidationError

    from stapel_categories.models import Feature

    config = {**_ref_config(), "optionsRef": {"vocabulary": "cars", "level": "Vendor"}}
    with pytest.raises(ValidationError):
        Feature(slug="vendor", name="Vendor", config=config).full_clean()


# ── the read surface, under the composite's own URLconf ──────────────


def test_the_terms_surface_answers_an_anonymous_reader(phones_vocabulary):
    """A catalogue is public data: no auth, and a label a person can read."""
    from django.test import Client

    response = Client().get("/vocabularies/api/v1/vocabularies/phones/terms/", {"level": "Vendor"})
    assert response.status_code == 200, response.content[:400]
    body = response.json()
    assert body["total"] == 2
    assert [term["label"] for term in body["results"]] == ["Apple", "Nokia"]


# ── the display half, all the way to the index ───────────────────────


@pytest.fixture
def ref_listing(db, user, phones_vocabulary):
    """A published listing whose title attribute is a vocabulary term.

    Its own category, so the other fixtures' ``brand`` feature cannot make
    the assertions below ambiguous.
    """
    from decimal import Decimal

    from stapel_categories.models import Category, CategoryFeature, Feature
    from stapel_listings.models import Listing
    from stapel_listings.services.publish import publish_listing

    category = Category.objects.create(name="Smartphones", slug="smartphones")
    CategoryFeature.objects.create(
        category=category,
        feature=Feature.objects.create(
            slug="vendor", name="Vendor", config=_ref_config(), show_at_title=True
        ),
        order=0,
    )
    listing = Listing.objects.create(
        owner=user,
        category_id=str(category.pk),
        language="en",
        title_draft="A phone",
        description_draft="A perfectly ordinary phone.",
        price_draft=Decimal("100.00"),
        features_draft={"vendor": {"type": "ref_select", "value": ["apple"]}},
    )
    publish_listing(listing)
    listing.apply_moderation("approved")
    listing.refresh_from_db()
    return listing


def _document(listing):
    from stapel_core.comm import call

    key = str(listing.pk)
    return {**call("listings.search_documents", {"keys": [key]})[key], "key": key}


def test_the_stored_projections_keep_the_code_and_the_label_apart(ref_listing):
    """The two halves, as listings stores them — the premise of everything below.

    ``value`` is the term code (the filter axis, and what a stored filter must
    keep matching after a translation); ``labels`` is the display snapshot
    taken at write time, which is why rendering a sold listing never re-reads
    the vocabulary.
    """
    (dao,) = ref_listing.features_title
    assert dao["type"] == "ref_select"
    assert dao["value"] == ["apple"]
    assert dao["labels"] == ["Apple"]
    assert ref_listing.features_search == {"vendor": ["apple"]}


def test_a_ref_valued_title_chip_reaches_the_index_as_a_label(ref_listing):
    """The composite's own join: codes filter, labels are what a human reads.

    Before 0.5.0 the mapper took every title chip out of ``features_search``,
    which for a vocabulary-backed value is the CODE — a result row would have
    shown ``apple`` and a search for "Apple" would have had nothing but the
    title to match on.
    """
    from stapel_classified.search_sources import map_listing

    document = map_listing(_document(ref_listing))
    assert document.text_extra == ("Apple",)
    # …and the filter axis is untouched: the code is what the facet counts and
    # what an existing `f.vendor=apple` filter keeps matching.
    assert document.features_search == {"vendor": ["apple"]}


def test_a_query_for_the_label_finds_the_listing(ref_listing):
    """End to end through the real index, which is the claim that matters."""
    from django.test import Client

    response = Client().get("/search/api/v1/query", {"type": "listing", "q": "Apple"})
    assert response.status_code == 200, response.content[:400]
    assert {item["key"] for item in response.json()["items"]} == {str(ref_listing.pk)}


def test_a_ref_dao_without_labels_falls_back_to_its_codes():
    """A DAO written before the vocabulary could answer still shows something.

    Dropping the attribute out of the text arm would be the worse failure: the
    chip would vanish rather than read awkwardly, and nothing would say why.
    """
    from stapel_classified.search_sources import _title_text

    payload = {
        "features_title": [{"slug": "vendor", "type": "ref_select", "labels": []}],
        "features_search": {"vendor": ["apple"]},
    }
    assert _title_text(payload) == ("apple",)


def test_non_ref_title_chips_still_come_from_features_search():
    """The unchanged half: one definition of "searchable", and it is listings'."""
    from stapel_classified.search_sources import _title_text

    payload = {
        "features_title": [
            {"slug": "make", "type": "string", "value": "apple"},
            {"slug": "vendor", "type": "ref_select", "labels": ["Apple"]},
        ],
        "features_search": {"make": ["apple"], "vendor": ["apple"]},
    }
    # DAO order is preserved — the category's feature order, not a set's.
    assert _title_text(payload) == ("apple", "Apple")


def test_an_inline_select_reaches_the_index_as_its_option_copy():
    """The same defect one type over, measured live on a classified board.

    An inline ``select`` stores the option's VALUE — a slug of its label —
    and until stapel-attributes 0.7.0 the DAO carried nothing else. So the
    index held ``b-u`` and ``bez-defektov``: a result row a buyer could not
    read, and a word no buyer would ever type. The only listings answering
    «б/у» were the two that happened to spell it in the description.
    """
    from stapel_classified.search_sources import _title_text

    payload = {
        "features_title": [
            {"slug": "condition", "type": "select", "value": ["b-u"], "labels": ["Б/у"]},
            {
                "slug": "screen_condition",
                "type": "select",
                "value": ["bez-defektov"],
                "labels": ["Без дефектов"],
            },
        ],
        "features_search": {
            "condition": ["b-u"],
            "screen_condition": ["bez-defektov"],
        },
    }
    assert _title_text(payload) == ("Б/у", "Без дефектов")


def test_a_select_dao_written_before_the_snapshot_falls_back_to_its_values():
    """Every listing published before stapel-attributes 0.7.0 is this row.

    The index degrades to what it always held rather than losing the
    attribute, and a re-projection is what upgrades it — the same rule the
    ref types have had since 0.5.0.
    """
    from stapel_classified.search_sources import _title_text

    payload = {
        "features_title": [{"slug": "condition", "type": "select", "value": ["b-u"]}],
        "features_search": {"condition": ["b-u"]},
    }
    assert _title_text(payload) == ("b-u",)


def test_a_multiselect_keeps_every_option_and_its_order():
    from stapel_classified.search_sources import _title_text

    payload = {
        "features_title": [
            {
                "slug": "sensors",
                "type": "select",
                "value": ["gps", "wi-fi"],
                "labels": ["GPS", "Wi-Fi"],
            }
        ],
        "features_search": {"sensors": ["gps", "wi-fi"]},
    }
    assert _title_text(payload) == ("GPS", "Wi-Fi")
