"""Sobre — 1.1.3. Autoria e contato, com convite à colaboração. A pilha
técnica mora em "Desenvolvimento do Protótipo"; aqui, só quem fez e como
falar com o autor. Página de pesquisa: largura total (ADR-034)."""

import streamlit as st

from app.componentes import layout as _layout

st.subheader("Autoria")
st.write(
    f"Este protótipo foi desenvolvido por **{_layout.DEV_NOME}**, engenheiro "
    f"civil especialista em BIM, sob orientação do Prof. "
    f"{_layout.DEV_ORIENTADOR}, como produto técnico do Trabalho de Conclusão "
    f"de Curso do {_layout.DEV_CURSO} da {_layout.DEV_INSTITUICAO}, em "
    f"{_layout.DEV_ANO}."
)

st.subheader("Contato e colaboração")
st.write(
    "Sugestões, críticas, relatos de uso e propostas de colaboração são "
    "bem-vindos, sobretudo de quem trabalha com análise de empreendimentos "
    "habitacionais, BIM ou dados geoespaciais. O protótipo foi estruturado "
    "para crescer, já que cada requisito é um módulo próprio e a base completa "
    "de requisitos da Portaria está documentada, de modo que novas regras, novas "
    "fontes de dados e outros estudos de caso podem ser acrescentados sem "
    "refazer o que já existe."
)
st.write(
    "Para falar com o autor, escreva para adrianomacs@gmail.com. No "
    "repositório, é possível abrir *issues* para relatar problemas ou sugerir "
    "melhorias e enviar *pull requests* para contribuir com código ou "
    "documentação."
)

st.caption(
    "Protótipo acadêmico, desenvolvido de forma independente. Não é ferramenta "
    "oficial do programa nem de nenhuma instituição, e seus resultados não "
    "substituem a análise técnica dos profissionais responsáveis."
)
