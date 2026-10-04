"""Grupos de requisitos — leitura da coleção declarativa.

Um grupo agrega regras individuais para apresentação e seleção **em bloco**
É camada de organização: a execução continua regra a regra no
executor. A definição vive em ``config/grupos_requisitos.yaml`` (YAML declarativo,
coerente com ``regras_ativas.yaml``).

A *situação* de cada regra (implementada ou não) não é declarada no YAML:
deriva do registro de regras (``regras_registradas()``) em tempo de execução.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import yaml

CAMINHO_PADRAO = os.path.join("config", "grupos_requisitos.yaml")


@dataclass(frozen=True)
class RegraDoGrupo:
    """Espelho enxuto de uma regra para a UI do grupo."""
    id: str
    rotulo: str = ""
    parametro: str = ""
    aplicabilidade: str = "ambas"  # unifamiliar | multifamiliar | ambas


@dataclass(frozen=True)
class Grupo:
    id: str
    rotulo: str
    camada: str = ""
    porta: str = ""
    descricao: str = ""
    regras: list[RegraDoGrupo] = field(default_factory=list)

    @property
    def ids(self) -> list[str]:
        return [r.id for r in self.regras]


def carregar(caminho: str = CAMINHO_PADRAO) -> dict[str, Grupo]:
    """Lê o YAML e devolve os grupos indexados por id (vazio se não existir)."""
    if not os.path.exists(caminho):
        return {}
    with open(caminho, "r", encoding="utf-8") as f:
        dados = yaml.safe_load(f) or {}

    grupos: dict[str, Grupo] = {}
    for g in dados.get("grupos") or []:
        regras = [RegraDoGrupo(
                      id=str(r.get("id", "")).strip(),
                      rotulo=str(r.get("rotulo", "")).strip(),
                      parametro=str(r.get("parametro", "")).strip(),
                      aplicabilidade=str(r.get("aplicabilidade", "ambas")).strip(),
                  ) for r in (g.get("regras") or [])]
        grupo = Grupo(id=str(g.get("id", "")).strip(),
                      rotulo=str(g.get("rotulo", "")).strip(),
                      camada=str(g.get("camada", "")).strip(),
                      porta=str(g.get("porta", "")).strip(),
                      descricao=str(g.get("descricao", "")).strip(),
                      regras=regras)
        if grupo.id:
            grupos[grupo.id] = grupo
    return grupos
