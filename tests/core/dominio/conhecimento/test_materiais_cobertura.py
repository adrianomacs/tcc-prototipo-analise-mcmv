"""Vocabulário das exceções de absortância do telhado (DN-01) —
``core/dominio/conhecimento/materiais_cobertura.py``."""

from __future__ import annotations

import pytest

from core.dominio.conhecimento import materiais_cobertura as mc


@pytest.mark.parametrize("nome, excecao", [
    ("Telha cerâmica", mc.TELHA_BARRO_NAO_VITRIFICADA),
    ("Telha de barro - Portuguesa", mc.TELHA_BARRO_NAO_VITRIFICADA),
    ("Argila cozida", mc.TELHA_BARRO_NAO_VITRIFICADA),
    ("Terracota", mc.TELHA_BARRO_NAO_VITRIFICADA),
    ("Telhado verde extensivo", mc.COBERTURA_VERDE),
    ("Cobertura Verde", mc.COBERTURA_VERDE),
    ("Green Roof", mc.COBERTURA_VERDE),
    ("Substrato vegetal", mc.COBERTURA_VERDE),
])
def test_reconhece_as_duas_excecoes(nome, excecao):
    assert mc.classificar(nome)[0] == excecao


@pytest.mark.parametrize("nome", [
    "Telha cerâmica esmaltada",     # vitrificada: a Portaria NÃO excetua
    "Cerâmica vitrificada",
    "Telha de barro vidrada",
    "Tinta verde",                  # a COR, não o sistema vegetado
    "Telha de fibrocimento",
    "Telha de concreto",
    "Telha romana",                 # perfil de telha não identifica material
    "Telha colonial",
    "", None,
])
def test_nao_e_excecao(nome):
    assert mc.classificar(nome) == (None, None)


def test_termo_casado_e_devolvido_para_o_relatorio():
    excecao, termo = mc.classificar("TELHA CERÂMICA NATURAL")
    assert excecao == mc.TELHA_BARRO_NAO_VITRIFICADA and termo == "ceramic"


def test_lista_de_materiais_primeira_excecao_vence():
    assert mc.classificar_materiais(["Tinta branca", "Telha de barro"]) == (
        mc.TELHA_BARRO_NAO_VITRIFICADA, "Telha de barro", "barro")
    assert mc.classificar_materiais(["Concreto", "Tinta branca"]) == (None, None, None)


def test_identificavel_exige_material_com_nome():
    assert mc.identificavel(["Concreto"])
    assert not mc.identificavel([])
    assert not mc.identificavel(["", "  "])
