"""Guarda estática: todo ``servico.atributo`` usado em ``app/`` existe no serviço.

Origem: a remoção das fachadas Strangler Fig reescreveu o
import de ``app/servicos/territorio.py`` e deixou cair ``de_mapa`` e
``de_ifc``. A suíte passou inteira porque nenhum teste importa a página do
Enquadramento; o erro só apareceu na tela, como ``AttributeError`` em
``territorio.de_mapa``. Este teste lê o código com ``ast`` (sem importar
Streamlit nem executar páginas) e reprova qualquer atributo órfão.
"""

from __future__ import annotations

import ast
from functools import lru_cache
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
SERVICOS = RAIZ / "app" / "servicos"


def _arquivo_do_modulo(modulo: str) -> Path:
    base = RAIZ.joinpath(*modulo.split("."))
    return base.with_suffix(".py") if base.with_suffix(".py").exists() else base / "__init__.py"


@lru_cache(maxsize=None)
def _nomes_de_topo(caminho: Path) -> frozenset:
    """Nomes definidos no topo do módulo, seguindo ``from x import *``."""
    nomes: set[str] = set()
    for no in ast.parse(caminho.read_text(encoding="utf-8")).body:
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            nomes.add(no.name)
        elif isinstance(no, (ast.Assign, ast.AnnAssign)):
            alvos = no.targets if isinstance(no, ast.Assign) else [no.target]
            nomes |= {n.id for alvo in alvos for n in ast.walk(alvo) if isinstance(n, ast.Name)}
        elif isinstance(no, ast.ImportFrom) and no.names[0].name == "*":
            origem = _nomes_de_topo(_arquivo_do_modulo(no.module))
            nomes |= {n for n in origem if not n.startswith("_")}
        elif isinstance(no, (ast.Import, ast.ImportFrom)):
            nomes |= {(a.asname or a.name).split(".")[0] for a in no.names}
    return frozenset(nomes)


def _usos_orfaos() -> list[str]:
    servicos = {p.stem: _nomes_de_topo(p) for p in SERVICOS.glob("*.py")}
    orfaos = []
    for arquivo in sorted((RAIZ / "app").rglob("*.py")):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        apelidos = {
            (a.asname or a.name): a.name
            for no in ast.walk(arvore)
            if isinstance(no, ast.ImportFrom) and no.module == "app.servicos"
            for a in no.names
        }
        for no in ast.walk(arvore):
            if (
                isinstance(no, ast.Attribute)
                and isinstance(no.value, ast.Name)
                and no.value.id in apelidos
            ):
                servico = apelidos[no.value.id]
                if servico in servicos and no.attr not in servicos[servico]:
                    rel = arquivo.relative_to(RAIZ).as_posix()
                    orfaos.append(f"{rel}:{no.lineno}: {no.value.id}.{no.attr}")
    return sorted(set(orfaos))


def test_nenhum_atributo_de_servico_orfao():
    assert _usos_orfaos() == []


def test_territorio_reexpoe_mapa_e_ifc():
    nomes = _nomes_de_topo(SERVICOS / "territorio.py")
    assert {"de_mapa", "de_ifc"} <= nomes
