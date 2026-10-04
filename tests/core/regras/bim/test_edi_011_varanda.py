"""Testes de EDI-011 (dimensões mínimas da varanda).

Isola ``EDI011.checar`` de ``core.regras.bim.edi_011_varanda``: sem executor e
sem agregação — substitui (monkeypatch) ``core.infra.ifc.extrator_ambientes.
listar`` (nomes/áreas nominais) e ``.medir`` (largura/comprimento/área de
footprint) por dados fixos, sem IfcOpenShell nem Shapely. A classificação
nominal (mesmo catálogo de EDI-004/007/008/009) não é mockada.

Além dos três estados, cobre a dupla fonte de área que a regra declara na
docstring: nominal (quantidade do IfcSpace, via ``Ambiente.area_m2``) quando
disponível, footprint geométrico como fallback quando não.
"""

from __future__ import annotations

from core.dominio.contratos.regra import Estado
from core.dominio.edificacao import Ambiente
from core.regras.bim.edi_011_varanda import EDI011
from tests.apoio.contexto_bim import contexto_bim


def _checar(ambientes, medidas, monkeypatch, modelo=object()):
    monkeypatch.setattr("core.infra.ifc.extrator_ambientes.listar",
                        lambda modelo: ambientes)
    monkeypatch.setattr("core.infra.ifc.extrator_ambientes.medir",
                        lambda modelo, global_ids: medidas)
    ctx = contexto_bim(modelo_ifc=modelo)
    return EDI011().checar(ctx)


def test_edi011_conforme_area_nominal_suficiente(monkeypatch):
    ambientes = [Ambiente(global_id="V1", nome="Varanda", area_m2=2.00,
                          fonte_area="quantidade")]
    medidas = {"V1": {"largura_m": 1.00, "comprimento_m": 2.00,
                       "area_footprint_m2": 2.0, "metodo": "x"}}
    r = _checar(ambientes, medidas, monkeypatch)
    assert r.estado is Estado.CONFORME
    assert r.detalhe["categoria"] == "varanda"
    assert r.detalhe["ambientes"][0]["fonte_area_avaliada"] == "quantidade"


def test_edi011_conforme_area_via_footprint_sem_quantidade(monkeypatch):
    # Sem area_m2 nominal (Ambiente sem quantidade lida) -> cai no fallback
    # de footprint, como a docstring da regra declara.
    ambientes = [Ambiente(global_id="V1", nome="Varanda")]
    medidas = {"V1": {"largura_m": 0.90, "comprimento_m": 1.80,
                       "area_footprint_m2": 1.62, "metodo": "x"}}
    r = _checar(ambientes, medidas, monkeypatch)
    assert r.estado is Estado.CONFORME
    assert r.detalhe["ambientes"][0]["fonte_area_avaliada"] == "footprint (geométrica)"


def test_edi011_nao_conforme_largura_insuficiente(monkeypatch):
    ambientes = [Ambiente(global_id="V1", nome="Varanda", area_m2=2.00)]
    medidas = {"V1": {"largura_m": 0.60, "comprimento_m": 3.00,
                       "area_footprint_m2": 1.8, "metodo": "x"}}
    r = _checar(ambientes, medidas, monkeypatch)
    assert r.estado is Estado.NAO_CONFORME
    assert "largura" in r.mensagem


def test_edi011_nao_conforme_area_insuficiente(monkeypatch):
    ambientes = [Ambiente(global_id="V1", nome="Varanda")]
    medidas = {"V1": {"largura_m": 1.00, "comprimento_m": 1.20,
                       "area_footprint_m2": 1.20, "metodo": "x"}}
    r = _checar(ambientes, medidas, monkeypatch)
    assert r.estado is Estado.NAO_CONFORME
    assert "área" in r.mensagem


def test_edi011_nao_avaliavel_sem_varanda_no_modelo(monkeypatch):
    ambientes = [Ambiente(global_id="S1", nome="Sala")]  # sem varanda
    r = _checar(ambientes, {}, monkeypatch)
    assert r.estado is Estado.NAO_AVALIAVEL
    assert "Nenhum ambiente identificado" in r.mensagem


def test_edi011_nao_avaliavel_sem_medida_completa(monkeypatch):
    ambientes = [Ambiente(global_id="V1", nome="Varanda", area_m2=2.00)]
    medidas = {"V1": {"erro": "footprint degenerado (sem triângulos válidos em planta)"}}
    r = _checar(ambientes, medidas, monkeypatch)
    assert r.estado is Estado.NAO_AVALIAVEL
    assert "sem medida completa" in r.mensagem


def test_edi011_nao_avaliavel_sem_modelo():
    r = EDI011().checar(contexto_bim(modelo_ifc=None))
    assert r.estado is Estado.NAO_AVALIAVEL


# --- Os não avaliáveis da própria regra levam motivo (ADR-006/022) ---

def test_edi011_sem_varanda_sai_com_motivo_informacao_ausente(monkeypatch):
    from core.dominio.vocabulario import motivos

    r = _checar([Ambiente(global_id="S1", nome="Sala")], {}, monkeypatch)
    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.INFORMACAO_AUSENTE


def test_edi011_sem_medida_completa_sai_com_motivo_informacao_ausente(monkeypatch):
    from core.dominio.vocabulario import motivos

    ambientes = [Ambiente(global_id="V1", nome="Varanda", area_m2=2.00)]
    medidas = {"V1": {"erro": "footprint degenerado (sem triângulos válidos em planta)"}}
    r = _checar(ambientes, medidas, monkeypatch)
    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.INFORMACAO_AUSENTE
    assert r.detalhe["categoria"] == "varanda"
