"""Requisitos a serem validados — o roteiro do que o protótipo vai verificar
no empreendimento declarado, checagem a checagem, na ordem do menu.

Fica na seção "Checagens do Protótipo" (Dados do Empreendimento), por isso
segue a anatomia do ADR-034: largura total, "O que esta página mostra" sob o
título, card do empreendimento e faixa de avisos. A situação de cada
requisito sai de ``grupos.situacao_no_empreendimento``, o mesmo cálculo de
aplicabilidade que a checagem faz ao abrir, e a contagem é por requisito da
Portaria (ADR-015). A frase de cada bloco é curta de propósito: a explicação
completa mora no "O que esta checagem verifica" de cada checagem.

A página não importa o núcleo (ADR-003) e se declara só em
``app/navegacao/arvore.py`` (ADR-010).
"""

from __future__ import annotations

import streamlit as st

from app.componentes import avisos
from app.componentes import dominio as _dominio
from app.componentes.cabecalho_empreendimento import (
    cabecalho_empreendimento,
    frase_do_empreendimento,
)
from app.estado import chaves
from app.navegacao import arvore
from app.servicos import analise, grupos
from app.servicos import declaracoes as dec
from app.servicos import empreendimento as emp_mod

# (página da checagem, id do grupo em config/grupos_requisitos.yaml, frase)
_BLOCOS = (
    (arvore.PAGINA_CHECAGEM_ENQUADRAMENTO, "enquadramento",
     "Confere se há escolas de educação infantil e de ensino fundamental ao "
     "alcance das famílias, pela distância caminhável a partir do terreno ou, "
     "no ensino fundamental, pelo transporte escolar."),
    (arvore.PAGINA_CHECAGEM_QUALIFICACAO, "qualificacao_urbanistica",
     "Compara as UHs previstas com o limite que o porte populacional do "
     "município impõe ao empreendimento."),
    (arvore.PAGINA_CHECAGEM_GEORREFERENCIAMENTO, "georreferenciamento",
     "Confere se o modelo está georreferenciado e se a sua posição cai no "
     "município declarado."),
    (arvore.PAGINA_CHECAGEM_PROGRAMA, "programa_necessidades",
     "Confere, no modelo da unidade tipo, a presença dos ambientes "
     "obrigatórios, a área útil mínima e as larguras mínimas de cozinha, "
     "sala, banheiro e varanda."),
    (arvore.PAGINA_CHECAGEM_BIM_GIS, "absortancia_zona_bioclimatica",
     "Confere se a absortância das paredes externas e da cobertura, lida no "
     "modelo, é compatível com a zona bioclimática do município."),
)


def _empreendimento_corrente():
    guardado = st.session_state.get(chaves.EMPREENDIMENTO)
    if guardado is not None:
        return guardado
    carregado = emp_mod.carregar()
    st.session_state[chaves.EMPREENDIMENTO] = carregado
    return carregado


def _celula(texto: str) -> str:
    return (texto or "").replace("|", "/").replace("<=", "≤").replace(">=", "≥")


def _legenda(aplicam: int, total: int) -> str:
    if total == 1:
        return ("O requisito se aplica a este empreendimento." if aplicam
                else "O requisito não se aplica a este empreendimento.")
    return f"Aplicam-se {aplicam} de {total} requisitos."


def _bloco(pagina, grupo, frase: str, declaracoes: dict) -> None:
    titulo = pagina.rotulo.split(" (")[0]
    selo = _dominio.selo_html(_dominio.DOMINIO_DA_CAMADA.get(grupo.camada, ""))
    st.markdown(f"<h3 style='margin-bottom:0.2rem'>{titulo} {selo}</h3>",
                unsafe_allow_html=True)
    st.write(frase)
    linhas = grupos.situacao_no_empreendimento(grupo, declaracoes)
    tabela = ["| Requisito | O que a Portaria exige | Neste empreendimento |",
              "|---|---|---|"]
    for regra, situacao in linhas:
        tabela.append(f"| **{regra.id}** {_celula(regra.rotulo)} "
                      f"| {_celula(regra.parametro)} | {situacao} |")
    st.markdown("\n".join(tabela))
    aplicam = sum(1 for _, s in linhas if not s.startswith("Não se aplica"))
    c1, c2 = st.columns([4, 1], vertical_alignment="center")
    c1.caption(_legenda(aplicam, len(linhas)))
    if c2.button("Ir para a checagem", key=f"ir_{grupo.id}",
                 icon=":material/arrow_forward:", use_container_width=True):
        st.switch_page(pagina.caminho)


def main() -> None:
    with st.expander("O que esta página mostra", icon=":material/info:"):
        st.write(
            "Reúne, checagem a checagem, os requisitos da Portaria que o "
            "protótipo verifica e indica quais se aplicam ao empreendimento "
            "declarado em Informações Gerais. O requisito que não se aplica, "
            "como a área útil mínima de casas num condomínio de apartamentos, "
            "fica fora da análise da checagem correspondente.")

    emp = _empreendimento_corrente()
    cabecalho_empreendimento(emp)
    declaracoes = analise.declaracoes_da_analise(emp, {})
    avisos.faixa_de_avisos([
        # Sem nada declarado, o card já orienta; o aviso da tipologia só
        # vale para um empreendimento que existe e ainda não a tem.
        None if declaracoes.get(dec.TIPOLOGIA)
        or not frase_do_empreendimento(emp) else avisos.Aviso(
            avisos.ORIENTACAO,
            "A unidade tipo ainda não tem tipologia declarada.",
            "Enquanto ela faltar, os requisitos exclusivos de casas ou de "
            "apartamentos aparecem como aplicáveis.",
            "Declare-a em Informações Gerais."),
    ])

    for pagina, gid, frase in _BLOCOS:
        grupo = grupos.carregar_grupo(gid)
        if grupo is None:
            continue
        _bloco(pagina, grupo, frase, declaracoes)


main()
