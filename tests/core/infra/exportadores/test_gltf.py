"""Teste de integração do conversor IFC -> GLB (incluindo filtro de tipos).

Gera um IFC4 mínimo (uma parede) e valida o GLB produzido e a filtragem por
tipo. Pulado se o IfcOpenShell não estiver instalado.
"""

import json
import struct

import pytest

ifcopenshell = pytest.importorskip("ifcopenshell")
pytestmark = pytest.mark.integracao

from core.infra.exportadores import gltf as exportador_gltf


def _ifc_minimo(caminho: str) -> str:
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
    return wall.GlobalId


def _json_do_glb(data: bytes) -> dict:
    assert data[:4] == b"glTF", "assinatura GLB ausente"
    clen = struct.unpack("<I", data[12:16])[0]
    return json.loads(data[20:20 + clen].decode("utf-8"))


def test_exporta_glb_com_geometria_e_guid(tmp_path):
    ifc = tmp_path / "m.ifc"
    guid = _ifc_minimo(str(ifc))

    glb = tmp_path / "m.glb"
    exportador_gltf.exportar(str(ifc), str(glb))

    data = glb.read_bytes()
    assert len(data) > 0
    js = _json_do_glb(data)
    assert len(js.get("meshes", [])) >= 1, "GLB sem malhas"
    nomes = [n.get("name") for n in js.get("nodes", [])]
    assert guid in nomes, "nó não foi nomeado pelo GlobalId"


def test_erro_quando_sem_geometria(tmp_path):
    from ifcopenshell.api import run
    m = run("project.create_file", version="IFC4")
    run("root.create_entity", m, ifc_class="IfcProject", name="P")
    vazio = tmp_path / "vazio.ifc"
    m.write(str(vazio))
    with pytest.raises(ValueError):
        exportador_gltf.exportar(str(vazio), str(tmp_path / "x.glb"))


def test_excluir_tipo_presente_remove_da_exportacao(tmp_path):
    # Excluir o único tipo com geometria deixa a exportação vazia -> ValueError.
    ifc = tmp_path / "m.ifc"
    _ifc_minimo(str(ifc))
    with pytest.raises(ValueError):
        exportador_gltf.exportar(str(ifc), str(tmp_path / "x.glb"),
                                 excluir_tipos=["IfcWall"])


def test_excluir_tipo_ausente_preserva_geometria(tmp_path):
    # Excluir um tipo que não está no modelo não afeta a parede.
    ifc = tmp_path / "m.ifc"
    guid = _ifc_minimo(str(ifc))
    glb = tmp_path / "m.glb"
    exportador_gltf.exportar(str(ifc), str(glb), excluir_tipos=["IfcSpace"])
    js = _json_do_glb(glb.read_bytes())
    assert guid in [n.get("name") for n in js.get("nodes", [])]


def test_ifc_nao_e_modificado_pela_exportacao(tmp_path):
    # Garantia de semântica: o IFC permanece com o mesmo nº de entidades.
    ifc = tmp_path / "m.ifc"
    _ifc_minimo(str(ifc))
    modelo = ifcopenshell.open(str(ifc))
    antes = len(list(modelo))
    exportador_gltf.exportar_modelo(modelo, str(tmp_path / "m.glb"),
                                    excluir_tipos=["IfcSpace"])
    assert len(list(modelo)) == antes
    assert len(modelo.by_type("IfcWall")) == 1
