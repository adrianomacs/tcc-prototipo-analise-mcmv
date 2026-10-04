"""Integridade da navegação: a árvore (`app/navegacao/arvore.py`) e todo
alvo de navegação (`st.Page(...)`, `st.switch_page(...)`) citado como string
literal em `app/` apontam para um arquivo que existe de verdade.

Por que este teste existe. O ADR-010 registrava que caminhos
de página eram literais soltos em pelo menos seis lugares: "mover ou
renomear uma página quebra navegação em tempo de execução, sem teste que
acuse". Uma varredura por regex cobre isso (as duas primeiras
funções abaixo). **Depois** a navegação virou dado em
`app/navegacao/arvore.py` — exatamente o gatilho que a
versão anterior deste arquivo previa para evoluir "para validar a ÁRVORE
inteira (posição, ícone, seção)": é o que as funções `test_arvore_*` e
`test_toda_pagina_em_disco_esta_na_arvore_ou_oculta` fazem, usando a árvore
como fonte da verdade em vez de uma varredura de citações. As duas funções
de citação continuam por uma razão diferente e ainda válida: pegam um
`st.switch_page("paginas/...")` escrito à mão com o caminho errado, o que a
árvore sozinha não cobre (esses caminhos vivem em `resultado.py` e
`relatorio*.py`, não em `arvore.py`).

A técnica das duas primeiras é a mesma de `test_icones_material.py`:
varredura por regex sobre o texto de `app/` (não importa nada, não executa
nada) — barata e não depende de o Streamlit estar instalado. As de árvore
importam só `app.navegacao.arvore`, que também não depende de Streamlit.
"""

from __future__ import annotations

import os
import re
from collections import Counter

from app.navegacao import arvore
from tests.conftest import RAIZ

PASTA_APP = os.path.join(RAIZ, "app")
PASTA_PAGINAS = os.path.join(PASTA_APP, "paginas")

# Um alvo de página como escrito em st.Page(...) e st.switch_page(...):
# sempre começa em "paginas/" e termina em ".py" — o mesmo padrão usado em
# arvore.py e nas páginas de relatório. Strings dinâmicas (ex.: o
# `origem_relatorio` guardado no session_state) não são literais e não
# aparecem aqui de propósito: o risco que F5 aponta é o caminho escrito à
# mão, não a variável.
PADRAO = re.compile(r'"(paginas/[A-Za-z0-9_./]+\.py)"')


def _alvos_citados() -> set[tuple[str, str]]:
    """``(arquivo_fonte, alvo)`` de toda citação literal encontrada em ``app/``."""
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
            for alvo in PADRAO.findall(conteudo):
                achados.add((os.path.relpath(caminho, RAIZ), alvo))
    return achados


def test_todo_alvo_de_navegacao_citado_existe_em_disco():
    citados = _alvos_citados()
    assert citados, "nenhuma citação de página encontrada — o padrão de busca envelheceu?"

    ausentes = []
    for arquivo_fonte, alvo in sorted(citados):
        caminho_alvo = os.path.join(PASTA_APP, alvo)
        if not os.path.isfile(caminho_alvo):
            ausentes.append(f"{arquivo_fonte}: \"{alvo}\" não existe em app/")

    assert not ausentes, ("alvo de navegação sem arquivo correspondente:\n"
                          + "\n".join(ausentes))


def _todos_arquivos_de_paginas() -> set[str]:
    """Todo ``.py`` de ``app/paginas/``, como ``"paginas/<subpasta>/<arquivo>.py"``
    — o mesmo formato de ``Pagina.caminho``."""
    em_disco: set[str] = set()
    for pasta, _, arquivos in os.walk(PASTA_PAGINAS):
        if "__pycache__" in pasta:
            continue
        for nome in arquivos:
            if not nome.endswith(".py"):
                continue
            caminho = os.path.join(pasta, nome)
            relativo = os.path.relpath(caminho, PASTA_APP).replace(os.sep, "/")
            em_disco.add(relativo)
    return em_disco


def test_toda_pagina_em_disco_esta_na_arvore_ou_oculta():
    """Nenhum arquivo de `app/paginas/` ficou órfão (fora da árvore e fora de
    `OCULTAS`), e a árvore não cita nenhum arquivo que não existe.

    Antes isso era uma varredura por citação textual (qualquer
    menção a "paginas/x.py" em algum lugar de `app/`); agora que a árvore é
    dado, a fonte da verdade é ela mesma.
    """
    em_disco = _todos_arquivos_de_paginas()
    conhecidas = {p.caminho for p in arvore.todas_as_paginas()}

    orfaos = sorted(em_disco - conhecidas)
    assert not orfaos, ("página em disco fora da árvore e de OCULTAS:\n"
                        + "\n".join(orfaos))

    fantasmas = sorted(conhecidas - em_disco)
    assert not fantasmas, ("árvore/OCULTAS citam página que não existe em disco:\n"
                           + "\n".join(fantasmas))


def test_arvore_tem_vinte_e_uma_paginas_navegaveis():
    """Contagem das páginas navegáveis (ADR-010): 17 + 2 de base, mais
    "Requisitos a serem validados" (`grupos_requisitos.py`, no grupo "Dados do
    Empreendimento"). Ficam então 18 na árvore, 2 delas ocultas (os
    relatórios, que continuam em `OCULTAS`). A "Qualificação Urbanística
    (GIS)" (EMP-025, ADR-028) abre a seção de análise do empreendimento: 19.
    O menu "Trabalho de Pesquisa" espelha a estrutura do texto
    da pesquisa: a Definição de Arquitetura fundiu-se em Arquitetura e
    Desenvolvimento, e entraram Desafios Técnicos, Conclusões e
    Considerações e Referências: 21."""
    total_na_arvore = sum(len(grupo.paginas)
                          for secao in arvore.ARVORE for grupo in secao.grupos)
    assert total_na_arvore == 21, (
        f"esperadas 21 páginas navegáveis na árvore, achei {total_na_arvore}")


def test_arvore_sem_caminho_duplicado():
    caminhos = [p.caminho for p in arvore.todas_as_paginas()]
    duplicados = [c for c, n in Counter(caminhos).items() if n > 1]
    assert not duplicados, f"caminho repetido na árvore/OCULTAS: {duplicados}"


def test_arvore_tem_exatamente_uma_pagina_padrao():
    defaults = [p for p in arvore.todas_as_paginas() if p.default]
    assert len(defaults) == 1, (
        f"esperada 1 página com default=True, achei {len(defaults)}: {defaults}")


def test_toda_pagina_e_larga():
    """Toda página ocupa a largura total da janela — pesquisa, checagens,
    resultados e relatórios; a aplicação é uniforme (ADR-034)."""
    estreitas = [p.caminho for p in arvore.todas_as_paginas() if not p.larga]
    assert estreitas == [], f"páginas fora da largura total: {estreitas}"
