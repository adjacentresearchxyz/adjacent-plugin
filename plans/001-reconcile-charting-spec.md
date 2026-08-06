# Plan 001: Reconcile the canonical Adjacent charting specification

> **Executor instructions**: Follow this plan step by step. Preserve the
> existing uncommitted chart-overlay changes in
> `scripts/chart-build.py`, `openclaw-plugin/src/index.ts`, and
> `openclaw-plugin/README.md`. Do not overwrite or revert them.
>
> **Drift check (run first)**:
> `git diff --stat 1f62e51..HEAD -- scripts/adjacent_chart_style.py AGENTS.md .factory/skills/adjacent-chart-style/SKILL.md .hermes/plugins/adjacent/skills/adjacent-chart-style/SKILL.md plugins/adjacent/skills/adjacent-chart-style/SKILL.md`
> If any in-scope file changed since this plan was written, compare the
> current excerpts below before proceeding.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: none
- **Category**: tech-debt
- **Planned at**: commit `1f62e51`, 2026-08-06

## Why this matters

The supplied charting document is a useful operational specification, but it
currently conflicts with this repository's `AGENTS.md` and the actual helper.
If copied verbatim, agents may apply the wrong palette, source-line format,
axis rules, or label placement. This plan makes one repository-relative
charting source of truth, keeps the Python helper canonical, and adds drift
checks so future host packages do not silently diverge.

## Current state

- `scripts/adjacent_chart_style.py` is the executable canonical helper. It is
  the implementation used by chart producers and is approximately 1,554 lines,
  not the 512-line helper described in the downloaded document.
- `AGENTS.md:137-178` currently specifies:
  - canvas `#ece9e2`
  - ink `#0a0f0d`
  - lone series off-black
  - series cycle green, orange, blue, purple, sage, pink
  - source line exactly `Source: Adjacent`
  - horizontal gridlines and no redundant chart furniture
- The downloaded source document was
  `/Users/lucas/Downloads/Telegram Desktop/charting_plugin_update.md`.
  It is not part of the repository and uses `/opt/data/...` absolute paths.
- Chart-style skill copies exist in:
  - `.factory/skills/adjacent-chart-style/SKILL.md`
  - `.hermes/plugins/adjacent/skills/adjacent-chart-style/SKILL.md`
  - `plugins/adjacent/skills/adjacent-chart-style/SKILL.md`
- The repository has host-specific packages and tests, but no check that the
  chart-style skill copies or chart helper guidance remain synchronized.

## Decisions to apply

Use this precedence order:

1. The executable behavior and public exports in
   `scripts/adjacent_chart_style.py`.
2. Repository safety and writing rules in `AGENTS.md`.
3. The consolidated charting document, after conflicts are explicitly
   resolved in the repository chart skill.
4. Individual producer scripts.

Do not inline the Python helper into Markdown. Reference it using the
repository-relative path `scripts/adjacent_chart_style.py`. The installed
runtime path may be mentioned separately as an example, but must not be the
only path.

Resolve these conflicts in favor of the existing repository conventions unless
the helper already implements the newer behavior:

- Keep the existing six-color `SERIES` cycle unless the helper and design
  tokens are updated together.
- Keep `Source: Adjacent` as the default source string. Do not add a timestamp
  to generated source text without updating `AGENTS.md`, the helper API, and
  all chart tests together.
- Do not require an x-axis title when the deck or chart context already
  communicates the unit.
- State label placement as chart-type-specific: labels outside bars by
  default, with explicit exceptions for sufficiently large stacked segments.
- Preserve the helper's actual font stacks and exported function signatures;
  do not claim IBM Plex Mono or Lora unless the implementation uses them.
- Preserve the existing no-em-dash, no-emoji, `%` not `pp`, mid-quote, and
  Heikin-Ashi rules.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Python syntax | `python3 -m py_compile scripts/adjacent_chart_style.py` | exit 0 |
| Chart helper tests | `python3 -m pytest tests/test_offline_signals.py tests/test_factory_hooks.py -q` | all selected tests pass |
| Full Python tests | `python3 -m pytest -q` | all tests pass |
| OpenClaw contracts | `python3 -m unittest tests.openclaw.test_openclaw -q` | 64 tests pass or the updated count passes |
| TypeScript build | `cd openclaw-plugin && npm run build` | exit 0 |

## Scope

**In scope:**

- `AGENTS.md`
- `scripts/adjacent_chart_style.py`
- `.factory/skills/adjacent-chart-style/SKILL.md`
- `.hermes/plugins/adjacent/skills/adjacent-chart-style/SKILL.md`
- `plugins/adjacent/skills/adjacent-chart-style/SKILL.md`
- `tests/test_factory_hooks.py`
- new or updated chart-style synchronization tests under `tests/`
- `plans/README.md`

**Out of scope:**

- `scripts/chart-build.py` and the existing multi-index changes
- `openclaw-plugin/src/index.ts` and its existing overlay changes
- direct-index order execution or adding `rebalance-index.py` to OpenClaw
- copying the helper source into any Markdown file
- adding new chart producer families not required for synchronization
- installing Python packages or changing the deployment environment

## Steps

### Step 1: Establish the actual helper contract

Read `scripts/adjacent_chart_style.py` and extract the actual public exports,
palette keys, `SERIES`, `SOURCE_DEFAULT`, font stacks, `save()` parameters,
and smoke-test behavior. Update the consolidated charting document into a
repository documentation file, preferably
`docs/charting-plugin-update.md`, using repository-relative helper paths.
Keep the detailed chart recipes and data quirks, but remove absolute-path-only
instructions and mark any environment-specific `/opt/data` paths as
deployment examples.

**Verify**:
`test -f docs/charting-plugin-update.md && grep -F 'scripts/adjacent_chart_style.py' docs/charting-plugin-update.md`
must succeed.

### Step 2: Resolve contradictions explicitly

Update `AGENTS.md` and the three host copies of the chart-style skill so they
agree on the resolved rules in the Decisions section. The skill should point
to the helper rather than reimplementing palette values or helper behavior.
Include a short “source of truth and precedence” section and a warning not to
inline or fork the helper API.

**Verify**:
`rg -n 'Source: Adjacent|SERIES|scripts/adjacent_chart_style.py|Heikin-Ashi' AGENTS.md .factory/skills/adjacent-chart-style .hermes/plugins/adjacent/skills/adjacent-chart-style plugins/adjacent/skills/adjacent-chart-style`
must find the same resolved rules in each host copy.

### Step 3: Add synchronization and contract tests

Add tests that:

- verify the helper exports the documented `SOURCE_DEFAULT`, `SERIES`, and
  required formatting functions
- verify the three host chart-style skill files exist
- verify each host copy contains the repository-relative helper reference and
  the resolved source-line and mid-quote rules
- fail if an absolute `/opt/data/adjacent-plugin` path is presented as the
  only canonical path

Follow the existing standard-library and pytest test style in
`tests/test_factory_hooks.py` and `tests/test_offline_signals.py`. Do not
assert the full Markdown document verbatim, because that would make editorial
wording unnecessarily brittle.

**Verify**:
`python3 -m pytest tests/test_chart_style_contract.py -q`
must pass with the new tests.

### Step 4: Run all verification and preserve unrelated work

Run every command in the Commands table. Review `git diff --stat` and confirm
the pre-existing chart overlay files remain intact and no generated `dist`,
PNG, CSV, cache, or virtual-environment files are added.

**Verify**:
`git status --short` shows only the intended chart-spec files plus the
pre-existing chart overlay files.

## Test plan

- Add `tests/test_chart_style_contract.py`.
- Test helper API shape and canonical defaults.
- Test host skill presence and cross-host references.
- Test the resolved source-line, palette-cycle, mid-quote, and Heikin-Ashi
  contract.
- Run the existing chart hook and offline signal tests.
- Run the full Python suite and OpenClaw contract suite.

## Done criteria

- [ ] `docs/charting-plugin-update.md` exists and uses repository-relative
  canonical paths.
- [ ] No Markdown file claims to contain or replace the helper source.
- [ ] `AGENTS.md` and all three host chart skills agree on resolved rules.
- [ ] The helper API and source default are covered by tests.
- [ ] Cross-host chart skill synchronization is covered by tests.
- [ ] Full Python tests pass.
- [ ] OpenClaw contract tests pass.
- [ ] TypeScript build passes.
- [ ] Existing uncommitted chart-overlay work is preserved.

## STOP conditions

Stop and report instead of improvising if:

- The helper exports or defaults differ materially from the Decisions section.
- The downloaded document requires a palette or typography change that cannot
  be reconciled with `AGENTS.md` without a design decision.
- Any host intentionally needs a different chart contract.
- A test requires changing the OpenClaw order allowlist.
- Verification requires installing matplotlib or another package.
- Any out-of-scope chart producer must be edited to make the contract pass.

## Maintenance notes

The helper remains the implementation source of truth. Future palette or
layout changes must update the helper first, then `AGENTS.md`, the three host
skill copies, and the contract tests. Keep operational producer inventories
in the documentation, but do not use the inventory as proof that a producer
actually follows the style contract; add a focused producer test when a
specific chart type is promoted to the approved set.
