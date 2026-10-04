"""A borda dos segredos: único módulo que lê `st.secrets` e conhece o
adaptador de rede do roteamento (`core.infra.rede.ors`).

Extraído de `_checagem_comum.py`. É aqui — e só aqui, do lado da
interface — que a chave do provedor é procurada; nem o núcleo nem as
regras leem `secrets.toml` ou variável de ambiente por conta própria (a
outra metade da borda é `core.composicao._cli`, do lado da linha de comando).
"""

from __future__ import annotations

import streamlit as st

from core import composicao
from core.infra.rede import ors


def roteador_de_rede():
    """O provedor de distância caminhável em rede, ou `None`.

    **Esta função é a borda.** É aqui que a chave é procurada; nem o
    pipeline nem as regras leem `secrets.toml` ou variável de ambiente por
    conta própria. Um núcleo que lê o ambiente dá resultados diferentes em
    máquinas diferentes e faz a suíte chamar a API de verdade.

    `None` não é erro: é a degradação declarada. Sem
    chave, as três regras de distância saem NÃO AVALIÁVEL por
    `metrica_insuficiente` — nunca aprovadas com o piso euclidiano.
    """
    try:
        segredos = st.secrets
    except Exception:                                   # noqa: BLE001
        # Sem secrets.toml o Streamlit levanta em vez de devolver vazio, e
        # uma tela que morre por falta de arquivo OPCIONAL seria pior que a
        # degradação que este módulo existe para permitir.
        segredos = None
    return ors.de_configuracao(segredos=segredos,
                               cache=composicao._cache_padrao())
