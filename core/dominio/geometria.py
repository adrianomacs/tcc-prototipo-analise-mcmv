"""Escolha e uso do sistema de coordenadas métrico do terreno.

Toda medida do Enquadramento (centróide, área, perímetro, distância) é feita em
um **CRS projetado métrico**, nunca em graus: o centróide calculado em lat/long
cai em outro lugar, e área em graus não tem significado. O CRS canônico interno
é **SIRGAS 2000 / UTM**, com o fuso derivado do próprio terreno.

Por que derivar o fuso em vez de fixá-lo: ``config/settings.yaml`` trazia
``EPSG:31983`` (fuso 23S) como exemplo, o que só serve para parte do país. O
fuso passa a vir da longitude do terreno, e o EPSG efetivamente usado fica
registrado na procedência — o resultado diz em que sistema foi medido.
"""

from __future__ import annotations

import math
from typing import Any

CRS_GEOGRAFICO = "EPSG:4326"        # WGS 84 — datum do mapa e da entrada por mapa
CRS_SIRGAS_GEOGRAFICO = "EPSG:4674"  # SIRGAS 2000 (geográficas)

# SIRGAS 2000 / UTM: os códigos EPSG são contíguos por fuso.
#   sul  : EPSG = 31960 + fuso, fusos 17S a 25S -> 31977..31985
#          (âncora conhecida: 31983 = SIRGAS 2000 / UTM zona 23S)
#   norte: EPSG = 31954 + fuso, fusos 11N a 22N -> 31965..31976
_SIRGAS_SUL_BASE = 31960
_SIRGAS_NORTE_BASE = 31954
_SIRGAS_SUL_FUSOS = range(17, 26)
_SIRGAS_NORTE_FUSOS = range(11, 23)


def fuso_utm(lon: float) -> int:
    """Fuso UTM de uma longitude em graus decimais (1 a 60)."""
    return int(math.floor((float(lon) + 180.0) / 6.0) % 60) + 1


def epsg_metrico(lon: float, lat: float) -> str:
    """CRS projetado métrico adequado ao ponto informado.

    Devolve SIRGAS 2000 / UTM quando o fuso está na cobertura do datum (caso de
    todo o território brasileiro) e, fora dela, WGS 84 / UTM — para que o
    protótipo não quebre com um dado fora do Brasil, apenas registre outro CRS.
    """
    fuso = fuso_utm(lon)
    norte = float(lat) >= 0.0
    if norte and fuso in _SIRGAS_NORTE_FUSOS:
        return f"EPSG:{_SIRGAS_NORTE_BASE + fuso}"
    if not norte and fuso in _SIRGAS_SUL_FUSOS:
        return f"EPSG:{_SIRGAS_SUL_BASE + fuso}"
    return f"EPSG:{(32600 if norte else 32700) + fuso}"


def transformador(de: str, para: str) -> Any:
    """Transformer do pyproj entre dois CRS, sempre em ordem (x, y)."""
    from pyproj import Transformer

    return Transformer.from_crs(de, para, always_xy=True)


def reprojetar_ponto(x: float, y: float, de: str, para: str) -> tuple[float, float]:
    """Reprojeta um par (x, y) — devolve (x, y) no CRS de destino."""
    return transformador(de, para).transform(float(x), float(y))


def reprojetar(geometria: Any, de: str, para: str) -> Any:
    """Reprojeta uma geometria Shapely entre dois CRS."""
    from shapely.ops import transform

    t = transformador(de, para)
    return transform(lambda x, y, z=None: t.transform(x, y), geometria)


def fusos_abrangidos(lon_min: float, lon_max: float) -> list[int]:
    """Fusos UTM cobertos por uma faixa de longitude (detecta terreno a cavaleiro)."""
    a, b = fuso_utm(lon_min), fuso_utm(lon_max)
    return list(range(min(a, b), max(a, b) + 1))
