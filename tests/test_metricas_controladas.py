"""Conjunto 1 da Prova 3 (correção das métricas): registros controlados com resultado
calculado à mão. Cada teste documenta o valor esperado e por quê.

Só tarefas de CALIBRAÇÃO (C1, C2) são usadas aqui.
"""
import json

from uxagent.metricas import agregar, levenshtein, metricas_segmento
from uxagent.verificador import segmentar, verificar_segmento

CAUSA = "causa:rotina:economia"


def test_c1_sucesso_caminho_minimo(rodar_script):
    seg = rodar_script("C1", "A", ["alternar:luz_sala", "nav:S5", "concluir", CAUSA, "confirmar"])
    m = metricas_segmento(seg)
    # 5 ações = A_min (5) -> X = 1,0; sequência igual a um caminho admissível -> D = 0
    assert m["sucesso"] == 1 and m["A"] == 5 and m["X"] == 1.0 and m["D"] == 0.0
    assert m["U"] == 0 and m["err_ATR"] == 0 and m["err_OMI"] == 0
    # oportunidades: ATR 1; ACT 0 (não visitou S3); SLP = toques com vizinho (só o interruptor) = 1
    assert (m["op_ATR"], m["op_ACT"], m["op_SLP"], m["op_OMI"]) == (1, 0, 1, 1)


def test_c1_causa_errada_e_atr(rodar_script):
    seg = rodar_script("C1", "A", ["alternar:luz_sala", "concluir", "causa:eu_outra", "confirmar"])
    v = verificar_segmento(seg)
    assert v["sucesso"] is False
    assert [e["categoria"] for e in v["erros"]] == ["E-ATR"]
    assert "Para mim está bom" in [t["etiqueta"] for t in v["mac"]]


def test_c1_conclui_sem_acender_e_omi(rodar_script):
    seg = rodar_script("C1", "A", ["nav:S5", "concluir", CAUSA, "confirmar"])
    v = verificar_segmento(seg)
    assert v["sucesso"] is False
    assert [e["categoria"] for e in v["erros"]] == ["E-OMI"]


def test_c1_nao_sei_nao_e_e_atr_mas_e_fracasso(rodar_script):
    seg = rodar_script("C1", "A", ["alternar:luz_sala", "concluir", "causa:nao_sei", "confirmar"])
    v = verificar_segmento(seg)
    assert v["sucesso"] is False and v["erros"] == []


def test_ce2_confirmar_sem_resposta_nao_encerra(rodar_script):
    seg = rodar_script("C1", "A", ["alternar:luz_sala", "concluir", "confirmar", "confirmar",
                                   CAUSA, "confirmar"])
    tipos = [e["event_type"] for e in seg]
    assert tipos.count("dialog_shown") == 2          # CE2 duas vezes
    v = verificar_segmento(seg)
    assert v["sucesso"] is True
    assert "Por que não funciona?" in [t["etiqueta"] for t in v["mac"]]
    assert metricas_segmento(seg)["A"] == 6


def test_uso_de_suporte_por_camada(rodar_script):
    # Ajuda (1 abertura de S6; abrir tópico dentro de S6 não conta) + dica local em S3 (1)
    seg = rodar_script("C2", "A", ["nav:S6", "topico:H8", "voltar_ajuda", "nav:S2",
                                   "abrir:bom_dia", "dica", "fechar_dica", "pausar_retomar",
                                   "concluir", "confirmar"])
    m = metricas_segmento(seg)
    assert (m["U"], m["U_ajuda"], m["U_dica"], m["U_por_que"]) == (2, 1, 1, 0)
    assert m["U_pre"] == 1 and m["sucesso"] == 1
    assert m["A"] == 10 and m["X"] == 2.0
    etiquetas = [t["etiqueta"] for t in verificar_segmento(seg)["mac"]]
    assert "Socorro!" in etiquetas and "O que é isto?" in etiquetas


def test_exclusao_confirmada_e_act_e_desfeita(rodar_script):
    seg = rodar_script("C2", "A", ["nav:S2", "abrir:bom_dia", "excluir", "al_excluir",
                                   "desfazer_exclusao", "abrir:bom_dia", "pausar_retomar",
                                   "concluir", "confirmar"])
    v = verificar_segmento(seg)
    assert v["sucesso"] is True                       # recuperada pela RA
    assert [e["categoria"] for e in v["erros"]] == ["E-ACT"]
    assert "Epa!" in [t["etiqueta"] for t in v["mac"]]


def test_alerta_cancelado_nao_e_erro(rodar_script):
    seg = rodar_script("C2", "A", ["nav:S2", "abrir:bom_dia", "excluir", "al_cancelar",
                                   "pausar_retomar", "concluir", "confirmar"])
    v = verificar_segmento(seg)
    assert v["erros"] == [] and v["sucesso"] is True
    assert "Epa!" in [t["etiqueta"] for t in v["mac"]]


def test_pausar_rotina_errada_e_act(rodar_script):
    seg = rodar_script("C2", "A", ["nav:S2", "abrir:economia", "pausar_retomar", "concluir",
                                   "confirmar"])
    v = verificar_segmento(seg)
    assert v["sucesso"] is False
    assert sorted(e["categoria"] for e in v["erros"]) == ["E-ACT", "E-OMI"]


def test_desistencia(rodar_script):
    seg = rodar_script("C2", "A", ["nav:S2", "desistir"])
    m = metricas_segmento(seg)
    assert m["situacao"] == "valido" and m["sucesso"] == 0 and m["fim"] == "desistencia"
    assert "Desisto" in m["mac"]


def test_limite_de_acoes(rodar_script):
    # limite = 3 x A_min = 15 em C2; alternar o mesmo interruptor 20 vezes
    seg = rodar_script("C2", "A", ["alternar:cafeteira"] * 20)
    m = metricas_segmento(seg)
    assert m["fim"] == "limite" and m["A"] == 15 and m["sucesso"] == 0


def test_registro_incompleto_e_desconhecido(rodar_script):
    seg = rodar_script("C1", "A", ["alternar:luz_sala", "nav:S5"])
    truncado = [e for e in seg if e["event_type"] != "task_end"]
    m = metricas_segmento(truncado)
    assert m["situacao"] == "desconhecido" and m["sucesso"] == "" and m["D"] == ""
    agg = agregar([m])[0]
    assert agg["n_desconhecidas"] == 1 and agg["S"] == "ND"


def test_falha_tecnica_e_indeterminada():
    from uxagent.registro import Registro
    import tempfile, pathlib
    d = pathlib.Path(tempfile.mkdtemp())
    reg = Registro(d / "f.jsonl", {"session_id": "f", "subject_id": "x", "persona_id": "p#1",
                                    "config_hash": "h", "synthetic": True, "group": "P",
                                    "condition": "A", "llm_model": "m"})
    reg.com(task_id="C1", task_set="cal", step=0)
    reg.evento("task_start", {})
    reg.evento("technical_failure", {"codigo": "F-API"})
    reg.evento("task_end", {"resultado": "indeterminado", "n_acoes": 0, "estado_final": {
        "aparelhos": {"luz_sala": False}, "rotinas": {}, "resposta_causa": None}})
    reg.fechar()
    from uxagent.registro import ler
    seg = segmentar(ler(d / "f.jsonl"))[0]
    m = metricas_segmento(seg)
    agg = agregar([m])[0]
    assert m["situacao"] == "indeterminado" and agg["n_indeterminadas"] == 1 and agg["S"] == "ND"


def test_taxa_de_sucesso_agregada():
    # 3 válidas (2 sucessos) + 1 indeterminada -> S = 2/3
    base = {"task_id": "C1", "condition": "A", "group": "P", "persona_id": "x#1",
            "llm_model": "m", "synthetic": True, "A": 5, "X": 1.0, "D": 0.0, "U": 0,
            "U_pre": 0, "A_rej": 0, **{f"err_{k}": 0 for k in "ATR ACT SLP OMI".split()},
            **{f"op_{k}": 1 for k in "ATR ACT SLP OMI".split()}}
    linhas = [dict(base, situacao="valido", sucesso=1), dict(base, situacao="valido", sucesso=1),
              dict(base, situacao="valido", sucesso=0, err_ATR=1),
              dict(base, situacao="indeterminado", sucesso="")]
    agg = agregar(linhas)[0]
    assert agg["S"] == round(2 / 3, 3) and agg["n_indeterminadas"] == 1
    assert agg["R_ATR"] == 0.25          # 1 erro / 4 oportunidades


def test_levenshtein():
    assert levenshtein(list("abc"), list("abc")) == 0
    assert levenshtein(list("abc"), list("axc")) == 1
    assert levenshtein([], list("ab")) == 2
