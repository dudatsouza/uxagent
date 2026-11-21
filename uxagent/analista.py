"""Modelos do analista: critérios de sucesso, caminhos admissíveis, A_min e oportunidades de erro.

FRONTEIRA DE INFORMAÇÃO: este módulo é usado só pelo verificador externo, pelo
cálculo de métricas e pelo executor por regras (controle). Ele NUNCA é importado
por ``observacao.py`` nem por ``politicas.LLMPolicy`` (há teste que garante isso).
"""
from __future__ import annotations

ROTINA_ALVO = {"C1": "economia", "C2": "bom_dia", "V1": "pico", "V2": "climatizacao"}
CAUSA_CORRETA = {"C1": "rotina:economia", "V1": "rotina:pico", "V2": "rotina:climatizacao"}


def estado_alvo(tarefa: str, estado: dict) -> bool:
    """Parte do critério que depende só dos aparelhos e rotinas (sem a causa)."""
    rot = estado["rotinas"]
    if tarefa == "C1":
        return estado["aparelhos"]["luz_sala"] is True
    if tarefa == "C2":
        r = rot.get("bom_dia")
        return r is not None and (r["situacao"] == "Pausada" or "cafeteira" not in r["aparelhos"])
    if tarefa == "V1":
        r = rot.get("pico")
        return r is not None and (r["situacao"] == "Pausada"
                                  or "tomada_ventilador" not in r["aparelhos"])
    if tarefa == "V2":
        r = rot.get("climatizacao")
        return r is not None and r.get("horario") == 21 and r["situacao"] == "Ativa"
    raise KeyError(tarefa)


def causa_ok(tarefa: str, estado: dict) -> bool:
    return not TEM_CAUSA[tarefa] or estado.get("resposta_causa") == CAUSA_CORRETA[tarefa]


def sucesso(tarefa: str, estado: dict, fim: str | None) -> bool:
    """Critério de sucesso pelo estado final da interface (Tabela V da Fase II)."""
    return fim == "concluida" and estado_alvo(tarefa, estado) and causa_ok(tarefa, estado)


_CONC = ["concluir", "confirmar"]


def _c(t):
    return ["concluir", f"causa:{CAUSA_CORRETA[t]}", "confirmar"]


CAMINHOS = {
    ("C1", "A"): [
        ["alternar:luz_sala", "nav:S5", *_c("C1")],
        ["nav:S5", "nav:S1", "alternar:luz_sala", *_c("C1")],
    ],
    ("C2", "A"): [
        ["nav:S2", "abrir:bom_dia", "pausar_retomar", *_CONC],
        ["nav:S2", "abrir:bom_dia", "editar", "caixa:cafeteira", "salvar", *_CONC],
    ],
    ("V1", "A"): [
        ["nav:S5", "nav:S2", "abrir:pico", "pausar_retomar", *_c("V1")],
        ["nav:S5", "nav:S2", "abrir:pico", "editar", "caixa:tomada_ventilador", "salvar",
         *_c("V1")],
    ],
    ("V2", "A"): [
        ["nav:S5", "nav:S2", "abrir:climatizacao", "editar", *["mais"] * 6, "salvar", *_c("V2")],
    ],
}
CAMINHOS[("C1", "B")] = CAMINHOS[("C1", "A")] + [
    ["porque", "desfazer_aviso", *_c("C1")],
    ["desfazer_aviso", "nav:S5", *_c("C1")],
    ["porque", "fechar_painel", "alternar:luz_sala", *_c("C1")],
]
CAMINHOS[("C2", "B")] = CAMINHOS[("C2", "A")]
CAMINHOS[("V1", "B")] = CAMINHOS[("V1", "A")] + [
    ["porque", "ir_rotina", "pausar_retomar", *_c("V1")],
    ["porque", "ir_rotina", "editar", "caixa:tomada_ventilador", "salvar", *_c("V1")],
]
CAMINHOS[("V2", "B")] = CAMINHOS[("V2", "A")] + [
    ["porque", "ir_rotina", "editar", *["mais"] * 6, "salvar", *_c("V2")],
]

# A_min do caderno E1 (Tabela IX): denominador de X = A / A_min.
A_MIN = {("C1", "A"): 5, ("C1", "B"): 5, ("C2", "A"): 5, ("C2", "B"): 5,
         ("V1", "A"): 7, ("V1", "B"): 6, ("V2", "A"): 14, ("V2", "B"): 13}

# Caminho seguido pelo executor por regras (método GOMS selecionado).
METODO_REFERENCIA = {
    ("C1", "A"): CAMINHOS[("C1", "A")][0],
    ("C1", "B"): ["porque", "desfazer_aviso", *_c("C1")],
    ("C2", "A"): CAMINHOS[("C2", "A")][0],
    ("C2", "B"): CAMINHOS[("C2", "A")][0],
    ("V1", "A"): CAMINHOS[("V1", "A")][0],
    ("V1", "B"): ["porque", "ir_rotina", "pausar_retomar", *_c("V1")],
    ("V2", "A"): CAMINHOS[("V2", "A")][0],
    ("V2", "B"): ["porque", "ir_rotina", "editar", *["mais"] * 6, "salvar", *_c("V2")],
}

# Oportunidades de erro por tarefa (Fase II, Tabela V e Apêndice A).
TEM_CAUSA = {"C1": True, "C2": False, "V1": True, "V2": True}


def oportunidades(tarefa: str, eventos: list[dict]) -> dict:
    """Oportunidades efetivamente expostas, a partir do registro."""
    exec_ = [e for e in eventos if e["event_type"] == "action_executed"]
    viu_s3 = any(e["event_type"] == "screen_view" and e["data"]["tela"] == "S3" for e in eventos)
    return {
        "ATR": 1 if TEM_CAUSA[tarefa] else 0,
        "ACT": 2 if (tarefa != "C1" or viu_s3) else 0,
        "SLP": sum(1 for e in exec_ if e["data"].get("tem_vizinho")),
        "OMI": 1,
    }


def metodos(acoes: list[str]) -> dict:
    """Método usado por subobjetivo (evento derivado method_selected)."""
    m = {}
    if "porque" in acoes:
        m["diagnostico"] = "painel"
    elif "nav:S5" in acoes:
        m["diagnostico"] = "historico"
    if "desfazer_aviso" in acoes:
        m["restaurar"] = "desfazer"
    elif any(a.startswith("alternar:") for a in acoes):
        m["restaurar"] = "interruptor"
    if "pausar_retomar" in acoes:
        m["suspender"] = "pausar"
    if "salvar" in acoes or "ce1_salvar" in acoes:
        m["suspender_ou_ajustar"] = "editar"
    return m


# Linha de base KLM de especialista (caderno E1, Tabela de KLM): segundos no caminho mínimo,
# método de referência; usada só no relatório, nunca pelo agente.
KLM_S = {("C1", "A"): 12.30, ("C1", "B"): 12.30, ("C2", "A"): 13.65, ("C2", "B"): 13.65,
         ("V1", "A"): 17.76, ("V1", "B"): 15.03, ("V2", "A"): 30.12, ("V2", "B"): 27.39}
