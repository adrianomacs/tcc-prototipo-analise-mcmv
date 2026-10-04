"""ADR-030/ADR-002 — a leitura do snapshot de municípios mora na infra.

O contrato da leitura: a lista para os seletores (vazia sem arquivo) e a
população do Censo 2022 por município (``None`` sem código, sem linha, sem
população ou sem arquivo — nunca um número chutado). Os dois municípios do
estudo de caso entram contra o snapshot **real**: são a âncora que pega uma
regeração que mude a base sem querer.
"""

from __future__ import annotations

import inspect

import pytest

from core.dominio.conhecimento import municipios
from core.infra.gis import csv_municipios as leitor

CABECALHO = "codigo_ibge;nome;uf;uf_nome;populacao_2022;densidade_2022\n"


@pytest.fixture(autouse=True)
def _sem_cache():
    leitor.limpar_cache()
    yield
    leitor.limpar_cache()


def _csv(tmp_path, *linhas):
    destino = tmp_path / "municipios_ibge.csv"
    destino.write_text(CABECALHO + "".join(linhas), encoding="utf-8")
    return str(destino)


# -- contra o snapshot real do repositório ----------------------------------

def test_estrela_rs_e_sao_jose_dos_campos_sp():
    estrela = leitor.populacao_do_municipio("4307807")
    assert estrela.populacao == 32183 and estrela.densidade == pytest.approx(173.94)
    assert leitor.populacao_do_municipio("3549904").populacao == 697054


def test_municipio_instalado_depois_do_censo_fica_sem_populacao():
    """Boa Esperança do Norte/MT (01/01/2025): sem porte, e não com o dos
    municípios de origem — população não se herda como zona (ADR-030)."""
    assert leitor.populacao_do_municipio("5101837") is None
    assert any(m.codigo_ibge == "5101837" for m in leitor.carregar())


def test_a_procedencia_acompanha_o_snapshot():
    proc = leitor.procedencia()
    pop = proc["populacao"]
    assert pop["tabela"] == "4714" and pop["data_de_referencia"] == "2022-07-31"
    assert pop["sem_populacao"] == ["5101837"]
    assert proc["lista_de_municipios"]["total"] == 5571


# -- contrato da leitura -----------------------------------------------------

def test_lista_e_populacao_de_um_csv_temporario(tmp_path):
    caminho = _csv(tmp_path, "0000001;Um;XX;Estado X;12345;6.7\n",
                   "0000002;Dois;XX;Estado X;;\n")
    assert [m.nome for m in leitor.carregar(caminho)] == ["Um", "Dois"]
    assert leitor.populacao_do_municipio("0000001", caminho).populacao == 12345
    assert leitor.populacao_do_municipio("0000002", caminho) is None
    assert leitor.populacao_do_municipio("", caminho) is None
    assert leitor.populacao_do_municipio("9999999", caminho) is None


def test_snapshot_antigo_sem_as_colunas_do_censo(tmp_path):
    """O snapshot anterior (só quatro colunas) continua servindo a lista e
    responde "sem população" — nunca derruba a tela."""
    destino = tmp_path / "municipios_ibge.csv"
    destino.write_text("codigo_ibge;nome;uf;uf_nome\n0000001;Um;XX;Estado X\n",
                       encoding="utf-8")
    assert len(leitor.carregar(str(destino))) == 1
    assert leitor.populacao_do_municipio("0000001", str(destino)) is None


def test_arquivo_ausente(tmp_path):
    caminho = str(tmp_path / "nao_existe.csv")
    assert leitor.carregar(caminho) == []
    assert leitor.populacao_do_municipio("4307807", caminho) is None
    assert leitor.procedencia(caminho) == {}


def test_o_dominio_nao_le_mais_o_arquivo():
    """ADR-002: a exceção de I/O do anel de domínio foi removida — a leitura
    saiu de ``conhecimento/municipios.py`` para cá."""
    fonte = inspect.getsource(municipios)
    assert not hasattr(municipios, "carregar")
    assert "import csv" not in fonte and "import os" not in fonte
