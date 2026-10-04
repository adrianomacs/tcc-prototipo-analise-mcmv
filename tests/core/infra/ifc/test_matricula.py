"""Matrícula do lote: property set com precedência sobre o atributo.

    pytest tests/core/infra/ifc/test_matricula.py

O IFC4.3 marca ``IfcSite.LandTitleNumber`` como depreciado — *"shall not be used
for export"* — e indica ``Pset_LandRegistration`` no lugar. Um modelo IFC4.3
conforme não preenche o atributo, então ler só ele faria a matrícula sumir
justamente nos modelos mais novos; com a premissa do IFC4 cravada, isso deixou de
ser hipótese distante.

Os nomes das propriedades **não foram supostos**: ``Pset_LandRegistration`` traz
``LandID``, ``IsPermanentID`` e ``LandTitleID``, conferidos nos templates de schema
do próprio IfcOpenShell 0.8.5 (idênticos em IFC4, IFC4X3 e IFC4X3_ADD2). Nenhum
teste aqui precisa da biblioteca: o ``ifcopenshell.util.element`` é injetado falso,
o que também prende o CONTRATO que o código espera dela.
"""

from __future__ import annotations

import sys
import types

import pytest

from core.dominio import terreno as trn
from core.infra.ifc import extrator_terreno as de_ifc
from core.infra.ifc import leitor_modelo as leitor_ifc

CG_LAT, CG_LON = -20.4712, -54.6215


@pytest.fixture
def psets(monkeypatch):
    """Injeta ``ifcopenshell.util.element.get_psets`` devolvendo o que se pedir."""
    tabela: dict = {}

    modulo = types.ModuleType("ifcopenshell")
    util = types.ModuleType("ifcopenshell.util")
    elemento = types.ModuleType("ifcopenshell.util.element")
    elemento.get_psets = lambda _: tabela
    util.element = elemento
    modulo.util = util
    monkeypatch.setitem(sys.modules, "ifcopenshell", modulo)
    monkeypatch.setitem(sys.modules, "ifcopenshell.util", util)
    monkeypatch.setitem(sys.modules, "ifcopenshell.util.element", elemento)

    def definir(**por_pset):
        tabela.clear()
        tabela.update(por_pset)
    return definir


def _site(**atributos):
    """IfcSite falso: só precisa responder a ``getattr``."""
    atributos.setdefault("GlobalId", "0SITE")
    atributos.setdefault("Name", "Lote 1")
    atributos.setdefault("LandTitleNumber", None)
    atributos.setdefault("Representation", None)
    return types.SimpleNamespace(**atributos)


# ---------------------------------------------------------------------------
# O acessor por pset nomeado
# ---------------------------------------------------------------------------

def test_propriedade_de_pset_devolve_valor_e_fonte(psets):
    psets(Pset_LandRegistration={"LandTitleID": "M-12345"})
    assert leitor_ifc.propriedade_de_pset(
        _site(), "Pset_LandRegistration", "LandTitleID") == (
            "M-12345", "Pset_LandRegistration.LandTitleID")


def test_propriedade_de_pset_nao_pega_homonimo_de_outro_pset(psets):
    """O motivo de existir, frente ao dicionário achatado.

    ``propriedades_do_elemento`` funde todos os Psets: um ``LandTitleID`` de
    outro pset seria indistinguível do certo, e a procedência mentiria sem que
    nada quebrasse.
    """
    psets(Pset_Outro={"LandTitleID": "NÃO É ESTE"})
    assert leitor_ifc.propriedade_de_pset(
        _site(), "Pset_LandRegistration", "LandTitleID") == (None, "")


def test_propriedade_de_pset_sem_biblioteca_nao_levanta(monkeypatch):
    monkeypatch.setitem(sys.modules, "ifcopenshell.util.element", None)
    assert leitor_ifc.propriedade_de_pset(_site(), "Qualquer", "Coisa") == (None, "")


# ---------------------------------------------------------------------------
# A precedência
# ---------------------------------------------------------------------------

def test_o_pset_tem_precedencia_sobre_o_atributo_depreciado(psets):
    psets(Pset_LandRegistration={"LandTitleID": "M-DO-PSET"})
    valor, fonte = de_ifc._matricula(_site(LandTitleNumber="M-DO-ATRIBUTO"))
    assert valor == "M-DO-PSET"
    assert fonte == "Pset_LandRegistration.LandTitleID"


def test_sem_pset_o_atributo_vale_e_a_fonte_diz_que_ele_e_depreciado(psets):
    psets()
    valor, fonte = de_ifc._matricula(_site(LandTitleNumber="M-LEGADO"))
    assert valor == "M-LEGADO"
    assert "LandTitleNumber" in fonte and "depreciado" in fonte


def test_sem_nenhum_dos_dois_nao_se_inventa_matricula(psets):
    psets()
    assert de_ifc._matricula(_site()) == ("", "")


def test_land_id_nao_e_matricula(psets):
    """São dois fatos no mesmo pset, e fundi-los seria erro de domínio.

    ``LandTitleID`` é o título (a matrícula do registro de imóveis);
    ``LandID`` identifica a parcela de terra. E o ``LandID`` não tem equivalente
    entre os atributos do IfcSite: ou vem do pset, ou não existe.
    """
    psets(Pset_LandRegistration={"LandID": "LOTE-07"})
    assert de_ifc._matricula(_site()) == ("", "")
    assert de_ifc._identificacao_do_lote(_site()) == (
        "LOTE-07", "Pset_LandRegistration.LandID")


# ---------------------------------------------------------------------------
# Os dois consumidores não podem divergir
# ---------------------------------------------------------------------------

def test_resumo_do_site_e_cross_check_resolvem_a_matricula_igual(psets):
    """Regressão contra o defeito difícil de ver: a mesma matrícula lida de dois
    jeitos, aparecendo diferente no resumo por site e no diagnóstico."""
    psets(Pset_LandRegistration={"LandTitleID": "M-999", "LandID": "LOTE-07"})
    site = _site(LandTitleNumber="M-LEGADO")

    resumo = de_ifc._resumo_site(site)
    terreno = trn.de_ponto_wgs84(CG_LAT, CG_LON)
    detalhe: dict = {}
    de_ifc._cross_checks(None, site, terreno, detalhe)

    assert resumo["matricula"] == detalhe["matricula"] == "M-999"
    assert resumo["matricula_fonte"] == detalhe["matricula_fonte"]
    assert terreno.procedencia["matricula_ifc"] == "M-999"
    assert terreno.procedencia["matricula_fonte"] == \
        "Pset_LandRegistration.LandTitleID"
    assert detalhe["land_id"] == "LOTE-07"


def test_cross_check_sem_matricula_nao_polui_a_procedencia(psets):
    psets()
    terreno = trn.de_ponto_wgs84(CG_LAT, CG_LON)
    detalhe: dict = {}
    de_ifc._cross_checks(None, _site(), terreno, detalhe)

    assert "matricula" not in detalhe and "land_id" not in detalhe
    assert "matricula_ifc" not in terreno.procedencia
