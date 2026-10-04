"""Testes de EDI-024 — o requisito-PAI da absortância do telhado (ADR-026).

Substituem os testes da versão anterior da regra, que iterava ``IfcCovering``
cru com limite único; a decisão que os supera é o ADR-026 (pai + ramos) com o
ADR-027 (população classificada). O que se prende aqui:

1. **Os três caminhos do pai, isolados** — herda, unânime, discordante —,
   ``EDI024().checar(ctx)`` direto sobre resultados de ramo montados à mão.
2. **Ponta a ponta pelo executor**, com EDI-024.1/024.2 reais sobre modelo
   falso: o invariante à leitura da DN-08 (≤ 0,4 conforme, > 0,6 não
   conforme, no meio indecisão declarada) e os ramos sempre NÃO AVALIÁVEIS.
3. **Quem conta é o pai** (ADR-015/026): os ramos ficam fora do denominador.
4. Metadado: filiação, modo, `ids_spec = None` (ADR-007).
"""

from __future__ import annotations

import pytest

from core.aplicacao.executor import executar
from core.dominio.contratos.regra import Contexto, Estado, Resultado, Verbo
from core.dominio.vocabulario import motivos
from core.infra.exportadores import relatorio_json
from core.regras.base import agregacao as ag
from core.regras.gis_bim.edi_024_absortancia import EDI024
from tests.apoio import ifc_falso as f
from tests.apoio.contexto_bim import contexto_bim

IDS = ["EDI-024", "EDI-024.1", "EDI-024.2"]


def _ramo(rid, veredito, aplicabilidade=ag.RAMO_INDETERMINADA, motivo="",
          elementos=()) -> Resultado:
    det = {ag.CHAVE_APLICABILIDADE: aplicabilidade,
           ag.CHAVE_VEREDITO_RAMO: veredito.value if veredito else ""}
    if aplicabilidade == ag.RAMO_APLICAVEL and veredito:
        return Resultado(regra_id=rid, estado=veredito, detalhe=det,
                         elementos=list(elementos))
    det[motivos.CHAVE] = motivo or motivos.ANALISE_HUMANA_DOCUMENTAL
    return Resultado(regra_id=rid, estado=Estado.NAO_AVALIAVEL, detalhe=det,
                     elementos=list(elementos))


# ---------------------------------------------------------------------------
# 1. Os três caminhos do pai, isolados
# ---------------------------------------------------------------------------

def test_pai_herda_quando_um_so_ramo_aplica():
    ctx = Contexto(resultados={
        "EDI-024.1": _ramo("EDI-024.1", Estado.CONFORME, ag.RAMO_APLICAVEL, elementos=["C1"]),
        "EDI-024.2": _ramo("EDI-024.2", Estado.NAO_CONFORME, ag.RAMO_INAPLICAVEL,
                           motivos.NAO_APLICAVEL),
    })
    r = EDI024().checar(ctx)
    assert r.estado is Estado.CONFORME
    assert r.detalhe["selecao"] == ag.SELECAO_HERDADO
    assert r.detalhe["candidatos"] == ["EDI-024.1"]
    assert r.elementos == ["C1"]


def test_pai_conclui_pela_unanimidade_sem_saber_o_ramo():
    ctx = Contexto(resultados={
        "EDI-024.1": _ramo("EDI-024.1", Estado.NAO_CONFORME),
        "EDI-024.2": _ramo("EDI-024.2", Estado.NAO_CONFORME),
    })
    r = EDI024().checar(ctx)
    assert r.estado is Estado.NAO_CONFORME
    assert r.detalhe["selecao"] == ag.SELECAO_UNANIME


def test_pai_discordante_e_indecisao_declarada_nunca_reprovacao():
    ctx = Contexto(resultados={
        "EDI-024.1": _ramo("EDI-024.1", Estado.CONFORME),
        "EDI-024.2": _ramo("EDI-024.2", Estado.NAO_CONFORME),
    })
    r = EDI024().checar(ctx)
    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.ANALISE_HUMANA_DOCUMENTAL
    assert r.detalhe["selecao"] == ag.SELECAO_DISCORDANTE


# ---------------------------------------------------------------------------
# 2. Ponta a ponta pelo executor — o invariante da DN-08
# ---------------------------------------------------------------------------

def _modelo_telhado(gid="COV1"):
    cov = f.covering(predefinido="ROOFING", gid=gid)
    telhado = f.telhado()
    return f.modelo_coverings(telhado, cov, f.rel_cobre(telhado, cov)), cov


def _executar(monkeypatch, absortancia, material="Telha de concreto"):
    modelo, _cov = _modelo_telhado()
    monkeypatch.setattr("core.infra.ifc.leitor_modelo.propriedades_do_elemento",
                        lambda e: {"AbsortanciaSolar": absortancia})
    monkeypatch.setattr("core.infra.ifc.leitor_modelo.materiais_do_elemento",
                        lambda e: [material])
    ctx = contexto_bim(modelo_ifc=modelo)
    return executar(ctx, ids_selecionados=IDS)


@pytest.mark.parametrize("absortancia, estado, selecao", [
    (0.30, Estado.CONFORME, ag.SELECAO_UNANIME),        # <= 0,4: conforme sob qualquer zona
    (0.50, Estado.NAO_AVALIAVEL, ag.SELECAO_DISCORDANTE),  # (0,4; 0,6]: indecidível
    (0.70, Estado.NAO_CONFORME, ag.SELECAO_UNANIME),    # > 0,6: não conforme sob qualquer zona
])
def test_invariante_a_leitura_do_telhado(monkeypatch, absortancia, estado, selecao):
    res = _executar(monkeypatch, absortancia)

    assert res["EDI-024"].estado is estado
    assert res["EDI-024"].detalhe["selecao"] == selecao
    assert res["EDI-024"].detalhe["candidatos"] == ["EDI-024.1", "EDI-024.2"]
    # Os ramos nunca emitem veredito próprio: aplicabilidade em aberto (DN-08).
    for rid in ("EDI-024.1", "EDI-024.2"):
        assert res[rid].estado is Estado.NAO_AVALIAVEL
        assert res[rid].detalhe[motivos.CHAVE] == motivos.ANALISE_HUMANA_DOCUMENTAL
        assert res[rid].detalhe[ag.CHAVE_APLICABILIDADE] == ag.RAMO_INDETERMINADA
    assert res["EDI-024"].elementos == ["COV1", "COV1"]


def test_faixa_indecidivel_tem_a_causa_declarada(monkeypatch):
    res = _executar(monkeypatch, 0.5)
    r = res["EDI-024"]
    assert r.detalhe[motivos.CHAVE] == motivos.ANALISE_HUMANA_DOCUMENTAL
    assert "não é reprovação" in r.mensagem
    por_id = {m["id"]: m for m in r.detalhe["membros"]}
    assert por_id["EDI-024.1"]["veredito_ramo"] == Estado.CONFORME.value
    assert por_id["EDI-024.2"]["veredito_ramo"] == Estado.NAO_CONFORME.value


def test_excecao_no_ramo_sobe_como_nao_aplicavel_no_pai(monkeypatch):
    res = _executar(monkeypatch, 0.9, material="Telha de barro")
    assert res["EDI-024"].estado is Estado.NAO_AVALIAVEL
    assert res["EDI-024"].detalhe[motivos.CHAVE] == motivos.NAO_APLICAVEL
    assert res["EDI-024"].detalhe["selecao"] == ag.SELECAO_PENDENTE


def test_sem_covering_classificado_o_pai_reporta_informacao_ausente(monkeypatch):
    """Covering órfão SEM lado declarado (forro `CEILING`): nenhum ramo tem
    população, e o pai reporta informação ausente. (Até a C4 o caso de teste
    era um `ROOFING` órfão — que, pela emenda ao ADR-027, hoje É população.)"""
    cov = f.covering(predefinido="CEILING", gid="ORFAO")
    modelo = f.modelo_coverings(cov)
    monkeypatch.setattr("core.infra.ifc.leitor_modelo.propriedades_do_elemento",
                        lambda e: {"AbsortanciaSolar": 0.2})
    monkeypatch.setattr("core.infra.ifc.leitor_modelo.materiais_do_elemento",
                        lambda e: ["Concreto"])
    res = executar(contexto_bim(modelo_ifc=modelo), ids_selecionados=IDS)
    assert res["EDI-024"].estado is Estado.NAO_AVALIAVEL
    assert res["EDI-024"].detalhe[motivos.CHAVE] == motivos.INFORMACAO_AUSENTE


def test_modelo_so_de_terreno_torna_o_conjunto_nao_aplicavel(monkeypatch):
    from core.dominio.empreendimento import Empreendimento
    from core.dominio.vocabulario import declaracoes as dec

    emp = Empreendimento()
    emp.declaracoes[dec.TIPO_MODELO] = dec.TERRENO
    res = executar(contexto_bim(modelo_ifc=f.modelo_vazio(), empreendimento=emp),
                   ids_selecionados=IDS)
    for rid in IDS:
        assert res[rid].estado is Estado.NAO_AVALIAVEL
        assert res[rid].detalhe[motivos.CHAVE] == motivos.NAO_APLICAVEL


# ---------------------------------------------------------------------------
# 3. Quem conta é o pai
# ---------------------------------------------------------------------------

def test_ramos_ficam_fora_do_denominador(monkeypatch):
    res = _executar(monkeypatch, 0.3)
    normativo = relatorio_json._normativo(res)
    assert normativo["ids"] == ["EDI-024"]
    assert normativo["membros"] == ["EDI-024.1", "EDI-024.2"]
    assert normativo["total"] == 1 and normativo["conformidade"] == 1.0
    assert normativo["cobertura"] == 1.0


# ---------------------------------------------------------------------------
# 4. Metadado
# ---------------------------------------------------------------------------

def test_metadado_do_pai():
    assert EDI024.agrega == ["EDI-024.1", "EDI-024.2"]
    assert EDI024.modo == ag.MODO_SELECAO_EXCLUSIVA
    assert EDI024.verbo is Verbo.AGREGACAO
    assert EDI024.ids_spec is None
    assert EDI024.depende_de == []
