"""ADR-030 — a leitura do snapshot de zonas mora na infra, e o que ela devolve.

O anel de domínio recebe a zona pronta: este é o único módulo que abre o CSV.
O que se prende aqui é o contrato dessa leitura — município sem linha devolve
``None`` em vez de zona vazia, base ilegível não levanta, e a linha herdada
chega marcada, com as origens já extraídas da observação.

Os dois valores conferidos à mão (Estrela/RS e São José dos
Campos/SP) entram como teste contra o snapshot **real**: são a âncora que
pega uma regeração que mude a base sem querer.
"""

from __future__ import annotations

import pytest

from core.dominio.conhecimento.zona_bioclimatica import FONTE_HERANCA, FONTE_NORMA
from core.infra.gis import csv_zonas_bioclimaticas as leitor

CABECALHO = ("codigo_ibge;nome;uf;zona_bioclimatica;fonte;latitude;longitude;"
             "altitude_m;tbs_media_anual_c;ur_media_anual_pct;"
             "radiacao_global_diaria_wm2;vento_medio_anual_ms;"
             "amplitude_termica_anual_c;nome_na_abnt;observacao\n")


@pytest.fixture(autouse=True)
def _sem_cache():
    leitor.limpar_cache()
    yield
    leitor.limpar_cache()


def _csv(tmp_path, *linhas):
    destino = tmp_path / "zonas_bioclimaticas.csv"
    destino.write_text(CABECALHO + "".join(linhas), encoding="utf-8")
    return str(destino)


# -- contra o snapshot real do repositório ----------------------------------

def test_estrela_rs_e_sao_jose_dos_campos_sp():
    """Os dois municípios conferidos à mão contra o PDF da ABNT."""
    assert str(leitor.do_municipio("4307807")) == "2R"     # Estrela/RS
    assert str(leitor.do_municipio("3549904")) == "2M"     # São José dos Campos/SP


def test_o_municipio_novo_herda_e_diz_que_herdou():
    zona = leitor.do_municipio("5101837")                  # Boa Esperança do Norte/MT
    assert zona is not None and zona.classe == "5B"
    assert zona.herdada is True
    assert zona.origens == ("5107925", "5106240")


def test_a_procedencia_acompanha_o_snapshot():
    proc = leitor.procedencia()
    assert proc.get("norma") == "ABNT TR 15220-3-1:2024"
    assert proc["municipios"]["sem_zona"] == 0


# -- contrato da leitura -----------------------------------------------------

def test_municipio_sem_linha_devolve_none(tmp_path):
    caminho = _csv(tmp_path, f"4307807;Estrela;RS;2R;{FONTE_NORMA};;;;;;;;;;\n")
    assert leitor.do_municipio("4307807", caminho) is not None
    assert leitor.do_municipio("3550308", caminho) is None
    assert leitor.do_municipio("", caminho) is None


def test_linha_sem_zona_nao_vira_zona_vazia(tmp_path):
    caminho = _csv(tmp_path, "5101837;Boa Esperança do Norte;MT;;AUSENTE;;;;;;;;;;\n")
    assert leitor.do_municipio("5101837", caminho) is None


def test_base_ausente_nao_levanta(tmp_path):
    caminho = str(tmp_path / "nao_existe.csv")
    assert leitor.carregar(caminho) == {}
    assert leitor.do_municipio("4307807", caminho) is None
    assert leitor.procedencia(caminho) == {}


def test_origens_saem_da_observacao_da_linha_herdada(tmp_path):
    caminho = _csv(tmp_path,
                   f"5101837;Boa Esperança do Norte;MT;5B;{FONTE_HERANCA};"
                   ";;;;;;;;;"
                   '"município não consta do X; zona herdada dos municípios de '
                   'origem (5107925, 5106240), que concordam — ADR-030"\n')
    zona = leitor.do_municipio("5101837", caminho)
    assert zona.herdada is True and zona.origens == ("5107925", "5106240")
