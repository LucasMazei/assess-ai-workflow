# Workflow Evidence Dossier

> Synthetic private example. It contains no local history, personal data, source code, credentials, or reusable locators.

## 1. Metadata and privacy envelope

```yaml
contract: workflow-evidence
contract_version: "1.0"
generated_at: "2026-08-09T00:00:00Z"
assessment_period:
  from: "2026-07-01T00:00:00Z"
  to: "2026-07-31T23:59:59Z"
subject_label: "Pessoa exemplo"
requested_role_lens: ["engineering"]
inferred_role_lens: []
sources_in_scope: ["opencode_local", "codex_local"]
source_analyses_used: ["analysis-opencode.json", "analysis-codex.json"]
raw_histories_reopened: false
raw_content_retained: false
sharing_default: private
sensitive_evidence_omitted: 0
locator_salt_scope: assessment_local
```

The evidence is synthetic and exists only to demonstrate the private dossier format.

## 2. Coverage and evidence map

| Source ID | Kind | Period | Eligible | Interpretable | Unit | Ratio | Dedup key | Retention caveat | Confidence ceiling |
|---|---|---|---:|---:|---|---:|---|---|---|
| codex_local | primary_history | 2026-07-01 to 2026-07-31 | 10 | 7 | root session | 0.70 | root session ID | Synthetic fixture | medium |
| opencode_local | primary_history | 2026-07-01 to 2026-07-31 | 12 | 8 | root session | 0.67 | root session ID | Synthetic fixture | medium |

- **Evidence units used:** 2 cases; 9 observations; 1 period.
- **Sampling rule:** Synthetic bounded sample for renderer documentation.
- **Known blind spots:** No real histories are represented.
- **Comparability (not_comparable):** The synthetic sources illustrate distinct retention profiles only.

## 3. Representative workflow cases

### WF-001 — Scoped implementation with validation

- **Case status:** complete
- **Primary role lens:** engineering
- **Period bucket:** 2026-07
- **Classification:** observed
- **Confidence:** medium
- **Sensitivity:** low
- **Dimensions:** framing, grounding, validation, handoff, safety

**Context and intent**

A synthetic task defines scope, confirms the local source of truth, implements a bounded change, and records validation before handoff.

**Workflow sequence**

1. `[observed]` Scope and acceptance criteria are established.
2. `[observed]` Local context is inspected before the change.
3. `[observed]` Validation is run before the result is reported.

**Tool and agent chain**

- Read-only inspection, bounded edit, targeted validation.

**Context management**

- Discovery and execution are treated as separate phases.

**Validation and feedback**

- The reported outcome is tied to a verification step.

**Outcome and handoff**

- The handoff states what was changed and how it was checked.

### WF-002 — Delegated research with a synthesis gap

- **Case status:** partial
- **Primary role lens:** engineering
- **Period bucket:** 2026-07
- **Classification:** observed
- **Confidence:** low
- **Sensitivity:** low
- **Dimensions:** routing, context, handoff

**Context and intent**

A synthetic task delegates an independent research step, but the expected synthesis format is not made explicit before execution.

**Workflow sequence**

1. `[observed]` The research subtask is separated from the main workflow.
2. `[observed]` A result is returned without a predeclared integration contract.
3. `[observed]` The final handoff requires clarification.

**Tool and agent chain**

- Delegated research followed by a main-agent synthesis attempt.

**Context management**

- The separate task limits context growth, but the return boundary is underspecified.

**Validation and feedback**

- A final review catches the missing synthesis detail.

**Outcome and handoff**

- The result is usable after clarification but not immediately reusable.

## 4. Recurring patterns

not_measurable — Synthetic fixture does not establish recurring behavior.

## 5. Counterpatterns and late failures

### CTR-001 — Delegation without an explicit synthesis contract

- **Classification:** observed
- **Dimensions:** routing, context
- **Frequency:** 1 of 2 synthetic eligible cases
- **Severity:** low
- **Confidence:** low
- **Behavior:** The expected integrated output is not stated before delegation.
- **Late-discovered signal:** The final handoff needs extra clarification.
- **Consequence observed:** Review effort increases.
- **Protective behavior present:** A final validation checkpoint limits impact.
- **Alternative explanation:** The task may have been small enough for implicit coordination.

## 6. Tool, agent, and model routing map

| Route ID | Root cases | Sequence | Why it fit | Integration observed | Outcome evidence | Caveat |
|---|---|---|---|---|---|---|
| RTE-01 | WF-001 | inspect to implement to validate | The task was bounded and verifiable. | The result was reconciled in a final handoff. | A validation step preceded reporting. | Synthetic example only. |

## 7. Role-lens synthesis

### engineering

- **Basis:** requested
- **Case refs:** WF-001
- **Relevant outcomes:** Bounded implementation and verification.
- **Relevant validation:** Targeted validation before handoff.
- **What is not applicable:** Business-impact attribution.
- **Confidence:** medium

## 8. Dimension evidence index

| Dimension | Status | Supporting cases/patterns | Counterevidence | Role lens | Coverage note | Max confidence |
|---|---|---|---|---|---|---|
| framing | evidence_available | WF-001 | None | engineering | Synthetic single-case illustration. | medium |
| grounding | evidence_available | WF-001 | None | engineering | Synthetic single-case illustration. | medium |
| routing | evidence_available | WF-001 | CTR-001 | engineering | Synthetic single-case illustration. | low |
| context | evidence_available | WF-001 | CTR-001 | engineering | Synthetic single-case illustration. | low |
| validation | evidence_available | WF-001 | None | engineering | Synthetic single-case illustration. | medium |
| handoff | evidence_available | WF-001 | None | engineering | Synthetic single-case illustration. | medium |
| reuse | not_measurable | None | None | engineering | No synthetic case establishes reusable assets. | insufficient |
| safety | evidence_available | WF-001 | None | engineering | Synthetic single-case illustration. | medium |

## 9. Not measurable, omitted, and conflicting evidence

### Not measurable

- Impacto causal no resultado de negócio.
- Recorrência de padrões ao longo de períodos independentes.

### Omitted for privacy

- `none: 0` — This fixture contains no source content.

### Conflicts and source limits

- The fixture intentionally models source limitations rather than real disagreement.

## 10. Reconciliation notes for the next agent

- **Promote with medium confidence:** Validation appears in the representative synthetic workflow. Refs: WF-001.
- **Do not compare:** The source counts are illustrative and must not support operational conclusions.
- **Recommendation candidate:** Add an explicit delegation contract. Reason: it makes synthesis reviewable. Success signal: each delegated task names the expected integrated output. Refs: CTR-001.

## 11. Validation checklist

- [x] All content is synthetic and sanitized.
- [x] No prompts, responses, code, personal data, paths, URLs, or credentials are included.
- [x] Observed, inferred, and not measurable claims remain distinct.
- [x] The dossier is private even though this sample contains no sensitive content.
