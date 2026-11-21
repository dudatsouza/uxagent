"""Verificador externo de sucesso, erros, métodos e etiquetas MAC.

Lê SOMENTE o registro de eventos e o estado final gravado pela interface no
``task_end``. Nunca consulta o agente nem a justificativa do LLM: a afirmação do
agente de que terminou não é critério (``Para mim está bom`` é etiquetado aqui).

Saída: ``<sessao>.verificado.jsonl`` com eventos derivados (pós-processamento):
``task_result``, ``error_tagged``, ``method_selected``, ``communicability_tagged``.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import analista
from .registro import ler

INVERSOS = {"mais": "menos", "menos": "mais"}
AUTOINVERSAS = ("alternar:", "caixa:", "pausar_retomar")
NAV_BARRA = ("nav:S1", "nav:S2", "nav:S5", "voltar_S2", "voltar_concluir", "fechar_painel")


def segmentar(eventos: list[dict]) -> list[list[dict]]:
    """Divide o registro em execuções de tarefa (task_start ... task_end)."""
    segs, atual = [], None
    for e in eventos:
        if e["event_type"] == "task_start":
            if atual is not None:
                segs.append(atual)          # registro incompleto (sem task_end)
            atual = [e]
        elif atual is not None:
            atual.append(e)
            if e["event_type"] == "task_end":
                segs.append(atual)
                atual = None
    if atual is not None:
        segs.append(atual)
    return segs


def _erros(tid: str, seg: list[dict], estado: dict | None, fim: str | None) -> list[dict]:
    erros = []
    alvo = analista.ROTINA_ALVO[tid]
    if estado is not None and fim == "concluida":
        if analista.TEM_CAUSA[tid]:
            c = estado.get("resposta_causa")
            if c is not None and c != "nao_sei" and c != analista.CAUSA_CORRETA[tid]:
                erros.append({"categoria": "E-ATR", "detalhe": c})
        if not analista.estado_alvo(tid, estado):
            erros.append({"categoria": "E-OMI", "detalhe": "concluiu sem o estado-alvo"})
    rotinas_erradas = set()
    for e in seg:
        if e["event_type"] != "state_changed":
            continue
        d = e["data"]
        var = d["variavel"]
        if not var.startswith("rotinas.") or d["origem"] != "persona":
            continue
        rid, campo = var.split(".")[1], var.split(".")[2]
        if campo == "existe" and d["antes"] is True and d["depois"] is False:
            erros.append({"categoria": "E-ACT", "detalhe": f"excluiu {rid}",
                          "evento_origem": e["event_id"]})
        elif campo != "existe" and (tid == "C1" or rid != alvo) and rid not in rotinas_erradas:
            rotinas_erradas.add(rid)
            erros.append({"categoria": "E-ACT", "detalhe": f"alterou {rid}",
                          "evento_origem": e["event_id"]})
    for e in seg:
        if e["event_type"] == "action_executed" and e["data"].get("slip"):
            erros.append({"categoria": "E-SLP", "detalhe": e["data"]["executed"],
                          "evento_origem": e["event_id"]})
    return erros


def _mac(seg: list[dict], fim: str | None, ok: bool) -> list[dict]:
    tags = []
    # Cadê?: >=3 navegações seguidas pelas barras ou por Voltar, sem state_changed nem support_open.
    seq = 0
    for e in seg:
        t = e["event_type"]
        if t == "action_executed" and e["data"]["executed"].startswith(NAV_BARRA):
            seq += 1
            if seq == 3:
                tags.append({"etiqueta": "Cadê?", "evento_origem": e["event_id"]})
        elif t in ("state_changed", "support_open") or (
                t == "action_executed" and not e["data"]["executed"].startswith(NAV_BARRA)):
            seq = 0
    execs = [e for e in seg if e["event_type"] == "action_executed"]
    acoes = [e["data"]["executed"] for e in execs]
    for e in seg:
        if e["event_type"] == "support_open":
            d = e["data"]
            if d.get("layer") == "dica" or d.get("topic") in ("H2", "H3", "H4"):
                tags.append({"etiqueta": "O que é isto?", "evento_origem": e["event_id"]})
            if d.get("layer") == "ajuda" and not d.get("dentro_de_S6"):
                tags.append({"etiqueta": "Socorro!", "evento_origem": e["event_id"]})
        if e["event_type"] == "dialog_choice" and e["data"]["escolha"] == "cancelar":
            tags.append({"etiqueta": "Epa!", "evento_origem": e["event_id"]})
    # Epa!: ação seguida, em até duas ações, da inversa sobre o mesmo elemento.
    for i, a in enumerate(acoes):
        inv = INVERSOS.get(a, a if a.startswith(AUTOINVERSAS) else None)
        if a == "al_excluir":
            inv = "desfazer_exclusao"
        if inv and inv in acoes[i + 1:i + 3]:
            tags.append({"etiqueta": "Epa!", "evento_origem": execs[i]["event_id"]})
    # Onde estou?: entra numa tela e volta à anterior na ação seguinte (A -> X -> A), 2+ vezes.
    entra_sai = 0
    for i in range(1, len(execs)):
        prev, cur = execs[i - 1], execs[i]
        if (prev.get("screen_after") != prev.get("screen_before")
                and cur.get("screen_before") == prev.get("screen_after")
                and cur.get("screen_after") == prev.get("screen_before")):
            entra_sai += 1
    if entra_sai >= 2:
        tags.append({"etiqueta": "Onde estou?", "ocorrencias": entra_sai})
    # Por que não funciona?: mesma ação 2+ vezes seguidas sem state_changed entre elas.
    ultima, mudou = None, False
    for e in seg:
        if e["event_type"] == "state_changed":
            mudou = True
        elif e["event_type"] == "action_executed":
            a = e["data"]["executed"]
            if a == ultima and not mudou and not a.startswith(AUTOINVERSAS):
                tags.append({"etiqueta": "Por que não funciona?", "evento_origem": e["event_id"]})
            ultima, mudou = a, False
    if fim == "concluida" and not ok:
        tags.append({"etiqueta": "Para mim está bom"})
    if fim == "desistencia":
        tags.append({"etiqueta": "Desisto"})
    return tags


def verificar_segmento(seg: list[dict]) -> dict:
    ini = seg[0]
    tid = ini["task_id"]
    fim_ev = next((e for e in seg if e["event_type"] == "task_end"), None)
    fim = fim_ev["data"]["resultado"] if fim_ev else None
    estado = fim_ev["data"]["estado_final"] if fim_ev else None
    if fim is None:
        situacao = "desconhecido"         # registro incompleto
    elif fim == "indeterminado":
        situacao = "indeterminado"        # falha técnica
    else:
        situacao = "valido"
    ok = bool(estado is not None and analista.sucesso(tid, estado, fim))
    execs = [e["data"]["executed"] for e in seg if e["event_type"] == "action_executed"]
    modelos = {e["data"].get("modelo_servido") for e in seg
               if e["event_type"] == "action_proposed" and e["data"].get("modelo_servido")}
    return {
        "session_id": ini["session_id"], "subject_id": ini["subject_id"], "task_id": tid,
        "task_set": ini["task_set"], "group": ini["group"], "condition": ini["condition"],
        "persona_id": ini["persona_id"], "config_hash": ini["config_hash"],
        "llm_model": ini["llm_model"], "synthetic": ini["synthetic"],
        "fim": fim, "situacao": situacao, "sucesso": ok if situacao == "valido" else None,
        "causa_final": estado.get("resposta_causa") if estado else None,
        "erros": _erros(tid, seg, estado, fim) if situacao != "desconhecido" else [],
        "oportunidades": analista.oportunidades(tid, seg),
        "metodo": analista.metodos(execs),
        "mac": _mac(seg, fim, ok),
        "modelos_servidos": sorted(modelos),
        "modelo_divergente": bool(modelos - {ini["llm_model"]}),
    }


def verificar_arquivo(caminho: Path) -> Path:
    eventos = ler(caminho)
    saida = Path(str(caminho).replace(".jsonl", ".verificado.jsonl"))
    with saida.open("w", encoding="utf-8") as f:
        for seg in segmentar(eventos):
            r = verificar_segmento(seg)
            base = {k: r[k] for k in ("session_id", "subject_id", "task_id", "synthetic")}
            f.write(json.dumps({"event_type": "task_result", **r}, ensure_ascii=False) + "\n")
            for err in r["erros"]:
                f.write(json.dumps({"event_type": "error_tagged", **base, **err},
                                   ensure_ascii=False) + "\n")
            f.write(json.dumps({"event_type": "method_selected", **base, "metodo": r["metodo"]},
                               ensure_ascii=False) + "\n")
            for tag in r["mac"]:
                f.write(json.dumps({"event_type": "communicability_tagged", **base, **tag},
                                   ensure_ascii=False) + "\n")
    return saida
