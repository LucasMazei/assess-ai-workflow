#!/usr/bin/env python3
"""Render a sanitized workflow-evidence JSON dossier as deterministic Markdown."""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


ROLE_LENSES = ["engineering", "product_design", "leadership_operations", "research_content", "mixed", "unknown"]
DIMENSIONS = ["framing", "grounding", "routing", "context", "validation", "handoff", "reuse", "safety"]
CLASSIFICATIONS = {"observed", "inferred", "not_measurable"}
CONFIDENCES = {"high", "medium", "low", "insufficient"}


class ValidationError(ValueError):
    pass


def fail(path: str, message: str) -> None:
    raise ValidationError(f"{path}: {message}")


def obj(value: Any, path: str, required: set[str], allowed: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(path, "expected object")
    missing = required - value.keys()
    extra = value.keys() - allowed
    if missing:
        fail(path, "missing required field(s): " + ", ".join(sorted(missing)))
    if extra:
        fail(path, f"unexpected field(s): {len(extra)}")
    return value


def arr(value: Any, path: str, item: Callable[[Any, str], None] | None = None, *, unique: bool = False) -> list[Any]:
    if not isinstance(value, list):
        fail(path, "expected array")
    if unique and len({json.dumps(x, sort_keys=True, ensure_ascii=False) for x in value}) != len(value):
        fail(path, "array items must be unique")
    if item:
        for i, member in enumerate(value):
            item(member, f"{path}[{i}]")
    return value


def string(value: Any, path: str, *, nonempty: bool = False, pattern: str | None = None) -> None:
    if not isinstance(value, str):
        fail(path, "expected string")
    if nonempty and not value:
        fail(path, "must not be empty")
    if pattern and not re.fullmatch(pattern, value):
        fail(path, "invalid format")


def integer(value: Any, path: str, *, minimum: int = 0) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        fail(path, f"expected integer >= {minimum}")


def enum(value: Any, path: str, values: set[str] | list[str]) -> None:
    if value not in values:
        fail(path, "invalid enum value")


def nullable(value: Any, path: str, validator: Callable[[Any, str], None]) -> None:
    if value is not None:
        validator(value, path)


def iso_datetime(value: Any, path: str) -> None:
    string(value, path)
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        fail(path, "invalid ISO 8601 date-time")


def period(value: Any, path: str) -> None:
    d = obj(value, path, {"from", "to"}, {"from", "to"})
    iso_datetime(d["from"], path + ".from")
    iso_datetime(d["to"], path + ".to")


def strings(value: Any, path: str, *, unique: bool = False) -> list[str]:
    return arr(value, path, string, unique=unique)


def enums(value: Any, path: str, values: set[str] | list[str], *, unique: bool = False) -> None:
    arr(value, path, lambda x, p: enum(x, p, values), unique=unique)


LOCATOR_RE = r"[a-z0-9_]+/(?:sess_h|artifact_h):[a-f0-9]{8,12}…/.*"
ROOT_LOCATOR_RE = r"(?:[a-z0-9_]+/sess_h:[a-f0-9]{8,12}…/root|locator_omitted: privacy)"
SAFE_LOCATOR_RE = r"(?:[a-z0-9_]+/sess_h:[a-f0-9]{8,12}…/[a-z0-9_-]+|locator_omitted: privacy)"


def locator(value: Any, path: str) -> None:
    keys = {"ref", "source_id", "locator", "event_type", "timestamp_bucket", "sanitization"}
    d = obj(value, path, keys, keys)
    string(d["ref"], path + ".ref", pattern=r"obs-[0-9]+")
    string(d["source_id"], path + ".source_id")
    string(d["locator"], path + ".locator", pattern=LOCATOR_RE)
    for key in ("event_type", "timestamp_bucket", "sanitization"):
        string(d[key], path + "." + key)


def sequence_event(value: Any, path: str) -> None:
    d = obj(value, path, {"classification", "text", "locators"}, {"classification", "text", "locators"})
    enum(d["classification"], path + ".classification", {"observed", "inferred"})
    string(d["text"], path + ".text")
    arr(d["locators"], path + ".locators", locator)


def workflow_case(value: Any, path: str) -> None:
    keys = {"id", "label", "case_status", "primary_role_lens", "secondary_role_lenses", "period_bucket", "root_task_locator", "classification", "confidence", "sensitivity", "dimensions", "context_and_intent", "workflow_sequence", "tool_and_agent_chain", "context_management", "validation_and_feedback", "outcome_and_handoff", "supporting_refs", "contradicting_refs", "interpretation", "alternative_explanation", "locator_ledger"}
    d = obj(value, path, keys, keys)
    string(d["id"], path + ".id", pattern=r"WF-[0-9]{3}")
    string(d["label"], path + ".label")
    enum(d["case_status"], path + ".case_status", {"complete", "partial", "blocked", "outcome_unknown"})
    enum(d["primary_role_lens"], path + ".primary_role_lens", ROLE_LENSES)
    enums(d["secondary_role_lenses"], path + ".secondary_role_lenses", ROLE_LENSES, unique=True)
    string(d["period_bucket"], path + ".period_bucket")
    string(d["root_task_locator"], path + ".root_task_locator", pattern=ROOT_LOCATOR_RE)
    enum(d["classification"], path + ".classification", CLASSIFICATIONS)
    enum(d["confidence"], path + ".confidence", CONFIDENCES)
    enum(d["sensitivity"], path + ".sensitivity", {"low", "moderate", "high"})
    enums(d["dimensions"], path + ".dimensions", DIMENSIONS, unique=True)
    string(d["context_and_intent"], path + ".context_and_intent")
    arr(d["workflow_sequence"], path + ".workflow_sequence", sequence_event)
    for key in ("tool_and_agent_chain", "context_management", "validation_and_feedback", "outcome_and_handoff", "supporting_refs", "contradicting_refs"):
        strings(d[key], path + "." + key)
    string(d["interpretation"], path + ".interpretation")
    nullable(d["alternative_explanation"], path + ".alternative_explanation", string)
    arr(d["locator_ledger"], path + ".locator_ledger", locator)
    if d["classification"] == "inferred":
        if len(set(d["supporting_refs"])) < 2 or d["alternative_explanation"] is None:
            fail(path, "inferred case requires 2 supporting refs and an alternative explanation")
        if d["confidence"] == "high":
            fail(path, "inferred case may not use high confidence")


def pattern_item(value: Any, path: str) -> None:
    keys = {"id", "label", "classification", "dimensions", "role_lenses", "case_refs", "source_spread", "period_spread", "support_count", "eligible_count", "contradictions", "confidence", "claim", "reasoning", "alternative_explanation", "boundary_conditions", "assessment_use"}
    d = obj(value, path, keys, keys)
    string(d["id"], path + ".id", pattern=r"PAT-[0-9]{3}")
    string(d["label"], path + ".label")
    enum(d["classification"], path + ".classification", CLASSIFICATIONS)
    enums(d["dimensions"], path + ".dimensions", DIMENSIONS)
    enums(d["role_lenses"], path + ".role_lenses", ROLE_LENSES)
    strings(d["case_refs"], path + ".case_refs")
    strings(d["source_spread"], path + ".source_spread")
    strings(d["period_spread"], path + ".period_spread")
    integer(d["support_count"], path + ".support_count")
    integer(d["eligible_count"], path + ".eligible_count")
    strings(d["contradictions"], path + ".contradictions")
    enum(d["confidence"], path + ".confidence", CONFIDENCES)
    string(d["claim"], path + ".claim")
    nullable(d["reasoning"], path + ".reasoning", string)
    nullable(d["alternative_explanation"], path + ".alternative_explanation", string)
    string(d["boundary_conditions"], path + ".boundary_conditions")
    string(d["assessment_use"], path + ".assessment_use")
    if d["support_count"] > d["eligible_count"]:
        fail(path, "support_count may not exceed eligible_count")
    if d["classification"] == "inferred":
        if d["reasoning"] is None or d["alternative_explanation"] is None or len(set(d["case_refs"])) < 2:
            fail(path, "inferred pattern requires reasoning, alternative explanation, and 2 case refs")
        if d["confidence"] == "high":
            fail(path, "inferred pattern may not use high confidence")
    if d["classification"] != "not_measurable" and (
        d["support_count"] < 3 or len(set(d["case_refs"])) < 2 or len(set(d["period_spread"])) < 2
    ):
        fail(path, "recurring pattern requires 3 supports, 2 cases, and 2 periods")


def counterpattern(value: Any, path: str) -> None:
    keys = {"id", "label", "classification", "dimensions", "case_refs", "frequency_count", "eligible_count", "severity", "confidence", "behavior", "late_discovered_signal", "consequence_observed", "protective_behavior_present", "alternative_explanation", "safe_locators"}
    d = obj(value, path, keys, keys)
    string(d["id"], path + ".id", pattern=r"CTR-[0-9]{3}")
    string(d["label"], path + ".label")
    enum(d["classification"], path + ".classification", CLASSIFICATIONS)
    enums(d["dimensions"], path + ".dimensions", DIMENSIONS)
    strings(d["case_refs"], path + ".case_refs")
    integer(d["frequency_count"], path + ".frequency_count")
    integer(d["eligible_count"], path + ".eligible_count")
    enum(d["severity"], path + ".severity", {"low", "moderate", "high"})
    enum(d["confidence"], path + ".confidence", CONFIDENCES)
    string(d["behavior"], path + ".behavior")
    nullable(d["late_discovered_signal"], path + ".late_discovered_signal", string)
    string(d["consequence_observed"], path + ".consequence_observed")
    nullable(d["protective_behavior_present"], path + ".protective_behavior_present", string)
    nullable(d["alternative_explanation"], path + ".alternative_explanation", string)
    arr(d["safe_locators"], path + ".safe_locators", lambda x, p: string(x, p, pattern=SAFE_LOCATOR_RE))
    if d["frequency_count"] > d["eligible_count"]:
        fail(path, "frequency_count may not exceed eligible_count")


def validate(data: Any) -> None:
    root_keys = {"contract", "contract_version", "metadata", "privacy_envelope", "coverage", "cases", "patterns", "counterpatterns", "routes", "role_lenses", "dimension_index", "limits", "reconciliation", "validation"}
    d = obj(data, "$", root_keys, root_keys)
    if d["contract"] != "workflow-evidence" or d["contract_version"] != "1.0":
        fail("$", "unsupported contract or version")

    mk = {"generated_at", "assessment_period", "subject_label", "requested_role_lens", "inferred_role_lens", "sources_in_scope", "source_analyses_used", "raw_histories_reopened", "raw_content_retained", "sharing_default", "sensitive_evidence_omitted", "locator_salt_scope"}
    m = obj(d["metadata"], "$.metadata", mk, mk)
    iso_datetime(m["generated_at"], "$.metadata.generated_at"); period(m["assessment_period"], "$.metadata.assessment_period")
    string(m["subject_label"], "$.metadata.subject_label", nonempty=True)
    enums(m["requested_role_lens"], "$.metadata.requested_role_lens", ROLE_LENSES, unique=True); enums(m["inferred_role_lens"], "$.metadata.inferred_role_lens", ROLE_LENSES, unique=True)
    arr(m["sources_in_scope"], "$.metadata.sources_in_scope", lambda x, p: string(x, p, pattern=r"[a-z0-9_]+"), unique=True)
    arr(m["source_analyses_used"], "$.metadata.source_analyses_used", lambda x, p: string(x, p, pattern=r"analysis-[a-z0-9_-]+\.json"), unique=True)
    for key, expected in (("raw_histories_reopened", False), ("raw_content_retained", False), ("sharing_default", "private"), ("locator_salt_scope", "assessment_local")):
        if m[key] != expected: fail("$.metadata." + key, "invalid constant")
    integer(m["sensitive_evidence_omitted"], "$.metadata.sensitive_evidence_omitted")
    string(d["privacy_envelope"], "$.privacy_envelope", nonempty=True)

    ck = {"sources", "evidence_units_used", "sampling_rule", "known_blind_spots", "comparability"}; c = obj(d["coverage"], "$.coverage", ck, ck)
    source_keys = {"source_id", "kind", "period", "eligible", "interpretable", "unit", "ratio", "dedup_key", "retention_caveat", "confidence_ceiling"}
    def source(x: Any, p: str) -> None:
        s = obj(x, p, source_keys, source_keys); string(s["source_id"], p+".source_id"); enum(s["kind"], p+".kind", {"primary_history", "aggregate_cache", "config", "artifact", "model_subset"}); period(s["period"], p+".period")
        nullable(s["eligible"], p+".eligible", integer); nullable(s["interpretable"], p+".interpretable", integer)
        string(s["unit"], p+".unit")
        if s["ratio"] is not None and (isinstance(s["ratio"], bool) or not isinstance(s["ratio"], (int, float)) or not 0 <= s["ratio"] <= 1): fail(p+".ratio", "expected number from 0 to 1 or null")
        if s["eligible"] is not None and s["interpretable"] is not None:
            if s["interpretable"] > s["eligible"]: fail(p+".interpretable", "may not exceed eligible")
            expected = None if s["eligible"] == 0 else s["interpretable"] / s["eligible"]
            if expected is not None and (s["ratio"] is None or abs(float(s["ratio"]) - expected) > 0.011): fail(p+".ratio", "must equal interpretable / eligible")
        string(s["dedup_key"], p+".dedup_key"); nullable(s["retention_caveat"], p+".retention_caveat", string); enum(s["confidence_ceiling"], p+".confidence_ceiling", CONFIDENCES | {"inherited"})
    arr(c["sources"], "$.coverage.sources", source)
    eu = obj(c["evidence_units_used"], "$.coverage.evidence_units_used", {"cases", "observations", "period_buckets"}, {"cases", "observations", "period_buckets"})
    for k in eu: integer(eu[k], "$.coverage.evidence_units_used."+k)
    if eu["cases"] != len(d["cases"]): fail("$.coverage.evidence_units_used.cases", "must equal the number of cases")
    string(c["sampling_rule"], "$.coverage.sampling_rule", nonempty=True); strings(c["known_blind_spots"], "$.coverage.known_blind_spots")
    def comparison(x: Any, p: str) -> None:
        q=obj(x,p,{"source_ids","status","reason"},{"source_ids","status","reason"}); a=arr(q["source_ids"],p+".source_ids",string)
        if len(a)<2: fail(p+".source_ids","expected at least 2 items")
        enum(q["status"],p+".status",{"convergent","conflicting","not_comparable"}); string(q["reason"],p+".reason")
    arr(c["comparability"], "$.coverage.comparability", comparison)
    arr(d["cases"], "$.cases", workflow_case); arr(d["patterns"], "$.patterns", pattern_item); arr(d["counterpatterns"], "$.counterpatterns", counterpattern)

    def route(x: Any,p: str)->None:
        keys={"id","root_cases","sequence","why_it_fit","integration_observed","outcome_evidence","caveat"}; q=obj(x,p,keys,keys); string(q["id"],p+".id",pattern=r"RTE-[0-9]{2}")
        strings(q["root_cases"],p+".root_cases"); strings(q["sequence"],p+".sequence"); string(q["why_it_fit"],p+".why_it_fit"); string(q["integration_observed"],p+".integration_observed"); string(q["outcome_evidence"],p+".outcome_evidence"); nullable(q["caveat"],p+".caveat",string)
    arr(d["routes"], "$.routes", route)
    def role(x: Any,p: str)->None:
        keys={"lens","basis","case_refs","relevant_outcomes","relevant_validation","not_applicable","confidence"}; q=obj(x,p,keys,keys); enum(q["lens"],p+".lens",ROLE_LENSES); enum(q["basis"],p+".basis",{"requested","observed","inferred"})
        for k in ("case_refs","relevant_outcomes","relevant_validation","not_applicable"): strings(q[k],p+"."+k)
        enum(q["confidence"],p+".confidence",CONFIDENCES)
        if q["basis"] == "inferred" and q["confidence"] == "high": fail(p+".confidence", "inferred role lens may not use high confidence")
    arr(d["role_lenses"], "$.role_lenses", role)
    def dim(x: Any,p: str)->None:
        keys={"dimension","status","supporting_refs","counterevidence_refs","role_lenses","coverage_note","max_confidence"}; q=obj(x,p,keys,keys); enum(q["dimension"],p+".dimension",DIMENSIONS); enum(q["status"],p+".status",{"evidence_available","not_measurable","not_applicable"})
        strings(q["supporting_refs"],p+".supporting_refs"); strings(q["counterevidence_refs"],p+".counterevidence_refs"); enums(q["role_lenses"],p+".role_lenses",ROLE_LENSES); string(q["coverage_note"],p+".coverage_note"); enum(q["max_confidence"],p+".max_confidence",CONFIDENCES)
    dims=arr(d["dimension_index"], "$.dimension_index", dim)
    if len(dims)!=8 or {x["dimension"] for x in dims} != set(DIMENSIONS): fail("$.dimension_index","must contain each of the 8 dimensions exactly once")
    lk={"not_measurable","omitted_for_privacy","conflicts_and_source_limits"}; lim=obj(d["limits"],"$.limits",lk,lk); strings(lim["not_measurable"],"$.limits.not_measurable"); strings(lim["conflicts_and_source_limits"],"$.limits.conflicts_and_source_limits")
    def omission(x:Any,p:str)->None:
        q=obj(x,p,{"class","count","effect"},{"class","count","effect"}); string(q["class"],p+".class"); integer(q["count"],p+".count"); string(q["effect"],p+".effect")
    arr(lim["omitted_for_privacy"],"$.limits.omitted_for_privacy",omission)
    rk={"promote","reject","do_not_compare","recommendation_candidates","deduplication_confirmed"}; rec=obj(d["reconciliation"],"$.reconciliation",rk,rk)
    def recitem(x:Any,p:str)->None:
        q=obj(x,p,{"claim","refs","confidence","reason"},{"claim","refs","confidence","reason"}); string(q["claim"],p+".claim"); strings(q["refs"],p+".refs"); enum(q["confidence"],p+".confidence",CONFIDENCES); string(q["reason"],p+".reason")
    arr(rec["promote"],"$.reconciliation.promote",recitem); arr(rec["reject"],"$.reconciliation.reject",recitem); strings(rec["do_not_compare"],"$.reconciliation.do_not_compare")
    def recommendation(x:Any,p:str)->None:
        q=obj(x,p,{"action","why","success_signal","refs"},{"action","why","success_signal","refs"}); string(q["action"],p+".action"); string(q["why"],p+".why"); string(q["success_signal"],p+".success_signal"); strings(q["refs"],p+".refs")
    arr(rec["recommendation_candidates"],"$.reconciliation.recommendation_candidates",recommendation)
    if rec["deduplication_confirmed"] is not True: fail("$.reconciliation.deduplication_confirmed","invalid constant")
    def check(x:Any,p:str)->None:
        q=obj(x,p,{"id","status","note"},{"id","status","note"}); string(q["id"],p+".id"); enum(q["status"],p+".status",{"pass","fail","not_applicable"}); nullable(q["note"],p+".note",string)
    checks = arr(d["validation"],"$.validation",check)
    if any(item["status"] == "fail" for item in checks): fail("$.validation", "contains a failed checklist item")
    validate_ids_and_refs(d)
    validate_privacy(d)


def validate_ids_and_refs(d: dict[str, Any]) -> None:
    groups = {k: {x["id"] for x in d[k]} for k in ("cases", "patterns", "counterpatterns", "routes")}
    for key in groups:
        if len(groups[key]) != len(d[key]): fail("$."+key, "duplicate IDs")
    sources = {x["source_id"] for x in d["coverage"]["sources"]}
    if not set(d["metadata"]["sources_in_scope"]).issuperset(sources): fail("$.coverage.sources", "source_id not in metadata.sources_in_scope")
    obs: set[str] = set()
    for i,c in enumerate(d["cases"]):
        for loc in c["locator_ledger"]:
            if loc["source_id"] not in sources: fail(f"$.cases[{i}].locator_ledger", "unknown source_id")
            obs.add(loc["ref"])
        for j,event in enumerate(c["workflow_sequence"]):
            for loc in event["locators"]:
                if loc["source_id"] not in sources: fail(f"$.cases[{i}].workflow_sequence[{j}]", "unknown source_id")
    all_ids = set().union(*groups.values(), obs)
    def refs(values: list[str], path: str, allowed: set[str]) -> None:
        for ref in values:
            if ref not in allowed: fail(path, "unknown reference")
    for i,x in enumerate(d["cases"]): refs(x["supporting_refs"]+x["contradicting_refs"],f"$.cases[{i}] references",obs)
    for name in ("patterns","counterpatterns"):
        for i,x in enumerate(d[name]): refs(x["case_refs"],f"$.{name}[{i}].case_refs",groups["cases"])
    for i,x in enumerate(d["routes"]): refs(x["root_cases"],f"$.routes[{i}].root_cases",groups["cases"])
    for i,x in enumerate(d["role_lenses"]): refs(x["case_refs"],f"$.role_lenses[{i}].case_refs",groups["cases"])
    for i,x in enumerate(d["dimension_index"]): refs(x["supporting_refs"]+x["counterevidence_refs"],f"$.dimension_index[{i}] references",all_ids)
    for bucket in ("promote","reject"):
        for i,x in enumerate(d["reconciliation"][bucket]): refs(x["refs"],f"$.reconciliation.{bucket}[{i}].refs",all_ids)
    for i,x in enumerate(d["reconciliation"]["recommendation_candidates"]): refs(x["refs"],f"$.reconciliation.recommendation_candidates[{i}].refs",all_ids)


PRIVACY_PATTERNS = [
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----", re.I)),
    ("email", re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("personal_path", re.compile(r"/Users/[^/\s]+(?:/|\b)")),
    ("url", re.compile(r"https?://", re.I)),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("github_token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")),
    ("generic_secret", re.compile(r"(?i)\b(?:api[_-]?key|secret|password|passwd|token|authorization|cookie)\s*[:=]\s*[\"']?[A-Za-z0-9_./+\-=]{8,}")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
]


def validate_privacy(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for k,v in value.items(): validate_privacy(v, f"{path}.{k}")
    elif isinstance(value, list):
        for i,v in enumerate(value): validate_privacy(v, f"{path}[{i}]")
    elif isinstance(value, str):
        for category, rx in PRIVACY_PATTERNS:
            if rx.search(value): fail(path, f"privacy violation ({category})")


def esc(value: Any) -> str:
    if value is None: return "—"
    if isinstance(value, bool): return "true" if value else "false"
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\\", "\\\\")
    for char in "`*_{}[]<>#+-.!|": text = text.replace(char, "\\" + char)
    return text.replace("\n", " ")


def code(value: Any) -> str:
    if value is None: return "—"
    text = str(value).replace("\r", " ").replace("\n", " ").replace("|", "\\|")
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    fence = "`" * (longest + 1)
    padding = " " if text.startswith("`") or text.endswith("`") else ""
    return fence + padding + text + padding + fence


def list_text(values: list[Any], *, refs: bool = False, join: str = ", ") -> str:
    if not values: return "Nenhum observado"
    vals = sorted(set(values)) if refs else values
    return join.join(esc(x) for x in vals)


def bullets(lines: list[str], values: list[Any]) -> None:
    if not values: lines.append("- Nenhum observado")
    else: lines.extend("- " + esc(x) for x in values)


def id_num(item: dict[str, Any]) -> int:
    return int(item["id"].split("-")[1])


def render(data: dict[str, Any]) -> str:
    m=data["metadata"]; c=data["coverage"]; lines=["# Workflow Evidence Dossier", "", "## 1. Metadata and privacy envelope", "", "```yaml"]
    yaml_string=lambda value: json.dumps(value,ensure_ascii=False)
    lines += [f"contract: {data['contract']}", f'contract_version: "{data["contract_version"]}"', f'generated_at: "{m["generated_at"]}"', "assessment_period:", f'  from: "{m["assessment_period"]["from"]}"', f'  to: "{m["assessment_period"]["to"]}"', f'subject_label: {yaml_string(m["subject_label"])}']
    for k in ("requested_role_lens","inferred_role_lens","sources_in_scope","source_analyses_used"):
        lines.append(f"{k}: [" + ", ".join(yaml_string(x) for x in m[k]) + "]")
    for k in ("raw_histories_reopened","raw_content_retained","sensitive_evidence_omitted"): lines.append(f"{k}: {esc(m[k])}")
    for k in ("sharing_default","locator_salt_scope"): lines.append(f"{k}: {m[k]}")
    lines += ["```", "", "**Privacy envelope**", "", esc(data["privacy_envelope"]), "", "## 2. Coverage and evidence map", "", "| Source ID | Kind | Period | Eligible | Interpretable | Unit | Ratio | Dedup key | Retention caveat | Confidence ceiling |", "|---|---|---|---:|---:|---|---:|---|---|---|"]
    for s in sorted(c["sources"],key=lambda x:x["source_id"]):
        ratio="—" if s["ratio"] is None else f"{s['ratio']:.2f}"
        p=f'{s["period"]["from"]} – {s["period"]["to"]}'
        vals=[s["source_id"],s["kind"],p,s["eligible"],s["interpretable"],s["unit"],ratio,s["dedup_key"],s["retention_caveat"],s["confidence_ceiling"]]
        lines.append("| " + " | ".join(esc(v) for v in vals) + " |")
    eu=c["evidence_units_used"]; lines += ["",f"- **Evidence units used:** {eu['cases']} casos; {eu['observations']} observações; {eu['period_buckets']} períodos.",f"- **Sampling rule:** {esc(c['sampling_rule'])}",f"- **Known blind spots:** {list_text(c['known_blind_spots'])}"]
    if c["comparability"]:
        for x in c["comparability"]: lines.append(f"- **Comparability ({esc(x['status'])}) — {list_text(x['source_ids'],refs=True)}:** {esc(x['reason'])}")
    else: lines.append("- **Comparability:** Nenhum observado")
    lines += ["", "## 3. Representative workflow cases"]
    if not data["cases"]: lines += ["", "not\\_measurable — Nenhum observado"]
    for x in sorted(data["cases"],key=id_num): render_case(lines,x)
    lines += ["", "## 4. Recurring patterns"]
    if not data["patterns"]: lines += ["", "not\\_measurable — Nenhum observado"]
    for x in sorted(data["patterns"],key=id_num):
        lines += ["",f"### {x['id']} — {esc(x['label'])}","",f"- **Classification:** {x['classification']}",f"- **Dimensions:** {list_text(x['dimensions'])}",f"- **Role lenses:** {list_text(x['role_lenses'])}",f"- **Case refs:** {list_text(x['case_refs'],refs=True)}",f"- **Source spread:** {list_text(x['source_spread'],refs=True)}",f"- **Period spread:** {list_text(x['period_spread'],refs=True)}",f"- **Support:** {x['support_count']} of {x['eligible_count']} eligible cases",f"- **Contradictions:** {list_text(x['contradictions'],refs=True)}",f"- **Confidence:** {x['confidence']}",f"- **Claim:** {esc(x['claim'])}",f"- **Reasoning:** {esc(x['reasoning'])}",f"- **Alternative explanation:** {esc(x['alternative_explanation'])}",f"- **Boundary conditions:** {esc(x['boundary_conditions'])}",f"- **Assessment use:** {esc(x['assessment_use'])}"]
    lines += ["", "## 5. Counterpatterns and late failures"]
    if not data["counterpatterns"]: lines += ["", "not\\_measurable — Nenhum observado"]
    for x in sorted(data["counterpatterns"],key=id_num):
        locs="Nenhum observado" if not x["safe_locators"] else ", ".join(code(v) for v in sorted(set(x["safe_locators"])))
        lines += ["",f"### {x['id']} — {esc(x['label'])}","",f"- **Classification:** {x['classification']}",f"- **Dimensions:** {list_text(x['dimensions'])}",f"- **Case refs:** {list_text(x['case_refs'],refs=True)}",f"- **Frequency:** {x['frequency_count']} of {x['eligible_count']} eligible cases",f"- **Severity:** {x['severity']}",f"- **Confidence:** {x['confidence']}",f"- **Behavior:** {esc(x['behavior'])}",f"- **Late-discovered signal:** {esc(x['late_discovered_signal'])}",f"- **Consequence observed:** {esc(x['consequence_observed'])}",f"- **Protective behavior present:** {esc(x['protective_behavior_present'])}",f"- **Alternative explanation:** {esc(x['alternative_explanation'])}",f"- **Safe locators:** {locs}"]
    render_routes_roles_dimensions_limits_reconciliation_validation(lines,data)
    return "\n".join(lines).rstrip("\n") + "\n"


def render_case(lines:list[str],x:dict[str,Any])->None:
    lines += ["",f"### {x['id']} — {esc(x['label'])}","",f"- **Case status:** {x['case_status']}",f"- **Primary role lens:** {x['primary_role_lens']}",f"- **Secondary role lenses:** {list_text(x['secondary_role_lenses'])}",f"- **Period bucket:** {esc(x['period_bucket'])}",f"- **Root task locator:** {code(x['root_task_locator'])}",f"- **Classification:** {x['classification']}",f"- **Confidence:** {x['confidence']}",f"- **Sensitivity:** {x['sensitivity']}",f"- **Dimensions:** {list_text(x['dimensions'])}","","**Context and intent**","",esc(x["context_and_intent"]),"","**Workflow sequence**",""]
    if not x["workflow_sequence"]: lines.append("Nenhum observado")
    for i,e in enumerate(x["workflow_sequence"],1):
        locs="" if not e["locators"] else " (" + ", ".join(code(z["locator"]) for z in e["locators"]) + ")"
        lines.append(f"{i}. `[{e['classification']}]` {esc(e['text'])}{locs}")
    for title,key in (("Tool and agent chain","tool_and_agent_chain"),("Context management","context_management"),("Validation and feedback","validation_and_feedback"),("Outcome and handoff","outcome_and_handoff")):
        lines += ["",f"**{title}**",""]; bullets(lines,x[key])
    lines += ["","**Evidence and counterevidence**","",f"- **Suporta:** {list_text(x['supporting_refs'],refs=True)}",f"- **Contradiz:** {list_text(x['contradicting_refs'],refs=True)}",f"- **Interpretação:** {esc(x['interpretation'])}",f"- **Alternativa plausível:** {esc(x['alternative_explanation'])}","","**Safe locator ledger**",""]
    if not x["locator_ledger"]: lines.append("Nenhum observado")
    else:
        lines += ["| Ref | Source | Locator | Event type | Timestamp bucket | Sanitization |","|---|---|---|---|---|---|"]
        for z in sorted(x["locator_ledger"],key=lambda a:(a["ref"],a["source_id"],a["locator"])): lines.append("| "+" | ".join([esc(z["ref"]),esc(z["source_id"]),code(z["locator"]),esc(z["event_type"]),esc(z["timestamp_bucket"]),esc(z["sanitization"])])+" |")


def render_routes_roles_dimensions_limits_reconciliation_validation(lines:list[str],d:dict[str,Any])->None:
    lines += ["","## 6. Tool, agent, and model routing map","","| Route ID | Root cases | Sequence | Why it fit | Integration observed | Outcome evidence | Caveat |","|---|---|---|---|---|---|---|"]
    if not d["routes"]: lines.append("| Nenhum observado | Nenhum observado | Nenhum observado | Nenhum observado | Nenhum observado | Nenhum observado | — |")
    for x in sorted(d["routes"],key=id_num): lines.append("| "+" | ".join([esc(x["id"]),list_text(x["root_cases"],refs=True)," → ".join(esc(v) for v in x["sequence"]) if x["sequence"] else "Nenhum observado",esc(x["why_it_fit"]),esc(x["integration_observed"]),esc(x["outcome_evidence"]),esc(x["caveat"])])+" |")
    lines += ["","## 7. Role-lens synthesis"]
    if not d["role_lenses"]: lines += ["","not\\_measurable — Nenhum observado"]
    for x in sorted(d["role_lenses"],key=lambda a:ROLE_LENSES.index(a["lens"])):
        lines += ["",f"### {x['lens']}","",f"- **Basis:** {x['basis']}",f"- **Case refs:** {list_text(x['case_refs'],refs=True)}",f"- **Relevant outcomes:** {list_text(x['relevant_outcomes'])}",f"- **Relevant validation:** {list_text(x['relevant_validation'])}",f"- **What is not applicable:** {list_text(x['not_applicable'])}",f"- **Confidence:** {x['confidence']}"]
    lines += ["","## 8. Dimension evidence index","","| Dimension | Status | Supporting cases/patterns | Counterevidence | Role lens | Coverage note | Max confidence |","|---|---|---|---|---|---|---|"]
    bydim={x["dimension"]:x for x in d["dimension_index"]}
    for name in DIMENSIONS:
        x=bydim[name]; lines.append("| "+" | ".join([name,x["status"],list_text(x["supporting_refs"],refs=True,join="; "),list_text(x["counterevidence_refs"],refs=True,join="; "),list_text(x["role_lenses"]),esc(x["coverage_note"]),x["max_confidence"]])+" |")
    lim=d["limits"]; lines += ["","## 9. Not measurable, omitted, and conflicting evidence","","### Not measurable",""]; bullets(lines,lim["not_measurable"])
    lines += ["","### Omitted for privacy",""]
    if not lim["omitted_for_privacy"]: lines.append("- Nenhum observado")
    else:
        for x in lim["omitted_for_privacy"]: lines.append(f"- `{esc(x['class'])}: {x['count']}` — {esc(x['effect'])}")
    lines += ["","### Conflicts and source limits",""]; bullets(lines,lim["conflicts_and_source_limits"])
    rec=d["reconciliation"]; lines += ["","## 10. Reconciliation notes for the next agent",""]
    for title,key in (("Promote","promote"),("Reject","reject")):
        if not rec[key]: lines.append(f"- **{title}:** Nenhum observado")
        for x in rec[key]: lines.append(f"- **{title} with {x['confidence']} confidence:** {esc(x['claim'])} Refs: {list_text(x['refs'],refs=True)}. Razão: {esc(x['reason'])}")
    if not rec["do_not_compare"]: lines.append("- **Do not compare:** Nenhum observado")
    else:
        for x in rec["do_not_compare"]: lines.append(f"- **Do not compare:** {esc(x)}")
    if not rec["recommendation_candidates"]: lines.append("- **Recommendation candidate:** Nenhum observado")
    else:
        for x in rec["recommendation_candidates"]: lines.append(f"- **Recommendation candidate:** {esc(x['action'])} Razão: {esc(x['why'])} Sinal: {esc(x['success_signal'])} Refs: {list_text(x['refs'],refs=True)}.")
    lines.append(f"- **Deduplication confirmed:** {esc(rec['deduplication_confirmed'])}")
    lines += [
        "", "### Questions for the reviewing agent", "",
        "1. Quais casos sustentam ou contradizem cada conclusão apresentada no HTML?",
        "2. A recorrência cumpre os mínimos de tarefas, eventos, fontes e períodos?",
        "3. Quais afirmações são observadas, inferidas ou não mensuráveis?",
        "4. A validação observada é proporcional à lente e ao risco de cada fluxo?",
        "5. Subagentes, variantes de modelo, caches e continuações foram deduplicados corretamente?",
        "6. Quais recomendações têm risco comprovado e sinal de sucesso verificável?",
        "7. Há alguma conclusão do HTML sem suporte, em conflito ou forte demais para a cobertura disponível?",
    ]
    lines += ["","## 11. Validation checklist",""]
    if not d["validation"]: lines.append("- [ ] Nenhum observado")
    marks={"pass":"[x]","fail":"[ ]","not_applicable":"[n/a]"}
    for x in d["validation"]:
        suffix="" if x["note"] is None else " — "+esc(x["note"])
        lines.append(f"- {marks[x['status']]} {esc(x['id'])}{suffix}")


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(f"usage: {Path(argv[0]).name} INPUT_JSON OUTPUT_MD", file=sys.stderr); return 2
    input_path, output_path = Path(argv[1]), Path(argv[2])
    try:
        with input_path.open("r", encoding="utf-8") as fh: data=json.load(fh)
        validate(data); rendered=render(data)
        parent_existed = output_path.parent.exists()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if not parent_existed:
            output_path.parent.chmod(0o700)
        flags=os.O_WRONLY|os.O_CREAT|os.O_TRUNC
        fd=os.open(output_path,flags,0o600)
        try:
            os.fchmod(fd,0o600)
            with os.fdopen(fd,"w",encoding="utf-8",newline="\n") as fh: fh.write(rendered)
        except Exception:
            try: os.close(fd)
            except OSError: pass
            raise
    except ValidationError as exc:
        print(f"error: {exc}",file=sys.stderr); return 1
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON at line {exc.lineno}, column {exc.colno}",file=sys.stderr); return 1
    except OSError:
        print("error: input/output operation failed",file=sys.stderr); return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
