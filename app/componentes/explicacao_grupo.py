"""Seção explicativa do grupo de requisitos: o que ele verifica e a tabela de
verificações que o compõem.

Extraído de `_checagem_comum.py`.
"""

from __future__ import annotations

import streamlit as st

from app.servicos.grupos import (Grupo, membros_de_agregacao, regra_do_grupo,
                                 regras_registradas)

APLICACAO_ROTULO = {
    "ambas": "Unifamiliar e multifamiliar",
    "unifamiliar": "Unifamiliar (casa)",
    "multifamiliar": "Multifamiliar (apto. / casa sobreposta)",
    "todas": "Todas as naturezas de modelo",
}


def explicacao_grupo(grupo: Grupo, em_expander: bool = False,
                     mostrar_situacao: bool = True) -> None:
    """Seção explicativa: o que o grupo verifica e as verificações que o compõem.

    ``em_expander`` recolhe o bloco num expander retraído (mantém o formulário
    de inputs no alto da página); ``mostrar_situacao`` controla a coluna de
    situação (implementada / em implementação) na tabela.
    """
    if em_expander:
        with st.expander(f"O que esta checagem verifica "
                         f"({len(grupo.regras)} verificações)", expanded=False,
                         icon=":material/info:"):
            _corpo_explicacao(grupo, mostrar_situacao)
    else:
        _corpo_explicacao(grupo, mostrar_situacao)


def explicacao_requisito(rid: str, descricao: str = "") -> None:
    """Expander recolhido "O que esta regra verifica", logo abaixo do voltar
    no relatório de um requisito (ADR-034, U2.1): a descrição, o parâmetro e
    a aplicação, tal como a tabela do grupo os declara."""
    achado = regra_do_grupo(rid)
    with st.expander("O que esta regra verifica", expanded=False,
                     icon=":material/info:"):
        if descricao:
            st.write(descricao)
        if achado is None:
            return
        grupo, regra = achado
        linhas = [f"**{regra.id}** — {regra.rotulo}" if regra.rotulo else f"**{regra.id}**"]
        if regra.parametro:
            linhas.append(f"**Parâmetro:** {regra.parametro}")
        linhas.append("**Aplicação:** "
                      + APLICACAO_ROTULO.get(regra.aplicabilidade, regra.aplicabilidade))
        linhas.append(f"**Checagem:** {grupo.rotulo}")
        st.markdown("  \n".join(linhas))


def _minusculo(rotulo: str) -> str:
    return rotulo[:1].lower() + rotulo[1:]


def resumo_da_execucao(grupo: Grupo, executaveis: list[str],
                       membros: set[str] | None = None) -> str:
    """A linha ao lado do botão Analisar (ADR-034, seção 2): os **requisitos**
    que serão verificados, pelo rótulo, sem ids (estes ficam no expander "O
    que esta checagem verifica").

    A unidade é o requisito da Portaria, a mesma do relatório: a alternativa
    ou o ramo de uma agregação (``membros``) não aparece à parte — o pai o
    consome. ``membros`` vem do registro por padrão; o teste o passa pronto."""
    membros = membros_de_agregacao() if membros is None else membros
    rotulos = {r.id: r.rotulo for r in grupo.regras}
    itens = [_minusculo(rotulos.get(rid) or rid)
             for rid in executaveis if rid not in membros]
    if not itens:
        return ""
    return "**Ao analisar, o protótipo verifica:** " + "; ".join(itens) + "."


_POR_QUE_FORA = {
    "unifamiliar": "aplica-se só a casas",
    "multifamiliar": "aplica-se só a apartamentos e casas sobrepostas",
}


def requisitos_do_grupo(grupo: Grupo, membros: set[str] | None = None) -> list:
    """As linhas do grupo que são requisitos (não membros de agregação)."""
    membros = membros_de_agregacao() if membros is None else membros
    return [r for r in grupo.regras if r.id not in membros]


def legenda_fora_da_analise(grupo: Grupo, executaveis: list[str],
                            membros: set[str] | None = None) -> str:
    """A legenda sob as métricas de cobertura (ADR-034, seção 2): quais
    requisitos do grupo ficam fora desta análise, pelo rótulo, e por quê
    quando a razão é a tipologia. Vazia quando todos entram."""
    fora = [r for r in requisitos_do_grupo(grupo, membros)
            if r.id not in set(executaveis)]
    if not fora:
        return ""
    itens = []
    for r in fora:
        motivo = _POR_QUE_FORA.get(r.aplicabilidade)
        rotulo = _minusculo(r.rotulo or r.id)
        itens.append(f"{rotulo} ({motivo})" if motivo else rotulo)
    return "**Fora desta análise:** " + "; ".join(itens) + "."


def cobertura(grupo: Grupo, executaveis: list[str]) -> None:
    """As métricas da seção 2 (ADR-034) e a legenda do que ficou de fora,
    contadas em **requisitos da Portaria** — a unidade do relatório (a mesma
    de 2.4.x). Antes contavam linhas de regra, e o Enquadramento mostrava 7
    "verificações" para 3 requisitos."""
    membros = membros_de_agregacao()
    requisitos = requisitos_do_grupo(grupo, membros)
    avaliaveis = [rid for rid in executaveis if rid not in membros]
    c1, c2 = st.columns(2)
    c1.metric("Requisitos do grupo", len(requisitos))
    c2.metric("Avaliáveis com o insumo atual", len(avaliaveis))
    if executaveis:
        legenda = legenda_fora_da_analise(grupo, executaveis, membros)
        if legenda:
            st.caption(legenda)


def _corpo_explicacao(grupo: Grupo, mostrar_situacao: bool) -> None:
    st.write(grupo.descricao)

    registradas = regras_registradas()
    if mostrar_situacao:
        linhas = ["| Verificação | Parâmetro | Aplicação | Situação |",
                  "|---|---|---|---|"]
    else:
        linhas = ["| Verificação | Parâmetro | Aplicação |", "|---|---|---|"]
    for r in grupo.regras:
        aplic = APLICACAO_ROTULO.get(r.aplicabilidade, r.aplicabilidade)
        celulas = [f"**{r.id}** — {r.rotulo}", r.parametro, aplic]
        if mostrar_situacao:
            celulas.append(_situacao(registradas.get(r.id)))
        linhas.append("| " + " | ".join(celulas) + " |")
    st.markdown("\n".join(linhas))
    st.caption("A checagem considera o grupo em bloco: verificações ainda em "
               "implementação, ou não aplicáveis às declarações do projeto, "
               "ficam fora da execução. Verificação **remetida a parecer** é "
               "executada e sai sempre como NÃO AVALIÁVEL, declarando a causa: "
               "o insumo que ela exigiria não é dado público, e nenhuma versão "
               "futura da ferramenta a automatiza.")


def _situacao(cls) -> str:
    """Situação da verificação na tabela do grupo — três valores, não dois.

    "Implementada" para uma regra que nunca produz veredito seria verdadeiro e
    enganoso ao mesmo tempo, que é a pior combinação: a coluna diria que a
    ferramenta avalia o requisito, e ela não avalia. O terceiro valor vem de
    ``Regra.remete_a``, declarado **pela própria regra** — uma lista de ids aqui
    na tela envelheceria em silêncio, do mesmo modo que uma legenda de critério
    de aceite reescrita à mão (ver ``_distancia_equipamento.CRITERIO_ACEITE``).
    """
    if cls is None:
        return "Em implementação"
    if getattr(cls, "remete_a", ""):
        from app.servicos import motivos

        alvo = {motivos.VERIFICACAO_EM_CAMPO: "vistoria",
                motivos.ANALISE_HUMANA_DOCUMENTAL: "parecer do analista"}.get(
                    cls.remete_a, "análise humana")
        return f"Não automatizável — remetida a {alvo}"
    return "Implementada"
