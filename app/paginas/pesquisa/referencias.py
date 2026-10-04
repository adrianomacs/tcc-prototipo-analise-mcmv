"""Referências — 1.2.9. A bibliografia do trabalho, na forma de lista de
referências. As entradas vêm de `docs/tcc/referencias.yaml`
pelo serviço `app.servicos.referencias`, a fonte única da página,
e as ainda pendentes de conferência aparecem marcadas. Página de pesquisa:
largura total (ADR-034)."""

import re

import streamlit as st

from app.servicos import referencias as _referencias

_URL = re.compile(r"<(https?://[^>\s]+)>")


@st.cache_data(show_spinner=False)
def _lista(carimbo: float):
    # "carimbo" (sem sublinhado) entra na chave do cache: editar o YAML
    # invalida a lista sem reiniciar o aplicativo.
    return _referencias.carregar_referencias()


refs = _lista(_referencias.carimbo_das_referencias())

st.write(
    "As referências abaixo são as mesmas do texto do TCC, na mesma ordem "
    "alfabética e no formato adotado pela USP/ESALQ. As que ainda aguardam "
    "conferência de algum dado na fonte estão indicadas como *a validar*."
)

for r in refs:
    # O endereço eletrônico vem entre "<" e ">", como pede o formato ESALQ.
    # Escapar só os sinais não basta, porque o Markdown reconhece o endereço
    # sozinho e engole o ">" final no link, que quebra; por isso o endereço
    # vira um link explícito e os sinais ficam escapados fora dele.
    texto = _URL.sub(r"\<[\1](\1)\>", r.texto)
    marca = " *(a validar)*" if r.validar else ""
    st.markdown(texto + marca)
