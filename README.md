# UXAgent — Sistema Instrumentado (E2)

Agente proxy baseado em LLM que opera o protótipo **CasaFácil** (automação residencial) no lugar da persona **Lúcia** (68 anos, novata em automação) e gera **dados sintéticos de uso**, auditáveis e comparáveis à linha de base KLM.
Disciplina de IHC — CEFET-MG, Campus Divinópolis. Design: Caderno E1 (`../fase_4_design/caderno_E1.pdf`).

> Todo dado produzido aqui é **SINTÉTICO**: gerado por configuração versionada do UXAgent, sem participação humana. Não representa o comportamento de pessoas idosas reais.

## Instalação

Python 3.10 ou mais recente.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Para usar o LLM, defina a credencial da API da Anthropic (ou faça `ant auth login`):

```bash
export ANTHROPIC_API_KEY=...
```

## Execução

Piloto de calibração com o LLM (só C1 e C2), versão A, 5 sessões contrabalançadas:

```bash
.venv/bin/python -m uxagent rodar --config configs/persona_lucia.yaml --politica llm --versao A --tarefas C1 C2 --sessoes 5 --semente 100 --contrabalancear --saida dados/piloto_llm
```

Ao final, o comando roda o verificador externo e exporta as métricas em `dados/piloto_llm/metricas/` (`metricas_por_execucao.csv` e `metricas_por_celula.json`).

O piloto completo (perfil, genérico, comparador e neutro, versões A e B, C1 e C2) roda com um único script, que no fim também gera a tabela do artigo E4 e o pacote E3:

```bash
sh scripts/piloto_llm.sh
```

`dados/teste_llm/` guarda duas sessões curtas de C1 (versão A) usadas só para conferir a integração com a API antes do piloto.

Agente neutro de comparação (sem ficha de persona, mecanismos neutros):

```bash
.venv/bin/python -m uxagent rodar --config configs/neutro.yaml --politica llm --versao A --tarefas C1 C2 --sessoes 5 --semente 100 --saida dados/piloto_llm
```

Demonstração comentada de uma execução (para o vídeo E5):

```bash
.venv/bin/python -m uxagent demo --config configs/persona_lucia.yaml --politica llm --versao B --tarefa C1
```

CasaFácil no navegador (abre `http://localhost:8765`), com dois modos: **Usar o app**, em que uma pessoa toca nas telas (não grava dados do estudo), e **Replay do agente**, que refaz passo a passo uma sessão gravada, mostrando onde o agente tocou, a justificativa, os mecanismos e o resultado do verificador. Usa a mesma máquina de estados de `casafacil.py`; só C1 e C2:

```bash
.venv/bin/python -m uxagent app
```

O roteiro do vídeo de demonstração (E5) está em `docs/roteiro_video_E5.md`.

Sem credencial, troque `--politica llm` por `--politica regras` (executor por regras, controle) ou `--politica aleatoria`.

Verificar e calcular métricas de uma pasta já existente:

```bash
.venv/bin/python -m uxagent verificar dados/piloto_llm
```

```bash
.venv/bin/python -m uxagent metricas dados/piloto_llm
```

Tabela LaTeX das métricas por célula, usada no artigo E4 (junta o piloto com o LLM e o de instrumentação):

```bash
.venv/bin/python -m uxagent tabela dados/piloto_llm dados/piloto_instrumentacao --saida ../fase_5_artigo/tab_piloto.tex
```

Testes (correção das métricas com registros controlados, fronteira de informação e mecanismos):

```bash
.venv/bin/python -m pytest -q
```

## Configurações (`configs/`)

| Arquivo | Grupo | Ficha no prompt | Mecanismos | Uso |
|---|---|---|---|---|
| `persona_lucia.yaml` | P | Lúcia | M1–M6 ligados, distribuições da Tabela III da Fase II | UXAgent |
| `comparador.yaml` | C | Carlos, 42 anos | M1–M6 com distribuições de usuário "normal" | comparador sintético |
| `generico.yaml` | P | Lúcia | todos desligados | controle: encenação sem mecanismos |
| `neutro.yaml` | C | nenhuma | todos desligados | agente neutro de comparação |

Parâmetros (θ, sorteados por sessão com a semente): `p_atr` (M1, atribuição errada da causa), `q_rot` (M2, não reconhecer ícone ou termo em inglês), `p_slip` (M3, deslize de toque), `p_hes` (M4, hesitação diante de ação destrutiva ou incerta), `r_nota` (M5, consultar o caderno), `c_comp` (M6, compreender a explicação). Distribuições: `uniforme`, `triangular` ou `fixo`. Uma chave desligada força o valor neutro.

**Congelamento.** V1 e V2 (validação) só rodam com `--validacao` **e** `congelado: true` no YAML. Nunca use V1/V2 para ajustar prompts, parâmetros ou a interface.

## Arquitetura (`uxagent/`)

| Módulo | Papel |
|---|---|
| `casafacil.py` | interface instrumentada: máquina de estados S1–S9, diálogos AL/CE1/CE2, ajuda em camadas, processos do sistema |
| `tarefas.py` | instrução literal e estado inicial de C1, C2 (calibração), V1, V2 (validação) |
| `observacao.py` | tradutor de observação: tela → texto $o_t$ com paridade de signos (sem ids internos, ícones pela forma) |
| `mecanismos.py` | amostrador de θ e controlador M1–M6, fora do prompt |
| `politicas.py` | `LLMPolicy` (Claude), `RegrasPolicy`, `AleatoriaPolicy`, `ScriptPolicy` |
| `executor.py` | ciclo observação → política → M4/M3 → interface → registro; limite de 3·A_min ações |
| `registro.py` | eventos JSONL com campos comuns e marcação sintética |
| `analista.py` | **modelos do analista** (sucesso, caminhos admissíveis, A_min, oportunidades); nunca chega ao agente |
| `verificador.py` | verificador externo: sucesso pelo estado final, erros, métodos, etiquetas MAC |
| `metricas.py` | S, R_k, A, X, D, U por camada, U_pre, latência; exporta CSV e JSON |

**Fronteira de informação.** O LLM recebe só: instrução fixa de formato (`prompts/sistema.txt`), ficha da persona, instrução da tarefa, observação $o'_t$ e, de $x_t$, a crença atual, as notas do caderno e as últimas 8 ações feitas na tarefa (memória de trabalho; ver `docs/depuracao.md`, D-01). Nunca recebe HTA, CTT, GOMS, A_min, critério de sucesso, estado JSON, outras telas, histórico da conversa nem dados de validação. Testes em `tests/test_fronteira_e_mecanismos.py` verificam isso.

**Ações restritas à MoLIC.** A resposta do LLM é uma saída estruturada (`output_config.format`) cujo campo `acao` é um `enum` com os números das falas u: disponíveis no estado atual. Fora disso, há uma nova solicitação e, depois, falha `F-FMT`.

**Sucesso verificado fora do agente.** O `task_end` grava o estado final da interface; `verificador.py` decide o sucesso por esse estado. A afirmação do agente não conta (um "concluí" com o estado errado vira a etiqueta "Para mim está bom").

## Reprodução

- Modelo: `claude-sonnet-5-5` (Anthropic), via API, SDK `anthropic==2.12.0`; `effort: low`; `max_tokens: 4000`. O identificador do modelo que respondeu (`modelo_servido`) é gravado em cada `action_proposed`.
- **Sem temperatura**: o Claude Sonnet 5.5 rejeita valores de amostragem diferentes do padrão. A Modelagem previa temperatura 0,7; a divergência está registrada aqui. A geração do LLM não é determinística; as sementes controlam só o amostrador e os mecanismos.
- **Fallback em recusa**: `fallbacks: default` (beta `server-side-fallback-2026-07-01`) faz o servidor repetir a chamada noutro modelo se o Sonnet 5.5 recusar. Se isso acontecer, o `task_result` marca `modelo_divergente: true`; essas execuções devem ser relatadas à parte. Para desligar, use `fallbacks: null` no YAML.
- Sementes: `--semente` define a semente da primeira sessão; as seguintes usam `semente + i`.
- Versões: `ui_version`, `mech_version`, `design_version`, `help_hash` e `config_hash` vão em todo evento.

## Dados do piloto (E3)

`dados/piloto_instrumentacao/` traz o piloto de **instrumentação**, sem LLM: executor por regras (só M3 ativo) e política aleatória (M1–M6 ativos), perfil e comparador, versões A e B, apenas C1 e C2. Ele confere que todo evento é gravado e que o verificador e as métricas funcionam; não é resultado sobre o agente.

O piloto com o LLM gera `dados/piloto_llm/` com o comando da seção Execução.

Dicionário de campos: `docs/dicionario_eventos.md`. Pacote E3 (registros de calibração, dicionário, prompts e configurações; recusa registros de V1/V2):

```bash
sh scripts/empacotar_E3.sh
```

O pacote sai em `../entregas/E3_piloto_Lacerda_Souza.zip`. Os registros são JSON Lines (um objeto JSON por linha); o evento `observation_delivered` traz a mensagem integral enviada ao LLM em cada passo, e o `session_start` traz o prompt de sistema.

Roteiro da demonstração em vídeo (E5): `docs/roteiro_video_E5.md`.

## Documentos do projeto

- Caderno de design E1: `../fase_4_design/caderno_E1.pdf`
- Artigo DesignUXAgent (A3): `../fase_4_design/DesignUXAgent_IHC_Grupo_Lacerda_Souza.pdf`
- Artigo E4, com o E1 anexado: `../fase_5_artigo/E4_UXAgent_IHC_Grupo_Lacerda_Souza_com_anexo_E1.pdf`

## Entregas (PDFs e vídeo)

| Pasta / arquivo | Conteúdo |
|---|---|
| `entregas/E4_Artigo_UXAgent_com_anexo_E1.pdf` | E4: artigo IEEE (6 p.) + anexo E1 (caderno de design, 14 p.) |
| `entregas/E1_Caderno_de_Design_UXAgent.pdf` | E1 sozinho |
| `entregas/A3_DesignUXAgent_IHC_Grupo_Lacerda_Souza.pdf` | artigo DesignUXAgent (A3) |
| `entregas/E5_Demonstracao_UXAgent.mp4` | E5: demonstração com legenda (4 min 51 s) |
| `entregas/E5_imagem_abertura.png` | imagem de abertura do vídeo |
| `artigos/fonte/` | fontes LaTeX dos três documentos (compilar com `tectonic` ou `pdflatex` + `bibtex` dentro da pasta) |
| `docs/` | dicionário de eventos, registro de depuração (D-01 a D-03) e roteiro do vídeo |

## Limitações

Resultados sintéticos, válidos só para depurar protocolo e métricas. O agente não reproduz tempo, cansaço, emoção nem satisfação; a justificativa do LLM é traço qualitativo, não medida. M1, M2, M4, M5 e M6 são hipóteses operacionais (Fase II, Tabela VI).
