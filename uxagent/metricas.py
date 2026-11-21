"""Cálculo das métricas mínimas a partir dos registros (dicionário da Fase II).

S  = N_corretas / N_iniciadas (indeterminadas e sem task_end fora do denominador,
     relatadas à parte);
R_k = N_erros_k / N_oportunidades_k, k in {ATR, ACT, SLP, OMI}; ND se denominador zero;
A  = n.º de action_executed; X = A / A_min; D = distância de edição normalizada até o
     caminho admissível mais próximo; A_rej = propostas retidas (só sintético);
U  = n.º de support_open por tarefa (aberturas de tópico dentro de S6 não contam);
U_pre = 1 se o primeiro suporte precede o primeiro erro;
L  = latência do LLM (desempenho do sistema, não tempo comportamental).

Exporta CSV (uma linha por execução de tarefa) e JSON (agregado por célula).
"""
from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

from . import analista
from .registro import ler
from .verificador import segmentar, verificar_segmento

CATEGORIAS = ["ATR", "ACT", "SLP", "OMI"]


def levenshtein(a: list[str], b: list[str]) -> int:
    ant = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(ant[j] + 1, cur[j - 1] + 1, ant[j - 1] + (x != y)))
        ant = cur
    return ant[-1]


def distancia_caminho(acoes: list[str], tarefa: str, versao: str) -> float:
    caminhos = analista.CAMINHOS[(tarefa, versao)]
    return min(levenshtein(acoes, c) / max(len(acoes), len(c), 1) for c in caminhos)


def metricas_segmento(seg: list[dict]) -> dict:
    v = verificar_segmento(seg)
    tid, versao = v["task_id"], v["condition"]
    execs = [e for e in seg if e["event_type"] == "action_executed"]
    acoes = [e["data"]["executed"] for e in execs]
    a_min = analista.A_MIN[(tid, versao)]
    sup = [e for e in seg if e["event_type"] == "support_open" and not e["data"].get("dentro_de_S6")]
    por_layer = defaultdict(int)
    for e in sup:
        por_layer[e["data"]["layer"]] += 1
    erros_por_cat = defaultdict(int)
    for err in v["erros"]:
        erros_por_cat[err["categoria"].split("-")[1]] += 1
    # U_pre: primeiro suporte antes do primeiro erro (pela ordem dos eventos)
    ids_erro = {err.get("evento_origem") for err in v["erros"] if err.get("evento_origem")}
    ordem = {e["event_id"]: i for i, e in enumerate(seg)}
    pos_erro = min((ordem[i] for i in ids_erro if i in ordem), default=None)
    pos_sup = ordem[sup[0]["event_id"]] if sup else None
    u_pre = int(pos_sup is not None and (pos_erro is None or pos_sup < pos_erro))
    latencias = [e["data"]["latencia_s"] for e in seg if e["event_type"] == "action_proposed"
                 and e["data"].get("latencia_s")]
    truncada = v["situacao"] != "valido"
    linha = {
        "session_id": v["session_id"], "subject_id": v["subject_id"], "task_id": tid,
        "task_set": v["task_set"], "group": v["group"], "condition": versao,
        "persona_id": v["persona_id"], "config_hash": v["config_hash"],
        "llm_model": v["llm_model"], "synthetic": v["synthetic"],
        "situacao": v["situacao"], "fim": v["fim"],
        "sucesso": "" if v["sucesso"] is None else int(v["sucesso"]),
        "A": len(execs), "A_min": a_min, "X": round(len(execs) / a_min, 3),
        "D": "" if truncada else round(distancia_caminho(acoes, tid, versao), 3),
        "A_rej": sum(1 for e in seg if e["event_type"] == "action_rejected"),
        "U": sum(por_layer[l] for l in ("ajuda", "dica", "por_que")),
        "U_ajuda": por_layer["ajuda"], "U_dica": por_layer["dica"],
        "U_por_que": por_layer["por_que"],
        "U_caderno": sum(1 for e in seg if e["event_type"] == "note_shown"),
        "U_pre": u_pre,
        "L_mediana_s": round(statistics.median(latencias), 3) if latencias else "",
        "sequencia": " ".join(acoes),
        "metodo": json.dumps(v["metodo"], ensure_ascii=False),
        "mac": ";".join(t["etiqueta"] for t in v["mac"]),
        "modelo_divergente": int(v["modelo_divergente"]),
    }
    for k in CATEGORIAS:
        linha[f"err_{k}"] = erros_por_cat[k]
        linha[f"op_{k}"] = v["oportunidades"][k]
    return linha


def calcular(arquivos: list[Path]) -> list[dict]:
    linhas = []
    for arq in arquivos:
        for seg in segmentar(ler(arq)):
            linhas.append(metricas_segmento(seg))
    return linhas


def agregar(linhas: list[dict]) -> list[dict]:
    """Agrega por célula: tarefa x versão x grupo x configuração x modelo."""
    celulas = defaultdict(list)
    for l in linhas:
        chave = (l["task_id"], l["condition"], l["group"], l["persona_id"].split("#")[0],
                 l["llm_model"])
        celulas[chave].append(l)
    out = []
    for (tid, cond, grp, pers, mod), ls in sorted(celulas.items()):
        validas = [l for l in ls if l["situacao"] == "valido"]
        def media(campo, base=validas):
            vals = [l[campo] for l in base if l.get(campo, "") != ""]
            return round(statistics.mean(vals), 3) if vals else "ND"
        reg = {"task_id": tid, "condition": cond, "group": grp, "config": pers, "llm_model": mod,
               "synthetic": all(l["synthetic"] for l in ls),
               "n_iniciadas": len(ls), "n_validas": len(validas),
               "n_indeterminadas": sum(1 for l in ls if l["situacao"] == "indeterminado"),
               "n_desconhecidas": sum(1 for l in ls if l["situacao"] == "desconhecido"),
               "S": round(sum(l["sucesso"] for l in validas) / len(validas), 3) if validas else "ND",
               "A_media": media("A"), "X_media": media("X"), "D_media": media("D"),
               "U_media": media("U"), "U_pre_prop": media("U_pre"),
               "A_rej_media": media("A_rej"),
               "U_ajuda_media": media("U_ajuda"), "U_dica_media": media("U_dica"),
               "U_por_que_media": media("U_por_que"),
               "L_mediana_s": (round(statistics.median(
                   [l["L_mediana_s"] for l in ls if l.get("L_mediana_s", "") != ""]), 3)
                   if any(l.get("L_mediana_s", "") != "" for l in ls) else "ND"),
               "n_modelo_divergente": sum(l.get("modelo_divergente", 0) for l in ls)}
        for k in CATEGORIAS:
            op = sum(l[f"op_{k}"] for l in ls)
            reg[f"R_{k}"] = round(sum(l[f"err_{k}"] for l in ls) / op, 3) if op else "ND"
        out.append(reg)
    return out


def exportar(linhas: list[dict], pasta: Path) -> tuple[Path, Path]:
    pasta.mkdir(parents=True, exist_ok=True)
    csv_p = pasta / "metricas_por_execucao.csv"
    with csv_p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        w.writeheader()
        w.writerows(linhas)
    json_p = pasta / "metricas_por_celula.json"
    json_p.write_text(json.dumps({"rotulo": "SINTÉTICO — gerado por configuração versionada do "
                                            "UXAgent, sem participação humana",
                                  "celulas": agregar(linhas)}, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    return csv_p, json_p
