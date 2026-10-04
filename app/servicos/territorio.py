"""Gateway único para tudo relacionado a território e localização: terreno,
malha municipal, equipamentos e o recorte municipal de equipamentos.

`app/servicos` é o único importador de `core/`: as páginas de checagem não
importam `core.infra.gis.ibge_malhas` nem o módulo de uma regra diretamente.
Este módulo reexpõe os submódulos e funções necessários.

O recorte vem de
`core.aplicacao.resolver_territorio` — o mesmo resolvedor que entrega os
equipamentos ao motor —, e não mais do módulo da regra de distância.
"""

from __future__ import annotations

import os

import streamlit as st

from core import composicao
from core.aplicacao import resolver_territorio as _resolver
from core.dominio import equipamentos  # noqa: F401
from core.dominio import geometria as _geometria
from core.dominio.conhecimento import municipios  # noqa: F401 (reexportado)
from core.dominio.terreno import (  # noqa: F401 (reexportado)
    ROTULO_NIVEL,
    ROTULO_ORIGEM,
    ROTULO_PRECISAO,
    Terreno,
    formatar_numero,
)
from core.infra.caminhos import ARTEFATOS, CONFIG
from core.infra.gis import csv_memorial as de_memorial  # noqa: F401 (reexportado)
from core.infra.gis import csv_municipios as _leitor_municipios
from core.infra.gis import ibge_malhas as malha_municipal
from core.infra.gis import mapa_interativo as de_mapa  # noqa: F401 (reexportado)
from core.infra.ifc import extrator_terreno as de_ifc  # noqa: F401 (reexportado)


@st.cache_data
def _municipios_snapshot() -> list:
    # A leitura mora na infra (ADR-002); `municipios` segue
    # reexportado acima pelas funções puras (``ufs``, ``por_uf``, links).
    return _leitor_municipios.carregar(os.path.join(CONFIG, "municipios_ibge.csv"))


def carregar_recorte(codigo_ibge: str):
    """``Leitura`` do recorte do município, ou ``None`` se não houver arquivo."""
    recorte = _resolver.recorte(codigo_ibge, composicao.fontes_territoriais())
    return recorte.leitura if recorte is not None else None


def procedencia_do_recorte(codigo_ibge: str) -> dict:
    return _resolver.procedencia(codigo_ibge, composicao.fontes_territoriais())


_PASTA_MALHAS = os.path.join(ARTEFATOS, "cache", "malhas")


def centro_municipio(codigo_ibge: str) -> tuple:
    """Centroide da malha municipal (IBGE), para posicionamento aproximado
    de modelos sem âncora geográfica derivável."""
    return malha_municipal.centro_municipio(codigo_ibge, _PASTA_MALHAS)


def epsg_sugerido(codigo_ibge: str) -> str | None:
    """EPSG SIRGAS 2000 / UTM do fuso e hemisfério do centro do município.

    É o padrão que a tela oferece ao importar o CSV de memorial: o CRS é
    declaração do usuário, sugerida pelo município declarado (ADR-029).
    """
    centro = centro_municipio(codigo_ibge)
    if not centro:
        return None
    lat, lon = centro
    return _geometria.epsg_metrico(lon, lat)


def conferir_ponto(codigo_ibge: str, lat: float, lon: float):
    """Confronto do centro do terreno com os limites municipais oficiais."""
    return malha_municipal.conferir_ponto(codigo_ibge, lat, lon, _PASTA_MALHAS)


def malha_em_cache(codigo_ibge: str) -> dict | None:
    """Contorno municipal (GeoJSON) já em cache — sem rede nesta camada."""
    return malha_municipal.malha_em_cache(codigo_ibge, _PASTA_MALHAS)
