# Registro de depuração do protocolo (insumo para a Prova 3, conjunto 4)

Cada alteração está ligada à evidência que a motivou. Só tarefas de **calibração** (C1, C2) foram usadas para depurar; V1 e V2 não foram executadas com o LLM.

## D-01 — 21/11/2026 — Agente preso entre Histórico e Início (C1, versão A)

- **Evidência.** Primeira execução com o LLM (`lucia`, semente 7, `claude-sonnet-5-5`): o agente alternou 14 vezes entre Histórico e Início, sempre com a justificativa de "confirmar no Histórico" o que já tinha lido, e a tarefa terminou por limite (15 ações), com a etiqueta MAC "Onde estou?". O registro desta execução foi sobrescrito pela execução seguinte com a mesma semente; a sequência está transcrita aqui.
- **Diagnóstico.** O LLM não recebe o histórico da conversa (decisão da Fase II), e $x_t$ entregava só a crença e as notas. A Fase II previa que $x_t$ incluísse "suportes consultados e passos", mas isso não chegava ao prompt. Sem memória do que já fez, a persona sintética "esquecia" que já consultara o Histórico.
- **Correção.** $x_t$ passa a guardar as ações já executadas na tarefa; as últimas 8 entram no prompt como "O que você já fez nesta tarefa" (`MEMORIA_ACOES` em `mecanismos.py`). O rótulo é o texto visível do elemento tocado e a tela que se abriu.
- **Status.** Hipótese operacional: 8 ações aproximam a memória de trabalho de curto prazo; não há valor publicado para esta tarefa. O valor é candidato à calibração e à análise de sensibilidade.
- **Verificação.** Duas novas execuções de C1 (sementes 7 e 8): sucesso verificado pelo estado final, com 10 e 9 ações; sem laço.
- **Limitação remanescente.** A memória é perfeita dentro da janela de 8 ações; não há esquecimento gradual.

## Piloto de calibração com o LLM — 21/11/2026

30 sessões (`dados/piloto_llm/`, sementes 200–204), 60 tarefas C1/C2: Lúcia e comparador nas versões A e B; agente neutro e agente genérico na versão A; 5 sessões por célula, `claude-sonnet-5-5`. Zero falhas técnicas, zero execuções com `modelo_divergente`, latência mediana de 2,0 s por chamada. Os registros foram gerados **antes** das correções D-02 e D-03 abaixo e são mantidos como evidência delas.

## D-02 — 21/11/2026 — Vaivém entre Concluir e Voltar em C2

- **Evidência.** Em C2, todas as células com ficha de persona (Lúcia A/B, comparador A/B, genérico A; 25 execuções) terminaram por limite (S = 0, X = 3,0). Em todas, o agente pausou a rotina certa, viu "Situação: Pausada", tocou Concluir e, na tela "Você terminou?", tocou Voltar "para conferir", repetindo até o limite; o verificador marcou "Onde estou?". O agente neutro, sem ficha, teve S = 1,0 (editou a rotina e confirmou). O agente genérico, sem mecanismos, falhou igual a Lúcia: **a falha vem da ficha no prompt e do próprio LLM, não de M1–M6**.
- **Diagnóstico.** A memória de D-01 guardava o elemento tocado, mas não o retorno visível. A persona sintética não "lembrava" de ter visto a rotina pausada.
- **Correção.** A memória passa a registrar o retorno visível da ação (ex.: `... sem texto (a tela mostrou: "Situação": "Ativa" -> "Pausada")`).
- **Verificação.** Duas execuções de C2 (Lúcia, A, sementes 300 e 301, `dados/teste_llm/`): uma terminou por limite, outra concluiu com sucesso na 15.ª ação. A dúvida mudou de objeto ("a 'Bom dia' é mesmo a rotina da cafeteira?"). **Correção parcial**.
- **Achado de protocolo.** A tela S7 de C2 ("Você terminou?") não resume o estado; um usuário cauteloso não tem como confirmar ali o que fez. Candidato a revisão de design (nova versão da interface, nova calibração), não a ajuste do agente.
- **Status.** Hipótese operacional. Não se seguiu ajustando o prompt até o agente acertar, para não calibrar demais com uma só tarefa.

## D-03 — 21/11/2026 — Erro de implementação em M1 na versão B (C1)

- **Evidência.** Lúcia em C1-B: S = 0,4, contra 1,0 em C1-A. Em s200 e s202 a crença inicial era "defeito"; o agente tocou Desfazer, visitou o Histórico, mas a crença não foi revista, e o filtro da pergunta de causa (M1/M6) nunca ofereceu a rotina certa: a tarefa terminou por limite.
- **Diagnóstico.** A revisão da crença pelo Histórico exigia o aviso ainda visível; "Desfazer" apaga o aviso. Erro de implementação, não decisão de design.
- **Correção.** $x_t$ guarda o aparelho do aviso visto no início da tarefa; a revisão no Histórico usa esse aparelho. Teste: `tests/test_d03_crenca.py`.
- **Consequência.** Os números de C1-B (Lúcia e comparador) do piloto estão afetados por este erro e devem ser lidos com essa ressalva.
