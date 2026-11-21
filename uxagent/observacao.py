"""Tradutor de observação: tela -> texto o_t (regras da Seção III do caderno E1).

Regras: texto literal entre aspas; ícones pela forma; só a tela atual; signos
dinâmicos como "Mudou na tela"; metalinguísticos só depois de abertos; ações
numeradas na ordem visual; nada do analista (HTA, CTT, GOMS, A_min, sucesso).

Este módulo não importa ``analista`` nem ``tarefas`` (verificado em teste).
"""
from __future__ import annotations

from .casafacil import Elemento

TITULOS = {"S1": "Início", "S2": "Rotinas", "S4": "Editar rotina", "S5": "Histórico",
           "S6": "Ajuda", "S7": "Concluir", "S8": "Por quê?", "S9": "Dica",
           "AL": "Mensagem do aplicativo", "CE1": "Mensagem do aplicativo"}
BARRA_INFERIOR = {"nav:S1", "nav:S2", "nav:S5", "nav:S6"}
BARRA_SUPERIOR = {"concluir", "desistir"}


def _desc(e: Elemento) -> str:
    """Descrição verbal de um elemento, sem significado que a tela não mostre."""
    if e.papel == "texto":
        return f"\"{e.texto}\""
    if e.papel == "interruptor":
        return f"interruptor \"{e.texto}\", com o texto \"{e.detalhe}\""
    if e.papel == "caixa":
        return f"caixa {e.detalhe}, \"{e.texto}\""
    if e.papel == "opcao":
        marca = " (selecionada)" if e.detalhe == "selecionada" else ""
        return f"opção \"{e.texto}\"{marca}"
    if e.papel == "item":
        return f"\"{e.texto}\"" + (f" — \"{e.detalhe}\"" if e.detalhe else "")
    if e.papel == "icone":
        return e.texto  # já é a descrição da forma (ou "[ícone sem nome]" após M2)
    return f"botão \"{e.texto}\""


def _chaves_dinamicas(els: list[Elemento]) -> dict[str, str]:
    """Signos cujo valor pode mudar na mesma tela."""
    out = {}
    for e in els:
        if e.detalhe is not None and e.papel in ("interruptor", "caixa", "item", "opcao"):
            out[f"{e.papel}:{e.texto}"] = str(e.detalhe)
        elif e.papel == "texto" and ":" in e.texto:
            k, v = e.texto.split(":", 1)
            if k in ("Situação", "Smart Schedule", "Aviso"):
                out[k] = v.strip()
    return out


def mudancas(anteriores: list[Elemento] | None, atuais: list[Elemento]) -> list[str]:
    if anteriores is None:
        return []
    a, b = _chaves_dinamicas(anteriores), _chaves_dinamicas(atuais)
    linhas = []
    for k, v in b.items():
        if k in a and a[k] != v:
            rotulo = k.split(":", 1)[1] if k.startswith(("interruptor:", "caixa:", "item:",
                                                          "opcao:")) else k
            linhas.append(f"Mudou na tela: \"{rotulo}\": \"{a[k]}\" -> \"{v}\"")
    for k in a:
        if k == "Aviso" and k not in b:
            linhas.append("Mudou na tela: o aviso sumiu")
    for k in b:
        if k == "Aviso" and k not in a:
            linhas.append(f"Mudou na tela: apareceu o aviso \"{b[k]}\"")
    return linhas


def montar(tela: str, titulo_rotina: str | None, elementos: list[Elemento],
           acoes_visiveis: list[str], mudou: list[str]) -> tuple[str, list[str]]:
    """Retorna (texto da observação, lista ordenada de ações internas oferecidas).

    ``acoes_visiveis`` é a lista de ações já filtrada pelos mecanismos (M1/M2/M6);
    a numeração segue a ordem visual.
    """
    titulo = titulo_rotina if tela == "S3" else TITULOS.get(tela, tela)
    linhas = [f"Tela: \"{titulo}\""]
    sup = [e for e in elementos if e.acao in BARRA_SUPERIOR]
    inf = [e for e in elementos if e.acao in BARRA_INFERIOR]
    corpo = [e for e in elementos if e.acao not in BARRA_SUPERIOR | BARRA_INFERIOR]
    if sup:
        linhas.append("Barra superior: " + ", ".join(f"\"{e.texto}\"" for e in sup))
    for e in corpo:
        linhas.append(_desc(e))
    if inf:
        linhas.append("Barra inferior: " + ", ".join(f"\"{e.texto}\"" for e in inf))
    linhas += mudou
    oferta = []
    linhas.append("Ações disponíveis:")
    for e in elementos:
        if e.acao and e.acao in acoes_visiveis and e.acao not in oferta:
            oferta.append(e.acao)
            linhas.append(f"[{len(oferta)}] tocar {_desc(e)}")
    return "\n".join(linhas), oferta
