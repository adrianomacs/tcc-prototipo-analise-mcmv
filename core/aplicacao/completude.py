"""Verificações de completude da Camada I.

Condicionam o restante do fluxo: validade do arquivo IFC, presença de
informações de georreferenciamento e disponibilidade das camadas GIS exigidas,
com seus sistemas de coordenadas e semântica identificados.

Importante (Passo 3): a completude da trilha GIS é independente da trilha BIM.
Estas funções apenas relatam o estado; quem decide o roteamento é o executor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RelatorioCompletude:
    ifc_valido: bool = False
    tem_georreferenciamento: bool = False
    camadas_gis_presentes: list[str] = field(default_factory=list)
    observacoes: list[str] = field(default_factory=list)


def checar_ifc(modelo: Any) -> tuple[bool, str]:
    """Confere se o modelo IFC foi aberto e possui um IfcProject."""
    if modelo is None:
        return False, "modelo IFC não carregado"
    try:
        projetos = modelo.by_type("IfcProject")
    except Exception as exc:
        return False, f"falha ao inspecionar o IFC: {exc!r}"
    if not projetos:
        return False, "IfcProject ausente"
    return True, "ok"


def checar_camadas(camadas_gis: dict[str, Any], exigidas: list[str]) -> tuple[bool, list[str]]:
    """Confere se as camadas GIS exigidas pelos requisitos estão presentes."""
    faltantes = [c for c in exigidas if c not in camadas_gis]
    return (len(faltantes) == 0), faltantes


def avaliar(modelo: Any, camadas_gis: dict[str, Any], georref: dict[str, Any],
            camadas_exigidas: list[str] | None = None) -> RelatorioCompletude:
    """Consolida as checagens de completude em um relatório."""
    rel = RelatorioCompletude()

    ok_ifc, msg = checar_ifc(modelo)
    rel.ifc_valido = ok_ifc
    if not ok_ifc:
        rel.observacoes.append(f"IFC: {msg}")

    rel.tem_georreferenciamento = bool(georref.get("valido", False))
    rel.camadas_gis_presentes = sorted(camadas_gis.keys())

    if camadas_exigidas:
        ok_cam, faltantes = checar_camadas(camadas_gis, camadas_exigidas)
        if not ok_cam:
            rel.observacoes.append(f"Camadas GIS faltantes: {', '.join(faltantes)}")

    return rel
