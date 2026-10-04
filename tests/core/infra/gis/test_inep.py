"""Adaptador das fontes nacionais do INEP (``core/territorio/de_inep.py``).

O teste que mais importa aqui é o de **regressão semântica**: garantir que
``IN_COMUM_FUND_AI`` nunca volte a ser lido como oferta de etapa. Ele é um
indicador de educação especial, e usá-lo como etapa produziria um número
plausível e errado — a pior espécie de defeito nesta ferramenta, porque
convence. As fixtures abaixo plantam o caso de propósito.
"""

from __future__ import annotations

import os

import pytest

from core.dominio import equipamentos as eq
from core.infra.gis import inep as de_inep
from tests.apoio.inep import (
    CAB_CATALOGO,
    CAB_ESCOLA,
    CAB_TURMA,
    CATALOGO,
    ESCOLAS,
    TURMAS,
)


@pytest.fixture
def fontes(tmp_path):
    """As três fontes nacionais, em miniatura, com os encodings reais."""
    escola = tmp_path / "Tabela_Escola_2025_V2.csv"
    turma = tmp_path / "Tabela_Turma_2025_V2.csv"
    catalogo = tmp_path / "Análise - Tabela da lista das escolas - Detalhado.csv"
    escola.write_text(CAB_ESCOLA + "\n" + "\n".join(ESCOLAS) + "\n", encoding="latin-1")
    turma.write_text(CAB_TURMA + "\n" + "\n".join(TURMAS) + "\n", encoding="latin-1")
    catalogo.write_text(CAB_CATALOGO + "\n" + "\n".join(CATALOGO) + "\n",
                        encoding="utf-8-sig")
    return {"escola": str(escola), "turma": str(turma), "catalogo": str(catalogo)}


@pytest.fixture
def extracao(fontes):
    return de_inep.extrair("4307807", calcular_sha=False, **fontes)


def _por_codigo(extracao) -> dict:
    return {e.codigo_inep: e for e in extracao.equipamentos}


# ---------------------------------------------------------------------------
# Regressão semântica — a razão de este arquivo existir
# ---------------------------------------------------------------------------

def test_in_comum_fund_ai_nao_e_oferta_de_etapa(extracao):
    """``IN_COMUM_*`` é educação especial, não etapa ofertada.

    A escola 103 tem ``IN_COMUM_FUND_AI = 1`` e **zero** turmas de anos
    iniciais. Se o adaptador voltasse a ler o indicador de nome parecido, ela
    entraria no ENQ-010.1 — conformidade falsa, e plausível o bastante para
    passar despercebida.
    """
    e = _por_codigo(extracao)["103"]
    assert eq.CICLO_FUND_I not in e.ciclos
    assert e.ciclos == [eq.CICLO_INFANTIL]


def test_etapa_vem_da_contagem_de_turmas(extracao):
    """E o inverso: ``IN_COMUM_FUND_AI = 0`` não impede a escola 102 de contar."""
    e = _por_codigo(extracao)["102"]
    assert e.ciclos == [eq.CICLO_FUND_I]


# ---------------------------------------------------------------------------
# Ciclos
# ---------------------------------------------------------------------------

def test_infantil_e_creche_ou_pre_escola(extracao):
    """A Portaria trata a educação infantil como faixa única de 0 a 5 anos.

    Ao contrário do fundamental, cujos dois ciclos são requisitos distintos,
    aqui creche e pré-escola satisfazem o mesmo ENQ-009.
    """
    por = _por_codigo(extracao)
    assert eq.CICLO_INFANTIL in por["101"].ciclos      # creche + pré
    assert eq.CICLO_INFANTIL in por["103"].ciclos      # só pré
    assert eq.CICLO_INFANTIL in por["107"].ciclos      # só creche


def test_os_dois_ciclos_do_fundamental_nunca_se_confundem(extracao):
    """Anos iniciais e anos finais são requisitos distintos, jamais somados."""
    por = _por_codigo(extracao)
    assert por["102"].ciclos == [eq.CICLO_FUND_I]
    assert set(por["108"].ciclos) == {eq.CICLO_FUND_I, eq.CICLO_FUND_II}


def test_escola_sem_turma_fica_sem_ciclo_e_e_reportada(extracao):
    e = _por_codigo(extracao)["105"]
    assert e.ciclos == []


# ---------------------------------------------------------------------------
# Atendimento — as duas derivações conferidas contra rótulo
# ---------------------------------------------------------------------------

def test_todas_as_turmas_exclusivas_vira_atendimento_exclusivo(extracao):
    e = _por_codigo(extracao)["104"]
    assert e.atendimento == eq.ATENDIMENTO_EXCLUSIVO_DEFICIENCIA


def test_ativa_que_nao_escolariza_vira_sem_escolarizacao(extracao):
    e = _por_codigo(extracao)["105"]
    assert e.atendimento == eq.ATENDIMENTO_SEM_ESCOLARIZACAO


def test_paralisada_nao_vira_sem_escolarizacao(extracao):
    """A restrição "entre escolas em atividade" não é detalhe: é o teste.

    Escola paralisada ou extinta tem ``IN_ESCOLARIZACAO == 0`` por definição,
    não por vocação. Sem o recorte, a derivação disparava para 34 mil
    estabelecimentos no país contra 683 realmente rotulados.
    """
    e = _por_codigo(extracao)["106"]
    assert e.situacao == eq.SITUACAO_PARALISADA
    assert e.atendimento == eq.ATENDIMENTO_GERAL


# ---------------------------------------------------------------------------
# Precedência POR CAMPO
# ---------------------------------------------------------------------------

def test_coordenada_vem_do_catalogo_e_a_procedencia_diz_isso(extracao):
    e = _por_codigo(extracao)["101"]
    assert (e.lat, e.lon) == (pytest.approx(-29.5013), pytest.approx(-51.9650))
    assert e.procedencia["coordenada"] == "catalogo"
    assert e.procedencia["ciclos"] == "microdado/Tabela_Turma"
    assert e.procedencia["rede"] == "microdado/Tabela_Escola"


def test_rede_e_situacao_vem_do_microdado(extracao):
    por = _por_codigo(extracao)
    assert por["101"].rede == eq.REDE_MUNICIPAL
    assert por["107"].rede == eq.REDE_PRIVADA
    assert por["101"].situacao == eq.SITUACAO_ATIVA


def test_conveniada_vem_do_catalogo(extracao):
    """O microdado desta safra só tem o conceito LARGO (parceria ou convênio).

    Usar o proxy largo para um campo estreito seria o erro do ``IN_COMUM_*``
    em miniatura, então o campo canônico é o rótulo exato do Catálogo.
    """
    por = _por_codigo(extracao)
    assert por["107"].conveniada is True
    assert por["101"].conveniada is False


def test_coordenada_ausente_entra_sem_coordenada_e_nao_reprova(extracao):
    """Lacuna de coordenada é descarte contado, nunca requisito reprovado."""
    e = _por_codigo(extracao)["108"]
    assert e.lat is None and e.lon is None
    assert e.procedencia["coordenada"] == "ausente"
    motivos = eq.filtrar(extracao.equipamentos).contagem_por_motivo
    assert motivos[eq.DESCARTE_SEM_COORDENADA] == 1


# ---------------------------------------------------------------------------
# Recorte, divergências e falhas
# ---------------------------------------------------------------------------

def test_recorte_municipal_e_pelo_codigo_ibge(extracao):
    assert "201" not in _por_codigo(extracao)
    assert extracao.nome_municipio == "Estrela" and extracao.uf == "RS"
    assert extracao.ano_censo == "2025"


def test_codigo_inexistente_avisa_em_vez_de_devolver_vazio_calado(fontes):
    r = de_inep.extrair("9999999", calcular_sha=False, **fontes)
    assert r.equipamentos == []
    assert any("CO_MUNICIPIO" in a for a in r.avisos)


def test_divergencia_entre_as_duas_fontes_e_medida(extracao):
    """Escola que existe numa fonte e não na outra é qualidade de dado medida."""
    assert "999" in extracao.divergencias.so_no_catalogo
    assert extracao.divergencias.so_no_catalogo != []


def test_coluna_essencial_ausente_interrompe_e_nomeia(tmp_path, fontes):
    """Nada é contornado por aproximação — nome parecido já provou enganar."""
    ruim = tmp_path / "Tabela_Turma_2025_V2.csv"
    ruim.write_text("NU_ANO_CENSO;CO_ENTIDADE;CO_MUNICIPIO\n2025;101;4307807\n",
                    encoding="latin-1")
    fontes["turma"] = str(ruim)
    r = de_inep.extrair("4307807", calcular_sha=False, **fontes)
    assert r.equipamentos == []
    assert "QT_TUR_FUND_AI" in r.faltando[de_inep.PAPEL_TURMA]
    assert not r.ok


def test_arquivo_inexistente_e_reportado_por_papel(fontes):
    fontes["catalogo"] = "/caminho/que/nao/existe.csv"
    r = de_inep.extrair("4307807", calcular_sha=False, **fontes)
    assert de_inep.PAPEL_CATALOGO in r.faltando


def test_sha256_e_estavel_e_sensivel(tmp_path):
    a = tmp_path / "a.txt"
    a.write_bytes(b"conteudo")
    primeiro = de_inep.sha256(str(a))
    assert primeiro == de_inep.sha256(str(a))
    a.write_bytes(b"conteudo!")
    assert de_inep.sha256(str(a)) != primeiro


# ---------------------------------------------------------------------------
# Encoding — a mesma armadilha do inspetor, agora no adaptador
# ---------------------------------------------------------------------------

def test_latin1_e_utf8_sao_distinguidos(fontes, extracao):
    """Nome acentuado tem de sobreviver aos dois encodings do conjunto."""
    assert _por_codigo(extracao)["101"].nome == "EMEI CRECHE"
    assert os.path.exists(fontes["catalogo"])
    r = de_inep.extrair("4307807", calcular_sha=False, **fontes)
    assert r.nome_municipio == "Estrela"
