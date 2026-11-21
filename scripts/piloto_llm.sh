#!/bin/sh
# Piloto de calibração com o LLM: só C1 e C2; perfil, genérico, comparador e neutro; versões A e B.
# Uso (na pasta uxagent/, com ANTHROPIC_API_KEY definida no terminal):
#   sh scripts/piloto_llm.sh        # 5 sessões por configuração e versão (padrão)
#   sh scripts/piloto_llm.sh 10     # 10 sessões
# Ao final: verificador, métricas, tabela do artigo E4 e pacote E3.
set -e
cd "$(dirname "$0")/.."
if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "ANTHROPIC_API_KEY não está definida neste terminal." >&2; exit 1
fi
N=${1:-5}
for cfg in persona_lucia generico comparador neutro; do
  for v in A B; do
    echo "== $cfg, versão $v, $N sessões"
    .venv/bin/python -m uxagent rodar --config "configs/$cfg.yaml" --politica llm --versao "$v" \
      --tarefas C1 C2 --sessoes "$N" --semente 100 --contrabalancear --saida dados/piloto_llm --sem-pos
  done
done
.venv/bin/python -m uxagent verificar dados/piloto_llm > /dev/null
.venv/bin/python -m uxagent metricas dados/piloto_llm
.venv/bin/python -m uxagent tabela dados/piloto_llm dados/piloto_instrumentacao \
  --saida ../fase_5_artigo/tab_piloto.tex
sh scripts/empacotar_E3.sh
grep -l '"technical_failure"' dados/piloto_llm/*.jsonl 2>/dev/null | sed 's/^/falha técnica em: /' || true
echo "Pronto. Avise o Claude para revisar os resultados e completar o artigo E4."
