import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from uxagent.executor import rodar_sessao  # noqa: E402
from uxagent.registro import ler  # noqa: E402
from uxagent.verificador import segmentar  # noqa: E402

NEUTRO = RAIZ / "configs" / "neutro.yaml"


@pytest.fixture
def rodar_script(tmp_path):
    """Roda uma tarefa com roteiro fixo (ações internas) e config neutra; devolve os eventos."""
    def _run(tarefa, versao, roteiro, config=NEUTRO, semente=1):
        p = rodar_sessao(config, "script", versao, [tarefa], semente, tmp_path,
                         roteiros={tarefa: roteiro})
        return segmentar(ler(p))[0]
    return _run
