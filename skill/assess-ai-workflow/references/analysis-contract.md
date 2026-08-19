# Contrato de análise

Todos os analisadores escrevem JSON UTF-8 válido e nunca incluem prompts integrais, respostas integrais, segredos ou dados pessoais desnecessários. Datas usam ISO 8601. Contagens sempre incluem denominador e regra de deduplicação.

## Saída de cada analisador de fonte

```json
{
  "contract_version": "1.0",
  "source": {
    "id": "codex_local",
    "tool": "opencode|codex|claude_code|cursor|other",
    "kind": "primary_history|aggregate_cache|config|artifact|model_subset",
    "paths_scanned": ["~/.codex/sessions"],
    "period": {"from": "2026-01-01T00:00:00Z", "to": "2026-07-01T00:00:00Z"},
    "parent_source_id": null
  },
  "coverage": {
    "eligible_units": 100,
    "readable_units": 92,
    "interpretable_units": 80,
    "unit": "root_session",
    "coverage_ratio": 0.8,
    "missing_reasons": ["8 arquivos ausentes"],
    "deduplication_key": "root_session_id",
    "retention_caveats": []
  },
  "observations": [
    {
      "id": "obs-001",
      "dimension": "framing|grounding|routing|context|validation|handoff|reuse|safety",
      "classification": "observed",
      "behavior": "Critérios de aceite foram explicitados antes da execução.",
      "polarity": "supports|contradicts|neutral",
      "task_id": "local-hash-or-redacted-id",
      "timestamp": "2026-06-10T12:00:00Z",
      "evidence_ref": {"source_id": "codex_local", "locator": "session hash + event index"},
      "role_lens": ["product_design"],
      "sensitivity": "low|moderate|high"
    }
  ],
  "metrics": [
    {
      "name": "sessions_with_validation",
      "value": 20,
      "denominator": 80,
      "unit": "root_session",
      "purpose": "corpus_description|supporting_signal",
      "interpretation_limit": "Não mede qualidade da validação."
    }
  ],
  "candidate_findings": [
    {
      "id": "finding-source-001",
      "dimension": "validation",
      "classification": "observed|inferred|not_measurable",
      "claim": "Validação aparece de modo recorrente nas tarefas de interface.",
      "observation_ids": ["obs-001"],
      "reasoning": "Obrigatório quando classification=inferred.",
      "alternative_explanation": "Obrigatório quando classification=inferred.",
      "confidence": "high|medium|low|insufficient",
      "limitations": []
    }
  ],
  "privacy": {
    "raw_content_retained": false,
    "redactions_applied": ["email", "token"],
    "high_sensitivity_excluded": 3
  },
  "errors": []
}
```

`coverage_ratio = interpretable_units / eligible_units`. Se `eligible_units` for desconhecido, use `null`, explique em `missing_reasons` e limite a confiança a `low`. `model_subset` exige `parent_source_id`; seus eventos devem manter a mesma chave de deduplicação do pai.

## Contrato do assessment final

```json
{
  "contract_version": "1.0",
  "generated_at": "2026-07-11T12:00:00-03:00",
  "subject": {
    "display_name": "Pessoa avaliada",
    "role_lens": ["leadership_operations"],
    "role_basis": "explicit|inferred|unknown",
    "intended_audience": "subject_private"
  },
  "scope": {
    "sources": ["codex_local", "claude_local"],
    "period": {"from": "2026-01-01", "to": "2026-07-01"},
    "excluded_sources": [{"source": "cursor", "reason": "not_found"}],
    "overall_coverage": "high|medium|low|insufficient",
    "comparability_warnings": []
  },
  "dimensions": [
    {
      "id": "framing",
      "status": "scored|not_measurable|not_applicable",
      "score": 4.0,
      "confidence": "high|medium|low|insufficient",
      "role_lens": ["leadership_operations"],
      "claims": [
        {
          "classification": "observed|inferred|not_measurable",
          "text": "Objetivos e restrições aparecem antes da delegação.",
          "evidence_refs": ["codex_local:obs-001"],
          "reasoning": null,
          "alternative_explanation": null
        }
      ],
      "counterevidence_refs": [],
      "limitations": [],
      "recommendation": "Adotar contrato curto de abertura nos casos ambíguos."
    }
  ],
  "overall": {
    "score": 4.1,
    "score_status": "published|withheld_insufficient_dimensions",
    "measurable_dimensions": 7,
    "confidence": "medium",
    "summary": "Síntese sem alegações sobre senioridade ou produtividade."
  },
  "strengths": [{"text": "...", "evidence_refs": ["..."]}],
  "priorities": [
    {
      "priority": 1,
      "action": "...",
      "why": "...",
      "success_signal": "...",
      "evidence_refs": ["..."]
    }
  ],
  "not_measurable": ["Impacto de negócio causal"],
  "methodology_warnings": [
    "Tokens, agentes e tamanho de chat não foram usados isoladamente como proxy de qualidade."
  ],
  "privacy": {
    "raw_prompts_in_report": false,
    "secrets_detected": 0,
    "sensitive_evidence_omitted": 0,
    "sharing_default": "private"
  }
}
```

Use `null`, não zero, para nota ou métrica desconhecida. Em dimensões `not_measurable` ou `not_applicable`, `score` deve ser `null`. Toda claim `inferred` exige `reasoning`, `alternative_explanation`, pelo menos 2 `evidence_refs` e confiança máxima `medium`, salvo triangulação direta entre fontes independentes.

## Dossiê profundo de evidências

Produza também `workflow-evidence.json` e renderize-o como `workflow-evidence.md` conforme [evidence-dossier-contract.md](evidence-dossier-contract.md). Esse dossiê usa as mesmas análises por fonte, janela, IDs de observação, lentes e regras de cobertura deste contrato. Ele pode conter mais casos e sequências do que o HTML, mas somente como paráfrases sanitizadas. Subagentes e variantes de modelo permanecem atributos do caso-raiz, nunca casos ou fontes independentes.

## Reconciliação

1. Deduplicate primeiro por sessão-raiz, depois por evento. Aliases de modelo e subagentes continuam vinculados ao pai.
2. Preserve períodos e coberturas por fonte; não some janelas sobrepostas ou caches agregados a históricos primários.
3. Converta observações em claim somente quando a evidência puder ser resumida sem expor conteúdo sensível.
4. Mostre evidência favorável e contraditória. Divergência inexplicada reduz a confiança um nível.
5. Aplique os mínimos da rubrica antes de pontuar. Confiança global nunca excede a menor confiança das fontes que sustentam as principais conclusões.
6. Valide: enums, referências existentes, denominadores, `coverage_ratio`, notas 1–5, mínimo de dimensões para nota global e ausência de conteúdo bruto.
