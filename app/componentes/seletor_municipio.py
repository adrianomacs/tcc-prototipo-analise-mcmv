"""Seletor de localização declarada (UF + município).

Fonte ÚNICA do seletor. Como é compartilhado por telas diferentes, as mensagens daqui não podem supor
o que a tela chamadora faz com a escolha.
"""

from __future__ import annotations

import streamlit as st

from app.componentes.campos import campo_somente_leitura
from app.servicos import declaracoes as dec
from app.servicos import territorio


def seletor_municipio(chave: str, preselecao: dict | None = None) -> dict:
    """UF + município + código IBGE numa linha; devolve as declarações.

    ``preselecao`` (``{"uf": ..., "ibge": ...}``) define a escolha inicial. Serve
    a um caso concreto e a um defeito real: quando a tela carrega um terreno já
    confirmado — do ``artefatos/terreno.json`` —, os seletores caíam no primeiro
    município em ordem alfabética (Acrelândia/AC), e a análise rodava contra uma
    localização declarada que **não era a do terreno**. Um terreno confirmado já
    carrega o município contra o qual foi validado; ele é quem deve mandar na
    primeira carga.

    A pré-seleção só vale no primeiro render: depois, a escolha do usuário vive
    em ``st.session_state`` e prevalece — é ela que permite trocar de município
    deliberadamente, e é o confronto (não o seletor) que avisa da divergência.

    Sem o snapshot local (``config/municipios_ibge.csv``), avisa e devolve um
    dicionário vazio — a tela segue utilizável, apenas sem o confronto com os
    limites municipais.
    """
    mun_mod = territorio.municipios

    base = territorio._municipios_snapshot()
    if not base:
        st.warning("Snapshot de municípios ainda não gerado — sem ele não há "
                   "confronto com os limites municipais nem município "
                   "pré-carregado. Para habilitar, rode na raiz do projeto: "
                   "`python scripts/gerar_municipios.py`",
                   icon=":material/travel_explore:")
        return {}

    pre = preselecao or {}
    pares_uf = mun_mod.ufs(base)

    col_uf, col_mun, col_cod, col_link = st.columns(
        [1.15, 2.1, 1.0, 0.35], vertical_alignment="bottom")

    with col_uf:
        rotulos = [f"{sigla} — {nome}" if nome else sigla for sigla, nome in pares_uf]
        idx_inicial = next((i for i, (sigla, _) in enumerate(pares_uf)
                            if sigla == str(pre.get("uf") or "").upper()), 0)
        idx = st.selectbox("UF:", range(len(rotulos)), index=idx_inicial,
                           format_func=lambda i: rotulos[i], key=f"uf__{chave}")
        uf = pares_uf[idx][0]

    with col_mun:
        da_uf = mun_mod.por_uf(base, uf)
        alvo = str(pre.get("ibge") or "").strip()
        idx_mun = next((i for i, m in enumerate(da_uf) if m.codigo_ibge == alvo), 0)
        escolhido = st.selectbox("Município:", da_uf, index=idx_mun,
                                 format_func=lambda m: m.nome,
                                 key=f"mun__{chave}")

    with col_cod:
        # Campo não editável no mesmo formato de UF e Município (ADR-034): o
        # código é derivado do município escolhido, nunca digitado.
        campo_somente_leitura("Código IBGE:", escolhido.codigo_ibge,
                              chave=f"ibge__{chave}__{escolhido.codigo_ibge}")

    with col_link:
        st.link_button(
            "", mun_mod.url_portal(escolhido),
            icon=":material/open_in_new:",
            help=f"Abrir {escolhido.nome}/{escolhido.uf} no portal Cidades do "
                 "IBGE. O portal indexa pelo NOME; se não abrir, use o código "
                 "ao lado para buscar.")

    return {dec.UF: uf, dec.MUNICIPIO: escolhido.nome,
            dec.MUNICIPIO_IBGE: escolhido.codigo_ibge}
