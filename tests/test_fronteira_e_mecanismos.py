"""Fronteira de informação, interface e mecanismos M1--M6."""
import ast
import random
import re
from pathlib import Path

import pytest

from uxagent import observacao, tarefas
from uxagent.casafacil import CasaFacil
from uxagent.executor import rodar_sessao
from uxagent.mecanismos import NEUTRO, Controlador, amostrar
from uxagent.politicas import Contexto, FalhaTecnica

PKG = Path(__file__).resolve().parent.parent / "uxagent"


def _imports(arquivo):
    arvore = ast.parse((PKG / arquivo).read_text())
    nomes = set()
    for n in ast.walk(arvore):
        if isinstance(n, ast.ImportFrom):
            nomes.add(n.module or "")
            nomes.update(a.name for a in n.names)
        elif isinstance(n, ast.Import):
            nomes.update(a.name for a in n.names)
    return nomes


def test_observacao_nao_importa_modelos_do_analista():
    assert not {"analista", "tarefas", "verificador"} & _imports("observacao.py")


def test_llmpolicy_nao_usa_analista():
    fonte = (PKG / "politicas.py").read_text()
    classe = fonte[fonte.index("class LLMPolicy"):fonte.index("class AleatoriaPolicy")]
    assert "analista" not in classe and "sucesso" not in classe


INTERNOS = re.compile(r"luz_sala|ar_quarto|tomada_ventilador|bom_dia|economia\b|pausar_retomar|"
                      r"rotina:[a-z]|causa:[a-z]|nav:|\bS[1-9]\b|estado_alvo|A_min|HTA|CTT|GOMS")


def _todas_as_telas(versao):
    """Percorre as telas de C1/C2 e devolve as observações montadas."""
    obs = []
    for tid, roteiro in [("C1", ["porque" if versao == "B" else "nav:S5", "nav:S6", "topico:H2",
                                 "voltar_ajuda", "concluir", "confirmar"]),
                         ("C2", ["nav:S2", "abrir:bom_dia", "dica", "fechar_dica", "excluir",
                                 "al_cancelar", "editar", "caixa:cafeteira", "cancelar_edicao"])]:
        ui = CasaFacil(tarefas.estado_inicial(tid), versao, tarefas.TAREFAS[tid]["perguntar_causa"])
        for passo in [None] + roteiro:
            if passo:
                ui.aplicar(passo)
            els = ui.render()
            titulo = ui.s["rotinas"][ui.s["rotina_aberta"]]["nome"] if ui.tela == "S3" else None
            texto, oferta = observacao.montar(ui.tela, titulo, els, ui.acoes_disponiveis(), [])
            obs.append((ui.tela, texto))
    return obs


@pytest.mark.parametrize("versao", ["A", "B"])
def test_observacao_sem_identificadores_internos(versao):
    for tela, texto in _todas_as_telas(versao):
        assert not INTERNOS.search(texto), (tela, INTERNOS.search(texto).group(), texto)


def test_icones_descritos_pela_forma_e_nao_pela_funcao():
    s3 = [t for tela, t in _todas_as_telas("A") if tela == "S3"][0]
    assert "duas barras verticais" in s3 and "lápis" in s3
    corpo = s3.split("Ações disponíveis:")[0]
    assert "Pausar" not in corpo and "Editar" not in corpo


def test_origem_so_aparece_no_historico_na_versao_a():
    ui = CasaFacil(tarefas.estado_inicial("C1"), "A", True)
    texto, _ = observacao.montar("S1", None, ui.render(), ui.acoes_disponiveis(), [])
    assert "Economia" not in texto and "Por quê" not in texto


def test_validacao_bloqueada_sem_congelamento(tmp_path):
    cfg = Path(__file__).resolve().parent.parent / "configs" / "neutro.yaml"
    with pytest.raises(PermissionError):
        rodar_sessao(cfg, "regras", "A", ["V1"], 1, tmp_path, permitir_validacao=True)
    with pytest.raises(PermissionError):
        rodar_sessao(cfg, "regras", "A", ["C1", "V2"], 1, tmp_path)


# ------------------------------------------------------------------ interface
def test_pa_horario_preso_em_23h():
    ui = CasaFacil(tarefas.estado_inicial("C2"), "A", False)
    for a in ["nav:S2", "abrir:bom_dia", "editar"]:
        ui.aplicar(a)
    for _ in range(30):
        ui.aplicar("mais")
    assert ui.s["edicao"]["horario"] == 23


def test_ce1_ao_cancelar_com_alteracoes_e_ajuda_volta_a_origem():
    ui = CasaFacil(tarefas.estado_inicial("C2"), "A", False)
    for a in ["nav:S2", "abrir:bom_dia", "editar", "caixa:cafeteira", "cancelar_edicao"]:
        ui.aplicar(a)
    assert ui.tela == "CE1"
    ui.aplicar("ce1_sair")
    assert ui.tela == "S3" and "cafeteira" in ui.s["rotinas"]["bom_dia"]["aparelhos"]
    ui.aplicar("nav:S6")
    ui.aplicar("voltar_ajuda")
    assert ui.tela == "S3"


# ----------------------------------------------------------------- mecanismos
def test_amostrador_respeita_faixas_e_chaves():
    import yaml
    cfg = yaml.safe_load((PKG.parent / "configs" / "persona_lucia.yaml").read_text())
    for s in range(200):
        t = amostrar(cfg, random.Random(s))
        assert 0.2 <= t["p_atr"] <= 0.8 and 0.01 <= t["p_slip"] <= 0.15
        assert 0.5 <= t["r_nota"] <= 1.0
    cfg["mecanismos"]["M3"] = False
    assert amostrar(cfg, random.Random(0))["p_slip"] == 0.0


def _ctl(**kw):
    return Controlador({**NEUTRO, **kw}, random.Random(0))


def test_m3_deslize_executa_vizinho():
    ui = CasaFacil(tarefas.estado_inicial("C1"), "A", True)
    els = ui.render()
    exe = _ctl(p_slip=1.0).deslize("alternar:luz_sala", els, ui.acoes_disponiveis())
    assert exe == "alternar:ar_quarto"


def test_m2_oculta_icone_ate_ler_a_ajuda():
    ui = CasaFacil(tarefas.estado_inicial("C2"), "A", False)
    for a in ["nav:S2", "abrir:bom_dia"]:
        ui.aplicar(a)
    ctl = _ctl(q_rot=1.0)
    els, acoes, ap = ctl.transformar(ui, ui.render())
    assert "pausar_retomar" not in acoes and "editar" not in acoes
    assert any(e.texto == "[ícone sem nome]" for e in els)
    out = ui.aplicar("dica")
    ctl.apos_acao(ui, "dica", "?", out)
    ui.aplicar("fechar_dica")
    _, acoes, _ = ctl.transformar(ui, ui.render())
    assert "pausar_retomar" in acoes


def test_m4_hesita_em_acao_destrutiva():
    ctl = _ctl(p_hes=1.0)
    assert ctl.hesitar("excluir", ["excluir", "nav:S6"]) == "nav:S6"
    assert ctl.hesitar("excluir", ["excluir", "nav:S6"]) == "nav:S6"
    assert ctl.hesitar("excluir", ["excluir", "nav:S6"]) is None     # máximo de 2


def test_m1_e_m6_crenca_e_filtro_da_causa():
    ui = CasaFacil(tarefas.estado_inicial("C1"), "B", True)
    ctl = _ctl(p_atr=1.0, c_comp=1.0)
    ctl.inicio_tarefa(ui, "C1")
    assert ctl.x.crenca in ("eu_outra", "defeito")
    ui.aplicar("concluir")
    _, acoes, _ = ctl.transformar(ui, ui.render())
    assert "causa:rotina:economia" not in acoes and "causa:nao_sei" in acoes
    ui.aplicar("voltar_concluir")
    out = ui.aplicar("porque")
    ctl.apos_acao(ui, "porque", "Por quê?", out)
    assert ctl.x.crenca == "rotina:economia"


def test_m5_nota_escrita_e_mostrada_na_tarefa_seguinte():
    ctl = _ctl(r_nota=1.0)
    ui = CasaFacil(tarefas.estado_inicial("C2"), "A", False)
    ctl.inicio_tarefa(ui, "C2")
    for a in ["nav:S2", "abrir:bom_dia", "pausar_retomar"]:
        out = ui.aplicar(a)
        ctl.apos_acao(ui, a, a, out)
    assert len(ctl.x.caderno) == 1
    assert ctl.notas_visiveis("C2")[0] == []          # não na mesma tarefa
    assert ctl.notas_visiveis("C1")[0] != []


# ---------------------------------------------------------------- LLMPolicy
class _Resp:
    def __init__(self, texto, stop="end_turn"):
        self.model = "claude-sonnet-5-5"
        self.stop_reason = stop
        self.usage = type("U", (), {"input_tokens": 10, "output_tokens": 5})()
        self.content = [type("B", (), {"type": "text", "text": texto})()]


def _politica(respostas, chamadas):
    from uxagent.politicas import LLMPolicy
    pol = LLMPolicy({"modelo": "claude-sonnet-5-5", "effort": "low", "fallbacks": None})

    def criar(**kw):
        chamadas.append(kw)
        return respostas.pop(0)
    pol.client = type("C", (), {"messages": type("M", (), {"create": staticmethod(criar)})()})()
    return pol


def test_llm_saida_estruturada_restrita_a_lista():
    chamadas = []
    pol = _politica([_Resp('{"acao": 2, "justificativa": "ok"}')], chamadas)
    esc = pol.escolher(Contexto("sistema", "tela", 3, ["a", "b", "c"]))
    assert esc.indice == 2
    fmt = chamadas[0]["output_config"]["format"]["schema"]["properties"]["acao"]
    assert fmt["enum"] == [1, 2, 3]
    assert "temperature" not in chamadas[0]
    # o contexto enviado é só sistema + mensagem do usuário (sem histórico)
    assert len(chamadas[0]["messages"]) == 1


def test_llm_formato_invalido_gera_f_fmt():
    pol = _politica([_Resp("talvez a 2"), _Resp('{"acao": 9, "justificativa": ""}')], [])
    with pytest.raises(FalhaTecnica) as e:
        pol.escolher(Contexto("s", "u", 3, ["a", "b", "c"]))
    assert e.value.codigo == "F-FMT"


def test_llm_recusa_gera_f_ref():
    pol = _politica([_Resp("", stop="refusal")], [])
    with pytest.raises(FalhaTecnica) as e:
        pol.escolher(Contexto("s", "u", 3, ["a", "b", "c"]))
    assert e.value.codigo == "F-REF"
