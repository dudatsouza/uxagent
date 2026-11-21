"""Políticas que escolhem a próxima fala u:.

- ``LLMPolicy``: o UXAgent. Recebe só a observação o'_t, a instrução, a ficha e x_t,
  e responde com o número de uma ação da lista (saída estruturada com enum).
- ``RegrasPolicy``: controle "executor por regras" (segue o método GOMS de referência).
- ``AleatoriaPolicy``: escolhe ao acaso; usada em testes e no piloto de instrumentação.
- ``ScriptPolicy``: sequência fixa de ações internas; usada em testes.

Fronteira: ``LLMPolicy`` não importa ``analista`` (teste garante).
"""
from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from pathlib import Path


class FalhaTecnica(Exception):
    """Falha técnica do protocolo (códigos F-API, F-FMT, F-REF)."""

    def __init__(self, codigo: str, mensagem: str):
        super().__init__(mensagem)
        self.codigo = codigo


@dataclass
class Contexto:
    sistema: str           # prompt de sistema (instrução fixa + ficha)
    usuario: str           # instrução da tarefa + x_t + observação + ações numeradas
    n_acoes: int
    oferta: list[str]      # ações internas na ordem numerada (NÃO vai ao LLM)


@dataclass
class Escolha:
    indice: int            # 1..n
    justificativa: str
    latencia_s: float
    meta: dict


class LLMPolicy:
    provider = "anthropic"

    def __init__(self, cfg_llm: dict):
        import anthropic  # importado aqui para os testes rodarem sem a API
        self._anthropic = anthropic
        self.client = anthropic.Anthropic(max_retries=cfg_llm.get("max_retries", 2))
        self.model = cfg_llm["modelo"]
        self.effort = cfg_llm.get("effort", "low")
        self.max_tokens = int(cfg_llm.get("max_tokens", 4000))
        self.fallbacks = cfg_llm.get("fallbacks")   # "default" ou None

    def _schema(self, n: int) -> dict:
        return {
            "type": "json_schema",
            "schema": {
                "type": "object",
                "properties": {
                    "acao": {"type": "integer", "enum": list(range(1, n + 1))},
                    "justificativa": {"type": "string"},
                },
                "required": ["acao", "justificativa"],
                "additionalProperties": False,
            },
        }

    def _chamar(self, ctx: Contexto):
        kwargs = dict(
            model=self.model,
            max_tokens=self.max_tokens,
            system=ctx.sistema,
            messages=[{"role": "user", "content": ctx.usuario}],
            output_config={"effort": self.effort, "format": self._schema(ctx.n_acoes)},
        )
        if self.fallbacks:
            return self.client.beta.messages.create(
                betas=["server-side-fallback-2026-07-01"], fallbacks=self.fallbacks, **kwargs)
        return self.client.messages.create(**kwargs)

    def escolher(self, ctx: Contexto) -> Escolha:
        a = self._anthropic
        ultimo_erro = None
        for tentativa in (1, 2):      # uma nova solicitação antes de F-FMT
            t0 = time.monotonic()
            try:
                resp = self._chamar(ctx)
            except a.BadRequestError as e:
                raise FalhaTecnica("F-API", f"400: {e.message}") from e
            except a.AuthenticationError as e:
                raise FalhaTecnica("F-API", "credencial inválida ou ausente") from e
            except a.RateLimitError as e:
                raise FalhaTecnica("F-API", "limite de taxa após novas tentativas") from e
            except a.APIStatusError as e:
                raise FalhaTecnica("F-API", f"HTTP {e.status_code}: {e.message}") from e
            except a.APIConnectionError as e:
                raise FalhaTecnica("F-API", "falha de conexão") from e
            lat = time.monotonic() - t0
            meta = {"modelo_servido": resp.model, "stop_reason": resp.stop_reason,
                    "request_id": getattr(resp, "_request_id", None),
                    "input_tokens": resp.usage.input_tokens,
                    "output_tokens": resp.usage.output_tokens,
                    "tentativa": tentativa}
            if resp.stop_reason == "refusal":
                cat = getattr(getattr(resp, "stop_details", None), "category", None)
                raise FalhaTecnica("F-REF", f"recusa do modelo ({cat})")
            texto = next((b.text for b in resp.content if b.type == "text"), "")
            try:
                dados = json.loads(texto)
                idx = int(dados["acao"])
                if not 1 <= idx <= ctx.n_acoes:
                    raise ValueError("fora da lista")
                return Escolha(idx, str(dados.get("justificativa", ""))[:500], lat, meta)
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
                ultimo_erro = f"{e}; resposta={texto[:200]!r}"
        raise FalhaTecnica("F-FMT", f"resposta fora do formato: {ultimo_erro}")


class AleatoriaPolicy:
    provider = "local"
    model = "aleatoria"

    def __init__(self, rng: random.Random):
        self.rng = rng

    def escolher(self, ctx: Contexto) -> Escolha:
        return Escolha(self.rng.randint(1, ctx.n_acoes), "escolha aleatória", 0.0, {})


class ScriptPolicy:
    """Escolhe ações internas de uma lista fixa (testes)."""
    provider = "local"
    model = "script"

    def __init__(self, roteiro: list[str]):
        self.roteiro = list(roteiro)

    def escolher(self, ctx: Contexto) -> Escolha:
        alvo = self.roteiro.pop(0) if self.roteiro else "desistir"
        if alvo not in ctx.oferta:
            alvo = "desistir" if "desistir" in ctx.oferta else ctx.oferta[0]
        return Escolha(ctx.oferta.index(alvo) + 1, "roteiro", 0.0, {})


class RegrasPolicy:
    """Controle: segue o método GOMS de referência e corrige deslizes desfazendo-os.

    Usa conhecimento do analista de propósito: serve como piso de ações (Fase II).
    """
    provider = "local"
    model = "regras"

    def __init__(self):
        self.plano: list[str] = []
        self.ultima_proposta: str | None = None

    def iniciar(self, tarefa: str, versao: str):
        from . import analista
        self.plano = list(analista.METODO_REFERENCIA[(tarefa, versao)])
        self.ultima_proposta = None

    def notificar(self, proposta: str, executada: str):
        """Recebe do executor o que foi executado (só este controle recebe isso)."""
        if executada in self.plano:
            # avança o plano até a ação executada (inclusive)
            del self.plano[: self.plano.index(executada) + 1]
        elif executada != proposta:
            # deslize reversível: desfaz antes de seguir
            inversas = {"mais": "menos", "menos": "mais", "editar": "cancelar_edicao",
                        "porque": "fechar_painel"}
            if executada.startswith(("alternar:", "caixa:")) or executada in (
                    "pausar_retomar", *inversas):
                self.plano.insert(0, inversas.get(executada, executada))

    def escolher(self, ctx: Contexto) -> Escolha:
        if self.plano and self.plano[0] in ctx.oferta:
            self._tentou_inicio = False
            return Escolha(ctx.oferta.index(self.plano[0]) + 1, "método de referência", 0.0, {})
        if self.plano and not getattr(self, "_tentou_inicio", False) and "nav:S1" in ctx.oferta:
            # deslize levou a outra tela: volta ao Início antes de seguir o plano
            self._tentou_inicio = True
            return Escolha(ctx.oferta.index("nav:S1") + 1, "recuperação", 0.0, {})
        for alvo in self.plano:
            if alvo in ctx.oferta:
                self.ultima_proposta = alvo
                return Escolha(ctx.oferta.index(alvo) + 1, "método de referência", 0.0, {})
        for saida in ("voltar_ajuda", "fechar_dica", "al_cancelar", "fechar_painel"):
            if saida in ctx.oferta:
                return Escolha(ctx.oferta.index(saida) + 1, "retorno", 0.0, {})
        return Escolha(ctx.oferta.index("desistir") + 1 if "desistir" in ctx.oferta else 1,
                       "sem plano", 0.0, {})


def carregar_prompt(pasta: Path, nome: str) -> str:
    return (pasta / nome).read_text(encoding="utf-8").strip()
