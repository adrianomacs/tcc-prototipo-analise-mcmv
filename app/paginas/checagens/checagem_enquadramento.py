"""Checagem — Enquadramento (GIS only): definição do terreno.

Recorte: equipamentos de educação. A tela entrega a **entrada** da checagem
— o terreno —, que é o insumo de todas as medidas do eixo; as regras ENQ
avaliam depois, e a tabela do grupo mostra o estado de cada uma.

Anatomia do ADR-034 — a página é a referência dele: título, "O que esta
checagem verifica", frase do empreendimento, faixa de avisos e as duas seções,
**Informações de entrada** (o terreno) e **Cobertura e análise**. A
definição do terreno é a exceção declarada ao empilhamento: o usuário desenha
ou digita e vê a resposta ao lado (ADR-034 (a)).

Fluxo da tela (cabeçalho do empreendimento -> terreno -> cobertura prevista):

  1. **ADR-004**: a UF/Município deixou
     de ter formulário próprio aqui — vem do ``Empreendimento`` declarado em
     "Informações Gerais" (2.1.1), mostrado no cabeçalho no topo da tela.
     Confirmar o terreno grava-o NO empreendimento (``empreendimento.json``);
     trocar o município com terreno confirmado é aviso e oferta de
     "Redefinir terreno" em 2.1.1 (regra 1 do §4.3), não mais nesta tela.
  2. Definição do terreno em quatro modos — desenhar a poligonal, enviar o
     modelo IFC, importar o CSV da poligonal do terreno, ou marcar o centro no
     mapa. Neste último o clique preenche a latitude e a longitude, que o
     usuário ainda pode ajustar à mão, e o terreno é sempre um ponto
     declarado (``terreno_de_coordenadas``). Enquanto o usuário desenha, um
     painel mostra ao vivo as medidas e os avisos.
  3. **Confirmar terreno** congela a geometria e grava o empreendimento. Os
     dois passos são deliberados: o componente de mapa devolve o desenho a
     cada reexecução do script e, sem o congelamento, ele se perde. Confirmar
     o terreno não é analisar — a análise segue de um clique só.

Execução: via ``streamlit run app/main.py``.
"""

from __future__ import annotations

import streamlit as st

from app.componentes import acao as acao_mod
from app.componentes import avisos
from app.componentes import explicacao_grupo as explicacao_mod
from app.componentes import mapa as _mapa
from app.componentes.cabecalho_empreendimento import cabecalho_empreendimento
from app.estado import chaves
from app.navegacao import arvore
from app.servicos import declaracoes as dec
from app.servicos import empreendimento as emp_mod
from app.servicos import grupos, territorio, uploads
from app.servicos.territorio import (
    ROTULO_NIVEL,
    ROTULO_ORIGEM,
    ROTULO_PRECISAO,
    Terreno,
    formatar_numero,
)

CHAVE = "enquadramento"
GRUPO_ID = "enquadramento"
ORIGEM = arvore.PAGINA_CHECAGEM_ENQUADRAMENTO
CENTRO_FALLBACK = (-15.7939, -47.8828)   # Brasília, sem município declarado

MODOS = {
    "Desenhar a poligonal no mapa": "desenhar",
    "Enviar o modelo IFC": "ifc",
    "Importar CSV da poligonal do terreno": "csv",
    "Marcar o centro no mapa": "ponto",
}

# Estado do modo de ponto. ``CHAVE_PONTO`` guarda a coordenada que o usuário
# definiu (por clique ou digitando) e é ela, não o valor-padrão dos campos, que
# diz se há ponto a mostrar e a confirmar. ``CHAVE_CLIQUE`` guarda o último
# clique já aplicado aos campos: o mapa devolve o mesmo ``last_clicked`` a cada
# reexecução, e sem essa marca um clique velho sobrescreveria o ajuste feito
# depois à mão.
CHAVE_PONTO = f"ponto__{CHAVE}"
CHAVE_CLIQUE = f"clique__{CHAVE}"
CHAVE_LAT = f"lat__{CHAVE}"
CHAVE_LON = f"lon__{CHAVE}"

# Limites de sanidade da área — avisam, não bloqueiam (um terreno pode ser uma
# gleba grande; o que não pode é o usuário não perceber que errou a escala).
AREA_MINIMA_M2 = 50.0
AREA_MAXIMA_M2 = 5_000_000.0


def _empreendimento_corrente():
    """O `Empreendimento` da sessão — mesmo padrão de `informacoes_gerais.
    _empreendimento_corrente()`, para as duas telas nunca divergirem sobre
    qual objeto está em memória."""
    guardado = st.session_state.get(chaves.EMPREENDIMENTO)
    if guardado is not None:
        return guardado
    carregado = emp_mod.carregar()
    st.session_state[chaves.EMPREENDIMENTO] = carregado
    return carregado


def _declaracoes_de(emp) -> dict:
    """A localização do empreendimento, no formato que `grupos.
    ids_executaveis`/`analise.analisar_enquadramento` já esperavam (a origem é o
    `Empreendimento`)."""
    if emp.localizacao is None:
        return {}
    return {dec.UF: emp.localizacao.uf, dec.MUNICIPIO: emp.localizacao.municipio,
            dec.MUNICIPIO_IBGE: emp.localizacao.codigo_ibge}


@st.cache_data(show_spinner=False)
def _centro_municipio(codigo_ibge: str):
    return territorio.centro_municipio(codigo_ibge)


def main() -> None:
    grupo = grupos.carregar_grupo(GRUPO_ID)
    if grupo is None:
        st.error("Grupo 'enquadramento' não encontrado em "
                 "config/grupos_requisitos.yaml.")
        return

    explicacao_mod.explicacao_grupo(grupo, em_expander=True, mostrar_situacao=True)

    emp = _empreendimento_corrente()
    cabecalho_empreendimento(emp)
    declaracoes = _declaracoes_de(emp)
    avisos.faixa_de_avisos([_aviso_municipio_ausente(declaracoes),
                            avisos.aviso_de_rede()])

    st.subheader("Informações de entrada")
    _definicao_do_terreno(emp, declaracoes)

    st.divider()
    st.subheader("Cobertura e análise")
    _cobertura(grupo, emp, declaracoes)


def _aviso_municipio_ausente(declaracoes: dict) -> avisos.Aviso | None:
    """Pré-condição da faixa: sem município declarado o mapa abre longe do
    terreno e a confirmação não confronta o centro com os limites municipais."""
    if declaracoes.get(dec.MUNICIPIO_IBGE):
        return None
    return avisos.Aviso(
        avisos.ALERTA, "Município ainda não declarado.",
        "O mapa abre fora da região do empreendimento e o terreno não é "
        "confrontado com os limites municipais.",
        "Declare-o em Informações Gerais.")


# ---------------------------------------------------------------------------
# Definição do terreno
# ---------------------------------------------------------------------------

def _terreno_corrente(emp):
    """Terreno confirmado — agora lido direto do `Empreendimento`;
    antes desta fase vinha de `artefatos/terreno.json` via `territorio.
    artefato.ler`, que o repositório do empreendimento já migra sozinho na
    primeira leitura (ver `core/infra/persistencia/empreendimento_json.py`).
    """
    return emp.terreno


def _definicao_do_terreno(emp, declaracoes: dict) -> None:
    confirmado = _terreno_corrente(emp)

    if confirmado is not None:
        _terreno_confirmado(emp, confirmado)
        return

    rotulo = st.radio("Como você quer definir o terreno?", list(MODOS),
                      horizontal=True, key=f"modo__{CHAVE}",
                      captions=["A poligonal habilita todas as medidas",
                                "Extrai o terreno do IfcSite do modelo",
                                "A tabela de vértices E/N da implantação",
                                "Rápido e ajustável, mas sem geometria do lote"])
    modo = MODOS[rotulo]

    centro, zoom = _centro_inicial(declaracoes)
    contorno = _contorno(declaracoes)

    if modo == "ifc":
        _entrada_ifc(emp, declaracoes, centro, zoom, contorno)
        return
    if modo == "csv":
        _entrada_csv(emp, declaracoes, centro, zoom, contorno)
        return
    if modo == "ponto":
        _entrada_ponto(emp, declaracoes, centro, zoom, contorno)
        return

    col_mapa, col_painel = st.columns([3, 2], gap="medium")
    with col_mapa:
        payload = _mapa.mapa(centro=centro, modo=modo, zoom=zoom,
                             contorno_municipal=contorno,
                             chave=f"mapa_{modo}__{CHAVE}")
        provisorio = _do_desenho(payload)

    with col_painel:
        _painel_provisorio(modo, provisorio, emp, declaracoes)


def _entrada_ponto(emp, declaracoes: dict, centro, zoom, contorno) -> None:
    """Marcar o centro no mapa e ajustar as coordenadas, num modo só.

    O mapa é desenhado ANTES do formulário, e é a posição vinda da sessão que o
    move: o marcador acompanha o que o usuário clicou ou digitou, que é o ponto
    de mostrar o mapa neste modo (ele precisa VER se acertou o lugar). O clique
    só chega depois de o mapa ser desenhado, então é aplicado aos campos
    aqui, antes de eles serem criados na execução seguinte (o Streamlit recusa
    a escrita numa chave de widget já desenhado), e a tela se reexecuta uma vez
    para o marcador ir ao lugar novo.
    """
    ponto = st.session_state.get(CHAVE_PONTO)
    previa = _previa_do_ponto(ponto)

    col_mapa, col_painel = st.columns([3, 2], gap="medium")
    with col_mapa:
        payload = _mapa.mapa(
            centro=ponto or centro, modo="clicar",
            zoom=_mapa.ZOOM_TERRENO if previa else zoom,
            contorno_municipal=contorno, terreno=previa,
            chave=f"mapa_ponto__{CHAVE}")

    clique = _clique_novo(payload)
    if clique is not None:
        st.session_state[CHAVE_PONTO] = clique
        st.session_state[CHAVE_LAT], st.session_state[CHAVE_LON] = clique
        st.rerun()

    with col_painel:
        provisorio = _formulario_coordenadas(ponto, centro)
        _painel_provisorio("ponto", provisorio, emp, declaracoes)


def _previa_do_ponto(ponto):
    """O terreno-ponto a mostrar no mapa, ou ``None`` se ainda não há ponto."""
    if ponto is None:
        return None
    try:
        return territorio.de_mapa.terreno_de_coordenadas(*ponto)
    except ValueError:
        return None


def _clique_novo(payload) -> tuple[float, float] | None:
    """O clique que ainda não foi aplicado aos campos, ou ``None``.

    Arredonda para a precisão dos campos (seis casas), para o valor do clique e
    o exibido serem o mesmo número. Sem ``last_clicked`` (componente zerado), a
    marca do último clique é esquecida.
    """
    dados = (payload or {}).get("last_clicked") or {}
    lat, lon = dados.get("lat"), dados.get("lng", dados.get("lon"))
    if lat is None or lon is None:
        st.session_state.pop(CHAVE_CLIQUE, None)
        return None
    clique = (round(float(lat), 6), round(float(lon), 6))
    if st.session_state.get(CHAVE_CLIQUE) == clique:
        return None
    st.session_state[CHAVE_CLIQUE] = clique
    return clique


@st.cache_data(show_spinner=False)
def _resolver_ifc(caminho: str, digest: str):
    """Cascata do IFC, cacheada pelo conteúdo do arquivo.

    O cache não é luxo: sem ele o modelo seria reaberto e reprocessado a cada
    reexecução do script — e um IFC de dezenas de MB tornaria a tela inusável.
    A chave é o digest do conteúdo, então trocar o arquivo invalida o cache.
    Devolve tipos serializáveis (o Terreno vai e volta pelo mesmo contrato do
    artefato, o que exercita a serialização de graça).
    """
    res = territorio.de_ifc.resolver_arquivo(caminho)
    return ((res.terreno.to_dict() if res.ok else None),
            list(res.diagnostico), res.detalhe)


def _entrada_ifc(emp, declaracoes: dict, centro, zoom, contorno) -> None:
    """Upload do modelo, cascata do IfcSite e painel de diagnóstico."""
    import hashlib

    arquivo = st.file_uploader(
        "Modelo IFC contendo o terreno (IfcSite)", type=["ifc"],
        key=f"ifc__{CHAVE}",
        help="O terreno é extraído do IfcSite. O modelo não é convertido para "
             "visualização 3D nesta tela — é lido apenas para derivar o terreno.")

    if arquivo is None:
        col_mapa, col_painel = st.columns([3, 2], gap="medium")
        with col_mapa:
            _mapa.mapa(centro=centro, modo="visualizar", zoom=zoom,
                       contorno_municipal=contorno, chave=f"mapa_ifc__{CHAVE}")
        with col_painel:
            # A escala explicada, com a referência da lista
            # de referências, antes do diagnóstico técnico que a cita.
            avisos.mostrar_aviso(avisos.Aviso(
                avisos.ORIENTACAO, "Envie o modelo IFC.",
                "O terreno é lido do limite do lote gravado no modelo, o "
                "IfcSite. Para cair no lugar certo do mapa, o modelo precisa "
                "estar georreferenciado no nível 50 da escala LoGeoRef, "
                "proposta por Clemen e Görne (2019), que classifica como o "
                "arquivo IFC registra a própria localização — nesse nível, com "
                "o sistema de coordenadas e os parâmetros de conversão para "
                "ele. Sem o limite desenhado, o terreno vira um ponto na "
                "coordenada do IfcSite."))
            avisos.aviso_premissa_ifc4()
        return

    digest = hashlib.sha1(arquivo.getbuffer()).hexdigest()[:16]
    caminho = uploads.salvar_upload(arquivo, "entradas/ifc", arquivo.name)
    with st.spinner("Lendo o modelo e extraindo o terreno…"):
        dados, diagnostico, detalhe = _resolver_ifc(caminho, digest)

    provisorio = Terreno.from_dict(dados) if dados else None

    col_mapa, col_painel = st.columns([3, 2], gap="medium")
    with col_mapa:
        if provisorio is not None:
            c, z = _mapa.enquadrar(provisorio)
            _mapa.mapa(centro=c, modo="visualizar", zoom=z,
                       contorno_municipal=contorno, terreno=provisorio,
                       chave=f"mapa_ifc__{CHAVE}")
        else:
            _mapa.mapa(centro=centro, modo="visualizar", zoom=zoom,
                       contorno_municipal=contorno, chave=f"mapa_ifc__{CHAVE}")

    with col_painel:
        # Antes do diagnóstico, e fora do expander: um schema aquém da premissa
        # explica tudo o que vem depois, e o expander pode estar recolhido.
        avisos.aviso_premissa_ifc4(detalhe.get("schema", ""))
        _painel_diagnostico_ifc(detalhe)
        if provisorio is None:
            st.error("Não foi possível derivar o terreno deste modelo.",
                     icon=":material/error:")
            for msg in diagnostico:
                st.markdown(f"- {msg}")
            st.caption("Os modos de mapa continuam disponíveis como **fonte "
                       "alternativa de insumo** — não como conserto do modelo.")
            return
        _painel_provisorio("ifc", provisorio, emp, declaracoes)


def _painel_diagnostico_ifc(detalhe: dict) -> None:
    """O que a cascata encontrou no modelo — sempre visível, deu certo ou não."""
    lg = detalhe.get("logeoref") or {}
    nivel = lg.get("nivel")
    alvo = lg.get("alvo", territorio.de_ifc.NIVEL_EXIGIDO)
    atinge = (nivel or 0) >= alvo and lg.get("crs_consistente")
    cor = ":green" if atinge else ":orange"

    with st.expander("Diagnóstico do modelo", expanded=not atinge,
                     icon=":material/troubleshoot:"):
        st.markdown(
            f"**Georreferenciamento:** {cor}[LoGeoRef {nivel} de {alvo}] · "
            f"CRS `{detalhe.get('epsg') or '—'}`"
            + (" · consistente" if lg.get("crs_consistente") else " · inconsistente"))
        if detalhe.get("crs_aviso"):
            st.caption(detalhe["crs_aviso"])

        sites = detalhe.get("sites") or []
        st.markdown(f"**IfcSite:** {len(sites)} encontrado(s), "
                    f"{detalhe.get('sites_com_geometria', 0)} com geometria")
        for s in sites:
            reps = ", ".join(f"{r.get('identificador') or '?'}"
                             f"/{r.get('tipo') or '?'}"
                             for r in (s.get("representacoes") or [])) or "sem representação"
            st.caption(f"`{s.get('global_id')}` {s.get('nome') or ''} — {reps}"
                       + (" — com lat/lon" if s.get("tem_lat_lon") else ""))

        if detalhe.get("metodo_geometria"):
            st.markdown(f"**Geometria:** {detalhe['metodo_geometria']}")
        if detalhe.get("area_pset_m2"):
            st.markdown(
                f"**Área declarada no IFC** (Pset_SiteCommon): "
                f"{formatar_numero(detalhe['area_pset_m2'])} m²"
                + (f" · desvio de {detalhe.get('desvio_area', 0)*100:.1f}% "
                   "em relação à medida" if detalhe.get("desvio_area") is not None else ""))
        if detalhe.get("matricula"):
            st.markdown(f"**Matrícula no IFC:** {detalhe['matricula']}")
            # A fonte anda junto: com o IFC4.3 depreciando o atributo, "de onde
            # veio" passou a distinguir um modelo novo de um legado, e quem
            # confere a matrícula no cartório quer saber qual campo leu.
            if detalhe.get("matricula_fonte"):
                st.caption(f"Origem: `{detalhe['matricula_fonte']}`")
        if detalhe.get("land_id"):
            st.markdown(f"**Identificação do lote (LandID):** {detalhe['land_id']}")
        if detalhe.get("escala_comprimento"):
            st.caption(f"Escala de comprimento do projeto: "
                       f"{detalhe['escala_comprimento']} (para metros).")


# ---------------------------------------------------------------------------
# Entrada por CSV de memorial descritivo (ADR-029)
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def _resolver_csv(caminho: str, digest: str, epsg: str, epsg_fonte: str,
                  area_txt: str):
    """Leitura do memorial, cacheada pelo conteúdo e pelos parâmetros.

    Mesma razão do cache do IFC: sem ele o arquivo seria relido e reprojetado
    a cada reexecução do script. A chave inclui o digest, o EPSG e a área
    declarada — mudar qualquer um invalida o cache. Devolve tipos
    serializáveis (o `Terreno` viaja pelo contrato do artefato).
    """
    leitura = territorio.de_memorial.ler(
        caminho, epsg=epsg, epsg_fonte=epsg_fonte,
        area_declarada_m2=area_txt or None)
    detalhe = {
        "dialeto": leitura.dialeto,
        "colunas": leitura.colunas_detectadas,
        "faltando": list(leitura.faltando),
        "rejeitadas": list(leitura.rejeitadas),
        "vertices": [v.nome for v in leitura.vertices],
        "procedencia": dict(leitura.terreno.procedencia) if leitura.terreno else {},
    }
    return ((leitura.terreno.to_dict() if leitura.terreno else None),
            leitura.erro, detalhe)


def _parametros_csv(declaracoes: dict) -> tuple[str, str, str]:
    """As duas declarações do modo CSV: o CRS (ADR-029) e a área do memorial.

    O CSV não carrega CRS e E/N não permitem deduzi-lo — o EPSG é declarado
    aqui, com o padrão sugerido pelo município declarado. A área é opcional e,
    quando informada, é conferida contra a área medida dos vértices.
    """
    codigo = str(declaracoes.get(dec.MUNICIPIO_IBGE) or "")
    sugerido = territorio.epsg_sugerido(codigo) if codigo else None

    opcoes = territorio.de_memorial.epsgs_utm_sirgas()
    codigos = [c for c, _ in opcoes]
    rotulos = dict(opcoes)
    OUTRO = "outro"
    rotulos[OUTRO] = "Outro código EPSG…"
    if sugerido in rotulos:
        rotulos[sugerido] += " — sugerido pelo município declarado"

    indice = codigos.index(sugerido) if sugerido in codigos else 0
    escolha = st.selectbox(
        "Sistema de coordenadas do memorial (CRS)", codigos + [OUTRO],
        index=indice, format_func=lambda c: rotulos.get(c, c),
        key=f"epsg__{CHAVE}",
        help="O arquivo não carrega o CRS, e coordenadas E/N não permitem "
             "deduzi-lo — a declaração é sua. A sugestão vem do fuso e "
             "hemisfério do município declarado.")
    if escolha == OUTRO:
        epsg = st.text_input("Código EPSG (CRS projetado)",
                             placeholder="ex.: EPSG:31982",
                             key=f"epsg_livre__{CHAVE}").strip()
        fonte = territorio.de_memorial.FONTE_EPSG_USUARIO
    else:
        epsg = escolha
        fonte = (territorio.de_memorial.FONTE_EPSG_MUNICIPIO
                 if escolha == sugerido
                 else territorio.de_memorial.FONTE_EPSG_USUARIO)

    area_txt = st.text_input(
        "Área declarada no memorial (m²) — opcional",
        placeholder="ex.: 95.907,00", key=f"area_memorial__{CHAVE}",
        help="Se informada, é conferida contra a área medida dos vértices — "
             "a checagem mais barata contra erro de digitação ou de CRS.")
    return epsg, fonte, area_txt.strip()


def _entrada_csv(emp, declaracoes: dict, centro, zoom, contorno) -> None:
    """Upload do CSV do memorial, declaração do CRS e painel de conferência."""
    import hashlib

    arquivo = st.file_uploader(
        "CSV do memorial descritivo (tabela de vértices da poligonal)",
        type=["csv"], key=f"csv_memorial__{CHAVE}",
        help="Uma linha por vértice, com coordenadas PROJETADAS (E/N em "
             "metros). Aceita o cabeçalho da planilha de cálculos do projeto "
             "de implantação (VÉRTICES / DISTÂNCIAS / LESTE / NORTE).")
    st.download_button(
        "Baixar o modelo de CSV", data=territorio.de_memorial.modelo_csv(),
        file_name="modelo_memorial_descritivo.csv", mime="text/csv",
        key=f"modelo_csv__{CHAVE}")
    epsg, epsg_fonte, area_txt = _parametros_csv(declaracoes)

    col_mapa, col_painel = st.columns([3, 2], gap="medium")

    if arquivo is None:
        with col_mapa:
            _mapa.mapa(centro=centro, modo="visualizar", zoom=zoom,
                       contorno_municipal=contorno, chave=f"mapa_csv__{CHAVE}")
        with col_painel:
            st.info("Envie o CSV com os vértices do memorial. A poligonal "
                    "levantada é o nível máximo de terreno — as distâncias e "
                    "a área são conferidas contra o memorial antes da "
                    "confirmação.", icon=":material/upload_file:")
        return

    if not epsg:
        with col_painel:
            st.warning("Informe o código EPSG do memorial para importar.",
                       icon=":material/edit_location:")
        return

    digest = hashlib.sha1(arquivo.getbuffer()).hexdigest()[:16]
    caminho = uploads.salvar_upload(arquivo, "entradas/gis", arquivo.name)
    with st.spinner("Lendo o memorial e montando a poligonal…"):
        dados, erro, detalhe = _resolver_csv(caminho, digest, epsg,
                                             epsg_fonte, area_txt)

    provisorio = Terreno.from_dict(dados) if dados else None

    with col_mapa:
        if provisorio is not None:
            c, z = _mapa.enquadrar(provisorio)
            _mapa.mapa(centro=c, modo="visualizar", zoom=z,
                       contorno_municipal=contorno, terreno=provisorio,
                       chave=f"mapa_csv__{CHAVE}")
        else:
            _mapa.mapa(centro=centro, modo="visualizar", zoom=zoom,
                       contorno_municipal=contorno, chave=f"mapa_csv__{CHAVE}")

    with col_painel:
        _painel_diagnostico_csv(detalhe, houve_erro=provisorio is None)
        if provisorio is None:
            st.error(erro or "Não foi possível montar a poligonal deste CSV.",
                     icon=":material/error:")
            return
        _painel_provisorio("csv", provisorio, emp, declaracoes)


def _painel_diagnostico_csv(detalhe: dict, *, houve_erro: bool) -> None:
    """O que a leitura encontrou no arquivo — sempre visível, deu certo ou não."""
    proc = detalhe.get("procedencia") or {}
    conf_dist = proc.get("conferencia_distancias") or {}
    problema = (houve_erro or detalhe.get("faltando")
                or detalhe.get("rejeitadas") or conf_dist.get("divergencias"))

    with st.expander("Diagnóstico da importação", expanded=bool(problema),
                     icon=":material/troubleshoot:"):
        d = detalhe.get("dialeto") or {}
        st.caption(f"Separador {d.get('separador')!r} · encoding "
                   f"{d.get('encoding')} · decimal decidido por valor")
        colunas = detalhe.get("colunas") or {}
        if colunas:
            st.markdown("**Colunas:** " + " · ".join(
                f"{campo} ← `{col}`" for campo, col in colunas.items()))
        for campo in detalhe.get("faltando") or []:
            st.markdown(f"- coluna obrigatória **{campo}** não encontrada")
        for numero, motivo in detalhe.get("rejeitadas") or []:
            st.markdown(f"- linha {numero}: {motivo}")

        vertices = detalhe.get("vertices") or []
        if vertices:
            st.markdown(f"**Vértices:** {len(vertices)} "
                        f"({', '.join(vertices)})")
        if proc.get("epsg_origem"):
            fonte = {"sugerido_do_municipio": "sugerido pelo município",
                     "informado_pelo_usuario": "informado pelo usuário"}.get(
                         proc.get("epsg_origem_fonte"), "")
            st.markdown(f"**CRS declarado:** `{proc['epsg_origem']}`"
                        + (f" ({fonte})" if fonte else ""))
        if proc.get("area_no_crs_do_memorial_m2"):
            st.markdown(
                f"**Área medida dos vértices:** "
                f"{formatar_numero(proc['area_no_crs_do_memorial_m2'])} m² no "
                f"CRS do memorial"
                + (f" · desvio de reprojeção "
                   f"{proc.get('desvio_reprojecao_ppm', 0):+.1f} ppm na "
                   f"remedida" if proc.get("desvio_reprojecao_ppm") is not None
                   else ""))
        if proc.get("area_declarada_m2") is not None:
            st.markdown(
                f"**Área declarada no memorial:** "
                f"{formatar_numero(proc['area_declarada_m2'])} m² · desvio "
                f"{proc.get('desvio_area_declarada_pct', 0):+.4f}%")
        if conf_dist:
            st.markdown(
                f"**Distâncias do memorial:** {conf_dist.get('lados_conferidos')}"
                f" de {conf_dist.get('lados_declarados')} lado(s) conferem")
            for div in conf_dist.get("divergencias") or []:
                st.caption(f"{div['de']}–{div['para']}: declarada "
                           f"{formatar_numero(div['declarada_m'])} m, "
                           f"calculada {formatar_numero(div['calculada_m'])} m")


def _do_desenho(payload):
    """Constrói o terreno provisório a partir do que o mapa devolveu."""
    if not payload:
        return None
    try:
        return territorio.de_mapa.terreno_desenhado(payload.get("all_drawings"))
    except ValueError:
        return None      # nada desenhado ainda: o painel orienta
    except Exception as exc:
        st.error(f"Não foi possível interpretar o que veio do mapa: {exc}")
        return None


def _definir_ponto_dos_campos() -> None:
    """Uma edição dos campos também define o ponto. É callback, e roda antes do
    script, então o mapa já desenha o marcador no valor digitado."""
    st.session_state[CHAVE_PONTO] = (float(st.session_state[CHAVE_LAT]),
                                     float(st.session_state[CHAVE_LON]))


def _formulario_coordenadas(ponto, centro: tuple[float, float]):
    """Os dois campos editáveis e o terreno-ponto que eles descrevem.

    Sem ponto definido os campos mostram o centro do município declarado, só
    para não nascerem vazios, e o terreno devolvido é ``None``: confirmar o
    centro do município sem ninguém ter escolhido seria confirmar sem querer.
    """
    base = ponto or centro
    st.session_state.setdefault(CHAVE_LAT, float(base[0]))
    st.session_state.setdefault(CHAVE_LON, float(base[1]))
    lat = st.number_input("Latitude (graus decimais)", min_value=-90.0,
                          max_value=90.0, step=0.0001, format="%.6f",
                          key=CHAVE_LAT, on_change=_definir_ponto_dos_campos)
    lon = st.number_input("Longitude (graus decimais)", min_value=-180.0,
                          max_value=180.0, step=0.0001, format="%.6f",
                          key=CHAVE_LON, on_change=_definir_ponto_dos_campos)
    st.caption("Clique no mapa para preencher os campos e ajuste-os se quiser. "
               "Coordenadas em WGS 84. Enquanto nada for marcado, os campos "
               "mostram o centro do município declarado.")
    if ponto is None:
        return None
    try:
        return territorio.de_mapa.terreno_de_coordenadas(lat, lon)
    except ValueError as exc:
        st.error(str(exc))
        return None


def _painel_provisorio(modo: str, provisorio, emp, declaracoes: dict) -> None:
    """Medidas ao vivo + botão de confirmação."""
    if provisorio is None:
        avisos.mostrar_aviso(avisos.Aviso(
            avisos.ORIENTACAO,
            "Defina o terreno pelo método escolhido acima.",
            _COMO_NESTE_METODO[modo]))
        return

    fora = _fora_do_municipio(modo, provisorio, declaracoes)
    if fora is not None:
        avisos.mostrar_aviso(fora)
    elif modo == "ifc":
        # O terreno segue, mas as duas posições do modelo não coincidem: o
        # usuário precisa saber de onde as distâncias vão partir.
        avisos.faixa_de_avisos([_aviso_de_divergencia(provisorio, declaracoes)])

    st.markdown("##### Terreno informado")
    if provisorio.tem_poligonal:
        c1, c2 = st.columns(2)
        c1.metric("Área", f"{formatar_numero(provisorio.area_m2, 0)} m²")
        c2.metric("Perímetro", f"{formatar_numero(provisorio.perimetro_m, 0)} m")
        st.caption("Confira a área contra a matrícula ou o memorial antes de "
                   "confirmar — é a checagem mais barata contra erro de escala. "
                   "As medidas se atualizam ao editar a poligonal no mapa.")
    lat, lon = provisorio.centro_wgs84
    # Os dados de procedência numa legenda só (ADR-034 (c)): o centro é o que o
    # usuário confere no mapa; nível, precisão e sistema são segundo plano.
    st.markdown(f"**Centro:** {lat:.6f}, {lon:.6f}")
    st.caption(f"{ROTULO_NIVEL[provisorio.nivel].capitalize()} · precisão "
               f"{ROTULO_PRECISAO[provisorio.precisao]} · medido em "
               f"{provisorio.crs_metrico} (fuso "
               f"{provisorio.procedencia.get('fuso_utm', '?')})")

    _avisos_do_terreno(provisorio, confirmado=False)

    if st.button("Confirmar terreno", type="primary", use_container_width=True,
                 key=f"confirmar__{CHAVE}", disabled=fora is not None):
        _confirmar(emp, provisorio, declaracoes)


_COMO_NESTE_METODO = {
    "ifc": "Envie o modelo IFC acima; o terreno é extraído dele.",
    "csv": "Envie acima o CSV com os vértices do memorial descritivo.",
    "desenhar": "Trace o perímetro com a ferramenta de polígono ou retângulo "
                "da barra do mapa. Para ajustar, use o lápis, arraste os "
                "vértices e confirme em **Salvar**.",
    "ponto": "Clique no mapa, sobre o centro do terreno. A latitude e a "
             "longitude se preenchem, e você pode ajustá-las nos campos.",
}


def _fora_do_municipio(modo: str, terreno, declaracoes: dict
                       ) -> avisos.Aviso | None:
    """O confronto com os limites municipais ANTES do clique (ADR-034 (c)):
    o problema nasce do insumo, então aparece junto dele, e o botão fica
    desabilitado — clicar só serviria para recusar. Só com a malha já em
    cache, para o render nunca depender de rede; sem ela, o confronto segue
    acontecendo em `_confirmar`, como antes."""
    codigo = str(declaracoes.get(dec.MUNICIPIO_IBGE) or "")
    if not codigo or territorio.malha_em_cache(codigo) is None:
        return None
    lat, lon = terreno.centro_wgs84
    if _dentro_do_municipio(codigo, round(lat, 7), round(lon, 7)) is not False:
        return None
    municipio = (f"{declaracoes.get(dec.MUNICIPIO, '')}/"
                 f"{declaracoes.get(dec.UF, '')}").strip("/")
    if modo == "ifc":
        # Com a divergência registrada, a causa é conhecida e a mensagem a diz;
        # a genérica fica para o modelo sem a segunda posição.
        especifico = _aviso_de_divergencia(terreno, declaracoes)
        if especifico is not None:
            return especifico
        return avisos.Aviso(
            avisos.ERRO, f"O terreno cai fora de {municipio}.",
            "A localização lida do modelo está em outro município.",
            "Confira a localização gravada no modelo ou defina o terreno por "
            "outro método.")
    return avisos.Aviso(
        avisos.ERRO, f"O terreno cai fora de {municipio}.",
        "O ponto ou o desenho está em outro município.",
        "Revise-o, ou a localização declarada em Informações Gerais.")


@st.cache_data(show_spinner=False)
def _dentro_do_municipio(codigo: str, lat: float, lon: float) -> bool | None:
    return territorio.conferir_ponto(codigo, lat, lon).dentro


def _aviso_de_divergencia(terreno, declaracoes: dict) -> avisos.Aviso | None:
    """A explicação da divergência entre o IfcSite e o IfcMapConversion, ou
    ``None`` quando o extrator não a registrou na procedência do terreno
    (ADR-038).

    O confronto de cada posição com o município declarado só acontece com a
    malha já em cache, como em ``_fora_do_municipio``: o render nunca depende de
    rede, e sem malha a mensagem simplesmente não afirma onde cada posição cai.
    """
    codigo = str(declaracoes.get(dec.MUNICIPIO_IBGE) or "")
    municipio = (f"{declaracoes.get(dec.MUNICIPIO, '')}/"
                 f"{declaracoes.get(dec.UF, '')}").strip("/")

    def dentro(lat: float, lon: float) -> bool | None:
        if not codigo or territorio.malha_em_cache(codigo) is None:
            return None
        return _dentro_do_municipio(codigo, lat, lon)

    return avisos.aviso_divergencia_do_terreno(
        terreno, municipio=municipio, dentro_do_municipio=dentro)


def _avisos_do_terreno(terreno, *, confirmado: bool) -> None:
    """Os avisos da leitura do terreno numa caixa só, com o texto técnico de
    cada um recolhido abaixo (ADR-034, U3).

    Duas caixas possíveis, conforme o que foi lido. Com poligonal, o que o
    usuário faz é conferir contorno e área contra a matrícula ou o memorial.
    Sem ela, o terreno é um ponto: não há contorno a conferir, e o que importa
    é saber que as medidas partem dele — numa caixa só, e não na do contorno,
    que não se aplica a um ponto (ADR-034 (c))."""
    if not terreno.tem_poligonal:
        aviso = avisos.Aviso(
            avisos.ALERTA, "O terreno é um ponto, não o contorno do lote.",
            "As distâncias aos equipamentos são medidas dele, e as "
            "verificações que dependem dos limites do terreno ficam não "
            "avaliáveis.",
            "Confira no mapa se o ponto está sobre o terreno.")
        if terreno.avisos:
            avisos.alerta_com_detalhe(aviso, list(terreno.avisos),
                                      rotulo="Por que este aviso")
        else:
            avisos.mostrar_aviso(aviso)
        return
    avisos.alerta_com_detalhe(
        avisos.Aviso(
            avisos.ALERTA,
            "Confira o contorno e a área do terreno"
            + ("." if confirmado else " antes de confirmar."),
            "A leitura encontrou pontos de atenção sobre a origem do terreno: o "
            "contorno pode não coincidir com o limite do lote.",
            "Compare a área com a da matrícula ou do memorial."),
        list(terreno.avisos), rotulo="Por que este aviso")


def _confirmar(emp, terreno, declaracoes: dict) -> None:
    """Valida contra a localização declarada e grava no empreendimento."""
    lat, lon = terreno.centro_wgs84
    codigo = str(declaracoes.get(dec.MUNICIPIO_IBGE) or "")
    municipio = declaracoes.get(dec.MUNICIPIO, "")

    if codigo:
        with st.spinner("Confrontando com os limites do município…"):
            res = territorio.conferir_ponto(codigo, lat, lon)
        if res.dentro is False:
            st.error(f"O centro do terreno cai **fora** dos limites de "
                     f"{municipio} (malha IBGE). Revise o desenho ou a "
                     f"localização declarada antes de confirmar.",
                     icon=":material/wrong_location:")
            return
        if res.dentro is None:
            terreno.avisos.append(
                "Confronto com os limites municipais não avaliado "
                f"({res.mensagem}). O terreno foi aceito como informado.")
        terreno.procedencia["confronto_municipio"] = res.to_dict()

    # Mantido por continuidade/auditoria (o próprio Empreendimento já é a
    # fonte de verdade da localização a partir desta fase).
    terreno.procedencia["municipio_declarado"] = {
        "uf": declaracoes.get(dec.UF, ""), "nome": municipio, "ibge": codigo}

    if terreno.area_m2 is not None:
        if terreno.area_m2 < AREA_MINIMA_M2:
            terreno.avisos.append(
                f"Área de apenas {terreno.area_m2:.0f} m² — verifique se o "
                "desenho cobre todo o terreno.")
        elif terreno.area_m2 > AREA_MAXIMA_M2:
            terreno.avisos.append(
                f"Área de {terreno.area_m2/10_000:.0f} ha — confirme se a "
                "poligonal é do terreno e não de uma área maior.")

    emp.definir_terreno(terreno)
    emp_mod.gravar(emp)
    st.session_state[chaves.EMPREENDIMENTO] = emp
    for k in (CHAVE_PONTO, CHAVE_CLIQUE):
        st.session_state.pop(k, None)
    st.rerun()


def _terreno_confirmado(emp, terreno) -> None:
    """Estado após a confirmação: mapa do terreno + resumo + redefinir."""
    st.success(f"Terreno confirmado — {terreno.resumo()}",
               icon=":material/check_circle:")

    centro, zoom = _mapa.enquadrar(terreno)
    col_mapa, col_painel = st.columns([3, 2], gap="medium")
    with col_mapa:
        _mapa.mapa(centro=centro, modo="visualizar", zoom=zoom,
                   contorno_municipal=_contorno_de(terreno), terreno=terreno,
                   chave=f"mapa_confirmado__{CHAVE}")
    with col_painel:
        st.markdown("##### Procedência")
        st.write(f"**Origem:** {ROTULO_ORIGEM.get(terreno.origem, terreno.origem)}  \n"
                 f"**Precisão:** {ROTULO_PRECISAO.get(terreno.precisao, terreno.precisao)}  \n"
                 f"**Sistema de medida:** {terreno.crs_metrico}")
        if terreno.tem_poligonal:
            st.write(f"**Área:** {formatar_numero(terreno.area_m2, 0)} m²  \n"
                     f"**Perímetro:** {formatar_numero(terreno.perimetro_m, 0)} m")
        _avisos_do_terreno(terreno, confirmado=True)
        if st.button("Redefinir terreno", use_container_width=True,
                     key=f"redefinir__{CHAVE}"):
            emp.definir_terreno(None)
            emp_mod.gravar(emp)
            st.session_state[chaves.EMPREENDIMENTO] = emp
            for k in (chaves.chave_relatorio(CHAVE),
                      chaves.chave_mostrar_resultados(CHAVE)):
                st.session_state.pop(k, None)
            st.rerun()


# ---------------------------------------------------------------------------
# Apoio: centro e contorno do mapa
# ---------------------------------------------------------------------------

def _centro_inicial(declaracoes: dict) -> tuple[tuple[float, float], int]:
    codigo = str(declaracoes.get(dec.MUNICIPIO_IBGE) or "")
    if codigo:
        centro = _centro_municipio(codigo)
        if centro:
            return centro, _mapa.ZOOM_MUNICIPIO
    return CENTRO_FALLBACK, 4


def _contorno(declaracoes: dict) -> dict | None:
    codigo = str(declaracoes.get(dec.MUNICIPIO_IBGE) or "")
    return territorio.malha_em_cache(codigo) if codigo else None


def _contorno_de(terreno) -> dict | None:
    codigo = str((terreno.procedencia.get("municipio_declarado") or {}).get("ibge") or "")
    return territorio.malha_em_cache(codigo) if codigo else None


# ---------------------------------------------------------------------------
# Cobertura prevista
# ---------------------------------------------------------------------------

def _cobertura(grupo, emp, declaracoes: dict) -> None:
    """Cobertura prevista e, com o terreno definido, a análise.

    A contagem é em requisitos da Portaria (ENQ-009, ENQ-010, ENQ-011): as
    alternativas A e B de cada pai são consumidas por ele e não contam à parte
    (``explicacao_grupo.cobertura``).
    """
    terreno = _terreno_corrente(emp)
    executaveis = grupos.ids_executaveis(grupo, declaracoes) if terreno else []
    explicacao_mod.cobertura(grupo, executaveis)

    if terreno is None:
        st.info("Defina o terreno acima para calcular a cobertura.",
                icon=":material/info:")
        return
    if not executaveis:
        st.info("Nenhuma verificação do grupo é executável com as declarações "
                "e o terreno atuais.", icon=":material/construction:")
        return

    acao_mod.acao_sem_ifc(
        CHAVE, grupo, declaracoes, origem_pagina=ORIGEM, empreendimento=emp,
        avisar_rede=False,
        resumo_execucao=explicacao_mod.resumo_da_execucao(grupo, executaveis))


main()
