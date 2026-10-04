"""A regra da dependência vale em ``core/`` sem exceção (ADR-002, ADR-036).

Os quatro anéis, de dentro para fora, e o que cada um pode importar:

- ``dominio``   — só ``dominio``;
- ``regras``    — ``dominio`` e ``regras``;
- ``aplicacao`` — ``dominio``, ``regras`` e ``aplicacao``;
- ``infra``     — ``dominio`` e ``infra`` (pula anéis, o que a regra permite).

Fora dos anéis há um único módulo de composição, ``core/composicao.py``, que
pode importar todos eles e que nenhum anel importa: é o ponto de entrada para
executar a verificação, pela interface e pela linha de comando.

A varredura é por ``ast``, e pega o que um ``grep`` de início de linha deixa
passar: o import local dentro de função (o jeito de adiar a carga do
IfcOpenShell, e por isso comum aqui), o relativo e o ``from core import x``.
Não importa nada e não executa nada.
"""

from __future__ import annotations

import ast
import os

from tests.conftest import RAIZ

PASTA_CORE = os.path.join(RAIZ, "core")

PERMITIDOS = {
    "dominio": {"dominio"},
    "regras": {"dominio", "regras"},
    "aplicacao": {"dominio", "regras", "aplicacao"},
    "infra": {"dominio", "infra"},
}
ANEIS = tuple(PERMITIDOS)

# O único módulo de composição, isento da regra (e proibido aos anéis).
MODULOS_DE_COMPOSICAO = ("composicao",)
# Os únicos arquivos de ``core/`` fora dos anéis.
TOPO_PERMITIDO = {"__init__.py", "composicao.py"}


def _modulos_importados(fonte: str, modulo: str) -> list[tuple[int, str]]:
    """``(linha, módulo absoluto)`` de todo import de ``core`` em ``fonte``.

    ``modulo`` é o nome pontuado do arquivo (``core.regras.base.x``), para
    resolver os imports relativos. ``from core import a, b`` vira ``core.a`` e
    ``core.b`` — é assim que um anel poderia importar a composição.
    """
    pacote = modulo.split(".")[:-1]
    achados: list[tuple[int, str]] = []
    for no in ast.walk(ast.parse(fonte)):
        if isinstance(no, ast.Import):
            achados += [(no.lineno, a.name) for a in no.names]
        elif isinstance(no, ast.ImportFrom):
            if no.level:
                base = pacote[:len(pacote) - (no.level - 1)]
                alvo = ".".join(base + ([no.module] if no.module else []))
            else:
                alvo = no.module or ""
            if alvo == "core":
                achados += [(no.lineno, f"core.{a.name}") for a in no.names]
            else:
                achados.append((no.lineno, alvo))
    return [(linha, m) for linha, m in achados if m == "core" or m.startswith("core.")]


def _arestas_para_fora(fonte: str, modulo: str) -> list[str]:
    """As arestas de ``modulo`` que a regra da dependência proíbe."""
    partes = modulo.split(".")
    origem = partes[1] if len(partes) > 2 else None   # None: topo de core/
    if origem is None and partes[-1] in MODULOS_DE_COMPOSICAO:
        return []
    proibidas = []
    for linha, alvo in _modulos_importados(fonte, modulo):
        destino = alvo.split(".")[1] if alvo.count(".") else ""
        if origem is None:                              # core/__init__.py
            proibidas.append(f"{linha}: topo de core -> {alvo}")
        elif destino in MODULOS_DE_COMPOSICAO:
            proibidas.append(f"{linha}: {origem} -> {alvo} (composição)")
        elif destino in PERMITIDOS and destino not in PERMITIDOS[origem]:
            proibidas.append(f"{linha}: {origem} -> {alvo}")
    return proibidas


def _arquivos_de_core():
    for pasta, subpastas, arquivos in os.walk(PASTA_CORE):
        subpastas[:] = [s for s in subpastas if s != "__pycache__"]
        for nome in sorted(arquivos):
            if nome.endswith(".py"):
                caminho = os.path.join(pasta, nome)
                rel = os.path.relpath(caminho, RAIZ)
                # ``core/regras/__init__.py`` vira ``core.regras.__init__``: o
                # pacote dos relativos continua sendo ``core.regras``.
                yield caminho, rel, rel[:-3].replace(os.sep, ".")


def test_nenhuma_dependencia_aponta_para_fora():
    violacoes = []
    for caminho, rel, modulo in _arquivos_de_core():
        with open(caminho, encoding="utf-8") as f:
            fonte = f.read()
        violacoes += [f"{rel}:{v}" for v in _arestas_para_fora(fonte, modulo)]
    assert not violacoes, (
        "Dependência apontando para fora dos anéis (ADR-002). Mova o módulo "
        "para o anel certo, declare uma porta no domínio ou leve a montagem "
        "para core/composicao.py:\n  " + "\n  ".join(violacoes))


def test_todo_modulo_de_core_mora_num_anel():
    soltos = []
    for _, rel, _modulo in _arquivos_de_core():
        partes = rel.split(os.sep)
        if len(partes) == 2:
            if partes[1] not in TOPO_PERMITIDO:
                soltos.append(rel)
        elif partes[1] not in ANEIS:
            soltos.append(rel)
    assert not soltos, (
        "Módulo de core/ fora dos quatro anéis e da composição — a regra da "
        "dependência não o alcançaria:\n  " + "\n  ".join(soltos))


def test_a_varredura_enxerga_import_local():
    """Autoteste do guarda: um guarda quebrado passaria verde em silêncio."""
    fonte = (
        "from core.dominio import ancora\n"
        "def checar(ctx):\n"
        "    from core.infra.ifc import extrator_ambientes\n"
        "    from . import agregacao\n"
        "    from core import composicao\n"
        "    return extrator_ambientes\n")
    achadas = _arestas_para_fora(fonte, "core.regras.base.exemplo")
    assert achadas == ["3: regras -> core.infra.ifc",
                       "5: regras -> core.composicao (composição)"]
    assert _arestas_para_fora(fonte, "core.composicao") == []
