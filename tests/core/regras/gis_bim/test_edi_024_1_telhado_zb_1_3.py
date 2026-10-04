"""EDI-024.1 — ramo ZB 1, 2 e 3 do telhado (≤ 0,6). A mecânica está testada em
``tests/core/regras/base/test_absortancia.py``; aqui, o que é DESTE arquivo:
o metadado, o limite e o fato de a cláusula não migrada o tornar candidato
em todo município (DN-08)."""

from __future__ import annotations

from core.dominio.conhecimento.zona_bioclimatica import ZonaBioclimatica
from core.dominio.contratos.regra import Dominio, Verbo
from core.regras.base import agregacao as ag
from core.regras.gis_bim.edi_024_1_telhado_zb_1_3 import EDI0241


def test_metadado():
    r = EDI0241
    assert r.id == "EDI-024.1"
    assert r.limite == 0.6 and r.parametro["absortancia_max"] == 0.6
    assert r.dominio is Dominio.GIS_BIM and r.verbo is Verbo.ATRIBUTO
    assert r.ids_spec is None and r.depende_de == []
    assert r.zonas == () and "1, 2 e 3" in r.zonas_texto
    assert r.ref_portaria.endswith("4.III.i.i")


def test_candidato_em_toda_zona():
    for classe in ("1M", "3B", "6B"):
        aplic, _ = EDI0241().aplicabilidade_na_zona(
            ZonaBioclimatica(classe=classe, codigo_ibge="0000000"))
        assert aplic == ag.RAMO_INDETERMINADA
