"""Componente de mapa da entrada do terreno (folium + streamlit-folium).

Um único ponto de contato com o mapa, usado nos três modos de entrada do
Enquadramento (desenhar a poligonal, marcar o centro, apenas visualizar). O
que o mapa devolve é repassado cru para ``app.servicos.territorio``, que é
quem sabe transformar payload em geometria — aqui não há regra de domínio.

Degradação graciosa: sem ``streamlit-folium`` instalado, a função avisa e
devolve ``None``; a tela continua utilizável pelos campos de latitude e
longitude do modo de marcar o centro. Mesmo padrão adotado para o snapshot de
municípios.

O contorno municipal vem do cache da malha do IBGE (``malha_em_cache``) —
sem rede nesta camada, igual à cena 3D do relatório do EMP-001.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from app.componentes import layout as _layout

ALTURA_PADRAO = _layout.ALTURA_MAPA_EDICAO
ZOOM_MUNICIPIO = 12
ZOOM_TERRENO = 17

# O mapa do RELATÓRIO segue a altura única de visualização do ADR-034 (b): em
# largura total, empilhado sob o card, com a legenda numa faixa própria abaixo.
ALTURA_RELATORIO = _layout.ALTURA_VISUALIZACAO

# Edição da poligonal já desenhada. ``edit`` PRECISA ser um objeto: o
# Leaflet.draw lê ``selectedPathOptions`` de dentro dele e, recebendo um
# booleano, liga o modo de edição SEM nenhum destaque visual — o botão parece
# morto (era o comportamento antes de 2026-09-10). Com o objeto, a poligonal em
# edição fica tracejada e os vértices arrastáveis; ``draw:edited`` e
# ``draw:deleted`` chegam ao Python porque o streamlit-folium remonta
# ``all_drawings`` a partir do FeatureGroup a cada evento.
_EDIT_OPTIONS = {
    "edit": {"selectedPathOptions": {"color": _layout.COR_DESTAQUE_ESCURO,
                                     "weight": 4, "dashArray": "6,6",
                                     "fillColor": _layout.COR_DESTAQUE,
                                     "fillOpacity": 0.15,
                                     "maintainColor": False}},
    "remove": {},
}

# Rótulos da barra de desenho em português. Precisa ser injetado ANTES da
# construção do controle (por isso entra no script do mapa antes do Draw), e
# vai dentro de try/catch: uma chave errada numa versão futura do Leaflet.draw
# deixaria os textos em inglês, jamais quebraria o mapa.
_JS_TRADUCAO = """
try {
  var L_ = L.drawLocal;
  L_.draw.toolbar.actions = {title: "Cancelar o desenho", text: "Cancelar"};
  L_.draw.toolbar.finish  = {title: "Concluir o desenho", text: "Concluir"};
  L_.draw.toolbar.undo    = {title: "Apagar o último ponto", text: "Apagar ponto"};
  L_.draw.toolbar.buttons.polygon   = "Desenhar a poligonal do terreno";
  L_.draw.toolbar.buttons.rectangle = "Desenhar o terreno como retângulo";
  L_.draw.handlers.polygon.tooltip = {
    start: "Clique para iniciar a poligonal.",
    cont:  "Clique para continuar.",
    end:   "Clique no primeiro ponto para fechar."};
  L_.draw.handlers.rectangle.tooltip = {start: "Arraste para desenhar o retângulo."};
  L_.edit.toolbar.actions.save     = {title: "Salvar as alterações", text: "Salvar"};
  L_.edit.toolbar.actions.cancel   = {title: "Descartar as alterações", text: "Cancelar"};
  L_.edit.toolbar.actions.clearAll = {title: "Apagar tudo", text: "Apagar tudo"};
  L_.edit.toolbar.buttons.edit           = "Editar a poligonal";
  L_.edit.toolbar.buttons.editDisabled   = "Nada desenhado para editar";
  L_.edit.toolbar.buttons.remove         = "Apagar a poligonal";
  L_.edit.toolbar.buttons.removeDisabled = "Nada desenhado para apagar";
  L_.edit.handlers.edit.tooltip = {
    text: "Arraste os vértices para ajustar o terreno.",
    subtext: "Clique em Salvar para confirmar."};
  L_.edit.handlers.remove.tooltip = {text: "Clique na poligonal para apagá-la."};
} catch (e) { console.log("traducao do Draw indisponivel:", e); }
"""

# Objetos devolvidos por modo: pedir só o necessário evita rerun a cada
# panorâmica ou zoom do usuário (o componente reexecuta o script a cada evento).
_RETORNO = {
    "desenhar": ["all_drawings", "last_active_drawing"],
    "clicar": ["last_clicked"],
    "visualizar": [],
    # O mapa do relatório não devolve nada: ele é leitura. Qualquer objeto
    # pedido aqui faria a página inteira reexecutar a cada zoom do usuário.
    "resultado": [],
}

# --- Cores dos pinos do mapa de resultado ----------------------------------
#
# Saturadas, e não os tons claros da tabela: sobre a base do OpenStreetMap um
# verde-pastel some. As chaves são as classificações de
# ``app.servicos.roteamento`` — a semântica mora em ``core.roteamento.contrato``,
# aqui só a tinta.
COR_CLASSIFICACAO = {
    "atende_provado": "#2e7d32",
    "dentro_do_piso": "#ef6c00",
    "fora_provado": "#c62828",
    "nao_medida": "#78909c",
}
COR_DESCARTADO = "#90a4ae"


def disponivel() -> bool:
    try:
        import folium  # noqa: F401
        from streamlit_folium import st_folium  # noqa: F401
    except Exception:
        return False
    return True


def aviso_indisponivel() -> None:
    st.warning(
        "O componente de mapa não está instalado — a entrada por desenho e por "
        "clique fica indisponível. Para habilitar, rode na raiz do projeto: "
        "`pip install -e \".[dev]\"` (ou `pip install streamlit-folium`). "
        "Enquanto isso, use **Marcar o centro no mapa** e digite a latitude "
        "e a longitude.",
        icon=":material/map:",
    )


def mapa(*, centro: tuple[float, float], modo: str = "visualizar",
         zoom: int = ZOOM_MUNICIPIO, contorno_municipal: dict | None = None,
         terreno: Any = None, altura: int = ALTURA_PADRAO,
         chave: str = "mapa") -> dict | None:
    """Desenha o mapa e devolve o payload de interação (ou None se indisponível).

    ``modo``: ``desenhar`` habilita o plugin Draw (polígono e retângulo);
    ``clicar`` captura o último clique; ``visualizar`` só exibe.
    ``terreno`` já confirmado é desenhado por cima, com o centro marcado.
    """
    if not disponivel():
        aviso_indisponivel()
        return None

    import folium
    from streamlit_folium import st_folium

    m = folium.Map(location=[centro[0], centro[1]], zoom_start=zoom,
                   tiles="OpenStreetMap", control_scale=True)

    if contorno_municipal:
        folium.GeoJson(
            contorno_municipal, name="Limite municipal",
            style_function=lambda _: {"color": _layout.COR_DESTAQUE_ESCURO,
                                      "weight": 3, "fillOpacity": 0.05},
        ).add_to(m)

    if terreno is not None:
        _desenhar_terreno(folium, m, terreno)

    if modo == "desenhar":
        from folium.plugins import Draw

        m.get_root().script.add_child(folium.Element(_JS_TRADUCAO))
        Draw(
            export=False,
            draw_options={"polygon": {"showArea": True}, "rectangle": True,
                          "polyline": False, "circle": False,
                          "circlemarker": False, "marker": False},
            edit_options=_EDIT_OPTIONS,
        ).add_to(m)

    kwargs = {"height": altura, "key": chave,
                  "returned_objects": _RETORNO.get(modo, [])}
    try:
        return st_folium(m, use_container_width=True, **kwargs)
    except TypeError:      # versões antigas do componente não têm o parâmetro
        return st_folium(m, width=None, **kwargs)


def _desenhar_terreno(folium, m, terreno: Any) -> None:
    """Poligonal confirmada (quando houver) e marcador no centro."""
    _terreno_no_mapa(folium, m, terreno.centro_wgs84, terreno.poligonal_wgs84)


def _terreno_no_mapa(folium, m, centro, poligonal: dict | None) -> None:
    """Desenha o terreno a partir de GEOMETRIA CRUA, não do objeto ``Terreno``.

    O relatório trabalha sobre o ``detalhe`` do resultado (dicionários vindos do
    JSON), e não sobre o objeto de domínio — é o que mantém o relatório
    reproduzível a partir do arquivo. As duas entradas caem aqui.
    """
    lat, lon = centro
    if poligonal:
        folium.GeoJson(
            poligonal, name="Terreno",
            style_function=lambda _: {"color": _layout.COR_DESTAQUE, "weight": 3,
                                      "fillColor": _layout.COR_DESTAQUE,
                                      "fillOpacity": 0.22},
        ).add_to(m)
    folium.Marker(
        [lat, lon], tooltip="Centro do terreno",
        icon=folium.Icon(color="darkblue", icon="crosshairs", prefix="fa"),
    ).add_to(m)


def enquadrar(terreno: Any) -> tuple[tuple[float, float], int]:
    """Centro e zoom adequados para exibir um terreno já confirmado."""
    return terreno.centro_wgs84, ZOOM_TERRENO


# ---------------------------------------------------------------------------
# Mapa do relatório das regras de distância a equipamento (ENQ-009/010.1/011.1)
# ---------------------------------------------------------------------------

def _graus_do_raio(lat: float, metros: float) -> tuple[float, float]:
    """(Δlatitude, Δlongitude) que cobrem ``metros`` — só para enquadrar."""
    import math

    dlat = metros / 111_320.0
    dlon = metros / max(111_320.0 * math.cos(math.radians(lat)), 1.0)
    return dlat, dlon


def _duas_distancias(linha: dict) -> list[str]:
    """As duas leituras do mesmo par, para o popup do pino.

    O número em destaque acima é o que DECIDIU; estas duas linhas mostram de onde
    ele veio. A comparação é o que deixa o desvio da malha viária visível —
    900 m em linha reta contra 1.100 m caminháveis diz algo que nenhum dos dois
    números diz sozinho.
    """
    reta, em_rede = linha.get("metros_linha_reta"), linha.get("metros_rede")
    if reta is None and em_rede is None:
        return []
    itens = []
    if reta is not None:
        itens.append(f"linha reta {reta:.0f} m")
    if em_rede is not None:
        itens.append(f"em rede {em_rede:.0f} m")
        if reta:
            itens.append(f"desvio {em_rede / reta:.2f}×")
    elif linha.get("erro_rede"):
        itens.append(f"em rede: {linha['erro_rede']}")
    return [f"<span style='font-size:.85em'>{' · '.join(itens)}</span>"]


def _popup_equipamento(linha: dict, rotulo_classificacao: str) -> str:
    partes = [f"<b>{linha.get('nome') or 'Equipamento'}</b>"]
    if linha.get("codigo_inep"):
        partes.append(f"INEP {linha['codigo_inep']}")
    if linha.get("metros") is not None:
        partes.append(f"<b>{linha['metros']:.0f} m</b> — {rotulo_classificacao}")
    else:
        partes.append(rotulo_classificacao)
    partes.extend(_duas_distancias(linha))
    rede_situacao = " · ".join(x for x in (linha.get("rede"), linha.get("situacao")) if x)
    if rede_situacao:
        partes.append(rede_situacao)
    if linha.get("endereco"):
        partes.append(f"<i>{linha['endereco']}</i>")
    if linha.get("rotulo_motivo"):
        partes.append(f"Descartado: {linha['rotulo_motivo']}")
    return "<br>".join(partes)


def mapa_resultado(detalhe: dict, *, altura: int = ALTURA_RELATORIO,
                   chave: str = "mapa_resultado") -> dict | None:
    """Mapa do resultado de uma regra ENQ de distância a equipamento.

    Lê **só** o ``detalhe`` do resultado: terreno analisado, limiar, raio de
    busca e os equipamentos já classificados. Nenhuma decisão de domínio é
    tomada aqui — a cor de cada pino vem da ``classificacao`` que a regra
    gravou, e o recorte do que aparece vem do campo ``no_raio``.

    **Só os equipamentos dentro do raio de busca são exibidos**: num município grande, pinar o conjunto inteiro cobre o
    território de marcadores irrelevantes ao requisito. A tabela do relatório
    continua completa — o mapa é o recorte, não a fonte.
    """
    if not disponivel():
        aviso_indisponivel()
        return None

    import folium

    from app.servicos import roteamento as rot  # gateway do núcleo

    terreno = (detalhe or {}).get("terreno") or {}
    centro_dict = terreno.get("centro_wgs84") or {}
    lat, lon = centro_dict.get("lat"), centro_dict.get("lon")
    if lat is None or lon is None:
        st.info("O resultado não registra o centro do terreno; não há o que "
                "situar no mapa.", icon=":material/location_off:")
        return None

    limiar = float(detalhe.get("limiar_m") or 0.0)
    raio = float(detalhe.get("raio_de_busca_m") or limiar or 0.0)

    m = folium.Map(location=[lat, lon], zoom_start=ZOOM_TERRENO,
                   tiles="OpenStreetMap", control_scale=True)

    # Círculo do LIMIAR primeiro, por baixo de tudo: é o critério normativo, e
    # o que o olho deve comparar com cada pino.
    if limiar:
        folium.Circle(
            [lat, lon], radius=limiar, color=_layout.COR_DESTAQUE_ESCURO,
            weight=2, dash_array="6,6", fill=False,
            tooltip=f"Limiar do requisito: {limiar:.0f} m").add_to(m)
    if raio and raio > limiar:
        folium.Circle(
            [lat, lon], radius=raio, color=_layout.COR_TEXTO_SUAVE,
            weight=1, dash_array="2,8", fill=False,
            tooltip=(f"Raio de pré-seleção para a distância caminhável: "
                     f"{raio:.0f} m")).add_to(m)

    _terreno_no_mapa(folium, m, (lat, lon), terreno.get("poligonal_wgs84"))

    avaliados = [e for e in (detalhe.get("equipamentos") or []) if e.get("no_raio")]
    grupo_avaliados = folium.FeatureGroup(name="Equipamentos avaliados", show=True)
    # Registros por CHAVE DE DESTINO, para o painel de rotas alcançar cada
    # objeto do Leaflet. A chave nunca é o nome: duas escolas homônimas
    # colapsariam numa entrada e o painel destacaria a errada — o mesmo defeito
    # de chave que ``euclidiana.chave_destino`` existe para não cometer.
    pinos_js: dict[str, str] = {}
    rotas_js: dict[str, str] = {}
    determinante_js = ""

    for linha in avaliados:
        if linha.get("lat") is None or linha.get("lon") is None:
            continue
        classificacao = linha.get("classificacao") or rot.CLASSIF_NAO_MEDIDA
        cor = COR_CLASSIFICACAO.get(classificacao, COR_DESCARTADO)
        determinante = bool(linha.get("determinante"))
        destino = str(linha.get("destino") or "")
        pino = folium.CircleMarker(
            [linha["lat"], linha["lon"]],
            radius=9 if determinante else 7,
            color="#ffffff", weight=2 if determinante else 1,
            fill=True, fill_color=cor, fill_opacity=0.95,
            tooltip=linha.get("nome") or "",
            popup=folium.Popup(
                _popup_equipamento(
                    linha, rot.ROTULO_CLASSIFICACAO.get(classificacao, "")),
                max_width=320),
        )
        pino.add_to(grupo_avaliados)
        if destino:
            pinos_js[destino] = pino.get_name()
        rota = linha.get("rota")
        if rota:
            # O TRAÇADO REAL: a rota que produziu o número exibido ao
            # lado, vinda da MESMA resposta do provedor. Desenhado só para quem
            # tem a linha reta dentro do limiar — os únicos que podem atender.
            #
            # Vai direto no mapa, e NÃO no FeatureGroup: o painel de rotas
            # liga e desliga cada rota individualmente com
            # ``map.removeLayer``/``addLayer``, e uma camada dentro de um grupo
            # não responde a isso — teria de ser removida do grupo, que é o
            # objeto errado para o painel conhecer.
            traco = folium.PolyLine(
                rota, color=cor, weight=5 if determinante else 3,
                opacity=0.9 if determinante else 0.7,
                tooltip=(f"{linha.get('nome', '')} — "
                         f"{(linha.get('metros') or 0):.0f} m a pé"))
            traco.add_to(m)
            if destino:
                rotas_js[destino] = traco.get_name()
                if determinante:
                    determinante_js = destino
        elif determinante:
            # Sem rota, a reta tracejada até o determinante materializa a medida
            # que decidiu o veredito. Ela é FALLBACK: desenhar as
            # duas seria sugerir uma comparação que não está em questão, e a
            # reta ao lado do caminho real confunde o que cada uma mede.
            folium.PolyLine(
                [[lat, lon], [linha["lat"], linha["lon"]]], color=cor,
                weight=2, dash_array="4,6", opacity=0.9,
                tooltip=(f"{linha.get('nome', '')} — "
                         f"{(linha.get('metros') or 0):.0f} m "
                         "(linha reta; sem traçado de rota)")
            ).add_to(grupo_avaliados)
    grupo_avaliados.add_to(m)

    descartados = detalhe.get("descartados_no_raio") or []
    if descartados:
        # Desligado por padrão: são o CONTRAPONTO do resultado, não o resultado.
        grupo_descartados = folium.FeatureGroup(
            name=f"Descartados no raio ({len(descartados)})", show=False)
        for linha in descartados:
            if linha.get("lat") is None or linha.get("lon") is None:
                continue
            folium.CircleMarker(
                [linha["lat"], linha["lon"]], radius=6, color=COR_DESCARTADO,
                weight=2, fill=True, fill_color="#ffffff", fill_opacity=0.85,
                tooltip=f"{linha.get('nome', '')} — {linha.get('rotulo_motivo', '')}",
                popup=folium.Popup(_popup_equipamento(linha, "não avaliado"),
                                   max_width=320),
            ).add_to(grupo_descartados)
        grupo_descartados.add_to(m)
        # À ESQUERDA, sob os botões de zoom: o painel de rotas ocupa
        # o canto superior direito, e os dois se sobrepunham — o controle de
        # camadas ficava ilegível atrás da lista. Um em cada canto.
        folium.LayerControl(collapsed=False, position="topleft").add_to(m)

    # Depois de tudo: o painel precisa dos nomes de variável dos pinos e das
    # rotas, que só existem depois de eles serem criados.
    _lista_clicavel(folium, m, avaliados, pinos_js, rotas_js, determinante_js)

    if raio:
        dlat, dlon = _graus_do_raio(lat, raio)
        m.fit_bounds([[lat - dlat, lon - dlon], [lat + dlat, lon + dlon]])

    from streamlit_folium import st_folium

    kwargs = {"height": altura, "key": chave, "returned_objects": _RETORNO["resultado"]}
    try:
        return st_folium(m, use_container_width=True, **kwargs)
    except TypeError:      # versões antigas do componente não têm o parâmetro
        return st_folium(m, width=None, **kwargs)


# ---------------------------------------------------------------------------
# Lista clicável DENTRO do iframe
# ---------------------------------------------------------------------------
#
# Por que dentro do iframe, e não com ``st.dataframe(on_select=...)``: a seleção
# nativa do Streamlit dispara um *rerun* completo, e o ``st_folium`` remonta o
# mapa — o usuário perde a panorâmica e o zoom que acabou de fazer para
# investigar. Dentro do iframe o clique não sai do navegador, e o mapa do
# relatório já pede ``returned_objects=[]`` justamente para não reexecutar a
# página. O precedente é a lista de ambientes da cena 3D (``app/componentes/cena3d.py``).
#
# A tabela do Streamlit continua sendo a tabela ANALÍTICA — ordenação, filtro e o
# conjunto inteiro avaliado. Esta lista é de NAVEGAÇÃO, restrita ao raio, que é o
# que o mapa pina.

_PAINEL_CSS = """
<style>
#painel-eq{position:absolute;top:10px;right:10px;z-index:9999;width:250px;
  max-height:calc(100% - 24px);overflow:auto;background:rgba(255,255,255,.96);
  border:1px solid #cfd8dc;border-radius:6px;box-shadow:0 1px 6px rgba(0,0,0,.25);
  font:12px/1.35 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:#263238}
#painel-eq .cab{padding:7px 9px;border-bottom:1px solid #eceff1;font-weight:700}
#painel-eq .dica{padding:6px 9px;border-bottom:1px solid #eceff1;color:#607d8b;
  font-size:11px;line-height:1.3}
#painel-eq .eq{padding:6px 9px;border-top:1px solid #f1f3f4;cursor:pointer;
  display:flex;align-items:center;gap:6px}
#painel-eq .eq:hover{background:#f5f7f8}
#painel-eq .eq.sel{background:#e8f0fe}
#painel-eq .bola{width:.7rem;height:.7rem;border-radius:50%;flex:0 0 auto}
#painel-eq .nm{flex:1 1 auto;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap}
#painel-eq .dist{flex:0 0 auto;color:#546e7a;font-variant-numeric:tabular-nums}
#painel-eq .rt{flex:0 0 auto;width:1.1rem;text-align:center;color:#b0bec5}
#painel-eq .eq.vis .rt{color:#1a73e8;font-weight:700}
</style>
"""

_PAINEL_JS = """
(function () {
  // DEFERIDO, e isto não é zelo: o folium emite o script DESTE bloco ANTES das
  // definições das camadas (conferido no HTML gerado — o bloco sai por volta do
  // byte 4.100 e as polilinhas por volta do 9.100).
  //
  // O modo de falhar é o pior possível, e foi o defeito visto em tela em
  // 13/09/2026 — as três rotas acesas e o painel inerte. Por causa do
  // *hoisting* do `var`, as variáveis do folium já EXISTEM quando este bloco
  // roda, valendo `undefined`: não há exceção, não há erro no console. O `MAPA`
  // vem `undefined`, o guard `if (!MAPA) return` desiste em silêncio, nenhuma
  // rota é ocultada e NENHUM clique é ligado. Um erro barulhento teria sido
  // melhor sorte do que tivemos.
  //
  // As referências ficam DENTRO da função diferida, que é o que adia a
  // resolução delas para depois de o documento ser lido.
  function ligar() {
  var MAPA = %(mapa)s, PINOS = %(pinos)s, ROTAS = %(rotas)s;
  var painel = document.getElementById("painel-eq");
  if (!painel || !MAPA) return;

  // O painel é um div sobre o mapa, não um controle do Leaflet: sem isto,
  // arrastar sobre a lista faz PAN no mapa e a roda do mouse dá ZOOM em vez de
  // rolar a lista.
  if (window.L && L.DomEvent) {
    L.DomEvent.disableClickPropagation(painel);
    L.DomEvent.disableScrollPropagation(painel);
  }

  // Estado inicial: só a rota da ELEITA fica visível. As demais existem, já
  // desenhadas, e são acesas pelo painel — abrir o mapa com todas ligadas faz
  // do traçado um emaranhado em vez de uma explicação.
  Object.keys(ROTAS).forEach(function (d) {
    if (d !== %(eleita)s && MAPA.hasLayer(ROTAS[d])) MAPA.removeLayer(ROTAS[d]);
  });

  function visivel(d) { return ROTAS[d] && MAPA.hasLayer(ROTAS[d]); }

  function pintarEstado() {
    painel.querySelectorAll(".eq").forEach(function (el) {
      el.classList.toggle("vis", visivel(el.dataset.destino));
    });
  }

  painel.querySelectorAll(".eq").forEach(function (el) {
    el.addEventListener("click", function () {
      var d = el.dataset.destino;
      painel.querySelectorAll(".eq").forEach(function (o) {
        o.classList.toggle("sel", o === el);
      });
      var pino = PINOS[d];
      if (pino) {
        // Centra sem mexer no zoom: quem já ajustou o enquadramento não o perde
        // por clicar num item da lista.
        MAPA.panTo(pino.getLatLng());
        if (pino.openPopup) pino.openPopup();
      }
      if (ROTAS[d]) {
        if (visivel(d)) { MAPA.removeLayer(ROTAS[d]); }
        else { ROTAS[d].addTo(MAPA); if (ROTAS[d].bringToFront) ROTAS[d].bringToFront(); }
      }
      pintarEstado();
    });
  });
  pintarEstado();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", ligar);
  } else {
    ligar();   // script injetado depois do carregamento (não é o caso aqui)
  }
})();
"""


def _lista_clicavel(folium, m, avaliados: list[dict], pinos_js: dict,
                    rotas_js: dict, eleita: str) -> None:
    """Painel de navegação sobre o mapa, ligado aos pinos e às rotas.

    Só desenha quando há pino registrado — sem isso o painel seria uma caixa
    vazia cobrindo o mapa.
    """
    import json as _json

    itens = []
    for linha in avaliados:
        destino = str(linha.get("destino") or "")
        if destino not in pinos_js:
            continue
        classificacao = linha.get("classificacao") or "nao_medida"
        cor = COR_CLASSIFICACAO.get(classificacao, COR_DESCARTADO)
        metros = linha.get("metros")
        rotulo_dist = f"{_mil(metros)} m" if metros is not None else "—"
        tem_rota = destino in rotas_js
        nome = _escapar(linha.get("nome") or destino)
        itens.append(
            f"<div class='eq' data-destino=\"{_escapar(destino)}\">"
            f"<span class='bola' style='background:{cor}'></span>"
            f"<span class='nm' title=\"{nome}\">{nome}</span>"
            f"<span class='dist'>{rotulo_dist}</span>"
            f"<span class='rt'>{'&#10141;' if tem_rota else ''}</span></div>")
    if not itens:
        return

    com_rota = len(rotas_js)
    dica = ("Clique para localizar." if not com_rota else
            "Clique para localizar; nos que têm <b>&#10141;</b>, o clique "
            "também mostra ou oculta a rota. Abre com a rota da <b>eleita</b>.")
    html = (_PAINEL_CSS + "<div id='painel-eq'>"
            f"<div class='cab'>Equipamentos no raio ({len(itens)})</div>"
            f"<div class='dica'>{dica}</div>" + "".join(itens) + "</div>")
    m.get_root().html.add_child(folium.Element(html))

    # As referências são NOMES DE VARIÁVEL do folium, injetados sem aspas: o
    # objeto Leaflet é o alvo, não uma string com o nome dele.
    def _mapa_js(registro: dict) -> str:
        return ("{" + ", ".join(f"{_json.dumps(k)}: {v}"
                                for k, v in registro.items()) + "}")

    codigo = _PAINEL_JS % {
        "mapa": m.get_name(),
        "pinos": _mapa_js(pinos_js),
        "rotas": _mapa_js(rotas_js),
        "eleita": _json.dumps(eleita),
    }
    m.add_child(_macro_de_script(codigo))


def _macro_de_script(codigo: str):
    """Empacota JS como ``MacroElement`` FILHO DO MAPA — e não da raiz.

    **Descoberto em tela, e não seria adivinhado.** O
    ``streamlit-folium`` não embute o HTML do ``Figure``: ele extrai o JS com
    ``generate_leaflet_string(mapa)``, que percorre a subárvore do **Map**
    chamando o macro ``script`` de cada filho. Script pendurado em
    ``m.get_root().script`` — como este estava — **é simplesmente descartado**.
    O ``<div>`` do painel continuava aparecendo, porque esse vem por outro
    caminho (``_get_html``), e o resultado era um painel visível e inerte, com
    todas as rotas acesas. Nenhum erro em lugar nenhum.

    Há um segundo motivo, independente, para o script ter de estar nessa mesma
    string: ``_replace_folium_vars`` reescreve os sufixos das variáveis
    (``poly_line_<hash>`` vira ``poly_line_div_3``) **só no texto coletado**.
    Injetado por fora, o script referenciaria nomes que deixaram de existir.

    O código vai por uma variável do template (``{{ this.codigo }}``) e não
    interpolado no texto: assim nenhuma chave ou porcentagem do JS é confundida
    com sintaxe do Jinja.
    """
    from branca.element import MacroElement
    from jinja2 import Template

    class _ScriptDoPainel(MacroElement):
        _template = Template(
            "{% macro script(this, kwargs) %}{{ this.codigo }}{% endmacro %}")

        def __init__(self, codigo: str) -> None:
            super().__init__()
            self.codigo = codigo

    return _ScriptDoPainel(codigo)


def _escapar(texto: str) -> str:
    """Escapa o que vai para dentro do HTML do painel.

    Nome de escola vem do recorte do INEP, que é dado de terceiro: um ``&`` ou
    um par de aspas num nome quebraria o atributo e, com ele, o ``data-destino``
    do item vizinho — a lista passaria a destacar o pino errado.
    """
    return (str(texto).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def legenda_resultado(detalhe: dict | None = None) -> None:
    """Legenda completa: primeiro os dois círculos, depois as cores dos pinos.

    Composição das duas metades, mantida como porta única para quem quer a
    legenda inteira de uma vez. Ela não fica colada embaixo
    do mapa, e sim numa faixa própria em largura inteira, abaixo do consolidado —
    ver ``paginas/relatorios/relatorio._faixa_legenda``.
    """
    legenda_circulos(detalhe)
    legenda_cores()


def legenda_circulos(detalhe: dict | None = None) -> None:
    """Os dois círculos tracejados do mapa — só faz algo com ``detalhe``.

    Sem isso eles ficavam sem explicação em lugar nenhum da tela — e a confusão
    que isso convida é a pior possível aqui: ler o círculo externo como o critério
    da Portaria, quando ele é o pré-filtro de chamadas ao roteador e não tem
    efeito nenhum sobre o veredito.
    """
    if detalhe:
        st.markdown(_legenda_dos_circulos(detalhe), unsafe_allow_html=True)


def legenda_cores() -> None:
    """As quatro classificações dos pinos, com o que cada cor autoriza concluir.

    O texto vem de ``rot.EXPLICACAO_CLASSIFICACAO``: uma legenda reescrita à mão
    tenderia a simplificar "dentro do limiar em linha reta" para "atende", que é
    precisamente a conclusão que a métrica não sustenta.

    Os quatro itens saem numa **grade** em vez de uma pilha: em largura inteira,
    quatro linhas curtas empilhadas desperdiçam a faixa. O ``auto-fit`` com
    mínimo de 22rem devolve a pilha sozinho quando a legenda cai numa coluna
    estreita, então a mesma função serve aos dois lugares sem parâmetro.
    """
    from app.servicos import roteamento as rot  # gateway do núcleo

    ordem = (rot.CLASSIF_ATENDE_PROVADO, rot.CLASSIF_DENTRO_DO_PISO,
             rot.CLASSIF_FORA_PROVADO, rot.CLASSIF_NAO_MEDIDA)
    itens = "".join(
        f"<div style='margin:.18rem 0'><span style='display:inline-block;"
        f"width:.7rem;height:.7rem;border-radius:50%;background:"
        f"{COR_CLASSIFICACAO[c]};margin-right:.45rem'></span>"
        f"<b>{rot.ROTULO_CLASSIFICACAO[c]}</b> — "
        f"{rot.EXPLICACAO_CLASSIFICACAO[c]}</div>"
        for c in ordem)
    st.markdown(
        f"<div style='font-size:.76rem;color:{_layout.COR_TEXTO_SUAVE};"
        f"line-height:1.45;display:grid;gap:0 1.6rem;"
        f"grid-template-columns:repeat(auto-fit,minmax(22rem,1fr))'>"
        f"{itens}</div>", unsafe_allow_html=True)


def _legenda_dos_circulos(detalhe: dict) -> str:
    """Os dois círculos tracejados, com o traço imitado e o tamanho em metros.

    O traço é reproduzido em CSS com o mesmo padrão e a mesma cor do desenho no
    mapa (``dash_array`` 6,6 e 2,8), para o olho ligar a linha da legenda ao
    círculo certo sem precisar contar pixels.
    """
    limiar = float(detalhe.get("limiar_m") or 0.0)
    raio = float(detalhe.get("raio_de_busca_m") or 0.0)
    quantos = detalhe.get("candidatos_para_roteamento")

    def _amostra(cor: str, espessura: int) -> str:
        return (f"<span style='display:inline-block;width:2.1rem;"
                f"border-top:{espessura}px dashed {cor};"
                f"margin:0 .45rem .22rem 0'></span>")

    linhas = []
    if limiar:
        linhas.append(
            _amostra(_layout.COR_DESTAQUE_ESCURO, 2)
            + f"<b>Limiar do requisito — {_mil(limiar)} m.</b> É o critério da "
              "Portaria: a distância caminhável até o equipamento tem de caber "
              "dentro dele.")
    if raio and raio > limiar:
        extra = (f" Nesta análise, alcançou {quantos} equipamento(s)."
                 if isinstance(quantos, int) else "")
        linhas.append(
            _amostra(_layout.COR_TEXTO_SUAVE, 1)
            + f"<b>Raio de pré-seleção — {_mil(raio)} m</b> "
              f"({raio / limiar:.0f}× o limiar). Separa quem segue para a "
              "verificação da distância caminhável, para não medir pelo caminho "
              "equipamento distante. <b>Não é critério</b> e não tem efeito no veredito."
            + extra)
    if limiar:
        linhas.append(_contagem_dos_que_podem_atender(detalhe, limiar))
    if not linhas:
        return ""
    corpo = "".join(f"<div style='margin:.18rem 0'>{l}</div>" for l in linhas)
    return (f"<div style='font-size:.76rem;color:{_layout.COR_TEXTO_SUAVE};"
            f"line-height:1.45;margin-bottom:.35rem'>{corpo}</div>")


def _contagem_dos_que_podem_atender(detalhe: dict, limiar: float) -> str:
    """Quantos equipamentos têm a LINHA RETA dentro do limiar.

    É o subconjunto que interessa de verdade: como a linha reta é piso da
    distância caminhável, **só estes podem atender o requisito** — quem já
    ultrapassa o limiar em linha reta está reprovado por construção, e nenhuma
    medição de rede muda isso.

    Fica na legenda por ser a leitura que o número de pinos no mapa não dá: o mapa
    exibe quem entrou no raio de pré-seleção (2× o limiar), que é maior. E é
    também o número que dimensiona qualquer trabalho por equipamento — traçado de
    rota, conferência manual — sem depender de estimativa.
    """
    linhas = (detalhe or {}).get("equipamentos") or []
    dentro = [linha for linha in linhas
              if linha.get("metros_linha_reta") is not None
              and linha["metros_linha_reta"] <= limiar]
    if not linhas:
        return ""
    com_rota = sum(1 for linha in linhas if linha.get("rota"))
    tracado = (f" É para esses que o <b>traçado da rota</b> é desenhado "
               f"({com_rota} desenhado(s) nesta análise)." if com_rota else "")
    return (f"<span style='display:inline-block;width:2.1rem'></span>"
            f"<b>{len(dentro)} de {len(linhas)}</b> equipamento(s) avaliado(s) "
            f"tem a linha reta dentro do limiar — os únicos que <b>podem</b> "
            "atender o requisito; os demais já estão acima dele por construção."
            + tracado)


def _mil(valor: float) -> str:
    """Metros com separador de milhar no padrão brasileiro."""
    return f"{valor:,.0f}".replace(",", ".")
