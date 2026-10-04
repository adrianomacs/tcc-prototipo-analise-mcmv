"""Leitura do snapshot de municípios: a lista e a população do Censo 2022.

O snapshot ``config/municipios_ibge.csv`` é gerado por
``scripts/gerar_municipios.py``, com procedência em
``config/municipios_ibge.json``. Este módulo é o **único** lugar que o abre: o
anel de domínio recebe o ``Municipio`` e a ``PopulacaoMunicipal`` prontos e
não faz I/O (ADR-002, ADR-030).

Duas leituras do mesmo arquivo, com contratos diferentes
--------------------------------------------------------

``carregar`` devolve a lista para os seletores da interface: sem arquivo, lista
vazia, e a tela orienta a rodar o script. ``populacao_do_municipio`` responde a
uma pergunta do território: sem código, sem linha, sem população (município
instalado depois do Censo) ou sem arquivo, devolve ``None`` — nunca um número
chutado —, e a regra que precisar do porte sai NÃO AVALIÁVEL.

São 5.571 linhas e o arquivo não muda durante a execução; a população fica em
cache por caminho, como a zona bioclimática, e ``limpar_cache()`` existe para o
teste que aponta o leitor para um CSV temporário.
"""

from __future__ import annotations

import csv
import json
import os

from core.dominio.conhecimento.municipios import Municipio
from core.dominio.conhecimento.porte_municipal import PopulacaoMunicipal
from core.infra import caminhos

CAMINHO_PADRAO = os.path.join(caminhos.CONFIG, "municipios_ibge.csv")

# Caminho -> {codigo_ibge: PopulacaoMunicipal}. Só entram municípios COM
# população: a ausência é a chave não existir.
_CACHE_POPULACAO: dict[str, dict[str, PopulacaoMunicipal]] = {}


def limpar_cache() -> None:
    """Esquece o que foi lido — para o teste que troca o CSV sob os pés."""
    _CACHE_POPULACAO.clear()


def _linhas(caminho: str) -> list[dict]:
    if not os.path.exists(caminho):
        return []
    with open(caminho, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def carregar(caminho: str = CAMINHO_PADRAO) -> list[Municipio]:
    """Lê a lista de municípios; lista vazia se o arquivo ainda não foi gerado."""
    return [Municipio(
                codigo_ibge=str(linha.get("codigo_ibge", "")).strip(),
                nome=str(linha.get("nome", "")).strip(),
                uf=str(linha.get("uf", "")).strip(),
                uf_nome=str(linha.get("uf_nome", "")).strip(),
            ) for linha in _linhas(caminho) if linha.get("codigo_ibge")]


def _numero(texto) -> float | None:
    try:
        return float(str(texto or "").strip())
    except ValueError:
        return None


def _populacoes(caminho: str) -> dict[str, PopulacaoMunicipal]:
    if caminho in _CACHE_POPULACAO:
        return _CACHE_POPULACAO[caminho]
    tabela: dict[str, PopulacaoMunicipal] = {}
    for linha in _linhas(caminho):
        codigo = str(linha.get("codigo_ibge", "")).strip()
        populacao = _numero(linha.get("populacao_2022"))
        if not codigo or populacao is None or populacao < 1:
            continue
        tabela[codigo] = PopulacaoMunicipal(
            codigo_ibge=codigo, populacao=int(populacao),
            densidade=_numero(linha.get("densidade_2022")))
    _CACHE_POPULACAO[caminho] = tabela
    return tabela


def populacao_do_municipio(codigo_ibge: str, caminho: str = CAMINHO_PADRAO
                           ) -> PopulacaoMunicipal | None:
    """A população do Censo 2022 do município, ou ``None``."""
    codigo = str(codigo_ibge or "").strip()
    if not codigo:
        return None
    return _populacoes(caminho).get(codigo)


def procedencia(caminho: str = CAMINHO_PADRAO) -> dict:
    """O JSON de procedência do snapshot; ``{}`` se não há."""
    destino = os.path.splitext(caminho)[0] + ".json"
    if not os.path.exists(destino):
        return {}
    try:
        with open(destino, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}
