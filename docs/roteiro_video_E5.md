# Roteiro da demonstração E5 (3 a 5 minutos)

Objetivo (enunciado do P3): mostrar uma execução completa do UXAgent, da tarefa recebida à verificação externa, evidenciando a interação do agente com a interface, as ações executadas e os eventos registrados.

O vídeo usa duas ferramentas do repositório:

- `python -m uxagent demo`: roda o agente de verdade (Claude, pela API) numa tarefa e grava o registro.
- `python -m uxagent app`: abre o **CasaFácil no navegador**, com as telas desenhadas como as de um celular. A aba **Replay do agente** refaz, passo a passo, a execução gravada (a mesma máquina de estados que o agente usou), destacando onde ele tocou.

## Preparação (antes de gravar)

1. Ativar "Não Perturbe" e fechar janelas pessoais. Nunca abrir o `~/.zshrc` (tem a chave da API).
2. **Terminal, aba 1** (deixar rodando durante todo o vídeo):
   ```bash
   cd ~/Documents/graduacao/8_periodo/ihc/uxagent
   .venv/bin/python -m uxagent app
   ```
   O navegador abre em `http://localhost:8765`.
3. **Terminal, aba 2** (⌘T): `cd ~/Documents/graduacao/8_periodo/ihc/uxagent` e aumentar a fonte (⌘+ quatro vezes).
4. Abrir `configs/persona_lucia.yaml` no TextEdit (`open -a TextEdit configs/persona_lucia.yaml`), só para mostrar.
5. Abrir o artigo E4 (`open ../fase_5_artigo/E4_UXAgent_IHC_Grupo_Lacerda_Souza.pdf`) na página 5 (Tabela III).
6. Ensaio: rodar o comando da Cena 3 uma vez fora da gravação.

Gravar com ⌘⇧5 → "Gravar a Tela Inteira" → Opções → Microfone do MacBook → Gravar. Parar no ícone ⏹ da barra de menus.

## Cena 1 — O app CasaFácil (0:00–0:40)

No navegador, aba **Usar o app**, tarefa C1, versão B, **Começar**. Mostrar a tela Início com o aviso amarelo; tocar em **Rotinas** e em **Bom dia** para mostrar os ícones sem texto; voltar ao **Início**.

Fala: "Este é o CasaFácil, o protótipo de aplicativo de casa inteligente do nosso trabalho. Ele tem as telas Início, Rotinas, Histórico, Ajuda e, na versão B, o botão 'Por quê?', que explica as ações automáticas. Quem vai usar o app não é uma pessoa: é o UXAgent, um agente baseado no Claude que faz o papel da Lúcia, 68 anos, novata em automação."

## Cena 2 — Parâmetros fora do prompt (0:40–1:05)

Mostrar o `persona_lucia.yaml` no TextEdit e passar o mouse pelos parâmetros.

Fala: "O comportamento do perfil não vem de pedir ao modelo que aja como idosa. Vem de seis mecanismos em código: chance de atribuir a causa errada, de não reconhecer um ícone, de tocar no botão vizinho, de hesitar, de consultar anotações e de entender a explicação. Cada sessão sorteia esses valores, com semente registrada."

## Cena 3 — O agente rodando de verdade (1:05–1:40)

Terminal, aba 2:
```bash
.venv/bin/python -m uxagent demo --config configs/persona_lucia.yaml --politica llm --versao B --tarefa C1 --semente 7 --saida dados/demo
```

Fala, enquanto roda (cerca de 15 s): "Aqui o agente está usando o app de verdade, chamando o Claude pela API. A cada passo ele recebe a descrição da tela e responde com o número de uma ação. Ao final, o verificador externo confere o resultado." Apontar a última linha `VERIFICADOR EXTERNO: sucesso=...`.

## Cena 4 — Replay no navegador (1:40–3:50)

No navegador: **⌘R** (para a página ver a sessão nova), aba **Replay do agente**, sessão `demo/lucia-B-llm-s7.jsonl`, tarefa C1. Avançar com **▶** (próximo passo), um passo de cada vez, comentando:

- A **instrução** no painel: "a mesma que uma pessoa leria".
- O **contorno vermelho**: onde o agente tocou. **Contorno laranja tracejado**, se aparecer: onde ele queria tocar, mas o mecanismo de deslize (M3) fez acertar o vizinho.
- A **justificativa** entre aspas: "o modelo explica a escolha; isso é registrado, mas não é medida".
- Os **mecanismos** (etiquetas roxas), por exemplo `M1: crenca → eu_outra` ("a persona acha que foi ela mesma") e depois a crença corrigida ao ler o Histórico.
- As **mudanças de estado** (etiquetas verdes), com a origem: persona ou rotina.
- Abrir **"O que a IA recebeu neste passo"**: "isto é tudo o que o modelo vê: só o texto da tela; ícones descritos pela forma; nada do estado interno nem da resposta certa".
- Último passo → **Tela final** com o cartão do **Verificador externo**: "o sucesso não é o que o agente disse; o verificador leu o estado final da casa. Aqui também aparecem os erros, como E-SLP, o deslize de toque, e as rupturas de comunicabilidade".

## Cena 5 — Registro e fechamento (3:50–4:40)

Terminal, aba 2:
```bash
grep -m1 '"action_proposed"' dados/demo/lucia-B-llm-s7.jsonl | python3 -m json.tool
```

Fala: "Cada passo vira um evento no registro JSON, com horário, persona, cena, fala, modelo e versões, e marcado como sintético. O prompt completo também fica gravado, para auditoria."

Mostrar a Tabela III do artigo E4.

Fala: "O mesmo sistema rodou o piloto: 30 sessões nas tarefas de calibração, sem falhas técnicas. O piloto encontrou problemas no protocolo, que estão documentados no artigo. As tarefas de validação ficam bloqueadas até a configuração ser congelada. Obrigada!"

## Depois de gravar

```bash
avconvert --source ~/Desktop/video.mov --output ~/Desktop/E5_UXAgent_Lacerda_Souza.mp4 --preset Preset1920x1080
```

(Renomear antes o arquivo gravado na Mesa para `video.mov`.) Conferir áudio e duração entre 3 e 5 minutos. O LLM não é determinístico: a execução pode sair diferente da do ensaio; isso não é problema.
