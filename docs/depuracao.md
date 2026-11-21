# Registro de depuração do protocolo (insumo para a Prova 3, conjunto 4)

Cada alteração está ligada à evidência que a motivou. Só tarefas de **calibração** (C1, C2) foram usadas para depurar; V1 e V2 não foram executadas com o LLM.

## D-01 — 21/11/2026 — Agente preso entre Histórico e Início (C1, versão A)

- **Evidência.** Primeira execução com o LLM (`lucia`, semente 7, `claude-sonnet-5-5`): o agente alternou 14 vezes entre Histórico e Início, sempre com a justificativa de "confirmar no Histórico" o que já tinha lido, e a tarefa terminou por limite (15 ações), com a etiqueta MAC "Onde estou?". O registro desta execução foi sobrescrito pela execução seguinte com a mesma semente; a sequência está transcrita aqui.
- **Diagnóstico.** O LLM não recebe o histórico da conversa (decisão da Fase II), e $x_t$ entregava só a crença e as notas. A Fase II previa que $x_t$ incluísse "suportes consultados e passos", mas isso não chegava ao prompt. Sem memória do que já fez, a persona sintética "esquecia" que já consultara o Histórico.
- **Correção.** $x_t$ passa a guardar as ações já executadas na tarefa; as últimas 8 entram no prompt como "O que você já fez nesta tarefa" (`MEMORIA_ACOES` em `mecanismos.py`). O rótulo é o texto visível do elemento tocado e a tela que se abriu.
- **Status.** Hipótese operacional: 8 ações aproximam a memória de trabalho de curto prazo; não há valor publicado para esta tarefa. O valor é candidato à calibração e à análise de sensibilidade.
- **Verificação.** Duas novas execuções de C1 (sementes 7 e 8): sucesso verificado pelo estado final, com 10 e 9 ações; sem laço.
- **Limitação remanescente.** A memória é perfeita dentro da janela de 8 ações; não há esquecimento gradual.
