"""Terreno a partir do mapa — desenho, clique ou coordenada digitada.

Camada fina e **pura** entre o componente de mapa (``app/_mapa.py``) e os
construtores de ``terreno.py``: converte o que o mapa devolve em geometria,
sem tocar em Streamlit. Fica aqui, e não no app, para poder ser testada sem
interface — o desenho é a entrada mais usada do Enquadramento e a que mais
depende de payload de terceiro (plugin Draw do folium).

O que o ``st_folium`` devolve em ``all_drawings`` é uma lista de *Features*
GeoJSON; aceita-se também FeatureCollection, Feature isolada ou geometria crua,
porque o formato varia com a versão do componente.
"""

from __future__ import annotations

from typing import Any

from core.dominio import terreno as trn


def anel_externo(geometria: dict) -> list[tuple[float, float]]:
    """Anel externo de um Polygon GeoJSON, como pares (lon, lat).

    Rejeita explicitamente o que não delimita área: um traçado de linha ou um
    ponto solto não são terreno, e o erro precisa dizer isso — não virar uma
    poligonal degenerada mais adiante.
    """
    tipo = (geometria or {}).get("type", "")
    coords = (geometria or {}).get("coordinates")
    if tipo == "Polygon":
        if not coords or not coords[0]:
            raise ValueError("Polígono sem coordenadas.")
        return [(float(x), float(y)) for x, y, *_ in coords[0]]
    if tipo == "MultiPolygon":
        if not coords:
            raise ValueError("MultiPolygon sem coordenadas.")
        # Maior anel externo entre as partes (heurística de área em graus,
        # suficiente para escolher a parte principal antes de reprojetar).
        partes = [[(float(x), float(y)) for x, y, *_ in parte[0]] for parte in coords]
        return max(partes, key=_area_bruta)
    raise ValueError(f"A geometria desenhada é do tipo '{tipo}': desenhe um "
                     "polígono (ou retângulo) delimitando o terreno.")


def _area_bruta(anel: list[tuple[float, float]]) -> float:
    """Área do polígono em graus² (fórmula do shoelace) — só para comparar partes."""
    s = 0.0
    for (x1, y1), (x2, y2) in zip(anel, anel[1:] + anel[:1]):
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def geometrias(payload: Any) -> list[dict]:
    """Extrai as geometrias GeoJSON de um payload do mapa, em ordem de desenho."""
    if not payload:
        return []
    if isinstance(payload, dict):
        if payload.get("type") == "FeatureCollection":
            return [f.get("geometry") for f in (payload.get("features") or [])
                    if f.get("geometry")]
        if payload.get("type") == "Feature":
            geo = payload.get("geometry")
            return [geo] if geo else []
        if payload.get("type"):          # geometria crua
            return [payload]
        return []
    if isinstance(payload, (list, tuple)):
        saida: list[dict] = []
        for item in payload:
            saida.extend(geometrias(item))
        return saida
    return []


def terreno_desenhado(payload: Any) -> trn.Terreno:
    """Constrói o terreno a partir do desenho feito no mapa.

    Quando há mais de um polígono no mapa, vale **o último desenhado** (é o que
    o usuário acabou de fazer) e o fato entra nos avisos: silenciosamente usar
    um de vários seria a pior escolha possível.
    """
    geos = [g for g in geometrias(payload)
            if (g or {}).get("type") in ("Polygon", "MultiPolygon")]
    if not geos:
        raise ValueError("Nenhum polígono desenhado no mapa.")

    t = trn.de_poligonal_wgs84(
        anel_externo(geos[-1]),
        origem=trn.ORIGEM_DESENHADA,
        precisao=trn.PRECISAO_APROXIMADA,
        procedencia={"entrada": "poligonal desenhada sobre o mapa (OSM)"},
    )
    if len(geos) > 1:
        t.avisos.append(f"Havia {len(geos)} polígonos no mapa; considerado o "
                        "último desenhado. Apague os demais para evitar dúvida.")
    return t


def terreno_de_clique(payload: Any) -> trn.Terreno:
    """Constrói o terreno (nível ponto) a partir do clique no mapa."""
    dados = payload or {}
    lat, lon = dados.get("lat"), dados.get("lng", dados.get("lon"))
    if lat is None or lon is None:
        raise ValueError("Nenhum ponto marcado no mapa.")
    return trn.de_ponto_wgs84(
        lat, lon, origem=trn.ORIGEM_DESENHADA, precisao=trn.PRECISAO_APROXIMADA,
        procedencia={"entrada": "centro marcado por clique no mapa (OSM)"},
    )


def terreno_de_coordenadas(lat: float, lon: float) -> trn.Terreno:
    """Constrói o terreno (nível ponto) a partir de coordenadas digitadas."""
    return trn.de_ponto_wgs84(
        lat, lon, origem=trn.ORIGEM_PONTO, precisao=trn.PRECISAO_DECLARADA,
        procedencia={"entrada": "coordenadas do centro informadas pelo usuário"},
    )
