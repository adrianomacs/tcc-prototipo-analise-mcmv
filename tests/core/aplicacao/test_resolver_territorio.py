"""ADR-011 (D1) — o território é resolvido pela aplicação, antes do motor.

Três coisas se prendem aqui:

1. **Pela composição, a regra usa o recorte resolvido** e não relê o disco —
   prova feita fazendo o leitor explodir depois de o contexto estar montado.
2. **A regra só aceita o recorte do município que julga**, e sem recorte
   resolvido sai NÃO AVALIÁVEL por erro de execução, nunca relendo arquivo.
3. **Sem terreno não se resolve nada** — Georreferenciamento e Programa de
   necessidades declaram município e não podem passar a depender do CSV.

O resolvedor fala com a porta ``FontesTerritoriais``: os testes de gate e de
falha usam a implementação em memória (``tests/apoio/fontes_territoriais.py``);
os que conferem dado real usam ``FontesCSV`` sobre ``config/``.
"""

from __future__ import annotations

import json
import os

import pytest

from core import composicao
from core.aplicacao import resolver_territorio
from core.aplicacao.executor import executar
from core.dominio.contratos.regra import Contexto, Estado
from core.dominio.empreendimento import Empreendimento, Localizacao
from core.dominio.equipamentos import RecorteMunicipal
from core.dominio.terreno import Terreno
from core.dominio.vocabulario import motivos
from core.infra.gis import csv_equipamentos as leitor
from core.infra.gis.fontes_csv import FontesCSV
from core.regras.gis.enq_009_educacao_infantil import ENQ009
from tests.apoio.fontes_territoriais import FontesEmMemoria

CENTRO = (-29.50186, -51.96529)
FONTES = FontesCSV()
CABECALHO = ("codigo_inep;nome;lat;lon;ciclos;rede;situacao;atendimento;"
             "conveniada;endereco")


def _linha(codigo, nome, metros, ciclo="infantil"):
    lat = CENTRO[0] + metros / 111_320.0
    return (f"{codigo};{nome};{lat:.8f};{CENTRO[1]:.8f};{ciclo};"
            "municipal;ativa;geral;nao;RUA X, 1")


@pytest.fixture
def pasta(tmp_path, monkeypatch):
    leitor._CACHE.clear()
    with open(tmp_path / "equipamentos_4307807.csv", "w", encoding="utf-8") as f:
        f.write(CABECALHO + "\n" + _linha("1", "EMEI LONGE", 3000) + "\n")
    with open(tmp_path / "equipamentos_4307807.json", "w", encoding="utf-8") as f:
        json.dump({"ano_censo": "2025", "nome_municipio": "Estrela", "uf": "RS",
                   "fontes": [{"arquivo": "x.csv"}]}, f)
    monkeypatch.setattr(leitor, "PASTA_RECORTES", str(tmp_path))
    yield str(tmp_path)
    leitor._CACHE.clear()


def _terreno():
    return Terreno(origem="mapa", nivel="ponto", precisao="declarada",
                   crs_metrico="EPSG:31982", centro_wgs84=CENTRO)


def _emp(terreno=True, codigo="4307807"):
    return Empreendimento(localizacao=Localizacao(codigo) if codigo else None,
                          terreno=_terreno() if terreno else None)


def test_recorte_presente_ausente_e_sem_codigo(pasta):
    r = resolver_territorio.recorte("4307807", FONTES)
    assert isinstance(r, RecorteMunicipal) and r.disponivel
    assert len(r.equipamentos) == 1 and r.procedencia["uf"] == "RS"
    assert r.origem == os.path.join(pasta, "equipamentos_4307807.csv")

    ausente = resolver_territorio.recorte("3549904", FONTES)
    assert ausente is not None and not ausente.disponivel
    assert ausente.equipamentos == [] and ausente.procedencia == {}

    assert resolver_territorio.recorte("", FONTES) is None


def test_so_resolve_com_terreno_e_municipio():
    fontes = FontesEmMemoria()
    assert resolver_territorio.para_empreendimento(_emp(), fontes) is not None
    assert resolver_territorio.para_empreendimento(_emp(terreno=False), fontes) is None
    assert resolver_territorio.para_empreendimento(_emp(codigo=""), fontes) is None
    assert resolver_territorio.para_empreendimento(None, fontes) is None


def test_falha_de_leitura_nao_sobe_do_resolvedor():
    fontes = FontesEmMemoria(erro=RuntimeError("CSV ilegível"))
    assert resolver_territorio.para_empreendimento(_emp(), fontes) is None


def test_montar_contexto_entrega_o_recorte_so_quando_ha_terreno(pasta):
    com = composicao.montar_contexto("", None, {}, empreendimento=_emp())
    assert com.recorte_equipamentos is not None
    assert com.recorte_equipamentos.codigo_ibge == "4307807"

    sem = composicao.montar_contexto("", None, {}, empreendimento=_emp(terreno=False))
    assert sem.recorte_equipamentos is None


def test_pelo_pipeline_a_regra_nao_rele_o_disco(pasta, monkeypatch):
    ctx = composicao.montar_contexto("", None, {}, empreendimento=_emp())
    # Com o contexto montado, o leitor passa a explodir: se a regra fosse ao
    # disco, o teste falharia aqui.
    monkeypatch.setattr(leitor, "recorte_municipal",
                        lambda *a, **k: pytest.fail("a regra releu o disco"))
    r = executar(ctx, ids_selecionados=["ENQ-009"])["ENQ-009"]
    assert r.estado is Estado.NAO_CONFORME
    assert r.detalhe["procedencia_recorte"]["nome_municipio"] == "Estrela"


def test_recorte_de_outro_municipio_e_ignorado(pasta):
    """Defensivo: a regra só aceita o recorte do município que ela está julgando.

    Se usasse o recorte (ausente) de 3549904, sairia por insumo ausente; ao
    ignorá-lo fica sem recorte resolvido, e sai por erro de execução.
    """
    ctx = Contexto(empreendimento=_emp(),
                   recorte_equipamentos=RecorteMunicipal(codigo_ibge="3549904"))
    r = ENQ009().checar(ctx)
    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.ERRO_DE_EXECUCAO


def test_recorte_ausente_mantem_o_caminho_na_mensagem_de_diagnostico(pasta):
    ctx = composicao.montar_contexto(
        "", None, {}, empreendimento=_emp(codigo="3549904"))
    r = executar(ctx, ids_selecionados=["ENQ-009"])["ENQ-009"]
    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe["recorte"] == os.path.join(pasta, "equipamentos_3549904.csv")


# ---------------------------------------------------------------------------
# Zona bioclimática (ADR-030)
# ---------------------------------------------------------------------------
#
# Mora aqui, e não junto do leitor, porque o assunto é o MESMO do arquivo: quem
# resolve o território é a aplicação, antes do motor. O que muda é o gate — e é
# exatamente isso que os testes abaixo prendem.


def test_zona_e_resolvida_a_partir_da_localizacao():
    assert str(resolver_territorio.zona_bioclimatica("4307807", FONTES)) == "2R"
    assert str(resolver_territorio.zona_bioclimatica("3549904", FONTES)) == "2M"
    assert resolver_territorio.zona_bioclimatica("", FONTES) is None


def test_zona_NAO_se_gateia_por_terreno():
    """O recorte exige terreno; a zona, não — e a diferença é decisão.

    Os consumidores da zona são regras EDI, que avaliam a unidade habitacional e
    rodam com um modelo isolado, sem terreno nenhum. Gateá-la por terreno as
    deixaria sem parâmetro justo no fluxo em que elas são o assunto.
    """
    sem_terreno = _emp(terreno=False)
    assert resolver_territorio.para_empreendimento(sem_terreno, FONTES) is None
    assert str(resolver_territorio.zona_para_empreendimento(sem_terreno, FONTES)) == "2R"


def test_sem_municipio_declarado_nao_ha_zona():
    fontes = FontesEmMemoria()
    assert resolver_territorio.zona_para_empreendimento(
        _emp(codigo=""), fontes) is None
    assert resolver_territorio.zona_para_empreendimento(None, fontes) is None


def test_o_pipeline_entrega_a_zona_no_contexto():
    ctx = composicao.montar_contexto("", None, {}, empreendimento=_emp())
    assert str(ctx.zona_bioclimatica) == "2R"
    assert ctx.zona_bioclimatica.herdada is False


def test_a_zona_nao_tem_caminho_por_declaracao():
    """Derivada quer dizer: não há como declará-la (ADR-030).

    Se um dia ``zona_bioclimatica`` aparecer no vocabulário de declarações, ela
    terá virado condição de contorno digitável — e este teste cai antes de a
    tela ganhar o seletor.
    """
    from core.dominio.vocabulario import declaracoes as dec
    assert not [n for n in dir(dec) if "zona" in n.lower()]

    emp = _emp()
    emp.declarar({"zona_bioclimatica": "6B"})
    ctx = composicao.montar_contexto("", None, {}, empreendimento=emp)
    assert str(ctx.zona_bioclimatica) == "2R"


def test_base_ilegivel_nao_derruba_a_analise():
    fontes = FontesEmMemoria(erro=OSError("base ilegível"))
    assert resolver_territorio.zona_para_empreendimento(_emp(), fontes) is None


# ---------------------------------------------------------------------------
# População do Censo 2022 — ADR-030, pelo caminho da zona
# ---------------------------------------------------------------------------

def test_populacao_e_resolvida_a_partir_da_localizacao_sem_terreno():
    sem_terreno = _emp(terreno=False)
    assert resolver_territorio.populacao_para_empreendimento(
        sem_terreno, FONTES).populacao == 32183
    assert resolver_territorio.populacao_para_empreendimento(
        _emp(codigo=""), FONTES) is None
    assert resolver_territorio.populacao_para_empreendimento(None, FONTES) is None


def test_o_pipeline_entrega_a_populacao_no_contexto():
    ctx = composicao.montar_contexto("", None, {}, empreendimento=_emp())
    assert ctx.populacao_municipal.populacao == 32183


def test_o_porte_nao_tem_caminho_por_declaracao():
    """Derivado quer dizer: não há como declará-lo (ADR-030) — nem população
    nem porte digitados mudam o que chega ao motor."""
    emp = _emp()
    emp.declarar({"porte_municipal": "acima_250k", "populacao": 999999})
    ctx = composicao.montar_contexto("", None, {}, empreendimento=emp)
    assert ctx.populacao_municipal.populacao == 32183


def test_base_de_municipios_ilegivel_nao_derruba_a_analise():
    fontes = FontesEmMemoria(erro=OSError("base ilegível"))
    assert resolver_territorio.populacao_para_empreendimento(_emp(), fontes) is None
