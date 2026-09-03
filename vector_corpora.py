"""Corpus providers for stapel-search's vector net (``VECTOR_CORPORA``).

stapel-search ships the registry empty because it knows nothing about
categories; this composite knows the tree, so it declares what gets
embedded — the ``SOURCES`` rule, applied to the second registry. The
vocabulary-label provider is NOT here: stapel-vocabularies owns its terms
and ships ``stapel_vocabularies.vector.label_corpus``; the preset merely
names both under their kinds.
"""
from __future__ import annotations


def category_corpus():
    """One entry per VISIBLE category: the name as the embedded text, the
    ancestry as the payload a suggest row is rendered from.

    The text is the bare name — the string a buyer's typo is a typo OF.
    The payload mirrors what ``categories.suggest`` puts in a row (id,
    slug, name, path, path_ids, depth), so a vector hit renders exactly
    like a name-matched destination, counts and all. Hidden nodes
    (inactive, test, soft-deleted) are skipped for the same reason the
    name matcher skips them: a dropdown must not lead where a buyer
    cannot go.
    """
    from stapel_categories.models import Category
    from treenode.utils import split_pks

    rows = {
        row["pk"]: row
        for row in Category.objects.values(
            "pk", "slug", "name", "tn_ancestors_pks", "active", "is_test", "deleted"
        )
    }
    for pk, row in rows.items():
        if not row["active"] or row["is_test"] or row["deleted"]:
            continue
        ancestor_pks = [int(value) for value in split_pks(row["tn_ancestors_pks"])]
        path_ids = [str(value) for value in (*ancestor_pks, pk)]
        names = [
            (rows.get(ancestor) or {}).get("name") or str(ancestor)
            for ancestor in ancestor_pks
        ] + [row["name"]]
        yield {
            "key": str(pk),
            "text": row["name"],
            "payload": {
                "id": pk,
                "slug": row["slug"],
                "name": row["name"],
                "path": names,
                "path_ids": path_ids,
                "depth": len(path_ids),
            },
        }


def facet_option_corpus():
    """One entry per distinct ``(slug, value)`` an inline ``select`` feature
    offers — the option catalogue a free-text query is matched against.

    This corpus exists because the other two cannot answer for it.
    ``vocab_label`` embeds stapel-vocabularies TERMS, which is where brands
    and models live (``ref_select`` features name a vocabulary and a level);
    a colour, a condition or a size is not a term at all — it is an option
    written inline in the feature's own config, and nothing embedded it.
    Without this provider the deterministic rung answers «красный» and the
    vector rung has nothing to search for «красные», which is the exact
    query a person types.

    The embedded text is the bare label for the same reason
    ``category_corpus`` embeds the bare name: it is the string the buyer's
    word is a variant OF. The payload carries the whole filter, so a hit
    becomes ``f.<slug>=<value>`` without a second lookup.

    Deduplicated by ``(slug, value)``: one option is offered by many
    categories (``color`` appears under most of the tree) and embedding it
    once per category would multiply 25k vectors into 51k identical ones.
    """
    from stapel_categories.models import Category  # noqa: F401  (app loaded)
    from stapel_categories.models import Feature

    seen: set[tuple[str, str]] = set()
    rows = Feature.objects.filter(deleted=False, is_test=False).values(
        "slug", "name", "config"
    )
    for row in rows:
        config = row["config"] or {}
        if config.get("type") != "select":
            continue
        options = config.get("options")
        if not isinstance(options, list):
            continue
        slug = row["slug"]
        for option in options:
            if not isinstance(option, dict):
                continue
            value = option.get("value")
            label = option.get("label")
            # An option with no label has nothing to embed, and one with no
            # value cannot become a filter — skip rather than invent either.
            if not value or not label:
                continue
            identity = (slug, str(value))
            if identity in seen:
                continue
            seen.add(identity)
            yield {
                "key": f"{slug}={value}",
                "text": str(label),
                "payload": {
                    "slug": slug,
                    "value": str(value),
                    "label": str(label),
                    "feature": row["name"] or slug,
                },
            }


__all__ = ["category_corpus", "facet_option_corpus"]
