# Contrato do dossiê de evidências

`workflow-evidence.md` é um artefato interno, local e privado que organiza evidência sanitizada para outro agente checar ou reconciliar o assessment. Ele acompanha o HTML como sua camada profunda de evidência: aprofunda fluxos completos, padrões, contraexemplos e limites de cobertura sem reproduzir histórico bruto.

O dossiê não é o relatório de leitura do usuário nem um arquivo de auditoria forense. É a entrada estruturada que a pessoa pode fornecer, junto com o HTML, a outro agente para checagem posterior das conclusões. Usa locators locais não reversíveis ou redigidos e preserva as regras de `privacy.md` e os mínimos de evidência de `rubric.md`.

## Finalidade e ciclo de vida

Use o dossiê para:

- reconstruir a sequência operacional de tarefas representativas;
- mostrar contexto, decisão, ferramentas/agentes, validação, resultado e handoff no mesmo caso;
- identificar comportamentos recorrentes e exceções sem transformar volume em qualidade;
- dar ao reconciliador exemplos suficientes para confirmar ou rejeitar candidate findings;
- preservar rastreabilidade local sem copiar prompts, respostas, código ou dados pessoais.

Crie o arquivo somente dentro do diretório isolado do assessment, com nome exato `workflow-evidence.md` e permissões restritas. Preserve-o por padrão ao lado do HTML; apague apenas os JSONs intermediários. O usuário decide se encaminha os dois artefatos a outro agente. O dossiê deve permanecer sanitizado e privado durante todo o ciclo de vida.

## Regras não negociáveis

1. **Somente material sanitizado.** Nunca inclua prompts ou respostas completos, mensagens privadas, código proprietário, segredos, valores de configuração, documentos, URLs privadas, nomes de pessoas/empresas/projetos ou paths com username.
2. **Paráfrase abstrata.** Registre a função do trecho observado, não sua redação. Exemplo seguro: “o pedido definiu critérios de aceite e uma restrição de escopo”.
3. **Sem expansão de acesso.** O agente que escreve ou lê o dossiê não deve reabrir históricos brutos. Ele recebe somente inventário agregado, registros redigidos e análises por fonte autorizadas.
4. **Locator não é conteúdo.** Locators servem para checar identidade e posição de um evento dentro da execução local. Não podem conter texto do evento, identificadores externos reutilizáveis ou informação pessoal.
5. **Fato separado de interpretação.** Toda unidade de evidência é `observed`, `inferred` ou `not_measurable`. Uma inferência nunca deve ser reescrita como observação.
6. **Resultado antes de volume.** Tokens, contagem de mensagens, agentes, tools, arquivos, testes ou duração não demonstram qualidade. Só podem descrever o corpus ou apoiar uma cadeia com resultado verificável.
7. **Contradição visível.** Um padrão deve apontar também exceções e contraexemplos relevantes. Ausência de contraexemplo encontrado não equivale a consistência perfeita.
8. **Lente por fluxo.** Aplique a lente da tarefa observada, não um cargo presumido. Uma mesma pessoa pode ter fluxos em lentes diferentes.
9. **Privacidade prevalece sobre rastreabilidade.** Se um locator ou exemplo puder reidentificar alguém, generalize ou omita. Registre a omissão como limite de cobertura.
10. **Sem avaliação de terceiros.** O sujeito é a pessoa que autorizou o assessment; ações incidentais de colegas, clientes ou familiares não entram como evidência individual.

## Estrutura exata do Markdown

O arquivo deve usar os títulos abaixo, nesta ordem. Se uma seção não tiver evidência, mantenha o título e explique `not_measurable`; não invente conteúdo.

```markdown
# Workflow Evidence Dossier

## 1. Metadata and privacy envelope
## 2. Coverage and evidence map
## 3. Representative workflow cases
### WF-001 — <rótulo abstrato>
## 4. Recurring patterns
### PAT-001 — <comportamento abstrato>
## 5. Counterpatterns and late failures
### CTR-001 — <comportamento abstrato>
## 6. Tool, agent, and model routing map
## 7. Role-lens synthesis
## 8. Dimension evidence index
## 9. Not measurable, omitted, and conflicting evidence
## 10. Reconciliation notes for the next agent
## 11. Validation checklist
```

Escreva em português, salvo se o assessment solicitar outro idioma. Use datas ISO 8601 e IDs locais estáveis. Não use HTML embutido, imagens, links externos ou anexos.

## Modelo canônico JSON para renderização determinística

O conteúdo normativo pode ser serializado como `workflow-evidence.json` antes de renderizar o Markdown. O JSON é temporário, recebe as mesmas proteções e retenção do dossiê e deve validar contra este schema JSON Schema 2020-12. Campos textuais já devem chegar sanitizados; o renderer não é responsável por descobrir PII.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "local://assess-ai-workflow/workflow-evidence.schema.json",
  "title": "WorkflowEvidence",
  "type": "object",
  "additionalProperties": false,
  "required": ["contract", "contract_version", "metadata", "privacy_envelope", "coverage", "cases", "patterns", "counterpatterns", "routes", "role_lenses", "dimension_index", "limits", "reconciliation", "validation"],
  "properties": {
    "contract": {"const": "workflow-evidence"},
    "contract_version": {"const": "1.0"},
    "metadata": {
      "type": "object",
      "additionalProperties": false,
      "required": ["generated_at", "assessment_period", "subject_label", "requested_role_lens", "inferred_role_lens", "sources_in_scope", "source_analyses_used", "raw_histories_reopened", "raw_content_retained", "sharing_default", "sensitive_evidence_omitted", "locator_salt_scope"],
      "properties": {
        "generated_at": {"type": "string", "format": "date-time"},
        "assessment_period": {"$ref": "#/$defs/period"},
        "subject_label": {"type": "string", "minLength": 1},
        "requested_role_lens": {"type": "array", "items": {"$ref": "#/$defs/roleLens"}, "uniqueItems": true},
        "inferred_role_lens": {"type": "array", "items": {"$ref": "#/$defs/roleLens"}, "uniqueItems": true},
        "sources_in_scope": {"type": "array", "items": {"type": "string", "pattern": "^[a-z0-9_]+$"}, "uniqueItems": true},
        "source_analyses_used": {"type": "array", "items": {"type": "string", "pattern": "^analysis-[a-z0-9_-]+\\.json$"}, "uniqueItems": true},
        "raw_histories_reopened": {"const": false},
        "raw_content_retained": {"const": false},
        "sharing_default": {"const": "private"},
        "sensitive_evidence_omitted": {"type": "integer", "minimum": 0},
        "locator_salt_scope": {"const": "assessment_local"}
      }
    },
    "privacy_envelope": {"type": "string", "minLength": 1},
    "coverage": {
      "type": "object",
      "additionalProperties": false,
      "required": ["sources", "evidence_units_used", "sampling_rule", "known_blind_spots", "comparability"],
      "properties": {
        "sources": {"type": "array", "items": {"$ref": "#/$defs/sourceCoverage"}},
        "evidence_units_used": {"type": "object", "required": ["cases", "observations", "period_buckets"], "properties": {"cases": {"type": "integer", "minimum": 0}, "observations": {"type": "integer", "minimum": 0}, "period_buckets": {"type": "integer", "minimum": 0}}, "additionalProperties": false},
        "sampling_rule": {"type": "string", "minLength": 1},
        "known_blind_spots": {"type": "array", "items": {"type": "string"}},
        "comparability": {"type": "array", "items": {"$ref": "#/$defs/comparability"}}
      }
    },
    "cases": {"type": "array", "items": {"$ref": "#/$defs/workflowCase"}},
    "patterns": {"type": "array", "items": {"$ref": "#/$defs/pattern"}},
    "counterpatterns": {"type": "array", "items": {"$ref": "#/$defs/counterpattern"}},
    "routes": {"type": "array", "items": {"$ref": "#/$defs/route"}},
    "role_lenses": {"type": "array", "items": {"$ref": "#/$defs/roleSynthesis"}},
    "dimension_index": {"type": "array", "minItems": 8, "maxItems": 8, "items": {"$ref": "#/$defs/dimensionEntry"}},
    "limits": {
      "type": "object",
      "additionalProperties": false,
      "required": ["not_measurable", "omitted_for_privacy", "conflicts_and_source_limits"],
      "properties": {
        "not_measurable": {"type": "array", "items": {"type": "string"}},
        "omitted_for_privacy": {"type": "array", "items": {"$ref": "#/$defs/privacyOmission"}},
        "conflicts_and_source_limits": {"type": "array", "items": {"type": "string"}}
      }
    },
    "reconciliation": {
      "type": "object",
      "additionalProperties": false,
      "required": ["promote", "reject", "do_not_compare", "recommendation_candidates", "deduplication_confirmed"],
      "properties": {
        "promote": {"type": "array", "items": {"$ref": "#/$defs/reconciliationItem"}},
        "reject": {"type": "array", "items": {"$ref": "#/$defs/reconciliationItem"}},
        "do_not_compare": {"type": "array", "items": {"type": "string"}},
        "recommendation_candidates": {"type": "array", "items": {"$ref": "#/$defs/recommendation"}},
        "deduplication_confirmed": {"const": true}
      }
    },
    "validation": {"type": "array", "items": {"$ref": "#/$defs/check"}}
  },
  "$defs": {
    "roleLens": {"enum": ["engineering", "product_design", "leadership_operations", "research_content", "mixed", "unknown"]},
    "dimension": {"enum": ["framing", "grounding", "routing", "context", "validation", "handoff", "reuse", "safety"]},
    "classification": {"enum": ["observed", "inferred", "not_measurable"]},
    "confidence": {"enum": ["high", "medium", "low", "insufficient"]},
    "period": {"type": "object", "required": ["from", "to"], "properties": {"from": {"type": "string", "format": "date-time"}, "to": {"type": "string", "format": "date-time"}}, "additionalProperties": false},
    "sourceCoverage": {
      "type": "object", "additionalProperties": false,
      "required": ["source_id", "kind", "period", "eligible", "interpretable", "unit", "ratio", "dedup_key", "retention_caveat", "confidence_ceiling"],
      "properties": {
        "source_id": {"type": "string"}, "kind": {"enum": ["primary_history", "aggregate_cache", "config", "artifact", "model_subset"]}, "period": {"$ref": "#/$defs/period"},
        "eligible": {"type": ["integer", "null"], "minimum": 0}, "interpretable": {"type": ["integer", "null"], "minimum": 0}, "unit": {"type": "string"}, "ratio": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
        "dedup_key": {"type": "string"}, "retention_caveat": {"type": ["string", "null"]}, "confidence_ceiling": {"enum": ["high", "medium", "low", "insufficient", "inherited"]}
      }
    },
    "comparability": {"type": "object", "required": ["source_ids", "status", "reason"], "properties": {"source_ids": {"type": "array", "minItems": 2, "items": {"type": "string"}}, "status": {"enum": ["convergent", "conflicting", "not_comparable"]}, "reason": {"type": "string"}}, "additionalProperties": false},
    "sequenceEvent": {"type": "object", "required": ["classification", "text", "locators"], "properties": {"classification": {"enum": ["observed", "inferred"]}, "text": {"type": "string"}, "locators": {"type": "array", "items": {"$ref": "#/$defs/locator"}}}, "additionalProperties": false},
    "locator": {"type": "object", "required": ["ref", "source_id", "locator", "event_type", "timestamp_bucket", "sanitization"], "properties": {"ref": {"type": "string", "pattern": "^obs-[0-9]+$"}, "source_id": {"type": "string"}, "locator": {"type": "string", "pattern": "^[a-z0-9_]+/(sess_h|artifact_h):[a-f0-9]{8,12}…/.*$"}, "event_type": {"type": "string"}, "timestamp_bucket": {"type": "string"}, "sanitization": {"type": "string"}}, "additionalProperties": false},
    "workflowCase": {
      "type": "object", "additionalProperties": false,
      "required": ["id", "label", "case_status", "primary_role_lens", "secondary_role_lenses", "period_bucket", "root_task_locator", "classification", "confidence", "sensitivity", "dimensions", "context_and_intent", "workflow_sequence", "tool_and_agent_chain", "context_management", "validation_and_feedback", "outcome_and_handoff", "supporting_refs", "contradicting_refs", "interpretation", "alternative_explanation", "locator_ledger"],
      "properties": {
        "id": {"type": "string", "pattern": "^WF-[0-9]{3}$"}, "label": {"type": "string"}, "case_status": {"enum": ["complete", "partial", "blocked", "outcome_unknown"]}, "primary_role_lens": {"$ref": "#/$defs/roleLens"},
        "secondary_role_lenses": {"type": "array", "items": {"$ref": "#/$defs/roleLens"}, "uniqueItems": true}, "period_bucket": {"type": "string"}, "root_task_locator": {"type": "string"}, "classification": {"$ref": "#/$defs/classification"}, "confidence": {"$ref": "#/$defs/confidence"}, "sensitivity": {"enum": ["low", "moderate", "high"]},
        "dimensions": {"type": "array", "items": {"$ref": "#/$defs/dimension"}, "uniqueItems": true}, "context_and_intent": {"type": "string"}, "workflow_sequence": {"type": "array", "items": {"$ref": "#/$defs/sequenceEvent"}}, "tool_and_agent_chain": {"type": "array", "items": {"type": "string"}},
        "context_management": {"type": "array", "items": {"type": "string"}}, "validation_and_feedback": {"type": "array", "items": {"type": "string"}}, "outcome_and_handoff": {"type": "array", "items": {"type": "string"}},
        "supporting_refs": {"type": "array", "items": {"type": "string"}}, "contradicting_refs": {"type": "array", "items": {"type": "string"}}, "interpretation": {"type": "string"}, "alternative_explanation": {"type": ["string", "null"]}, "locator_ledger": {"type": "array", "items": {"$ref": "#/$defs/locator"}}
      }
    },
    "pattern": {"type": "object", "required": ["id", "label", "classification", "dimensions", "role_lenses", "case_refs", "source_spread", "period_spread", "support_count", "eligible_count", "contradictions", "confidence", "claim", "reasoning", "alternative_explanation", "boundary_conditions", "assessment_use"], "properties": {"id": {"type": "string", "pattern": "^PAT-[0-9]{3}$"}, "label": {"type": "string"}, "classification": {"$ref": "#/$defs/classification"}, "dimensions": {"type": "array", "items": {"$ref": "#/$defs/dimension"}}, "role_lenses": {"type": "array", "items": {"$ref": "#/$defs/roleLens"}}, "case_refs": {"type": "array", "items": {"type": "string", "pattern": "^WF-[0-9]{3}$"}}, "source_spread": {"type": "array", "items": {"type": "string"}}, "period_spread": {"type": "array", "items": {"type": "string"}}, "support_count": {"type": "integer", "minimum": 0}, "eligible_count": {"type": "integer", "minimum": 0}, "contradictions": {"type": "array", "items": {"type": "string"}}, "confidence": {"$ref": "#/$defs/confidence"}, "claim": {"type": "string"}, "reasoning": {"type": ["string", "null"]}, "alternative_explanation": {"type": ["string", "null"]}, "boundary_conditions": {"type": "string"}, "assessment_use": {"type": "string"}}, "additionalProperties": false},
    "counterpattern": {"type": "object", "required": ["id", "label", "classification", "dimensions", "case_refs", "frequency_count", "eligible_count", "severity", "confidence", "behavior", "late_discovered_signal", "consequence_observed", "protective_behavior_present", "alternative_explanation", "safe_locators"], "properties": {"id": {"type": "string", "pattern": "^CTR-[0-9]{3}$"}, "label": {"type": "string"}, "classification": {"$ref": "#/$defs/classification"}, "dimensions": {"type": "array", "items": {"$ref": "#/$defs/dimension"}}, "case_refs": {"type": "array", "items": {"type": "string"}}, "frequency_count": {"type": "integer", "minimum": 0}, "eligible_count": {"type": "integer", "minimum": 0}, "severity": {"enum": ["low", "moderate", "high"]}, "confidence": {"$ref": "#/$defs/confidence"}, "behavior": {"type": "string"}, "late_discovered_signal": {"type": ["string", "null"]}, "consequence_observed": {"type": "string"}, "protective_behavior_present": {"type": ["string", "null"]}, "alternative_explanation": {"type": ["string", "null"]}, "safe_locators": {"type": "array", "items": {"type": "string"}}}, "additionalProperties": false},
    "route": {"type": "object", "required": ["id", "root_cases", "sequence", "why_it_fit", "integration_observed", "outcome_evidence", "caveat"], "properties": {"id": {"type": "string", "pattern": "^RTE-[0-9]{2}$"}, "root_cases": {"type": "array", "items": {"type": "string"}}, "sequence": {"type": "array", "items": {"type": "string"}}, "why_it_fit": {"type": "string"}, "integration_observed": {"type": "string"}, "outcome_evidence": {"type": "string"}, "caveat": {"type": ["string", "null"]}}, "additionalProperties": false},
    "roleSynthesis": {"type": "object", "required": ["lens", "basis", "case_refs", "relevant_outcomes", "relevant_validation", "not_applicable", "confidence"], "properties": {"lens": {"$ref": "#/$defs/roleLens"}, "basis": {"enum": ["requested", "observed", "inferred"]}, "case_refs": {"type": "array", "items": {"type": "string"}}, "relevant_outcomes": {"type": "array", "items": {"type": "string"}}, "relevant_validation": {"type": "array", "items": {"type": "string"}}, "not_applicable": {"type": "array", "items": {"type": "string"}}, "confidence": {"$ref": "#/$defs/confidence"}}, "additionalProperties": false},
    "dimensionEntry": {"type": "object", "required": ["dimension", "status", "supporting_refs", "counterevidence_refs", "role_lenses", "coverage_note", "max_confidence"], "properties": {"dimension": {"$ref": "#/$defs/dimension"}, "status": {"enum": ["evidence_available", "not_measurable", "not_applicable"]}, "supporting_refs": {"type": "array", "items": {"type": "string"}}, "counterevidence_refs": {"type": "array", "items": {"type": "string"}}, "role_lenses": {"type": "array", "items": {"$ref": "#/$defs/roleLens"}}, "coverage_note": {"type": "string"}, "max_confidence": {"$ref": "#/$defs/confidence"}}, "additionalProperties": false},
    "privacyOmission": {"type": "object", "required": ["class", "count", "effect"], "properties": {"class": {"type": "string"}, "count": {"type": "integer", "minimum": 0}, "effect": {"type": "string"}}, "additionalProperties": false},
    "reconciliationItem": {"type": "object", "required": ["claim", "refs", "confidence", "reason"], "properties": {"claim": {"type": "string"}, "refs": {"type": "array", "items": {"type": "string"}}, "confidence": {"$ref": "#/$defs/confidence"}, "reason": {"type": "string"}}, "additionalProperties": false},
    "recommendation": {"type": "object", "required": ["action", "why", "success_signal", "refs"], "properties": {"action": {"type": "string"}, "why": {"type": "string"}, "success_signal": {"type": "string"}, "refs": {"type": "array", "items": {"type": "string"}}}, "additionalProperties": false},
    "check": {"type": "object", "required": ["id", "status", "note"], "properties": {"id": {"type": "string"}, "status": {"enum": ["pass", "fail", "not_applicable"]}, "note": {"type": ["string", "null"]}}, "additionalProperties": false}
  }
}
```

### Regras determinísticas de renderização

1. Valide o JSON antes de escrever Markdown; falha de schema bloqueia a renderização.
2. Preserve a ordem dos 11 títulos deste contrato, independentemente da ordem das chaves no JSON.
3. Ordene `coverage.sources` por `source_id`; `cases`, `patterns`, `counterpatterns` e `routes` pelo sufixo numérico do ID; `role_lenses` pela ordem do enum; `dimension_index` na ordem fixa `framing`, `grounding`, `routing`, `context`, `validation`, `handoff`, `reuse`, `safety`.
4. Dentro de listas de refs, elimine duplicatas e ordene lexicograficamente. Não reordene `workflow_sequence`, `tool_and_agent_chain` nem `routes[].sequence`.
5. Renderize `null` como `—`, arrays vazios como `Nenhum observado` e booleans como `true`/`false`. Nunca invente texto para preencher ausência.
6. Formate ratios com duas casas e contagens como inteiros. Não calcule score de dimensão ou global.
7. Escape Markdown em todo texto livre. Renderize locators somente entre crases e nunca como links.
8. Para cada caso, produza as subseções na ordem do template. Para padrões e contrapadrões, preserve a ordem de campos mostrada neste contrato.
9. A seção 11 deve renderizar `pass` como `[x]`, `fail` como `[ ]` e `not_applicable` como `[n/a]`, seguida de `note` quando existente.
10. A mesma entrada JSON deve produzir bytes Markdown idênticos, exceto quando `generated_at` mudar na entrada. Use UTF-8, LF e exatamente uma newline final.

## 1. Metadata and privacy envelope

Preencha exatamente este bloco:

```yaml
contract: workflow-evidence
contract_version: "1.0"
generated_at: "2026-07-11T12:00:00-03:00"
assessment_period:
  from: "2026-01-01T00:00:00Z"
  to: "2026-07-01T00:00:00Z"
subject_label: "Pessoa avaliada"
requested_role_lens: []
inferred_role_lens: [leadership_operations, product_design]
sources_in_scope: [codex_local, claude_local]
source_analyses_used: [analysis-codex.json, analysis-claude.json]
raw_histories_reopened: false
raw_content_retained: false
sharing_default: private
sensitive_evidence_omitted: 3
locator_salt_scope: assessment_local
```

Regras:

- `subject_label` usa “Pessoa avaliada”, salvo nome fornecido explicitamente no pedido.
- `requested_role_lens` vence qualquer inferência; preserve ambas para transparência.
- Nomes de arquivos de análise podem aparecer, mas nunca paths pessoais completos.
- `locator_salt_scope` descreve o escopo do hash; nunca registre o salt.
- Se houve detecção de segredo, informe apenas a classe e a quantidade na seção 9, nunca o valor ou sua localização exata.

Em seguida, escreva um parágrafo curto chamado **Privacy envelope** declarando o que foi excluído e quais transformações foram aplicadas: paráfrase, generalização temporal, remoção de entidades, path redigido e hashing local.

## 2. Coverage and evidence map

Inclua uma linha por fonte, sem somar fontes não comparáveis:

| Source ID | Kind | Period | Eligible | Interpretable | Unit | Ratio | Dedup key | Retention caveat | Confidence ceiling |
|---|---|---|---:|---:|---|---:|---|---|---|
| codex_local | primary_history | 2026-01–2026-07 | 100 | 80 | root_session | 0.80 | root_session_id | janela parcial em um mês | high |
| codex_luna | model_subset | 2026-04–2026-07 | — | — | subset_event | — | parent root_session_id | incluído em codex_local | inherited |

Depois, inclua:

- **Evidence units used:** número de fluxos, observações e períodos representados.
- **Sampling rule:** como os casos foram escolhidos, incluindo busca por resultados, falhas tardias, lentes e períodos; evite amostra baseada apenas em volume ou recência.
- **Known blind spots:** fontes bloqueadas, retenção desigual, metadata-only, tarefas sem resultado persistido e conteúdo sensível omitido.
- **Comparability:** marque pares de fontes como `convergent`, `conflicting` ou `not_comparable`, com uma frase de razão.

`coverage_ratio = interpretable_units / eligible_units`. Quando o denominador for desconhecido, use `—`, explique o motivo e limite a confiança a `low`. Caches agregados, aliases, modelos e subagentes não aumentam o denominador da sessão-raiz.

## 3. Representative workflow cases

Esta é a seção central. Cada caso representa uma tarefa-raiz, não uma mensagem nem um subagente. Use o template completo:

```markdown
### WF-001 — Implementação com validação proporcional

- **Case status:** complete | partial | blocked | outcome_unknown
- **Primary role lens:** engineering
- **Secondary role lenses:** []
- **Period bucket:** 2026-Q2
- **Root task locator:** `codex_local/sess_h:8f2c…`
- **Classification:** observed
- **Confidence:** high
- **Sensitivity:** low
- **Dimensions:** framing, grounding, routing, validation, handoff

**Context and intent**

Paráfrase de 1–3 frases sobre o tipo de trabalho, objetivo operacional e restrições explícitas. Não nomear produto, cliente, pessoa ou repositório.

**Workflow sequence**

1. `[observed]` A tarefa declarou resultado esperado e fronteira de escopo. (`evt_h:0ab1…/i:3`)
2. `[observed]` O agente inspecionou a fonte de verdade local antes de propor mudança. (`evt_h:54d0…/i:7`)
3. `[observed]` Dois subagentes receberam partes independentes, vinculados à mesma tarefa-raiz. (`agent_h:91cc…/i:11-18`)
4. `[observed]` A síntese resolveu uma divergência entre os retornos. (`evt_h:778e…/i:23`)
5. `[observed]` O artefato foi validado por teste e inspeção da superfície final. (`evt_h:123a…/i:31`, `evt_h:a930…/i:35`)
6. `[observed]` O handoff separou feito, não verificado e próximo passo. (`evt_h:0ff2…/i:39`)

**Tool and agent chain**

`root agent -> local search -> file inspection -> 2 parallel subagents -> synthesis -> test -> runtime inspection -> handoff`

**Context management**

- Contexto mantido: contrato, fonte de verdade e critérios de aceite.
- Contexto evitado ou descartado: detalhe histórico sem relação com o objetivo.
- Mudança de fase: descoberta -> execução -> validação, marcada explicitamente ou observável na sequência.

**Validation and feedback**

- Método: teste automatizado + inspeção do artefato executável.
- Proporcionalidade: adequada ao risco da tarefa.
- Feedback loop: uma falha intermediária mudou a implementação antes do fechamento.
- Limite: não há evidência de observação pós-entrega.

**Outcome and handoff**

- Resultado observado: artefato local atualizado e superfície final exercitada.
- Estado: complete.
- Handoff: caminho abstrato, verificações realizadas e ressalva remanescente.
- Resultado causal ou impacto de negócio: not_measurable.

**Evidence and counterevidence**

- Suporta: `obs-014`, `obs-019`, `obs-021`.
- Contradiz: `obs-020` — o primeiro fechamento ocorreu antes da inspeção final.
- Interpretação: o fluxo possui correção iterativa, mas o gate de inspeção ainda depende de lembrança.
- Alternativa plausível: a inspeção pode ter ocorrido fora da fonte retida.

**Safe locator ledger**

| Ref | Source | Locator | Event type | Timestamp bucket | Sanitization |
|---|---|---|---|---|---|
| obs-014 | codex_local | `sess_h:8f2c…/evt_h:54d0…/i:7` | tool_call | 2026-05 | hash + month bucket |
```

### Cobertura mínima dos casos

Inclua, quando o corpus permitir:

- no mínimo 6 casos representativos;
- casos distribuídos por pelo menos 2 tarefas e 2 períodos para sustentar recorrência;
- ao menos 1 caso completo, 1 caso parcial ou bloqueado e 1 caso com falha descoberta tarde;
- ao menos 1 fluxo com validação forte e 1 com validação ausente ou insuficiente;
- ao menos 1 fluxo de cada lente recorrente no corpus;
- ao menos 2 fontes primárias quando duas ou mais estiverem disponíveis;
- ao menos 1 caso que mostre síntese após delegação, se subagentes forem usados no corpus;
- ao menos 1 caso sem subagentes, para evitar confundir delegação com maturidade.

Se houver menos de 6 tarefas interpretáveis, inclua todas as elegíveis e marque `insufficient_case_coverage`. Não fragmente uma tarefa para alcançar o mínimo. Um caso isolado pode ilustrar uma prática, mas nunca sustenta um hábito.

### Exemplos seguros de fluxos por lente

Os exemplos abaixo mostram granularidade e linguagem esperadas. São modelos parafraseados, não fatos sobre a pessoa.

**Engineering — diagnóstico antes de correção**

`pedido de diagnosticar -> inspeção de logs sanitizados -> hipótese -> reprodução -> causa confirmada -> explicação -> nenhuma mutação`

Boa leitura: o agente respeitou a autoridade limitada a diagnóstico e confirmou a causa em runtime. Contraexemplo relevante: abriu uma mudança não autorizada mesmo com causa ainda incerta.

**Product design — forma da experiência antes do plano final**

`brief abstrato -> inspeção do produto atual -> alternativas -> protótipo -> feedback -> decisão -> especificação com critérios`

Boa leitura: a pessoa reduziu incerteza de UX antes de comprometer implementação. Limite: feedback de stakeholder não prova adoção por usuário.

**Leadership/operations — decisão rastreável**

`fontes internas autorizadas -> síntese -> conflito explicitado -> decisão -> owner e prazo -> confirmação -> follow-up`

Boa leitura: o handoff transformou informação em responsabilidade verificável. Contraexemplo: resumo elegante sem owner, confirmação ou acompanhamento.

**Research/content — fontes e revisão**

`pergunta -> fontes primárias -> notas de proveniência -> síntese -> revisão factual -> adaptação ao público -> publicação autorizada`

Boa leitura: afirmações centrais são rastreáveis e a revisão é proporcional. Contraexemplo: muitas fontes secundárias sem relação entre evidência e conclusão.

**Mixed — mudança de lente explícita**

`descoberta de produto -> decisão -> implementação -> validação executável -> comunicação operacional`

Boa leitura: cada fase usa seus próprios critérios de resultado. Evite aplicar “tests passed” como única validação da decisão de produto ou “stakeholder gostou” como validação técnica.

**Unknown — prática universal**

`objetivo -> fonte de verdade -> execução autorizada -> checagem do resultado -> limites -> próximo passo`

Boa leitura: avalie framing, grounding, autoridade e fechamento sem assumir profissão.

## 4. Recurring patterns

Um padrão é uma síntese sustentada por múltiplos casos. Use o template:

```markdown
### PAT-001 — Validação combina mecanismo e superfície final

- **Classification:** observed | inferred | not_measurable
- **Dimensions:** validation, handoff
- **Role lenses:** engineering, product_design
- **Case refs:** WF-001, WF-004, WF-006
- **Source spread:** codex_local, claude_local
- **Period spread:** 2026-Q1, 2026-Q2
- **Support:** 3 of 5 eligible cases
- **Contradictions:** WF-003, WF-005
- **Confidence:** medium
- **Claim:** paráfrase curta do comportamento recorrente.
- **Reasoning:** obrigatório se `inferred`; conecte pelo menos duas observações.
- **Alternative explanation:** obrigatório se `inferred`.
- **Boundary conditions:** quando o padrão aparece ou quebra.
- **Assessment use:** dimensão ou recomendação que pode sustentar.
```

Para afirmar padrão recorrente, exija ao menos 3 eventos interpretáveis, em 2 tarefas e 2 períodos. Informe sempre o denominador elegível. Um padrão não recebe confiança `high` apenas por aparecer muitas vezes em uma única sessão ou ferramenta.

Padrões úteis incluem:

- contrato explícito antes da execução em tarefas ambíguas;
- inspeção da fonte de verdade antes de abstração;
- paralelização apenas de partes independentes e síntese posterior;
- separação clara entre descoberta, decisão, execução e review;
- validação proporcional ao risco e à lente da tarefa;
- fechamento com `feito`, `bloqueado`, `não verificado` e próximo passo;
- aprendizado de falhas convertido em regra, template, skill ou automação;
- pedido de aprovação antes de mutação sensível.

Não registre como padrão de maturidade: “usa muitos agentes”, “consome poucos tokens”, “faz muitas tool calls”, “tem chats longos”, “gera muitos arquivos” ou “termina rápido”.

## 5. Counterpatterns and late failures

Contraexemplos não são resíduos: ajudam a calibrar confiança, prioridade e condição de quebra. Use:

```markdown
### CTR-001 — Fechamento declarado antes da validação da superfície

- **Classification:** observed
- **Dimensions:** validation, handoff
- **Case refs:** WF-003, WF-005
- **Frequency:** 2 of 5 eligible cases
- **Severity:** low | moderate | high
- **Confidence:** medium
- **Behavior:** o estado foi tratado como concluído antes da checagem relevante.
- **Late-discovered signal:** erro apareceu após teste parcial ou no retorno do usuário.
- **Consequence observed:** retrabalho local; impacto externo not_measurable.
- **Protective behavior present:** o fluxo foi reaberto e a ressalva corrigida.
- **Alternative explanation:** parte da validação pode não estar retida.
- **Safe locators:** `sess_h:…/evt_h:…`.
```

Procure especialmente:

- conclusão baseada só em runner, sem abrir a superfície pedida;
- decisão baseada em memória quando uma fonte viva estava disponível;
- delegação sem contrato de saída ou sem síntese;
- contexto longo reutilizado após mudança material de objetivo;
- artefato criado, mas não encontrado, aberto ou validado;
- recomendação sem sinal de sucesso ou owner quando a lente exige;
- mutação feita durante um pedido apenas de review ou diagnóstico;
- erro tardio que revela ausência de gate previsível;
- handoff que mistura confirmado, inferido e desconhecido.

Um contraexemplo isolado não define um hábito negativo. Registre escopo, frequência e comportamento protetor. Não atribua intenção, negligência, capacidade ou performance.

## 6. Tool, agent, and model routing map

Mapeie função e sequência, não popularidade:

| Route ID | Root cases | Sequence | Why it fit | Integration observed | Outcome evidence | Caveat |
|---|---|---|---|---|---|---|
| RTE-01 | WF-001, WF-004 | search -> inspect -> agent pair -> synthesize -> validate | subtarefas independentes | divergência resolvida no agente-raiz | artefato + inspeção | agentes não são unidades adicionais |
| RTE-02 | WF-002 | browser -> computer fallback -> handoff | validação de superfície | não aplicável | fluxo exercitado | retenção parcial |

### Deduplicação obrigatória

- A unidade principal é `root_session_id` ou equivalente estável.
- Subagentes herdam `parent_root_session_id`; seus eventos entram na sequência do caso-pai.
- Um subagente não é uma tarefa adicional, mesmo se possuir transcript próprio.
- Aliases, perfis e variantes de modelo são atributos ou subconjuntos da fonte hospedeira.
- Um `model_subset` exige `parent_source_id` e a mesma chave de deduplicação do pai.
- Eventos espelhados em cache e histórico primário são contados uma vez, preferindo a fonte semântica primária.
- Retentativas idênticas de tool call contam como uma tentativa operacional com número de retries; resultados materialmente diferentes podem ser eventos distintos.
- Mesma tarefa continuada em thread, worktree ou handoff só vira novo caso se houver novo contrato de resultado. Caso contrário, mantenha um caso com segmentos.
- Não some janelas sobrepostas nem compare modelos que tenham retenção ou granularidade diferentes sem ressalva.

O mapa pode descrever que um modelo ou agente foi usado, mas nunca concluir que ele é “melhor” por contagem, velocidade, custo ou tamanho do resultado. Avalie apenas a adequação observável do roteamento e a qualidade da integração.

## 7. Role-lens synthesis

Use uma subseção por lente presente:

```markdown
### engineering

- **Basis:** requested | observed | inferred
- **Case refs:** WF-001, WF-003
- **Relevant outcomes:** mudança executável; diagnóstico confirmado.
- **Relevant validation:** testes proporcionais; runtime; observabilidade.
- **What is not applicable:** validação com usuário quando não pertence ao caso.
- **Confidence:** medium
```

Lentes válidas: `engineering`, `product_design`, `leadership_operations`, `research_content`, `mixed`, `unknown`. Não derive cargo ou senioridade. Para `mixed`, declare qual lente rege cada caso. Se a lente vier do pedido, marque `requested`; se houver evidência explícita no corpus, `observed`; se for interpretação, `inferred`, com confiança máxima `medium` salvo triangulação independente.

## 8. Dimension evidence index

Inclua exatamente as oito dimensões e seus vínculos, sem pontuar no dossiê:

| Dimension | Status | Supporting cases/patterns | Counterevidence | Role lens | Coverage note | Max confidence |
|---|---|---|---|---|---|---|
| framing | evidence_available | WF-001; PAT-002 | CTR-003 | mixed | 4/6 casos elegíveis | medium |
| grounding | not_measurable | — | — | unknown | fonte semântica insuficiente | insufficient |
| routing | evidence_available | WF-001; PAT-004 | CTR-002 | engineering | subagentes deduplicados | medium |
| context | evidence_available | ... | ... | ... | ... | ... |
| validation | evidence_available | ... | ... | ... | ... | ... |
| handoff | evidence_available | ... | ... | ... | ... | ... |
| reuse | not_applicable | — | — | ... | corpus não contém tarefa de sistematização aplicável | insufficient |
| safety | evidence_available | ... | ... | ... | ... | ... |

Valores de `Status`: `evidence_available`, `not_measurable` ou `not_applicable`. Esta seção prepara a pontuação conforme `rubric.md`, mas não a antecipa. O reconciliador ainda deve confirmar o mínimo de 3 eventos em 2 tarefas e, para hábito longitudinal, 2 períodos.

## 9. Not measurable, omitted, and conflicting evidence

Divida em três listas:

### Not measurable

Declare perguntas que o corpus não responde, por exemplo impacto causal no negócio, qualidade percebida por usuário, adoção posterior, trabalho ocorrido fora das ferramentas ou conclusão de tarefas sem artefato retido.

### Omitted for privacy

Informe apenas classe, quantidade e efeito analítico:

- `high_sensitivity_content: 3` — contabilizado na cobertura, excluído dos exemplos; reduz confiança qualitativa.
- `secret_detected: true; class: credential_like` — valor e locator omitidos.
- `third_party_identity: 5` — entidades removidas sem avaliar terceiros.

### Conflicts and source limits

Registre divergências como `convergent`, `conflicting` ou `not_comparable`. Explique se a diferença pode resultar de retenção, granularidade, janela temporal ou fonte metadata-only. Divergência inexplicada reduz a confiança em um nível.

## 10. Reconciliation notes for the next agent

Esta seção orienta, mas não decide o assessment final. Inclua:

- candidate findings prontos para promover, com refs de casos e padrões;
- candidate findings que devem ser rejeitados por cobertura insuficiente;
- claims `inferred` com raciocínio, alternativa e confiança máxima permitida;
- contradições que precisam aparecer na mesma dimensão;
- limites que impedem comparação entre ferramentas ou períodos;
- quais recomendações têm risco comprovado e sinal de sucesso observável;
- quais evidências não podem ser exibidas no HTML apesar de contarem para cobertura;
- checagem explícita de que nenhuma contagem de subagente/modelo foi somada à sessão-raiz.

Finalize a seção com uma subseção `### Questions for the reviewing agent` cobrindo: suporte e contradição das conclusões do HTML, mínimos de recorrência, classificação das claims, proporcionalidade da validação, deduplicação, sinais de sucesso e conclusões fortes demais para a cobertura.

Exemplo:

```markdown
- **Promote with medium confidence:** validação proporcional aparece em WF-001, WF-004 e WF-006, mas CTR-001 mostra quebra em tarefas de interface.
- **Reject as habit:** reaproveitamento em template aparece apenas em WF-005; usar como estudo de caso, não como padrão.
- **Do not compare:** Claude retém detalhe semântico por 30 dias; Codex cobre 6 meses. As taxas não possuem denominadores equivalentes.
- **Recommendation candidate:** adicionar gate de inspeção da superfície antes do handoff. Sinal: 100% dos casos elegíveis registram método e resultado da inspeção.
```

## 11. Validation checklist

O agente que gera o dossiê deve marcar cada item como `[x]`, `[ ]` ou `[n/a]` e explicar qualquer item não concluído.

### Estrutura e rastreabilidade

- [ ] Os 11 títulos obrigatórios existem e estão na ordem definida.
- [ ] Cada caso tem ID único, tarefa-raiz, lente, classificação, confiança e status.
- [ ] Cada caso contém contexto, sequência, cadeia de tools/agentes, contexto/fases, validação, resultado/handoff, contraevidência e ledger.
- [ ] Todas as refs usadas em padrões, contrapadrões e índice apontam para IDs existentes.
- [ ] Datas usam ISO 8601 ou buckets mensais/trimestrais quando necessário à privacidade.
- [ ] Locators permitem checagem local de identidade/posição sem conter conteúdo bruto.

### Cobertura e raciocínio

- [ ] Há 6 casos ou todos os casos elegíveis quando o corpus é menor.
- [ ] Casos cobrem mais de um período e fonte quando disponíveis.
- [ ] Há resultado completo, caso parcial/bloqueado e falha tardia quando existentes.
- [ ] Há evidência favorável e contraditória no mesmo padrão/dimensão.
- [ ] Todo padrão longitudinal cumpre 3 eventos, 2 tarefas e 2 períodos.
- [ ] Toda claim informa denominador elegível e regra de seleção.
- [ ] Toda inferência tem ao menos 2 evidências, raciocínio, alternativa plausível e confiança compatível.
- [ ] `not_measurable` e `not_applicable` não foram convertidos em deficiência.
- [ ] A lente foi aplicada por tarefa, sem inferir cargo, senioridade ou produtividade.

### Deduplicação

- [ ] A unidade é sessão/tarefa-raiz, não mensagem, subagente ou modelo.
- [ ] Subagentes estão vinculados ao pai e não aumentam o total de tarefas.
- [ ] Modelos, aliases e perfis são subconjuntos da ferramenta hospedeira.
- [ ] Caches e históricos primários sobrepostos foram deduplicados.
- [ ] Retentativas e continuações foram tratadas conforme as regras deste contrato.
- [ ] Comparações com janelas ou granularidades distintas têm ressalva explícita.

### Privacidade e segurança

- [ ] Nenhum prompt, resposta, mensagem, documento ou código extenso foi copiado.
- [ ] Não há segredo, valor de configuração, cookie, credential, header ou URL assinada.
- [ ] Não há nomes, e-mails, handles, IDs externos, paths pessoais ou falas identificáveis.
- [ ] Projetos, empresas, clientes e terceiros foram generalizados.
- [ ] Conteúdo médico, financeiro, jurídico, RH e outros dados sensíveis foi omitido ou abstrato.
- [ ] Locators são hash/redigidos, com salt não persistido e escopo local.
- [ ] Uma busca final por padrões de segredo e PII não encontrou material reproduzível.
- [ ] O dossiê não contém ranking, profiling ou alegações sobre performance, intenção ou personalidade.
- [ ] O arquivo está em diretório isolado, com acesso restrito e retenção declarada.

### Compatibilidade com o assessment

- [ ] Dimensões e lentes usam apenas enums de `rubric.md`.
- [ ] Classificações e confiança seguem `analysis-contract.md`.
- [ ] Coverage ratio, denominadores e confidence ceiling estão consistentes com os JSONs de fonte.
- [ ] Claims contraditórias reduzem confiança quando não resolvidas.
- [ ] O dossiê não contém pontuação antecipada nem nova fonte não autorizada.
- [ ] As notas de reconciliação distinguem claramente promover, rejeitar e não comparar.

## Formato dos locators

Use um dos formatos abaixo:

```text
<source_id>/sess_h:<hash_curto>/evt_h:<hash_curto>/i:<índice>
<source_id>/sess_h:<hash_curto>/agent_h:<hash_curto>/i:<início>-<fim>
<source_id>/artifact_h:<hash_curto>/section:<rótulo_genérico>
```

Requisitos:

- Use HMAC ou hash com salt aleatório específico do assessment quando o gerador suportar; não persista o salt no dossiê.
- Mostre somente 8–12 caracteres hexadecimais e reticências.
- Hashes servem para igualdade local, não para recuperação do texto.
- `source_id` deve existir no JSON da fonte.
- `i` é índice interno sanitizado ou ordinal estável, não linha contendo conteúdo sensível.
- Para paths, use apenas família redigida, como `~/.codex/sessions/<redacted>`, se imprescindível à cobertura; não use path no locator de caso.
- Para datas sensíveis, prefira bucket mensal ou trimestral. Timestamp exato só entra quando já é seguro e necessário para deduplicação.
- Se até o locator for reidentificável, use `locator_omitted: privacy` e explique o efeito na confiança.

Exemplos válidos:

- `codex_local/sess_h:8f2c091a…/evt_h:54d011b7…/i:7`
- `claude_local/sess_h:31a92cc0…/agent_h:7ca551e2…/i:11-18`
- `cursor_meta/artifact_h:990df812…/section:validation`

Exemplos proibidos:

- `/Users/nome/cliente-secreto/projeto/sessao.jsonl:184`
- `https://internal.example/task/12345`
- `session: implementar pagamento para Empresa X`
- hash sem salt de e-mail, telefone, username, nome de projeto ou qualquer string de baixo espaço de busca.

## Classificação e confiança

### `observed`

Use quando o comportamento está diretamente visível em mensagem redigida, tool call, configuração autorizada, artefato ou resultado. Descreva apenas o que ocorreu. “Executou teste e recebeu resultado de sucesso” pode ser observado; “garantiu qualidade” não.

### `inferred`

Use para interpretação apoiada por pelo menos duas observações. Inclua:

- cadeia de raciocínio explícita;
- no mínimo 2 refs de evidência;
- alternativa plausível;
- limite de cobertura;
- confiança máxima `medium`, salvo triangulação direta de fontes independentes.

Exemplo: “A pessoa parece usar subagentes para reduzir espera em partes independentes” é inferência. Evidência: contratos distintos, execução paralela e síntese posterior em mais de um caso. Alternativa: o paralelismo pode ter sido sugerido automaticamente pelo agente.

### `not_measurable`

Use quando o corpus não permite responder. Não formule uma conclusão negativa. Exemplo: “Impacto causal no tempo de entrega: not_measurable; não há baseline comparável nem observação pós-entrega.”

### Confiança

- `high`: fonte semântica primária, cobertura >=70%, exemplos em >=3 períodos ou >=10 tarefas, pouca contradição inexplicada.
- `medium`: cobertura de 30–69% ou 4–9 tarefas, fontes parcialmente agregadas, padrão ainda sustentado por observação direta.
- `low`: cobertura <30%, <=3 tarefas, janela curta, retenção desigual ou dependência relevante de inferência.
- `insufficient`: denominador ou evidência interpretável ausente.

A confiança de um caso pode superar a de um padrão apenas quando o caso é diretamente observado. A confiança reconciliada nunca supera o teto da fonte que sustenta a conclusão. Contradição inexplicada reduz um nível.

## Padrões de redação segura

Use:

- “Em 3 de 5 tarefas elegíveis, o objetivo e o critério de conclusão apareceram antes da execução.”
- “Dois agentes trataram partes independentes e o agente-raiz reconciliou uma divergência.”
- “A validação combinou teste automatizado e inspeção da superfície final.”
- “O handoff separou concluído, bloqueado e não verificado.”
- “Um caso terminou sem evidência retida de confirmação; o resultado é `outcome_unknown`.”

Evite:

- “A pessoa é muito produtiva porque usa muitos agentes.”
- “O modelo X é superior porque terminou mais rápido.”
- “O usuário sempre valida tudo” com um único exemplo.
- “A tarefa foi um sucesso” quando há apenas completion event.
- “O agente ficou confuso” ou outra atribuição mental não observável.
- qualquer fragmento reconhecível de prompt, mensagem, código, nome, path ou cliente.

## Critério de aceite

O dossiê está pronto somente quando outro agente consegue, usando apenas este Markdown e os JSONs sanitizados de análise, responder:

1. Quais fluxos completos sustentam cada candidate finding?
2. Em que contexto, lente e fase o comportamento apareceu?
3. Qual foi a cadeia de ferramentas/agentes e como os resultados foram integrados?
4. Qual validação ocorreu, qual resultado foi observado e o que permaneceu desconhecido?
5. Quais contraexemplos ou falhas tardias calibram a conclusão?
6. A recorrência cumpre os mínimos de tarefas, eventos e períodos?
7. Subagentes, modelos e caches foram deduplicados corretamente?
8. A conclusão é observada, inferida ou não mensurável, com confiança compatível?
9. Os locators permitem checagem local sem expor conteúdo ou identidade?
10. O material pode ser convertido em assessment sem introduzir PII, segredo, código proprietário, ranking ou profiling?

Se qualquer resposta depender de reabrir histórico bruto, o dossiê falhou em suficiência ou sanitização. Refaça a síntese a partir das entradas redigidas autorizadas; não amplie o acesso.
