"""Testes de EDI-019 — o requisito-PAI da absortância das paredes externas.

O que se prende aqui, e por que cada coisa:

1. **As doze classes, nenhuma sem faixa.** Ponto corrigido na regra:
   a edição vigente da norma não tem zona 7 nem 8, e as faixas de 2025
   esgotam as doze classes (ADR-030). Logo **nenhuma** classe deixa o pai sem
   veredito por falta de faixa — e o teste é esse, não o de um
   ``NAO_APLICAVEL`` por zona fora de faixa, que aqui não existe.
2. **O pai é degenerado** (ADR-026): um ramo aplica, o outro sai NÃO
   AVALIÁVEL por não aplicável, e o pai herda — ``SELECAO_HERDADO`` sempre
   que a zona se resolve.
3. **Zona não resolvida** é o único caminho que faz os dois ramos virarem
   candidatos; aí vale o invariante à leitura, como no telhado.
4. **Quem conta é o pai** (ADR-015/026) e o metadado.
"""

from __future__ import annotations

import pytest

from core.aplicacao.executor import executar
from core.dominio.conhecimento.zona_bioclimatica import CLASSES, ZonaBioclimatica
from core.dominio.contratos.regra import Estado, Verbo
from core.dominio.vocabulario import motivos
from core.infra.exportadores import relatorio_json
from core.regras.base import agregacao as ag
from core.regras.gis_bim.edi_019_absortancia_parede import EDI019
from tests.apoio import ifc_falso as f
from tests.apoio.contexto_bim import contexto_bim

IDS = ["EDI-019", "EDI-019.1", "EDI-019.2"]

# Valor escolhido de propósito: atende ao limite do ramo de ZB 1–2 (<= 0,6) e
# não atende ao do ramo de ZB 3–6 (<= 0,4). É o que torna visível QUAL ramo a
# zona selecionou — com 0,3 os dois concordariam e o teste não diria nada.
ENTRE_OS_LIMITES = 0.5


def _modelo_parede_externa(gid="COV-PAREDE"):
    cov = f.covering(gid=gid)
    parede = f.parede()
    return f.modelo_coverings(parede, cov, f.rel_cobre(parede, cov))


def _executar(monkeypatch, zona=None, absortancia=ENTRE_OS_LIMITES, externo=True):
    modelo = _modelo_parede_externa()
    monkeypatch.setattr("core.infra.ifc.leitor_modelo.propriedades_do_elemento",
                        lambda e: {"AbsortanciaSolar": absortancia})
    monkeypatch.setattr(
        "core.infra.ifc.leitor_modelo.propriedade_de_pset",
        lambda e, pset, *chaves: ((externo, f"{pset}.IsExternal")
                                  if pset == "Pset_CoveringCommon" else (None, "")))
    ctx = contexto_bim(modelo_ifc=modelo,
                       zona_bioclimatica=(ZonaBioclimatica(classe=zona, codigo_ibge="0000000")
                                      if zona else None))
    return executar(ctx, ids_selecionados=IDS)


# ---------------------------------------------------------------------------
# 1. As doze classes — nenhuma deixa o pai sem veredito
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("classe", CLASSES)
def test_nenhuma_das_doze_classes_deixa_o_pai_sem_veredito(monkeypatch, classe):
    res = _executar(monkeypatch, zona=classe)
    pai = res["EDI-019"]

    assert pai.estado in (Estado.CONFORME, Estado.NAO_CONFORME), (
        f"ZB {classe} deixou EDI-019 sem veredito — as faixas de 4.II.a.x "
        "esgotam as doze classes da norma vigente (ADR-030)")
    assert pai.detalhe["selecao"] == ag.SELECAO_HERDADO
    assert len(pai.detalhe["candidatos"]) == 1


@pytest.mark.parametrize("classe, esperado, ramo", [
    ("1M", Estado.CONFORME, "EDI-019.1"), ("1R", Estado.CONFORME, "EDI-019.1"),
    ("2M", Estado.CONFORME, "EDI-019.1"), ("2R", Estado.CONFORME, "EDI-019.1"),
    ("3A", Estado.NAO_CONFORME, "EDI-019.2"), ("4B", Estado.NAO_CONFORME, "EDI-019.2"),
    ("5A", Estado.NAO_CONFORME, "EDI-019.2"), ("6B", Estado.NAO_CONFORME, "EDI-019.2"),
])
def test_a_zona_seleciona_o_ramo_e_o_pai_herda(monkeypatch, classe, esperado, ramo):
    """Pai degenerado (ADR-026): 0,5 é conforme sob <= 0,6 e não conforme sob
    <= 0,4 — o veredito do pai denuncia qual ramo a zona selecionou."""
    res = _executar(monkeypatch, zona=classe)

    assert res["EDI-019"].estado is esperado
    assert res["EDI-019"].detalhe["candidatos"] == [ramo]
    assert res[ramo].estado is esperado
    outro = "EDI-019.2" if ramo == "EDI-019.1" else "EDI-019.1"
    assert res[outro].estado is Estado.NAO_AVALIAVEL
    assert res[outro].detalhe[motivos.CHAVE] == motivos.NAO_APLICAVEL
    assert res[outro].detalhe[ag.CHAVE_APLICABILIDADE] == ag.RAMO_INAPLICAVEL


def test_poucas_paredes_acima_do_limite_da_zona_reprovam_o_pai(monkeypatch):
    """Caso misto: na ZB 2R, três revestimentos a
    0,35 e um a 0,72. Medido é medido — um acima de 0,6 basta para o ramo
    aplicável reprovar, e o pai herda; a mensagem nomeia o revestimento."""
    parede = f.parede()
    covs = [f.covering(gid=g) for g in ("OK1", "OK2", "OK3", "ACIMA")]
    modelo = f.modelo_coverings(parede, *covs, f.rel_cobre(parede, *covs))
    valores = {"OK1": 0.35, "OK2": 0.35, "OK3": 0.35, "ACIMA": 0.72}
    monkeypatch.setattr(
        "core.infra.ifc.leitor_modelo.propriedades_do_elemento",
        lambda e: {"AbsortanciaSolar": valores[e.GlobalId]})
    monkeypatch.setattr(
        "core.infra.ifc.leitor_modelo.propriedade_de_pset",
        lambda e, pset, *chaves: ((True, f"{pset}.IsExternal")
                                  if pset == "Pset_CoveringCommon" else (None, "")))
    ctx = contexto_bim(modelo_ifc=modelo,
                       zona_bioclimatica=ZonaBioclimatica(classe="2R",
                                                      codigo_ibge="0000000"))
    res = executar(ctx, ids_selecionados=IDS)

    assert res["EDI-019.1"].estado is Estado.NAO_CONFORME
    assert res["EDI-019"].estado is Estado.NAO_CONFORME
    assert res["EDI-019"].detalhe["selecao"] == ag.SELECAO_HERDADO
    assert "1 de 4" in res["EDI-019.1"].mensagem
    assert "ACIMA" in res["EDI-019.1"].mensagem
    situacoes = {c["global_id"]: c["situacao"]
                 for c in res["EDI-019.1"].detalhe["coverings"]}
    assert situacoes["ACIMA"] == "nao_atende"
    assert situacoes["OK1"] == "atende"


# ---------------------------------------------------------------------------
# 2. Zona não resolvida: o único caminho de dois candidatos
# ---------------------------------------------------------------------------

def test_sem_zona_resolvida_os_dois_ramos_sao_candidatos(monkeypatch):
    res = _executar(monkeypatch, zona=None)
    pai = res["EDI-019"]
    assert pai.estado is Estado.NAO_AVALIAVEL
    assert pai.detalhe["selecao"] == ag.SELECAO_DISCORDANTE
    assert pai.detalhe[motivos.CHAVE] == motivos.ANALISE_HUMANA_DOCUMENTAL
    assert pai.detalhe["candidatos"] == ["EDI-019.1", "EDI-019.2"]


@pytest.mark.parametrize("absortancia, estado", [
    (0.30, Estado.CONFORME),        # <= 0,4: conforme sob qualquer zona
    (0.70, Estado.NAO_CONFORME),    # > 0,6: não conforme sob qualquer zona
])
def test_sem_zona_o_invariante_a_leitura_ainda_conclui(monkeypatch, absortancia, estado):
    res = _executar(monkeypatch, zona=None, absortancia=absortancia)
    assert res["EDI-019"].estado is estado
    assert res["EDI-019"].detalhe["selecao"] == ag.SELECAO_UNANIME


# ---------------------------------------------------------------------------
# 3. Quem conta é o pai
# ---------------------------------------------------------------------------

def test_ramos_ficam_fora_do_denominador(monkeypatch):
    res = _executar(monkeypatch, zona="1M")
    normativo = relatorio_json._normativo(res)
    assert normativo["ids"] == ["EDI-019"]
    assert normativo["membros"] == ["EDI-019.1", "EDI-019.2"]
    assert normativo["total"] == 1 and normativo["cobertura"] == 1.0


def test_modelo_so_de_terreno_torna_o_conjunto_nao_aplicavel():
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
# 4. Metadado
# ---------------------------------------------------------------------------

def test_metadado_do_pai():
    assert EDI019.agrega == ["EDI-019.1", "EDI-019.2"]
    assert EDI019.modo == ag.MODO_SELECAO_EXCLUSIVA
    assert EDI019.verbo is Verbo.AGREGACAO
    assert EDI019.ids_spec is None
    assert EDI019.depende_de == []
