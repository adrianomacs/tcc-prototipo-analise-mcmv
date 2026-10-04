"""Caminhos absolutos do projeto, resolvidos a partir deste arquivo — não do
diretório de trabalho corrente.

Um módulo que precisa da raiz do projeto não deve recalculá-la com
``os.path.dirname(os.path.dirname(os.path.abspath(__file__)))``. Caminhos
relativos como ``"config/settings.yaml"`` só resolvem certo quando o processo
é iniciado a partir da raiz — o que acontece com ``streamlit run`` e ``pytest``,
mas é um acoplamento implícito, não garantido. Este módulo é a fonte única
para quem o adota.

``RAIZ`` soma os ``os.path.dirname`` necessários para apontar para a raiz do
projeto (não para ``core/``).
"""

from __future__ import annotations

import os

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
APP_DIR = os.path.join(RAIZ, "app")
CONFIG = os.path.join(RAIZ, "config")
ARTEFATOS = os.path.join(RAIZ, "artefatos")
ENTRADAS = os.path.join(RAIZ, "entradas")
PASTA_TILES = os.path.join(ARTEFATOS, "tiles")


def pasta_tiles(chave: str) -> str:
    """Subpasta de tiles 3D de uma checagem. Sem ela, a conversão de
    todas as checagens gravaria na mesma pasta (`PASTA_TILES` sozinha), e a
    checagem mais recente sobrescreveria em disco os artefatos 3D da anterior
    quando as duas fossem abertas na mesma sessão do Streamlit.
    Cada `chave` de checagem (o mesmo valor de `app.estado.chaves.
    chave_relatorio`) ganha sua própria subpasta sob `PASTA_TILES`.
    """
    return os.path.join(PASTA_TILES, chave)


PASTA_CACHE_TILES = os.path.join(ARTEFATOS, "cache", "tiles")


def pasta_cache_tiles(digest: str) -> str:
    """Conversão 3D guardada pelo CONTEÚDO do IFC.

    Uma subpasta por identidade de conversão — sha256 do arquivo mais os
    parâmetros que mudam o resultado (âncora manual, tipos excluídos). O
    reenvio do mesmo arquivo copia daqui em vez de converter de novo.
    ``artefatos/cache/`` já é ignorada pelo git.
    """
    return os.path.join(PASTA_CACHE_TILES, digest)
