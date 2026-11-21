"""Visualizador: o replay refaz exatamente a execução gravada, e o modo manual só aceita C1/C2."""
import pytest

from uxagent import visual
from uxagent.executor import rodar_sessao
from uxagent.registro import ler

from .conftest import NEUTRO


def test_replay_reproduz_estado_final_gravado(tmp_path, monkeypatch):
    monkeypatch.setattr(visual, "DADOS", tmp_path)
    roteiro = ["nav:S2", "abrir:bom_dia", "pausar_retomar", "concluir", "confirmar"]
    p = rodar_sessao(NEUTRO, "script", "A", ["C2"], 1, tmp_path / "s", roteiros={"C2": roteiro})
    r = visual.replay(str(p.relative_to(tmp_path)), "C2")
    assert [q["executada"] for q in r["quadros"]] == roteiro
    gravado = [e for e in ler(p) if e["event_type"] == "task_end"][0]["data"]["estado_final"]
    assert r["final"]["tela"] == gravado["tela"]
    assert r["verificador"]["sucesso"] is True


def test_replay_recusa_validacao_e_caminho_fora_de_dados(tmp_path, monkeypatch):
    monkeypatch.setattr(visual, "DADOS", tmp_path)
    with pytest.raises(ValueError):
        visual.replay("../../etc/passwd", "C1")
    with pytest.raises(ValueError):
        visual.replay("qualquer.jsonl", "V1")


def test_modo_manual_so_calibracao_e_verifica_pelo_estado():
    m = visual.SessaoManual()
    with pytest.raises(ValueError):
        m.nova("V2", "A")
    m.nova("C2", "A")
    for a in ["nav:S2", "abrir:bom_dia", "pausar_retomar", "concluir"]:
        m.tocar(a)
    r = m.tocar("confirmar")
    assert r["fim"] == "concluida" and r["sucesso"] is True
