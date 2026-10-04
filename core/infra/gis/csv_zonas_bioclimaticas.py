"""Leitura do snapshot de zonas bioclimáticas por município.

O snapshot ``config/zonas_bioclimaticas.csv`` é gerado por
``scripts/gerar_zonas_bioclimaticas.py`` a partir dos cinco PDFs regionais da
ABNT TR 15220-3-1:2024, com procedência (sha256 por PDF) em
``config/zonas_bioclimaticas.json``. Este módulo é o **único** lugar que o abre:
o anel de domínio recebe a ``ZonaBioclimatica`` pronta e não faz I/O (ADR-030).

Por que há cache
----------------

São 5.571 linhas e o arquivo não muda durante a execução. Sem cache, cada
análise releria o snapshot inteiro para responder por um município — e o
pipeline monta um contexto por checagem. O cache é por caminho, e
``limpar_cache()`` existe para o teste que aponta o leitor para um CSV
temporário.

Falha de leitura não sobe daqui
-------------------------------

Arquivo ausente ou ilegível devolve ``None``, no mesmo espírito do
``resolver_territorio`` (ADR-011): a regra que precisar da zona sai NÃO
AVALIÁVEL com a causa registrada, e não derruba a análise inteira.
"""

from __future__ import annotations

import csv
import os

from core.dominio.conhecimento.zona_bioclimatica import (
    FONTE_HERANCA,
    ZonaBioclimatica,
)
from core.infra import caminhos

CAMINHO_PADRAO = os.path.join(caminhos.CONFIG, "zonas_bioclimaticas.csv")

# Caminho -> {codigo_ibge: ZonaBioclimatica}. Só entram municípios COM zona: a
# ausência é a chave não existir, e não uma zona vazia a testar depois.
_CACHE: dict[str, dict[str, ZonaBioclimatica]] = {}


def limpar_cache() -> None:
    """Esquece o que foi lido — para o teste que troca o CSV sob os pés."""
    _CACHE.clear()


def _origens(observacao: str) -> tuple[str, ...]:
    """Os códigos IBGE de origem citados na observação da linha herdada.

    A observação é o que o gerador escreve (``…origem (5107925, 5106240)…``).
    Ela é o registro legível da herança; aqui ela vira dado para o relatório
    poder nomear as origens sem reabrir o JSON de procedência.
    """
    esquerda, _, resto = observacao.partition("origem (")
    if not resto or not esquerda:
        return ()
    dentro, _, _ = resto.partition(")")
    return tuple(c.strip() for c in dentro.split(",") if c.strip().isdigit())


def carregar(caminho: str = CAMINHO_PADRAO) -> dict[str, ZonaBioclimatica]:
    """O snapshot inteiro, indexado por código IBGE; vazio se não houver."""
    if caminho in _CACHE:
        return _CACHE[caminho]
    tabela: dict[str, ZonaBioclimatica] = {}
    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8", newline="") as f:
            for linha in csv.DictReader(f, delimiter=";"):
                codigo = str(linha.get("codigo_ibge", "")).strip()
                classe = str(linha.get("zona_bioclimatica", "")).strip()
                if not codigo or not classe:
                    continue
                fonte = str(linha.get("fonte", "")).strip()
                tabela[codigo] = ZonaBioclimatica(
                    classe=classe, codigo_ibge=codigo, fonte=fonte,
                    origens=(_origens(str(linha.get("observacao", "")))
                             if fonte == FONTE_HERANCA else ()))
    _CACHE[caminho] = tabela
    return tabela


def do_municipio(codigo_ibge: str,
                 caminho: str = CAMINHO_PADRAO) -> ZonaBioclimatica | None:
    """A zona do município, ou ``None`` — sem código, sem linha, sem arquivo."""
    codigo = str(codigo_ibge or "").strip()
    if not codigo:
        return None
    return carregar(caminho).get(codigo)


def procedencia(caminho: str = CAMINHO_PADRAO) -> dict:
    """O JSON de procedência do snapshot, para o aviso da tela; ``{}`` se não há."""
    import json
    destino = os.path.splitext(caminho)[0] + ".json"
    if not os.path.exists(destino):
        return {}
    try:
        with open(destino, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}
