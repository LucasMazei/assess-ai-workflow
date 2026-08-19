# Diagnóstico de Uso de IA

Assessment individual e privado de como cada dev usa ferramentas de IA (OpenCode, Codex, Claude Code, Cursor, subagents, skills, MCPs...). Roda **100% local** na sua máquina e gera dois artefatos que você entrega no final.

> **Isto não é ranking, nota de performance ou vigilância.** O objetivo é mapear boas práticas e contrapadrões do time pra escalar o uso de IA com mais qualidade. Sem comparação individual, sem histórico bruto centralizado.

---

## O que é

`assess-ai-workflow` é uma skill de agente de IA que:

- Audita, **em modo somente-leitura**, o histórico local das suas ferramentas de IA.
- Gera dois **HTMLs executivos**: `assessment-personal.html` (privado) e `assessment-shareable.html` (compartilhável), ambos legíveis offline.
- Gera um **Markdown de evidências** (`workflow-evidence.md`) — sanitizado, para revisão por outro agente ou revisor técnico.

A análise é local: não acessa credenciais, cookies ou senhas, não faz upload, e os exemplos são parafraseados/redigidos. Detalhes em [`skill/assess-ai-workflow/references/privacy.md`](skill/assess-ai-workflow/references/privacy.md).

---

## Não precisa de Codex

O scanner lê o histórico local de **OpenCode, Codex, Claude Code e Cursor** — **independente de qual agente você usa pra rodar a skill**. Se você usa Cursor mas roda pelo OpenCode, ela ainda audita seu histórico do Cursor.

A ferramenta que **roda** a skill não precisa ser a que você usa no dia a dia. Ela só precisa: executar `python3`, ler arquivos e escrever os artefatos. Escolha o caminho da ferramenta que você já tem.

> **Requisito comum:** `python3` no PATH. Nada além disso pra instalar.

---

## Como rodar

### Opção A — Claude Code (recomendado, mais simples)

Skill nativa. Clone o repositório e copie a skill:

```bash
git clone <repository-url> assess-ai-workflow
mkdir -p ~/.claude/skills
cp -r assess-ai-workflow/skill/assess-ai-workflow ~/.claude/skills/
```

Isso cria `~/.claude/skills/assess-ai-workflow/`.

> ⚠️ **Abrir o Claude Code na pasta deste repo NÃO instala a skill.** A cópia em `skill/` é só pra distribuir. A skill precisa estar em `~/.claude/skills/` (comando acima) e o Claude Code lê as skills **no boot** — então **reinicie a sessão** depois de instalar.

Abra o Claude Code na sua máquina e peça:

> **Rode a skill `assess-ai-workflow` pra auditar meu histórico local de uso de IA e gerar meu assessment (HTML + workflow-evidence.md).**

### Opção B — Cursor

Cursor não tem sistema de skills, mas o **Agent** lê arquivos e roda comandos no terminal.

1. Clone este repo (ou baixe a pasta [`skill/`](skill/)).
2. Abra a pasta no Cursor.
3. No **modo Agent** (não "Ask"), envie:

   > **Leia `skill/assess-ai-workflow/SKILL.md` e execute o fluxo completo de ponta a ponta, gerando o HTML e o `workflow-evidence.md`. Rode os scripts python quando o SKILL.md mandar.**

4. Aprove as execuções de terminal (`python3`) quando o Cursor pedir.

> Cursor não tem subagents — o SKILL.md já prevê rodar as análises em sequência nesse caso. Só fica um pouco mais lento.

### Opção C — Codex

1. Clone o repo e copie a skill:

   ```bash
    git clone <repository-url> assess-ai-workflow
   mkdir -p ~/.codex/skills
   cp -r assess-ai-workflow/skill/assess-ai-workflow ~/.codex/skills/
   ```
2. No Codex, envie:

    > **Use `$assess-ai-workflow` para revisar todo meu histórico local de uso de IA e gerar meu assessment.**

### Opção D — OpenCode

Adicione a pasta `skill/` às paths de skills no `~/.config/opencode/opencode.json`:

```json
{
  "skills": {
    "paths": ["~/Documents/Programming/assess-ai-workflow-main/skill"]
  }
}
```

Reinicie o OpenCode e peça:

> **Use a skill `assess-ai-workflow` para auditar meu histórico local de IA e gerar meu assessment.**

---

## Conferir

- Abra o **HTML** no navegador (funciona offline) e confira se faz sentido.
- Há exemplos genéricos completos: [`assessment compartilhável`](examples/sample-assessment-shareable.html), [`assessment pessoal`](examples/sample-assessment-personal.html) e [`dossiê privado`](examples/sample-workflow-evidence.md).
- Por padrão a skill grava em `~/Documents/AI Workflow Assessments/YYYY-MM-DD-assessment/`.
- O `workflow-evidence.md` é técnico e sanitizado — não precisa ler linha a linha, mas dá uma passada pra garantir que nada sensível vazou.

---

## Compartilhamento

Compartilhe os artefatos conforme o acordo de privacidade do seu time.

- Se algo bloquear (ferramenta sem histórico, script quebrando, etc.), registre o bloqueio explícito e avise — falta de evidência **não** vira punição.

---

## Suporte

Fale com a pessoa responsável pela iniciativa ou com o revisor técnico.
