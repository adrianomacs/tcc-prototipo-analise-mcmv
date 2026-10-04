"""EDI-019.2 — ramo ZB 3 a 6 da parede externa (≤ 0,4). Metadado, faixa e, o
que só se vê com os dois ramos juntos: a partição das doze classes é exata —
sem sobreposição e sem sobra (ADR-030)."""

from __future__ import annotations

import pytest

from core.dominio.conhecimento.zona_bioclimatica import CLASSES, ZonaBioclimatica
from core.dominio.contratos.regra import Dominio, Verbo
from core.regras.base import agregacao as ag
from core.regras.gis_bim.edi_019_1_parede_zb_1_2 import EDI0191
from core.regras.gis_bim.edi_019_2_parede_zb_3_6 import EDI0192


def test_metadado():
    r = EDI0192
    assert r.id == "EDI-019.2"
    assert r.limite == 0.4 and r.parametro["absortancia_max"] == 0.4
    assert r.dominio is Dominio.GIS_BIM and r.verbo is Verbo.ATRIBUTO
    assert r.ids_spec is None and r.depende_de == []
    assert r.familia == "parede externa"
    assert r.excecoes_por_material is False
    assert r.ref_portaria.endswith("4.II.a.x.2")
    assert EDI0192.zonas == ("3A", "3B", "4A", "4B", "5A", "5B", "6A", "6B")


def test_os_dois_ramos_particionam_as_doze_classes_sem_sobra():
    """A afirmação a prender: as faixas de 2025 ESGOTAM as doze
    classes da ABNT TR 15220-3-1:2024 — não existe parede sem limite, e
    portanto não existe ramo NÃO APLICÁVEL por zona fora de faixa."""
    um_dois, tres_seis = set(EDI0191.zonas), set(EDI0192.zonas)
    assert um_dois & tres_seis == set(), "as faixas não podem se sobrepor"
    assert um_dois | tres_seis == set(CLASSES), "as faixas têm de esgotar a norma"


@pytest.mark.parametrize("classe", CLASSES)
def test_toda_classe_e_aplicavel_a_exatamente_um_ramo(classe):
    zona = ZonaBioclimatica(classe=classe, codigo_ibge="0000000")
    aplicaveis = [r for r in (EDI0191(), EDI0192())
                  if r.aplicabilidade_na_zona(zona)[0] == ag.RAMO_APLICAVEL]
    assert len(aplicaveis) == 1
