"""EDI-019.1 — ramo ZB 1 e 2 da parede externa (≤ 0,6). A mecânica está em
``tests/core/regras/base/test_absortancia.py``; aqui, o que é DESTE arquivo:
o metadado, o limite, a faixa em vocabulário VIGENTE (ao contrário do
telhado) e a ausência de exceção por material (DN-02)."""

from __future__ import annotations

import pytest

from core.dominio.conhecimento.zona_bioclimatica import ZonaBioclimatica
from core.dominio.contratos.regra import Dominio, Verbo
from core.regras.base import agregacao as ag
from core.regras.gis_bim.edi_019_1_parede_zb_1_2 import EDI0191


def test_metadado():
    r = EDI0191
    assert r.id == "EDI-019.1"
    assert r.limite == 0.6 and r.parametro["absortancia_max"] == 0.6
    assert r.dominio is Dominio.GIS_BIM and r.verbo is Verbo.ATRIBUTO
    assert r.ids_spec is None and r.depende_de == []
    assert r.familia == "parede externa"
    assert r.excecoes_por_material is False      # 4.II.a.x não excetua (DN-02)
    assert r.ref_portaria.endswith("4.II.a.x.1")


def test_a_faixa_esta_no_vocabulario_vigente():
    """Diferença central em relação aos ramos de telhado (DN-08): aqui a
    cláusula foi migrada, então ``zonas`` traz classes de verdade."""
    assert EDI0191.zonas == ("1M", "1R", "2M", "2R")
    assert "1 e 2" in EDI0191.zonas_texto


@pytest.mark.parametrize("classe, esperado", [
    ("1M", ag.RAMO_APLICAVEL), ("1R", ag.RAMO_APLICAVEL),
    ("2M", ag.RAMO_APLICAVEL), ("2R", ag.RAMO_APLICAVEL),
    ("3A", ag.RAMO_INAPLICAVEL), ("6B", ag.RAMO_INAPLICAVEL),
])
def test_a_zona_seleciona_de_verdade(classe, esperado):
    aplic, _ = EDI0191().aplicabilidade_na_zona(
        ZonaBioclimatica(classe=classe, codigo_ibge="0000000"))
    assert aplic == esperado
