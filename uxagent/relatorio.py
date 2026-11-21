"""Gera tabelas LaTeX do piloto a partir de ``metricas_por_celula.json``.

Uso: ``python -m uxagent tabela dados/piloto_llm dados/piloto_instrumentacao --saida t.tex``.
As tabelas entram no artigo E4 por ``\\input``; rodar de novo após um piloto atualiza o artigo.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import analista

POLITICA = {"regras": "regras", "aleatoria": "aleatória", "script": "roteiro"}


def _n(v, casas=2):
    if v in ("ND", None, ""):
        return "ND"
    return f"{float(v):.{casas}f}".replace(".", ",")


def _celulas(pastas: list[Path]) -> list[dict]:
    out = []
    for p in pastas:
        arq = Path(p) / "metricas" / "metricas_por_celula.json"
        if arq.exists():
            out += json.loads(arq.read_text(encoding="utf-8"))["celulas"]
    ordem_cfg = {"lucia-v1": 0, "generico-v1": 1, "comparador-v1": 2, "neutro-v1": 3}
    return sorted(out, key=lambda c: (c["llm_model"] in POLITICA, c["llm_model"], c["task_id"],
                                      c["condition"], ordem_cfg.get(c["config"], 9)))


def tabela(pastas: list[Path]) -> str:
    linhas = []
    for c in _celulas(pastas):
        tid, ver = c["task_id"], c["condition"]
        pol = POLITICA.get(c["llm_model"], "LLM")
        cfg = c["config"].replace("-v1", "").replace("lucia", "Lúcia")
        n = f'{c["n_validas"]}/{c["n_iniciadas"]}'
        u = (f'{_n(c["U_media"])} ({_n(c.get("U_ajuda_media"),1)}/{_n(c.get("U_dica_media"),1)}/'
             f'{_n(c.get("U_por_que_media"),1)})')
        lat = _n(c.get("L_mediana_s"), 1) if pol == "LLM" else "---"
        linhas.append(" & ".join([
            tid, ver, f'{cfg} ({c["group"]})', pol, n, _n(c["S"]),
            f'{_n(c["A_media"],1)} ({analista.A_MIN[(tid, ver)]})', _n(c["X_media"]),
            _n(c["D_media"]), u, _n(c["R_ATR"]), _n(c["R_ACT"]), _n(c["R_SLP"]), _n(c["R_OMI"]),
            lat]) + r" \\")
    cab = (r"\textbf{T} & \textbf{V} & \textbf{Config. (grupo)} & \textbf{Política} & "
           r"\textbf{$n$} & \textbf{$S$} & \textbf{$A$ ($A_{\min}$)} & \textbf{$X$} & "
           r"\textbf{$D$} & \textbf{$U$ (aj./dica/pq.)} & \textbf{$R_{\mathrm{ATR}}$} & "
           r"\textbf{$R_{\mathrm{ACT}}$} & \textbf{$R_{\mathrm{SLP}}$} & "
           r"\textbf{$R_{\mathrm{OMI}}$} & \textbf{$L$ (s)} \\")
    return "\n".join([
        "% Gerado por python -m uxagent tabela; não editar à mão.",
        r"\begin{tabular}{@{}llllrrrrrlrrrrr@{}}", r"\toprule", cab, r"\midrule",
        *linhas, r"\bottomrule", r"\end{tabular}", ""])


def klm() -> str:
    linhas = [f"{t} & {v} & {analista.A_MIN[(t, v)]} & {_n(s)} \\\\"
              for (t, v), s in analista.KLM_S.items() if t in ("C1", "C2")]
    return "\n".join([r"\begin{tabular}{@{}llrr@{}}", r"\toprule",
                      r"\textbf{T} & \textbf{V} & \textbf{$A_{\min}$} & \textbf{KLM (s)} \\",
                      r"\midrule", *linhas, r"\bottomrule", r"\end{tabular}", ""])
