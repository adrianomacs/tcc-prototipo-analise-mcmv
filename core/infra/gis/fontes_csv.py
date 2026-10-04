"""``FontesCSV`` — a implementação da porta ``FontesTerritoriais`` sobre os
snapshots versionados em ``config/``.

Não lê nada por conta própria: delega aos três leitores que já são o único
lugar de cada arquivo (``csv_equipamentos``, ``csv_zonas_bioclimaticas``,
``csv_municipios``) e, para a conferência do EMP-001, à malha municipal do
IBGE (``ibge_malhas``). A pasta e os caminhos padrão são lidos **na hora da
chamada**, e não congelados no construtor, para que um teste possa apontar o
recorte para uma pasta temporária trocando o atributo do leitor.

Quem a constrói e injeta é ``core/composicao.py`` (ADR-011); o resolvedor da
aplicação só conhece a porta (``core/dominio/contratos/fontes_territoriais.py``).
"""

from __future__ import annotations

from core.dominio.conhecimento.porte_municipal import PopulacaoMunicipal
from core.dominio.conhecimento.zona_bioclimatica import ZonaBioclimatica
from core.dominio.equipamentos import RecorteMunicipal
from core.infra.gis import (
    csv_equipamentos,
    csv_municipios,
    csv_zonas_bioclimaticas,
    ibge_malhas,
)


class FontesCSV:
    """O território lido dos CSVs de ``config/`` (ou de caminhos explícitos)."""

    def __init__(self, pasta_recortes: str | None = None,
                 caminho_zonas: str | None = None,
                 caminho_municipios: str | None = None) -> None:
        self._pasta_recortes = pasta_recortes
        self._caminho_zonas = caminho_zonas
        self._caminho_municipios = caminho_municipios

    def _pasta(self) -> str:
        return self._pasta_recortes or csv_equipamentos.PASTA_RECORTES

    def recorte_equipamentos(self, codigo_ibge: str) -> RecorteMunicipal:
        return csv_equipamentos.recorte_municipal(codigo_ibge, self._pasta())

    def procedencia_do_recorte(self, codigo_ibge: str) -> dict:
        return csv_equipamentos.procedencia_do_recorte(codigo_ibge, self._pasta())

    def zona_bioclimatica(self, codigo_ibge: str) -> ZonaBioclimatica | None:
        return csv_zonas_bioclimaticas.do_municipio(
            codigo_ibge, self._caminho_zonas or csv_zonas_bioclimaticas.CAMINHO_PADRAO)

    def populacao_municipal(self, codigo_ibge: str) -> PopulacaoMunicipal | None:
        return csv_municipios.populacao_do_municipio(
            codigo_ibge, self._caminho_municipios or csv_municipios.CAMINHO_PADRAO)

    def conferir_ponto_no_municipio(self, codigo_ibge: str, lat: float,
                                    lon: float):
        # A malha não é CSV de config/: é o cache de malhas do IBGE
        # (``ibge_malhas``). Fica nesta implementação porque é a mesma pergunta
        # ao território, e o leitor é chamado na hora, como os outros.
        return ibge_malhas.conferir_ponto(codigo_ibge, lat, lon)
