"""Visão Geral — 1.1.1. O problema, o contexto e o índice da seção "Trabalho
de Pesquisa". Página de pesquisa: largura total, sem card do
empreendimento (ADR-034). Texto neutro quanto a instituições: o programa é
público e a pesquisa, independente."""

import streamlit as st

st.write(
    "O Programa Minha Casa, Minha Vida (PMCMV) é a principal política "
    "habitacional do Governo Federal. Todo empreendimento proposto ao programa "
    "passa por uma análise de conformidade com a Portaria MCID nº 725/2023, "
    "que reúne as exigências de inserção urbana e as especificações técnicas "
    "do programa, desde a localização do terreno e a distância a escolas e "
    "outros equipamentos públicos até a área e os ambientes mínimos de cada "
    "unidade habitacional."
)

st.write(
    "Essa análise ainda é feita, em grande parte, de forma manual, sobre "
    "pranchas e memoriais. Parte do que a Portaria exige está dentro do "
    "projeto, como áreas, ambientes e dimensões, e parte está fora dele, no "
    "território, como o terreno, o entorno e os equipamentos próximos. Conferir as "
    "duas coisas consome tempo, depende da leitura de cada analista e deixa "
    "pouco registro de como cada requisito foi verificado."
)

st.write(
    "Este protótipo é o produto técnico de um Trabalho de Conclusão de Curso "
    "do MBA em Engenharia de Software (USP/ESALQ). O trabalho investiga se uma "
    "arquitetura de software modular, construída sobre padrões abertos, "
    "consegue cruzar o modelo BIM do empreendimento (em formato IFC) com dados "
    "geográficos (GIS) e verificar automaticamente um recorte representativo "
    "dos requisitos da Portaria. O caso estudado é um empreendimento real "
    "submetido ao programa."
)

st.write(
    "O protótipo mostrou que é viável automatizar conjuntos de regras da "
    "Portaria e que a ferramenta pode funcionar como apoio à decisão dos "
    "profissionais técnicos que analisam os empreendimentos submetidos, sem "
    "substituir o seu parecer. Esse avanço depende, porém, de algo anterior à "
    "tecnologia, que são padrões e requisitos de informação bem estabelecidos para os "
    "projetos e demais insumos entregues à análise. O trabalho detalha e amplia "
    "essa discussão nas seções a seguir."
)

st.markdown("""
| Página | O que traz |
|---|---|
| Metodologia | Os seis passos da pesquisa e onde cada um é detalhado |
| Análise, Classificação e Seleção dos Requisitos | A base de requisitos extraída da Portaria e o recorte verificado pelo protótipo |
| Framework de Análise | O fluxo de análise ideal, do enquadramento do terreno ao relatório |
| Arquitetura e Desenvolvimento do Protótipo | A arquitetura do software, a pilha técnica e o método de desenvolvimento |
| Dados para os Testes | O estudo de caso e as bases públicas consumidas |
| Avaliação do Protótipo | Como se mede o que o protótipo consegue concluir, e o que ele concluiu |
| Desafios Técnicos | As dificuldades da integração BIM-GIS e quem pode removê-las |
| Conclusões e Considerações | O que o trabalho conclui e o que fica como continuação |
| Referências | A bibliografia do trabalho |
""")

