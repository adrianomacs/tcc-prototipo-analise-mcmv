"""Card do empreendimento (ADR-004; forma do ADR-034 (d)).

As checagens não têm formulário próprio de UF/Município — quem declara isso é
a página 2.1.1 (`informacoes_gerais.py`). Este componente é o que elas mostram
no lugar, logo abaixo de "O que esta checagem verifica": o empreendimento em
prosa, num card destacado, com o link para a 2.1.1. A própria 2.1.1 mostra o
mesmo card, sem o link, para o proponente ver se está declarando um
empreendimento coerente.

A frase lê a composição declarada (ADR-023) e só a aritmética que
`Empreendimento` já expõe; a inconsistência declaradas × previstas não entra
nela — é aviso à parte, e só informação, nunca veredito (ADR-033).
"""

from __future__ import annotations

from html import escape

import streamlit as st

from app.componentes import avisos
from app.componentes import layout as _layout
from app.navegacao.arvore import PAGINA_INFORMACOES_GERAIS
from app.servicos import declaracoes as dec
from app.servicos.empreendimento import Empreendimento

_PLURAL_TIPOLOGIA = {dec.CASA: "casas", dec.APARTAMENTO: "apartamentos"}
_MAX_EDIFICACOES_LISTADAS = 3

# Ícone de casa (Material Symbols "home_work", traçado simplificado) em SVG
# inline: o card é HTML, e o atalho ``:material/...:`` do Streamlit não vale
# dentro de ``unsafe_allow_html``.
_ICONE_CASA = (
    "<svg width='26' height='26' viewBox='0 0 24 24' aria-hidden='true' "
    "style='flex:0 0 auto;margin-top:2px'><path fill='{cor}' d='M12 3 2 11h3v9h"
    "5v-6h4v6h5v-9h3L12 3Z'/></svg>")


def _enumerar(itens: list[str]) -> str:
    """"A", "A e B", "A, B e C" — a enumeração do português."""
    if len(itens) <= 1:
        return "".join(itens)
    return ", ".join(itens[:-1]) + " e " + itens[-1]


def _uhs(n: int) -> str:
    return f"{n} UH" if n == 1 else f"{n} UHs"


def _edificacoes(edificacoes: list) -> str:
    """Até três pelo nome, cada uma com as UHs que compõe; mais que isso, a
    contagem com o intervalo (ADR-034 (d)) — a frase é lida, não auditada."""
    nomes = [e.nome for e in edificacoes]
    if len(edificacoes) > _MAX_EDIFICACOES_LISTADAS:
        return (f"dividido em {len(edificacoes)} edificações "
                f"({nomes[0]} a {nomes[-1]})")
    itens = [f"{e.nome} ({_uhs(e.unidades_compostas)})" if e.unidades_compostas
             else e.nome for e in edificacoes]
    if len(itens) == 1:
        return f"dividido na edificação {itens[0]}"
    return f"dividido nas edificações {_enumerar(itens)}"


def frase_do_empreendimento(empreendimento: Empreendimento) -> str:
    """O empreendimento em prosa, montado só do que foi declarado (ADR-034 (d)).

    Um padrão único, que vai recebendo as declarações e omite o que falta —
    nunca inventa. A única variação é **condomínio × loteamento**, que muda a
    forma de distribuição (loteamento não lista edificações). O total de UHs é
    ``unidades_previstas``, o número da proposta (ADR-028). O que se repete é
    nomeado **unidade tipo**, nunca "tipologia": no domínio, tipologia é casa
    × apartamento (ADR-023), e a tela fala a mesma língua. Devolve ``""``
    quando não há nada declarado — quem chama decide o que mostrar.
    """
    emp = empreendimento
    loc = emp.localizacao
    arranjo = emp.declaracoes.get(dec.ARRANJO)
    previstas = emp.unidades_previstas
    tipologias = sorted({u.tipologia for u in emp.unidades_tipo
                         if u.tipologia in _PLURAL_TIPOLOGIA})
    habitacoes = _enumerar([_PLURAL_TIPOLOGIA[t] for t in tipologias])
    tipos = [u.nome for u in emp.unidades_tipo if u.nome]
    edificacoes = [e for e in emp.edificacoes if e.nome]

    if arranjo == dec.LOTEAMENTO:
        predicado = "é um loteamento"
        if previstas:
            predicado += f" de {_uhs(previstas)}"
        if habitacoes:
            predicado += f" em {habitacoes}"
    elif arranjo == dec.CONDOMINIO:
        predicado = "é um condomínio"
        if habitacoes:
            predicado += f" de {habitacoes}"
        if previstas:
            predicado += f" que totaliza {_uhs(previstas)}"
    elif previstas:
        predicado = f"totaliza {_uhs(previstas)}"
        if habitacoes:
            predicado += f" em {habitacoes}"
    elif habitacoes:
        predicado = f"é composto de {habitacoes}"
    else:
        predicado = ""

    complementos = []
    if edificacoes and arranjo != dec.LOTEAMENTO:
        complementos.append(_edificacoes(edificacoes))
    if tipos:
        complementos.append(("com a unidade tipo " if len(tipos) == 1
                             else "com as unidades tipo ") + _enumerar(tipos))

    if not (emp.nome or loc or predicado or complementos):
        return ""
    frase = "O empreendimento analisado"
    if emp.nome:
        frase += f", o {emp.nome},"
    verbos = []
    if loc is not None:
        verbos.append(f"está situado em {loc.municipio}/{loc.uf}")
    if predicado:
        verbos.append(predicado)
    if verbos:
        frase += " " + " e ".join(verbos)
    elif emp.nome:
        frase = frase[:-1]          # sem verbo, a vírgula do aposto sobra
    if complementos:
        frase += ", " + ", ".join(complementos)
    return frase + "."


def montar_card(frase: str) -> str:
    """HTML do card: fundo e ícone no azul-petróleo da identidade visual, que
    não é cor de nenhuma caixa de aviso nem de estado (ADR-034 (c))."""
    cor = _layout.COR_DESTAQUE
    return (
        f"<div style='display:flex;gap:.8rem;align-items:flex-start;"
        f"padding:.85rem 1.1rem;border-radius:8px;background:{cor}14;"
        f"border:1px solid {cor}55;line-height:1.5;"
        f"margin-bottom:1.1rem'>"
        + _ICONE_CASA.format(cor=cor)
        + f"<div>{escape(frase)}</div></div>")


def card_do_empreendimento(empreendimento: Empreendimento, *,
                           com_link: bool = True) -> None:
    """O card destacado; ``com_link`` põe ao lado o botão para a 2.1.1.

    `st.button` + `st.switch_page`, e não `st.page_link`: este valida a
    navegação no momento do render e lança fora de `st.navigation` (o teste
    de página isolada); o botão só resolve o caminho ao ser clicado."""
    frase = frase_do_empreendimento(empreendimento)
    if not frase:
        st.info("Nenhum empreendimento definido ainda. Preencha "
                "**Informações Gerais** (UF, Município, implantação e "
                "composição) antes de analisar.", icon=":material/domain:")
    if com_link:
        col_card, col_link = st.columns([5, 1.1], vertical_alignment="center")
    else:
        col_card, col_link = st.container(), None
    with col_card:
        if frase:
            st.markdown(montar_card(frase), unsafe_allow_html=True)
            _aviso_de_inconsistencia(empreendimento, com_link=com_link)
    if col_link is not None:
        with col_link:
            if st.button("Editar", icon=":material/edit:",
                         key="editar_empreendimento", use_container_width=True):
                st.switch_page(PAGINA_INFORMACOES_GERAIS.caminho)


def cabecalho_empreendimento(empreendimento: Empreendimento) -> None:
    """O card com o link para a 2.1.1 — o que toda checagem mostra no topo."""
    card_do_empreendimento(empreendimento, com_link=True)


def aviso_de_inconsistencia(empreendimento: Empreendimento, *,
                            com_link: bool = True) -> avisos.Aviso | None:
    """As duas aritméticas do ADR-022 que não fecham, como ALERTA sob o card.

    É ``warning`` e não ``error`` (ADR-034 (c)): a página segue, mas o dado é
    incoerente e o limite de UHs (EMP-025.1, ADR-028) sai não avaliável com o
    motivo ``inconsistencia_declaratoria``. Um card em destaque, e não uma legenda
    cinza fácil de não ver (ADR-034 (c)). Função pura, para o
    teste montar o texto sem ``AppTest``; ``None`` quando os números fecham."""
    if empreendimento.declaracao_consistente:
        return None
    partes = []
    excedente = empreendimento.excedente_declarado
    if excedente:
        partes.append(
            f"as unidades tipo somam {empreendimento.unidades_declaradas} UHs, "
            f"{excedente} a mais que as {empreendimento.unidades_previstas} "
            "previstas")
    for u in empreendimento.unidades_tipo:
        if empreendimento.excedente_composto(u):
            partes.append(
                f"as edificações somam {empreendimento.unidades_compostas(u)} "
                f"UHs da unidade tipo {u.nome or u.id}, que declara "
                f"{u.unidades}")
    texto = "; ".join(partes)
    return avisos.Aviso(
        avisos.ALERTA, "Os números de UHs declarados não fecham.",
        texto[:1].upper() + texto[1:] + ". Enquanto isso, o limite de UHs "
        "por empreendimento não pode ser verificado.",
        "Corrija em Informações Gerais." if com_link
        else "Corrija as quantidades abaixo.")


def aviso_de_cobertura_declarada(empreendimento: Empreendimento
                                 ) -> avisos.Aviso | None:
    """Unidades tipo que cobrem MENOS UHs do que as previstas, como ORIENTAÇÃO.

    Não é o ADR-022: declarar a menos não contradiz nada, só deixa UHs fora do
    alcance das regras que julgam a unidade tipo (Programa, absortância) — o
    "conforme" delas vale para as declaradas. Por isso é ``info``, sem motivo
    de não avaliável e sem mudar veredito (ADR-034 (c)). Só com previsão e ao
    menos uma unidade tipo declaradas; a soma das edificações não entra, porque
    declará-las é opcional."""
    previstas = empreendimento.unidades_previstas
    declaradas = empreendimento.unidades_declaradas
    if not previstas or not declaradas or declaradas >= previstas:
        return None
    return avisos.Aviso(
        avisos.ORIENTACAO,
        f"As unidades tipo cobrem {declaradas} das {previstas} UHs previstas.",
        "Os resultados das checagens valem só para as unidades declaradas.",
        "Declare as demais unidades tipo se fizerem parte da proposta.")


def _aviso_de_inconsistencia(empreendimento: Empreendimento, *,
                             com_link: bool = True) -> None:
    aviso = (aviso_de_inconsistencia(empreendimento, com_link=com_link)
             or aviso_de_cobertura_declarada(empreendimento))
    if aviso is not None:
        avisos.mostrar_aviso(aviso)
