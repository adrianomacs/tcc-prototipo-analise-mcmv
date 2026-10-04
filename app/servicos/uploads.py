"""Upload de arquivos enviados pelo usuário (modelos IFC) para `entradas/`.

Extraído de `_checagem_comum.py`.
"""

from __future__ import annotations

import os

from core.infra.caminhos import RAIZ


def salvar_upload(arquivo, pasta_destino: str, nome: str) -> str:
    destino_abs = os.path.join(RAIZ, pasta_destino)
    os.makedirs(destino_abs, exist_ok=True)
    caminho = os.path.join(destino_abs, nome)
    with open(caminho, "wb") as f:
        f.write(arquivo.getbuffer())
    return caminho
