"""Cores dos domínios de requisito (GIS, BIM, GIS + BIM, análise humana).

As mesmas do preenchimento da coluna "Classificação" da planilha-mãe, para a
tela e a base se lerem com a mesma legenda. Texto sempre escuro, porque o
fundo é claro nos dois temas. Usado pela página de Análise dos Requisitos e
por "Requisitos a serem validados".
"""

from __future__ import annotations

import streamlit as st

DOMINIOS = ("GIS only", "BIM only", "GIS + BIM", "Análise humana")
COR_DOMINIO = {
    "GIS only": "#E2EFDA",
    "BIM only": "#DDEBF7",
    "GIS + BIM": "#FCE4D6",
    "Análise humana": "#F2F2F2",
}
TEXTO = "#1A1A1A"

# A camada declarada em config/grupos_requisitos.yaml, no rótulo da legenda.
DOMINIO_DA_CAMADA = {
    "GIS": "GIS only",
    "BIM": "BIM only",
    "GIS_BIM": "GIS + BIM",
    "BIM_GIS": "GIS + BIM",
}


def selo_html(dominio: str) -> str:
    cor = COR_DOMINIO.get(dominio, COR_DOMINIO["Análise humana"])
    return (f'<span style="background:{cor};color:{TEXTO};padding:2px 10px;'
            f'border-radius:4px;margin-right:8px;white-space:nowrap">'
            f'{dominio}</span>')


def legenda() -> None:
    itens = "".join(selo_html(d) for d in DOMINIOS)
    st.markdown(f"<div style='margin:4px 0 12px'>{itens}</div>",
                unsafe_allow_html=True)
