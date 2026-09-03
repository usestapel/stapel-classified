"""The corpus providers the vector net searches — declared HERE, the SOURCES rule.

stapel-search ships ``VECTOR_CORPORA = {}`` because it knows nothing about
categories or vocabularies; this composite knows both, so it is the one
that says WHAT gets embedded: every visible category name (with its
ancestry as payload, so a bare hit renders as a destination), and — via
stapel-vocabularies' own provider — the brand-shaped vocabulary labels.
"""
import pytest

pytestmark = pytest.mark.django_db


@pytest.fixture
def tree(db):
    from stapel_categories.models import Category

    root = Category.objects.create(name="Обувь", slug="obuv")
    leaf = Category.objects.create(name="Timberland", slug="timberland", tn_parent=root)
    Category.objects.create(name="Черновик", slug="chernovik", is_test=True)
    return root, leaf


def test_category_corpus_yields_visible_names_with_ancestry(tree):
    from stapel_classified.vector_corpora import category_corpus

    root, leaf = tree
    entries = {entry["key"]: entry for entry in category_corpus()}
    assert set(entries) == {str(root.pk), str(leaf.pk)}

    hit = entries[str(leaf.pk)]
    assert hit["text"] == "Timberland"
    assert hit["payload"] == {
        "id": leaf.pk,
        "slug": "timberland",
        "name": "Timberland",
        "path": ["Обувь", "Timberland"],
        "path_ids": [str(root.pk), str(leaf.pk)],
        "depth": 2,
    }


def test_facet_option_corpus_yields_one_entry_per_distinct_slug_value(db):
    """A colour is an inline option, not a vocabulary term — so it is only
    embeddable from here, and only once however many categories offer it."""
    from stapel_categories.models import Feature
    from stapel_classified.vector_corpora import facet_option_corpus

    colour = {
        "type": "select",
        "options": [
            {"label": "Красный", "value": "krasnyy"},
            {"label": "Синий", "value": "siniy"},
        ],
    }
    root = Feature.objects.create(name="Цвет", slug="color", config=colour)
    # `color` is offered all over the tree — the slug is unique only among
    # ROOT features, so the duplicate is a real shape, not a contrived one.
    # 51k option rows on the live stand dedupe to 25k distinct (slug, value);
    # embedding them undeduped would double the corpus for nothing.
    Feature.objects.create(
        name="Цвет", slug="color", config=colour, tn_parent=root
    )
    # Neither a hidden feature nor a non-select one contributes.
    Feature.objects.create(name="Тест", slug="t", config=colour, is_test=True)
    Feature.objects.create(
        name="Пробег", slug="mileage", config={"type": "int"}
    )
    # An option missing either half cannot become a filter.
    Feature.objects.create(
        name="Размер",
        slug="size",
        config={"type": "select", "options": [{"label": "", "value": "x"}]},
    )

    entries = {entry["key"]: entry for entry in facet_option_corpus()}
    assert set(entries) == {"color=krasnyy", "color=siniy"}

    hit = entries["color=krasnyy"]
    assert hit["text"] == "Красный"
    assert hit["payload"] == {
        "slug": "color",
        "value": "krasnyy",
        "label": "Красный",
        "feature": "Цвет",
    }


def test_the_preset_declares_every_corpus_and_the_vocab_seam():
    from stapel_classified.preset import SETTINGS_DEFAULTS

    assert SETTINGS_DEFAULTS["STAPEL_SEARCH"]["VECTOR_CORPORA"] == {
        "category": "stapel_classified.vector_corpora.category_corpus",
        "vocab_label": "stapel_vocabularies.vector.label_corpus",
        "facet_option": "stapel_classified.vector_corpora.facet_option_corpus",
    }
    vocab = SETTINGS_DEFAULTS["STAPEL_VOCABULARIES"]
    assert vocab["VECTOR_SIMILAR_FUNCTION"] == "search.similar"
    assert vocab["VECTOR_LABEL_LEVELS"]
