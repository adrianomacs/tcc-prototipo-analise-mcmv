"""Elementos de layout comuns a todas as páginas (identidade visual).

Centraliza: paleta (espelho do ``[theme]`` em .streamlit/config.toml), CSS
global, cabeçalho com o título da página corrente e rodapé com os dados do
desenvolvedor.

O menu lateral saiu daqui (ADR-010):
mora agora em ``app/navegacao/sidebar.py``, que desenha a árvore de
``app/navegacao/arvore.py`` em vez das listas soltas que este módulo recebia
antes.
"""

from __future__ import annotations

import streamlit as st

# --- Paleta (espelha o [theme] de .streamlit/config.toml) ---
COR_DESTAQUE = "#1F6F8B"         # azul-petróleo
COR_DESTAQUE_ESCURO = "#155066"  # títulos
COR_TEXTO_SUAVE = "#5B6770"      # legendas, eyebrow, rodapé
COR_BORDA = "#D7DEE3"

# --- Alturas (ADR-034 (b)) ---
# Uma constante só para mapa e cena de RELATÓRIO, que desde o ADR-034 ocupam a
# largura total, empilhados sob o card: em notebook (1366 × 768, ou 1920 × 1080
# a 125–150 %) 520 px cabem com o card ainda à vista ao rolar, e em largura
# total mostram mais área que os 700 de antes em meia largura.
ALTURA_VISUALIZACAO = 520
# O mapa de EDIÇÃO (definição do terreno) fica lado a lado com o painel de
# medidas — o usuário desenha e vê a resposta — e mantém a altura de antes.
ALTURA_MAPA_EDICAO = 460
# Tabela longa de resultado: altura fixa, para a página não crescer sem limite.
ALTURA_TABELA = 300

# --- Dados do desenvolvedor (rodapé e página Sobre) ---
DEV_NOME = "Adriano Macedo Silva"
DEV_CURSO = "MBA em Engenharia de Software"
DEV_INSTITUICAO = "USP/ESALQ"
DEV_ORIENTADOR = "Dr. Jorge Carlos Valverde Rebaza"
DEV_ANO = "2026"

# Título do trabalho — eyebrow do cabeçalho de toda página (o cabeçalho da
# sidebar diz só "Menu de navegação" — ver ``app/navegacao/sidebar.py``).
TITULO_TRABALHO = ("Integração BIM-GIS para verificação automatizada de "
                   "requisitos do PMCMV: arquitetura e prova de conceito")

_CSS = """
<style>
/* Largura de leitura contida nas páginas comuns; total nas de tela dividida */
[data-testid="stMainBlockContainer"] {{ max-width: {largura}; }}

/* Cabeçalho */
.cab-eyebrow {{ font-size: .72rem; letter-spacing: .14em; text-transform: uppercase;
  color: {suave}; margin-bottom: -.35rem; }}
h1 {{ color: {escuro}; }}
hr.cab-linha {{ border: none; border-top: 3px solid {destaque}; width: 64px;
  margin: .2rem 0 1.3rem 0; }}

/* Menu lateral */
.marca {{ font-weight: 700; font-size: 1.06rem; color: {escuro};
  line-height: 1.2; margin-bottom: .9rem; }}

/* Rodapé */
.rodape {{ margin-top: 3rem; padding-top: .9rem; border-top: 1px solid {borda};
  font-size: .74rem; color: {suave}; text-align: center; line-height: 1.55; }}
</style>
"""


def aplicar_estilo(larga: bool = False) -> None:
    """Injeta o CSS global. ``larga=True`` libera a largura total (relatório)."""
    st.markdown(
        _CSS.format(
            largura="100%" if larga else "62rem",
            destaque=COR_DESTAQUE, escuro=COR_DESTAQUE_ESCURO,
            suave=COR_TEXTO_SUAVE, borda=COR_BORDA,
        ),
        unsafe_allow_html=True,
    )


def cabecalho(pag) -> None:
    """Cabeçalho comum: título do trabalho (eyebrow) + título da página corrente."""
    st.markdown(f'<div class="cab-eyebrow">{TITULO_TRABALHO}</div>',
                unsafe_allow_html=True)
    st.title(pag.title)
    st.markdown('<hr class="cab-linha">', unsafe_allow_html=True)


def rodape() -> None:
    """Rodapé comum com os dados do desenvolvedor."""
    st.markdown(
        f'<div class="rodape"><b>{DEV_NOME}</b> · {DEV_CURSO} · '
        f'{DEV_INSTITUICAO} · {DEV_ANO}<br>'
        f'Protótipo de Trabalho de Conclusão de Curso — orientador: '
        f'{DEV_ORIENTADOR}</div>',
        unsafe_allow_html=True,
    )


def secao_outras_informacoes() -> None:
    """Separa, em todo relatório, o julgamento do requisito do material de
    consulta (expanders técnicos, tabelas de apoio, JSON): uma linha e o
    título "Outras informações" (ADR-034)."""
    st.divider()
    st.subheader("Outras informações")


def em_desenvolvimento(fase: str) -> None:
    """Aviso padrão das páginas ainda não implementadas."""
    st.info(f"Página em desenvolvimento — prevista na **{fase}**.",
            icon=":material/construction:")
