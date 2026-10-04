"""Checagem — Qualificação Urbanística (GIS): o porte do empreendimento.

O cruzamento desta tela é **declaração × território**: o total de UH que o
proponente declarou para o empreendimento (ADR-028) contra o limite que o porte
populacional do município impõe (Anexo II, item 4.I.a). O porte vem do Censo
Demográfico 2022, derivado do município — nunca perguntado aqui (ADR-030).
Não há modelo IFC: é a primeira checagem da Fase 2, antes das que leem
geometria.

Anatomia do ADR-034: explicação do grupo, card do empreendimento, faixa de
avisos (o que falta em Informações Gerais) e as duas seções:

  1) **Informações de entrada** — o município e as UH previstas, em campos
     **não editáveis**: vêm só de Informações Gerais (o botão "Editar" do
     card leva até lá); a tela não tem campo de porte nem de população;
  2) **Cobertura e análise** — as métricas de cobertura, a linha "Ao
     analisar…" com o botão e o resultado (componente comum), com o acesso ao
     relatório do EMP-025. O painel do porte que ficava aqui saiu: repetia,
     item a item, o relatório do requisito (ADR-034).

A página não importa o núcleo (ADR-003) e se declara só em
``app/navegacao/arvore.py`` (ADR-010).

Execução: via ponto de entrada ``streamlit run app/main.py``.
"""

from __future__ import annotations

import streamlit as st

from app.componentes import acao as acao_mod
from app.componentes import avisos
from app.componentes.campos import campo_somente_leitura
from app.componentes import explicacao_grupo as explicacao_mod
from app.componentes.cabecalho_empreendimento import cabecalho_empreendimento
from app.estado import chaves
from app.navegacao import arvore
from app.servicos import analise, grupos
from app.servicos import empreendimento as emp_mod

# CHAVE: artefatos/relatorios/<chave>.json (ADR-001); GRUPO_ID: o id em
# config/grupos_requisitos.yaml.
CHAVE = "qualificacao"
GRUPO_ID = "qualificacao_urbanistica"
ORIGEM = arvore.PAGINA_CHECAGEM_QUALIFICACAO


def _empreendimento_corrente():
    guardado = st.session_state.get(chaves.EMPREENDIMENTO)
    if guardado is not None:
        return guardado
    carregado = emp_mod.carregar()
    st.session_state[chaves.EMPREENDIMENTO] = carregado
    return carregado


def main() -> None:
    grupo = grupos.carregar_grupo(GRUPO_ID)
    if grupo is None:
        st.error(f"Grupo '{GRUPO_ID}' não encontrado em "
                 "config/grupos_requisitos.yaml.")
        return

    explicacao_mod.explicacao_grupo(grupo, em_expander=True, mostrar_situacao=False)

    emp = _empreendimento_corrente()
    cabecalho_empreendimento(emp)
    avisos.faixa_de_avisos(_avisos(emp))

    st.subheader("Informações de entrada")
    _entrada(emp)

    st.divider()
    st.subheader("Cobertura e análise")
    declaracoes = analise.declaracoes_da_analise(emp, {})
    executaveis = grupos.ids_executaveis(grupo, declaracoes)
    explicacao_mod.cobertura(grupo, executaveis)
    acao_mod.acao_sem_ifc(CHAVE, grupo, declaracoes, ORIGEM, emp,
                          com_rede=False,
                          espera="Conferindo o porte do empreendimento…",
                          referencia="ao município e às UH",
                          resumo_execucao=explicacao_mod.resumo_da_execucao(
                              grupo, executaveis))


def _avisos(emp) -> list[avisos.Aviso | None]:
    """O que falta em Informações Gerais, dito antes, na faixa (ADR-034 (c)) —
    avisa, não bloqueia: a regra sai NÃO AVALIÁVEL com a causa registrada, e é
    essa a resposta."""
    return [
        None if emp.codigo_ibge else avisos.Aviso(
            avisos.ALERTA, "Município ainda não declarado.",
            "O porte do município define o limite de UHs; sem ele, o limite "
            "não pode ser escolhido.",
            "Declare-o em Informações Gerais."),
        None if emp.unidades_previstas else avisos.Aviso(
            avisos.ALERTA, "UH previstas ainda não declaradas.",
            "É esse o número comparado com o limite.",
            "Declare-as em Informações Gerais."),
    ]


def _entrada(emp) -> None:
    """Seção 1 (ADR-034): a entrada que a regra consome, em campo não
    editável — o usuário vê com o que ela vai rodar; o lugar de mudar é
    Informações Gerais (botão "Editar" do card)."""
    loc = emp.localizacao
    municipio = f"{loc.municipio}/{loc.uf}" if loc is not None else None
    c1, c2 = st.columns(2)
    with c1:
        campo_somente_leitura("Município", municipio, chave="qualif_municipio",
                              ajuda="Declarado em Informações Gerais.")
    with c2:
        campo_somente_leitura("UH previstas para o empreendimento",
                              emp.unidades_previstas or None,
                              chave="qualif_previstas",
                              ajuda="Declaradas em Informações Gerais.")
    st.caption("A população vem do Censo 2022, pelo município; não é "
               "declarada pelo proponente.")


main()
