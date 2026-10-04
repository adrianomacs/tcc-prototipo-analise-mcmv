"""Checagem — Georreferenciamento do modelo (GIS + BIM) — grupo EMP-001.

Anatomia do ADR-034: explicação do grupo, card do empreendimento (a
localização vem de Informações Gerais, 2.1.1), faixa de avisos e as duas
seções:
  1) **Informações de entrada** — o que o arquivo contém e de quem é (a única
     declaração LOCAL desta tela) e o upload do IFC;
  2) **Cobertura e análise** — métricas, a linha "Ao analisar…" com o botão,
     o resultado e, quando o modelo não se posiciona sozinho, o
     posicionamento aproximado para a cena 3D.

A localização declarada alimenta o CROSS-CHECK do EMP-001: a âncora
geográfica derivada do modelo é confrontada com a malha municipal oficial
(IBGE, sob demanda + cache). Sem localização declarada em 2.1.1, a análise
roda sem o confronto (mesmo comportamento original do EMP-001 sem snapshot
de municípios).

O que o arquivo contém, e de quem ele é (ADR-023)
--------------------------------------------------

A "natureza do modelo" — Terreno, Edificação isolada, Terreno com
edificações — é a pergunta que condiciona as regras (o que o arquivo
CONTÉM), mas, como 2.1.1 declara a composição antes de qualquer upload, ela
não responde a outra: **de quem** o
arquivo é. As duas viajam juntas na mesma escolha — cada opção do seletor
carrega uma natureza e um ALVO (`app.servicos.analise`), e o alvo é que diz a
qual unidade tipo ou edificação física o contêiner se pendura. Nenhum valor
novo entrou no vocabulário de `natureza`: "unidade tipo isolada" e "edificação
isolada" são a mesma `edificacao_isolada` de sempre — o que as distingue é o
dono, não o conteúdo.

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
from app.servicos import analise, conversao_3d, grupos, territorio
from app.servicos import declaracoes as dec
from app.servicos import empreendimento as emp_mod

CHAVE = "georref"
GRUPO_ID = "georreferenciamento"
ORIGEM = arvore.PAGINA_CHECAGEM_GEORREFERENCIAMENTO

ROTULO_TERRENO = "Terreno"
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
        st.error("Grupo 'georreferenciamento' não encontrado em "
                 "config/grupos_requisitos.yaml.")
        return

    explicacao_mod.explicacao_grupo(grupo, em_expander=True, mostrar_situacao=False)

    emp = _empreendimento_corrente()
    cabecalho_empreendimento(emp)
    avisos.faixa_de_avisos([_aviso_municipio_ausente(emp)])

    st.subheader("Informações de entrada")
    declaracoes_locais, alvo = _formulario_inputs(emp)
    arquivo_ifc = st.file_uploader("Modelo IFC", type=["ifc"])
    # A premissa antes do envio: é aqui que ela ainda evita uma reexportação.
    avisos.aviso_premissa_ifc4()

    st.divider()
    st.subheader("Cobertura e análise")
    executaveis = grupos.ids_executaveis(
        grupo, analise.declaracoes_da_analise(emp, declaracoes_locais))
    explicacao_mod.cobertura(grupo, executaveis)
    acao_mod.acao(CHAVE, arquivo_ifc, grupo, declaracoes_locais, ORIGEM, emp,
                  alvo=alvo,
                  resumo_execucao=explicacao_mod.resumo_da_execucao(
                      grupo, executaveis))

    _posicionamento_manual(emp)


def _aviso_municipio_ausente(emp) -> avisos.Aviso | None:
    """Pré-condição da faixa (ADR-034 (c)): sem município, o EMP-001 roda sem
    o confronto com os limites municipais."""
    if emp.codigo_ibge:
        return None
    return avisos.Aviso(
        avisos.ALERTA, "Município ainda não declarado.",
        "A localização do modelo não será confrontada com os limites do "
        "município.",
        "Declare-o em Informações Gerais.")


def _opcoes(emp) -> dict[str, tuple[str, str]]:
    """Rótulo -> (natureza, alvo) — o que o arquivo contém e de quem ele é.

    "Terreno" e "Terreno com as edificações" existem sempre: o primeiro é o
    modelo só do terreno, e o segundo é o federado, que se pendura no terreno
    E em todas as edificações físicas (no único tipo, se não houver física
    nenhuma). As isoladas são nomeadas uma a uma, por NOME — nunca por ordem
    de lista, mesma postura de `core.dominio.ancora`.
    """
    opcoes: dict[str, tuple[str, str]] = {
        ROTULO_TERRENO: (dec.TERRENO, analise.ALVO_TERRENO),
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
    """Declaração LOCAL desta tela: o que o arquivo enviado contém e de quem
    ele é (ver o cabeçalho do módulo).

    UF/Município não são perguntados aqui — vêm do `Empreendimento` (2.1.1),
    mostrado no cabeçalho acima. `app.servicos.analise` funde o dicionário de
    declarações às do empreendimento na hora de analisar; nada aqui é
    persistido no `empreendimento.json`, nem o alvo — a quem o arquivo
    pertence é afirmação sobre ESTA análise.

    O default continua sendo o modelo federado, como antes da R2: é o caso do
    fluxo dourado e o mais comum nas submissões reais.
    """
    opcoes = _opcoes(emp)
    rotulos = list(opcoes)
    rotulo = st.selectbox("O arquivo enviado contém:", rotulos,
                          index=rotulos.index(ROTULO_TODAS),
                          key=f"alvo__{CHAVE}")
    if not emp.unidades_tipo and not emp.edificacoes:
        st.caption("Nenhuma unidade tipo ou edificação declarada em "
                   "**Informações Gerais** — declare-as lá para poder enviar "
                   "um modelo isolado de uma delas.")
    natureza, alvo = opcoes[rotulo]
    return {dec.TIPO_MODELO: natureza}, alvo


@st.cache_data
def _centro_municipio(codigo_ibge: str) -> tuple[float, float] | None:
    return territorio.centro_municipio(codigo_ibge)


def _posicionamento_manual(emp) -> None:
    """Posicionamento aproximado do modelo sem âncora geográfica derivável.

    Só aparece quando a conversão 3D terminou e o modelo NÃO é posicionável.
    A âncora manual alimenta apenas a VISUALIZAÇÃO (o veredito do EMP-001 não
    muda: o modelo segue sem georreferenciamento estruturado). Default de
    lat/lon: centroide da malha do município declarado no `Empreendimento`.
    """
    caminho_ifc = st.session_state.get(chaves.chave_caminho_ifc(CHAVE))
    if not caminho_ifc or conversao_3d.estado_viz(CHAVE) != "pronto":
        return
    status = conversao_3d.ler_status_viz(CHAVE)
    if status.get("posicionavel"):
        return

    st.markdown("##### Posicionamento aproximado do modelo")
    avisos.mostrar_aviso(avisos.Aviso(
        avisos.ORIENTACAO,
        "O modelo não traz localização que permita posicioná-lo no mapa.",
        "Para ver a cena 3D, informe coordenadas aproximadas; isso vale só "
        "para a visualização e não muda o resultado do georreferenciamento."))

    lat0, lon0 = -15.7939, -47.8828  # fallback: Brasília
    codigo = emp.codigo_ibge
    if codigo:
        centro = _centro_municipio(codigo)
        if centro:
            lat0, lon0 = centro
            st.caption(f"Sugestão pré-preenchida: centro de "
                       f"{emp.localizacao.municipio}/{emp.localizacao.uf} "
                       "(malha IBGE).")

    c1, c2, c3 = st.columns(3)
    lat = c1.number_input("Latitude (graus)", min_value=-90.0, max_value=90.0,
                          value=float(lat0), step=0.0001, format="%.6f")
    lon = c2.number_input("Longitude (graus)", min_value=-180.0, max_value=180.0,
                          value=float(lon0), step=0.0001, format="%.6f")
    rot = c3.number_input("Rotação (graus, anti-horário)", min_value=-180.0,
                          max_value=180.0, value=0.0, step=1.0)

    if st.button("Aplicar posicionamento aproximado", type="primary"):
        ancora_manual = {
            "modo": "manual", "lat": float(lat), "lon": float(lon),
            "altura": 0.0, "rotacao_graus": float(rot),
            "mensagem": "Posicionamento APROXIMADO informado pelo usuário "
                        "(modelo sem georreferenciamento estruturado).",
        }
        conversao_3d.iniciar_conversao(CHAVE, caminho_ifc, ancora_manual=ancora_manual)
        st.rerun()


main()
