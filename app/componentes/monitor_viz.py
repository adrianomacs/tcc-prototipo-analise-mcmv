"""Ticker de polling da conversão 3D em segundo plano.

Extraído de `_checagem_comum.py`. Recebe `chave` da checagem
: o estado consultado (`estado_viz`) passou a ser por
checagem, não mais global.
"""

from __future__ import annotations

import streamlit as st

from app.servicos.conversao_3d import estado_viz

if hasattr(st, "fragment"):  # Streamlit >= 1.37: polling parcial sem recarregar tudo
    @st.fragment(run_every=2)
    def _monitor_viz(chave: str) -> None:
        """Ticker de polling: reprocessa o app quando a conversão 3D termina."""
        if estado_viz(chave) == "processando":
            st.caption("⏳ Convertendo o modelo para visualização 3D em segundo plano…")
        else:
            st.rerun()
else:  # Fallback para versões sem fragmentos: atualização manual.
    def _monitor_viz(chave: str) -> None:
        st.caption("⏳ Convertendo o modelo para visualização 3D em segundo plano…")
        if st.button("Atualizar estado da visualização", key=f"viz_refresh__{chave}"):
            st.rerun()
