WORKSPACE ?= ..
REPOS = httk-core httk-atomistic httk-io httk-data httk-workflow httk-analyse httk-serve

.PHONY: docs-snapshot check

# Refresh references/docs/ from a workspace checkout's per-repo narrative docs.
# Copies top-level Markdown only (no generated AutoAPI output, no notebooks).
docs-snapshot:
	@for r in $(REPOS); do \
		test -d $(WORKSPACE)/$$r/docs || { echo "missing $(WORKSPACE)/$$r/docs — run from a workspace checkout or set WORKSPACE="; exit 1; }; \
	done
	rm -rf references/docs
	@for r in $(REPOS); do \
		mkdir -p references/docs/$$r; \
		cp $(WORKSPACE)/$$r/docs/*.md references/docs/$$r/; \
		for d in $(WORKSPACE)/$$r/docs/*/; do \
			b=$$(basename $$d); \
			case $$b in _*|reference|notebooks|__pycache__) continue;; esac; \
			ls $$d*.md >/dev/null 2>&1 || continue; \
			mkdir -p references/docs/$$r/$$b; \
			cp $$d*.md references/docs/$$r/$$b/; \
		done; \
		echo "references/docs/$$r: $$(find references/docs/$$r -name '*.md' | wc -l) files"; \
	done
	@date -u +"snapshot: %Y-%m-%dT%H:%M:%SZ" > references/docs/SNAPSHOT
	@echo "Snapshot refreshed; review and commit."

# Sanity: every file SKILL.md points into exists.
check:
	@test -f SKILL.md
	@for f in architecture.md modules.md campaign.md data-serving.md; do \
		test -f references/$$f || { echo "missing references/$$f"; exit 1; }; done
	@test -f references/docs/httk-workflow/workflow_cli.md || echo "note: docs snapshot absent or incomplete (run make docs-snapshot)"
	@echo "check ok"
