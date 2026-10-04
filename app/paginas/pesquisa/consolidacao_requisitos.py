"""Análise, Classificação e Seleção dos Requisitos — 1.2.2. O Passo 1 do
trabalho: como os requisitos da Portaria foram classificados, o quadro-resumo
por fase e domínio, o recorte implementado (em destaque) e a base completa,
navegável, num expander. Texto alinhado ao Passo 1 do método;
a tabela do recorte fica por requisito, e não por checagem. Números lidos da planilha em
tempo de execução (`app/servicos/requisitos.py`), nunca escritos à mão.
Página de pesquisa: largura total (ADR-034)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.componentes import dominio as _dominio
from app.servicos import requisitos as _requisitos

# Cores dos domínios: as da planilha-mãe, num componente comum
# (`app/componentes/dominio.py`), compartilhado com "Requisitos a serem
# validados".
DOMINIOS = _dominio.DOMINIOS
_COR_DOMINIO = _dominio.COR_DOMINIO
_TEXTO = _dominio.TEXTO
_FASES = ("Enquadramento do Terreno", "Análise do Empreendimento")


# O carimbo da planilha entra como argumento para o cache se renovar quando a
# base é regravada; sem ele, uma sessão aberta seguiria com a versão antiga.
# Sem sublinhado no nome: o st.cache_data ignora argumentos que começam por "_".
@st.cache_data(show_spinner="Carregando a base de requisitos…")
def _base_completa(carimbo: float):
    return _requisitos.carregar_base_completa()


@st.cache_data
def _ids_ativos():
    return _requisitos.carregar_ids_ativos()


@st.cache_data
def _nao_convertidos(carimbo: float):
    return _requisitos.contar_nao_convertidos()


def _estilo_dominio(valor) -> str:
    cor = _COR_DOMINIO.get(valor)
    return f"background-color: {cor}; color: {_TEXTO}" if cor else ""


def _colorir(df: pd.DataFrame, coluna: str):
    """Pinta a célula do domínio; sem jinja2, devolve a tabela sem cor."""
    try:
        estilo = df.style
        pintar = getattr(estilo, "map", None) or estilo.applymap  # pandas < 2.1
        return pintar(_estilo_dominio, subset=[coluna])
    except Exception:
        return df


def _legenda() -> None:
    _dominio.legenda()


carimbo = _requisitos.carimbo_da_base()
df = _base_completa(carimbo)
ids_ativos = _ids_ativos()

if df.empty:
    st.warning(
        "**A base de requisitos não foi encontrada.** Sem a planilha-mãe no "
        "repositório, não há o que listar nesta página.",
        icon=":material/error:")
    st.stop()

base = _requisitos.contar_base(df)
rec = _requisitos.contar_recorte(df, ids_ativos)
n_nao_convertidos = _nao_convertidos(carimbo)
ativos = df[df["ID"].isin(ids_ativos)]

_n_dom = df["Classificação"].value_counts()

st.write(
    "O primeiro passo construiu uma base estruturada dos requisitos técnicos "
    "do PMCMV, a partir da leitura sistemática da Portaria MCID nº 725/2023, "
    "na versão compilada até a Portaria MCID nº 1.079/2026, sob a ótica de "
    "quem analisa um empreendimento. Cada requisito foi caracterizado por um "
    "conjunto de atributos, a fase do fluxo a que pertence (enquadramento do "
    "terreno ou análise do empreendimento), a disciplina, a aplicabilidade "
    "quanto ao arranjo e à tipologia (condomínio ou loteamento, casa ou "
    "apartamento), o caráter obrigatório ou recomendável, conforme a própria "
    "Portaria, e a natureza do parâmetro (quantitativo, qualitativo ou "
    "documental)."
)
st.write(
    "São quatro domínios. Os requisitos **GIS only** dependem só do "
    "território, como a localização, o entorno e os equipamentos públicos. Os "
    "**BIM only** são verificáveis no modelo da edificação, em ambientes, "
    "áreas, dimensões e materiais. Os **GIS + BIM** exigem cruzar o modelo "
    "com o território, como no georreferenciamento ou na absortância conforme "
    "a zona bioclimática. Já os de **análise humana** dependem de decisão "
    "interpretativa, documental ou subjetiva, e marcam a fronteira da "
    "automação. A classificação se apoia nos fundamentos da verificação "
    "automatizada de regras (Eastman et al., 2009; Solihin e Eastman, 2015), "
    "que distinguem as regras conforme a complexidade e a origem das "
    "informações que a sua checagem requer."
)
st.write(
    "A decomposição seguiu um critério de granularidade segundo o qual cada "
    "linha da base tem um único verbo de verificação, um único alvo, um único "
    "domínio e uma única condição de aplicabilidade. Distinguem-se, assim, o "
    "requisito, linha que representa um dispositivo da Portaria, e o "
    "desdobramento, linha subordinada a um requisito por atomização ou por "
    "agrupamento. Todo dispositivo que impõe, veda, recomenda ou dispensa algo "
    "tem ao menos uma linha na base, e os que não viraram linha, como "
    "definições e procedimentos do agente, estão registrados com o motivo "
    f"({n_nao_convertidos} dispositivos), de modo que a cobertura da Portaria "
    f"é fechada. O resultado é uma base de **{base['requisitos']} requisitos** "
    f"e {base['atomizacoes'] + base['agrupamentos']} desdobramentos "
    f"({base['atomizacoes']} atomizações e {base['agrupamentos']} "
    f"agrupamentos), que somam **{base['verificacoes']} verificações**, já "
    f"que {base['nos_de_agregacao']} requisitos apenas reúnem o resultado dos "
    "seus membros. Na distribuição por domínio, são "
    f"{_n_dom.get('BIM only', 0)} linhas BIM only, "
    f"{_n_dom.get('Análise humana', 0)} de análise humana, "
    f"{_n_dom.get('GIS + BIM', 0)} GIS + BIM e {_n_dom.get('GIS only', 0)} "
    "GIS only, o que mostra o predomínio dos requisitos verificáveis a partir "
    "do modelo. O método completo está no Leia-me da planilha, em "
    "`config/Base_Requisitos_Portaria_MCID_725.xlsx`."
)

st.subheader("Quadro-resumo")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Requisitos da Portaria", base["requisitos"])
c2.metric("Desdobramentos", base["atomizacoes"] + base["agrupamentos"])
c3.metric("Verificações", base["verificacoes"])
c4.metric("Requisitos no recorte", rec["requisitos"])

quadro = pd.crosstab(df["Fase"], df["Classificação"])
quadro = quadro.reindex(index=[f for f in _FASES if f in quadro.index],
                        columns=[d for d in DOMINIOS if d in quadro.columns],
                        fill_value=0)
quadro["Total"] = quadro.sum(axis=1)
quadro.loc["Total"] = quadro.sum(axis=0)
quadro.index.name = "Fase"
_legenda()
st.dataframe(quadro, use_container_width=True)
st.caption(
    f"Requisitos e desdobramentos da base ({base['linhas']} linhas) por fase "
    "e domínio. O enquadramento do terreno é quase todo GIS e a análise do "
    "empreendimento, quase toda BIM, o que mostra que nenhum dos dois "
    "domínios, sozinho, cobre o problema.")

st.subheader("O recorte implementado")
st.write(
    f"O protótipo implementa **{rec['requisitos']} requisitos**, que ocupam "
    f"{rec['linhas']} linhas da base e somam **{rec['verificacoes']} "
    f"verificações**, já que {rec['nos_de_agregacao']} deles reúnem o "
    "resultado dos seus membros. Foram escolhidos pela viabilidade técnica "
    "de verificação, entendida como a disponibilidade das informações no "
    "modelo IFC e nas bases geoespaciais públicas, pela representatividade "
    "dos diferentes domínios e pela relevância prática no fluxo de análise. "
    "Buscou-se deliberadamente um conjunto enxuto, capaz de exercitar os "
    "diferentes mecanismos de verificação previstos, e não de cobrir a "
    "Portaria. Os requisitos se organizam nas cinco checagens, na ordem em "
    "que o protótipo as apresenta. A base completa, com todas as linhas e "
    "seus atributos, está disponível para consulta logo abaixo."
)
por_id = df.set_index("ID")
linhas = []
for pai, grupo in ativos.groupby("Grupo (pai)", sort=False):
    ref = por_id.loc[pai] if pai in por_id.index else grupo.iloc[0]
    linhas.append({
        "Requisito": pai,
        "O que verifica": ref["Requisito"],
        "IDs na base": ", ".join(grupo["ID"]),
        "Domínio": ref["Classificação"],
        "Fase": ref["Fase"],
    })
recorte = pd.DataFrame(linhas)
_legenda()
st.dataframe(_colorir(recorte, "Domínio"), hide_index=True,
             use_container_width=True)

with st.expander(f"Base completa da Portaria ({base['linhas']} linhas)",
                 icon=":material/table_view:"):
    completa = df.copy()
    completa["No recorte"] = completa["ID"].isin(ids_ativos)

    fc1, fc2, fc3 = st.columns(3)
    anexos_sel = fc1.multiselect("Anexo", sorted(completa["Anexo"].unique()))
    dominios_sel = fc2.multiselect(
        "Domínio", [d for d in DOMINIOS if d in set(completa["Classificação"])])
    vinculos_sel = fc3.multiselect(
        "Tipo de vínculo",
        sorted(completa["Tipo de vínculo"].dropna().unique()))
    fc4, fc5 = st.columns(2)
    verbos_sel = fc4.multiselect(
        "Método de verificação",
        sorted(completa["Método de verificação"].dropna().unique()))
    aplicabilidades_sel = fc5.multiselect(
        "Aplicabilidade", sorted(completa["Aplicabilidade"].dropna().unique()))
    so_recorte = st.checkbox("Mostrar só o recorte do protótipo")

    filtrado = completa
    if anexos_sel:
        filtrado = filtrado[filtrado["Anexo"].isin(anexos_sel)]
    if dominios_sel:
        filtrado = filtrado[filtrado["Classificação"].isin(dominios_sel)]
    if vinculos_sel:
        filtrado = filtrado[filtrado["Tipo de vínculo"].isin(vinculos_sel)]
    if verbos_sel:
        filtrado = filtrado[filtrado["Método de verificação"].isin(verbos_sel)]
    if aplicabilidades_sel:
        filtrado = filtrado[filtrado["Aplicabilidade"].isin(aplicabilidades_sel)]
    if so_recorte:
        filtrado = filtrado[filtrado["No recorte"]]

    colunas = [
        "ID", "Grupo (pai)", "Tipo de vínculo", "Anexo", "Fase",
        "Classificação", "Aplicabilidade", "Requisito", "Parâmetro objetivo",
        "Método de verificação", "Caráter", "Verificabilidade no modelo",
        "No recorte",
    ]
    tabela = filtrado[colunas].rename(
        columns={"Classificação": "Domínio"}).reset_index(drop=True)
    _legenda()
    st.dataframe(_colorir(tabela, "Domínio"), hide_index=True,
                 use_container_width=True, height=520,
                 column_config={"No recorte": st.column_config.CheckboxColumn(
                     "No recorte")})
    st.caption(
        f"{len(tabela)} de {base['linhas']} linhas exibidas "
        f"({int(tabela['No recorte'].sum())} no recorte do protótipo).")
