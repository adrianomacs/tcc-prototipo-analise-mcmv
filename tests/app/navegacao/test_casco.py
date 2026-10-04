"""Integração do "casco" de navegação (`app/main.py` + `app/navegacao/
sidebar.py`) — o que os testes por página (`test_paginas_renderizam.py`)
não cobrem, porque cada um roda a página isolada com `AppTest.from_file`
direto no arquivo, sem passar por `main.py`.

Por que este teste existe. O ADR-010 reescreveu justamente essa casca: `main.py` passou a montar `st.Page` a
partir da árvore e a chamar `sidebar.menu_lateral`, que por sua vez usa
`st.segmented_control` (nível 1) e `st.expander` (nível 2) pela primeira
vez neste projeto. Nada nos testes por página exercitava essa montagem —
um erro ali (ex.: `st.Page` duplicado, identidade quebrada entre o
dicionário e o `st.navigation`, `segmented_control` com opções erradas)
passaria despercebido até o autor abrir o app de verdade. `AppTest.
from_file("app/main.py")` roda o casco inteiro (com a página padrão),
exatamente como `streamlit run app/main.py` faria.

Nota sobre `at.status` nos testes abaixo: a `AppTest` do Streamlit 1.64
classifica todo bloco "expandable" com ícone como `Status` em vez de
`Expander` — é assim que a própria lib distingue um `st.expander(icon=...)`
de um `st.status()`, que compartilham o mesmo proto interno (comentário em
`streamlit/testing/v1/element_tree.py`: "Blocks are classified as a status
by the presence of an icon, so an st.expander with an icon is also exposed
via at.status."). Como os grupos do menu (`sidebar.py`) agora sempre têm
ícone (`grupo.icone`), eles caem
em `at.status`, não em `at.expander` — mesmo sendo, na prática, expanders
comuns. `.proto` é o mesmo `BlockProto.Expandable` nos dois casos.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("streamlit", reason="sem Streamlit não há o que renderizar")
pytestmark = pytest.mark.interface

from streamlit.testing.v1 import AppTest

from tests.conftest import RAIZ

CAMINHO_MAIN = os.path.join(RAIZ, "app", "main.py")


def _rodar() -> AppTest:
    at = AppTest.from_file(CAMINHO_MAIN)
    at.run(timeout=60)
    return at


def test_main_roda_sem_excecao_na_pagina_padrao():
    at = _rodar()
    assert not at.exception, "\n".join(str(e) for e in at.exception)
    assert at.title[0].value == "Visão Geral"


def test_segmented_control_lista_as_duas_secoes_com_a_primeira_ativa():
    at = _rodar()
    assert not at.exception
    (controle,) = at.segmented_control
    assert controle.options == ["Informações da Pesquisa", "Checagens do Protótipo"]
    # A página padrão (Visão Geral) está na primeira seção — é ela que deve
    # vir pré-selecionada, sem o autor precisar clicar em nada.
    assert controle.value == "Informações da Pesquisa"


def test_todos_os_grupos_vem_sempre_expandidos():
    """Todos os grupos de uma seção vêm sempre abertos (não só o da página
    corrente, para que o usuário não precise clicar nos demais) —
    ver a nota do módulo sobre por que a consulta é `at.status`, não
    `at.expander`."""
    at = _rodar()
    rotulos_expandidos = {e.proto.label: e.proto.expanded for e in at.status}
    assert rotulos_expandidos == {"Home": True, "Trabalho de Pesquisa": True}


def test_trocar_de_secao_troca_os_grupos_mostrados():
    at = _rodar()
    (controle,) = at.segmented_control
    at = controle.set_value("Checagens do Protótipo").run(timeout=60)
    assert not at.exception

    rotulos = [e.proto.label for e in at.status]
    assert rotulos == [
        "Dados do Empreendimento",
        "Fase 1: Enquadramento",
        "Fase 2: Análise do Empreendimento",
        "Resultados",
    ]
    # Todos os grupos vêm sempre expandidos, não só o da página corrente.
    assert all(e.proto.expanded for e in at.status)


def test_pagina_padrao_usa_largura_total():
    """Desde o ADR-034 toda página é larga, a Visão Geral inclusive."""
    at = _rodar()
    assert any("max-width: 100%" in m.value for m in at.markdown), (
        "a página padrão (Visão Geral, larga=True) deveria injetar o CSS "
        "de largura total (100%)"
    )
    assert not any("max-width: 62rem" in m.value for m in at.markdown)


def test_relatorio_oculto_mantem_a_secao_da_checagem_de_origem():
    """Regressão: ao abrir "Verificar relatório", o
    controle ficava desenhado em "Checagens do Protótipo" mas os grupos
    mostrados eram os de "Informações da Pesquisa". A página oculta herda a
    seção da origem gravada em `ORIGEM_RELATORIO`, e controle e grupos
    concordam."""
    from app.estado import chaves
    from app.navegacao import arvore

    at = _rodar()
    at = at.segmented_control[0].set_value("Checagens do Protótipo").run(timeout=60)
    at.session_state[chaves.ORIGEM_RELATORIO] = arvore.PAGINA_CHECAGEM_ENQUADRAMENTO
    at.switch_page(arvore.PAGINA_RELATORIO.caminho).run(timeout=60)
    assert not at.exception, "\n".join(str(e) for e in at.exception)
    assert at.segmented_control[0].value == "Checagens do Protótipo"
    rotulos = {e.proto.label for e in at.status}
    assert "Home" not in rotulos and "Dados do Empreendimento" in rotulos


def test_ir_a_pagina_de_outra_secao_troca_a_secao():
    from app.navegacao import arvore

    at = _rodar()
    at.switch_page(arvore.PAGINA_INFORMACOES_GERAIS.caminho).run(timeout=60)
    assert not at.exception, "\n".join(str(e) for e in at.exception)
    assert at.segmented_control[0].value == "Checagens do Protótipo"
