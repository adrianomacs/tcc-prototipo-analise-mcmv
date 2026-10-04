"""Persistência do terreno resolvido — ``artefatos/terreno.json``.

Contrato entre a etapa de entrada e a de análise, no mesmo padrão de
``status.json`` / ``espacos.json``. Existe por uma razão
prática: o Streamlit reexecuta o script a cada interação, e a resolução do
terreno não pode depender de estado em memória — a análise, o mapa e o
relatório leem o mesmo arquivo.

Escrita atômica (arquivo temporário + ``os.replace``) para que uma leitura
concorrente nunca veja JSON parcial.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone

from core.dominio.terreno import Terreno

NOME_ARQUIVO = "terreno.json"


def caminho(pasta_artefatos: str) -> str:
    return os.path.join(pasta_artefatos, NOME_ARQUIVO)


def gravar(terreno: Terreno, pasta_artefatos: str) -> str:
    """Grava o terreno e devolve o caminho do arquivo."""
    os.makedirs(pasta_artefatos, exist_ok=True)
    destino = caminho(pasta_artefatos)
    dados = terreno.to_dict()
    dados["gravado_em"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    fd, tmp = tempfile.mkstemp(dir=pasta_artefatos, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
        os.replace(tmp, destino)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return destino


def ler(pasta_artefatos: str) -> Terreno | None:
    """Lê o terreno gravado, ou None se ainda não houver (ou estiver ilegível)."""
    origem = caminho(pasta_artefatos)
    if not os.path.exists(origem):
        return None
    try:
        with open(origem, "r", encoding="utf-8") as f:
            return Terreno.from_dict(json.load(f))
    except (OSError, ValueError, TypeError, KeyError):
        return None


def descartar(pasta_artefatos: str) -> None:
    """Remove o artefato — usado ao iniciar uma nova análise."""
    origem = caminho(pasta_artefatos)
    if os.path.exists(origem):
        os.unlink(origem)
