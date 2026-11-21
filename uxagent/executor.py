"""Executor (controlador do ciclo): interface -> mecanismos -> observação -> política -> ação.

Ciclo de cada passo (arquitetura da Fase II):
  1. a interface expõe a tela atual;
  2. o controlador transforma a observação (M1, M2, M5) e monta o_t;
  3. a política escolhe um número da lista de ações (fala u:);
  4. o controlador valida, aplica M4 (hesitação) e M3 (deslize);
  5. a interface executa e o registrador grava os eventos;
  6. o fim da tarefa é decidido por Concluir/Desistir/limite; o SUCESSO é decidido
     depois, pelo verificador externo, a partir do estado final.
"""
from __future__ import annotations

import hashlib
import json
import platform
import random
from pathlib import Path

import yaml

from . import analista, observacao, tarefas
from .casafacil import UI_VERSION, CasaFacil, help_hash
from .mecanismos import MECH_VERSION, NEUTRO, Controlador, amostrar, theta_hash
from .politicas import (AleatoriaPolicy, Contexto, FalhaTecnica, LLMPolicy, RegrasPolicy,
                        ScriptPolicy, carregar_prompt)
from .registro import DESIGN_VERSION, Registro

RAIZ = Path(__file__).resolve().parent.parent
PROMPTS = RAIZ / "prompts"


def carregar_config(caminho: Path) -> tuple[dict, str]:
    texto = Path(caminho).read_text(encoding="utf-8")
    cfg = yaml.safe_load(texto)
    h = hashlib.sha256(texto.encode())
    for nome in ("sistema.txt", cfg.get("ficha") or ""):
        if nome:
            h.update((PROMPTS / nome).read_bytes())
    return cfg, h.hexdigest()[:12]


def prompt_sistema(cfg: dict) -> str:
    base = carregar_prompt(PROMPTS, "sistema.txt")
    if cfg.get("ficha"):
        base += "\n\nQuem você é:\n" + carregar_prompt(PROMPTS, cfg["ficha"])
    return base


def _rotulo(els, acao) -> str:
    el = next((e for e in els if e.acao == acao), None)
    return observacao._desc(el) if el else acao


def criar_politica(nome: str, cfg: dict, semente: int, roteiro=None):
    if nome == "llm":
        return LLMPolicy(cfg["llm"])
    if nome == "regras":
        return RegrasPolicy()
    if nome == "aleatoria":
        return AleatoriaPolicy(random.Random(semente + 10_000))
    if nome == "script":
        return ScriptPolicy(roteiro or [])
    raise ValueError(nome)


def rodar_sessao(cfg_path: Path, politica: str, versao: str, lista_tarefas: list[str],
                 semente: int, saida: Path, permitir_validacao: bool = False,
                 roteiros: dict | None = None) -> Path:
    cfg, cfg_hash = carregar_config(cfg_path)
    for t in lista_tarefas:
        if t in tarefas.VALIDACAO and not (permitir_validacao and cfg.get("congelado")):
            raise PermissionError(
                f"{t} é tarefa de validação (congelada). Use --validacao com uma configuração "
                "congelada (congelado: true); nunca para calibrar ou ajustar.")
    rng = random.Random(semente)
    theta = amostrar(cfg, rng)
    if politica == "regras":
        # Controle "executor por regras" (Fase II): só M3 atua; é o piso de ações.
        theta = {**NEUTRO, "p_slip": theta["p_slip"]}
    ctl = Controlador(theta, rng)
    pol = criar_politica(politica, cfg, semente)
    sistema = prompt_sistema(cfg) if politica == "llm" else "(política local, sem LLM)"
    modelo = cfg["llm"]["modelo"] if politica == "llm" else pol.model
    session_id = f"{cfg['nome']}-{versao}-{politica}-s{semente}"
    reg = Registro(Path(saida) / f"{session_id}.jsonl", {
        "session_id": session_id, "subject_id": f"sint-{semente:04d}",
        "persona_id": f"{cfg['persona_id']}#{theta_hash(theta)}", "config_hash": cfg_hash,
        "synthetic": True, "origin": "synthetic", "group": cfg["grupo"], "condition": versao,
        "ui_version": UI_VERSION, "mech_version": MECH_VERSION,
        "design_version": DESIGN_VERSION, "help_hash": help_hash(),
        "llm_provider": pol.provider, "llm_model": modelo, "seed": semente,
    })
    reg.evento("session_start", {
        "config": cfg, "theta": theta, "politica": politica, "tarefas": lista_tarefas,
        "prompt_sistema": sistema, "python": platform.python_version()})

    for ordem, tid in enumerate(lista_tarefas, start=1):
        if hasattr(pol, "roteiro") and roteiros:
            pol.roteiro = list(roteiros.get(tid, []))
        _rodar_tarefa(reg, ctl, pol, sistema, tid, versao, ordem)
    reg.evento("session_end", {"caderno": ctl.x.caderno, "aprendidos": sorted(ctl.x.aprendidos)})
    reg.fechar()
    return reg.caminho


def _rodar_tarefa(reg: Registro, ctl: Controlador, pol, sistema: str, tid: str, versao: str,
                  ordem: int):
    defn = tarefas.TAREFAS[tid]
    ui = CasaFacil(tarefas.estado_inicial(tid), versao, defn["perguntar_causa"])
    limite = 3 * analista.A_MIN[(tid, versao)]
    instrucao = f"{tarefas.INSTRUCAO_GERAL} {defn['instrucao']}"
    reg.com(task_id=tid, task_set=defn["conjunto"], step=0)
    reg.evento("task_start", {"ordem": ordem, "instrucao": instrucao,
                              "estado_inicial": ui.snapshot(), "limite_acoes": limite})
    for m in ctl.inicio_tarefa(ui, tid):
        reg.evento("mechanism_applied", m)
    if isinstance(pol, RegrasPolicy):
        pol.iniciar(tid, versao)

    acoes_exec = 0
    resultado = None
    anteriores = None
    tela_anterior = None
    while True:
        els = ui.render()
        tela = ui.tela
        if tela != tela_anterior:
            reg.evento("screen_view", {"tela": tela, "elementos": [observacao._desc(e) for e in els]},
                       screen=tela)
        els_t, disponiveis, aplicados = ctl.transformar(ui, els)
        notas, ev_notas = ctl.notas_visiveis(tid)
        mudou = observacao.mudancas(anteriores if tela == tela_anterior else None, els)
        titulo = ui.s["rotinas"][ui.s["rotina_aberta"]]["nome"] if tela == "S3" else None
        obs, oferta = observacao.montar(tela, titulo, els_t, disponiveis, mudou)
        partes = [f"Tarefa: {instrucao}"]
        if notas:
            partes.append("Suas anotações no caderno:\n" + "\n".join(f"- {n}" for n in notas))
            for n in notas:
                reg.evento("note_shown", {"texto": n})
        crenca = ctl.texto_crenca(ui)
        if crenca:
            partes.append(f"Sua impressão até agora: {crenca}")
        memoria = ctl.x.memoria()
        if memoria:
            partes.append("O que você já fez nesta tarefa (da mais antiga à mais recente):\n"
                          + "\n".join(f"- tocou {m}" for m in memoria))
        partes.append(f"Passo {acoes_exec + 1}. O que aparece na tela agora:\n{obs}")
        partes.append("Responda com o número de uma das ações disponíveis.")
        usuario = "\n\n".join(partes)
        for m in aplicados + ev_notas:
            reg.evento("mechanism_applied", m)
        reg.evento("observation_delivered", {
            "o_t": obs, "prompt_usuario": usuario,
            "prompt_sistema_sha": hashlib.sha256(sistema.encode()).hexdigest()[:12],
            "crenca": ctl.x.crenca, "n_acoes": len(oferta)}, screen=tela)
        anteriores, tela_anterior = els, tela

        try:
            esc = pol.escolher(Contexto(sistema, usuario, len(oferta), oferta))
        except FalhaTecnica as f:
            reg.evento("technical_failure", {"codigo": f.codigo, "mensagem": str(f)})
            resultado = "indeterminado"
            break
        proposta = oferta[esc.indice - 1]
        reg.evento("action_proposed", {"indice": esc.indice, "fala_u": _rotulo(els_t, proposta),
                                       "proposed": proposta, "justificativa": esc.justificativa,
                                       "latencia_s": round(esc.latencia_s, 3), **esc.meta},
                   screen=tela)
        executar = proposta
        subst = ctl.hesitar(proposta, oferta)
        if subst:
            reg.evento("action_rejected", {"motivo": "hesitation", "proposed": proposta,
                                           "substituida_por": subst, "mecanismo": "M4"})
            executar = subst
        alvo = executar
        executar = ctl.deslize(alvo, els, ui.acoes_disponiveis())
        slip = executar != alvo
        el_exec = next(e for e in els if e.acao == executar)
        tem_vizinho = bool([v for v in el_exec.vizinhos if v in ui.acoes_disponiveis()])
        hash_antes = ui.state_hash()
        out = ui.aplicar(executar)
        acoes_exec += 1
        reg.com(step=acoes_exec)
        fala_d = ui.tela
        reg.evento("action_executed", {
            "cena": tela, "fala_u": observacao._desc(el_exec), "proposed": alvo,
            "executed": executar, "slip": slip, "tem_vizinho": tem_vizinho,
            "fala_d": f"tela {fala_d}", "sem_efeito": out["sem_efeito"]},
            screen_before=tela, screen_after=ui.tela, state_before_hash=hash_antes,
            state_after_hash=ui.state_hash())
        if isinstance(pol, RegrasPolicy):
            pol.notificar(alvo, executar)
        for m in out["mudancas"]:
            origem = "persona" if m["origem"] == "pessoa" else f"rotina:{m['origem']}"
            reg.evento("state_changed", {**m, "origem": origem})
        if out["dialogo"]:
            reg.evento("dialog_shown", {"tipo": out["dialogo"], "cena": tela})
        if executar.startswith(("al_", "ce1_")):
            reg.evento("dialog_choice", {"tipo": tela, "escolha": executar.split("_", 1)[1]})
        if out["suporte_abre"]:
            reg.evento("support_open", {**out["suporte_abre"], "scene_origin": tela})
        if out["suporte_fecha"]:
            reg.evento("support_close", {**out["suporte_fecha"], "scene_return": ui.tela})
        if out["causa"]:
            reg.evento("cause_selected", {"opcao": out["causa"]})
        rotulo = el_exec.texto if el_exec.papel == "icone" else f"\"{el_exec.texto}\""
        if fala_d != tela:
            rotulo += f" (abriu a tela \"{observacao.TITULOS.get(fala_d, 'da rotina')}\")"
        else:
            # D-02: a memória guarda também o retorno visível da ação (signo dinâmico).
            visto = observacao.mudancas(els, ui.render())
            if visto:
                rotulo += " (a tela mostrou: " + "; ".join(
                    v.replace("Mudou na tela: ", "") for v in visto) + ")"
        for m in ctl.apos_acao(ui, executar, rotulo, out):
            if m.get("efeito") == "nota_escrita":
                reg.evento("note_written", {"texto": m["texto"]})
            reg.evento("mechanism_applied", m)
        if out["fim"]:
            resultado = out["fim"]
            break
        if acoes_exec >= limite:
            resultado = "limite"
            break

    reg.evento("task_end", {"resultado": resultado, "n_acoes": acoes_exec,
                            "estado_final": ui.snapshot()})
    reg.com(step=0)


def dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)
