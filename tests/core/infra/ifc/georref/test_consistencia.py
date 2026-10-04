"""Testes do validador de consistência de localização (endereço × site × CRS)."""

import math

import pytest

from core.infra.ifc.georref import consistencia as cons
from tests.apoio.ifc_real import modelo_georreferenciado

# --- helpers puros (sem IfcOpenShell) --------------------------------------

def test_haversine_distancia_conhecida():
    # 1 grau de longitude no equador ~ 111.32 km
    assert math.isclose(cons._haversine_km((0.0, 0.0), (0.0, 1.0)), 111.32, abs_tol=0.5)


def test_mesmo_pais_normalizado():
    assert cons._mesmo_pais("The Netherlands", "Netherlands - onshore, incl. Waddenzee")
    assert not cons._mesmo_pais("Brazil", "Netherlands - onshore")


# --- integração (constrói IFC; pula sem IfcOpenShell) ----------------------

ifcopenshell = pytest.importorskip("ifcopenshell")
pytestmark = pytest.mark.integracao


def test_divergencia_do_site_e_sinalizada():
    # IfcSite em Boston (default Revit), CRS em 's-Hertogenbosch.
    m = modelo_georreferenciado((42, 21, 31, 181945), (-71, -3, -24, -263305), "The Netherlands")
    loc = cons.avaliar(m)
    assert loc.distancia_site_crs_km > 1000
    assert loc.consistente is False
    assert any("IfcSite" in a for a in loc.avisos)
    # país do endereço bate com o CRS (NL) -> sem aviso de país
    assert not any("País" in a for a in loc.avisos)


def test_site_proximo_do_crs_consistente():
    # IfcSite ~ na mesma posição do CRS (51.71, 5.31).
    m = modelo_georreferenciado((51, 42, 44, 0), (5, 18, 34, 0), "The Netherlands")
    loc = cons.avaliar(m)
    assert loc.distancia_site_crs_km < 1.0
    assert loc.consistente is True
    assert loc.avisos == []


def test_pais_divergente_e_sinalizado():
    # Endereço diz Brasil, mas CRS é holandês.
    m = modelo_georreferenciado((51, 42, 44, 0), (5, 18, 34, 0), "Brazil")
    loc = cons.avaliar(m)
    assert any("País" in a for a in loc.avisos)
