#!/bin/sh
# Monta o pacote E3 (dados do piloto de calibração) a partir do que existe em dados/.
# Uso: sh scripts/empacotar_E3.sh   (gera ../entregas/E3_piloto_Lacerda_Souza.zip)
set -e
cd "$(dirname "$0")/.."
DESTINO="../entregas/E3_piloto_Lacerda_Souza.zip"
mkdir -p ../entregas
rm -f "$DESTINO"
PASTAS=""
for p in dados/piloto_llm dados/piloto_instrumentacao dados/teste_llm; do
  [ -d "$p" ] && PASTAS="$PASTAS $p"
done
[ -d dados/piloto_llm ] || echo "AVISO: dados/piloto_llm não existe; o pacote leva só o piloto de instrumentação."
# Só tarefas de calibração entram (o executor bloqueia V1/V2 sem congelamento).
if grep -l '"task_id": "V[12]"' $(find $PASTAS -name '*.jsonl') >/dev/null 2>&1; then
  echo "ERRO: há registros de V1/V2 nas pastas do piloto; o E3 é só de calibração." >&2; exit 1
fi
zip -q -r "$DESTINO" $PASTAS docs/dicionario_eventos.md docs/depuracao.md prompts configs README.md
echo "$DESTINO"
unzip -l "$DESTINO" | tail -1
