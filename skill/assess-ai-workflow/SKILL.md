---
name: assess-ai-workflow
description: Assess AI workflow: run a one-shot, privacy-conscious audit of local OpenCode, Codex, Claude Code, and Cursor histories and generate polished HTML assessments plus a private machine-oriented Markdown evidence dossier. Use when a person or team wants an evidence-backed monthly AI-workflow report or wants to review their agent use, including subagents, skills, MCPs, browser/computer tools, validation, context, handoffs, or model variants such as Luna, without raw prompts, token rankings, or inferred engineering seniority.
---

# Assess AI Workflow

Audit the histories on the current computer, synthesize a role-aware workflow assessment, and return coordinated artifacts: two HTML reports for the person — a private **personal** copy (with real, redacted session excerpts) and a sanitized **shareable** copy — plus a private Markdown evidence dossier intended for later agent review. Execute the full flow from a single invocation. The only permitted interruption is the scope gate in step 2 (confirming which discovered projects are in scope); beyond that, do not interview the user unless no supported history exists.

## Non-negotiable rules

- Remain read-only against source histories, app databases, configs, and repositories.
- Do not access cookies, keychains, saved passwords, environment-variable values, credential stores, or secret files.
- Do not use network search, connectors, or uploads to enrich the assessment.
- Do not copy full prompts, source code, personal messages, emails, tokens, or credentials into agent context or the report.
- Use the deterministic scanner first. Give analyzers only its aggregated inventory and redacted samples.
- Never score productivity, job seniority, engineering ability, or business impact from local histories.
- Never treat tokens, agent count, tool-call count, session duration, chat length, or completion events as quality by themselves.
- Separate `observed`, `inferred`, and `not_measurable`. Attach confidence and coverage to every scored claim.
- Treat a missing or unsupported source as a coverage gap, not a low score.
- Keep Luna or other model names as subsets of their host tool unless an independent history store is actually found.
- Generate one self-contained HTML for the person and one private `workflow-evidence.md` for another agent. Intermediate JSON is temporary unless the user explicitly asks to retain an auditable bundle.
- The Markdown may be deeper than the HTML, but never less private: use paraphrased examples, redacted locators, tool categories, outcomes, and confidence—not raw prompts or responses.

Read [references/privacy.md](references/privacy.md) before scanning. Read [references/rubric.md](references/rubric.md), [references/analysis-contract.md](references/analysis-contract.md), and [references/evidence-dossier-contract.md](references/evidence-dossier-contract.md) before spawning analyzers, scoring, or writing the Markdown dossier.

## One-shot workflow

Resolve `SKILL_DIR` to the directory containing this `SKILL.md`. All script and reference paths below are relative to that directory, never to the user's current repository.

### 1. Create an isolated output directory

Default to:

```text
~/Documents/AI Workflow Assessments/YYYY-MM-DD-assessment/
```

If `~/Documents` is unavailable, use `./ai-workflow-assessment-YYYY-MM-DD/`. Never write assessment artifacts inside a product repository unless the user explicitly chose that destination.

Create the directory under a restrictive umask (`umask 077`) when the shell supports it. The scanner and renderer also restrict the permissions of files they create.

### 2. Confirm scope, then scan in-scope history

**2a. Enumerate projects (scope gate).** Claude Code stores history per working directory under `~/.claude/projects`, and the scanner auto-discovers every one — including session stores written by background/observer agents (e.g. `claude-mem`), which are not the person's own workflow and, being the most numerous, otherwise dominate the bounded sample and drown out real work. So first list what exists:

```bash
python3 "$SKILL_DIR/scripts/scan_histories.py" \
  --list-projects \
  --output-dir <output-dir>/scan
```

This writes `projects.json` (read-only, cheap). It covers **all sources and the LLMs behind them** so the gate can present the whole picture:

- `claude_projects`: one row per Claude project with `key`, `sessions`, `last_modified`, `subagent_files`, and a `likely_background_agent` heuristic.
- `codex`: `detected`, session/file `sessions` count, and `last_modified`.
- `opencode`: `detected`, locally retained SQLite `sessions` count, and `last_modified`.
- `cursor`: `detected` and locations (`sessions` is null — Cursor content lives in SQLite and is only counted during the full scan).
- `llm_signals`: **which LLMs the person has signals from, per source**, as `{raw_model: session_count}` (e.g. `claude: {claude-opus-4-8: 331, claude-sonnet-5: 148, ...}`, `codex: {gpt-5.5: 38, ...}`). Claude counts exclude background-agent dirs so they reflect the person's own usage.

Present **every detected source together with its `llm_signals`** and ask the person **which sources / LLMs to follow** in the analysis — many people use essentially one tool (e.g. only Claude) and will want to skip the rest so faint or noisy sources don't muddy the read. Also ask which Claude projects to include. **Pre-select the sources that carry real signal and pre-deselect `likely_background_agent` Claude projects and metadata-only sources (empty `llm_signals` / 0 messages, e.g. some Cursor builds).** Do not force a source in just because it was detected, and do not silently drop one that has signal — let the person decide. If the environment cannot ask (headless/cron), default to every source with non-empty `llm_signals`, minus `likely_background_agent` projects, and record the assumption as a coverage note. This gate is the one allowed interruption; it satisfies the privacy rule of analyzing only what is placed in scope.

**2b. Scan the in-scope history.** Map the person's choice onto two mechanisms:

- **Sources** (OpenCode / Codex / Claude / Cursor) → `--sources <comma list>`. Drop a whole source by omitting it (e.g. `--sources opencode,codex,claude` leaves Cursor out).
- **Claude projects** → `--exclude-projects=<keys>` (or `--include-projects=<keys>` when only specific projects are wanted). Keys start with `-`, so you MUST use the `=` form — a space form is parsed as a flag. Comma-separate multiple keys.

```bash
python3 "$SKILL_DIR/scripts/scan_histories.py" \
  --output-dir <output-dir>/scan \
  --days 0 \
  --sources <e.g. opencode,codex,claude,cursor — only the sources kept in scope> \
  --role "<role from request, or empty>" \
  "--exclude-projects=<comma-separated Claude keys to drop, e.g. the observer store>"
```

Sampling defaults are tuned for dense, recency-weighted evidence: `--max-samples 300` (redacted qualitative excerpts, recent-first) and `--max-cases-per-month 50` (representative workflow cases kept per calendar month per source). You normally do not pass them; lower them only for a quick look. Case selection is **recent-months-first** — when the budget binds, recent months fill before older ones, because how a person works with AI drifts over time and stale months should not dilute the read. `--days 0` means all locally available history.

Preserve the scanner's reported coverage windows and limitations, and record the scope choice (`scan_parameters.sources`, `scan_parameters.max_samples`, `scan_parameters.max_cases_per_month`, `scan_parameters.claude_project_filter`) in the assessment's methodology. A source can be **detected but metadata-only** (session shells with empty messages / 0 tool calls / 0 samples — e.g. some Cursor builds); treat those as `not interpretable` coverage, never as scored evidence. Do not infer that a source is complete merely because many files exist.

Expected scanner outputs:

- `history-scan.json`: normalized coverage, aggregate metrics, bounded redacted samples, sanitized workflow cases, paths checked, exclusions, and parser limitations.

If no supported source is found, stop and report the exact locations checked. Do not create an empty assessment.

### 3. Analyze each source independently

Spawn one subagent per available primary source, up to the available concurrency limit:

- Codex, including archived sessions and model subsets.
- OpenCode, including parent and delegated sessions retained in its local SQLite store.
- Claude Code, separating historical cache from currently retained detailed transcripts.
- Cursor, distinguishing discoverable metadata from unavailable or unsafe chat content.
- Any additional adapter reported by the scanner.

Give each analyzer only:

- the corresponding source entry and redacted records from `history-scan.json`;
- [references/rubric.md](references/rubric.md);
- [references/analysis-contract.md](references/analysis-contract.md).

Require JSON output at `<output-dir>/analysis-<source>.json`. The analyzer must not reopen raw histories. Its job is to identify workflow patterns, counterexamples, late-discovered failures, coverage limits, and role-relevant evidence.

Promote only `session_type: parent` entries into representative workflow cases. Use subagent entries and delegation tool signals only as nested evidence for a parent case; never inflate the case count with child agents or model variants.

Build locator ledgers only from the scanner's assessment-local HMAC `case_id` and `event_locators`. Never invent event or artifact hashes. When no safe locator exists, use the contract's `locator_omitted: privacy` form and lower traceability confidence.

If subagents are unavailable, perform the same source-isolated analyses sequentially. Do not skip source separation or let one tool's stronger retention dominate the findings.

### 4. Reconcile rather than average

Synthesize the source analyses into `<output-dir>/assessment.json`. Separately synthesize the deeper evidence layer into `<output-dir>/workflow-evidence.json` using the canonical model in [references/evidence-dossier-contract.md](references/evidence-dossier-contract.md). Both files must point to the same source-analysis IDs and coverage window.

- Deduplicate model subsets from their host source.
- Do not add historical caches to retained transcript windows when they overlap or use different grains.
- Prefer rates with explicit denominators over raw counts.
- Use qualitative evidence to explain metrics, not to decorate them.
- Resolve source conflicts explicitly as `convergent`, `conflicting`, or `not_comparable`.
- Infer the person's operating role only when evidence is strong. Otherwise use the rubric's `unknown` lens and lower confidence. A role supplied by the user wins.
- If no display name is supplied, use `Pessoa avaliada`; never infer identity from usernames, home paths, account metadata, or message content.
- Compute the overall workflow-maturity score as the simple average of measurable dimensions, exactly as defined in the rubric. Publish it only when at least five dimensions are measurable; otherwise retain the score.
- Optionally attach `evidence_excerpts` to each dimension for the personal render: an array of `{text, source, date, locator}` drawn from the scanner's already-redacted `qualitative_samples`, giving the subject a concrete, practical example per dimension. Keep excerpts short; scrub third-party identities even here; never add secrets. These render only in the personal variant — the shareable variant drops them.

The assessment must cover:

1. Executive summary.
2. Source coverage and confidence.
3. Operating-role interpretation.
4. Maturity dimensions with evidence.
5. Strongest reusable behaviors.
6. Frictions, waste, and risk.
7. Context and phase hygiene.
8. Delegation and synthesis quality.
9. Validation and closure.
10. Safety and authority controls.
11. Prioritized recommendations with success signals.
12. Methodology, assumptions, and what is not measurable.

### 5. Render and validate the HTML

Render **two audience variants** of the same assessment — a private personal copy and a sanitized shareable copy:

```bash
# Personal — includes real, redacted session excerpts; marked PRIVADO; for the subject only
python3 "$SKILL_DIR/scripts/render_report.py" \
  <output-dir>/assessment.json \
  <output-dir>/assessment-personal.html \
  --audience personal

# Shareable — no excerpts, safe to send to a person or another agent
python3 "$SKILL_DIR/scripts/render_report.py" \
  <output-dir>/assessment.json \
  <output-dir>/assessment-shareable.html \
  --audience shareable
```

`--audience` defaults to `shareable`. The two variants read the same `assessment.json`; the difference is driven by the optional per-dimension `evidence_excerpts` you added in step 4 (see below):

- **personal** renders `evidence_excerpts` inline under each dimension (short real quotes, each with `source · date · locator`) behind a prominent `PRIVADO — NÃO compartilhar` banner. Its privacy gate is secrets-only (keys/tokens/JWT still fail closed); the subject's own project names may remain because they opted into their own local copy.
- **shareable** drops every excerpt and runs the strict privacy gate (secrets **plus** e-mail/URL/home-path). It must contain none of the excerpt text.

The renderer validates the schema before writing; fix any reported error and rerun. After rendering, for **each** file confirm it is non-empty, contains `<!doctype html>`, includes the headings `Cobertura por fonte`, `Perfil de maturidade`, `Forças observadas`, `Fricções e riscos`, `Exemplos de evidência`, `Recomendações priorizadas`, and `Metodologia e ressalvas`, and has no external `script`, `link`, or `img` references. Then confirm the **shareable** file contains none of the excerpt strings and no `PRIVADO` banner, and the **personal** file does.

Both reports must be readable without a server or internet connection, support light and dark system themes, escape all source text, contain no external assets, and remain useful when charts are ignored.

### 6. Render and validate the internal evidence dossier

Run:

```bash
python3 "$SKILL_DIR/scripts/render_evidence_dossier.py" \
  <output-dir>/workflow-evidence.json \
  <output-dir>/workflow-evidence.md
```

The Markdown must follow [references/evidence-dossier-contract.md](references/evidence-dossier-contract.md), contain the required machine-readable metadata block declaring private sharing, contain multiple sanitized workflow cases when coverage permits, and include questions for the reviewing agent. It must remain useful without the HTML and must reference evidence only through redacted local IDs.

Validate that the dossier contains no raw prompt blocks, home-directory usernames, e-mail addresses, credentials, private URLs, third-party names, or proprietary code. The renderer must fail closed when its structural or privacy checks fail.

After all artifacts pass validation, remove `history-scan.json`, `assessment.json`, `workflow-evidence.json`, and the per-source analysis JSON unless the user explicitly requested auditable intermediates. Keep `assessment-personal.html`, `assessment-shareable.html`, and `workflow-evidence.md`. When useful, also keep a separately sanitized aggregate inventory with no excerpts.

### 7. Handoff

Return:

- the absolute **shareable** HTML path (the safe-to-send report) and the absolute **personal** HTML path (labeled private — contains session excerpts, do not share);
- the absolute Markdown dossier path, labeled as private input for another agent rather than user reading;
- the assessed period and discovered sources;
- the overall workflow-maturity label and its confidence;
- the top two strengths;
- the top three improvements;
- material coverage or privacy limitations.

**Open the generated HTML reports for the person.** After validation and cleanup, open both HTML files in the default browser so they can read them immediately — do not make the person hunt for the path. Use the platform opener, detached so it never blocks, and open the shareable report first:

```bash
# Linux
setsid xdg-open "<output-dir>/assessment-shareable.html" >/dev/null 2>&1 < /dev/null
setsid xdg-open "<output-dir>/assessment-personal.html"  >/dev/null 2>&1 < /dev/null
# macOS: open "<file>"   ·   Windows: start "" "<file>"
```

Open only files that exist and passed validation. Skip this silently in a headless/no-display or non-interactive (cron) environment — still return the paths in that case. Never open the Markdown dossier (it is agent input, not user reading).

Do not dump the full analysis into chat. The HTML is the user-facing answer; the Markdown is the durable evidence layer for later agent checking.

## Failure handling

- Parser failure for one source: continue with others, mark that source `blocked`, and preserve the exact safe error.
- Unsupported schema version: report the file family and version signal without dumping content.
- Oversized histories: stream records; never load the entire corpus into memory.
- Cursor chat data unavailable: report detected storage and supported metadata only; do not scrape UI databases speculatively.
- Renderer validation failure: fix the assessment JSON or renderer and rerun; do not hand off an unvalidated HTML.
- Dossier validation or privacy failure: fix or remove the offending synthesized example and rerun; never bypass the fail-closed check or hand off a partial Markdown file.
- Insufficient qualitative samples: lower confidence and omit the score rather than inventing evidence.
