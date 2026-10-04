"""Regressão: unidade do IfcMapConversion (Eastings/Northings -> metros).

Replica o caso real do arquivo da buildingSMART (Gymzaal Amersfoort, exportado
do Revit): projeto em milímetros e offsets do MapConversion em mm, sem MapUnit.
Sem a conversão de unidade, a reprojeção caía no Pacífico (bug de 1000x).
Pulado se o IfcOpenShell não estiver instalado.
"""

import math

import pytest

ifcopenshell = pytest.importorskip("ifcopenshell")
pytestmark = pytest.mark.integracao

from core.infra.ifc.georref import (
    ancora,
    leitor_crs,
)


def _ifc_georref(raw_unidade: str, eastings: float, northings: float):
    from ifcopenshell.api import run
    m = run("project.create_file", version="IFC4")
    run("root.create_entity", m, ifc_class="IfcProject", name="P")
    run("unit.assign_unit", m, length={"is_metric": True, "raw": raw_unidade})
    run("context.add_context", m, context_type="Model")
    run("georeference.add_georeferencing", m)
    run("georeference.edit_georeferencing", m,
        projected_crs={"Name": "EPSG:28992"},
        coordinate_operation={"Eastings": eastings, "Northings": northings,
                              "OrthogonalHeight": 0.0, "XAxisAbscissa": 1.0,
                              "XAxisOrdinate": 0.0, "Scale": 1.0})
    return m


def test_offsets_em_mm_convertidos_para_metros():
    m = _ifc_georref("MILLIMETERS", 149692000.0, 413790000.0)
    info = leitor_crs.ler(m)
    assert math.isclose(info.unidade_para_m, 0.001, rel_tol=1e-9)
    assert math.isclose(info.map_conversion["eastings"], 149692.0, rel_tol=1e-6)


def test_ancora_amersfoort_com_modelo_em_mm():
    m = _ifc_georref("MILLIMETERS", 149692000.0, 413790000.0)
    a = ancora.derivar(m)
    assert a.modo == "preciso"
    assert math.isclose(a.lon, 5.3104, abs_tol=1e-2)
    assert math.isclose(a.lat, 51.7128, abs_tol=1e-2)


def test_modelo_em_metros_nao_e_reescalado():
    m = _ifc_georref("METERS", 149692.0, 413790.0)
    info = leitor_crs.ler(m)
    assert math.isclose(info.unidade_para_m, 1.0, rel_tol=1e-9)
    assert math.isclose(info.map_conversion["eastings"], 149692.0, rel_tol=1e-6)
    a = ancora.derivar(m)
    assert math.isclose(a.lon, 5.3104, abs_tol=1e-2)
    assert math.isclose(a.lat, 51.7128, abs_tol=1e-2)


def _ifc_contraditorio():
    """MapUnit declara METRE, projeto em mm e offsets em mm (bug do Revit real)."""
    from ifcopenshell.api import run
    m = run("project.create_file", version="IFC4")
    run("root.create_entity", m, ifc_class="IfcProject", name="P")
    run("unit.assign_unit", m, length={"is_metric": True, "raw": "MILLIMETERS"})
    run("context.add_context", m, context_type="Model")
    run("georeference.add_georeferencing", m)
    run("georeference.edit_georeferencing", m,
        projected_crs={"Name": "EPSG:28992"},
        coordinate_operation={"Eastings": 149626315.91, "Northings": 413717684.22,
                              "OrthogonalHeight": 0.0, "XAxisAbscissa": 1.0,
                              "XAxisOrdinate": 0.0, "Scale": 1.0})
    # força MapUnit = METRE (contradição com os valores em mm)
    crs = m.by_type("IfcProjectedCRS")[0]
    crs.MapUnit = m.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE")
    return m


def test_mapunit_metro_mas_valores_mm_e_reinterpretado():
    m = _ifc_contraditorio()
    info = leitor_crs.ler(m)
    assert math.isclose(info.unidade_para_m, 0.001, rel_tol=1e-9)
    assert info.dentro_area_uso is True
    assert "inconsistente" in info.aviso.lower()
    a = ancora.derivar(m)
    assert math.isclose(a.lon, 5.31, abs_tol=1e-2)
    assert math.isclose(a.lat, 51.71, abs_tol=1e-2)
    assert "inconsistente" in a.mensagem.lower()
