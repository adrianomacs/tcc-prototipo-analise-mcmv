"""Metodologia — 1.2.1. O mapa do método: o enquadramento da pesquisa e os
seis passos, cada um remetendo à página que o detalha, com cada linha
alinhada ao Material e Métodos. Fica enxuta de
propósito, sem a classificação da pesquisa. Página de
pesquisa: largura total (ADR-034)."""

import streamlit as st

st.write(
    "A pesquisa tem natureza aplicada e caráter exploratório. O procedimento "
    "adotado foi a pesquisa experimental na modalidade prova de conceito, em "
    "que um protótipo de software foi desenvolvido para avaliar, sobre um "
    "empreendimento real e mediante manipulação controlada da informação "
    "disponível, se a verificação "
    "automatizada de requisitos integrando BIM e GIS é tecnicamente viável. "
    "O trabalho seguiu seis passos, cada um com uma página de mesmo nome neste "
    "menu, e se encerra em Conclusões e Considerações."
)

st.markdown("""
| Passo | O que foi feito |
|---|---|
| **1. Análise, classificação e seleção dos requisitos** | A Portaria MCID nº 725/2023, na versão compilada, foi decomposta em requisitos verificáveis, cada um classificado pelo domínio de informação necessário à sua verificação (BIM, GIS, ambos ou análise humana). Dessa base se extraiu o recorte implementado no protótipo. |
| **2. Framework de análise** | A partir do processo de análise previsto na Portaria e dos ciclos de informação da ABNT NBR ISO 19650, desenhou-se um fluxo idealizado de informação, do enquadramento do terreno à análise do empreendimento e que considerasse o uso do protótipo. |
| **3. Arquitetura e desenvolvimento do protótipo** | A arquitetura foi definida segundo a Arquitetura Limpa e o Domain-Driven Design, sob quatro premissas fixadas antes da implementação, sobre ferramentas e padrões abertos e com o conteúdo normativo declarado fora do código, e o protótipo foi implementado até executar as regras do recorte e consolidar os seus resultados. |
| **4. Dados para os testes** | Para a análise do protótipo, foi utilizado um projeto real submetido ao programa, que dispunha de modelo BIM em formato aberto, situado no município de Estrela/RS. Do território foram levantadas, em bases públicas, as informações geoespaciais necessárias às checagens, e do material entregue foram produzidas as variantes que compõem os cenários de teste. |
| **5. Avaliação do protótipo** | Em cada cenário, com a informação disponível progressivamente ampliada, retirada ou apenas alterada na forma, mediram-se a capacidade de conclusão e a conformidade, comparando-se a mudança esperada com a mudança observada em relação ao cenário de que cada um parte. |
| **6. Desafios técnicos** | As dificuldades encontradas ao longo do desenvolvimento e dos cenários foram registradas e organizadas por tema, para delimitar o que a verificação automatizada consegue fazer hoje e o que precisaria mudar para que conseguisse mais. |
""")
