"""Municípios brasileiros — o que um município é na interface e no território.

O snapshot ``config/municipios_ibge.csv`` é gerado por
``scripts/gerar_municipios.py`` (APIs de localidades e de agregados do IBGE) e
alimenta os seletores de UF/município da interface, o cross-check de
localização do EMP-001 e a população do Censo 2022 (ADR-030). A **leitura**
dele mora em ``core/infra/gis/csv_municipios`` — o ``dominio/`` não faz I/O
(ADR-002); este módulo guarda só o valor e as funções puras sobre ele.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Municipio:
    codigo_ibge: str
    nome: str
    uf: str
    uf_nome: str = ""


def ufs(municipios: list[Municipio]) -> list[tuple[str, str]]:
    """Pares (sigla, nome) das UFs presentes, ordenados por sigla."""
    vistos: dict[str, str] = {}
    for m in municipios:
        vistos.setdefault(m.uf, m.uf_nome)
    return sorted(vistos.items())


def por_uf(municipios: list[Municipio], uf: str) -> list[Municipio]:
    """Municípios da UF, ordenados por nome."""
    return sorted((m for m in municipios if m.uf == uf), key=lambda m: m.nome)


# ---------------------------------------------------------------------------
# Portal Cidades do IBGE
# ---------------------------------------------------------------------------
#
# O portal indexa por SLUG DO NOME, não pelo código de 7 dígitos — o que
# reintroduz a dependência de acentuação e grafia que fez o código ser a chave
# em todo o resto do módulo. Daí a divisão de papéis: o **código** é o que a
# interface garante (visível e copiável, e é ele que nomeia o recorte de
# equipamentos); o **link** é conveniência, e quando a slugificação divergir da
# do IBGE quem falha é o link, não a identificação do município.
#
# Mora aqui, e não na camada de interface, porque é conhecimento sobre
# municípios — e porque assim pode ser testado sem Streamlit.

BASE_PORTAL = "https://cidades.ibge.gov.br/brasil"
BASE_API_LOCALIDADES = ("https://servicodados.ibge.gov.br/api/v1/localidades/"
                        "municipios")


def slug_ibge(nome: str) -> str:
    """Nome do município no formato de URL do portal Cidades.

    Minúsculas, sem acento, separadores virando hífen. ``Nova Friburgo`` vira
    ``nova-friburgo``.
    """
    import unicodedata

    sem_acento = "".join(c for c in unicodedata.normalize("NFKD", str(nome or ""))
                         if not unicodedata.combining(c))
    limpo = re.sub(r"[^a-z0-9]+", "-", sem_acento.strip().lower())
    return limpo.strip("-")


def url_portal(municipio: Municipio) -> str:
    """Página Panorama do município no portal Cidades do IBGE."""
    return f"{BASE_PORTAL}/{municipio.uf.lower()}/{slug_ibge(municipio.nome)}/panorama"


def url_api(codigo_ibge: str) -> str:
    """Alternativa chaveada pelo CÓDIGO, se o slug do portal não resolver.

    Devolve JSON em vez de página, mas não depende de grafia — é o caminho
    seguro quando o nome tem apóstrofo ou grafia divergente.
    """
    return f"{BASE_API_LOCALIDADES}/{str(codigo_ibge).strip()}"
