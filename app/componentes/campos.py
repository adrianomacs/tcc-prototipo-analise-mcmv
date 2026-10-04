"""Campos de leitura (ADR-034): a entrada que a página consome mas não edita.

Na seção "Informações de entrada", uma checagem cujo insumo vem todo de
Informações Gerais (a Qualificação Urbanística) mostra esse insumo mesmo assim,
em campo **não editável** — o usuário vê com o que a regra vai rodar, e o
lugar de mudar é o link para a 2.1.1 do cabeçalho.
"""

from __future__ import annotations

import streamlit as st

VAZIO = "—"


def valor_exibido(valor) -> str:
    """O que o campo mostra: o valor, ou um travessão quando não declarado —
    nunca um zero ou uma string vazia que pareçam dado."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return VAZIO
    return str(valor)


def campo_somente_leitura(rotulo: str, valor, *, chave: str,
                          ajuda: str | None = None) -> None:
    st.text_input(rotulo, value=valor_exibido(valor), disabled=True,
                  key=chave, help=ajuda)
