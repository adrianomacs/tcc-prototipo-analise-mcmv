"""Testes do empacotamento em 3D Tiles (passo 3)."""

import math
import os

import pytest

from core.infra.exportadores import tiles3d as t3d

# --- transform ENU -> ECEF (matemática pura) -------------------------------

def test_transform_ortonormal_e_origem():
    pytest.importorskip("pyproj")
    from pyproj import Transformer
    m = t3d.transform_ecef(-47.9, -22.58, 0.0, 0.0)
    assert len(m) == 16

    cols = [m[0:3], m[4:7], m[8:11]]
    for c in cols:
        assert math.isclose(math.hypot(*c), 1.0, abs_tol=1e-9)   # unitárias

    def dot(a, b):
        return sum(x * y for x, y in zip(a, b))
    assert abs(dot(cols[0], cols[1])) < 1e-9
    assert abs(dot(cols[1], cols[2])) < 1e-9
    assert abs(dot(cols[0], cols[2])) < 1e-9

    x, y, z = Transformer.from_crs("EPSG:4326", "EPSG:4978",
                                   always_xy=True).transform(-47.9, -22.58, 0.0)
    assert math.isclose(m[12], x, rel_tol=1e-9)
    assert math.isclose(m[13], y, rel_tol=1e-9)
    assert math.isclose(m[14], z, rel_tol=1e-9)


def test_rotacao_90_gira_eixo_x():
    # Em lon=0, lat=0: east=(0,1,0), north=(0,0,1). Rot 90° leva X do modelo ao Norte.
    m = t3d.transform_ecef(0.0, 0.0, 0.0, 90.0)
    mx = m[0:3]
    assert math.isclose(mx[2], 1.0, abs_tol=1e-9)


# --- geração do tileset (usa GLB real; pula sem IfcOpenShell) --------------

ifcopenshell = pytest.importorskip("ifcopenshell")
pytestmark = pytest.mark.integracao
from core.infra.exportadores import gltf as exportador_gltf


def _ifc_minimo(caminho: str) -> None:
    from ifcopenshell.api import run
    m = run("project.create_file", version="IFC4")
    proj = run("root.create_entity", m, ifc_class="IfcProject", name="P")
    run("unit.assign_unit", m)
    ctx = run("context.add_context", m, context_type="Model")
    body = run("context.add_context", m, context_type="Model",
               context_identifier="Body", target_view="MODEL_VIEW", parent=ctx)
    site = run("root.create_entity", m, ifc_class="IfcSite", name="Site")
    bld = run("root.create_entity", m, ifc_class="IfcBuilding", name="B")
    sto = run("root.create_entity", m, ifc_class="IfcBuildingStorey", name="S")
    run("aggregate.assign_object", m, relating_object=proj, products=[site])
    run("aggregate.assign_object", m, relating_object=site, products=[bld])
    run("aggregate.assign_object", m, relating_object=bld, products=[sto])
    wall = run("root.create_entity", m, ifc_class="IfcWall", name="Wall-1")
    rep = run("geometry.add_wall_representation", m, context=body,
              length=5.0, height=3.0, thickness=0.2)
    run("geometry.assign_representation", m, product=wall, representation=rep)
    run("spatial.assign_container", m, relating_structure=sto, products=[wall])
    m.write(caminho)


def test_gerar_tileset_estrutura(tmp_path):
    ifc = tmp_path / "m.ifc"
    _ifc_minimo(str(ifc))
    glb = tmp_path / "m.glb"
    exportador_gltf.exportar(str(ifc), str(glb))

    ancora = {"modo": "preciso", "lon": -47.9, "lat": -22.58,
              "altura": 0.0, "rotacao_graus": 0.0, "epsg": "EPSG:31983"}
    ts = t3d.gerar_tileset(str(glb), ancora, str(tmp_path / "tileset.json"))

    assert ts["asset"]["version"] == "1.1"
    assert len(ts["root"]["transform"]) == 16
    assert ts["root"]["content"]["uri"] == "m.glb"
    assert ts["root"]["boundingVolume"]["sphere"][3] > 0  # raio positivo
    assert (tmp_path / "tileset.json").exists()


def test_gerar_tileset_sem_ancora_falha(tmp_path):
    ifc = tmp_path / "m.ifc"
    _ifc_minimo(str(ifc))
    glb = tmp_path / "m.glb"
    exportador_gltf.exportar(str(ifc), str(glb))
    with pytest.raises(ValueError):
        t3d.gerar_tileset(str(glb), {"modo": "indisponivel", "lat": None, "lon": None},
                          str(tmp_path / "tileset.json"))


def test_orquestrador_sem_georref_avisa(tmp_path):
    # IFC mínimo não tem MapConversion nem lat/long -> âncora indisponível.
    ifc = tmp_path / "m.ifc"
    _ifc_minimo(str(ifc))
    res = t3d.exportar(str(ifc), str(tmp_path / "tiles"))
    assert res["tileset"] is None
    assert "aviso" in res
    assert os.path.exists(res["glb"])
