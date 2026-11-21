"""Tarefas da Fase II: instrução literal e condição inicial.

Só o que é dado igualmente a pessoas e ao agente fica aqui. Critérios de
sucesso, caminhos admissíveis e A_min ficam em ``analista.py`` e nunca são
importados pelo agente.

V1 e V2 são de validação, congeladas desde 26/10/2026. O executor só as roda
com ``--validacao`` e configuração congelada (ver ``executor.py``).
"""
from __future__ import annotations

import copy

INSTRUCAO_GERAL = ("Imagine que esta é a sua casa. Faça do seu jeito; se quiser, use a Ajuda do "
                   "aplicativo. Quando terminar, toque em Concluir; se não quiser continuar, "
                   "toque em Desistir.")

NOMES_ROTINAS = {
    "economia": "Economia de energia",
    "bom_dia": "Bom dia",
    "pico": "Horário de pico",
    "climatizacao": "Climatização",
}


def _rotinas_base() -> dict:
    """Rotinas que a filha criou; todas existem em todas as tarefas."""
    return {
        "economia": {"nome": "Economia de energia", "situacao": "Ativa", "horario": None,
                     "condicao": "não houver movimento na sala por 30 minutos",
                     "acao": "desligar", "aparelhos": ["luz_sala"],
                     "motivo": "não houve movimento na sala por 30 minutos"},
        "bom_dia": {"nome": "Bom dia", "situacao": "Ativa", "horario": 7, "condicao": None,
                    "acao": "ligar", "aparelhos": ["luz_sala", "cafeteira"],
                    "motivo": "chegou o horário programado (07h00)"},
        "pico": {"nome": "Horário de pico", "situacao": "Ativa", "horario": None,
                 "condicao": "for entre 13h30 e 17h00",
                 "acao": "desligar", "aparelhos": ["tomada_ventilador"],
                 "motivo": "é horário de pico de energia (13h30 a 17h00)"},
        "climatizacao": {"nome": "Climatização", "situacao": "Ativa", "horario": 15,
                         "condicao": None, "acao": "ligar", "aparelhos": ["ar_quarto"],
                         "motivo": "chegou o horário programado (15h00)"},
    }


def _estado(relogio_min: int, aparelhos: dict, aviso=None, historico=None, ajustes=None) -> dict:
    rot = _rotinas_base()
    for rid, campos in (ajustes or {}).items():
        rot[rid].update(campos)
    return {
        "relogio": relogio_min,
        "aparelhos": aparelhos,
        "rotinas": rot,
        "nomes_rotinas": dict(NOMES_ROTINAS),
        "aviso": aviso,
        "historico": historico or [],
    }


TAREFAS = {
    "C1": {
        "conjunto": "cal",
        "instrucao": ("A luz da sala apagou sozinha agora há pouco. Descubra por que isso "
                      "aconteceu e acenda a luz de novo."),
        "perguntar_causa": True,
        "estado": lambda: _estado(
            14 * 60 + 10,
            {"luz_sala": False, "ar_quarto": False, "cafeteira": False, "tomada_ventilador": True},
            aviso={"aparelho": "luz_sala", "ligado": False, "hora": "14h02", "rotina": "economia",
                   "motivo": "não houve movimento na sala por 30 minutos"},
            historico=[
                {"hora": "07h00", "aparelho": "luz_sala", "ligado": True, "origem": "bom_dia"},
                {"hora": "07h00", "aparelho": "cafeteira", "ligado": True, "origem": "bom_dia"},
                {"hora": "07h40", "aparelho": "cafeteira", "ligado": False, "origem": "pessoa"},
                {"hora": "14h02", "aparelho": "luz_sala", "ligado": False, "origem": "economia"},
            ]),
    },
    "C2": {
        "conjunto": "cal",
        "instrucao": ("Você viaja amanhã cedo e não quer que a cafeteira ligue sozinha enquanto "
                      "estiver fora. Sua filha preparou as automações, e você não quer perdê-las."),
        "perguntar_causa": False,
        "estado": lambda: _estado(
            21 * 60,
            {"luz_sala": True, "ar_quarto": False, "cafeteira": False, "tomada_ventilador": False},
            historico=[
                {"hora": "07h00", "aparelho": "luz_sala", "ligado": True, "origem": "bom_dia"},
                {"hora": "07h00", "aparelho": "cafeteira", "ligado": True, "origem": "bom_dia"},
                {"hora": "07h35", "aparelho": "cafeteira", "ligado": False, "origem": "pessoa"},
            ]),
    },
    # --- Validação: congeladas em 26/10/2026 -------------------------------
    "V1": {
        "conjunto": "val",
        "instrucao": ("A tomada do ventilador desligou sozinha à tarde. Descubra o que aconteceu e "
                      "faça com que isso não se repita hoje."),
        "perguntar_causa": True,
        "estado": lambda: _estado(
            14 * 60 + 20,
            {"luz_sala": False, "ar_quarto": False, "cafeteira": False, "tomada_ventilador": False},
            aviso={"aparelho": "tomada_ventilador", "ligado": False, "hora": "13h30",
                   "rotina": "pico", "motivo": "é horário de pico de energia (13h30 a 17h00)"},
            historico=[
                {"hora": "13h05", "aparelho": "tomada_ventilador", "ligado": True,
                 "origem": "pessoa"},
                {"hora": "13h30", "aparelho": "tomada_ventilador", "ligado": False,
                 "origem": "pico"},
            ],
            ajustes={"pico": {"reativa": {"aparelho": "tomada_ventilador", "ligado": False,
                                          "atraso_min": 2}}}),
    },
    "V2": {
        "conjunto": "val",
        "instrucao": ("O ar-condicionado do quarto ligou sozinho às 15h. Descubra quem o ligou e "
                      "faça com que ele só ligue às 21h."),
        "perguntar_causa": True,
        "estado": lambda: _estado(
            15 * 60 + 10,
            {"luz_sala": False, "ar_quarto": True, "cafeteira": False, "tomada_ventilador": False},
            aviso={"aparelho": "ar_quarto", "ligado": True, "hora": "15h00",
                   "rotina": "climatizacao", "motivo": "chegou o horário programado (15h00)"},
            historico=[
                {"hora": "15h00", "aparelho": "ar_quarto", "ligado": True,
                 "origem": "climatizacao"},
            ]),
    },
}

CALIBRACAO = [t for t, d in TAREFAS.items() if d["conjunto"] == "cal"]
VALIDACAO = [t for t, d in TAREFAS.items() if d["conjunto"] == "val"]


def estado_inicial(tarefa: str) -> dict:
    return copy.deepcopy(TAREFAS[tarefa]["estado"]())
