"""Testes da âncora geográfica (passo 2)."""

import math

from core.infra.ifc.georref import ancora
from tests.apoio.ifc_falso import (
    modelo_ifc2x3,
    modelo_nivel_30,
    modelo_nivel_50,
    modelo_vazio,
)


def test_modo_preciso_reprojeta_origem():
    a = ancora.derivar(modelo_nivel_50(epsg="EPSG:31983",
                                       eastings=200000.0, northings=7500000.0))
    assert a.modo == "preciso"
    assert a.epsg == "EPSG:31983"
    # confere contra o pyproj diretamente
    from pyproj import Transformer
    lon, lat = Transformer.from_crs("EPSG:31983", "EPSG:4326",
                                    always_xy=True).transform(200000.0, 7500000.0)
    assert math.isclose(a.lon, lon, abs_tol=1e-6)
    assert math.isclose(a.lat, lat, abs_tol=1e-6)
    assert a.disponivel


def test_rotacao_do_map_conversion():
    # XAxisAbscissa=0, XAxisOrdinate=1 -> eixo X do modelo aponta para o Norte -> 90°
    m = modelo_nivel_50()
    for e in m.by_type("IfcMapConversion"):
        e.XAxisAbscissa, e.XAxisOrdinate = 0.0, 1.0
    a = ancora.derivar(m)
    assert math.isclose(a.rotacao_graus, 90.0, abs_tol=1e-6)


def test_modo_aproximado_pelo_site():
    # Sem CRS projetado (nível 30): usa lat/long do IfcSite.
    a = ancora.derivar(modelo_nivel_30())
    assert a.modo == "aproximado"
    assert math.isclose(a.lat, 23.0, abs_tol=1e-6)   # RefLatitude [23,0,0]
    assert math.isclose(a.lon, 46.0, abs_tol=1e-6)


def test_ifc2x3_cai_no_aproximado():
    # IFC2X3 não comporta CRS projetado, mas tem lat/long no site.
    a = ancora.derivar(modelo_ifc2x3())
    assert a.modo == "aproximado"


def test_modelo_vazio_indisponivel():
    a = ancora.derivar(modelo_vazio())
    assert a.modo == "indisponivel"
    assert not a.disponivel


def test_dms_negativo():
    # latitude sul: primeira componente negativa
    assert math.isclose(ancora._dms_para_graus([-22, 30, 0]), -22.5, abs_tol=1e-9)
    assert ancora._dms_para_graus(None) is None
