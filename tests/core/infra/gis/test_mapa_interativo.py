"""Testes da conversão payload-do-mapa -> Terreno (Enquadramento — R2).

Lógica pura: nenhum Streamlit, nenhum folium. O payload do plugin Draw é
imitado no formato que o ``st_folium`` devolve (lista de Features GeoJSON),
porque é justamente o formato de terceiro que pode mudar de versão.
"""

from __future__ import annotations

import pytest

from core.dominio import terreno as trn
from core.infra.gis import mapa_interativo as de_mapa

CG_LON, CG_LAT = -54.6215, -20.4712


def _poligono(lon: float = CG_LON, lat: float = CG_LAT, d: float = 0.0005) -> dict:
    return {"type": "Polygon", "coordinates": [[
        [lon - d, lat - d], [lon + d, lat - d], [lon + d, lat + d],
        [lon - d, lat + d], [lon - d, lat - d]]]}


def _feature(geo: dict) -> dict:
    return {"type": "Feature", "properties": {}, "geometry": geo}


# --- anel externo ----------------------------------------------------------

def test_anel_externo_de_polygon():
    anel = de_mapa.anel_externo(_poligono())
    assert len(anel) == 5 and anel[0] == anel[-1]
    assert all(isinstance(x, float) and isinstance(y, float) for x, y in anel)


def test_anel_externo_ignora_terceira_coordenada():
    geo = {"type": "Polygon", "coordinates": [[[CG_LON, CG_LAT, 500.0],
                                               [CG_LON + 0.001, CG_LAT, 500.0],
                                               [CG_LON + 0.001, CG_LAT + 0.001, 500.0],
                                               [CG_LON, CG_LAT, 500.0]]]}
    assert de_mapa.anel_externo(geo) == [(CG_LON, CG_LAT),
                                         (CG_LON + 0.001, CG_LAT),
                                         (CG_LON + 0.001, CG_LAT + 0.001),
                                         (CG_LON, CG_LAT)]


def test_anel_externo_recusa_geometria_sem_area_com_mensagem_util():
    for geo in ({"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
                {"type": "Point", "coordinates": [0, 0]}):
        with pytest.raises(ValueError, match="desenhe um polígono"):
            de_mapa.anel_externo(geo)


def test_multipolygon_usa_a_maior_parte():
    pequeno = _poligono(d=0.0002)["coordinates"]
    grande = _poligono(d=0.0020)["coordinates"]
    geo = {"type": "MultiPolygon", "coordinates": [pequeno, grande]}
    anel = de_mapa.anel_externo(geo)
    largura = max(x for x, _ in anel) - min(x for x, _ in anel)
    assert largura == pytest.approx(0.0040, rel=1e-6)


# --- extração de geometrias de payloads variados --------------------------

def test_geometrias_aceita_os_formatos_que_o_componente_devolve():
    geo = _poligono()
    assert de_mapa.geometrias([_feature(geo)]) == [geo]
    assert de_mapa.geometrias({"type": "FeatureCollection",
                               "features": [_feature(geo)]}) == [geo]
    assert de_mapa.geometrias(_feature(geo)) == [geo]
    assert de_mapa.geometrias(geo) == [geo]


def test_geometrias_de_payload_vazio_e_lista_vazia():
    for vazio in (None, [], {}, {"type": "FeatureCollection", "features": []}):
        assert de_mapa.geometrias(vazio) == []


# --- construção do terreno -------------------------------------------------

def test_terreno_desenhado_produz_poligonal_aproximada():
    t = de_mapa.terreno_desenhado([_feature(_poligono())])
    assert t.nivel == trn.NIVEL_POLIGONAL
    assert t.origem == trn.ORIGEM_DESENHADA
    assert t.precisao == trn.PRECISAO_APROXIMADA
    assert t.area_m2 > 0 and t.perimetro_m > 0
    assert t.atende(trn.NIVEL_POLIGONAL)


def test_terreno_desenhado_com_varios_poligonos_usa_o_ultimo_e_avisa():
    primeiro = _feature(_poligono(d=0.0002))
    ultimo = _feature(_poligono(d=0.0020))
    t = de_mapa.terreno_desenhado([primeiro, ultimo])
    grande = de_mapa.terreno_desenhado([ultimo])
    assert t.area_m2 == pytest.approx(grande.area_m2, rel=1e-9)
    assert any("último desenhado" in a for a in t.avisos)


def test_terreno_desenhado_sem_poligono_recusa():
    with pytest.raises(ValueError, match="Nenhum polígono"):
        de_mapa.terreno_desenhado([])
    with pytest.raises(ValueError, match="Nenhum polígono"):
        de_mapa.terreno_desenhado([_feature({"type": "LineString",
                                             "coordinates": [[0, 0], [1, 1]]})])


def test_terreno_de_clique_aceita_a_chave_lng_do_folium():
    t = de_mapa.terreno_de_clique({"lat": CG_LAT, "lng": CG_LON})
    assert t.nivel == trn.NIVEL_PONTO
    assert t.centro_wgs84 == pytest.approx((CG_LAT, CG_LON), abs=1e-9)
    assert not t.atende(trn.NIVEL_POLIGONAL)


def test_terreno_de_clique_sem_ponto_recusa():
    for vazio in (None, {}, {"lat": CG_LAT}):
        with pytest.raises(ValueError, match="Nenhum ponto"):
            de_mapa.terreno_de_clique(vazio)


def test_terreno_de_coordenadas_e_declarado_nao_aproximado():
    t = de_mapa.terreno_de_coordenadas(CG_LAT, CG_LON)
    assert t.origem == trn.ORIGEM_PONTO
    assert t.precisao == trn.PRECISAO_DECLARADA
    assert t.crs_metrico == "EPSG:31981"


def test_terreno_de_coordenadas_recusa_valor_fora_de_intervalo():
    with pytest.raises(ValueError):
        de_mapa.terreno_de_coordenadas(120.0, CG_LON)
