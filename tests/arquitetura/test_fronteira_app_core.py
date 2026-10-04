"""`app/servicos` é o único importador do núcleo (`core/`) dentro de `app/`.

ADR-003: "teste
que falha se `app/paginas` ou `app/componentes` importar `core.`" — o mesmo
enunciado, `grep "from core" app/paginas app/componentes` vazio.

Por que este teste existe. Quando as páginas importavam o núcleo diretamente,
`checagem_enquadramento.py` importava `core.infra.gis.ibge_malhas`, `core.territorio.*` e até o módulo
de uma regra (`core.motor.regras.gis._distancia_equipamento`) diretamente; esse
acesso foi movido para `app/servicos/`, que passa a ser o único
*gateway* do núcleo — `app/paginas` e `app/componentes` só chamam
`app.servicos.*` e entre si. Sem este teste, um `import core.…` novo dentro
de uma página ou de um componente reabriria a dependência direta em silêncio,
e nada mais no projeto o impediria.

A técnica é a mesma de `test_icones_material.py` e `test_arvore.py`:
varredura por regex sobre o texto de `app/paginas` e `app/componentes` (não
importa nada, não executa nada) — barata e não depende de o Streamlit estar
instalado.
"""

from __future__ import annotations

import os
import re

from tests.conftest import RAIZ

PASTA_APP = os.path.join(RAIZ, "app")

# `import core`, `import core.x.y`, `from core import x`, `from core.x import y`
# — sempre com `core` como o primeiro componente do caminho (não pega
# `app.servicos.territorio` nem menções em prosa como "core/motor/…" dentro
# de uma docstring, que não são import).
PADRAO = re.compile(r"^\s*(?:from\s+core(?:\.\S+)?\s+import\s+\S+|import\s+core(?:\.\S+)?)\b",
                    re.MULTILINE)

PASTAS_VETADAS = ("paginas", "componentes")


def _imports_de_core_em(nome_pasta: str) -> list[str]:
    """``"arquivo:linha: trecho"`` de todo import de `core` encontrado."""
    achados: list[str] = []
    pasta_alvo = os.path.join(PASTA_APP, nome_pasta)
    for pasta, _, arquivos in os.walk(pasta_alvo):
        if "__pycache__" in pasta:
            continue
        for nome in sorted(arquivos):
            if not nome.endswith(".py"):
                continue
            caminho = os.path.join(pasta, nome)
            with open(caminho, "r", encoding="utf-8") as f:
                linhas = f.readlines()
            for i, linha in enumerate(linhas, start=1):
                if PADRAO.match(linha):
                    relativo = os.path.relpath(caminho, RAIZ)
                    achados.append(f"{relativo}:{i}: {linha.strip()}")
    return achados


def test_paginas_nao_importam_core_diretamente():
    achados = _imports_de_core_em("paginas")
    assert not achados, (
        "app/paginas importando core/ diretamente — passe por app/servicos:\n"
        + "\n".join(achados)
    )


def test_componentes_nao_importam_core_diretamente():
    achados = _imports_de_core_em("componentes")
    assert not achados, (
        "app/componentes importando core/ diretamente — passe por "
        "app/servicos:\n" + "\n".join(achados)
    )


def test_servicos_e_o_unico_importador_do_nucleo():
    """Confirma o inverso: fora de `app/servicos`, nenhuma pasta de `app/`
    (exceto `paginas`/`componentes`, já cobertos acima) importa `core`.

    Cobre `app/estado/` e o próprio `app/main.py` — hoje nenhum dos dois
    precisa de `core`, e um import futuro ali seria o mesmo desvio que este
    arquivo existe para prevenir.
    """
    achados: list[str] = []
    for pasta, subpastas, arquivos in os.walk(PASTA_APP):
        if "__pycache__" in pasta:
            continue
        subpastas[:] = [s for s in subpastas if s != "__pycache__"]
        relativo_pasta = os.path.relpath(pasta, PASTA_APP)
        primeiro_componente = relativo_pasta.split(os.sep, 1)[0]
        if primeiro_componente in PASTAS_VETADAS or primeiro_componente == "servicos":
            continue
        for nome in sorted(arquivos):
            if not nome.endswith(".py"):
                continue
            caminho = os.path.join(pasta, nome)
            with open(caminho, "r", encoding="utf-8") as f:
                linhas = f.readlines()
            for i, linha in enumerate(linhas, start=1):
                if PADRAO.match(linha):
                    relativo = os.path.relpath(caminho, RAIZ)
                    achados.append(f"{relativo}:{i}: {linha.strip()}")
    assert not achados, (
        "import de core/ fora de app/servicos (e fora de app/paginas e "
        "app/componentes, já cobertos pelos testes acima):\n"
        + "\n".join(achados)
    )
