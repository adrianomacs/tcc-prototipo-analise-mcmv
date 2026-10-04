"""Cena 3D dos relatórios: os dados que a página entrega à cena.

A cor de cada elemento vem do relatório, e a caixa de cada revestimento do
``revestimentos.json`` da conversão (ADR-001); aqui se prende a junção dos
dois e a gravação do documento da cena, sem navegador.
"""

from __future__ import annotations

import json
import re

import pytest

pytest.importorskip("streamlit")

from app.componentes import cena3d  # noqa: E402


def test_ambientes_para_cena_levam_o_resultado():
    det = {"tipo": "larguras", "ambientes": [
        {"global_id": "a", "nome": "BWC", "atende": False, "categoria_rotulo": "Banheiro"},
        {"nome": "sem gid"}]}
    itens = cena3d.ambientes_para_cena(det)
    assert [i["global_id"] for i in itens] == ["a"]
    assert itens[0]["resultado"] == "nao_atende"
    assert itens[0]["rotulo"] == "não atende"


def test_revestimento_sem_caixa_fica_na_lista_e_fora_da_cena():
    itens = [{"global_id": "g1", "resultado": "atende"},
             {"global_id": "g2", "resultado": "neutro"}]
    caixas = [{"global_id": "g1", "min": [0, 0, 0], "max": [1, 0.01, 3],
               "espessura": 0.01}]
    juntos = {i["global_id"]: i for i in cena3d.revestimentos_com_caixas(itens, caixas)}
    assert juntos["g1"]["espessura"] == 0.01 and juntos["g1"]["resultado"] == "atende"
    assert "min" not in juntos["g2"]


def test_gravar_cena_preenche_todos_os_marcadores(tmp_path, monkeypatch):
    monkeypatch.setattr(cena3d, "_STATIC_DIR", str(tmp_path))
    viz = {"posicionavel": True, "glb_b64": "AAAA", "transform": [1.0] * 16,
           "espacos": [], "ancora": {"altura": 2.0}}
    revs = [{"global_id": "g1", "resultado": "nao_atende", "min": [0, 0, 0],
             "max": [1, 1, 1], "espessura": 1.0}]
    cena3d.gravar_cena(viz, revestimentos=revs)
    html = (tmp_path / "cena.html").read_text(encoding="utf-8")
    assert not re.search(r"__[A-Z_]+__", html)
    assert json.dumps(cena3d.COR_RESULTADO) in html
    assert '"g1"' in html


def test_legenda_tem_as_tres_cores():
    html = cena3d.legenda_cores()
    for cor in cena3d.COR_RESULTADO.values():
        assert cor in html


def test_cena_com_glb_por_endereco_nao_embute_base64(tmp_path, monkeypatch):
    monkeypatch.setattr(cena3d, "_STATIC_DIR", str(tmp_path))
    viz = {"posicionavel": True, "glb_b64": None, "transform": [1.0] * 16,
           "glb_url": "/app/static/modelos/bim_gis.glb?v=1", "espacos": []}
    cena3d.gravar_cena(viz)
    html = (tmp_path / "cena.html").read_text(encoding="utf-8")
    assert '"/app/static/modelos/bim_gis.glb?v=1"' in html
    assert 'const b64 = "";' in html
