"""Renderizador nativo da árvore de navegação (ADR-010).

A composição dos três níveis é `segmented_control` → `expander` →
`page_link`, sem nenhuma dependência nova:

- **Nível 1** (as duas seções) — `st.segmented_control` no topo da sidebar;
  ao trocar, os grupos mostrados abaixo passam a ser só os da seção
  escolhida.
- **Nível 2** (os grupos) — `st.expander`, **sempre aberto** (todos os grupos visíveis,
  sem exigir um clique). Todo grupo
  usa expander, mesmo os de uma única página (ver a nota em `arvore.Grupo`).
- **Nível 3** (as páginas) — `st.page_link`, que já destaca sozinho a
  página corrente (comparação nativa por `page_script_hash`, no frontend do
  Streamlit) — é por isso que não há nenhuma lógica extra aqui para "marcar"
  a página ativa: ao voltar para uma página, o próprio `page_link` dela já
  aparece destacado, sem código nenhum deste módulo precisar saber disso.

Este módulo não conhece caminhos de arquivo: recebe a `ARVORE` (dado) e um
dicionário que já traduziu cada `Pagina` no `st.Page` correspondente — quem
monta esse dicionário e cria os `st.Page` é `app/main.py`, o único lugar que
o faz.
"""

from __future__ import annotations

import streamlit as st

from app.estado import chaves
from app.navegacao.arvore import ARVORE, Pagina, Secao

_CHAVE_SECAO = "nav_secao"
_CHAVE_ULTIMA_PAGINA = "_nav_ultima_pagina"


def menu_lateral(paginas_st: dict[Pagina, st.Page], atual: st.Page) -> None:
    """Desenha a sidebar inteira: cabeçalho, seções, grupos e páginas."""
    _sincronizar_secao(paginas_st, atual)

    with st.sidebar:
        st.markdown('<div class="marca">Menu de navegação</div>',
                    unsafe_allow_html=True)

        nomes_secoes = [secao.nome for secao in ARVORE]
        escolhida = st.segmented_control(
            "Seção", nomes_secoes, label_visibility="collapsed",
            key=_CHAVE_SECAO,
        ) or st.session_state.get(_CHAVE_SECAO) or ARVORE[0].nome
        secao = next(s for s in ARVORE if s.nome == escolhida)

        for grupo in secao.grupos:
            with st.expander(grupo.nome, icon=grupo.icone, expanded=True):
                for pagina in grupo.paginas:
                    st.page_link(paginas_st[pagina])


def _sincronizar_secao(paginas_st: dict[Pagina, st.Page],
                       atual: st.Page) -> None:
    """Fixa a seção do nível 1 no `session_state` ANTES de criar o widget.

    Ao abrir um relatório (página oculta), o
    `segmented_control` continuava DESENHADO em "Checagens do Protótipo",
    mas o valor devolvido caía no `default` (a primeira seção) e os grupos
    mostrados eram os de "Informações da Pesquisa". A fonte de verdade passa
    a ser só a chave do widget, escrita aqui quando a página MUDA — em reruns
    da mesma página a escolha manual do usuário é preservada.

    Página oculta herda a seção da página de origem do relatório
    (`chaves.ORIGEM_RELATORIO`); sem origem, a seção corrente é mantida.
    """
    mudou = st.session_state.get(_CHAVE_ULTIMA_PAGINA) != atual.url_path
    st.session_state[_CHAVE_ULTIMA_PAGINA] = atual.url_path

    secao = _secao_da_pagina(paginas_st, atual)
    if secao is None:
        origem = st.session_state.get(chaves.ORIGEM_RELATORIO)
        secao = _secao_do_no(origem) if isinstance(origem, Pagina) else None

    if secao is not None and (mudou or _CHAVE_SECAO not in st.session_state):
        st.session_state[_CHAVE_SECAO] = secao.nome
    elif not st.session_state.get(_CHAVE_SECAO):
        st.session_state[_CHAVE_SECAO] = ARVORE[0].nome


def _secao_do_no(pagina: Pagina) -> Secao | None:
    for secao in ARVORE:
        for grupo in secao.grupos:
            if pagina in grupo.paginas:
                return secao
    return None


def _secao_da_pagina(paginas_st: dict[Pagina, st.Page],
                     atual: st.Page) -> Secao | None:
    """A seção (nível 1) que contém a página corrente; `None` nas ocultas."""
    for secao in ARVORE:
        for grupo in secao.grupos:
            for pagina in grupo.paginas:
                if paginas_st.get(pagina) is atual:
                    return secao
    return None
