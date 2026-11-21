# Dicionário de campos dos eventos (E3)

Todo registro é **SINTÉTICO**: gerado por configuração versionada do UXAgent, sem participação humana.
Formato: JSON Lines, um arquivo por sessão (`<config>-<versão>-<política>-s<semente>.jsonl`).
O verificador gera ao lado `<sessão>.verificado.jsonl` com os eventos derivados.

## Campos comuns (em todo evento)

| Campo | Tipo | Significado |
|---|---|---|
| `event_id` | texto | `<session_id>-<nnnnn>`, sequencial na sessão; lacuna indica evento perdido (F-LOG) |
| `event_type` | texto | tipo do evento (tabelas abaixo) |
| `t_wall` | ISO 8601 UTC | instante do registro |
| `session_id` | texto | sessão (um participante sintético) |
| `subject_id` | texto | `sint-<semente>` |
| `persona_id` | texto | `<ficha/versão>#<hash dos parâmetros θ sorteados>` |
| `config_hash` | texto | hash do YAML + prompts usados |
| `synthetic`, `origin` | bool, texto | sempre `true` e `"synthetic"` |
| `group` | `P` ou `C` | perfil ou comparador |
| `condition` | `A` ou `B` | versão da interface |
| `task_id`, `task_set` | texto | `C1`, `C2` (`cal`); `V1`, `V2` (`val`, bloqueadas sem congelamento) |
| `step` | inteiro | n.º de ações executadas na tarefa até o evento |
| `ui_version`, `mech_version`, `design_version`, `help_hash` | texto | versões da interface, dos mecanismos, do caderno E1 e do texto da ajuda |
| `llm_provider`, `llm_model` | texto | `anthropic`/`claude-sonnet-5-5`, ou `local`/`regras`/`aleatoria` |
| `seed` | inteiro | semente do amostrador e dos mecanismos |
| `screen`, `screen_before`, `screen_after` | texto | cena (S1–S9, AL, CE1) |
| `state_before_hash`, `state_after_hash` | texto | hash do estado JSON da interface |
| `data` | objeto | conteúdo específico do tipo |

## Eventos do registro

| `event_type` | `data` | Quando |
|---|---|---|
| `session_start` | `config`, `theta` (parâmetros sorteados), `politica`, `tarefas`, `prompt_sistema` (texto integral), `python` | abertura da sessão |
| `task_start` | `ordem`, `instrucao` (texto lido), `estado_inicial` (JSON), `limite_acoes` (3·A_min) | início da tarefa |
| `screen_view` | `tela`, `elementos` (signos visíveis, sem ids internos) | a cada troca de tela |
| `mechanism_applied` | `mecanismo` (M1–M6), `efeito`, `valor`… | quando um mecanismo atua (só sintético) |
| `observation_delivered` | `o_t` (observação), `prompt_usuario` (mensagem integral enviada ao LLM), `prompt_sistema_sha`, `crenca`, `n_acoes` | antes de cada chamada à política |
| `action_proposed` | `indice`, `fala_u`, `proposed`, `justificativa`, `latencia_s`, `modelo_servido`, `stop_reason`, `request_id`, tokens | resposta da política (só sintético) |
| `action_rejected` | `motivo` = `hesitation`, `proposed`, `substituida_por` | M4 reteve a ação |
| `action_executed` | `cena`, `fala_u`, `proposed`, `executed`, `slip`, `tem_vizinho`, `fala_d`, `sem_efeito` | a interface aplicou a ação |
| `state_changed` | `variavel`, `antes`, `depois`, `origem` (`persona` ou `rotina:<id>`) | cada mudança de estado |
| `dialog_shown` | `tipo` (AL, CE1, CE2), `cena` | alerta ou captura exibidos |
| `dialog_choice` | `tipo`, `escolha` | opção tocada no diálogo |
| `support_open` | `layer` (ajuda, dica, por_que), `topic`, `scene_origin`, `dentro_de_S6` | abertura de suporte |
| `support_close` | `layer`, `scene_return` | fechamento |
| `note_written`, `note_shown` | `texto` | M5: nota escrita; nota mostrada na observação |
| `cause_selected` | `opcao` | opção marcada em S7 |
| `technical_failure` | `codigo` (F-API, F-FMT, F-REF), `mensagem` | falha técnica; tarefa vira `indeterminado` |
| `task_end` | `resultado` (concluida, desistencia, limite, indeterminado), `n_acoes`, `estado_final` (JSON) | fim declarado pela interface |
| `session_end` | `caderno`, `aprendidos` | fechamento da sessão |

## Eventos derivados (verificador externo, `*.verificado.jsonl`)

| `event_type` | Conteúdo |
|---|---|
| `task_result` | `sucesso` (pelo estado final), `situacao` (valido, indeterminado, desconhecido), `erros`, `oportunidades`, `metodo`, `mac`, `modelos_servidos`, `modelo_divergente` |
| `error_tagged` | `categoria` (E-ATR, E-ACT, E-SLP, E-OMI), `detalhe`, `evento_origem` |
| `method_selected` | `metodo` por subobjetivo (historico/painel, interruptor/desfazer, pausar/editar) |
| `communicability_tagged` | `etiqueta` MAC (Cadê?, O que é isto?, Epa!, Onde estou?, Por que não funciona?, Socorro!, Para mim está bom, Desisto) e `evento_origem` |
