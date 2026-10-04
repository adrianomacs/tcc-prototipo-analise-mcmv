"""Rede de segurança (ADR-010): cada
página do app roda sem lançar exceção no estado inicial de sessão.

Não é teste de conteúdo — é o teste "não quebrou". A memória do projeto
registra, duas vezes, que uma prova lendo o `render()` cru do Streamlit
passou verde com a tela quebrada de verdade (ver a memória
`folium-js-filho-do-mapa`): o `render()` aceita qualquer coisa e não valida
nada. `streamlit.testing.v1.AppTest` é diferente — ele executa o script da
página de ponta a ponta com o Streamlit de verdade (o mesmo que valida
ícone Material inexistente, tipo de widget errado etc.) e expõe qualquer
exceção lançada durante a execução. Antes deste arquivo, a única página
coberta por teste era a validação de ícones (`test_icones_material.py`);
4.600 linhas de `app/` não tinham nenhum teste de
"a tela abre".

Cada página é testada isolada, sem upload, sem terreno confirmado, sem
análise rodada — o estado em que o usuário abre a página pela primeira
vez. A página de relatório (`relatorio.py`)
tem um teste próprio, abaixo: nesse estado ela deve mostrar um aviso, não
uma tela em branco nem uma exceção.

Requisito de execução (igual ao resto da suíte): `pytest` a partir da raiz
do projeto — é de lá que `st.secrets` (usado pela checagem de Enquadramento
para avisar sobre a ausência de chave do provedor de rede) e os caminhos
relativos a `config/`/`artefatos/` são resolvidos.

**ADR-010**: a lista de
páginas deixou de ser mantida à mão aqui — agora vem de
`app.navegacao.arvore`, a mesma árvore que `app/main.py` usa para montar a
navegação de verdade. `test_navegacao.py` prova a integridade dessa árvore
(nenhuma página órfã, nenhum caminho duplicado); este arquivo só varre
"a árvore inteira roda sem exceção".
"""

from __future__ import annotations

import os

import pytest

from app.navegacao import arvore

pytest.importorskip("streamlit", reason="sem Streamlit não há o que renderizar")
pytestmark = pytest.mark.interface

from streamlit.testing.v1 import AppTest

from tests.conftest import RAIZ

PASTA_PAGINAS = os.path.join(RAIZ, "app", "paginas")

# Toda folha da árvore (as 17 navegáveis) + as ocultas (os dois relatórios e
# `grupos_requisitos.py`, de decisão adiada — ver arvore.py), no formato que
# `_rodar` espera: caminho relativo a `app/paginas/`, sem o prefixo
# "paginas/" que `Pagina.caminho` carrega.
TODAS = [p.caminho.split("paginas/", 1)[1] for p in arvore.todas_as_paginas()]

# Só os dois relatórios têm o comportamento "sem sessão, mostra aviso"
# verificado abaixo — `grupos_requisitos.py` é um placeholder estático como
# os demais, coberto só pelo teste "não lança exceção".
PAGINAS_RELATORIO = [p.caminho.split("paginas/", 1)[1] for p in arvore.OCULTAS
                     if p.caminho.startswith("paginas/relatorios/")]


def _rodar(nome_arquivo: str) -> AppTest:
    caminho = os.path.join(PASTA_PAGINAS, nome_arquivo)
    at = AppTest.from_file(caminho)
    at.run(timeout=60)
    return at


@pytest.mark.parametrize("nome_arquivo", TODAS)
def test_pagina_renderiza_sem_excecao(nome_arquivo):
    at = _rodar(nome_arquivo)
    assert not at.exception, (
        f"{nome_arquivo} lançou exceção no estado inicial:\n"
        + "\n".join(str(e) for e in at.exception)
    )


@pytest.mark.parametrize("nome_arquivo", PAGINAS_RELATORIO)
def test_pagina_de_relatorio_sem_sessao_mostra_aviso(nome_arquivo):
    """Sem `session_state`, o relatório deve avisar e retornar — não
    renderizar em branco. Uma tela em branco passaria no teste acima (não
    lança exceção) e ainda assim estaria quebrada; este teste cobre
    justamente essa lacuna.
    """
    at = _rodar(nome_arquivo)
    # Estado vazio é orientação (`st.info`, ADR-034 (c)), uniforme em todos
    # os relatórios: nunca `st.warning`.
    assert not at.warning, (
        f"{nome_arquivo} mostrou o estado vazio como st.warning; o ADR-034 (c) "
        "pede st.info")
    textos_aviso = [i.value for i in at.info]
    assert textos_aviso, (
        f"{nome_arquivo} não mostrou orientação com a sessão vazia — "
        "verifique se o guard de 'nenhuma análise selecionada' ainda existe"
    )
