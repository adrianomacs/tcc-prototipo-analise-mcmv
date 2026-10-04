"""Modelo IFC real (via IfcOpenShell), para os poucos testes de georreferenciamento
e da regra EMP-001 que precisam do parser de verdade — complementa `ifc_falso.py`
(que evita IfcOpenShell) em vez de o substituir.
"""

from __future__ import annotations


def modelo_georreferenciado(site_lat, site_lon, country):
    """Projeto IFC4 com CRS, IfcSite e endereço postal — para os testes de
    consistência de localização e do detalhe da regra EMP-001.

    Requer IfcOpenShell instalado; quem chama esta função deve ter feito
    ``pytest.importorskip("ifcopenshell")`` antes.
    """
    import ifcopenshell.guid
    from ifcopenshell.api import run

    m = run("project.create_file", version="IFC4")
    run("root.create_entity", m, ifc_class="IfcProject", name="P")
    run("unit.assign_unit", m, length={"is_metric": True, "raw": "MILLIMETERS"})
    run("context.add_context", m, context_type="Model")
    run("georeference.add_georeferencing", m)
    # 's-Hertogenbosch em EPSG:28992, valores em mm (como o arquivo real)
    run("georeference.edit_georeferencing", m,
        projected_crs={"Name": "EPSG:28992"},
        coordinate_operation={"Eastings": 149626315.91, "Northings": 413717684.22,
                              "OrthogonalHeight": 0.0, "XAxisAbscissa": 1.0,
                              "XAxisOrdinate": 0.0, "Scale": 1.0})
    m.create_entity("IfcSite", GlobalId=ifcopenshell.guid.new(), Name="Site",
                    RefLatitude=list(site_lat), RefLongitude=list(site_lon))
    m.create_entity("IfcPostalAddress", Country=country, Town="'s-Hertogenbosch",
                    PostalCode="5231 RJ", AddressLines=["Hambakendreef 2A"])
    return m
