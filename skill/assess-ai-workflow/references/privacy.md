# Privacidade e segurança

O assessment é uma auditoria local e privada por padrão. O histórico pode conter segredos, dados pessoais, informações médicas, financeiras, jurídicas, comerciais e de terceiros. A capacidade de ler um arquivo não implica autorização para reproduzi-lo, enviá-lo ou compartilhá-lo.

## Regras obrigatórias

1. **Consentimento e escopo:** analisar somente contas, perfis, diretórios e períodos pertencentes à pessoa e colocados em escopo. Não contornar permissões, criptografia, login ou controles do sistema.
2. **Somente leitura:** não editar históricos, configurações, repositórios, mensagens ou caches. Criar apenas os artefatos de saída previamente autorizados.
3. **Processamento local:** não enviar conteúdo bruto a serviços externos, web search, telemetria, repositórios ou conectores. Não instalar software nem habilitar sync sem aprovação explícita.
4. **Minimização:** extrair apenas metadados e trechos semânticos necessários. Preferir contagens, paráfrases e identificadores hash/redigidos. Não copiar prompts ou respostas integrais.
5. **Segredos:** nunca colocar em logs ou relatórios tokens, chaves, cookies, senhas, credenciais, variáveis de ambiente, headers, URLs assinadas ou conteúdo de arquivos secretos. Se detectados, registrar somente `secret_detected: true` e a classe, sem valor.
6. **Dados sensíveis:** omitir conteúdo médico, financeiro, jurídico, RH, avaliação de desempenho, documentos de identidade, endereço, telefone, e-mail pessoal e informações confidenciais de clientes. Use apenas uma paráfrase abstrata se indispensável à conclusão.
7. **Terceiros:** remover nomes, handles, e-mails, IDs e falas identificáveis de colegas, clientes e familiares. Não avaliar terceiros incidentais no histórico.
8. **Saída privada:** gravar com permissão restrita quando suportado; não publicar, abrir PR, enviar mensagem, anexar ou subir o relatório. Compartilhamento exige ação e aprovação explícitas da pessoa avaliada.
9. **Sem profiling indevido:** não inferir saúde, política, religião, etnia, sexualidade, estado emocional, personalidade, inteligência, produtividade, senioridade, performance ou intenção a partir do histórico.
10. **Sem ação expansiva:** o assessment não autoriza corrigir configs, apagar arquivos, instalar hooks, mudar permissões, executar código encontrado no histórico ou contatar pessoas.

## Redação segura de evidências

- Use: “Em 6 tarefas de planejamento, critérios de aceite foram declarados antes da execução.”
- Evite: prompt literal, nome do projeto confidencial, path com username, texto de cliente ou fragmento de segredo.
- Use locators locais redigidos ou hashes; paths exibidos no relatório devem usar `~` e remover nomes pessoais quando possível.
- Evidência de alta sensibilidade pode contar para cobertura, mas deve ser omitida da saída; registre a omissão.

Antes de persistir qualquer artefato, faça uma varredura por padrões de credencial e identificadores pessoais. Se a sanitização não puder ser garantida, não gere HTML/JSON detalhado: entregue somente um aviso local e uma lista abstrata do que ficou bloqueado.

## Conteúdo que não deve entrar no relatório

- prompts e respostas completos;
- valores de secrets ou conteúdo de `.env`, keychains e arquivos de credenciais;
- conversas privadas não necessárias à análise;
- código proprietário extenso;
- nomes ou avaliações individuais de terceiros;
- URLs privadas, IDs externos reutilizáveis e paths pessoais completos;
- alegações sem evidência ou inferências sensíveis.

## Retenção e descarte

Arquivos intermediários devem ser temporários, sanitizados e excluídos ao final quando isso puder ser feito sem afetar arquivos preexistentes. Não apague fontes. O relatório final deve declarar fontes, período, exclusões, nível de cobertura e se houve evidência sensível omitida. A pessoa decide se guarda ou compartilha o resultado.

## Condições de parada

Pare e marque `blocked` quando houver dúvida sobre propriedade/autorização, quando a única rota exigir quebrar controles, quando a fonte estiver ativa/corrompida e a leitura puder danificá-la, ou quando segredos não puderem ser excluídos com segurança. Continue com as demais fontes seguras e registre a lacuna; não peça que a pessoa cole segredos ou históricos integrais no chat.

## Uso organizacional

Este relatório serve para coaching individual. Não deve ser usado para ranking, remuneração, promoção, punição, monitoramento oculto ou comparação entre pessoas. Qualquer uso gerencial exige consentimento informado, direito de revisão pela pessoa avaliada e uma política organizacional específica fora desta skill.
