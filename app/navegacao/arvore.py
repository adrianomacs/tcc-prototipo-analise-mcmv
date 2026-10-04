"""Estrutura do menu como dado (ADR-010).

Um nó = (rótulo, ícone, filhos | página). Três níveis, nunca mais que isso:
**Seção** (nível 1) > **Grupo** (nível 2) > **Página** (nível 3, folha).

Este módulo não importa Streamlit nem desenha nada — é só o dado ("a
estrutura do menu passa a ser um dado", ADR-010). Quem lê a árvore para
desenhar a sidebar é
`app/navegacao/sidebar.py`; quem lê a árvore para montar a navegação nativa
(`st.Page`/`st.navigation`) é `app/main.py` — o único lugar que cria um
`st.Page` de verdade. Assim, mover ou renomear uma página muda só este
arquivo; nenhum outro módulo conhece caminhos de arquivo.

A árvore tem 21 páginas navegáveis em duas seções (com `Requisitos a
serem validados` em "Dados do Empreendimento" — ver mais abaixo); páginas
ainda sem conteúdo entram como placeholders (`_layout.em_desenvolvimento`)
até serem escritas.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Pagina:
    """Uma folha da árvore: um arquivo em `app/paginas/`.

    `caminho` é relativo a `app/` — o mesmo formato que `st.Page` e
    `st.switch_page` já usam. `larga` marca as páginas de largura total, em
    vez da largura de leitura de 62rem. Desde o ADR-034 toda página da
    árvore é larga, pesquisa inclusive — a tela se adapta à janela; o campo
    fica por página, junto com o resto do que a descreve.
    `requer_empreendimento` marca as páginas que exigem um `Empreendimento`
    definido em 2.1.1.
    """

    rotulo: str
    caminho: str
    icone: str | None = None
    default: bool = False
    larga: bool = False
    requer_empreendimento: bool = False


@dataclass(frozen=True)
class Grupo:
    """Nível 2: um agrupamento de páginas dentro de uma seção.

    Todo grupo — mesmo o de uma página só (hoje, "Fase 1: Enquadramento") —
    renderiza como `st.expander` (ver `sidebar.py`): é a opção "coerência", porque o rótulo do grupo
    carrega contexto que a página filha sozinha não diz (ex.: "Fase 1:
    Enquadramento" acima de "Enquadramento (GIS)") — cada grupo funciona
    como o seu próprio item de menu. Todo grupo vem SEMPRE expandido
    (ver `sidebar.py`), não só o que contém a página corrente.
    """

    nome: str
    paginas: tuple[Pagina, ...]
    icone: str | None = None


@dataclass(frozen=True)
class Secao:
    """Nível 1: uma das duas grandes divisões do menu."""

    nome: str
    grupos: tuple[Grupo, ...]
    icone: str | None = None


# --- Seção 1: Informações da Pesquisa --------------------------------------

_HOME = Grupo("Home", icone=":material/cottage:", paginas=(
    Pagina("Visão Geral", "paginas/pesquisa/home.py",
           icone=":material/home:", default=True, larga=True),
    Pagina("Agradecimentos", "paginas/pesquisa/agradecimentos.py",
           icone=":material/volunteer_activism:", larga=True),
    Pagina("Sobre", "paginas/pesquisa/sobre.py",
           icone=":material/info:", larga=True),
))

_TRABALHO_PESQUISA = Grupo("Trabalho de Pesquisa", icone=":material/science:", paginas=(
    # Um item por passo do método, na ordem do método, mais o fecho e
    # as referências.
    Pagina("Metodologia", "paginas/pesquisa/metodologia.py",
           icone=":material/menu_book:", larga=True),
    Pagina("Análise, Classificação e Seleção dos Requisitos",
           "paginas/pesquisa/consolidacao_requisitos.py",
           icone=":material/table_view:", larga=True),
    Pagina("Framework de Análise", "paginas/pesquisa/fluxo_idealizado.py",
           icone=":material/schema:", larga=True),
    Pagina("Arquitetura e Desenvolvimento do Protótipo",
           "paginas/pesquisa/desenvolvimento_prototipo.py",
           icone=":material/handyman:", larga=True),
    Pagina("Dados para os Testes", "paginas/pesquisa/dados_utilizados.py",
           icone=":material/dataset:", larga=True),
    Pagina("Avaliação do Protótipo",
           "paginas/pesquisa/metodologia_avaliacao.py",
           icone=":material/speed:", larga=True),
    Pagina("Desafios Técnicos", "paginas/pesquisa/desafios_tecnicos.py",
           icone=":material/flag:", larga=True),
    Pagina("Conclusões e Considerações", "paginas/pesquisa/conclusoes.py",
           icone=":material/task_alt:", larga=True),
    Pagina("Referências", "paginas/pesquisa/referencias.py",
           icone=":material/bookmarks:", larga=True),
))

SECAO_PESQUISA = Secao("Informações da Pesquisa", (_HOME, _TRABALHO_PESQUISA),
                       icone=":material/school:")

# --- Seção 2: Checagens do Protótipo ----------------------------------------

# ADR-010: páginas citadas por código FORA deste módulo (o cabeçalho do
# empreendimento, o "voltar" dos relatórios, a origem gravada por
# `app.componentes.resultado`) passam a importar o NÓ da árvore em vez de
# escrever o caminho de novo como string solta — mover ou renomear uma
# dessas páginas volta a ser uma mudança só aqui.
PAGINA_INFORMACOES_GERAIS = Pagina(
    "Informações Gerais", "paginas/checagens/informacoes_gerais.py",
    icone=":material/apartment:", larga=True)
PAGINA_CHECAGEM_ENQUADRAMENTO = Pagina(
    "Enquadramento (GIS)", "paginas/checagens/checagem_enquadramento.py",
    icone=":material/travel_explore:", larga=True)
PAGINA_CHECAGEM_QUALIFICACAO = Pagina(
    "Qualificação Urbanística (GIS)",
    "paginas/checagens/checagem_qualificacao.py",
    icone=":material/location_city:", larga=True)
PAGINA_CHECAGEM_GEORREFERENCIAMENTO = Pagina(
    "Georreferenciamento do Modelo (BIM + GIS)",
    "paginas/checagens/checagem_georreferenciamento.py",
    icone=":material/public:", larga=True)
PAGINA_CHECAGEM_PROGRAMA = Pagina(
    "Programa de Necessidades (BIM)", "paginas/checagens/checagem_programa.py",
    icone=":material/checklist:", larga=True)
PAGINA_CHECAGEM_BIM_GIS = Pagina(
    "Requisitos de Projeto (BIM + GIS)", "paginas/checagens/checagem_bim_gis.py",
    icone=":material/hub:", larga=True)
PAGINA_RELATORIO = Pagina(
    "Relatório do requisito", "paginas/relatorios/relatorio.py", larga=True)

_DADOS_EMPREENDIMENTO = Grupo("Dados do Empreendimento", icone=":material/domain:", paginas=(
    PAGINA_INFORMACOES_GERAIS,
    # Era `grupos_requisitos.py`, oculta (decisão adiada inicialmente). O
    # autor decidiu dar-lhe um lugar definitivo aqui em vez de esperar: é o
    # requisito por empreendimento, não uma página de pesquisa — o arquivo
    # em si não mudou de lugar em disco nem de conteúdo, só de posição na
    # árvore e de rótulo.
    Pagina("Requisitos a serem validados",
           "paginas/pesquisa/grupos_requisitos.py",
           icone=":material/list_alt:", larga=True),
))

_FASE1_ENQUADRAMENTO = Grupo("Fase 1: Enquadramento", icone=":material/looks_one:", paginas=(
    PAGINA_CHECAGEM_ENQUADRAMENTO,
))

# A Qualificação urbanística abre a Fase 2: é
# Anexo II, como as demais, mas não exige modelo — só o município e as UH
# declaradas em Informações Gerais.
_FASE2_ANALISE = Grupo("Fase 2: Análise do Empreendimento", icone=":material/looks_two:", paginas=(
    PAGINA_CHECAGEM_QUALIFICACAO,
    PAGINA_CHECAGEM_GEORREFERENCIAMENTO,
    PAGINA_CHECAGEM_PROGRAMA,
    PAGINA_CHECAGEM_BIM_GIS,
))

# ADR-010: as duas telas deixam de ser placeholder e passam a ser
# referenciadas por outro código (o "Voltar" do relatório de requisito
# aberto a partir de 2.4.2 usa PAGINA_RELATORIO_CHECAGEM como origem) —
# por isso, como as demais páginas citadas fora deste módulo, ganham nome
# próprio em vez de ficarem só dentro da tupla do grupo.
PAGINA_RESULTADOS = Pagina(
    "Cobertura do Protótipo", "paginas/checagens/resultados.py",
    icone=":material/monitoring:", larga=True)
PAGINA_RELATORIO_CHECAGEM = Pagina(
    "Relatório de Checagem", "paginas/checagens/relatorio_checagem.py",
    icone=":material/summarize:", larga=True)

_RESULTADOS = Grupo("Resultados", icone=":material/insights:", paginas=(
    PAGINA_RESULTADOS,
    PAGINA_RELATORIO_CHECAGEM,
))

SECAO_CHECAGENS = Secao("Checagens do Protótipo", (
    _DADOS_EMPREENDIMENTO, _FASE1_ENQUADRAMENTO, _FASE2_ANALISE, _RESULTADOS,
), icone=":material/rule:")

ARVORE: tuple[Secao, ...] = (SECAO_PESQUISA, SECAO_CHECAGENS)

# Páginas que existem e continuam navegáveis por `st.switch_page`, mas não
# aparecem no menu lateral — o mesmo padrão que `main.py` já usava para os
# dois relatórios antes da Fase 2, formalizado aqui como dado.
OCULTAS: tuple[Pagina, ...] = (
    PAGINA_RELATORIO,
)


def todas_as_paginas() -> list[Pagina]:
    """Toda folha da árvore, na ordem do menu, seguida das ocultas."""
    paginas: list[Pagina] = []
    for secao in ARVORE:
        for grupo in secao.grupos:
            paginas.extend(grupo.paginas)
    paginas.extend(OCULTAS)
    return paginas
