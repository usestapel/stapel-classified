PYTHON ?= python3

.PHONY: contract contract-check

# First: patch the `surface` section of docs/capabilities.json
# (discoverability-design.md §1.2, stapel_tools.surface --patch) — the symbols
# a product is meant to CALL instead of writing its own, plus a refresh of
# module/version from pyproject. NOTE: the rest of docs/capabilities.json in
# this module is HAND-AUTHORED (no schema/flows/errors triad emitter exists —
# see git log: "author capabilities.json for the stapel-catalog sweep") and
# this target never touches provides/axes/extension_points/requires — only
# module/version/surface. stapel-classified's surface_roots
# (docs/capabilities.meta.json) is deliberately EMPTY: the composite is
# transparent INSTALLED_APPS/urls/config glue over stapel-categories +
# stapel-listings + stapel-reviews + stapel-geo and has no permission classes,
# functions, capability fields or templates of its own.
#
# Second: emit the fifth contract artifact, docs/llms.txt
# (stapel_tools.llms_txt — the module's own context slice for an agent;
# badge-canon §3), from the (now-patched) docs/capabilities.json.
#
# Third: assemble README.md (stapel_tools.readme) from docs/readme.md — the
# human half, the only file a person edits — plus the artifacts above. The
# badge row, the version, the fact table and every doc link are generated,
# so they cannot lag a release the way a hand-written README always has.
contract:
	$(PYTHON) -m stapel_tools.surface . --patch
	$(PYTHON) -m stapel_tools.llms_txt . --out docs
	$(PYTHON) -m stapel_tools.readme .

# Drift gate: surface --patch --check compares the derived module/version/
# surface against the committed capabilities.json; llms_txt's own --check
# mode compares a fresh render against the committed docs/llms.txt; readme
# --check compares a fresh render against the committed README.md.
contract-check:
	$(PYTHON) -m stapel_tools.surface . --patch --check
	$(PYTHON) -m stapel_tools.llms_txt . --check
	$(PYTHON) -m stapel_tools.readme . --check
