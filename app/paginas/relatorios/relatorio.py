"""Página dedicada: relatório de um requisito (ADR-034).

Anatomia única, empilhada: voltar e "O que esta regra verifica", faixa de
avisos, card de verificação, frase de contexto, resultado, mapa ou cena 3D em
largura total e o técnico em expanders.

Página oculta (fora do menu lateral): acessada via ``st.switch_page`` a partir
da tabela de resultados das checagens, inclusive das regras do Programa de
necessidades, que têm cada uma o seu relatório, com a cena só dos ambientes
daquela regra (ADR-034).
"""

from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from app.componentes import mapa as _mapa
from app.componentes import relatorio_absortancia as absortancia
from app.componentes import relatorio_ambientes as ambientes
from app.componentes import relatorio_georref as georref
from app.componentes import relatorio_porte as porte
from app.componentes.avisos import alerta_com_detalhe, faixa_de_avisos
from app.componentes.card_verificacao import card_verificacao
from app.componentes.cena3d import (
    ambientes_para_cena,
    gravar_cena,
    legenda_cores,
    revestimentos_com_caixas,
)
from app.componentes.explicacao_grupo import explicacao_requisito
from app.componentes.layout import ALTURA_VISUALIZACAO, secao_outras_informacoes
from app.componentes.paineis import (
    painel_agregacao,
    painel_ambientes_atributos,
    painel_ambientes_resumo,
    painel_areas_uh,
    painel_enq_consulta,
    painel_enq_equipamentos,
    painel_enq_resumo,
    painel_larguras,
    painel_remetida,
    painel_requisito,
)
from app.estado import chaves
from app.navegacao import arvore
from app.servicos import conversao_3d, qualificacao, relatorios, territorio


def main() -> None:
    r = st.session_state.get(chaves.REQ_SELECIONADO)
    # A chave da checagem que abriu este requisito — carrega a
    # visualização 3D da MESMA checagem.
    chave = st.session_state.get(chaves.CHAVE_SELECIONADA)

    # Voltar e "O que esta regra verifica" dividem a primeira linha (ADR-034):
    # os dois são navegação e contexto, não resultado, e empilhados gastavam a
    # altura que o card precisa.
    col_voltar, col_explica = st.columns([1, 4], vertical_alignment="top")
    with col_voltar:
        voltar = st.button("← Voltar à checagem", use_container_width=True)
    if voltar:
        # A origem é gravada por quem abre o relatório
        # (app.componentes.resultado) como um nó `Pagina` (ADR-010).
        origem = st.session_state.get(chaves.ORIGEM_RELATORIO)
        st.switch_page(origem.caminho if origem
                       else arvore.PAGINA_CHECAGEM_PROGRAMA.caminho)
    if r:
        with col_explica:
            explicacao_requisito(r.get("requisito", ""), r.get("descricao", ""))

    if not r:
        st.info("**Nenhum requisito selecionado.** Volte à checagem e clique "
                "em “Verificar relatório” em um requisito.",
                icon=":material/info:")
        return

    # Despacho por tipo de diagnóstico: cada relatório tem um layout dedicado.
    detalhe = r.get("detalhe") or {}
    tipo = detalhe.get("tipo")
    if tipo == "logeoref":
        _relatorio_emp001(chave, r, detalhe)
    elif tipo == "distancia_equipamento":
        _relatorio_enq(r, detalhe)
    elif tipo == "agregacao":
        _relatorio_requisito_agregado(r, detalhe)
    elif ambientes.eh_ambientes(detalhe):
        _relatorio_ambientes(chave, r, detalhe)
    else:
        st.subheader("Resultado da checagem")
        painel_requisito(r)


def _relatorio_emp001(chave: str, r: dict, detalhe: dict) -> None:
    """Relatório do EMP-001 na anatomia do ADR-034, empilhado: avisos de
    posição na faixa, card com o nível exigido e o medido, a escala explicada
    antes do resultado, a cena 3D em largura total e o técnico (níveis,
    posição, consistência, procedência) em expanders."""
    viz = conversao_3d.carregar_payload_viz(chave, publicar_glb=True)

    # Limites do município declarado (se a análise baixou/cacheou a malha).
    declarada = detalhe.get("localizacao_declarada") or {}
    malha = None
    if declarada.get("municipio_ibge"):
        malha = territorio.malha_em_cache(declarada["municipio_ibge"])

    faixa_de_avisos(georref.avisos_emp001(detalhe))
    card_verificacao(r, detalhe, georref.criterio_logeoref(detalhe))
    st.markdown(georref.CONTEXTO_LOGEOREF)
    st.markdown(georref.texto_resultado(detalhe))

    st.subheader("Modelo no contexto geográfico")
    components.iframe(gravar_cena(viz, malha=malha, ajustes=True),
                      height=ALTURA_VISUALIZACAO)
    if _modelo_grande_demais(viz):
        pass
    elif not (viz and viz.get("posicionavel")):
        motivo = (viz or {}).get("erro") or "sem âncora geográfica derivável"
        st.info("**O modelo não pôde ser posicionado no globo.** Na checagem "
                "de georreferenciamento, o posicionamento aproximado permite "
                "vê-lo mesmo assim.", icon=":material/info:")
        st.caption(f"Causa: {motivo}.")
    if malha:
        st.caption(f"Contorno no mapa: limites de {georref.lugar_declarado(declarada)} "
                   "(malha municipal do IBGE), referência do confronto com o "
                   "município declarado.")

    secao_outras_informacoes()
    georref.painel_niveis(detalhe)
    georref.painel_posicao(detalhe)
    georref.painel_consistencia(detalhe)
    georref.painel_informacoes_extraidas(detalhe)
    _json_bruto(r)


def _relatorio_ambientes(chave: str, r: dict, detalhe: dict) -> None:
    """Relatório de uma regra do Programa de necessidades (ADR-034).

    Cada regra tem o seu, como as demais checagens, e a cena carrega só os
    ambientes que ESTA regra julgou, lidos do ``ambientes`` do ``detalhe``: a
    largura do banheiro mostra só os banheiros; a área útil, os ambientes
    que entraram na soma. Os ambientes deixados de fora (ADR-031) e os
    atributos IFC vão a "Outras informações" de cada relatório, porque um
    ambiente triado muda o resultado de qualquer regra do grupo.
    """
    meta = (relatorios.ler(chave) or {}).get("meta") or {} if chave else {}
    alerta_com_detalhe(ambientes.AVISO_GERAL,
                       ambientes.pontos_de_atencao(detalhe, meta),
                       rotulo="Por que este aviso")
    card_verificacao(r, detalhe, ambientes.criterio(r))
    st.markdown(ambientes.CONTEXTO_AMBIENTES)
    if r.get("mensagem"):
        st.markdown(r["mensagem"])

    tipo = detalhe.get("tipo")
    if tipo == "ambientes":
        painel_ambientes_resumo(detalhe)
    elif tipo == "areas_uh":
        painel_areas_uh(detalhe)
    else:
        painel_larguras(detalhe)

    viz = conversao_3d.carregar_payload_viz(chave, publicar_glb=True)
    st.subheader("Modelo e ambientes")
    components.iframe(gravar_cena(viz, ambientes_para_cena(detalhe, r.get("estado")),
                                  ajustes=True), height=ALTURA_VISUALIZACAO)
    if _modelo_grande_demais(viz):
        pass
    elif not (viz and viz.get("posicionavel")):
        motivo = (viz or {}).get("erro") or "sem âncora geográfica derivável"
        st.caption(f"O modelo não pôde ser posicionado no globo ({motivo}).")
    else:
        st.markdown(legenda_cores(), unsafe_allow_html=True)
        st.caption(ambientes.legenda_cena(detalhe))

    secao_outras_informacoes()
    fora = ambientes.ambientes_fora(detalhe)
    if fora:
        with st.expander(f"{ambientes.SECAO_AMBIENTES_FORA} ({len(fora)})",
                         expanded=False, icon=":material/visibility_off:"):
            st.caption("Ambientes do modelo que esta verificação não "
                       "considerou, por parecerem erro de exportação. "
                       "Localize cada um pelo GUID no modelo autoral.")
            st.dataframe(ambientes.linhas_ambientes_fora(fora),
                         hide_index=True, use_container_width=True)
    with st.expander("Atributos IFC extraídos dos ambientes", expanded=False,
                     icon=":material/table_view:"):
        st.caption("A fonte de cada área e o termo que classificou cada "
                   "ambiente considerado por esta verificação.")
        painel_ambientes_atributos(detalhe)
    _json_bruto(r)


def _relatorio_enq(r: dict, detalhe: dict) -> None:
    """Relatório das regras de distância a equipamento (ENQ-009/010.1/011.1).

    Tela dividida no mesmo padrão dos demais relatórios, com o mapa no lugar da
    cena 3D: à esquerda o território (terreno analisado, limiar, equipamentos),
    à direita o consolidado da análise.

    **Layout.** Duas faixas, não duas colunas:
    em cima mapa e consolidado lado a lado; embaixo a **tabela em largura
    inteira**. A tabela tem oito colunas e, espremida numa meia-página, ganhava
    rolagem horizontal — e rolagem horizontal em tabela é onde o dado se esconde.
    A largura inteira é também o que abriu espaço para a coluna de endereço.

    **ADR-034:** tudo empilhado em largura total — "O que esta regra verifica",
    card, consolidado, mapa de 520 px com a legenda, tabela e JSON.
    """
    _banner_veredito(r, detalhe)
    _faixa_territorio(r, detalhe)
    st.markdown("---")
    _faixa_tabela(detalhe)
    secao_outras_informacoes()
    _json_bruto(r)


def _faixa_territorio(r: dict, detalhe: dict, *, sufixo: str = "") -> None:
    """O consolidado da análise e, abaixo, o mapa — empilhados (ADR-034 (a)).

    Lado a lado, em notebook, o mapa e o consolidado se esmagavam; empilhados,
    cada um tem a largura inteira, e o mapa fica com a altura única de
    relatório (ADR-034 (b)). A legenda continua numa faixa própria logo abaixo
    do mapa (:func:`_faixa_legenda`), material de consulta.
    """
    st.subheader("Resultado da análise")
    painel_enq_resumo(detalhe, r)

    st.subheader("Terreno e equipamentos no território")
    _mapa.mapa_resultado(
        detalhe, chave=f"mapa_rel__{r.get('requisito','')}{sufixo}")
    _faixa_legenda(detalhe)


def _faixa_legenda(detalhe: dict) -> None:
    """Faixa da legenda, em largura inteira, abaixo do mapa e do consolidado.

    Reúne o que antes ficava espremido sob o mapa: o recorte que o mapa exibe, os
    dois círculos tracejados e as cores dos pinos. Vem depois do texto do
    consolidado de propósito — é material de consulta, lido quando o olho volta do
    mapa com uma dúvida, não na primeira passada.

    A legenda dos círculos continua condicionada ao ``detalhe`` (é ele que tem o
    limiar e o raio), e o externo segue rotulado como pré-seleção e **não**
    critério — o mal-entendido do R5a, que esta legenda existe para não repetir.
    """
    avaliados = [e for e in (detalhe.get("equipamentos") or []) if e.get("no_raio")]
    total = len(detalhe.get("equipamentos") or [])

    st.caption(
        f"O mapa exibe os **{len(avaliados)}** equipamento(s) dentro do raio "
        f"de busca; os demais **{max(total - len(avaliados), 0)}** avaliados "
        "estão na tabela abaixo. O terreno aparece como poligonal ou como ponto, "
        "conforme o insumo que o originou.")
    _mapa.legenda_circulos(detalhe)
    _mapa.legenda_cores()
    painel_enq_consulta(detalhe)


def _faixa_tabela(detalhe: dict) -> None:
    """Segunda faixa: os equipamentos avaliados, em largura inteira."""
    st.subheader("Equipamentos avaliados")
    painel_enq_equipamentos(detalhe)


def _json_bruto(*objetos: dict) -> None:
    with st.expander("Dados brutos (JSON)"):
        for obj in objetos:
            st.json(obj)


# ---------------------------------------------------------------------------
# Requisito agregado — um relatório por requisito da Portaria
# ---------------------------------------------------------------------------

def _relatorio_requisito_agregado(r: dict, detalhe: dict) -> None:
    """Relatório ÚNICO do requisito-pai (ENQ-010, ENQ-011).

    A unidade é o requisito, não a linha: se
    conformidade e cobertura contam **requisitos da Portaria**, o relatório tem
    de ter a mesma unidade. Antes, a história de um requisito ficava espalhada em
    três telas — a distância no relatório da alternativa A, a remessa no da B, e o
    intervalo no do pai.

    As alternativas **não** têm mais botão próprio na tela de análise; elas são
    seções desta página. O mapa e a tabela de escolas vêm do ``detalhe`` da
    alternativa medida, que viaja no mesmo ``relatorio.json`` — a regra remetida
    não carrega dado nenhum, de propósito (ver ``core/regras/base/remessa.py``).

    **Ordem da página.** O mapa e a lista vêm
    PRIMEIRO, logo abaixo do veredito; a mecânica da decisão — o intervalo, a
    tabela de alternativas e o detalhamento da alternativa remetida — fica num
    **expander recolhido**. A versão anterior empilhava tudo isso antes do mapa e
    empurrava para baixo o que interessa em primeiro lugar, deixando o relatório do
    requisito agregado bem mais longo que o de ENQ-009 sem necessidade. A mecânica
    continua a um clique, para quem precisa auditar — sob
    "Outras informações", no fim da página, como em todo relatório (ADR-034).
    """
    membros = st.session_state.get(chaves.MEMBROS_SELECIONADOS) or []
    if porte.eh_porte(membros):
        _relatorio_porte(r, detalhe, membros)
        return
    if absortancia.eh_absortancia(membros):
        _relatorio_absortancia(r, detalhe, membros)
        return
    medida = _membro_por_tipo(membros, "distancia_equipamento")

    _banner_veredito(r, detalhe, _criterio_agregacao(detalhe, membros))

    if medida is not None:
        det = medida.get("detalhe") or {}
        _faixa_territorio(medida, det, sufixo="__pai")
        st.markdown("---")
        _faixa_tabela(det)
        # A armadilha: a lista ao lado de uma alternativa não avaliável
        # pode ser lida como se ELA tivesse sido medida. O rótulo desfaz isso.
        st.caption(
            f"Este é o conjunto de equipamentos do requisito, medido pela "
            f"alternativa **{medida.get('requisito', '')}** — "
            f"{medida.get('descricao', '')}. As distâncias nada dizem sobre as "
            "demais alternativas.")
    elif membros:
        st.info("Nenhuma alternativa deste requisito produziu medição de "
                "distância nesta análise, então não há mapa nem lista de "
                "equipamentos a exibir.", icon=":material/map:")

    secao_outras_informacoes()
    _como_foi_decidido(detalhe, membros)
    _json_bruto(r, *membros)


def _relatorio_porte(r: dict, detalhe: dict, membros: list[dict]) -> None:
    """Relatório do EMP-025 (ADR-034): o "e" dos dois limites do porte, sem
    mapa — o insumo é a população do município, não uma geometria."""
    individual = porte.membro(membros, porte.ID_INDIVIDUAL)
    contiguos = porte.membro(membros, porte.ID_CONTIGUOS)
    det_ind = individual.get("detalhe") or {}

    faixa_de_avisos(porte.avisos_porte(det_ind))
    card_verificacao(r, detalhe, porte.criterio_porte(det_ind))
    st.markdown(porte.CONTEXTO_PORTE)
    chave = st.session_state.get(chaves.CHAVE_SELECIONADA)
    municipio = qualificacao.municipio(relatorios.ler(chave)) if chave else {}
    porte.painel_resultado(det_ind, individual, contiguos, municipio)
    porte.painel_consulta(det_ind, contiguos)
    secao_outras_informacoes()
    porte.painel_decisao(detalhe, membros)
    _json_bruto(r, *membros)


def _relatorio_absortancia(r: dict, detalhe: dict, membros: list[dict]) -> None:
    """Relatório do EDI-019/EDI-024 (ADR-034): os limites por zona, a zona do
    município, os revestimentos avaliados e a cena 3D com a caixa de cada
    revestimento na cor do seu resultado."""
    ramos = absortancia.ramos(membros)
    chave = st.session_state.get(chaves.CHAVE_SELECIONADA)
    municipio = qualificacao.municipio(relatorios.ler(chave)) if chave else {}

    faixa_de_avisos(absortancia.avisos_absortancia(ramos))
    card_verificacao(r, detalhe, absortancia.criterio_absortancia(
        ramos, absortancia.maior_absortancia(ramos)))
    st.markdown(absortancia.CONTEXTO_ABSORTANCIA)
    if absortancia.eh_telhado(ramos):
        st.markdown(absortancia.CONTEXTO_TELHADO)
    absortancia.painel_resultado(ramos, municipio)
    _cena_revestimentos(chave, ramos)
    secao_outras_informacoes()
    absortancia.painel_decisao(detalhe, ramos)
    absortancia.painel_populacao(ramos)
    _json_bruto(r, *membros)


def _cena_revestimentos(chave: str, ramos: list[dict]) -> None:
    """A cena da absortância: os revestimentos que entraram na verificação,
    cada um na cor do resultado sob o limite que decide (ADR-034), com a
    caixa que a conversão gravou (ADR-001)."""
    viz = conversao_3d.carregar_payload_viz(chave, publicar_glb=True)
    itens = revestimentos_com_caixas(absortancia.revestimentos_para_cena(ramos),
                                     (viz or {}).get("revestimentos") or [])
    st.subheader("Revestimentos no modelo")
    components.iframe(gravar_cena(viz, ajustes=True, revestimentos=itens),
                      height=ALTURA_VISUALIZACAO)
    if _modelo_grande_demais(viz):
        return
    if not (viz and viz.get("posicionavel")):
        motivo = (viz or {}).get("erro") or "sem âncora geográfica derivável"
        st.caption(f"O modelo não pôde ser posicionado no globo ({motivo}).")
        return
    com_caixas = sum(1 for i in itens if i.get("min"))
    if com_caixas:
        st.markdown(legenda_cores(), unsafe_allow_html=True)
    st.caption(absortancia.legenda_cena(itens, com_caixas))


def _modelo_grande_demais(viz: dict) -> bool:
    """Avisa, sob a cena, que o modelo convertido passou do que o app entrega
    ao navegador, e devolve se foi o caso. Aviso ``warning`` (ADR-034
    (c)): o relatório segue válido, só a cena fica sem o modelo."""
    if not (viz or {}).get("glb_grande_demais"):
        return False
    st.warning(
        f"**O modelo convertido é grande demais para a cena.** Ele tem "
        f"{viz.get('glb_mb', '—')} MB, acima dos 200 MB que a aplicação "
        "consegue entregar ao navegador, então a cena mostra só o mapa. O "
        "resultado da verificação não muda. Simplificar a geometria dos "
        "elementos mais detalhados no modelo autoral reduz o tamanho.",
        icon=":material/warning:")
    return True


def _como_foi_decidido(detalhe: dict, membros: list[dict]) -> None:
    """A mecânica da decisão, recolhida: intervalo, alternativas e remessas.

    O rótulo do expander carrega o essencial (quantas alternativas confirmadas
    contra o mínimo), para quem não abrir não perder a informação — e para quem
    abrir saber que vai encontrar o detalhamento de cada alternativa.
    """
    n_conf = detalhe.get("n_conf", 0)
    n_pot = detalhe.get("n_pot", 0)
    k = detalhe.get("k", 1)
    total = detalhe.get("total_membros", len(membros))
    intervalo = f"{n_conf}" if n_conf == n_pot else f"{n_conf} a {n_pot}"
    rotulo = (f"Como este requisito foi decidido — {intervalo} de {total} "
              f"alternativa(s) atende(m), mínimo {k}")

    with st.expander(rotulo, expanded=False, icon=":material/rule:"):
        painel_agregacao(detalhe)
        for membro in membros:
            det = membro.get("detalhe") or {}
            if det.get("tipo") != "remetida":
                continue
            st.markdown("---")
            st.markdown(f"**{membro.get('requisito', '')} — "
                        f"{membro.get('descricao', '')}**")
            painel_remetida(det)


def _membro_por_tipo(membros: list[dict], tipo: str) -> dict | None:
    """Primeiro membro cujo diagnóstico é do tipo pedido, ou ``None``."""
    for membro in membros:
        if (membro.get("detalhe") or {}).get("tipo") == tipo:
            return membro
    return None


def _banner_veredito(r: dict, detalhe: dict,
                     criterio: str | None = None) -> None:
    """O card de verificação (ADR-034) com o CRITÉRIO da norma.

    ``criterio`` acrescenta, abaixo da descrição, o parâmetro objetivo do
    requisito — o limiar de distância e o que foi medido contra ele. Sem isso o
    card diria *o que* é o requisito e não *o que ele exige*. Ver
    :func:`_criterio_distancia`.
    """
    if criterio is None:
        criterio = _criterio_distancia(detalhe)
    card_verificacao(r, detalhe, criterio)


def _criterio_distancia(detalhe: dict) -> str:
    """O parâmetro objetivo de uma regra de distância, em linguagem normativa.

    Montado dos campos que a própria regra gravou (``limiar_m``, ``rotulo_ciclo``,
    o determinante), nunca reescrito à mão — mesma razão do ``criterio_aceite``:
    uma legenda digitada na tela envelhece em silêncio quando o parâmetro muda.
    """
    if (detalhe or {}).get("tipo") != "distancia_equipamento":
        return ""
    limiar = detalhe.get("limiar_m") or 0.0
    if not limiar:
        return ""

    ciclo = detalhe.get("rotulo_ciclo") or "equipamento exigido"
    texto = (f"<b>Exige:</b> distância caminhável máxima de "
             f"<b>{_mil(limiar)} m</b>, computada a partir do centro do terreno, "
             f"até {ciclo}")

    det = detalhe.get("determinante") or {}
    metros = det.get("metros")
    if metros is not None:
        from app.servicos import roteamento as rot
        metrica = rot.ROTULO_METRICA.get(det.get("metrica"), det.get("metrica") or "")
        texto += (f". <b>Medido:</b> {_mil(metros)} m no equipamento mais próximo"
                  + (f" ({metrica})" if metrica else ""))
    return texto + "."


def _criterio_agregacao(detalhe: dict, membros: list[dict]) -> str:
    """O critério do requisito-pai: o "ou" da norma e o limiar de cada via.

    Lista as alternativas com o parâmetro de cada uma, para o leitor ver o
    requisito da Portaria inteiro sem abrir o expander — o item 3.b e o 3.c são
    "distância OU transporte", e mostrar só uma das vias contaria meia norma.
    """
    k = (detalhe or {}).get("k", 1)
    total = (detalhe or {}).get("total_membros", len(membros))
    vias = []
    for membro in membros:
        det = membro.get("detalhe") or {}
        rid = membro.get("requisito", "")
        if det.get("tipo") == "distancia_equipamento" and det.get("limiar_m"):
            vias.append(f"<b>{rid}</b> distância caminhável até "
                        f"<b>{_mil(det['limiar_m'])} m</b>")
        elif det.get("tipo") == "remetida":
            vias.append(f"<b>{rid}</b> {det.get('insumo') or 'via não avaliável'} "
                        "(não avaliável)")
        else:
            vias.append(f"<b>{rid}</b>")
    if not vias:
        return ""
    conector = " <b>ou</b> " if k == 1 and total > 1 else " · "
    prefixo = ("<b>Exige:</b> qualquer uma das vias — " if k == 1
               else f"<b>Exige:</b> ao menos {k} de {total} — ")
    return prefixo + conector.join(vias) + "."


def _mil(valor: float) -> str:
    """Metros com separador de milhar no padrão brasileiro."""
    return f"{float(valor):,.0f}".replace(",", ".")


main()
