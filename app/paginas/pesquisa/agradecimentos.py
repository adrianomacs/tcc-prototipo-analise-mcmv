"""Agradecimentos — 1.1.2. Texto do autor, do pessoal ao institucional. Página de pesquisa: largura total
(ADR-034)."""

import streamlit as st

from app.componentes import layout as _layout

st.write(
    "Agradeço, primeiramente, à minha família, pelo apoio e pela formação que "
    "me deram ao longo de tantos anos de estudo. De forma especial, à minha "
    "esposa, que conviveu com a luz do meu monitor acesa em nosso quarto "
    "durante os dias de elaboração deste trabalho."
)

st.write(
    f"Ao meu orientador, Prof. {_layout.DEV_ORIENTADOR}, pela orientação e "
    "pela leitura crítica ao longo de toda a pesquisa."
)

st.write(
    "À CAIXA, instituição que incentiva a formação de seus colaboradores e "
    "que me permitiu ingressar nesta especialização em Engenharia de Software."
)

st.write(
    "À TELESIL, que prontamente se dispôs a fornecer os materiais e os "
    "modelos de informação necessários para a realização desta pesquisa."
)

st.markdown(
    "*Que o trabalho aqui desenvolvido possa, de alguma forma, contribuir "
    "para o propósito de transformar a vida das pessoas por meio da moradia "
    "digna a quem mais precisa.*"
)
