"""Toda citação a `docs/…` em docstring ou comentário do código aponta para
um arquivo vigente, e não para `docs/arquivo/` nem `docs/planos/`.

ADR-002 e ADR-003 documentam a regra de dependência do código; a regra de
convivência da documentação (`docs/README.md`, §"Regras de convivência",
item 3) é irmã dela: "código e testes citam ADRs e docs/arquitetura|modulos/,
nunca planos nem fases. Um plano é citável só enquanto está em `planos/`."

Este teste transforma a regra em verificação automática, na mesma família de
`test_fachadas_removidas.py` (varredura estática, não executa nada).

Escopo deliberado: só docstrings (primeira instrução de módulo/classe/função,
via `ast`) e comentários (`#`, via `tokenize`) são varridos — strings comuns
(texto mostrado nas telas, por exemplo `app/paginas/pesquisa/definicao_
arquitetura.py`) não entram nesta varredura porque não são "código citando
plano para se justificar"; são conteúdo para o leitor da tela, não código
citando documento.
"""

from __future__ import annotations

import ast
import os
import re
import tokenize

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PASTAS_VARRIDAS = ("core", "app", "tests")

PADRAO_CAMINHO_DOCS = re.compile(r"docs/[A-Za-z0-9_./-]+\.(?:md|png|csv|xlsx)")


def _arquivos_py():
    for pasta in PASTAS_VARRIDAS:
        base = os.path.join(RAIZ, pasta)
        for raiz_atual, _dirs, arquivos in os.walk(base):
            for nome in arquivos:
                if nome.endswith(".py"):
                    yield os.path.join(raiz_atual, nome)


def _docstrings(caminho: str, fonte: str) -> list[str]:
    """Docstring de módulo e de cada classe/função definida no arquivo."""
    arvore = ast.parse(fonte, filename=caminho)
    textos = []
    doc_modulo = ast.get_docstring(arvore)
    if doc_modulo:
        textos.append(doc_modulo)
    for no in ast.walk(arvore):
        if isinstance(no, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            doc = ast.get_docstring(no)
            if doc:
                textos.append(doc)
    return textos


def _comentarios(caminho: str) -> list[str]:
    textos = []
    with open(caminho, "rb") as arq:
        for tok in tokenize.tokenize(arq.readline):
            if tok.type == tokenize.COMMENT:
                textos.append(tok.string.lstrip("#").strip())
    return textos


def _citacoes_docs_em_codigo():
    """(caminho_do_arquivo_py, caminho_docs_citado) para cada citação achada
    em docstring ou comentário."""
    for caminho in _arquivos_py():
        with open(caminho, encoding="utf-8") as arq:
            fonte = arq.read()
        textos = _docstrings(caminho, fonte) + _comentarios(caminho)
        for texto in textos:
            for achado in PADRAO_CAMINHO_DOCS.findall(texto):
                yield caminho, achado


def test_todo_caminho_docs_citado_em_docstring_ou_comentario_existe():
    faltando = []
    for caminho, achado in _citacoes_docs_em_codigo():
        if not os.path.isfile(os.path.join(RAIZ, achado)):
            faltando.append(f"{os.path.relpath(caminho, RAIZ)}: docs/… citado não existe: {achado}")
    assert not faltando, "\n" + "\n".join(faltando)


def test_nenhuma_citacao_em_docstring_ou_comentario_aponta_para_arquivo_ou_planos():
    proibidas = []
    for caminho, achado in _citacoes_docs_em_codigo():
        if achado.startswith(("docs/arquivo/", "docs/planos/")):
            proibidas.append(f"{os.path.relpath(caminho, RAIZ)}: cita {achado} (superado ou de vida curta)")
    assert not proibidas, "\n" + "\n".join(proibidas)
