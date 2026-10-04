"""Teste do payload de visualização (GLB base64 + transform) e das caixas
dos revestimentos (``revestimentos.json``, ADR-001)."""

import base64
import json
import struct

import pytest

ifcopenshell = pytest.importorskip("ifcopenshell")
pytestmark = pytest.mark.integracao

from core.infra.exportadores import visualizacao


def _ifc_georref_mm(tmp, com_geo=True, com_covering=False):
    from ifcopenshell.api import run
    m = run("project.create_file", version="IFC4")
    proj = run("root.create_entity", m, ifc_class="IfcProject", name="P")
    run("unit.assign_unit", m, length={"is_metric": True, "raw": "MILLIMETERS"})
    ctx = run("context.add_context", m, context_type="Model")
    body = run("context.add_context", m, context_type="Model",
               context_identifier="Body", target_view="MODEL_VIEW", parent=ctx)
    site = run("root.create_entity", m, ifc_class="IfcSite", name="Site")
    bld = run("root.create_entity", m, ifc_class="IfcBuilding", name="B")
    sto = run("root.create_entity", m, ifc_class="IfcBuildingStorey", name="S")
    run("aggregate.assign_object", m, relating_object=proj, products=[site])
    run("aggregate.assign_object", m, relating_object=site, products=[bld])
    run("aggregate.assign_object", m, relating_object=bld, products=[sto])
    wall = run("root.create_entity", m, ifc_class="IfcWall", name="W")
    rep = run("geometry.add_wall_representation", m, context=body,
              length=5.0, height=3.0, thickness=0.2)
    run("geometry.assign_representation", m, product=wall, representation=rep)
    run("spatial.assign_container", m, relating_structure=sto, products=[wall])
    if com_covering:
        # Placa de 1 cm × 5 m × 3 m (um revestimento de fachada).
        cov = run("root.create_entity", m, ifc_class="IfcCovering", name="Pintura")
        rep_c = run("geometry.add_wall_representation", m, context=body,
                    length=5.0, height=3.0, thickness=0.01)
        run("geometry.assign_representation", m, product=cov, representation=rep_c)
        run("spatial.assign_container", m, relating_structure=sto, products=[cov])
    if com_geo:
        run("georeference.add_georeferencing", m)
        run("georeference.edit_georeferencing", m,
            projected_crs={"Name": "EPSG:28992"},
            coordinate_operation={"Eastings": 149626315.91, "Northings": 413717684.22,
                                  "OrthogonalHeight": 0.0, "XAxisAbscissa": 1.0,
                                  "XAxisOrdinate": 0.0, "Scale": 1.0})
    caminho = str(tmp / "m.ifc")
    m.write(caminho)
    return caminho


def test_payload_posicionavel(tmp_path):
    ifc = _ifc_georref_mm(tmp_path, com_geo=True)
    p = visualizacao.gerar_payload(ifc, str(tmp_path / "tiles"))
    assert p["posicionavel"] is True
    assert len(p["transform"]) == 16
    # base64 decodifica para um GLB válido
    assert base64.b64decode(p["glb_b64"])[:4] == b"glTF"


def test_payload_sem_georref(tmp_path):
    ifc = _ifc_georref_mm(tmp_path, com_geo=False)
    p = visualizacao.gerar_payload(ifc, str(tmp_path / "tiles"))
    assert p["posicionavel"] is False
    assert p["transform"] is None
    assert base64.b64decode(p["glb_b64"])[:4] == b"glTF"


def test_conversao_grava_a_caixa_do_revestimento(tmp_path):
    """A caixa sai do GLB, no frame local z-up: a placa de 1 cm tem essa
    espessura, e o payload a entrega à cena."""
    ifc = _ifc_georref_mm(tmp_path, com_covering=True)
    p = visualizacao.gerar_payload(ifc, str(tmp_path / "tiles"))
    revs = p["revestimentos"]
    assert len(revs) == 1 and revs[0]["nome"] == "Pintura"
    dims = sorted(round(b - a, 3) for a, b in zip(revs[0]["min"], revs[0]["max"]))
    assert dims == [0.01, 3.0, 5.0]
    assert revs[0]["espessura"] == pytest.approx(0.01, abs=1e-3)


def test_payload_sem_revestimentos_json_segue_sem_destaque(tmp_path):
    """Conversão antiga (sem o arquivo): a cena abre, só sem as caixas."""
    ifc = _ifc_georref_mm(tmp_path)
    pasta = tmp_path / "tiles"
    visualizacao.gerar_artefatos(ifc, str(pasta))
    (pasta / "revestimentos.json").unlink()
    assert visualizacao.carregar_payload(str(pasta))["revestimentos"] == []


def _glb_minimo(caminho, nos):
    """GLB só com o bloco JSON: nós nomeados, uma malha e um acessor cada."""
    gltf = {"asset": {"version": "2.0"}, "nodes": [], "meshes": [], "accessors": []}
    for nome, prims in nos.items():
        idx_prims = []
        for mn, mx in prims:
            gltf["accessors"].append({"min": mn, "max": mx, "count": 3,
                                      "type": "VEC3", "componentType": 5126})
            idx_prims.append({"attributes": {"POSITION": len(gltf["accessors"]) - 1}})
        gltf["meshes"].append({"primitives": idx_prims})
        gltf["nodes"].append({"name": nome, "mesh": len(gltf["meshes"]) - 1})
    corpo = json.dumps(gltf).encode()
    corpo += b" " * (-len(corpo) % 4)
    with open(caminho, "wb") as f:
        f.write(b"glTF" + struct.pack("<II", 2, 12 + 8 + len(corpo)))
        f.write(struct.pack("<I", len(corpo)) + b"JSON" + corpo)


def test_caixas_do_glb_une_primitivas_e_ignora_outros_nos(tmp_path):
    glb = tmp_path / "m.glb"
    _glb_minimo(glb, {"cov": [([0, 0, 0], [1, 2, 3]), ([-1, 0, 0], [0.5, 2, 4])],
                      "parede": [([0, 0, 0], [9, 9, 9])]})
    caixas = visualizacao.caixas_do_glb(str(glb), {"cov", "ausente"})
    assert set(caixas) == {"cov"}
    assert caixas["cov"]["min"] == [-1, 0, 0] and caixas["cov"]["max"] == [1, 2, 4]
    assert caixas["cov"]["espessura"] == 2
