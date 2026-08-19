#!/usr/bin/env python3
"""Render a normalized AI-workflow assessment JSON as a self-contained HTML report."""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import sys
from pathlib import Path
from typing import Any


class SchemaError(ValueError):
    """Raised when the normalized assessment does not match the renderer contract."""


# Secret patterns: credentials/keys/tokens that must never leak, in any audience.
SECRETS_PATTERNS = (
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.I)),
    ("credential", re.compile(r"\b(?:(?:sk|ghp|gho|xox[abprs])-|github_pat_)[-A-Za-z0-9_]{12,}\b", re.I)),
    ("aws_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("bearer", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}", re.I)),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{4,}")),
)

# Strict patterns (shareable audience): secrets plus emails/paths/URLs.
PRIVACY_PATTERNS = SECRETS_PATTERNS + (
    ("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
    ("personal_path", re.compile(r"/Users/[^/\s]+(?:/|\b)")),
    ("external_url", re.compile(r"https?://", re.I)),
)


# Generic, non-sensitive explanations for each maturity dimension, keyed by the
# canonical dimension id. Rendered as a hover/focus tooltip in both audiences.
DIMENSION_TOOLTIPS = {
    "framing": "Framing e contrato de trabalho: você deixa claro objetivo, contexto, restrições, o que está fora de escopo, formato de saída e critério de \"pronto\" antes de executar ou delegar. Bom quando: tarefas ambíguas abrem com um contrato curto e explícito, não com improviso.",
    "grounding": "Grounding e proveniência: você aponta a fonte de verdade, separa fonte viva de memória e preserva de onde veio cada conclusão. Bom quando: decisões se apoiam em fonte primária verificada (código, estado real, doc), não em suposição.",
    "routing": "Decomposição e roteamento: você escolhe o fluxo, a ferramenta, a skill ou o agente conforme a incerteza, divide o trabalho em partes coerentes e integra os resultados. Bom quando: só o que é independente roda em paralelo e a síntese reconcilia as partes.",
    "context": "Gestão de contexto e fases: você evita contexto irrelevante, marca checkpoints, abre contexto novo quando o objetivo muda e separa descoberta, decisão, execução e review. Bom quando: cada fase tem seu foco e o contexto não vira uma sopa acumulada.",
    "validation": "Validação e feedback: você pede evidência proporcional ao risco — testes, inspeção do artefato, browser, fonte cruzada ou revisão humana. Bom quando: o quanto se valida cresce com o risco da tarefa, e a falha é pega antes do fechamento.",
    "handoff": "Artefatos, decisão e handoff: você produz saídas reutilizáveis, separa hipótese de decisão e fecha com feito / bloqueado / não verificado / próximo passo. Bom quando: quem recebe (você no futuro ou outra pessoa) sabe o estado exato sem readivinhar.",
    "reuse": "Reuso e melhoria do sistema: você transforma padrões recorrentes em templates, skills, documentação ou automações e revisa o processo a partir de falhas reais. Bom quando: a segunda vez de uma tarefa é mais barata que a primeira porque virou sistema.",
    "safety": "Segurança, privacidade e autoridade: você limita acesso e mutações, protege segredos e dados pessoais e pede aprovação para ações sensíveis. Bom quando: ações de alto impacto (produção, exclusão, envio) passam por um gate explícito antes de rodar.",
}


def scan_privacy(value: Any, patterns: tuple, path: str = "root", skip_keys: tuple = ()) -> None:
    """Fail closed without echoing sensitive source text in the error.

    Keys named in ``skip_keys`` are not descended into (used to exclude
    ``evidence_excerpts`` from the shareable strict scan, since they are dropped).
    """
    if isinstance(value, dict):
        for key, item in value.items():
            if key in skip_keys:
                continue
            scan_privacy(item, patterns, f"{path}.{key}", skip_keys)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            scan_privacy(item, patterns, f"{path}[{index}]", skip_keys)
    elif isinstance(value, str):
        for category, pattern in patterns:
            if pattern.search(value):
                raise SchemaError(f"{path} failed privacy validation ({category})")


def validate_privacy(value: Any, path: str = "root") -> None:
    """Strict full-input privacy scan (backward-compatible entry point)."""
    scan_privacy(value, PRIVACY_PATTERNS, path)


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def require_object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SchemaError(f"{path} must be an object")
    return value


def require_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise SchemaError(f"{path} must be an array")
    return value


def require_text(obj: dict[str, Any], key: str, path: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SchemaError(f"{path}.{key} must be a non-empty string")
    return value.strip()


def number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SchemaError(f"{path} must be a number")
    return float(value)


def alias(obj: dict[str, Any], canonical: str, *alternatives: str) -> None:
    """Copy the first present alias to canonical without discarding extra keys."""
    if canonical in obj:
        return
    for key in alternatives:
        if key in obj:
            obj[canonical] = obj[key]
            return


def normalize_canonical(value: dict[str, Any]) -> dict[str, Any]:
    """Convert the final assessment contract into the presentation contract."""
    required = (
        "contract_version", "generated_at", "subject", "scope", "dimensions",
        "overall", "strengths", "priorities", "not_measurable",
        "methodology_warnings", "privacy",
    )
    missing = [key for key in required if key not in value]
    if missing:
        raise SchemaError("canonical assessment is missing required field(s): " + ", ".join(missing))
    if value.get("contract_version") != "1.0":
        raise SchemaError("root.contract_version must be '1.0'")
    subject = require_object(value["subject"], "root.subject")
    display_name = require_text(subject, "display_name", "root.subject")
    scope = require_object(value["scope"], "root.scope")
    source_ids = require_list(scope.get("sources"), "root.scope.sources")
    dimensions_in = require_list(value["dimensions"], "root.dimensions")
    overall = require_object(value["overall"], "root.overall")
    strengths_in = require_list(value["strengths"], "root.strengths")
    priorities_in = require_list(value["priorities"], "root.priorities")
    not_measurable = require_list(value["not_measurable"], "root.not_measurable")
    warnings = require_list(value["methodology_warnings"], "root.methodology_warnings")
    privacy = require_object(value["privacy"], "root.privacy")

    coverage_label = scope.get("overall_coverage", "unknown")
    allowed_coverage = {"high", "medium", "low", "insufficient"}
    if coverage_label not in allowed_coverage:
        raise SchemaError("root.scope.overall_coverage must be high, medium, low, or insufficient")
    sources: list[dict[str, Any]] = []
    coverage_display = confidence_label(coverage_label)
    for i, source_id in enumerate(source_ids):
        if not isinstance(source_id, str) or not source_id.strip():
            raise SchemaError(f"root.scope.sources[{i}] must be a non-empty string")
        sources.append({
            "name": source_id,
            "status": "included",
            "coverage": None,
            "coverage_label": coverage_display,
            "note": f"Fonte incluída · cobertura global {coverage_display}",
        })
    excluded = require_list(scope.get("excluded_sources", []), "root.scope.excluded_sources")
    for i, excluded_source in enumerate(excluded):
        item = require_object(excluded_source, f"root.scope.excluded_sources[{i}]")
        sources.append({
            "name": require_text(item, "source", f"root.scope.excluded_sources[{i}]"),
            "status": "excluded",
            "coverage": None,
            "coverage_label": "excluded",
            "note": f"Excluída · {item.get('reason', 'motivo não informado')}",
        })
    if not sources:
        raise SchemaError("root.scope.sources must contain at least one source")

    dimensions: list[dict[str, Any]] = []
    legacy_frictions: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    for i, raw_dimension in enumerate(dimensions_in):
        item = require_object(raw_dimension, f"root.dimensions[{i}]")
        dim_id = require_text(item, "id", f"root.dimensions[{i}]")
        status = require_text(item, "status", f"root.dimensions[{i}]")
        if status not in {"scored", "not_measurable", "not_applicable"}:
            raise SchemaError(f"root.dimensions[{i}].status has an invalid value")
        confidence = require_text(item, "confidence", f"root.dimensions[{i}]")
        if confidence not in {"high", "medium", "low", "insufficient"}:
            raise SchemaError(f"root.dimensions[{i}].confidence has an invalid value")
        score = item.get("score")
        if status == "scored":
            score = number(score, f"root.dimensions[{i}].score")
            if not 1 <= score <= 5:
                raise SchemaError(f"root.dimensions[{i}].score must be between 1 and 5")
        elif score is not None:
            raise SchemaError(f"root.dimensions[{i}].score must be null when status is {status}")
        claims = require_list(item.get("claims", []), f"root.dimensions[{i}].claims")
        claim_texts: list[str] = []
        claim_refs: list[str] = []
        for j, raw_claim in enumerate(claims):
            claim = require_object(raw_claim, f"root.dimensions[{i}].claims[{j}]")
            classification = require_text(claim, "classification", f"root.dimensions[{i}].claims[{j}]")
            if classification not in {"observed", "inferred", "not_measurable"}:
                raise SchemaError(f"root.dimensions[{i}].claims[{j}].classification has an invalid value")
            claim_text = require_text(claim, "text", f"root.dimensions[{i}].claims[{j}]")
            refs = require_list(claim.get("evidence_refs", []), f"root.dimensions[{i}].claims[{j}].evidence_refs")
            if any(not isinstance(ref, str) or not ref.strip() for ref in refs):
                raise SchemaError(f"root.dimensions[{i}].claims[{j}].evidence_refs must contain strings")
            if classification == "inferred":
                if len(set(refs)) < 2:
                    raise SchemaError(f"root.dimensions[{i}].claims[{j}] inferred claims require at least 2 evidence refs")
                require_text(claim, "reasoning", f"root.dimensions[{i}].claims[{j}]")
                require_text(claim, "alternative_explanation", f"root.dimensions[{i}].claims[{j}]")
                if confidence == "high":
                    raise SchemaError(f"root.dimensions[{i}].claims[{j}] inferred claims may not use high confidence")
            claim_texts.append(claim_text)
            claim_refs.extend(str(ref) for ref in refs)
            evidence.append({
                "source": ", ".join(str(ref) for ref in refs) or dim_id,
                "excerpt": claim_text,
                "context": f"{dim_id} · {classification} · confiança {confidence}",
                "classification": classification,
            })
        limitations = require_list(item.get("limitations", []), f"root.dimensions[{i}].limitations")
        counterrefs = require_list(item.get("counterevidence_refs", []), f"root.dimensions[{i}].counterevidence_refs")
        excerpts: list[dict[str, Any]] = []
        raw_excerpts = item.get("evidence_excerpts")
        if raw_excerpts is not None:
            excerpts_list = require_list(raw_excerpts, f"root.dimensions[{i}].evidence_excerpts")
            for k, raw_excerpt in enumerate(excerpts_list):
                excerpt = require_object(raw_excerpt, f"root.dimensions[{i}].evidence_excerpts[{k}]")
                for field in ("text", "source", "date", "locator"):
                    if not isinstance(excerpt.get(field), str):
                        raise SchemaError(
                            f"root.dimensions[{i}].evidence_excerpts[{k}].{field} must be a string"
                        )
                excerpts.append({
                    "text": excerpt["text"],
                    "source": excerpt["source"],
                    "date": excerpt["date"],
                    "locator": excerpt["locator"],
                })
        summary = " ".join(claim_texts) or (
            "Não mensurável com a evidência disponível." if status == "not_measurable"
            else "Não aplicável ao recorte avaliado."
        )
        dimensions.append({
            "id": dim_id,
            "name": dim_id.replace("_", " ").title(),
            "score": score,
            "max_score": 5,
            "summary": summary,
            "status": status,
            "confidence": confidence,
            "claims": claims,
            "limitations": limitations,
            "recommendation": item.get("recommendation"),
            "evidence_excerpts": excerpts,
        })
        # Legacy fallback only: coverage limitations are NOT real frictions/risks.
        # They already render per-dimension under "Limitações"; keep them out of the
        # "Fricções e riscos" section unless no explicit frictions list is provided.
        friction_details = [str(x) for x in limitations]
        if counterrefs:
            friction_details.append("Contraevidências: " + ", ".join(str(x) for x in counterrefs))
        if status == "scored" and score is not None and score <= 3.5 and item.get("recommendation"):
            friction_details.append(str(item["recommendation"]))
        if friction_details:
            legacy_frictions.append({
                "title": dim_id.replace("_", " ").title(),
                "detail": " ".join(friction_details),
                "evidence_refs": claim_refs + [str(x) for x in counterrefs],
                "confidence": confidence,
            })

    # Prefer an explicit, curated risks list for "Fricções e riscos" so the section
    # shows real frictions, not coverage caveats. Fall back to the legacy derivation.
    explicit_frictions = value.get("frictions", value.get("risks"))
    if isinstance(explicit_frictions, list) and explicit_frictions:
        frictions: list[dict[str, Any]] = []
        for i, raw_friction in enumerate(explicit_frictions):
            item_f = require_object(raw_friction, f"root.frictions[{i}]")
            text_f = require_text(item_f, "text", f"root.frictions[{i}]")
            refs_f = require_list(item_f.get("evidence_refs", []), f"root.frictions[{i}].evidence_refs")
            if any(not isinstance(r, str) or not r.strip() for r in refs_f):
                raise SchemaError(f"root.frictions[{i}].evidence_refs must contain strings")
            title_f = item_f.get("title")
            if not (isinstance(title_f, str) and title_f.strip()):
                title_f = text_f.split(":", 1)[0][:60] if ":" in text_f[:60] else "Risco"
            conf_f = item_f.get("confidence", "")
            if conf_f and conf_f not in {"high", "medium", "low", "insufficient"}:
                raise SchemaError(f"root.frictions[{i}].confidence has an invalid value")
            frictions.append({
                "title": title_f.strip(),
                "detail": text_f,
                "evidence_refs": [str(r) for r in refs_f],
                "confidence": conf_f,
            })
    else:
        frictions = legacy_frictions

    score_status = require_text(overall, "score_status", "root.overall")
    if score_status not in {"published", "withheld_insufficient_dimensions"}:
        raise SchemaError("root.overall.score_status must be published or withheld_insufficient_dimensions")
    overall_score = overall.get("score")
    if overall_score is not None:
        overall_score = number(overall_score, "root.overall.score")
        if not 1 <= overall_score <= 5:
            raise SchemaError("root.overall.score must be between 1 and 5 or null")
    if score_status == "withheld_insufficient_dimensions" and overall_score is not None:
        raise SchemaError("root.overall.score must be null when score_status is withheld_insufficient_dimensions")
    measurable_dimensions = overall.get("measurable_dimensions")
    if isinstance(measurable_dimensions, bool) or not isinstance(measurable_dimensions, int):
        raise SchemaError("root.overall.measurable_dimensions must be an integer")
    actual_measurable = sum(1 for item in dimensions if item["status"] == "scored")
    if measurable_dimensions != actual_measurable:
        raise SchemaError(
            "root.overall.measurable_dimensions must equal the number of dimensions with status scored "
            f"({actual_measurable})"
        )
    if score_status == "published" and (overall_score is None or measurable_dimensions < 5):
        raise SchemaError("root.overall may be published only with a score and at least 5 measurable dimensions")
    if score_status == "published":
        expected_score = round(sum(float(item["score"]) for item in dimensions if item["score"] is not None) / measurable_dimensions, 1)
        if abs(float(overall_score) - expected_score) > 0.05:
            raise SchemaError(f"root.overall.score must equal the one-decimal mean of measurable dimensions ({expected_score})")
    if score_status == "withheld_insufficient_dimensions" and measurable_dimensions >= 5:
        raise SchemaError("root.overall must be published when at least 5 dimensions are measurable")
    overall_confidence = require_text(overall, "confidence", "root.overall")
    if overall_confidence not in {"high", "medium", "low", "insufficient"}:
        raise SchemaError("root.overall.confidence has an invalid value")
    summary_text = require_text(overall, "summary", "root.overall")

    if privacy.get("raw_prompts_in_report") is not False:
        raise SchemaError("root.privacy.raw_prompts_in_report must be false")
    if privacy.get("sharing_default") != "private":
        raise SchemaError("root.privacy.sharing_default must be private")

    strengths: list[dict[str, Any]] = []
    for i, raw_strength in enumerate(strengths_in):
        item = require_object(raw_strength, f"root.strengths[{i}]")
        refs = require_list(item.get("evidence_refs", []), f"root.strengths[{i}].evidence_refs")
        text = require_text(item, "text", f"root.strengths[{i}]")
        strengths.append({"title": text, "detail": text, "evidence_refs": refs})

    recommendations: list[dict[str, Any]] = []
    for i, raw_priority in enumerate(priorities_in):
        item = require_object(raw_priority, f"root.priorities[{i}]")
        action = require_text(item, "action", f"root.priorities[{i}]")
        recommendations.append({
            "priority": item.get("priority", i + 1),
            "title": action,
            "action": action,
            "why": item.get("why", ""),
            "effort": item.get("success_signal", ""),
            "evidence_refs": item.get("evidence_refs", []),
        })

    period = require_object(scope.get("period", {}), "root.scope.period")
    period_from, period_to = period.get("from", "?"), period.get("to", "?")
    caveats = [str(item) for item in warnings]
    caveats += [str(item) for item in scope.get("comparability_warnings", [])]
    caveats += [f"Não mensurável: {item}" for item in not_measurable]
    privacy_note = (
        f"Prompts brutos no relatório: {privacy.get('raw_prompts_in_report', 'unknown')}; "
        f"segredos detectados: {privacy.get('secrets_detected', 'unknown')}; "
        f"evidências sensíveis omitidas: {privacy.get('sensitive_evidence_omitted', 'unknown')}; "
        f"compartilhamento padrão: {privacy.get('sharing_default', 'unknown')}."
    )
    caveats.append(
        "Por privacidade e design, a análise interpreta apenas uma amostra redigida "
        "(dezenas de trechos curtos + poucos casos-raiz \"parent\"), não o conteúdo integral "
        "de todas as sessões. Por isso algumas dimensões dizem \"poucas tarefas interpretáveis\" "
        "mesmo havendo muitas sessões no disco; aumentar o teto de amostragem adensa a evidência."
    )
    caveats.append(privacy_note)
    return {
        "meta": {
            "title": f"Assessment de uso de IA — {display_name}",
            "generated_at": value["generated_at"],
            "subject": {"name": display_name, "role": ", ".join(subject.get("role_lens", []))},
        },
        "summary": {
            "headline": "Síntese do uso de IA",
            "narrative": summary_text,
            "overall_score": overall_score,
            "score_max": 5,
            "score_status": score_status,
            "confidence": overall_confidence,
            "maturity_label": f"Confiança {confidence_label(overall_confidence)}",
            "coverage_label": coverage_display,
            "period_from": period_from,
            "period_to": period_to,
            "measurable_dimensions": measurable_dimensions,
            "total_dimensions": len(dimensions),
            "sources_label": ", ".join(
                s.replace("_local", "").replace("_", " ").title() for s in source_ids
            ),
        },
        "sources": sources,
        "dimensions": dimensions,
        "strengths": strengths,
        "frictions": frictions,
        "evidence": evidence,
        "recommendations": recommendations,
        "methodology": {
            "scope": f"Fontes: {', '.join(source_ids)}. Período: {period_from} a {period_to}.",
            "rubric": "Notas de 1 a 5 por dimensão; confiança e limitações são preservadas.",
            "caveats": caveats,
        },
    }


def validate(data: Any) -> dict[str, Any]:
    root = dict(require_object(data, "root"))
    if "contract_version" in root:
        root = normalize_canonical(root)
    required = (
        "meta",
        "summary",
        "sources",
        "dimensions",
        "strengths",
        "frictions",
        "evidence",
        "recommendations",
        "methodology",
    )
    missing = [key for key in required if key not in root]
    if missing:
        raise SchemaError("root is missing required field(s): " + ", ".join(missing))

    meta = dict(require_object(root["meta"], "root.meta"))
    alias(meta, "generated_at", "generatedAt", "date")
    root["title"] = require_text(meta, "title", "root.meta")
    root["generated_at"] = require_text(meta, "generated_at", "root.meta")
    root["subject"] = meta.get("subject", root.get("subject", {}))
    summary = dict(require_object(root["summary"], "root.summary"))
    alias(summary, "headline", "title")
    alias(summary, "narrative", "description", "overview")
    alias(summary, "overall_score", "score")
    alias(summary, "score_max", "max_score")
    require_text(summary, "headline", "root.summary")
    require_text(summary, "narrative", "root.summary")
    raw_score = summary.get("overall_score")
    score = None if raw_score is None else number(raw_score, "root.summary.overall_score")
    score_max = number(summary.get("score_max", 5), "root.summary.score_max")
    if score_max <= 0 or (score is not None and not 0 <= score <= score_max):
        raise SchemaError("root.summary.overall_score must be between 0 and score_max")
    if score is None and summary.get("score_status") != "withheld_insufficient_dimensions":
        raise SchemaError("root.summary.overall_score may be null only when score_status is withheld_insufficient_dimensions")
    summary.setdefault("score_max", score_max)
    root["executive_summary"] = summary

    for section in ("sources", "dimensions", "strengths", "frictions", "evidence", "recommendations"):
        require_list(root[section], f"root.{section}")
    if not root["sources"]:
        raise SchemaError("root.sources must contain at least one source")
    if not root["dimensions"]:
        raise SchemaError("root.dimensions must contain at least one dimension")

    for i, item in enumerate(root["sources"]):
        obj = dict(require_object(item, f"root.sources[{i}]"))
        alias(obj, "name", "label", "source")
        alias(obj, "coverage", "coverage_pct", "coverage_percent")
        require_text(obj, "name", f"root.sources[{i}]")
        require_text(obj, "status", f"root.sources[{i}]")
        raw_coverage = obj.get("coverage", 0)
        coverage = None if raw_coverage is None else number(raw_coverage, f"root.sources[{i}].coverage")
        if coverage is not None and not 0 <= coverage <= 100:
            raise SchemaError(f"root.sources[{i}].coverage must be between 0 and 100")
        obj.setdefault("coverage", coverage)
        root["sources"][i] = obj

    for i, item in enumerate(root["dimensions"]):
        obj = dict(require_object(item, f"root.dimensions[{i}]"))
        alias(obj, "name", "label", "dimension")
        alias(obj, "max_score", "score_max")
        require_text(obj, "name", f"root.dimensions[{i}]")
        raw_dim_score = obj.get("score")
        dim_score = None if raw_dim_score is None else number(raw_dim_score, f"root.dimensions[{i}].score")
        dim_max = number(obj.get("max_score", 5), f"root.dimensions[{i}].max_score")
        if dim_max <= 0 or (dim_score is not None and not 0 <= dim_score <= dim_max):
            raise SchemaError(f"root.dimensions[{i}].score must be between 0 and max_score")
        if dim_score is None and obj.get("status") not in {"not_measurable", "not_applicable"}:
            raise SchemaError(f"root.dimensions[{i}].score may be null only for an unscored status")
        obj.setdefault("max_score", dim_max)
        root["dimensions"][i] = obj

    for section in ("strengths", "frictions"):
        for i, item in enumerate(root[section]):
            obj = dict(require_object(item, f"root.{section}[{i}]"))
            alias(obj, "title", "name", "label")
            alias(obj, "detail", "description", "summary")
            require_text(obj, "title", f"root.{section}[{i}]")
            require_text(obj, "detail", f"root.{section}[{i}]")
            root[section][i] = obj

    for i, item in enumerate(root["evidence"]):
        obj = dict(require_object(item, f"root.evidence[{i}]"))
        alias(obj, "source", "source_name")
        alias(obj, "excerpt", "example", "quote")
        require_text(obj, "source", f"root.evidence[{i}]")
        require_text(obj, "excerpt", f"root.evidence[{i}]")
        root["evidence"][i] = obj

    for i, item in enumerate(root["recommendations"]):
        obj = dict(require_object(item, f"root.recommendations[{i}]"))
        alias(obj, "title", "name", "label")
        alias(obj, "action", "description", "recommendation")
        require_text(obj, "title", f"root.recommendations[{i}]")
        require_text(obj, "action", f"root.recommendations[{i}]")
        root["recommendations"][i] = obj

    methodology = require_object(root["methodology"], "root.methodology")
    require_text(methodology, "scope", "root.methodology")
    caveats = require_list(methodology.get("caveats"), "root.methodology.caveats")
    for i, caveat in enumerate(caveats):
        if not isinstance(caveat, str) or not caveat.strip():
            raise SchemaError(f"root.methodology.caveats[{i}] must be a non-empty string")
    return root


def text_or(obj: dict[str, Any], key: str, fallback: str = "") -> str:
    value = obj.get(key, fallback)
    return esc(value if value not in (None, "") else fallback)


def confidence_label(value: Any) -> str:
    return {
        "high": "alta",
        "medium": "média",
        "low": "baixa",
        "insufficient": "insuficiente",
    }.get(str(value).lower(), str(value))


def status_label(value: Any) -> str:
    return {
        "scored": "pontuada",
        "not_measurable": "não mensurável",
        "not_applicable": "não aplicável",
        "included": "incluída",
        "excluded": "excluída",
    }.get(str(value).lower(), str(value))


CONF_CLASS = {"high": "alta", "medium": "media", "low": "baixa", "insufficient": "insuficiente"}


def conf_chip(confidence: Any) -> str:
    cls = CONF_CLASS.get(str(confidence).lower(), "baixa")
    return (
        f'<span class="conf {cls}"><span class="d" aria-hidden="true"></span>'
        f'confiança {esc(confidence_label(confidence))}</span>'
    )


def render_pips(score: Any, max_score: float, measurable: bool) -> str:
    slots = int(round(max_score))
    if not measurable or score is None:
        cells = "".join('<span class="pip na"></span>' for _ in range(slots))
        return f'<span class="pips" role="img" aria-label="Não mensurável">{cells}</span>'
    value = float(score)
    cells = []
    for n in range(1, slots + 1):
        if value >= n:
            cells.append('<span class="pip full"></span>')
        elif value >= n - 0.5:
            cells.append('<span class="pip half"></span>')
        else:
            cells.append('<span class="pip"></span>')
    aria = f"Nota {value:.1f} de {max_score:g}"
    return f'<span class="pips" role="img" aria-label="{esc(aria)}">{"".join(cells)}</span>'


def render_excerpts(excerpts: list[dict[str, Any]]) -> str:
    if not excerpts:
        return ""
    items = []
    for ex in excerpts:
        meta = " · ".join(
            esc(part) for part in (ex.get("source"), ex.get("date"), ex.get("locator")) if part
        )
        items.append(
            f'<figure class="excerpt"><blockquote>{esc(ex.get("text", ""))}</blockquote>'
            f'<figcaption class="src">{meta}</figcaption></figure>'
        )
    return f'<div class="excerpts">{"".join(items)}</div>'


def render_radar(dimensions: list[dict[str, Any]]) -> str:
    n = len(dimensions)
    if n == 0:
        return ""
    cx = cy = 150.0
    outer = 105.0
    max_score = 5.0

    def point(radius: float, idx: int) -> tuple[float, float]:
        angle = math.radians(-90 + idx * 360.0 / n)
        return cx + radius * math.cos(angle), cy + radius * math.sin(angle)

    rings = []
    for step in range(1, 6):
        radius = outer * step / max_score
        pts = " ".join(f"{x:.2f},{y:.2f}" for x, y in (point(radius, i) for i in range(n)))
        extra = ' stroke="var(--border-strong)"' if step == 5 else ""
        rings.append(f'<polygon points="{pts}"{extra}/>')

    spokes, na_marks, labels, data_pts = [], [], [], []
    aria_bits = []
    for i, dim in enumerate(dimensions):
        ex, ey = point(outer, i)
        measurable = dim.get("status") == "scored" and dim.get("score") is not None
        cos_a = math.cos(math.radians(-90 + i * 360.0 / n))
        anchor = "middle" if abs(cos_a) < 0.34 else ("start" if cos_a > 0 else "end")
        lx, ly = point(outer + 18, i)
        na = not measurable
        fill = "var(--radar-na)" if na else "var(--text-soft)"
        labels.append(
            f'<text x="{lx:.2f}" y="{ly:.2f}" text-anchor="{anchor}" dy="0.32em" fill="{fill}">'
            f'{esc(dim["name"])}</text>'
        )
        if measurable:
            spokes.append(f'<line x1="{cx:.0f}" y1="{cy:.0f}" x2="{ex:.2f}" y2="{ey:.2f}"/>')
            dx, dy = point(outer * float(dim["score"]) / max_score, i)
            data_pts.append((dx, dy))
            aria_bits.append(f'{dim["name"]} {float(dim["score"]):.1f}')
        else:
            na_marks.append(
                f'<line x1="{cx:.0f}" y1="{cy:.0f}" x2="{ex:.2f}" y2="{ey:.2f}" '
                f'stroke="var(--radar-na)" stroke-width="1.4" stroke-dasharray="4 4"/>'
                f'<circle cx="{ex:.2f}" cy="{ey:.2f}" r="4.5" fill="none" stroke="var(--radar-na)" '
                f'stroke-width="1.4" stroke-dasharray="3 3"/>'
            )
            aria_bits.append(f'{dim["name"]} não mensurável')

    data_poly = " ".join(f"{x:.2f},{y:.2f}" for x, y in data_pts)
    dots = "".join(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3.4"/>' for x, y in data_pts)
    aria = "Radar das dimensões. " + ", ".join(aria_bits) + "."
    return (
        f'<svg class="radar-svg" viewBox="-64 -46 428 392" role="img" aria-label="{esc(aria)}">'
        f'<g fill="none" stroke="var(--radar-grid)" stroke-width="1">{"".join(rings)}</g>'
        f'<g stroke="var(--radar-grid)" stroke-width="1">{"".join(spokes)}</g>'
        f'{"".join(na_marks)}'
        f'<polygon points="{data_poly}" fill="var(--radar-fill)" stroke="var(--radar-poly)" '
        f'stroke-width="2" stroke-linejoin="round"/>'
        f'<g fill="var(--radar-poly)">{dots}</g>'
        f'<g font-family="var(--font)" font-size="11.5" font-weight="600">{"".join(labels)}</g>'
        f'</svg>'
    )


def render_gauge(overall: Any, overall_max: float, score_status: str) -> tuple[str, str]:
    circumference = 2 * math.pi * 52
    if overall is None:
        progress = ""
        num = "—"
        badge = (
            '<span class="status-pub status-held"><span class="dot" aria-hidden="true"></span>'
            'Retida</span>'
        )
        aria = "Nota global retida"
    else:
        filled = float(overall) / overall_max * circumference
        progress = (
            f'<circle cx="70" cy="70" r="52" fill="none" stroke="var(--success-2)" stroke-width="14" '
            f'stroke-linecap="round" stroke-dasharray="{filled:.2f} {circumference:.2f}" '
            f'transform="rotate(-90 70 70)"/>'
        )
        num = f"{float(overall):.1f}"
        if score_status == "published":
            badge = '<span class="status-pub"><span class="dot" aria-hidden="true"></span>Publicada</span>'
        else:
            badge = (
                '<span class="status-pub status-held"><span class="dot" aria-hidden="true"></span>'
                'Retida</span>'
            )
        aria = f"Nota global {float(overall):.1f} de {overall_max:g}"
    gauge = (
        f'<div class="gauge-wrap" role="img" aria-label="{esc(aria)}">'
        f'<svg viewBox="0 0 140 140" aria-hidden="true">'
        f'<circle cx="70" cy="70" r="52" fill="none" stroke="var(--track)" stroke-width="14"/>'
        f'{progress}</svg>'
        f'<div class="gauge-center"><div class="gauge-num">{esc(num)}<small>/{overall_max:g}</small></div>'
        f'<div class="gauge-cap">nota global</div></div></div>'
    )
    return gauge, badge


def render_dimension_cards(dimensions: list[dict[str, Any]], audience: str) -> str:
    cards = []
    for i, dim in enumerate(dimensions):
        idx = f"{i + 1:02d}"
        score = dim.get("score")
        max_score = float(dim.get("max_score", 5))
        status = dim.get("status", "scored")
        measurable = status == "scored" and score is not None
        pips = render_pips(score, max_score, measurable)
        if measurable:
            pip_val = f'<span class="pip-val">{float(score):.1f}</span>'
            right = conf_chip(dim.get("confidence"))
            card_cls = "dim card"
        else:
            pip_val = '<span class="pip-val na">n/a</span>'
            label = "não aplicável" if status == "not_applicable" else "não mensurável"
            right = f'<span class="na-badge">{esc(label)}</span>'
            card_cls = "dim card na-dim"

        limitations = [str(x) for x in dim.get("limitations", [])]
        recommendation = dim.get("recommendation")
        evi_inner = []
        if limitations:
            evi_inner.append(
                '<span class="lbl">Limitações</span><p>' + esc("; ".join(limitations)) + "</p>"
            )
        if recommendation:
            evi_inner.append('<span class="lbl">O que melhorar</span><p>' + esc(str(recommendation)) + "</p>")
        details = ""
        if evi_inner:
            details = (
                '<details class="evi"><summary><span class="chev" aria-hidden="true">▶</span>'
                'ver limitações / o que melhorar</summary>'
                f'<div class="evi-body">{"".join(evi_inner)}</div></details>'
            )

        excerpts_block = ""
        if audience == "personal":
            excerpts_block = render_excerpts(dim.get("evidence_excerpts", []))

        info = ""
        tip = DIMENSION_TOOLTIPS.get(dim.get("id"))
        if tip:
            info = (
                f'<span class="dim-info" tabindex="0" role="button" aria-label="{esc(tip)}">'
                f'<span class="dim-info-mark" aria-hidden="true">i</span>'
                f'<span class="dim-tip" role="tooltip">{esc(tip)}</span></span>'
            )

        cards.append(
            f'<article class="{card_cls}"><div class="dim-top">'
            f'<span class="dim-idx">{esc(idx)}</span>'
            f'<span class="dim-name">{text_or(dim, "name")}{info}</span>'
            f'<div class="dim-right">{pips}{pip_val}{right}</div></div>'
            f'<p class="dim-forme"><b>Resumo:</b> {text_or(dim, "summary", "Sem observação adicional.")}</p>'
            f'{excerpts_block}{details}</article>'
        )
    return "".join(cards)


def render_callouts(items: list[dict[str, Any]], kind: str, empty: str) -> str:
    if not items:
        return f'<p class="empty">{esc(empty)}</p>'
    icon = "✓" if kind == "pos" else "!"
    blocks = []
    for item in items:
        sev = ""
        if item.get("confidence"):
            sev = f'<span class="sev">confiança {esc(confidence_label(item["confidence"]))}</span>'
        title_html = text_or(item, "title")
        detail_html = text_or(item, "detail")
        # Avoid repeating the same sentence twice (e.g. strengths where title == detail).
        body = f'<b>{title_html}</b>' + (f' {detail_html}' if detail_html and detail_html != title_html else "")
        blocks.append(
            f'<div class="callout {kind}"><span class="ic" aria-hidden="true">{icon}</span>'
            f'<p>{body}{sev}</p></div>'
        )
    return f'<div class="callout-list">{"".join(blocks)}</div>'


def render_todos(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<p class="empty">Nenhuma recomendação priorizada.</p>'
    blocks = []
    for i, item in enumerate(items):
        priority = text_or(item, "priority", str(i + 1))
        why = (
            f'<p class="todo-why"><b>Por quê:</b> {text_or(item, "why")}</p>'
            if item.get("why") else ""
        )
        signal = (
            f'<span class="todo-signal"><span class="s" aria-hidden="true">◎</span>'
            f'<span><b>Sinal de sucesso:</b> {text_or(item, "effort")}</span></span>'
            if item.get("effort") else ""
        )
        blocks.append(
            f'<label class="todo-item card"><input type="checkbox" class="cb" '
            f'aria-label="Concluir recomendação {esc(priority)}">'
            f'<div><div class="todo-action">{esc(priority)}. {text_or(item, "action")}</div>'
            f'{why}{signal}</div></label>'
        )
    return f'<div class="todo">{"".join(blocks)}</div>'


def render_coverage_rows(sources: list[dict[str, Any]]) -> str:
    rows = []
    for item in sources:
        name = text_or(item, "name")
        status = status_label(item.get("status", ""))
        if item.get("status") == "excluded":
            ceiling, cap_cls = "fora de escopo", "none"
        else:
            ceiling = str(item.get("coverage_label", "—"))
            low = ceiling.lower()
            if low == "alta":
                cap_cls = "alta"
            elif low in ("média", "media"):
                cap_cls = "media"
            elif low == "baixa":
                cap_cls = "baixa"
            else:
                cap_cls = "none"
        note = text_or(item, "note", "—")
        rows.append(
            f'<tr><td><span class="src">{name}</span></td><td>{esc(status)}</td>'
            f'<td><span class="cap {cap_cls}"><span class="d" aria-hidden="true"></span>'
            f'{esc(ceiling)}</span></td><td>{note}</td></tr>'
        )
    return "".join(rows)


def render_evidence_table(evidence: list[dict[str, Any]]) -> str:
    if not evidence:
        return '<p class="empty">Nenhum trecho abstrato foi incluído no relatório.</p>'
    rows = "".join(
        f'<tr><td><span class="src">{text_or(item, "source")}</span></td>'
        f'<td>{text_or(item, "excerpt")}</td><td>{text_or(item, "context", "—")}</td></tr>'
        for item in evidence
    )
    return (
        '<div class="table-scroll"><table><thead><tr>'
        '<th scope="col">Fonte</th><th scope="col">Evidência (abstrata)</th>'
        '<th scope="col">Classificação</th></tr></thead>'
        f'<tbody>{rows}</tbody></table></div>'
    )


def render(data: dict[str, Any], audience: str = "shareable") -> str:
    summary = data["executive_summary"]
    raw_overall = summary["overall_score"]
    overall = None if raw_overall is None else float(raw_overall)
    overall_max = float(summary.get("score_max", 5))
    subject = data.get("subject") if isinstance(data.get("subject"), dict) else {}
    dims = data["dimensions"]

    measurable = summary.get("measurable_dimensions")
    if not isinstance(measurable, int):
        measurable = sum(
            1 for d in dims if d.get("status", "scored") == "scored" and d.get("score") is not None
        )
    total = summary.get("total_dimensions") or len(dims)
    score_status = summary.get("score_status", "published")
    confidence = str(summary.get("confidence", "")).lower()
    low_conf = confidence in ("low", "insufficient")

    gauge, status_badge = render_gauge(overall, overall_max, score_status)
    radar = render_radar(dims)
    dimension_cards = render_dimension_cards(dims, audience)
    strengths = render_callouts(data["strengths"], "pos", "Nenhuma força documentada.")
    frictions = render_callouts(data["frictions"], "risk", "Nenhuma fricção documentada.")
    todos = render_todos(data["recommendations"])
    coverage_rows = render_coverage_rows(data["sources"])
    evidence_table = render_evidence_table(data["evidence"])
    caveats = "".join(f"<li>{esc(item)}</li>" for item in data["methodology"]["caveats"])

    overall_chip = "retida" if overall is None else f"{float(overall):.1f}/{overall_max:g}"
    period_from = summary.get("period_from")
    period_to = summary.get("period_to")
    window = f"{esc(str(period_from))} – {esc(str(period_to))}" if period_from and period_to else "—"
    sources_label = esc(summary.get("sources_label", "")) or "—"
    coverage_label = esc(summary.get("coverage_label", "—"))
    role = text_or(subject, "role") if subject.get("role") else ""
    name = text_or(subject, "name") if subject.get("name") else "Pessoa avaliada"
    generated = esc(data["generated_at"])

    meta_chips = [f'<span class="meta"><span class="dot" aria-hidden="true"></span><b>{name}</b></span>']
    if role:
        meta_chips.append(f'<span class="meta">Papel:&nbsp;<b>{role}</b></span>')
    meta_chips.append(f'<span class="meta">Período:&nbsp;<b>{window}</b></span>')
    meta_chips.append(f'<span class="meta">Fontes:&nbsp;<b>{sources_label}</b></span>')
    meta_chips.append(f'<span class="meta">Cobertura global:&nbsp;<b>{coverage_label}</b></span>')

    quick_chips = (
        f'<span class="chip"><span class="v">{esc(overall_chip)}</span><span class="l">nota global</span></span>'
        f'<span class="chip"><span class="v">{measurable}/{total} mensuráveis</span><span class="l">dimensões</span></span>'
        f'<span class="chip"><span class="v">{window}</span><span class="l">janela</span></span>'
        f'<span class="chip"><span class="v">{sources_label}</span><span class="l">fontes</span></span>'
    )

    low_banner = ""
    if low_conf:
        low_banner = (
            '<div class="lowconf"><span class="ic" aria-hidden="true">!</span>'
            f'<p><span class="tag">CONFIANÇA {esc(confidence_label(confidence)).upper()}.</span> '
            'Trate esta nota como leitura direcional, não veredito: a amostra interpretável por fonte é '
            'pequena e as janelas são curtas e não comparáveis entre ferramentas. '
            '<b>Serve para orientar a próxima ação</b> — não para medir senioridade, produtividade ou '
            'capacidade técnica.</p></div>'
        )

    private_banner = ""
    audience_note = "versão para compartilhar"
    evidence_hint = "Excertos abstratos (afirmações classificadas); não são prompts integrais."
    if audience == "personal":
        private_banner = (
            '<div class="private-banner" role="alert"><span class="ic" aria-hidden="true">🔒</span>'
            '<span>PRIVADO — contém trechos das suas sessões · NÃO compartilhar</span></div>'
        )
        audience_note = "versão pessoal"
        evidence_hint = (
            "Os trechos reais das sessões aparecem em cada dimensão acima; a tabela lista as "
            "afirmações abstratas classificadas."
        )

    rubric = (
        f'<h3>Rubrica</h3><p>{text_or(data["methodology"], "rubric")}</p>'
        if data["methodology"].get("rubric") else ""
    )

    return f'''<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:; object-src 'none'; base-uri 'none'; form-action 'none'">
<meta name="referrer" content="no-referrer"><title>{esc(data['title'])}</title>
<style>
:root{{
--bg:#fafafa;--surface:#fff;--surface-2:#f5f5f5;--surface-3:#fafafa;--border:#e5e5e5;--border-strong:#d4d4d4;
--text:#171717;--text-soft:#404040;--text-muted:#737373;
--brand:#e92e30;--brand-strong:#b92022;--brand-ink:#830405;--brand-soft:#fff6f6;--brand-soft-2:#ffecec;--brand-line:#ffc1c2;
--success:#16a34a;--success-2:#10b981;--warning:#f59e0b;--warning-ink:#a16207;--danger:#dc2626;--info:#2563eb;--violet:#8b5cf6;
--track:#e5e5e5;--shadow-sm:0 1px 2px rgba(23,23,23,.06),0 1px 3px rgba(23,23,23,.05);--shadow-md:0 2px 4px rgba(23,23,23,.05),0 8px 24px rgba(23,23,23,.07);
--radius:16px;--radius-sm:11px;--font:Inter,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
--radar-grid:#e5e5e5;--radar-poly:#e92e30;--radar-fill:rgba(233,46,48,.12);--radar-na:#a3a3a3;--pip-empty:#e5e5e5;color-scheme:light dark}}
@media (prefers-color-scheme:dark){{:root{{
--bg:#141414;--surface:#1d1d1d;--surface-2:#232323;--surface-3:#1a1a1a;--border:#333;--border-strong:#404040;
--text:#fafafa;--text-soft:#d4d4d4;--text-muted:#a3a3a3;
--brand:#ff6b6d;--brand-strong:#ff4143;--brand-ink:#ff9697;--brand-soft:rgba(255,65,67,.10);--brand-soft-2:rgba(255,65,67,.16);--brand-line:rgba(255,107,109,.45);
--success:#22c55e;--success-2:#10b981;--warning:#eab308;--warning-ink:#eab308;--danger:#ef4444;--info:#60a5fa;--violet:#a78bfa;
--track:#3a3a3a;--shadow-sm:0 1px 2px rgba(0,0,0,.4);--shadow-md:0 8px 28px rgba(0,0,0,.45);
--radar-grid:#3a3a3a;--radar-poly:#ff6b6d;--radar-fill:rgba(255,107,109,.16);--radar-na:#8a8a8a;--pip-empty:#3a3a3a}}}}
:root[data-theme="dark"]{{
--bg:#141414;--surface:#1d1d1d;--surface-2:#232323;--surface-3:#1a1a1a;--border:#333;--border-strong:#404040;
--text:#fafafa;--text-soft:#d4d4d4;--text-muted:#a3a3a3;
--brand:#ff6b6d;--brand-strong:#ff4143;--brand-ink:#ff9697;--brand-soft:rgba(255,65,67,.10);--brand-soft-2:rgba(255,65,67,.16);--brand-line:rgba(255,107,109,.45);
--success:#22c55e;--success-2:#10b981;--warning:#eab308;--warning-ink:#eab308;--danger:#ef4444;--info:#60a5fa;--violet:#a78bfa;
--track:#3a3a3a;--shadow-sm:0 1px 2px rgba(0,0,0,.4);--shadow-md:0 8px 28px rgba(0,0,0,.45);
--radar-grid:#3a3a3a;--radar-poly:#ff6b6d;--radar-fill:rgba(255,107,109,.16);--radar-na:#8a8a8a;--pip-empty:#3a3a3a}}
:root[data-theme="light"]{{
--bg:#fafafa;--surface:#fff;--surface-2:#f5f5f5;--surface-3:#fafafa;--border:#e5e5e5;--border-strong:#d4d4d4;
--text:#171717;--text-soft:#404040;--text-muted:#737373;
--brand:#e92e30;--brand-strong:#b92022;--brand-ink:#830405;--brand-soft:#fff6f6;--brand-soft-2:#ffecec;--brand-line:#ffc1c2;
--success:#16a34a;--success-2:#10b981;--warning:#f59e0b;--warning-ink:#a16207;--danger:#dc2626;--info:#2563eb;--violet:#8b5cf6;
--track:#e5e5e5;--radar-grid:#e5e5e5;--radar-poly:#e92e30;--radar-fill:rgba(233,46,48,.12);--radar-na:#a3a3a3;--pip-empty:#e5e5e5}}
*{{box-sizing:border-box}}html{{-webkit-text-size-adjust:100%}}
body{{margin:0;background:var(--bg);color:var(--text);font-family:var(--font);line-height:1.55;font-size:15px;-webkit-font-smoothing:antialiased;overflow-x:hidden}}
.wrap{{max-width:1080px;margin:0 auto;padding:28px 22px 64px}}
h1,h2,h3{{margin:0;line-height:1.25;letter-spacing:-.01em}}p{{margin:0}}a{{color:var(--brand-strong)}}
::selection{{background:var(--brand-soft-2);color:var(--brand-ink)}}
:focus-visible{{outline:2.5px solid var(--brand);outline-offset:2px;border-radius:6px}}
.card{{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow-sm)}}
.section{{margin-top:26px}}
.section-head{{display:flex;align-items:baseline;gap:12px;margin-bottom:14px;flex-wrap:wrap}}
.section-head h2{{font-size:16px;font-weight:700}}
.section-head .kicker{{font-size:11px;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:var(--brand-strong)}}
.section-head .hint{{font-size:12.5px;color:var(--text-muted);margin-left:auto}}
.private-banner{{display:flex;align-items:center;gap:11px;margin-bottom:18px;padding:14px 16px;border-radius:var(--radius-sm);background:var(--brand-soft-2);border:1px solid var(--brand-line);color:var(--brand-ink);font-weight:700;font-size:13.5px;letter-spacing:.01em}}
.private-banner .ic{{flex:none;width:26px;height:26px;border-radius:7px;background:var(--brand);color:#fff;display:grid;place-items:center;font-size:14px;font-weight:800}}
header.hero{{padding:26px 26px 24px;overflow:hidden}}
.brand-row{{display:flex;align-items:center;gap:11px;margin-bottom:18px}}
.brand-mark{{width:30px;height:30px;border-radius:8px;background:linear-gradient(150deg,var(--brand),var(--brand-strong));display:grid;place-items:center;color:#fff;font-weight:800;font-size:15px;box-shadow:var(--shadow-sm);flex:none}}
.brand-name{{font-weight:700;font-size:13px;letter-spacing:.02em}}.brand-name span{{color:var(--text-muted);font-weight:500}}
.hero-grid{{display:grid;grid-template-columns:1fr auto;gap:28px;align-items:center}}
.hero-title{{font-size:26px;font-weight:800;letter-spacing:-.02em}}
.hero-sub{{margin-top:8px;color:var(--text-soft);font-size:14px;max-width:52ch}}
.meta-row{{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}}
.meta{{display:inline-flex;align-items:center;gap:7px;padding:5px 11px;background:var(--surface-2);border:1px solid var(--border);border-radius:999px;font-size:12.5px;color:var(--text-soft);white-space:nowrap}}
.meta b{{color:var(--text);font-weight:600}}.meta .dot{{width:6px;height:6px;border-radius:50%;background:var(--brand);flex:none}}
.chips{{display:flex;flex-wrap:wrap;gap:9px;margin-top:16px}}
.chip{{display:inline-flex;align-items:center;gap:8px;padding:9px 13px;background:var(--surface-2);border:1px solid var(--border);border-radius:12px;white-space:nowrap}}
.chip .v{{font-size:15px;font-weight:800;letter-spacing:-.01em;color:var(--text)}}.chip .l{{font-size:11px;color:var(--text-muted);font-weight:500}}
.score-cluster{{display:flex;flex-direction:column;align-items:center;gap:12px;min-width:210px}}
.gauge-wrap{{position:relative;width:172px;height:172px}}.gauge-wrap svg{{width:100%;height:100%;display:block}}
.gauge-center{{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center}}
.gauge-num{{font-size:44px;font-weight:800;letter-spacing:-.03em;line-height:1;color:var(--text)}}.gauge-num small{{font-size:18px;font-weight:600;color:var(--text-muted)}}
.gauge-cap{{margin-top:3px;font-size:10.5px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--text-muted)}}
.status-pub{{display:inline-flex;align-items:center;gap:6px;font-size:11.5px;font-weight:600;color:var(--success);background:color-mix(in srgb,var(--success) 12%,transparent);border:1px solid color-mix(in srgb,var(--success) 32%,transparent);padding:3px 10px;border-radius:999px}}
.status-pub .dot{{width:6px;height:6px;border-radius:50%;background:var(--success)}}
.status-held{{color:var(--text-muted);background:var(--surface-2);border-color:var(--border-strong)}}.status-held .dot{{background:var(--text-muted)}}
.lowconf{{display:flex;gap:11px;align-items:flex-start;margin-top:20px;padding:13px 15px;border-radius:var(--radius-sm);background:color-mix(in srgb,var(--warning) 12%,transparent);border:1px solid color-mix(in srgb,var(--warning) 40%,transparent)}}
.lowconf .ic{{flex:none;width:22px;height:22px;border-radius:50%;background:var(--warning);color:#171717;font-weight:800;display:grid;place-items:center;font-size:14px}}
.lowconf p{{font-size:13px;color:var(--text-soft)}}.lowconf b{{color:var(--text)}}.lowconf .tag{{display:inline-block;font-weight:800;color:var(--warning-ink);letter-spacing:.04em}}
.radar-card{{padding:22px 24px}}.radar-layout{{display:grid;grid-template-columns:1fr 300px;gap:26px;align-items:center}}
.radar-svg{{width:100%;height:auto;display:block;max-width:440px;margin:0 auto}}
.legend h3{{font-size:13px;font-weight:700;margin-bottom:6px}}.legend p{{font-size:13px;color:var(--text-soft);margin-bottom:14px}}
.legend-item{{display:flex;gap:10px;align-items:flex-start;font-size:12.5px;color:var(--text-soft);margin-bottom:10px}}
.legend-item .sw{{flex:none;width:26px;height:14px;border-radius:4px;margin-top:2px}}
.sw-poly{{background:var(--radar-fill);border:1.6px solid var(--radar-poly)}}.sw-grid{{background:transparent;border:1px solid var(--border-strong)}}
.sw-na{{background:repeating-linear-gradient(45deg,var(--radar-na),var(--radar-na) 2px,transparent 2px,transparent 5px);border:1px dashed var(--radar-na)}}
.dims{{display:flex;flex-direction:column;gap:10px}}.dim{{padding:16px 18px}}
.dim-top{{display:grid;grid-template-columns:26px 1fr auto;gap:14px;align-items:center}}
.dim-idx{{width:26px;height:26px;border-radius:8px;background:var(--surface-2);border:1px solid var(--border);display:grid;place-items:center;font-size:12px;font-weight:700;color:var(--text-muted);font-family:var(--mono)}}
.dim-name{{font-size:15px;font-weight:700;letter-spacing:-.01em}}
.dim-info{{position:relative;display:inline-flex;align-items:center;justify-content:center;vertical-align:middle;margin-left:7px;width:16px;height:16px;border-radius:50%;background:var(--surface-2);border:1px solid var(--border-strong);color:var(--text-muted);cursor:help;flex:none}}
.dim-info:hover,.dim-info:focus-visible{{color:var(--brand-strong);border-color:var(--brand-line);background:var(--brand-soft)}}
.dim-info-mark{{font-size:10px;font-weight:800;font-style:normal;line-height:1;font-family:var(--font)}}
.dim-tip{{position:absolute;left:0;top:calc(100% + 8px);z-index:60;width:max-content;max-width:min(320px,calc(100vw - 32px));white-space:normal;padding:11px 13px;border-radius:var(--radius-sm);background:var(--surface);color:var(--text-soft);border:1px solid var(--border-strong);box-shadow:var(--shadow-md);font-size:12.5px;font-weight:400;line-height:1.5;letter-spacing:normal;text-transform:none;opacity:0;visibility:hidden;transform:translateY(-3px);transition:opacity .15s ease,transform .15s ease;pointer-events:none}}
.dim-info:hover .dim-tip,.dim-info:focus .dim-tip,.dim-info:focus-within .dim-tip,.dim-info:focus-visible .dim-tip{{opacity:1;visibility:visible;transform:translateY(0)}}
.dim-right{{display:flex;align-items:center;gap:14px;flex-wrap:wrap;justify-content:flex-end}}
.pips{{display:inline-flex;gap:5px;align-items:center}}
.pip{{width:15px;height:15px;border-radius:50%;background:var(--pip-empty);position:relative;overflow:hidden}}
.pip.full{{background:var(--brand)}}.pip.half::before{{content:"";position:absolute;inset:0;width:50%;background:var(--brand)}}
.pip.na{{background:repeating-linear-gradient(45deg,var(--radar-na),var(--radar-na) 2px,transparent 2px,transparent 4px);border:1px dashed var(--radar-na);width:14px;height:14px}}
.pip-val{{font-family:var(--mono);font-size:13px;font-weight:700;color:var(--text);min-width:30px;text-align:right;white-space:nowrap}}
.pip-val.na{{color:var(--text-muted);font-weight:600}}
.conf{{display:inline-flex;align-items:center;gap:6px;font-size:11.5px;font-weight:600;padding:3px 9px;border-radius:999px;white-space:nowrap}}.conf .d{{width:6px;height:6px;border-radius:50%}}
.conf.alta{{color:var(--success);background:color-mix(in srgb,var(--success) 13%,transparent);border:1px solid color-mix(in srgb,var(--success) 32%,transparent)}}.conf.alta .d{{background:var(--success)}}
.conf.media{{color:var(--warning-ink);background:color-mix(in srgb,var(--warning) 14%,transparent);border:1px solid color-mix(in srgb,var(--warning) 34%,transparent)}}.conf.media .d{{background:var(--warning)}}
.conf.baixa{{color:var(--text-muted);background:var(--surface-2);border:1px dashed var(--border-strong)}}.conf.baixa .d{{background:var(--text-muted)}}
.conf.insuficiente{{color:var(--text-muted);background:var(--surface-2);border:1px dashed var(--border-strong)}}.conf.insuficiente .d{{background:var(--text-muted)}}
.dim-forme{{margin:11px 0 0 40px;font-size:13.5px;color:var(--text-soft)}}.dim-forme b{{color:var(--text);font-weight:600}}
.excerpts{{margin:11px 0 0 40px;display:flex;flex-direction:column;gap:9px}}
.excerpt{{margin:0;padding:11px 13px;background:var(--surface-3);border:1px solid var(--border);border-left:3px solid var(--brand-line);border-radius:var(--radius-sm)}}
.excerpt blockquote{{margin:0;font-size:13px;color:var(--text-soft)}}.excerpt blockquote::before{{content:"\\201C"}}.excerpt blockquote::after{{content:"\\201D"}}
.excerpt .src{{margin-top:6px;font-family:var(--mono);font-size:11px;color:var(--text-muted)}}
details.evi{{margin:11px 0 0 40px}}
details.evi>summary{{cursor:pointer;list-style:none;display:inline-flex;align-items:center;gap:7px;font-size:12.5px;font-weight:600;color:var(--brand-strong);padding:5px 0}}
details.evi>summary::-webkit-details-marker{{display:none}}details.evi>summary .chev{{transition:transform .18s ease;font-size:10px}}details.evi[open]>summary .chev{{transform:rotate(90deg)}}
.evi-body{{margin-top:8px;padding:13px 15px;background:var(--surface-3);border:1px solid var(--border);border-radius:var(--radius-sm);font-size:13px;color:var(--text-soft)}}
.evi-body .lbl{{font-size:10.5px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--text-muted);display:block;margin-bottom:3px}}
.evi-body .lbl+p{{margin-bottom:11px}}.evi-body .lbl+p:last-child{{margin-bottom:0}}
.dim.na-dim{{border-style:dashed;background:var(--surface-3)}}
.na-badge{{display:inline-flex;align-items:center;gap:6px;font-size:11px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:var(--text-muted);background:var(--surface-2);border:1px dashed var(--border-strong);padding:4px 10px;border-radius:999px;white-space:nowrap}}
.two-col{{display:grid;grid-template-columns:1fr 1fr;gap:22px}}
.callout-list{{display:flex;flex-direction:column;gap:11px}}
.callout{{display:flex;gap:12px;padding:14px 16px;border-radius:var(--radius-sm);border:1px solid var(--border);background:var(--surface)}}
.callout .ic{{flex:none;width:26px;height:26px;border-radius:8px;display:grid;place-items:center;font-weight:800;font-size:14px}}
.callout p{{font-size:13.5px;color:var(--text-soft)}}
.callout.pos{{border-color:color-mix(in srgb,var(--success) 30%,var(--border))}}.callout.pos .ic{{background:color-mix(in srgb,var(--success) 15%,transparent);color:var(--success)}}
.callout.risk{{border-color:color-mix(in srgb,var(--warning) 32%,var(--border))}}.callout.risk .ic{{background:color-mix(in srgb,var(--warning) 15%,transparent);color:var(--warning-ink)}}
.sev{{display:inline-block;font-size:10.5px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:var(--warning-ink);margin-top:5px}}
.todo{{display:flex;flex-direction:column;gap:12px}}.todo-item{{display:grid;grid-template-columns:24px 1fr;gap:13px;padding:16px 18px}}
.todo-item .cb{{appearance:none;-webkit-appearance:none;width:22px;height:22px;margin-top:1px;border:2px solid var(--border-strong);border-radius:7px;background:var(--surface);cursor:pointer;position:relative;flex:none;transition:.15s}}
.todo-item .cb:checked{{background:var(--success);border-color:var(--success)}}
.todo-item .cb:checked::after{{content:"";position:absolute;left:6px;top:2px;width:6px;height:11px;border:solid #fff;border-width:0 2.5px 2.5px 0;transform:rotate(45deg)}}
.todo-action{{font-size:14.5px;font-weight:700;color:var(--text);letter-spacing:-.01em}}
.todo-item:has(.cb:checked) .todo-action{{text-decoration:line-through;text-decoration-color:var(--text-muted);color:var(--text-muted)}}
.todo-why{{font-size:13px;color:var(--text-muted);margin-top:5px}}
.todo-signal{{display:inline-flex;align-items:flex-start;gap:7px;margin-top:9px;padding:7px 11px;background:color-mix(in srgb,var(--success) 10%,transparent);border:1px solid color-mix(in srgb,var(--success) 26%,transparent);border-radius:9px;font-size:12.5px;color:var(--text-soft)}}
.todo-signal .s{{color:var(--success);font-weight:700;flex:none}}.todo-signal b{{color:var(--text);font-weight:600}}
.table-scroll{{overflow-x:auto;border:1px solid var(--border);border-radius:var(--radius);background:var(--surface)}}
table{{border-collapse:collapse;width:100%;min-width:560px;font-size:13.5px}}
thead th{{text-align:left;font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--text-muted);padding:12px 16px;border-bottom:1px solid var(--border);background:var(--surface-2)}}
tbody td{{padding:13px 16px;border-bottom:1px solid var(--border);color:var(--text-soft);vertical-align:top}}
tbody tr:last-child td{{border-bottom:none}}td .src{{font-weight:700;color:var(--text)}}
.cap{{display:inline-flex;align-items:center;gap:6px;font-size:11.5px;font-weight:600;padding:2px 9px;border-radius:999px;white-space:nowrap}}.cap .d{{width:6px;height:6px;border-radius:50%}}
.cap.alta{{color:var(--success);background:color-mix(in srgb,var(--success) 13%,transparent);border:1px solid color-mix(in srgb,var(--success) 30%,transparent)}}.cap.alta .d{{background:var(--success)}}
.cap.baixa{{color:var(--text-muted);background:var(--surface-2);border:1px dashed var(--border-strong)}}.cap.baixa .d{{background:var(--text-muted)}}
.cap.media{{color:var(--warning-ink);background:color-mix(in srgb,var(--warning) 14%,transparent);border:1px solid color-mix(in srgb,var(--warning) 30%,transparent)}}.cap.media .d{{background:var(--warning)}}
.cap.none{{color:var(--text-muted);background:transparent;border:1px dashed var(--border)}}.cap.none .d{{background:var(--border-strong)}}
.method-wrap{{padding:0;overflow:hidden}}
details.method>summary{{cursor:pointer;list-style:none;display:flex;align-items:center;gap:11px;padding:17px 20px;font-weight:700;font-size:14.5px;color:var(--text)}}
details.method>summary::-webkit-details-marker{{display:none}}details.method>summary .chev{{margin-left:auto;transition:transform .18s ease;color:var(--text-muted)}}
details.method[open]>summary .chev{{transform:rotate(90deg)}}
details.method>summary .tagm{{font-size:11px;font-weight:600;color:var(--text-muted);background:var(--surface-2);border:1px solid var(--border);padding:2px 9px;border-radius:999px}}
.method-body{{padding:4px 22px 20px;border-top:1px solid var(--border)}}.method-body h3{{font-size:12.5px;margin:14px 0 4px;color:var(--text-soft)}}.method-body p{{font-size:13px;color:var(--text-muted)}}
.method-body ul{{margin:10px 0 0;padding-left:20px}}.method-body li{{font-size:13px;color:var(--text-muted);margin-bottom:9px;line-height:1.5}}
.empty{{margin:0;padding:18px;border:1px dashed var(--border);border-radius:var(--radius-sm);color:var(--text-muted);font-size:13.5px}}
.hint-note{{font-size:12.5px;color:var(--text-muted);margin-top:11px}}
footer{{margin-top:30px;text-align:center;font-size:12px;color:var(--text-muted)}}footer .sep{{margin:0 8px;opacity:.5}}
@media (max-width:860px){{.hero-grid{{grid-template-columns:1fr}}.score-cluster{{flex-direction:row;flex-wrap:wrap;justify-content:flex-start;align-items:center;gap:18px}}.radar-layout{{grid-template-columns:1fr}}.two-col{{grid-template-columns:1fr}}}}
@media (max-width:560px){{.wrap{{padding:18px 14px 48px}}.hero-title{{font-size:22px}}header.hero,.radar-card{{padding:20px 16px}}.dim{{padding:15px 15px}}.dim-forme,.excerpts,details.evi{{margin-left:0}}.dim-top{{grid-template-columns:26px 1fr}}.dim-right{{grid-column:1 / -1;justify-content:flex-start;margin-top:4px}}.gauge-wrap{{width:150px;height:150px}}}}
@media print{{:root{{color-scheme:light}}body{{background:#fff}}.card,.callout,.todo-item,.table-scroll{{break-inside:avoid}}}}
</style></head><body>
<div class="wrap">
{private_banner}
<header class="hero card">
<div class="brand-row"><div class="brand-mark" aria-hidden="true">AI</div><div class="brand-name">AI Workflow <span>· Assessment de Workflow com IA</span></div></div>
<div class="hero-grid">
<div>
<h1 class="hero-title">{esc(data['title'])}</h1>
<p class="hero-sub">{text_or(summary,'narrative')}</p>
<div class="meta-row">{"".join(meta_chips)}</div>
<div class="chips" aria-label="Estatísticas rápidas">{quick_chips}</div>
</div>
<div class="score-cluster">{gauge}{status_badge}</div>
</div>
{low_banner}
</header>

<section class="section" aria-labelledby="profile">
<div class="section-head"><span class="kicker">Visão geral</span><h2 id="profile">Perfil de maturidade — {total} dimensões</h2><span class="hint">escala 0–5 · dimensões n/a marcadas</span></div>
<div class="radar-card card"><div class="radar-layout">
<div>{radar}</div>
<div class="legend"><h3>Como ler</h3><p>Cada eixo é uma dimensão do seu workflow, de 0 (centro) a 5 (borda). Quanto mais preenchido, mais consolidado o hábito.</p>
<div class="legend-item"><span class="sw sw-poly" aria-hidden="true"></span><span>Seu perfil atual, dimensão a dimensão.</span></div>
<div class="legend-item"><span class="sw sw-grid" aria-hidden="true"></span><span>Anéis de referência marcam as notas 1 a 5.</span></div>
<div class="legend-item"><span class="sw sw-na" aria-hidden="true"></span><span>Eixos tracejados marcados como <b>n/a</b> não são zero: são <b>não mensuráveis</b> nesta janela.</span></div>
</div>
</div></div>
</section>

<section class="section" aria-labelledby="scorecard">
<div class="section-head"><span class="kicker">Placar</span><h2 id="scorecard">Dimensão por dimensão</h2><span class="hint">nota · confiança · o que significa</span></div>
<div class="dims">{dimension_cards}</div>
</section>

<section class="section">
<div class="two-col">
<div><div class="section-head"><span class="kicker">Positivo</span><h2>Forças observadas</h2></div>{strengths}</div>
<div><div class="section-head"><span class="kicker">Atenção</span><h2>Fricções e riscos</h2></div>{frictions}</div>
</div>
</section>

<section class="section" aria-labelledby="actions">
<div class="section-head"><span class="kicker">Próximos passos</span><h2 id="actions">Recomendações priorizadas</h2><span class="hint">marque ao concluir · cada uma tem um sinal de sucesso</span></div>
{todos}
</section>

<section class="section" aria-labelledby="evidence">
<div class="section-head"><span class="kicker">Base de evidência</span><h2 id="evidence">Exemplos de evidência</h2></div>
<p class="hint-note">{esc(evidence_hint)}</p>
{evidence_table}
</section>

<section class="section" aria-labelledby="coverage">
<div class="section-head"><span class="kicker">Base de evidência</span><h2 id="coverage">Cobertura por fonte</h2><span class="hint">o que sustenta (e limita) esta nota</span></div>
<div class="table-scroll"><table><thead><tr><th scope="col">Fonte</th><th scope="col">Status</th><th scope="col">Teto de confiança</th><th scope="col">Observação</th></tr></thead><tbody>{coverage_rows}</tbody></table></div>
</section>

<section class="section" aria-labelledby="method">
<div class="section-head"><span class="kicker">Como foi medido</span><h2 id="method">Metodologia e ressalvas</h2></div>
<details class="method card method-wrap"><summary>Ver escopo, premissas e ressalvas <span class="tagm">confiança {esc(confidence_label(confidence))}</span> <span class="chev" aria-hidden="true">▶</span></summary>
<div class="method-body"><h3>Escopo</h3><p>{text_or(data['methodology'],'scope')}</p>{rubric}<h3>Ressalvas</h3><ul>{caveats or '<li>Nenhuma ressalva registrada.</li>'}</ul></div>
</details>
</section>

<footer>{esc(data['title'])}<span class="sep">·</span>{esc(audience_note)}<span class="sep">·</span>gerado em {generated}<span class="sep">·</span>relatório local autocontido, sem dependências externas</footer>
</div>
</body></html>'''


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Preferred canonical schema (contract_version 1.0):
  contract_version, generated_at, subject, scope, dimensions, overall,
  strengths, priorities, not_measurable, methodology_warnings, privacy

Also accepted: presentation schema:
  meta: {title, generated_at, subject?: {name?, role?}}
  summary: {headline, narrative, overall_score, score_max?: 5, maturity_label?}
  sources: [{name, status, coverage: 0..100, note?}]
  dimensions: [{name, score, max_score?: 5, summary?}]
  strengths/frictions: [{title, detail, evidence_refs?: []}]
  evidence: [{source, excerpt, context?}]
  recommendations: [{priority?, title, action, why?, effort?}]
  methodology: {scope, rubric?, caveats: [string]}

See references/analysis-contract.md.
Additional keys are ignored. Common camelCase and label/description aliases are accepted.""",
    )
    parser.add_argument("input", type=Path, help="normalized assessment JSON")
    parser.add_argument("output", type=Path, help="destination HTML file")
    parser.add_argument(
        "--audience",
        choices=("personal", "shareable"),
        default="shareable",
        help="personal renders evidence_excerpts with a private banner (secrets-only gate); "
        "shareable drops excerpts and applies the strict privacy gate (default)",
    )
    args = parser.parse_args()
    try:
        with args.input.open(encoding="utf-8") as handle:
            raw_data = json.load(handle)
        if args.audience == "personal":
            # Personal file may keep the user's own project names, emails, URLs and paths;
            # fail closed only on secrets/credentials/tokens.
            scan_privacy(raw_data, SECRETS_PATTERNS)
        else:
            # Shareable file: strict scan over the whole input EXCEPT evidence_excerpts
            # (which are dropped from the output entirely).
            scan_privacy(raw_data, PRIVACY_PATTERNS, skip_keys=("evidence_excerpts",))
        data = validate(raw_data)
        document = render(data, args.audience)
        parent_existed = args.output.parent.exists()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if not parent_existed:
            args.output.parent.chmod(0o700)
        args.output.write_text(document, encoding="utf-8")
        args.output.chmod(0o600)
    except FileNotFoundError as exc:
        print(f"render_report: file not found: {exc.filename}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"render_report: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}", file=sys.stderr)
        return 2
    except (OSError, SchemaError) as exc:
        print(f"render_report: {exc}", file=sys.stderr)
        return 2
    print(f"Rendered {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
