"""EDI-024.2 — ramo ZB 4 a 8 do telhado (≤ 0,4). Mecânica em
``tests/core/regras/base/test_absortancia.py``; aqui só o que é deste arquivo."""

from __future__ import annotations

from core.dominio.conhecimento.zona_bioclimatica import ZonaBioclimatica
from core.dominio.contratos.regra import Dominio, Verbo
from core.regras.base import agregacao as ag
from core.regras.gis_bim.edi_024_2_telhado_zb_4_8 import EDI0242


def test_metadado():
    r = EDI0242
    assert r.id == "EDI-024.2"
    assert r.limite == 0.4 and r.parametro["absortancia_max"] == 0.4
    assert r.dominio is Dominio.GIS_BIM and r.verbo is Verbo.ATRIBUTO
    assert r.ids_spec is None and r.depende_de == []
    assert r.zonas == () and "7 e 8" in r.zonas_texto
    assert r.ref_portaria.endswith("4.III.i.ii")


def test_candidato_em_toda_zona():
    for classe in ("1M", "3B", "6B"):
        aplic, _ = EDI0242().aplicabilidade_na_zona(
            ZonaBioclimatica(classe=classe, codigo_ibge="0000000"))
        assert aplic == ag.RAMO_INDETERMINADA


def test_os_dois_ramos_particionam_o_zoneamento_de_2005():
    """É a premissa do invariante da DN-08: 0,4 < 0,6 e as faixas juntas
    cobrem 1 a 8 — o município está certamente numa das duas."""
    from core.regras.gis_bim.edi_024_1_telhado_zb_1_3 import EDI0241
    assert EDI0242.limite < EDI0241.limite
    assert EDI0241.zonas_texto == "1, 2 e 3" and EDI0242.zonas_texto == "4, 5, 6, 7 e 8"
