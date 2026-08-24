# stapel-classified — contract emission + drift gate (contract-pipeline.md §2-3).
#
# Until 0.2.0 this module served no HTTP and owned no state, so it had no
# schema/flows/errors triad and docs/capabilities.json was hand-authored. It
# now serves /classified/api/v1 (the conversation<->listing join no member is
# allowed to hold), so it emits the same five artifacts every other module
# does, from a single-module {classified + core} instance mounted at the
# canonical prefix (_codegen.py / _codegen_settings.py / codegen_urls.py).
#
# A composite's schema is its OWN surface, never the union of its members' —
# each member emits its own.
#
# PYTHON must have the module + its deps importable (the repo venv, or a CI
# venv). Emission is pinned to Python 3.12: drf-spectacular renders component
# descriptions differently across minors, and a contract emitted on the wrong
# one produces false diffs forever.
PYTHON ?= python3

.PHONY: contract contract-check lint test migration-lint

contract:
	$(PYTHON) -m stapel_classified._codegen --out docs
	$(PYTHON) -m stapel_classified._capabilities --out docs
	$(PYTHON) -m stapel_tools.llms_txt . --out docs
	$(PYTHON) -m stapel_tools.readme .

# Drift gate: regenerate into a temp dir and diff against the committed docs/*.
contract-check:
	@tmp=$$(mktemp -d); \
	$(PYTHON) -m stapel_classified._codegen --out "$$tmp" || { rm -rf "$$tmp"; exit 1; }; \
	$(PYTHON) -m stapel_classified._capabilities --out "$$tmp" || { rm -rf "$$tmp"; exit 1; }; \
	$(PYTHON) -m stapel_tools.llms_txt . --out "$$tmp" || { rm -rf "$$tmp"; exit 1; }; \
	rc=0; \
	for f in schema.json flows.json errors.json capabilities.json llms.txt; do \
		if ! diff -q "docs/$$f" "$$tmp/$$f" >/dev/null 2>&1; then \
			echo "DRIFT: docs/$$f is stale — run 'make contract' and commit it"; \
			diff "docs/$$f" "$$tmp/$$f" | head -20; rc=1; \
		fi; \
	done; \
	rm -rf "$$tmp"; \
	$(PYTHON) -m stapel_tools.readme . --check || rc=1; \
	if [ $$rc -eq 0 ]; then echo "contract-check: docs/{schema,flows,errors,capabilities,llms.txt} + README.md up to date"; fi; \
	exit $$rc

# Expand/contract gate for Django migrations (release-management.md §3).
migration-lint:
	$(PYTHON) -m stapel_tools.migration_lint . --strict $(if $(BASE_SHA),--base-sha $(BASE_SHA),)

lint:
	ruff check . --select E,F,W --ignore E501

test:
	$(PYTHON) -m pytest tests/ -q
