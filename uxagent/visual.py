"""Visualizador do CasaFácil no navegador (para pessoas verem o app e o replay do agente).

Usa a MESMA máquina de estados de ``casafacil.py``; a página só desenha o que o
Python devolve. Dois modos:

- "Usar o app": a pessoa toca nos elementos; nada é registrado como dado do estudo.
- "Replay": refaz, passo a passo, as ações executadas numa sessão gravada (JSONL),
  mostrando a tela real, onde o agente tocou, a justificativa e os mecanismos.

Só C1 e C2 (calibração). V1/V2 seguem congeladas e não aparecem aqui.

Uso:  python -m uxagent app    (abre http://localhost:8765)
"""
from __future__ import annotations

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import analista, tarefas
from .casafacil import CasaFacil, Elemento
from .observacao import TITULOS
from .registro import ler
from .verificador import segmentar, verificar_segmento

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "dados"
PAGINA = Path(__file__).resolve().parent / "web" / "index.html"
TAREFAS_VISIVEIS = ["C1", "C2"]


def _titulo(ui: CasaFacil) -> str:
    if ui.tela == "S3" and ui.s.get("rotina_aberta"):
        return ui.s["rotinas"][ui.s["rotina_aberta"]]["nome"]
    return TITULOS.get(ui.tela, ui.tela)


def _el(e: Elemento) -> dict:
    return {"papel": e.papel, "texto": e.texto, "acao": e.acao, "detalhe": e.detalhe,
            "icone": e.icone}


def tela_json(ui: CasaFacil) -> dict:
    return {"tela": ui.tela, "titulo": _titulo(ui), "modal": bool(ui.s["dialogo"]),
            "versao": ui.versao, "elementos": [_el(e) for e in ui.render()]}


# ------------------------------------------------------------------ replay
def listar_sessoes() -> list[dict]:
    out = []
    for p in sorted(DADOS.glob("*/*.jsonl")):
        if p.name.endswith(".verificado.jsonl"):
            continue
        tids = []
        for linha in p.open(encoding="utf-8"):
            if '"task_start"' in linha:
                tids.append(json.loads(linha)["task_id"])
        tids = [t for t in tids if t in TAREFAS_VISIVEIS]
        if tids:
            out.append({"arquivo": str(p.relative_to(DADOS)), "tarefas": tids})
    return out


def replay(arquivo: str, tarefa: str) -> dict:
    caminho = (DADOS / arquivo).resolve()
    if DADOS.resolve() not in caminho.parents or not caminho.is_file():
        raise ValueError("arquivo fora de dados/")
    if tarefa not in TAREFAS_VISIVEIS:
        raise ValueError("só tarefas de calibração (C1, C2)")
    seg = next((s for s in segmentar(ler(caminho)) if s[0]["task_id"] == tarefa), None)
    if seg is None:
        raise ValueError("tarefa não encontrada na sessão")
    ini = seg[0]
    ui = CasaFacil(ini["data"]["estado_inicial"], ini["condition"],
                   tarefas.TAREFAS[tarefa]["perguntar_causa"])
    quadros, pend = [], {"mecanismos": [], "proposta": None, "rejeitada": None, "o_t": None}
    for e in seg[1:]:
        t, d = e["event_type"], e["data"]
        if t == "mechanism_applied":
            pend["mecanismos"].append(d)
        elif t == "observation_delivered":
            pend["o_t"] = d.get("o_t")
        elif t == "action_proposed":
            pend["proposta"] = d
        elif t == "action_rejected":
            pend["rejeitada"] = d
        elif t == "action_executed":
            quadros.append({
                "passo": len(quadros) + 1, "tela": tela_json(ui),
                "executada": d["executed"], "pretendida": d["proposed"], "deslize": d["slip"],
                "fala_u": d["fala_u"],
                "justificativa": (pend["proposta"] or {}).get("justificativa"),
                "proposta_original": (pend["rejeitada"] or {}).get("proposed"),
                "mecanismos": pend["mecanismos"], "o_t": pend["o_t"], "mudancas": [],
            })
            ui.aplicar(d["executed"])
            pend = {"mecanismos": [], "proposta": None, "rejeitada": None, "o_t": None}
        elif t == "state_changed" and quadros:
            quadros[-1]["mudancas"].append(d)
        elif t == "technical_failure" and quadros:
            quadros[-1]["falha"] = d
    v = verificar_segmento(seg)
    return {
        "sessao": ini["session_id"], "tarefa": tarefa, "versao": ini["condition"],
        "persona": ini["persona_id"].split("#")[0], "modelo": ini["llm_model"],
        "instrucao": ini["data"]["instrucao"], "quadros": quadros, "final": tela_json(ui),
        "mecanismos_finais": pend["mecanismos"],
        "verificador": {"fim": v["fim"], "sucesso": v["sucesso"],
                        "erros": [x["categoria"] for x in v["erros"]],
                        "mac": [x["etiqueta"] for x in v["mac"]]},
    }


# ------------------------------------------------------------- modo "usar"
class SessaoManual:
    """Uso livre por uma pessoa. Não grava eventos: não é dado do estudo."""

    def __init__(self):
        self.ui: CasaFacil | None = None
        self.tarefa = None
        self.n = 0
        self.lock = threading.Lock()

    def nova(self, tarefa: str, versao: str) -> dict:
        if tarefa not in TAREFAS_VISIVEIS or versao not in ("A", "B"):
            raise ValueError("tarefa ou versão inválida")
        with self.lock:
            self.ui = CasaFacil(tarefas.estado_inicial(tarefa), versao,
                                tarefas.TAREFAS[tarefa]["perguntar_causa"])
            self.tarefa, self.n = tarefa, 0
            return self._estado(mudancas=[])

    def tocar(self, acao: str) -> dict:
        with self.lock:
            if self.ui is None or self.ui.s["fim"]:
                raise ValueError("comece uma tarefa")
            out = self.ui.aplicar(acao)
            self.n += 1
            return self._estado(mudancas=out["mudancas"])

    def _estado(self, mudancas) -> dict:
        fim = self.ui.s["fim"]
        res = {"tela": tela_json(self.ui), "mudancas": mudancas, "acoes": self.n, "fim": fim,
               "instrucao": f"{tarefas.INSTRUCAO_GERAL} {tarefas.TAREFAS[self.tarefa]['instrucao']}"}
        if fim:
            res["sucesso"] = analista.sucesso(self.tarefa, self.ui.snapshot(), fim)
        return res


# ------------------------------------------------------------------ servidor
def criar_handler(manual: SessaoManual):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):  # silencioso
            pass

        def _json(self, obj, status=200):
            corpo = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def do_GET(self):
            u = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            try:
                if u.path == "/":
                    corpo = PAGINA.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(corpo)))
                    self.end_headers()
                    self.wfile.write(corpo)
                elif u.path == "/api/sessoes":
                    self._json(listar_sessoes())
                elif u.path == "/api/replay":
                    self._json(replay(q["arquivo"], q["tarefa"]))
                else:
                    self._json({"erro": "não encontrado"}, 404)
            except (ValueError, KeyError) as e:
                self._json({"erro": str(e)}, 400)

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            dados = json.loads(self.rfile.read(n) or b"{}")
            try:
                if self.path == "/api/nova":
                    self._json(manual.nova(dados["tarefa"], dados["versao"]))
                elif self.path == "/api/tocar":
                    self._json(manual.tocar(dados["acao"]))
                else:
                    self._json({"erro": "não encontrado"}, 404)
            except (ValueError, KeyError) as e:
                self._json({"erro": str(e)}, 400)
    return H


def servir(porta: int = 8765, abrir: bool = True):
    srv = ThreadingHTTPServer(("127.0.0.1", porta), criar_handler(SessaoManual()))
    url = f"http://localhost:{porta}"
    print(f"CasaFácil no navegador: {url}   (Ctrl+C para encerrar)")
    if abrir:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
