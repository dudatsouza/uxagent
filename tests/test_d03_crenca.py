"""D-03 (docs/depuracao.md): a pista do Histórico revê a crença mesmo depois de "Desfazer"."""
import random

from uxagent import tarefas
from uxagent.casafacil import CasaFacil
from uxagent.mecanismos import NEUTRO, Controlador


def test_historico_reve_crenca_depois_de_desfazer_na_versao_b():
    ui = CasaFacil(tarefas.estado_inicial("C1"), "B", True)
    ctl = Controlador({**NEUTRO, "p_atr": 1.0}, random.Random(0))
    ctl.inicio_tarefa(ui, "C1")
    assert ctl.x.crenca in ("eu_outra", "defeito")
    for a in ["desfazer_aviso", "nav:S5"]:          # o aviso some com o Desfazer
        out = ui.aplicar(a)
        ctl.apos_acao(ui, a, a, out)
    assert ui.s["aviso"] is None
    assert ctl.x.crenca == "rotina:economia"
    ui.aplicar("concluir")
    _, acoes, _ = ctl.transformar(ui, ui.render())
    assert "causa:rotina:economia" in acoes
