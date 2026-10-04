"""Todo ícone `:material/…:` usado nas telas existe de verdade.

    pytest tests/app/componentes/test_icones_material.py

**Por que este teste existe.** A tela de Georreferenciamento
quebrou uma vez com ``StreamlitAPIException: ":material/description_off:" is not a valid
Material icon`` — um nome plausível, inexistente, escrito à mão. O defeito
sobreviveu à revisão e à prova de tela com o ``streamlit`` falso pelo motivo que
define a classe: **o falso aceita qualquer string como ícone**, porque ele
registra chamadas, não valida argumentos. Só o Streamlit de verdade valida, e ele
valida tarde — no render, na frente do usuário.

O teste é a contrapartida barata disso: varre o código das telas, extrai todo
``:material/…:`` e pede ao **próprio validador do Streamlit** que julgue cada um.
Roda onde o Streamlit existe (a máquina do desenvolvedor) e se pula sozinho onde não
existe (o contêiner), que é exatamente onde ele não teria como decidir nada.
"""

from __future__ import annotations

import os
import re

import pytest

from tests.conftest import RAIZ

PASTA_APP = os.path.join(RAIZ, "app")

# O shortcode como o Streamlit o reconhece; o nome do ícone é o grupo 1.
PADRAO = re.compile(r":material/([a-z0-9_]+):")


def _icones_usados() -> set[tuple[str, str]]:
    """``(arquivo, icone)`` de todo shortcode encontrado em ``app/``."""
    achados: set[tuple[str, str]] = set()
    for pasta, _, arquivos in os.walk(PASTA_APP):
        if "__pycache__" in pasta:
            continue
        for nome in arquivos:
            if not nome.endswith(".py"):
                continue
            caminho = os.path.join(pasta, nome)
            with open(caminho, "r", encoding="utf-8") as f:
                conteudo = f.read()
            for icone in PADRAO.findall(conteudo):
                achados.add((os.path.relpath(caminho, RAIZ), icone))
    return achados


def test_todo_icone_material_das_telas_existe():
    pytest.importorskip("streamlit", reason="sem Streamlit não há o que validar")
    try:
        from streamlit.string_util import validate_material_icon
    except Exception:                                    # noqa: BLE001
        # API interna do Streamlit. Se ela mudar de lugar, este teste vira ruído
        # — e um teste que quebra por mudança de vizinho ensina a ignorá-lo.
        pytest.skip("validador de ícones do Streamlit não está onde se esperava")

    usados = _icones_usados()
    assert usados, "nenhum shortcode encontrado — o padrão de busca envelheceu?"

    invalidos = []
    for arquivo, icone in sorted(usados):
        try:
            validate_material_icon(f":material/{icone}:")
        except Exception as exc:                         # noqa: BLE001
            invalidos.append(f"{arquivo}: :material/{icone}: — {exc}")

    assert not invalidos, "ícone inexistente nas telas:\n" + "\n".join(invalidos)
