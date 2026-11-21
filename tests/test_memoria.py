"""Memória de trabalho em x_t (D-01 e D-02, docs/depuracao.md). Só tarefas de calibração."""


def _prompts(seg):
    return [e["data"]["prompt_usuario"] for e in seg if e["event_type"] == "observation_delivered"]


def test_memoria_registra_acoes_e_telas_abertas(rodar_script):
    seg = rodar_script("C1", "A", ["nav:S5", "nav:S1", "desistir"])
    ultimo = _prompts(seg)[-1]
    assert "O que você já fez nesta tarefa" in ultimo
    assert "tocou \"Histórico\" (abriu a tela \"Histórico\")" in ultimo


def test_memoria_registra_o_retorno_visivel_da_acao(rodar_script):
    seg = rodar_script("C2", "A", ["nav:S2", "abrir:bom_dia", "pausar_retomar", "concluir",
                                   "confirmar"])
    no_s7 = _prompts(seg)[-1]
    assert "duas barras verticais, sem texto (a tela mostrou: \"Situação\": \"Ativa\" -> " \
           "\"Pausada\")" in no_s7


def test_memoria_nao_mostra_identificadores_internos(rodar_script):
    seg = rodar_script("C2", "A", ["nav:S2", "abrir:bom_dia", "pausar_retomar", "concluir",
                                   "confirmar"])
    for p in _prompts(seg):
        assert "pausar_retomar" not in p and "bom_dia" not in p and "nav:" not in p
