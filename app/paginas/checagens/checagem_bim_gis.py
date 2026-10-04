"""Checagem — Validações BIM + GIS: absortância solar por zona bioclimática.

A primeira checagem em que **um dado do território decide o parâmetro e a
aplicabilidade de uma verificação sobre o modelo**: a zona bioclimática,
derivada do município (ADR-030), escolhe qual ramo de cada requisito de
absortância se aplica — parede externa (EDI-019) e telhado (EDI-024) — e,
com ele, o limite contra o qual o ``IfcCovering`` é comparado (ADR-026).

Anatomia do ADR-034: explicação do grupo, card do empreendimento (é de lá,
e só de lá, que vem o município — a zona nunca é declarada), faixa de avisos
e as duas seções:

  1) **Informações de entrada** — o que o arquivo contém e de quem é, o
     upload do IFC e a frase de contexto (absortância × zona);
  2) **Cobertura e análise** — métricas, a linha "Ao analisar…" com o botão
     e o resultado (componente comum), com o acesso ao relatório de EDI-019 e
     EDI-024. O painel "O que o território decidiu sobre o modelo" que ficava
     aqui saiu: repetia o relatório da absortância (ADR-034).

A página não importa o núcleo (ADR-003) e se declara só em
``app/navegacao/arvore.py`` (ADR-010).

Execução: via ponto de entrada ``streamlit run app/main.py``.
"""

from __future__ import annotations

import streamlit as st

from app.componentes import acao as acao_mod
from app.componentes import avisos
from app.componentes import explicacao_grupo as explicacao_mod
from app.componentes.cabecalho_empreendimento import cabecalho_empreendimento
from app.estado import chaves
from app.navegacao import arvore
from app.servicos import analise, grupos
from app.servicos import declaracoes as dec
from app.servicos import empreendimento as emp_mod

# CHAVE: artefatos/relatorios/<chave>.json (ADR-001); GRUPO_ID: o id em
# config/grupos_requisitos.yaml.
CHAVE = "bim_gis"
GRUPO_ID = "absortancia_zona_bioclimatica"
ORIGEM = arvore.PAGINA_CHECAGEM_BIM_GIS

ROTULO_TODAS = "Terreno com as edificações"


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
    avisos.faixa_de_avisos([_aviso_municipio_ausente(emp)])

    st.subheader("Informações de entrada")
    declaracoes_locais, alvo = _formulario_inputs(emp)
    arquivo_ifc = st.file_uploader("Modelo IFC", type=["ifc"])

    st.divider()
    st.subheader("Cobertura e análise")
    executaveis = grupos.ids_executaveis(
        grupo, analise.declaracoes_da_analise(emp, declaracoes_locais))
    explicacao_mod.cobertura(grupo, executaveis)
    acao_mod.acao(CHAVE, arquivo_ifc, grupo, declaracoes_locais, ORIGEM, emp,
                  alvo=alvo,
                  resumo_execucao=explicacao_mod.resumo_da_execucao(
                      grupo, executaveis))


def _aviso_municipio_ausente(emp) -> avisos.Aviso | None:
    """Pré-condição da faixa (ADR-034 (c)): sem município não há zona, e sem
    zona nenhum ramo sabe se aplica — as regras saem NÃO AVALIÁVEL com a causa
    registrada (ADR-030). Avisa, não bloqueia."""
    if emp.codigo_ibge:
        return None
    return avisos.Aviso(
        avisos.ALERTA, "Município ainda não declarado.",
        "A zona bioclimática vem dele; sem ela, nenhum limite de absortância "
        "é escolhido e as verificações sairão como não avaliáveis.",
        "Declare-o em Informações Gerais.")


def _opcoes(emp) -> dict[str, tuple[str, str]]:
    """Rótulo -> (natureza, alvo). As mesmas escolhas do Georreferenciamento
    menos "Terreno": um modelo só do terreno não tem envoltória, e as regras
    de absortância exigem edificação (``COM_EDIFICACAO``)."""
    opcoes: dict[str, tuple[str, str]] = {
        ROTULO_TODAS: (dec.TERRENO_COM_EDIFICACOES, analise.ALVO_TODAS),
    }
    for unidade_tipo in emp.unidades_tipo:
        nome = unidade_tipo.nome or "(sem nome)"
        opcoes[f"{nome} — unidade tipo isolada"] = (
            dec.EDIFICACAO_ISOLADA, analise.alvo_de_unidade_tipo(unidade_tipo.id))
    for edificacao in emp.edificacoes:
        nome = edificacao.nome or "(sem nome)"
        opcoes[f"{nome} — edificação isolada"] = (
            dec.EDIFICACAO_ISOLADA, analise.alvo_de_edificacao(edificacao.id))
    return opcoes


def _formulario_inputs(emp) -> tuple[dict, str]:
    opcoes = _opcoes(emp)
    rotulo = st.selectbox("O arquivo enviado contém:", list(opcoes),
                          key=f"alvo__{CHAVE}")
    # Frase de contexto (ADR-034 (e)): zona bioclimática e revestimento não
    # têm fonte na lista de referências — vão sem citação.
    st.caption("A absortância solar é conferida nos revestimentos externos do "
               "modelo (paredes e cobertura), contra o limite que a zona "
               "bioclimática impõe. A zona vem do município declarado em "
               "Informações Gerais (ABNT TR 15220-3-1:2024); não é perguntada "
               "aqui.")
    natureza, alvo = opcoes[rotulo]
    return {dec.TIPO_MODELO: natureza}, alvo


main()
