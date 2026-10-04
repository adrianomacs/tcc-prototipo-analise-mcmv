"""Testes de EDI-004 / EDI-004.1 (programa mínimo de necessidades).

Isola ``EDI004.checar`` / ``EDI0041.checar`` de ``core.regras.bim.
edi_004_programa_necessidades``: sem executor e sem agregação — substitui
(monkeypatch) ``core.infra.ifc.extrator_ambientes.listar`` por uma lista fixa
de :class:`Ambiente`, sem IfcOpenShell. A classificação nominal em si
(``core.dominio.conhecimento.catalogo_ambientes``) não é mockada — é lógica
pura, e os nomes abaixo foram escolhidos para casar com as categorias.

Mesma observação de ``test_edi_001_002_area_util_uh.py`` sobre o "não
avaliável": o caso testado aqui é o caminho interno de ``checar`` (nenhum
IfcSpace no modelo), não o motivo da taxonomia do ADR-006 (atribuído pelo
executor, fora do escopo desta regra isolada).
"""

from __future__ import annotations

import pytest

from core.dominio.contratos.regra import Estado
from core.dominio.edificacao import Ambiente
from core.regras.bim.edi_004_programa_necessidades import EDI004, EDI0041
from tests.apoio.contexto_bim import contexto_bim


def _checar(regra_cls, ambientes, monkeypatch, modelo=object()):
    monkeypatch.setattr("core.infra.ifc.extrator_ambientes.listar",
                        lambda modelo: ambientes)
    ctx = contexto_bim(modelo_ifc=modelo)
    return regra_cls().checar(ctx)


_PROGRAMA_COMPLETO = [
    Ambiente(global_id="A1", nome="Sala de estar"),
    Ambiente(global_id="A2", nome="Dormitório de casal"),
    Ambiente(global_id="A3", nome="Dormitório 2"),  # 2º dormitório (dormitorio_2p)
    Ambiente(global_id="A4", nome="Cozinha"),
    Ambiente(global_id="A5", nome="Área de serviço"),
    Ambiente(global_id="A6", nome="Banheiro"),
]


# --- EDI-004 (programa mínimo: sala, 2 dormitórios, cozinha, área de --------
# --- serviço, banheiro) -----------------------------------------------------

def test_edi004_conforme_programa_completo(monkeypatch):
    r = _checar(EDI004, _PROGRAMA_COMPLETO, monkeypatch)
    assert r.estado is Estado.CONFORME
    assert r.detalhe["faltantes"] == []


def test_edi004_nao_conforme_falta_categoria(monkeypatch):
    sem_cozinha = [a for a in _PROGRAMA_COMPLETO if a.global_id != "A4"]
    r = _checar(EDI004, sem_cozinha, monkeypatch)
    assert r.estado is Estado.NAO_CONFORME
    assert any("Cozinha" in f for f in r.detalhe["faltantes"])


def test_edi004_nao_avaliavel_sem_ambientes_no_modelo(monkeypatch):
    r = _checar(EDI004, [], monkeypatch)
    assert r.estado is Estado.NAO_AVALIAVEL
    assert "Nenhum ambiente" in r.mensagem


# --- EDI-004.1 (varanda, UH multifamiliar) ---------------------------------

def test_edi0041_conforme_varanda_presente(monkeypatch):
    com_varanda = _PROGRAMA_COMPLETO + [Ambiente(global_id="A7", nome="Varanda")]
    r = _checar(EDI0041, com_varanda, monkeypatch)
    assert r.estado is Estado.CONFORME


def test_edi0041_nao_conforme_sem_varanda(monkeypatch):
    r = _checar(EDI0041, _PROGRAMA_COMPLETO, monkeypatch)
    assert r.estado is Estado.NAO_CONFORME
    assert "não identificada" in r.mensagem


# --- Normalização pelo contêiner (ADR-021) ---------------------------------

def test_edi004_normaliza_a_exigencia_pelas_unidades_representadas(monkeypatch):
    """Contêiner que representa 2 UHs exige o programa duas vezes — e o programa
    de uma só UH deixa de atender."""
    from core.dominio.empreendimento import Empreendimento
    from core.dominio.modelo_bim import ModeloBIM
    from core.dominio.unidade_tipo import UnidadeTipo

    monkeypatch.setattr("core.infra.ifc.extrator_ambientes.listar",
                        lambda modelo: _PROGRAMA_COMPLETO)
    emp = Empreendimento(unidades_tipo=[
        UnidadeTipo(nome="Geminada", modelo=ModeloBIM(unidades_representadas=2))])
    r = EDI004().checar(contexto_bim(modelo_ifc=object(), empreendimento=emp))
    assert r.estado is Estado.NAO_CONFORME
    assert r.detalhe["num_uhs"] == 2
    assert "2 UHs" in r.mensagem


def test_edi004_nao_le_mais_o_numero_das_declaracoes(monkeypatch):
    """Guarda do ADR-021: declaração não escala parâmetro normativo. Uma chave
    ``num_uhs`` sobrevivente num artefato antigo não pode voltar a multiplicar
    a exigência pelas costas do contêiner."""
    from core.dominio.empreendimento import Empreendimento

    monkeypatch.setattr("core.infra.ifc.extrator_ambientes.listar",
                        lambda modelo: _PROGRAMA_COMPLETO)
    emp = Empreendimento(declaracoes={"num_uhs": 2})
    r = EDI004().checar(contexto_bim(modelo_ifc=object(), empreendimento=emp))
    assert r.estado is Estado.CONFORME and r.detalhe["num_uhs"] == 1


# --- O não avaliável da própria regra leva motivo (ADR-006/022) ------
#
# Sem motivo, "nenhum IfcSpace" sairia com ``detalhe`` vazio e a decomposição
# por causa do relatório não conseguiria classificá-lo. O motivo é ``informacao_ausente``: o modelo existe,
# o que falta é o conteúdo que o requisito de informação (ADR-007) exigiria.

def test_edi004_sem_ifcspace_sai_com_motivo_informacao_ausente(monkeypatch):
    from core.dominio.vocabulario import motivos

    r = _checar(EDI004, [], monkeypatch)
    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.INFORMACAO_AUSENTE


def test_edi0041_sem_ifcspace_sai_com_motivo_informacao_ausente(monkeypatch):
    from core.dominio.vocabulario import motivos

    r = _checar(EDI0041, [], monkeypatch)
    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.INFORMACAO_AUSENTE


# ---------------------------------------------------------------------------
# Sem modelo — a família inteira do programa (ADR-033)
# ---------------------------------------------------------------------------

def _regras_do_programa():
    from core.regras.bim.edi_001_002_area_util_uh import EDI001, EDI002
    from core.regras.bim.edi_007_008_009_larguras import EDI007, EDI008, EDI009
    from core.regras.bim.edi_011_varanda import EDI011
    return [EDI004, EDI0041, EDI001, EDI002, EDI007, EDI008, EDI009, EDI011]


@pytest.mark.parametrize("classe", _regras_do_programa(), ids=lambda c: c.id)
def test_programa_sem_modelo_e_insumo_do_proponente_ausente(classe):
    from core.dominio.vocabulario import motivos

    r = classe().checar(contexto_bim(modelo_ifc=None))
    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.INSUMO_DO_PROPONENTE_AUSENTE
