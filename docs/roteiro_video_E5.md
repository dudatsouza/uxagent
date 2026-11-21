# Roteiro da demonstração E5 (3 a 5 minutos)

Objetivo: mostrar uma execução completa do UXAgent, da tarefa recebida à verificação externa, com a interação do agente com a interface, as ações executadas e os eventos registrados.

Preparação (antes de gravar):

- Terminal com fonte grande, na pasta `uxagent/`, com `ANTHROPIC_API_KEY` definida.
- Abrir também o caderno E1 (`../fase_4_design/caderno_E1.pdf`) na página da MoLIC e um editor com `configs/persona_lucia.yaml`.
- Rodar o comando uma vez fora da gravação para conferir que a chave funciona.
- Sem chave, trocar `--politica llm` por `--politica regras` e dizer no vídeo que é o executor por regras (controle), não o LLM.

## Cena 1 — O que é e o que vamos ver (0:00–0:30)

Fala: "O UXAgent é um agente que usa o aplicativo CasaFácil no lugar da Lúcia, 68 anos, novata em automação. Ele só vê o que a tela mostra, só pode tocar no que a tela oferece, e quem decide se a tarefa deu certo é um verificador externo. Vamos rodar a tarefa de calibração C1 na versão B."

Mostrar: a figura de arquitetura do artigo E4.

## Cena 2 — Parâmetros fora do prompt (0:30–1:00)

Mostrar `configs/persona_lucia.yaml` e apontar as distribuições de `p_atr`, `q_rot`, `p_slip`, `p_hes`, `r_nota` e `c_comp`.

Fala: "O comportamento do perfil não vem de pedir ao modelo que aja como idosa. Vem de seis mecanismos em código, com parâmetros sorteados a cada sessão a partir destas distribuições, com semente registrada."

## Cena 3 — Execução comentada (1:00–3:00)

```bash
.venv/bin/python -m uxagent demo --config configs/persona_lucia.yaml --politica llm --versao B --tarefa C1 --semente 7
```

Rolar a saída devagar e apontar:

1. A instrução literal da tarefa, igual à que uma pessoa leria.
2. A observação `o_t`: só texto visível, ícones pela forma, ações numeradas. "Não há nomes de variáveis nem o estado interno."
3. A linha `>>> agente propõe [n] ...` com a justificativa: "o modelo responde só com um número da lista; a justificativa é registrada, mas não é métrica."
4. Linhas de mecanismo, se aparecerem: `[M1]` crença sobre a causa, `[DESLIZE M3]`, `!!! M4 hesitação`, `[M6]` ao ler o painel "Por quê?".
5. `estado: ... (persona)` ou `(rotina:...)`: a mudança de estado e sua origem.
6. O fim declarado pela interface (`concluida`, `desistencia` ou `limite`).

## Cena 4 — Verificação externa e registro (3:00–4:15)

Apontar a última linha `VERIFICADOR EXTERNO: sucesso=... | erros=[...] | MAC=[...]`.

Fala: "O sucesso não é o que o agente disse: o verificador leu o estado final da interface. Se o agente concluísse com a causa errada, apareceria E-ATR e a etiqueta 'Para mim está bom'."

Abrir o registro indicado na saída e mostrar três eventos:

```bash
grep -m1 '"observation_delivered"' dados/demo/lucia-B-llm-s7.jsonl | python3 -m json.tool | head -40
```

```bash
grep -m1 '"action_proposed"' dados/demo/lucia-B-llm-s7.jsonl | python3 -m json.tool
```

```bash
cat dados/demo/lucia-B-llm-s7.verificado.jsonl | python3 -m json.tool --json-lines | head -60
```

Fala: "Cada evento tem horário, persona, cena, fala e resposta, versões e hashes. O prompt enviado ao modelo fica gravado por inteiro, para auditoria."

## Cena 5 — Fechamento (4:15–4:45)

Fala: "Os mesmos comandos rodam o piloto completo com as tarefas de calibração e calculam sucesso, erros por oportunidade, ações em relação ao KLM e uso de ajuda. As tarefas de validação V1 e V2 ficam bloqueadas até a configuração ser congelada."

Mostrar a Tabela de métricas do artigo E4.
