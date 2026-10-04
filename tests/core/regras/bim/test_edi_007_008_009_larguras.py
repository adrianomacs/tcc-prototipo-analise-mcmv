"""Testes de EDI-007/008/009 (larguras mínimas de ambientes).

Isola ``_checar_largura`` de ``core.regras.bim.edi_007_008_009_larguras``: sem
executor e sem agregação — substitui (monkeypatch) ``core.infra.ifc.
extrator_ambientes.listar`` (nomes/áreas) e ``.medir`` (largura geométrica) por
dados fixos, sem IfcOpenShell nem Shapely. A classificação nominal (mesmo
catálogo de EDI-004) não é mockada.

EDI-007 (cozinha, ≥ 1,80 m) recebe os três estados; EDI-008 (sala, ≥ 2,40 m) e
EDI-009 (banheiro, ≥ 1,50 m) recebem casos que confirmam o parâmetro de cada
uma foi ligado corretamente à mesma mecânica comum.
"""

from __future__ import annotations

from core.dominio.contratos.regra import Estado
from core.dominio.edificacao import Ambiente
from core.regras.bim.edi_007_008_009_larguras import EDI007, EDI008, EDI009
from tests.apoio.contexto_bim import contexto_bim


def _checar(regra_cls, ambientes, medidas, monkeypatch, modelo=object()):
    monkeypatch.setattr("core.infra.ifc.extrator_ambientes.listar",
                        lambda modelo: ambientes)
    monkeypatch.setattr("core.infra.ifc.extrator_ambientes.medir",
                        lambda modelo, global_ids: medidas)
    ctx = contexto_bim(modelo_ifc=modelo)
    return regra_cls().checar(ctx)


# --- EDI-007 (cozinha, ≥ 1,80 m) -- os três estados -------------------------

def test_edi007_conforme_largura_suficiente(monkeypatch):
    ambientes = [Ambiente(global_id="C1", nome="Cozinha")]
    medidas = {"C1": {"largura_m": 2.00, "comprimento_m": 3.00,
                       "area_footprint_m2": 6.0, "metodo": "x"}}
    r = _checar(EDI007, ambientes, medidas, monkeypatch)
    assert r.estado is Estado.CONFORME
    assert r.detalhe["categoria"] == "cozinha"


def test_edi007_nao_conforme_largura_insuficiente(monkeypatch):
    ambientes = [Ambiente(global_id="C1", nome="Cozinha")]
    medidas = {"C1": {"largura_m": 1.50, "comprimento_m": 3.00,
                       "area_footprint_m2": 4.5, "metodo": "x"}}
    r = _checar(EDI007, ambientes, medidas, monkeypatch)
    assert r.estado is Estado.NAO_CONFORME
    assert "Cozinha" in r.mensagem


def test_edi007_nao_avaliavel_categoria_ausente_no_modelo(monkeypatch):
    ambientes = [Ambiente(global_id="S1", nome="Sala")]  # sem cozinha
    r = _checar(EDI007, ambientes, {}, monkeypatch)
    assert r.estado is Estado.NAO_AVALIAVEL
    assert "Nenhum ambiente identificado" in r.mensagem


def test_edi007_nao_avaliavel_conjunto_incompleto_sem_medida(monkeypatch):
    # Categoria presente, mas a geometria não pôde ser medida: os medidos
    # atendem, mas o conjunto está incompleto -> não avaliável (não conforme).
    ambientes = [Ambiente(global_id="C1", nome="Cozinha")]
    medidas = {"C1": {"erro": "footprint degenerado (sem triângulos válidos em planta)"}}
    r = _checar(EDI007, ambientes, medidas, monkeypatch)
    assert r.estado is Estado.NAO_AVALIAVEL
    assert "incompleto" in r.mensagem


# --- EDI-008 (sala, ≥ 2,40 m) ----------------------------------------------

def test_edi008_conforme_largura_suficiente(monkeypatch):
    ambientes = [Ambiente(global_id="S1", nome="Sala de estar")]
    medidas = {"S1": {"largura_m": 2.50, "comprimento_m": 4.00,
                       "area_footprint_m2": 10.0, "metodo": "x"}}
    r = _checar(EDI008, ambientes, medidas, monkeypatch)
    assert r.estado is Estado.CONFORME


def test_edi008_nao_conforme_largura_insuficiente(monkeypatch):
    # 2,10 m atenderia o mínimo do banheiro/cozinha, mas não o da sala (2,40 m).
    ambientes = [Ambiente(global_id="S1", nome="Sala de estar")]
    medidas = {"S1": {"largura_m": 2.10, "comprimento_m": 4.00,
                       "area_footprint_m2": 8.4, "metodo": "x"}}
    r = _checar(EDI008, ambientes, medidas, monkeypatch)
    assert r.estado is Estado.NAO_CONFORME


# --- EDI-009 (banheiro, ≥ 1,50 m) ------------------------------------------

def test_edi009_conforme_largura_suficiente(monkeypatch):
    ambientes = [Ambiente(global_id="B1", nome="Banheiro")]
    medidas = {"B1": {"largura_m": 1.60, "comprimento_m": 2.00,
                       "area_footprint_m2": 3.2, "metodo": "x"}}
    r = _checar(EDI009, ambientes, medidas, monkeypatch)
    assert r.estado is Estado.CONFORME


def test_edi009_nao_conforme_largura_insuficiente(monkeypatch):
    ambientes = [Ambiente(global_id="B1", nome="Banheiro")]
    medidas = {"B1": {"largura_m": 1.20, "comprimento_m": 2.00,
                       "area_footprint_m2": 2.4, "metodo": "x"}}
    r = _checar(EDI009, ambientes, medidas, monkeypatch)
    assert r.estado is Estado.NAO_CONFORME


# --- Os não avaliáveis da própria regra levam motivo (ADR-006/022) ---
#
# Categoria sem correspondência nominal e ambiente sem geometria medível
# saem com ``informacao_ausente``: conteúdo que o requisito de informação
# (ADR-007) exigiria e o modelo não traz. Sem motivo, a decomposição por causa
# do relatório não conseguiria classificar esses não avaliáveis. Uma regra de
# cada parâmetro, para prender que as três compartilham o caminho.

def test_edi007_categoria_ausente_sai_com_motivo_informacao_ausente(monkeypatch):
    from core.dominio.vocabulario import motivos

    r = _checar(EDI007, [Ambiente(global_id="S1", nome="Sala")], {}, monkeypatch)
    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.INFORMACAO_AUSENTE


def test_edi008_categoria_ausente_sai_com_motivo_informacao_ausente(monkeypatch):
    from core.dominio.vocabulario import motivos

    r = _checar(EDI008, [Ambiente(global_id="C1", nome="Cozinha")], {}, monkeypatch)
    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.INFORMACAO_AUSENTE


def test_edi009_categoria_ausente_sai_com_motivo_informacao_ausente(monkeypatch):
    from core.dominio.vocabulario import motivos

    r = _checar(EDI009, [Ambiente(global_id="C1", nome="Cozinha")], {}, monkeypatch)
    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.INFORMACAO_AUSENTE


def test_edi007_sem_medida_sai_com_motivo_informacao_ausente(monkeypatch):
    from core.dominio.vocabulario import motivos

    ambientes = [Ambiente(global_id="C1", nome="Cozinha")]
    medidas = {"C1": {"erro": "footprint degenerado (sem triângulos válidos em planta)"}}
    r = _checar(EDI007, ambientes, medidas, monkeypatch)
    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.INFORMACAO_AUSENTE
    # O diagnóstico das larguras continua ao lado do motivo.
    assert r.detalhe["categoria"] == "cozinha"
