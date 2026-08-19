# Rubrica de maturidade do workflow com IA

Use esta rubrica para avaliar **como a pessoa trabalha com IA**, não sua capacidade técnica, produtividade ou senioridade. Primeiro identifique o papel predominante a partir de evidência explícita; se não houver, use `unknown` e mantenha a leitura universal.

## Lente de papel

Escolha uma ou mais lentes sem mudar as dimensões:

- `engineering`: implementação, diagnóstico, testes, review e operação de software.
- `product_design`: descoberta, framing, decisão, especificação, protótipo e validação com usuários.
- `leadership_operations`: delegação, síntese, decisão, comunicação, governança e acompanhamento.
- `research_content`: qualidade de fontes, síntese, criação, revisão e publicação.
- `mixed`: trabalho recorrente em mais de uma lente.
- `unknown`: papel não comprovado no corpus.

As lentes mudam os exemplos de boa evidência, não o padrão de exigência. Para uma pessoa não desenvolvedora, ausência de commits ou testes de código é `not_applicable`, nunca deficiência. Não infira cargo, nível, remuneração, produtividade, inteligência ou senioridade de engenharia.

| Lente | Resultado e validação relevantes |
|---|---|
| `engineering` | mudança executável; testes, review, runtime e observabilidade proporcionais ao risco |
| `product_design` | decisão ou experiência verificável; pesquisa, protótipo, critérios e feedback de usuário/stakeholder |
| `leadership_operations` | decisão, alinhamento ou processo; fonte cruzada, owner, prazo, confirmação e acompanhamento |
| `research_content` | síntese ou publicação; qualidade de fontes, atribuição, revisão factual/editorial e adequação ao público |
| `mixed` | aplicar a lente da tarefa a cada caso antes de reconciliar o padrão |
| `unknown` | avaliar apenas práticas universais e evitar exemplos específicos de profissão |

## Dimensões

1. **Framing e contrato de trabalho** — explicita objetivo, contexto, restrições, fora de escopo, formato de saída, autoridade e critério de conclusão.
2. **Grounding e proveniência** — aponta fontes de verdade, separa fonte primária de memória e preserva a origem das conclusões.
3. **Decomposição e roteamento** — escolhe fluxo, ferramenta, skill, agente ou subagente conforme a incerteza; divide trabalho em partes coerentes e integra os resultados.
4. **Gestão de contexto e fases** — evita contexto irrelevante, registra checkpoints, abre contexto fresco quando o contrato muda e distingue descoberta, decisão, execução e review.
5. **Validação e feedback** — pede evidência proporcional ao risco: testes, inspeção do artefato, browser, fonte cruzada, revisão humana ou checklist adequado ao papel.
6. **Artefatos, decisão e handoff** — produz saídas reutilizáveis, distingue hipótese de decisão, registra feito/bloqueado/não verificado e deixa próximo passo claro.
7. **Reuso e melhoria do sistema** — transforma padrões recorrentes em templates, skills, documentação, automações ou regras; revisa o processo com base em falhas reais.
8. **Segurança, privacidade e autoridade** — limita acesso e mutações, protege segredos e dados pessoais, pede aprovação para ações sensíveis e respeita fronteiras de escopo.

## Âncoras de pontuação

Pontue cada dimensão de `1.0` a `5.0`, em incrementos de `0.5`, apenas quando houver cobertura suficiente.

| Nota | Âncora comportamental |
|---|---|
| 1 | Ausente ou comportamento recorrente aumenta risco; a evidência mostra dependência de improviso. |
| 2 | Ocorre ocasionalmente, de forma reativa ou inconsistente; falhas previsíveis não têm proteção. |
| 3 | Prática funcional e repetida em trabalhos comuns, mas quebra em casos longos, ambíguos ou de maior risco. |
| 4 | Prática explícita, consistente e adequada ao risco; exceções são localizadas e reconhecidas. |
| 5 | Sistema deliberado, reutilizável e adaptativo; mede resultados, aprende com falhas e ensina o padrão a outras pessoas. |

Não force uma nota. Use `not_measurable` quando faltarem exemplos interpretáveis e `not_applicable` quando a dimensão não se aplicar à lente ou ao trabalho observado. A nota global é a média simples das dimensões mensuráveis, arredondada para uma casa decimal, somente se pelo menos 5 das 8 dimensões forem mensuráveis. Não publique nota global caso contrário.

## Regras de evidência

Cada conclusão deve ser rotulada:

- `observed`: comportamento diretamente visível em mensagem, tool call, configuração, artefato ou resultado.
- `inferred`: interpretação razoável baseada em pelo menos duas observações; declarar a cadeia de raciocínio e alternativa plausível.
- `not_measurable`: o histórico local não contém evidência suficiente para responder.

Para pontuar uma dimensão, exija no mínimo 3 eventos interpretáveis distribuídos em 2 tarefas e, para afirmar hábito longitudinal, em 2 períodos distintos. Um único caso pode virar estudo de caso, nunca hábito. Evidência contraditória deve aparecer na mesma dimensão e reduzir a confiança.

## Confiança e cobertura

- `high`: fontes semânticas primárias disponíveis; >=70% do corpus elegível no período; exemplos em >=3 períodos ou >=10 tarefas; pouca contradição não explicada.
- `medium`: 30–69% do corpus, ou 4–9 tarefas, ou fontes parcialmente agregadas; padrão ainda sustentado por exemplos diretos.
- `low`: <30% do corpus, <=3 tarefas, janela curta, fonte truncada/migrada ou inferência forte. Não usar para comparação nem recomendação de alta consequência.
- `insufficient`: denominador ou evidência interpretável ausente; não pontuar.

Registre cobertura separadamente por ferramenta e período. Subagentes, modelos ou aliases que pertencem a uma sessão-pai são subconjuntos: não some suas contagens ao total como histórias independentes. Não compare ferramentas com janelas ou retenções diferentes sem ressalva explícita.

## Proibições de interpretação

Nunca use isoladamente como sinal de qualidade, maturidade ou produtividade:

- tokens consumidos ou custo;
- número de agentes/subagentes;
- duração ou número de mensagens do chat;
- número de tool calls, skills, commits, testes ou arquivos;
- velocidade, volume de código ou frequência de uso.

Essas métricas só podem descrever o corpus ou apoiar uma hipótese ligada a resultado verificável, por exemplo: contexto excessivo **e** falha por limite. Não crie ranking entre pessoas, equipes, modelos ou ferramentas. Não converta esta rubrica em avaliação de performance, perfil psicológico ou senioridade de engenharia.

## Saída por dimensão

Para cada dimensão, entregue: `status`, `score` se mensurável, `confidence`, `role_lens`, 2–4 evidências resumidas, contraevidência, interpretação, limitação e uma ação concreta. Recomendações devem partir do maior risco ou gargalo comprovado, não da menor nota automaticamente.
