"""Framework de Análise — 1.2.3. Versão estendida do Passo 2 do método,
na mesma ordem: o contraste entre o processo atual e o fluxo
idealizado (em colunas comparáveis), os ciclos de informação da
ABNT NBR ISO 19650, as duas fases, o IDS fora da ferramenta (ADR-007) e os
quatro blocos do protótipo na Figura 1. Cita caminhos do repositório só onde
ajudam, sem citar ADR na tela (ADR-034, emenda das páginas de pesquisa). A
figura em raias é gerada por
`scripts/gerar_figura1.py` (ver docs/figuras/README.md); a página só lê o SVG,
não o desenha, e o mostra a três quartos da largura."""

import os

import streamlit as st

# Raiz do repositório medida a partir deste arquivo (app/paginas/pesquisa/),
# como em app/componentes/cena3d.py, para não depender do diretório de onde o
# Streamlit foi lançado.
_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
_FIGURA_1 = os.path.join(_RAIZ, "docs", "figuras", "figura1_fluxo_idealizado.svg")

st.write(
    'Esta página apresenta o fluxo de informações pensado para que a '
    'análise de um empreendimento, feita hoje sobre pranchas, memoriais e '
    'documentos, possa ser apoiada por uma ferramenta de verificação '
    'automatizada. O objetivo do processo continua exatamente o mesmo, '
    'analisar o empreendimento proposto à luz da Portaria, mas, para que '
    'parte das checagens possa ser automatizada, os insumos passam a ter de'
    ' chegar em formatos que a máquina consegue ler e manipular. A tabela '
    'abaixo contrasta as duas situações.'
)

st.markdown("""
| | Hoje | No fluxo idealizado |
|---|---|---|
| **Insumos** | Pranchas, planilhas, memoriais e documentos tipicamente disponibilizados em PDF | Modelo BIM em IFC, poligonal georreferenciada do terreno e dados declarados do empreendimento |
| **Contexto do terreno** | Levantado caso a caso pelo analista, com vistoria in loco | Cruzado automaticamente com bases públicas |
| **Verificação** | Manual, requisito a requisito | Automática para o que é verificável, com o motivo declarado quando não é |
| **Registro** | Disperso no parecer | Relatório com cada requisito, o dado consumido e o resultado |
| **Papel do analista** | Conferir tudo | Conferir o relatório, tratar as pendências e decidir |
""")

st.write(
    'O fluxo idealizado se apoia, além das determinações da Portaria, nos '
    '**ciclos de informação** da ABNT NBR ISO 19650, que estruturam a '
    'gestão da informação a partir da relação entre a parte contratante, '
    'que especifica os seus requisitos de informação, e a parte contratada,'
    ' que produz e entrega os contêineres de informação. No PMCMV, quem '
    'analisa e contrata ocupa o papel de parte contratante, e o proponente,'
    ' o de parte contratada. Hoje não existem requisitos de informação de '
    'projeto formalmente definidos para os modelos do programa, e portanto '
    'não há diretrizes de modelagem que padronizem o conteúdo dos modelos '
    'BIM entregues, lacuna que a pesquisa busca compreender melhor e para '
    'cuja superação pretende oferecer subsídios.'
)

_, _meio, _ = st.columns([1, 6, 1])
with _meio:
    if os.path.isfile(_FIGURA_1):
        st.image(_FIGURA_1, width="stretch")
    else:
        st.warning(
            "A figura do fluxo idealizado não foi encontrada. Para gerá-la, "
            "rode `python scripts/gerar_figura1.py` na raiz do projeto.",
            icon=":material/schema:",
        )
    st.caption(
        "Figura 1. Fluxo idealizado para as fases de enquadramento do terreno "
        "e de análise do empreendimento"
    )
    st.caption("Fonte: Resultados originais da pesquisa")

st.write(
    'O processo gira em torno do **empreendimento**, objeto ao qual toda '
    'regra se aplica. A primeira fase, o **enquadramento do terreno**, '
    'estabelece a localização do empreendimento e avalia o seu acesso a '
    'infraestrutura e serviços. O insumo principal é a poligonal do '
    'terreno, obtida da matrícula do imóvel, do projeto de implantação ou '
    'de levantamento planialtimétrico, e o fluxo idealizado a admite em '
    'formatos tabulares e cartográficos típicos, como CSV, Shapefile e '
    'GeoJSON, ou como modelo IFC do terreno (buildingSMART Australasia, '
    '2020). No protótipo, ela pode ser desenhada no mapa, importada de um '
    'CSV com os vértices do memorial descritivo, no modelo que a própria '
    'tela oferece para download (`config/modelo_memorial_descritivo.csv`), '
    'ou lida de um modelo IFC, e na falta dela o centro do terreno pode ser'
    ' marcado no mapa. Sobre a poligonal, o contexto geográfico é cruzado '
    'com bases públicas para classificar a qualificação do terreno, mínima '
    'ou superior, conforme o regramento do programa, etapa em que fica '
    'evidente a dependência de bases de dados capazes de alimentar a '
    'análise.'
)

st.write(
    'Aprovado o enquadramento, a proposta avança para a **análise do '
    'empreendimento**, em que os insumos passam a ser os modelos BIM e o '
    '**IDS** ganha papel relevante. Publicados os requisitos de informação '
    'em formato aberto (buildingSMART International, 2024), o próprio '
    'proponente consome o IDS e valida o modelo antes de submetê-lo, e o '
    'IDS funciona como um filtro anterior ao motor de regras, fora da '
    'ferramenta de verificação, como um acordo entre quem pede e quem '
    'entrega a informação, de modo que o que chega à análise já atende ao '
    'que foi pedido. No processo real, as duas fases são separadas pela '
    'portaria de seleção das propostas, marco que a Figura 1 situa na raia '
    'da parte contratante, e o protótipo representa as duas sem mecanismo '
    'que denote essa aprovação intermediária.'
)

st.write(
    'Na Figura 1, o protótipo aparece como um bloco único abaixo das raias,'
    ' que atende às duas fases e se organiza em **quatro etapas**, '
    'adaptadas dos quatro estágios que Eastman et al. (2009) formularam '
    'para um sistema de verificação automatizada de regras, a interpretação'
    ' e estruturação das regras, a preparação e ingestão de dados, a '
    'execução pelo motor de regras e a saída de dados. A primeira etapa é '
    'alimentada pela base de requisitos do Passo 1, guardada em '
    '`config/Base_Requisitos_Portaria_MCID_725.xlsx`, interpretação que '
    'permanece manual por depender do conhecimento do domínio (Solihin e '
    'Eastman, 2015), e a mesma base é a origem dos requisitos de informação'
    ' que a parte contratante publicaria como IDS. O proponente consome o '
    'IDS ao preparar os entregáveis BIM e alimenta a segunda etapa nas duas'
    ' fases, com a poligonal do terreno no enquadramento e com os modelos '
    'IFC e os dados declarados na análise, etapa que recebe ainda as '
    'informações das bases públicas. O IDS, como filtro, atesta que as '
    'informações existem e têm o tipo esperado, papel que Fischer et al. '
    '(2024) situam como pré-condição da verificação, e não como a '
    'verificação em si. A execução confronta valores de propriedades, '
    'geometria e parâmetros normativos, e a saída devolve ao analista o '
    'resultado de cada requisito, conforme, não conforme ou não avaliável, '
    'com as pendências retornando ao proponente e a decisão seguindo para a'
    ' parte contratante, a quem continuam cabendo a conferência e a '
    'decisão.'
)

st.write(
    'A partir desse fluxo, tornou-se possível traçar as necessidades que '
    'orientaram a arquitetura do protótipo, apresentada em Arquitetura e '
    'Desenvolvimento do Protótipo.'
)
