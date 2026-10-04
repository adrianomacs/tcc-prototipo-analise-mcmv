"""Exportação do contexto geográfico para GeoJSON.

Gera o artefato de feições territoriais (lotes, equipamentos, malha viária)
consumido pela visualização. Reprojeta as camadas para coordenadas geográficas
(EPSG:4674) antes de exportar, mantendo compatibilidade com o CesiumJS.
"""

from __future__ import annotations

import os
from typing import Any


def exportar(camadas_gis: dict[str, Any], pasta_destino: str,
             epsg_geografico: str = "EPSG:4674") -> list[str]:
    """Exporta cada camada GIS como um arquivo GeoJSON reprojetado.

    Retorna a lista de caminhos gerados.
    """
    os.makedirs(pasta_destino, exist_ok=True)
    gerados: list[str] = []
    for nome, gdf in camadas_gis.items():
        try:
            gdf_geo = gdf.to_crs(epsg_geografico)
        except Exception:
            gdf_geo = gdf  # camada sem CRS definido: exporta como está
        destino = os.path.join(pasta_destino, f"{nome}.geojson")
        gdf_geo.to_file(destino, driver="GeoJSON")
        gerados.append(destino)
    return gerados
