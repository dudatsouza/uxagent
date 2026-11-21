"""Linha de comando do UXAgent.

Exemplos:
  python -m uxagent rodar --config configs/persona_lucia.yaml --politica llm --versao A \
      --tarefas C1 C2 --sessoes 5 --semente 100 --saida dados/piloto
  python -m uxagent verificar dados/piloto
  python -m uxagent metricas dados/piloto
  python -m uxagent demo --config configs/persona_lucia.yaml --politica regras --tarefa C1
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import metricas, relatorio, verificador
from .executor import rodar_sessao
from .registro import ler


def _arquivos(pasta: Path) -> list[Path]:
    return sorted(p for p in Path(pasta).glob("*.jsonl") if not p.name.endswith(".verificado.jsonl"))


def cmd_rodar(a):
    caminhos = []
    for i in range(a.sessoes):
        ordem = list(a.tarefas)
        if a.contrabalancear and i % 2 == 1:
            ordem = ordem[::-1]
        semente = a.semente + i
        p = rodar_sessao(Path(a.config), a.politica, a.versao, ordem, semente, Path(a.saida),
                         permitir_validacao=a.validacao)
        caminhos.append(p)
        print(f"[{i + 1}/{a.sessoes}] {p}")
    if not a.sem_pos:
        for p in caminhos:
            verificador.verificar_arquivo(p)
        csv_p, json_p = metricas.exportar(metricas.calcular(_arquivos(Path(a.saida))),
                                          Path(a.saida) / "metricas")
        print(f"métricas: {csv_p}\n          {json_p}")


def cmd_verificar(a):
    for p in _arquivos(Path(a.pasta)):
        print(verificador.verificar_arquivo(p))


def cmd_metricas(a):
    linhas = metricas.calcular(_arquivos(Path(a.pasta)))
    csv_p, json_p = metricas.exportar(linhas, Path(a.saida or Path(a.pasta) / "metricas"))
    print(csv_p, json_p, sep="\n")


def cmd_tabela(a):
    Path(a.saida).write_text(relatorio.tabela([Path(p) for p in a.pastas]), encoding="utf-8")
    print(a.saida)


def cmd_demo(a):
    """Roda uma tarefa e imprime, passo a passo, o que o agente viu e fez (para o vídeo E5)."""
    p = rodar_sessao(Path(a.config), a.politica, a.versao, [a.tarefa], a.semente,
                     Path(a.saida))
    evs = ler(p)
    for e in evs:
        t, d = e["event_type"], e["data"]
        if t == "task_start":
            print(f"\n=== TAREFA {e['task_id']} (versão {e['condition']}) ===\n{d['instrucao']}\n")
        elif t == "observation_delivered":
            print(f"--- observação o_t (passo {e['step'] + 1}) ---\n{d['o_t']}")
        elif t == "action_proposed":
            print(f">>> agente propõe [{d['indice']}] {d['fala_u']}  ({d['justificativa']})")
        elif t == "action_rejected":
            print(f"!!! M4 hesitação: {d['proposed']} -> {d['substituida_por']}")
        elif t == "action_executed":
            extra = "  [DESLIZE M3]" if d["slip"] else ""
            print(f"    executado: {d['fala_u']} -> {d['fala_d']}{extra}")
        elif t == "state_changed":
            print(f"    estado: {d['variavel']}: {d['antes']} -> {d['depois']} ({d['origem']})")
        elif t == "mechanism_applied":
            print(f"    [{d['mecanismo']}] {d.get('efeito', '')} {d.get('valor', '')}")
        elif t == "task_end":
            print(f"\n=== fim declarado pela interface: {d['resultado']} ({d['n_acoes']} ações) ===")
    v = verificador.verificar_arquivo(p)
    r = next(x for x in ler(v) if x["event_type"] == "task_result")
    print(f"VERIFICADOR EXTERNO: sucesso={r['sucesso']} | erros={[x['categoria'] for x in r['erros']]}"
          f" | MAC={[t['etiqueta'] for t in r['mac']]}")
    print(f"registro: {p}")


def cmd_app(a):
    from .visual import servir
    servir(a.porta, abrir=not a.sem_navegador)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="uxagent")
    sub = ap.add_subparsers(required=True)
    r = sub.add_parser("rodar", help="executa sessões sintéticas")
    r.add_argument("--config", required=True)
    r.add_argument("--politica", choices=["llm", "regras", "aleatoria"], default="llm")
    r.add_argument("--versao", choices=["A", "B"], required=True)
    r.add_argument("--tarefas", nargs="+", default=["C1", "C2"])
    r.add_argument("--sessoes", type=int, default=1)
    r.add_argument("--semente", type=int, default=1)
    r.add_argument("--saida", default="dados/rascunho")
    r.add_argument("--contrabalancear", action="store_true",
                   help="inverte a ordem das tarefas nas sessões ímpares")
    r.add_argument("--validacao", action="store_true",
                   help="permite V1/V2 (exige configuração com congelado: true)")
    r.add_argument("--sem-pos", action="store_true", help="não roda verificador nem métricas")
    r.set_defaults(f=cmd_rodar)
    v = sub.add_parser("verificar", help="verificador externo sobre uma pasta de registros")
    v.add_argument("pasta")
    v.set_defaults(f=cmd_verificar)
    m = sub.add_parser("metricas", help="calcula e exporta métricas (CSV e JSON)")
    m.add_argument("pasta")
    m.add_argument("--saida")
    m.set_defaults(f=cmd_metricas)
    tb = sub.add_parser("tabela", help="tabela LaTeX das métricas por célula (artigo E4)")
    tb.add_argument("pastas", nargs="+")
    tb.add_argument("--saida", default="tabela_piloto.tex")
    tb.set_defaults(f=cmd_tabela)
    d = sub.add_parser("demo", help="uma execução comentada, para demonstração")
    d.add_argument("--config", required=True)
    d.add_argument("--politica", choices=["llm", "regras", "aleatoria"], default="llm")
    d.add_argument("--versao", choices=["A", "B"], default="A")
    d.add_argument("--tarefa", default="C1")
    d.add_argument("--semente", type=int, default=7)
    d.add_argument("--saida", default="dados/demo")
    d.set_defaults(f=cmd_demo)
    w = sub.add_parser("app", help="CasaFácil no navegador: usar o app e replay do agente")
    w.add_argument("--porta", type=int, default=8765)
    w.add_argument("--sem-navegador", action="store_true", help="não abre o navegador")
    w.set_defaults(f=cmd_app)
    args = ap.parse_args(argv)
    args.f(args)


if __name__ == "__main__":
    sys.exit(main())
