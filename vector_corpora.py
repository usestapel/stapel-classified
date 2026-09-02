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


__all__ = ["category_corpus"]
