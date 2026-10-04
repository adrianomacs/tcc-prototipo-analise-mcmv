"""Ponto de entrada da aplicação multipágina (Streamlit).

Execução:
    streamlit run app/main.py

Estrutura (ADR-010):
  - a navegação é dado, em ``app.navegacao.arvore``: este
    módulo é o ÚNICO lugar que traduz cada ``Pagina`` da árvore num
    ``st.Page`` de verdade, e o único que sabe que a navegação nativa fica
    oculta (``st.navigation(position="hidden")``) atrás de um menu lateral
    desenhado à mão em ``app.navegacao.sidebar.menu_lateral``, o que permite
    a hierarquia de três níveis (seção > grupo > página) que a navegação
    padrão do Streamlit não tem;
  - a largura da página (leitura vs. tela dividida) e a página inicial vêm
    do campo ``larga``/``default`` de cada ``Pagina`` — não são mais uma
    lista solta neste arquivo;
  - cabeçalho (título da página) e rodapé (dados do desenvolvedor) comuns,
    aplicados aqui em volta de ``pagina.run()``;
  - as páginas vivem em ``paginas/pesquisa/``, ``paginas/checagens/`` e
    ``paginas/relatorios/``; as páginas fora da árvore
    (``app.navegacao.arvore.OCULTAS``) seguem acessadas via
    ``st.switch_page``, sem aparecer no menu.
"""

from __future__ import annotations

import streamlit as st

from app.componentes import layout as _layout
from app.navegacao import arvore as _arvore
from app.navegacao import sidebar as _sidebar

# Configuração global única: layout largo + CSS de contenção por página
# (evita múltiplas chamadas a set_page_config entre páginas).
st.set_page_config(layout="wide")

# --- st.Page por Pagina: o único lugar do projeto que cria um st.Page. ---
# A árvore (dado) e as páginas ocultas viram, juntas, a lista que
# st.navigation() precisa; o dicionário é o que permite ao restante do app
# (sidebar, aplicar_estilo) ir da Pagina-dado ao st.Page-de-verdade e vice-
# versa sem conhecer caminho de arquivo nenhum.
_PAGINAS_ST: dict[_arvore.Pagina, st.Page] = {
    pagina: st.Page(pagina.caminho, title=pagina.rotulo, icon=pagina.icone,
                    default=pagina.default)
    for pagina in _arvore.todas_as_paginas()
}

pagina = st.navigation(list(_PAGINAS_ST.values()), position="hidden")

# A Pagina-dado correspondente ao st.Page que a navegação escolheu — é dela
# que vem "larga" (largura) e é ela que a sidebar usa para saber a seção e o
# grupo correntes.
_pagina_dado = next(dado for dado, st_pagina in _PAGINAS_ST.items()
                    if st_pagina is pagina)

_layout.aplicar_estilo(larga=_pagina_dado.larga)
_sidebar.menu_lateral(_PAGINAS_ST, pagina)
_layout.cabecalho(pagina)
pagina.run()
_layout.rodape()
