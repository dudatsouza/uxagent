"""Registrador de eventos em JSONL (um arquivo por sessão).

Todo evento leva os campos comuns da Fase II e as extensões do caderno E1.
``synthetic=true`` e ``origin="synthetic"`` identificam a origem sintética.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

DESIGN_VERSION = "e1-2026-11-22"


class Registro:
    def __init__(self, caminho: Path, comuns: dict):
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.f = self.caminho.open("w", encoding="utf-8")
        self.comuns = dict(comuns)
        self.contexto: dict = {}
        self.n = 0

    def com(self, **ctx):
        """Define campos de contexto (tarefa, task_set, step...) para os próximos eventos."""
        self.contexto.update(ctx)

    def evento(self, event_type: str, data: dict | None = None, **extra) -> dict:
        self.n += 1
        ev = {
            "event_id": f"{self.comuns['session_id']}-{self.n:05d}",
            "event_type": event_type,
            "t_wall": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            **self.comuns, **self.contexto, **extra,
            "data": data or {},
        }
        self.f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        self.f.flush()
        return ev

    def fechar(self):
        self.f.close()


def ler(caminho: Path) -> list[dict]:
    with Path(caminho).open(encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]
