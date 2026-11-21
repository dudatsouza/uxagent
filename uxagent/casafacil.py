"""Protótipo instrumentado CasaFácil (interface de teste).

Implementa a máquina de estados da Tabela XII do caderno E1: cenas S1--S9,
diálogos AL, CE1 e CE2, acesso ubíquo e processos do sistema. O estado é um
dicionário JSON-serializável, lido pelo verificador externo ao fim da tarefa.

Esta camada não conhece o agente nem os critérios de sucesso: ela só expõe a
tela atual (``render``) e aplica ações (``aplicar``).
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field

UI_VERSION = "casafacil-1.0"

APARELHOS_ORDEM = ["luz_sala", "ar_quarto", "cafeteira", "tomada_ventilador"]
NOMES_APARELHOS = {
    "luz_sala": "Luz da sala",
    "ar_quarto": "Ar-condicionado do quarto",
    "cafeteira": "Cafeteira",
    "tomada_ventilador": "Tomada do ventilador",
}
GENERO_FEM = {"luz_sala": True, "ar_quarto": False, "cafeteira": True, "tomada_ventilador": True}

# --------------------------------------------------------------------------
# Textos de ajuda (Tabela XV do caderno). Iguais para pessoas e agente.
# --------------------------------------------------------------------------
TOPICOS_AJUDA = {
    "H1": ("O que é uma rotina?",
           "Uma rotina é uma regra que o aplicativo segue sozinho: num horário ou numa situação, "
           "ela liga ou desliga aparelhos. Quem cria a rotina escolhe quando ela age. "
           "As rotinas ficam na aba Rotinas."),
    "H2": ("O que faz o botão de duas barras?",
           "É o botão Pausar. Uma rotina pausada fica guardada, mas não age até ser retomada. "
           "Quando ela está pausada, o botão mostra um triângulo: é o Retomar."),
    "H3": ("O que faz o botão de lápis?",
           "É o botão Editar. Ele abre a rotina para mudar o horário e os aparelhos incluídos."),
    "H4": ("O que é \"Smart Schedule\"?",
           "É o horário em que a rotina age. Toque em + ou - para mudar de hora em hora, "
           "de 00h a 23h. Depois, toque em Salvar."),
    "H5": ("Como saber quem mudou um aparelho?",
           "Abra a aba Histórico. Cada linha mostra a hora, o aparelho, o que mudou e quem mudou: "
           "\"Você\" ou o nome da rotina."),
    "H6": ("Como fazer uma rotina parar de agir por um tempo?",
           "Abra Rotinas, toque no nome da rotina e toque no botão de duas barras (Pausar). "
           "Para ela voltar a agir, toque no triângulo (Retomar)."),
    "H7": ("Pausar, editar ou excluir: qual usar?",
           "Pausar: a rotina para de agir, mas fica guardada. Editar: muda o horário ou os aparelhos. "
           "Excluir: apaga a rotina; o aplicativo pede confirmação e, logo depois, ainda mostra "
           "\"Desfazer\" na lista de rotinas."),
    "H8": ("Onde ficam as rotinas?",
           "Na aba Rotinas, na barra de baixo, que aparece em todas as telas."),
    "H9": ("Como desfazer uma mudança?",
           "Se você ligou ou desligou um aparelho sem querer, toque no interruptor de novo. "
           "Se pausou uma rotina, toque em Retomar. Se excluiu uma rotina, toque em Desfazer "
           "na lista de rotinas."),
    "H10": ("O que são Concluir e Desistir?",
            "Concluir: avisa que você terminou o que foi pedido. Desistir: encerra sem terminar."),
}
ACRESCIMO_B = {
    "H5": " Você também pode tocar em \"Por quê?\" no aviso da tela Início.",
    "H9": " Se uma rotina mudou um aparelho, toque em Desfazer no aviso.",
}
DICA = {
    "S3": ("Botão de duas barras: Pausar (a rotina para de agir, mas fica guardada). "
           "Triângulo: Retomar. Lápis: Editar (muda horário e aparelhos). "
           "Excluir rotina: apaga a rotina (o aplicativo pede confirmação)."),
    "S4": ("Smart Schedule: horário em que a rotina age; use + e - (de 00h a 23h). "
           "Caixas: aparelhos que a rotina liga ou desliga. Salvar guarda as mudanças."),
}


def texto_ajuda(topico: str, versao: str) -> str:
    texto = TOPICOS_AJUDA[topico][1]
    if versao == "B" and topico in ACRESCIMO_B:
        texto += ACRESCIMO_B[topico]
    return texto


def help_hash() -> str:
    payload = json.dumps({"topicos": TOPICOS_AJUDA, "b": ACRESCIMO_B, "dica": DICA},
                         ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


# --------------------------------------------------------------------------
# Elementos de tela
# --------------------------------------------------------------------------
@dataclass
class Elemento:
    """Um signo visível. ``acao`` é o identificador interno (nunca vai ao agente)."""
    papel: str                 # texto, botao, interruptor, caixa, opcao, icone, item
    texto: str                 # texto literal visível, ou descrição da forma do ícone
    acao: str | None = None    # id interno da ação; None se não acionável
    vizinhos: list[str] = field(default_factory=list)  # ações adjacentes (M3)
    icone: str | None = None   # "pausa", "retomar", "lapis": candidatos a M2
    rotulo_estrangeiro: bool = False  # controles sob "Smart Schedule" (M2)
    detalhe: str | None = None # estado visível do controle (ex.: marcada)


def _fmt_hora(minutos: int) -> str:
    return f"{minutos // 60:02d}h{minutos % 60:02d}"


def _estado_txt(ap: str, ligado: bool) -> str:
    if GENERO_FEM[ap]:
        return "Ligada" if ligado else "Desligada"
    return "Ligado" if ligado else "Desligado"


class CasaFacil:
    """Interface instrumentada. Toda mudança passa por ``aplicar``."""

    def __init__(self, estado_inicial: dict, versao: str, perguntar_causa: bool):
        if versao not in ("A", "B"):
            raise ValueError("versao deve ser A ou B")
        self.versao = versao
        self.perguntar_causa = perguntar_causa
        self.s = copy.deepcopy(estado_inicial)
        self.s.update({
            "versao": versao, "tela": "S1", "pilha": [], "rotina_aberta": None,
            "edicao": None, "dialogo": None, "ce2": False, "faixa_excluida": None,
            "resposta_causa": None, "fim": None, "topico": None,
            "excluidas": self.s.get("excluidas", {}),
            "pendentes": self.s.get("pendentes", []),
        })

    # ---------------------------------------------------------------- util
    def snapshot(self) -> dict:
        return copy.deepcopy(self.s)

    def state_hash(self) -> str:
        return hashlib.sha256(json.dumps(self.s, sort_keys=True, ensure_ascii=False)
                              .encode()).hexdigest()[:12]

    @property
    def tela(self) -> str:
        if self.s["dialogo"]:
            return self.s["dialogo"]["tipo"]
        return self.s["tela"]

    def _rot(self, rid: str) -> dict:
        return self.s["rotinas"][rid]

    def _regra(self, rid: str) -> str:
        r = self._rot(rid)
        acoes = [f"{NOMES_APARELHOS[a]}" for a in r["aparelhos"]]
        verbo = "ligar" if r["acao"] == "ligar" else "desligar"
        alvo = " e ".join(acoes) if acoes else "(nenhum aparelho)"
        if r.get("horario") is not None:
            cond = f"for {r['horario']:02d}h00"
        else:
            cond = r["condicao"]
        return f"Se {cond}, então {verbo} {alvo}"

    # -------------------------------------------------------------- render
    def render(self) -> list[Elemento]:
        """Elementos visíveis na ordem visual (cima-baixo, esquerda-direita)."""
        s = self.s
        if s["dialogo"]:
            d = s["dialogo"]
            if d["tipo"] == "AL":
                nome = self._rot(d["rotina"])["nome"]
                return [Elemento("texto", f"Excluir a rotina \"{nome}\"? Ela sai da lista de rotinas."),
                        Elemento("botao", "Cancelar", "al_cancelar"),
                        Elemento("botao", "Excluir", "al_excluir")]
            if d["tipo"] == "CE1":
                return [Elemento("texto", "Você mudou esta rotina. Salvar as mudanças?"),
                        Elemento("botao", "Salvar", "ce1_salvar"),
                        Elemento("botao", "Sair sem salvar", "ce1_sair")]
        els: list[Elemento] = []
        tela = s["tela"]
        # barra superior
        if tela != "S7":
            els.append(Elemento("botao", "Concluir", "concluir"))
        els.append(Elemento("botao", "Desistir", "desistir"))
        getattr(self, f"_render_{tela}")(els)
        # barra inferior
        els += [Elemento("aba", "Início", "nav:S1"), Elemento("aba", "Rotinas", "nav:S2"),
                Elemento("aba", "Histórico", "nav:S5"), Elemento("aba", "Ajuda", "nav:S6")]
        return els

    def _aviso_txt(self) -> str | None:
        a = self.s.get("aviso")
        if not a:
            return None
        ap = a["aparelho"]
        return f"{NOMES_APARELHOS[ap]}: {_estado_txt(ap, a['ligado']).lower()} às {a['hora']}"

    def _render_S1(self, els):
        aviso = self._aviso_txt()
        if aviso:
            els.append(Elemento("texto", f"Aviso: {aviso}"))
            if self.versao == "B":
                els.append(Elemento("botao", "Por quê?", "porque", vizinhos=["desfazer_aviso"]))
                els.append(Elemento("botao", "Desfazer", "desfazer_aviso", vizinhos=["porque"]))
        els.append(Elemento("texto", "Meus aparelhos"))
        ids = [f"alternar:{a}" for a in APARELHOS_ORDEM]
        for i, ap in enumerate(APARELHOS_ORDEM):
            viz = [ids[j] for j in (i - 1, i + 1) if 0 <= j < len(ids)]
            ligado = self.s["aparelhos"][ap]
            els.append(Elemento("interruptor", NOMES_APARELHOS[ap], ids[i], vizinhos=viz,
                                detalhe=_estado_txt(ap, ligado)))

    def _render_S8(self, els):
        aviso = self._aviso_txt()
        if aviso:
            els.append(Elemento("texto", f"Aviso: {aviso}"))
        a = self.s.get("aviso_explicado") or self.s.get("aviso")
        if a:
            r = self._rot(a["rotina"])
            verbo = "ligou" if a["ligado"] else "desligou"
            els.append(Elemento("texto",
                                f"A rotina \"{r['nome']}\" {verbo} {NOMES_APARELHOS[a['aparelho']]} "
                                f"às {a['hora']} porque {a['motivo']}."))
        if self.s.get("aviso"):
            els.append(Elemento("botao", "Desfazer", "desfazer_aviso", vizinhos=["ir_rotina"]))
        els.append(Elemento("botao", "Ir para a rotina", "ir_rotina",
                            vizinhos=["desfazer_aviso"] if self.s.get("aviso") else []))
        els.append(Elemento("botao", "Fechar", "fechar_painel"))

    def _render_S2(self, els):
        els.append(Elemento("texto", "Rotinas"))
        for rid, r in self.s["rotinas"].items():
            els.append(Elemento("item", r["nome"], f"abrir:{rid}", detalhe=r["situacao"]))
        fx = self.s["faixa_excluida"]
        if fx:
            nome = self.s["excluidas"][fx]["nome"]
            els.append(Elemento("texto", f"Rotina \"{nome}\" excluída."))
            els.append(Elemento("botao", "Desfazer", "desfazer_exclusao"))

    def _render_S3(self, els):
        rid = self.s["rotina_aberta"]
        r = self._rot(rid)
        els.append(Elemento("botao", "Voltar", "voltar_S2"))
        els.append(Elemento("texto", r["nome"]))
        els.append(Elemento("texto", f"Situação: {r['situacao']}"))
        els.append(Elemento("texto", f"Regra: {self._regra(rid)}"))
        if r["situacao"] == "Ativa":
            els.append(Elemento("icone", "botão com ícone de duas barras verticais, sem texto",
                                "pausar_retomar", vizinhos=["editar"], icone="pausa"))
        else:
            els.append(Elemento("icone", "botão com ícone de triângulo, sem texto",
                                "pausar_retomar", vizinhos=["editar"], icone="retomar"))
        els.append(Elemento("icone", "botão com ícone de lápis, sem texto", "editar",
                            vizinhos=["pausar_retomar"], icone="lapis"))
        els.append(Elemento("botao", "?", "dica"))
        els.append(Elemento("botao", "Excluir rotina", "excluir"))

    def _render_S4(self, els):
        e = self.s["edicao"]
        els.append(Elemento("botao", "Cancelar", "cancelar_edicao"))
        if e["horario"] is not None:
            els.append(Elemento("texto", f"Smart Schedule: {e['horario']:02d}h00"))
            els.append(Elemento("botao", "-", "menos", vizinhos=["mais"], rotulo_estrangeiro=True))
            els.append(Elemento("botao", "+", "mais", vizinhos=["menos"], rotulo_estrangeiro=True))
            els.append(Elemento("texto", "de 00h a 23h"))
        els.append(Elemento("texto", "Aparelhos"))
        ids = [f"caixa:{a}" for a in APARELHOS_ORDEM]
        for i, ap in enumerate(APARELHOS_ORDEM):
            viz = [ids[j] for j in (i - 1, i + 1) if 0 <= j < len(ids)]
            marcada = ap in e["aparelhos"]
            els.append(Elemento("caixa", NOMES_APARELHOS[ap], ids[i], vizinhos=viz,
                                detalhe="com marca de seleção" if marcada else "vazia"))
        els.append(Elemento("botao", "?", "dica"))
        els.append(Elemento("botao", "Salvar", "salvar"))

    def _render_S5(self, els):
        els.append(Elemento("texto", "Histórico"))
        for linha in reversed(self.s["historico"]):
            ap = linha["aparelho"]
            orig = "Você" if linha["origem"] == "pessoa" else \
                f"Rotina {self.s['nomes_rotinas'][linha['origem']]}"
            els.append(Elemento("texto", f"{linha['hora']} · {NOMES_APARELHOS[ap]} · "
                                          f"{_estado_txt(ap, linha['ligado'])} · {orig}"))

    def _render_S6(self, els):
        els.append(Elemento("texto", "Ajuda"))
        for tid, (perg, _) in TOPICOS_AJUDA.items():
            els.append(Elemento("item", perg, f"topico:{tid}"))
            if self.s["topico"] == tid:
                els.append(Elemento("texto", texto_ajuda(tid, self.versao)))
        els.append(Elemento("botao", "Voltar", "voltar_ajuda"))

    def _render_S9(self, els):
        origem = self.s["pilha"][-1]["tela"] if self.s["pilha"] else "S3"
        els.append(Elemento("texto", DICA.get(origem, DICA["S3"])))
        els.append(Elemento("botao", "Fechar", "fechar_dica"))

    def _render_S7(self, els):
        if self.perguntar_causa:
            els.append(Elemento("texto", "Por que isso aconteceu?"))
            for oid, txt in self.opcoes_causa():
                marc = "selecionada" if self.s["resposta_causa"] == oid else None
                els.append(Elemento("opcao", txt, f"causa:{oid}", detalhe=marc))
        else:
            els.append(Elemento("texto", "Você terminou?"))
        if self.s["ce2"]:
            els.append(Elemento("texto", "Escolha uma resposta antes de confirmar."))
        els.append(Elemento("botao", "Confirmar", "confirmar"))
        els.append(Elemento("botao", "Voltar", "voltar_concluir"))

    def opcoes_causa(self) -> list[tuple[str, str]]:
        ops = [("eu_outra", "Eu ou outra pessoa"), ("defeito", "Defeito")]
        ops += [(f"rotina:{rid}", f"Rotina {r['nome']}") for rid, r in self.s["rotinas"].items()]
        ops.append(("nao_sei", "Não sei"))
        return ops

    def acoes_disponiveis(self) -> list[str]:
        return [e.acao for e in self.render() if e.acao]

    # ------------------------------------------------------------- aplicar
    def aplicar(self, acao: str) -> dict:
        """Aplica uma ação válida. Retorna dict com mudanças, diálogos e suporte.

        O retorno é instrumentação (vai ao registro), não ao agente.
        """
        if acao not in self.acoes_disponiveis():
            raise ValueError(f"ação indisponível na tela {self.tela}: {acao}")
        s = self.s
        out = {"mudancas": [], "dialogo": None, "suporte_abre": None, "suporte_fecha": None,
               "causa": None, "fim": None, "sem_efeito": False}
        tela_antes = self.tela

        def mudar(var, antes, depois, origem="pessoa"):
            out["mudancas"].append({"variavel": var, "antes": antes, "depois": depois,
                                    "origem": origem})

        def ir(tela):
            s["tela"] = tela

        def empilha(tela_dest):
            s["pilha"].append({"tela": s["tela"], "rotina_aberta": s["rotina_aberta"]})
            ir(tela_dest)

        def desempilha():
            if s["pilha"]:
                o = s["pilha"].pop()
                s["tela"], s["rotina_aberta"] = o["tela"], o["rotina_aberta"]
            else:
                ir("S1")

        if acao.startswith("nav:"):
            dest = acao[4:]
            if dest == "S6":
                if s["tela"] != "S6":
                    empilha("S6")
                    s["topico"] = None
                    out["suporte_abre"] = {"layer": "ajuda", "topic": None}
            else:
                if s["tela"] in ("S6", "S9"):
                    out["suporte_fecha"] = {"layer": "ajuda" if s["tela"] == "S6" else "dica"}
                if s["tela"] == "S8":
                    out["suporte_fecha"] = {"layer": "por_que"}
                s["pilha"].clear()
                if s["tela"] == "S2" and dest != "S2":
                    s["faixa_excluida"] = None   # a faixa "Desfazer" some ao sair de S2
                ir(dest)
        elif acao == "concluir":
            empilha("S7")
            s["ce2"] = False
        elif acao == "desistir":
            s["fim"] = "desistencia"
            out["fim"] = "desistencia"
        elif acao.startswith("alternar:"):
            ap = acao.split(":", 1)[1]
            antes = s["aparelhos"][ap]
            s["aparelhos"][ap] = not antes
            mudar(f"aparelhos.{ap}", antes, not antes)
            self._historico(ap, not antes, "pessoa")
            self._agendar_reacao(ap)
        elif acao == "porque":
            ir("S8")
            s["aviso_explicado"] = copy.deepcopy(s["aviso"])
            out["suporte_abre"] = {"layer": "por_que", "topic": s["aviso"]["rotina"]}
        elif acao == "desfazer_aviso":
            a = s["aviso"]
            ap = a["aparelho"]
            antes = s["aparelhos"][ap]
            s["aparelhos"][ap] = not a["ligado"]
            mudar(f"aparelhos.{ap}", antes, s["aparelhos"][ap])
            self._historico(ap, s["aparelhos"][ap], "pessoa")
            s["aviso"] = None
            self._agendar_reacao(ap)
        elif acao == "ir_rotina":
            rid = (s.get("aviso_explicado") or s["aviso"])["rotina"]
            out["suporte_fecha"] = {"layer": "por_que"}
            s["rotina_aberta"] = rid
            ir("S3")
        elif acao == "fechar_painel":
            out["suporte_fecha"] = {"layer": "por_que"}
            ir("S1")
        elif acao.startswith("abrir:"):
            s["rotina_aberta"] = acao.split(":", 1)[1]
            s["faixa_excluida"] = None
            ir("S3")
        elif acao == "desfazer_exclusao":
            rid = s["faixa_excluida"]
            s["rotinas"][rid] = s["excluidas"].pop(rid)
            s["faixa_excluida"] = None
            mudar(f"rotinas.{rid}.existe", False, True)
        elif acao == "voltar_S2":
            ir("S2")
        elif acao == "pausar_retomar":
            r = self._rot(s["rotina_aberta"])
            antes = r["situacao"]
            r["situacao"] = "Pausada" if antes == "Ativa" else "Ativa"
            mudar(f"rotinas.{s['rotina_aberta']}.situacao", antes, r["situacao"])
        elif acao == "editar":
            r = self._rot(s["rotina_aberta"])
            s["edicao"] = {"rotina": s["rotina_aberta"], "horario": r.get("horario"),
                           "aparelhos": list(r["aparelhos"]), "alterado": False}
            ir("S4")
        elif acao == "dica":
            empilha("S9")
            out["suporte_abre"] = {"layer": "dica", "topic": tela_antes}
        elif acao == "fechar_dica":
            desempilha()
            out["suporte_fecha"] = {"layer": "dica"}
        elif acao == "excluir":
            s["dialogo"] = {"tipo": "AL", "rotina": s["rotina_aberta"]}
            out["dialogo"] = "AL"
        elif acao == "al_cancelar":
            s["dialogo"] = None
        elif acao == "al_excluir":
            rid = s["dialogo"]["rotina"]
            s["excluidas"][rid] = s["rotinas"].pop(rid)
            s["dialogo"] = None
            s["faixa_excluida"] = rid
            s["rotina_aberta"] = None
            mudar(f"rotinas.{rid}.existe", True, False)
            ir("S2")
        elif acao in ("mais", "menos"):
            e = s["edicao"]
            novo = e["horario"] + (1 if acao == "mais" else -1)
            if 0 <= novo <= 23:          # PA: preso em 00h--23h
                e["horario"] = novo
                e["alterado"] = True
            else:
                out["sem_efeito"] = True
        elif acao.startswith("caixa:"):
            ap = acao.split(":", 1)[1]
            e = s["edicao"]
            if ap in e["aparelhos"]:
                e["aparelhos"].remove(ap)
            else:
                e["aparelhos"].append(ap)
                e["aparelhos"].sort(key=APARELHOS_ORDEM.index)
            e["alterado"] = True
        elif acao in ("salvar", "ce1_salvar"):
            self._salvar(mudar)
            s["dialogo"] = None
            ir("S3")
        elif acao == "cancelar_edicao":
            if s["edicao"]["alterado"]:
                s["dialogo"] = {"tipo": "CE1"}
                out["dialogo"] = "CE1"
            else:
                s["edicao"] = None
                ir("S3")
        elif acao == "ce1_sair":
            s["edicao"] = None
            s["dialogo"] = None
            ir("S3")
        elif acao.startswith("topico:"):
            s["topico"] = acao.split(":", 1)[1]
            out["suporte_abre"] = {"layer": "ajuda", "topic": s["topico"], "dentro_de_S6": True}
        elif acao == "voltar_ajuda":
            desempilha()
            out["suporte_fecha"] = {"layer": "ajuda"}
        elif acao.startswith("causa:"):
            s["resposta_causa"] = acao.split(":", 1)[1]
            s["ce2"] = False
            out["causa"] = s["resposta_causa"]
        elif acao == "confirmar":
            if self.perguntar_causa and s["resposta_causa"] is None:
                s["ce2"] = True
                out["dialogo"] = "CE2"
            else:
                s["fim"] = "concluida"
                out["fim"] = "concluida"
        elif acao == "voltar_concluir":
            desempilha()
        else:  # pragma: no cover
            raise ValueError(acao)

        out["mudancas"] += self._avancar_relogio()
        return out

    # --------------------------------------------------------- processos
    def _salvar(self, mudar):
        e = self.s["edicao"]
        r = self._rot(e["rotina"])
        if r.get("horario") != e["horario"]:
            mudar(f"rotinas.{e['rotina']}.horario", r.get("horario"), e["horario"])
            r["horario"] = e["horario"]
        if r["aparelhos"] != e["aparelhos"]:
            mudar(f"rotinas.{e['rotina']}.aparelhos", list(r["aparelhos"]), list(e["aparelhos"]))
            r["aparelhos"] = list(e["aparelhos"])
        self.s["edicao"] = None

    def _historico(self, ap, ligado, origem):
        self.s["historico"].append({"hora": _fmt_hora(self.s["relogio"]), "aparelho": ap,
                                    "ligado": ligado, "origem": origem})

    def _agendar_reacao(self, ap):
        """Rotinas reativas (V1): religar a tomada não basta enquanto a rotina estiver ativa."""
        for rid, r in self.s["rotinas"].items():
            rea = r.get("reativa")
            if rea and rea["aparelho"] == ap and self.s["aparelhos"][ap] != rea["ligado"]:
                self.s["pendentes"].append({"rotina": rid, "aparelho": ap,
                                            "em": self.s["relogio"] + rea["atraso_min"]})

    def _avancar_relogio(self) -> list[dict]:
        self.s["relogio"] += 1
        mudancas = []
        restantes = []
        for p in self.s["pendentes"]:
            r = self.s["rotinas"].get(p["rotina"])
            if self.s["relogio"] < p["em"]:
                restantes.append(p)
                continue
            if not r or r["situacao"] != "Ativa" or p["aparelho"] not in r["aparelhos"]:
                continue
            ap, alvo = p["aparelho"], r["reativa"]["ligado"]
            if self.s["aparelhos"][ap] != alvo:
                mudancas.append({"variavel": f"aparelhos.{ap}", "antes": self.s["aparelhos"][ap],
                                 "depois": alvo, "origem": p["rotina"]})
                self.s["aparelhos"][ap] = alvo
                self._historico(ap, alvo, p["rotina"])
                self.s["aviso"] = {"aparelho": ap, "ligado": alvo,
                                   "hora": _fmt_hora(self.s["relogio"]), "rotina": p["rotina"],
                                   "motivo": r["motivo"]}
        self.s["pendentes"] = restantes
        return mudancas
