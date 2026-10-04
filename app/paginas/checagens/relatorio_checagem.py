"""Relatório de Checagem — 2.4.2: o texto descritivo das análises gravadas.

A 2.4.1 (Cobertura do Protótipo) tem os números e o acesso a cada relatório;
esta página tem o **texto**, no estilo de um parecer: montado de forma
determinística só dos relatórios em disco do empreendimento corrente
(ADR-001), sem modelo de linguagem e sem frase que não decorra de um
requisito verificado. Quem monta é `app.servicos.parecer.montar` (ADR-035);
a página só o desenha, na anatomia do ADR-034: título, "O que esta página
mostra", faixa de avisos, card de síntese e o texto. Não há card do
empreendimento: o texto abre com a mesma frase, e repeti-la seria redundante.
"""

import streamlit as st

from app.componentes import avisos
from app.componentes.cabecalho_empreendimento import frase_do_empreendimento
from app.componentes.card_verificacao import montar_card_grupo
from app.componentes.paineis import ROTULO_ESTADO
from app.servicos import empreendimento as emp_servico
from app.servicos import parecer as parecer_servico
from app.servicos import relatorios
from app.servicos.vereditos import (
    _veredito_geral,
    contagens_em_requisitos,
    explicacao_do_resultado,
)

# Estado de cada requisito na tabela da checagem: as cores do ADR-034 (c), na sintaxe
# de cor do Markdown do Streamlit (que não aceita hexadecimal).
_COR_NA_TABELA = {"conforme": "green", "nao_conforme": "red", "nao_avaliavel": "orange"}

_SEPARADOR_SHA = " — SHA-256 "
# Monoespaçado sem a cor do código em linha, que é verde e se leria como "conforme".
_ESTILO_SHA = "font-family:monospace;font-size:.85em;color:inherit;word-break:break-all"


def _celula(texto: str) -> str:
    return texto.replace("|", "\\|").replace("\n", " ")


def _celula_id(requisito: str) -> str:
    """O id do requisito não quebra no hífen nem no ponto ("ENQ-010.2")."""
    return f"<span style='white-space:nowrap'>{_celula(requisito)}</span>"


def _tabela_de_requisitos(bloco: parecer_servico.BlocoChecagem) -> None:
    """Os requisitos verificados pela checagem e o resultado de cada um, em
    tabela, no lugar da lista e das frases de resultado do parágrafo (ADR-035):
    são os mesmos requisitos da Portaria, com os mesmos campos, e a alternativa
    de agregação não ganha linha própria. O resultado vai em cor (ADR-034 (c))."""
    corpo = []
    for linha in bloco.linhas:
        # Espaço não separável: "Não conforme" não quebra a coluna em duas linhas.
        rotulo = ROTULO_ESTADO.get(linha.estado, str(linha.estado)).replace(" ", "\u00a0")
        cor = _COR_NA_TABELA.get(linha.estado)
        resultado = f":{cor}[**{rotulo}**]" if cor else rotulo
        corpo.append(f"| {_celula_id(linha.requisito)} | {_celula(linha.descricao)} "
                     f"| {resultado} | {_celula(linha.detalhe)} |")
    st.markdown("\n".join(["| Requisito | Descrição | Resultado | Detalhe |",
                           "|---|---|---|---|", *corpo]), unsafe_allow_html=True)


def _tabela_de_pendencias(grupo: parecer_servico.GrupoPendencia) -> None:
    """Os requisitos de uma pendência em tabela, no lugar dos bullets; a ação,
    que é a mesma para todos eles, fica na frase acima (ADR-035). O detalhe é o
    complemento que o parecer já monta para cada item."""
    corpo = []
    for item in grupo.itens:
        corpo.append(f"| {_celula_id(item.requisito)} "
                     f"| {_celula(_maiuscula(item.descricao))} "
                     f"| {_celula(_maiuscula(item.complemento))} |")
    st.markdown("\n".join(["| Requisito | Descrição | Detalhe |", "|---|---|---|", *corpo]),
                unsafe_allow_html=True)


def _maiuscula(texto: str) -> str:
    return texto[:1].upper() + texto[1:]


def _titulo_de_secao(titulo: str) -> None:
    st.subheader(titulo, divider="gray")


def _tabela_de_arquivos(linhas: tuple[str, ...]) -> None:
    """Nome e impressão digital em colunas; as palavras são as de cada linha de
    `Parecer.arquivos` (ADR-035), só repartidas, e o SHA-256 vai em fonte
    monoespaçada, para não se confundir com o nome."""
    corpo = []
    for linha in linhas:
        nome, achou, sha = linha.partition(_SEPARADOR_SHA)
        if not achou:
            nome, _sep, sha = linha.partition(" — ")
            celula = sha
        else:
            celula = f"<span style='{_ESTILO_SHA}'>{sha}</span>"
        corpo.append(f"| {nome} | {celula} |")
    st.markdown("\n".join(["| Arquivo | SHA-256 |", "|---|---|", *corpo]),
                unsafe_allow_html=True)


def _desenhar(p: parecer_servico.Parecer) -> None:
    """Os blocos do texto, com títulos de seção para a leitura na tela. As
    palavras são exatamente as de `Parecer.texto()` (ADR-035); muda só a
    marcação: seção em subtítulo com filete, nome de cada checagem em título
    próprio, os requisitos de cada checagem e o resultado em tabela, depois dos
    insumos em prosa, as pendências por destinatário em tabela, sob a frase da
    ação, e os arquivos em tabela (ADR-034)."""
    _titulo_de_secao("Síntese da análise")
    st.markdown(p.abertura)
    _titulo_de_secao("Resultado por checagem")
    blocos = {b.titulo: b for b in p.blocos}
    for titulo, paragrafo in p.checagens:
        st.markdown(f"#### {titulo}")
        bloco = blocos.get(titulo)
        if bloco is None or not bloco.linhas:
            st.markdown(paragrafo)
            continue
        st.markdown(bloco.introducao)
        _tabela_de_requisitos(bloco)
    if p.limites:
        _titulo_de_secao("Limites da análise")
        st.markdown("\n".join(f"- {linha}" for linha in p.limites))
    # Respiro maior antes da parte que o analista usa para agir.
    st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)
    _titulo_de_secao("Pendências")
    if not any(p.pendencias.values()):
        st.markdown("Nenhuma pendência decorre desta análise.")
    for dest, grupos in p.pendencias.items():
        if not grupos:
            continue
        st.markdown(f"**{parecer_servico.TITULO_DESTINATARIO[dest]}**")
        for g in grupos:
            st.markdown(g.acao)
            _tabela_de_pendencias(g)
    if p.arquivos:
        _titulo_de_secao("Arquivos analisados")
        _tabela_de_arquivos(p.arquivos)
    st.caption(p.nota)


emp = emp_servico.carregar()

with st.expander("O que esta página mostra", icon=":material/info:"):
    st.write("Um relatório descritivo das checagens já executadas para este "
             "empreendimento: o que foi analisado, com quais arquivos, o "
             "resultado de cada requisito, os limites da análise e as "
             "pendências, separadas por quem precisa agir. O texto é montado "
             "automaticamente a partir das análises gravadas — o mesmo "
             "resultado gera sempre o mesmo texto — e não substitui o parecer "
             "do analista. Os números e o acesso ao relatório de cada "
             "requisito estão em Cobertura do Protótipo.")

encontrados = relatorios.relatorios_do_empreendimento_corrente()

if not encontrados:
    st.info(
        "Nenhuma checagem foi executada para este empreendimento ainda "
        "(ou os relatórios gravados são de uma versão anterior dele). Rode "
        "ao menos uma das checagens em “Checagens do Protótipo” "
        "para gerar o relatório.",
        icon=":material/summarize:")
else:
    faltantes = [parecer_servico.TITULOS[c] for c in relatorios.CHECAGENS
                 if c not in encontrados]
    avisos.faixa_de_avisos([avisos.aviso_consolidado_parcial(faltantes)])

    consolidado = relatorios.consolidar(encontrados)
    label, cor = _veredito_geral({"normativo": consolidado})
    st.markdown(montar_card_grupo(
        "Resultado consolidado", label, cor,
        contagens_em_requisitos(consolidado),
        explicacao_do_resultado(consolidado)), unsafe_allow_html=True)

    _desenhar(parecer_servico.montar(encontrados, frase_do_empreendimento(emp)))
