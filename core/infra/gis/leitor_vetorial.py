"""Leitura de camadas geoespaciais com GeoPandas.

Carrega as camadas exigidas pelos requisitos selecionados (ex.: equipamentos
urbanos, malha viária) em GeoDataFrames, indexados por um nome semântico.
"""

from __future__ import annotations

import os
from typing import Any


def carregar_camada(caminho: str) -> Any:
    """Lê um arquivo geoespacial (.shp, .geojson, .gpkg) como GeoDataFrame."""
    import geopandas as gpd

    return gpd.read_file(caminho)


def carregar_pasta(pasta_gis: str) -> dict[str, Any]:
    """Carrega todas as camadas de uma pasta, indexadas pelo nome do arquivo.

    Ex.: ``entradas/gis/equipamento_escola.geojson`` -> chave 'equipamento_escola'.
    """
    camadas: dict[str, Any] = {}
    if not os.path.isdir(pasta_gis):
        return camadas
    for nome in os.listdir(pasta_gis):
        if nome.lower().endswith((".shp", ".geojson", ".json", ".gpkg")):
            chave = os.path.splitext(nome)[0]
            camadas[chave] = carregar_camada(os.path.join(pasta_gis, nome))
    return camadas
