WORKSPACE ?= ..
REPOS = httk-core httk-atomistic httk-io httk-data httk-workflow httk-analyse httk-serve
SKILL_DIR = skills/httk

.PHONY: docs-snapshot check dist ci clean

# Refresh the skill's references/docs/ from per-repo narrative docs.
# Copies top-level Markdown only (no generated AutoAPI output, no notebooks).
docs-snapshot:
	@for r in $(REPOS); do \
		test -d $(WORKSPACE)/$$r/docs || { echo "missing $(WORKSPACE)/$$r/docs — run from a workspace checkout or set WORKSPACE="; exit 1; }; \
	done
	rm -rf $(SKILL_DIR)/references/docs
	@for r in $(REPOS); do \
		mkdir -p $(SKILL_DIR)/references/docs/$$r; \
		cp $(WORKSPACE)/$$r/docs/*.md $(SKILL_DIR)/references/docs/$$r/; \
		for d in $(WORKSPACE)/$$r/docs/*/; do \
			b=$$(basename $$d); \
			case $$b in _*|reference|notebooks|__pycache__) continue;; esac; \
			ls $$d*.md >/dev/null 2>&1 || continue; \
			mkdir -p $(SKILL_DIR)/references/docs/$$r/$$b; \
			cp $$d*.md $(SKILL_DIR)/references/docs/$$r/$$b/; \
		done; \
		echo "$(SKILL_DIR)/references/docs/$$r: $$(find $(SKILL_DIR)/references/docs/$$r -name '*.md' | wc -l) files"; \
	done
	@date -u +"snapshot: %Y-%m-%dT%H:%M:%SZ" > $(SKILL_DIR)/references/docs/SNAPSHOT
	@echo "Snapshot refreshed; review and commit."

# Validate the source packages without creating distribution files.
check:
	@test -f .codex-plugin/plugin.json
	@test -f $(SKILL_DIR)/SKILL.md
	@for f in architecture.md modules.md campaign.md data-serving.md; do \
		test -f $(SKILL_DIR)/references/$$f || { echo "missing $(SKILL_DIR)/references/$$f"; exit 1; }; done
	@test -f $(SKILL_DIR)/references/docs/httk-workflow/workflow_cli.md || echo "note: docs snapshot absent or incomplete (run make docs-snapshot)"
	@python3 scripts/build_packages.py --check
	@echo "check ok"

dist:
	@python3 scripts/build_packages.py

ci: check dist

clean:
	rm -rf dist
