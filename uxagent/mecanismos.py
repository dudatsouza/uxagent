"""Amostrador de parâmetros e mecanismos M1--M6, fora do prompt.

O comportamento do perfil vem daqui, e não do texto do prompt. Cada mecanismo
tem chave liga-desliga no YAML; desligado, seu parâmetro assume o valor neutro.
"""
from __future__ import annotations

import copy
import hashlib
import json
import random
from collections import Counter
from dataclasses import dataclass, field

from .casafacil import CasaFacil, Elemento

MECH_VERSION = "mech-1.0"

NEUTRO = {"p_atr": 0.0, "q_rot": 0.0, "p_slip": 0.0, "p_hes": 0.0, "r_nota": 1.0, "c_comp": 1.0}
CHAVE_DO_PARAM = {"p_atr": "M1", "q_rot": "M2", "p_slip": "M3", "p_hes": "M4", "r_nota": "M5",
                  "c_comp": "M6"}
DESTRUTIVAS = {"excluir", "al_excluir"}
SOB_INCERTEZA = {"confirmar", "pausar_retomar", "salvar", "ce1_salvar"}
SUBSTITUTOS = ["nav:S6", "al_cancelar", "voltar_concluir", "voltar_S2", "cancelar_edicao",
               "fechar_painel", "nav:S1"]
MAX_HESITACOES = 2
MEMORIA_ACOES = 8   # ações recentes mantidas em x_t (hipótese operacional; ver docs/depuracao.md)
APRENDE = {"H2": {"pausa", "retomar"}, "H3": {"lapis"}, "H4": {"smart"},
           "dica:S3": {"pausa", "retomar", "lapis"}, "dica:S4": {"smart"}}


def amostrar(cfg: dict, rng: random.Random) -> dict:
    """Sorteia theta a partir das distribuições do YAML (Tabela III da Fase II)."""
    theta = {}
    chaves = cfg.get("mecanismos", {})
    for nome, dist in cfg.get("parametros", {}).items():
        if not chaves.get(CHAVE_DO_PARAM[nome], False):
            theta[nome] = NEUTRO[nome]
            continue
        tipo = dist["tipo"]
        if tipo == "fixo":
            theta[nome] = float(dist["valor"])
        elif tipo == "uniforme":
            theta[nome] = rng.uniform(dist["min"], dist["max"])
        elif tipo == "triangular":
            theta[nome] = rng.triangular(dist["min"], dist["max"], dist["moda"])
        else:
            raise ValueError(f"distribuição desconhecida: {tipo}")
    for nome, v in NEUTRO.items():
        theta.setdefault(nome, v)
    return {k: round(v, 4) for k, v in theta.items()}


def theta_hash(theta: dict) -> str:
    return hashlib.sha256(json.dumps(theta, sort_keys=True).encode()).hexdigest()[:10]


@dataclass
class EstadoPersona:
    """x_t: estado operacional externo ao LLM."""
    crenca: str | None = None             # eu_outra | defeito | nao_sei | rotina:<id>
    caderno: list[dict] = field(default_factory=list)   # notas {texto, tarefa}
    aprendidos: set[str] = field(default_factory=set)   # rótulos entendidos (M2)
    trajeto: list[str] = field(default_factory=list)    # rótulos tocados desde a última nota
    feitos: list[str] = field(default_factory=list)     # ações já feitas nesta tarefa (memória)
    hesitacoes: Counter = field(default_factory=Counter)
    tarefa: str | None = None
    aparelho_aviso: str | None = None   # aparelho da mudança automática que a persona viu (D-03)

    def nova_tarefa(self, tarefa: str):
        """Reinicia x_t entre tarefas, exceto caderno e rótulos aprendidos."""
        self.crenca, self.trajeto, self.hesitacoes, self.tarefa = None, [], Counter(), tarefa
        self.feitos = []
        self.aparelho_aviso = None

    def memoria(self, n: int = MEMORIA_ACOES) -> list[str]:
        """Últimas n ações da tarefa: memória de trabalho do que a persona já fez (HO)."""
        return self.feitos[-n:]


class Controlador:
    """Aplica M1--M6 sobre observação, ação e estado."""

    def __init__(self, theta: dict, rng: random.Random):
        self.t = theta
        self.rng = rng
        self.x = EstadoPersona()

    # ------------------------------------------------------------- M1
    def _m1(self, ui: CasaFacil, eventos: list):
        aviso = ui.s.get("aviso")
        if not aviso:
            return
        self.x.aparelho_aviso = aviso["aparelho"]
        if self.x.crenca == f"rotina:{aviso['rotina']}":
            return
        if self.t["p_atr"] > 0 and self.rng.random() < self.t["p_atr"]:
            self.x.crenca = self.rng.choice(["eu_outra", "defeito"])
        else:
            self.x.crenca = "nao_sei"
        eventos.append({"mecanismo": "M1", "efeito": "crenca", "valor": self.x.crenca})

    def inicio_tarefa(self, ui: CasaFacil, tarefa: str) -> list[dict]:
        self.x.nova_tarefa(tarefa)
        ev: list[dict] = []
        self._m1(ui, ev)
        return ev

    # -------------------------------------------- transformação da observação
    def transformar(self, ui: CasaFacil, els: list[Elemento]) -> tuple[list[Elemento], list[str], list[dict]]:
        """M2 (filtro de rótulos) e filtro de affordance da causa (M1/M6)."""
        aplicados = []
        novos, acoes = [], []
        for e in els:
            e2 = copy.copy(e)
            chave = e.icone or ("smart" if e.rotulo_estrangeiro else None)
            if (chave and chave not in self.x.aprendidos and self.t["q_rot"] > 0
                    and self.rng.random() < self.t["q_rot"]):
                e2.texto = "[ícone sem nome]" if e.icone else f"[\"{e.texto}\" sem nome]"
                e2.acao = None   # sai da lista de ações até a leitura da ajuda
                aplicados.append({"mecanismo": "M2", "elemento": e.texto})
            novos.append(e2)
            if e2.acao:
                acoes.append(e2.acao)
        # Filtro da pergunta de causa: só opções compatíveis com a crença registrada.
        if ui.tela == "S7" and self.x.crenca not in (None, "nao_sei"):
            permitidas = {f"causa:{self.x.crenca}", "causa:nao_sei"}
            antes = len(acoes)
            acoes = [a for a in acoes if not a.startswith("causa:") or a in permitidas]
            if len(acoes) != antes:
                aplicados.append({"mecanismo": "M1/M6", "efeito": "filtro_causa",
                                  "crenca": self.x.crenca})
        return novos, acoes, aplicados

    def notas_visiveis(self, tarefa: str) -> tuple[list[str], list[dict]]:
        """M5: notas de tarefas anteriores entram na observação com prob. r_nota."""
        notas = [n["texto"] for n in self.x.caderno if n["tarefa"] != tarefa]
        if notas and self.rng.random() < self.t["r_nota"]:
            return notas, [{"mecanismo": "M5", "efeito": "nota_mostrada", "n": len(notas)}]
        return [], []

    def texto_crenca(self, ui: CasaFacil) -> str | None:
        c = self.x.crenca
        if c is None:
            return None
        if c == "nao_sei":
            return "Você ainda não sabe por que isso aconteceu."
        if c == "eu_outra":
            return "Você acha que foi você ou outra pessoa que mexeu."
        if c == "defeito":
            return "Você acha que foi um defeito."
        rid = c.split(":", 1)[1]
        return f"Você acha que foi a rotina \"{ui.s['nomes_rotinas'][rid]}\"."

    # ---------------------------------------------------------- M4 e M3
    def hesitar(self, acao: str, disponiveis: list[str]) -> str | None:
        """M4: retém ação destrutiva ou incerta; devolve o substituto ou None."""
        candidata = acao in DESTRUTIVAS or (
            self.x.crenca == "nao_sei" and (acao in SOB_INCERTEZA or acao.startswith("alternar:")))
        if not candidata or self.x.hesitacoes[acao] >= MAX_HESITACOES:
            return None
        if self.t["p_hes"] > 0 and self.rng.random() < self.t["p_hes"]:
            for s in SUBSTITUTOS:
                if s in disponiveis and s != acao:
                    self.x.hesitacoes[acao] += 1
                    return s
        return None

    def deslize(self, acao: str, els: list[Elemento], disponiveis: list[str]) -> str:
        """M3: com p_slip, executa um vizinho adjacente no lugar do alvo."""
        el = next((e for e in els if e.acao == acao), None)
        if not el:
            return acao
        viz = [v for v in el.vizinhos if v in disponiveis]
        if viz and self.t["p_slip"] > 0 and self.rng.random() < self.t["p_slip"]:
            return self.rng.choice(viz)
        return acao

    # ----------------------------------------------------- após a ação
    def apos_acao(self, ui: CasaFacil, executada: str, rotulo: str, out: dict) -> list[dict]:
        ev: list[dict] = []
        self.x.feitos.append(rotulo)
        if executada not in ("nav:S6", "dica", "fechar_dica", "voltar_ajuda") \
                and not executada.startswith("topico:"):
            self.x.trajeto.append(rotulo)
        # Aprendizagem de rótulos (M2): leitura da ajuda correspondente.
        chave = None
        if executada.startswith("topico:"):
            chave = executada.split(":", 1)[1]
        elif executada == "dica":
            chave = f"dica:{out.get('suporte_abre', {}).get('topic')}"
        if chave in APRENDE:
            novos = APRENDE[chave] - self.x.aprendidos
            if novos:
                self.x.aprendidos |= novos
                ev.append({"mecanismo": "M2", "efeito": "rotulo_aprendido",
                           "rotulos": sorted(novos)})
        # M1: nova mudança automática sem pista de origem.
        if any(m["origem"] not in ("pessoa",) for m in out["mudancas"]):
            self._m1(ui, ev)
        # Pista de origem no Histórico: revisão da crença (M1).
        # D-03: usa o aparelho do aviso que a persona viu, mesmo que ele já tenha sumido
        # da tela (por exemplo, depois de "Desfazer" na versão B).
        if ui.tela == "S5" and self.x.aparelho_aviso:
            ap = self.x.aparelho_aviso
            # a linha da mudança automática anunciada no aviso (a mais recente não feita por ela)
            linhas = [l for l in ui.s["historico"] if l["aparelho"] == ap and l["origem"] != "pessoa"]
            if linhas:
                nova = f"rotina:{linhas[-1]['origem']}"
                if self.x.crenca != nova:
                    self.x.crenca = nova
                    ev.append({"mecanismo": "M1", "efeito": "crenca_revista_historico",
                               "valor": nova})
        # M6: painel "Por quê?" aberto.
        if executada == "porque":
            rid = ui.s["aviso_explicado"]["rotina"]
            if self.rng.random() < self.t["c_comp"]:
                self.x.crenca = f"rotina:{rid}"
                ev.append({"mecanismo": "M6", "efeito": "crenca_atualizada",
                           "valor": self.x.crenca})
            else:
                ev.append({"mecanismo": "M6", "efeito": "explicacao_nao_compreendida"})
        # M5: subobjetivo atingido (mudança em rotina feita pela persona) -> nota.
        if any(m["variavel"].startswith("rotinas.") and m["origem"] == "pessoa"
               for m in out["mudancas"]):
            texto = "Caminho que funcionou: " + " -> ".join(self.x.trajeto)
            self.x.caderno.append({"texto": texto, "tarefa": self.x.tarefa})
            self.x.trajeto = []
            ev.append({"mecanismo": "M5", "efeito": "nota_escrita", "texto": texto})
        return ev
