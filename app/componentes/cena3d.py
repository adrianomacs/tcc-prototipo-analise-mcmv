"""Cena 3D (CesiumJS) compartilhada pelos relatórios.

O modelo IFC é posicionado no globo (CesiumJS + OpenStreetMap) via GLB
embutido + matriz ECEF. A cena é gravada como um HTML completo em
``app/static/`` e carregada por URL real (iframe src) — e não por ``srcdoc`` —,
pois o srcdoc do components.html impedia silenciosamente o carregamento dos
tiles.

Mapa de fundo alternável no painel "Camadas" (canto inferior esquerdo):
  * Mapa — tiles padrão do OpenStreetMap (padrão; o mesmo fundo dos mapas 2D);
  * Satélite — Esri World Imagery pelo endereço aberto. RESTRIÇÃO: os termos da
    Esri vedam USO COMERCIAL desse endereço sem chave. Serve ao protótipo
    acadêmico; para uso institucional/comercial (p. ex. na CAIXA), trocar
    pelo acesso com chave (ArcGIS Location Platform — mesma imagem, suporte
    nativo no CesiumJS via ``Cesium.ArcGisMapService.defaultAccessToken``),
    guardando a chave fora do Git.

Camadas opcionais da cena:
  * lista clicável de AMBIENTES (destaque do volume exato do IfcSpace);
  * lista clicável de REVESTIMENTOS (caixa do IfcCovering, lida do
    ``revestimentos.json`` da conversão, translúcida e com contorno, só sob
    seleção; o modelo segue com as cores dele);
  * MALHA municipal (IBGE), com liga/desliga no mesmo painel "Camadas".

Ambientes e revestimentos são pintados pelo RESULTADO de cada um (verde
atende, vermelho não atende, cinza não avaliado), que a página lê do
``detalhe`` do relatório; os artefatos de visualização trazem só geometria
(ADR-001), e o relatório não ganha campo para servir à tela (ADR-034).

Extraído de ``paginas/relatorio.py`` quando o relatório consolidado do grupo
"Programa de necessidades" passou a reutilizar a mesma cena.
"""

from __future__ import annotations

import json
import os
import time

from app.componentes.relatorio_ambientes import ROTULO_RESULTADO, resultado_por_ambiente

# Atenção ao caminho: media dirname(__file__) a partir deste próprio arquivo
# (`app/componentes/cena3d.py`), então gravava em `app/componentes/static/` —
# um nível fundo demais — enquanto a URL devolvida abaixo sempre assumiu
# `/app/static/`, onde o `enableStaticServing` do Streamlit realmente serve
# (a pasta ao lado de `app/main.py`). Resultado: "File not found" no iframe
# assim que o relatório chegava a desenhar a cena. `app/componentes` não pode
# importar `core.` (regra 1, ADR-003), daí o `dirname` extra em vez de usar
# `core.infra.caminhos.APP_DIR` (que já calcula isto certo).
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_STATIC_DIR = os.path.join(APP_DIR, "static")

# Cores do resultado na cena e na legenda da página (uma fonte só).
COR_RESULTADO = {"atende": "#2E7D32", "nao_atende": "#C62828", "neutro": "#7A8791"}

# Documento HTML completo da cena (servido por URL real, não srcdoc).
# __MODELO__/__MALHA__ são substituídos pelos blocos opcionais (ou vazio).
_DOC = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<link href="https://cesium.com/downloads/cesiumjs/releases/1.118/Build/Cesium/Widgets/widgets.css" rel="stylesheet">
<script src="https://cesium.com/downloads/cesiumjs/releases/1.118/Build/Cesium/Cesium.js"></script>
<style>
html,body{margin:0;height:100%}#c{width:100%;height:100%;background:#dfe8ef}
#painel{position:absolute;top:8px;right:8px;width:236px;max-height:92%;overflow:auto;
  background:rgba(255,255,255,.94);border:1px solid #bbb;border-radius:6px;
  font:12px/1.35 system-ui,sans-serif;z-index:10;box-shadow:0 1px 6px rgba(0,0,0,.2)}
#painel h4{margin:0;padding:8px 10px;background:#f2f4f7;border-bottom:1px solid #e2e6ea;font-size:12px}
#painel .amb{padding:6px 10px;border-top:1px solid #eee;cursor:pointer}
#painel .amb:hover{background:#eef3ff}
#painel .amb.sel{background:#ffe9a8}
#painel .amb small{color:#556}
#painel .acao{color:#345;font-style:italic}
#camadas{position:absolute;bottom:34px;left:8px;z-index:10;
  background:rgba(255,255,255,.94);border:1px solid #bbb;border-radius:6px;
  font:12px/1.35 system-ui,sans-serif;padding:7px 10px;
  box-shadow:0 1px 6px rgba(0,0,0,.2)}
#camadas .tit{font-weight:600;margin-bottom:3px}
#camadas label{display:flex;align-items:center;gap:6px;cursor:pointer;margin:2px 0}
#camadas hr{border:0;border-top:1px solid #e2e6ea;margin:5px 0}
</style>
</head>
<body>
<div id="c"></div>
<script>
Cesium.Ion.defaultAccessToken = "";
window.__viewer = null;
try {
  const prov = new Cesium.UrlTemplateImageryProvider({
    // Tiles padrão do OpenStreetMap — o mesmo fundo dos mapas 2D (Folium).
    // A CARTO passou a exigir chave de API (set/2026: marca d'água
    // "API KEY REQUIRED"). Política de uso do OSM: atribuição visível e
    // nada de download em massa — https://operations.osmfoundation.org/policies/tiles/
    url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    maximumLevel: 19,
    // Credit(texto, true) = exibido no rodapé da cena. Um texto solto vai só
    // para o link "Data attribution", e a política do OSM veda atribuição escondida.
    credit: new Cesium.Credit("© OpenStreetMap contributors", true)
  });
  const viewer = new Cesium.Viewer("c", {
    baseLayer: new Cesium.ImageryLayer(prov),
    baseLayerPicker:false, geocoder:false, timeline:false, animation:false,
    sceneModePicker:false, homeButton:false, navigationHelpButton:false,
    infoBox:false, selectionIndicator:false, fullscreenButton:false
  });
  window.__viewer = viewer;

  // Satélite: Esri World Imagery pelo endereço ABERTO (sem chave).
  // RESTRIÇÃO DE USO: os termos da Esri vedam uso COMERCIAL deste endereço.
  // Aceitável no protótipo acadêmico (TCC); para uso institucional/comercial,
  // trocar pelo acesso com chave (ArcGIS Location Platform) — ver docstring.
  // Camada criada oculta: o Cesium não baixa tiles de camada com show=false,
  // e o crédito da Esri só aparece no rodapé quando ela está visível.
  // Atenção à ordem {y}/{x} do serviço ArcGIS (linha antes da coluna).
  const satelite = viewer.imageryLayers.addImageryProvider(
    new Cesium.UrlTemplateImageryProvider({
      url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      maximumLevel: 19,
      credit: new Cesium.Credit("Powered by Esri — Fonte: Esri, Vantor, Earthstar Geographics e comunidade de usuários GIS", true)
    }));
  satelite.show = false;

  // Painel "Camadas": escolha do fundo (+ malha municipal, se houver).
  const cam = document.createElement("div"); cam.id = "camadas";
  cam.innerHTML = "<div class='tit'>Camadas</div>" +
    "<label><input type='radio' name='fundo' value='mapa'> Mapa (OpenStreetMap)</label>" +
    "<label><input type='radio' name='fundo' value='satelite'> Satélite (Esri)</label>";
  document.body.appendChild(cam);
  window.__camadas = cam;
  const mapaOsm = viewer.imageryLayers.get(0);   // camada base (OSM)
  function usarFundo(nome) {
    // Uma camada por vez: o OSM oculto não baixa tiles nem exibe crédito.
    satelite.show = (nome === "satelite");
    mapaOsm.show = !satelite.show;
    cam.querySelectorAll("input[name=fundo]").forEach(function (r) { r.checked = (r.value === nome); });
    try { localStorage.setItem("cena3d.fundo", nome); } catch (e) {}
  }
  cam.querySelectorAll("input[name=fundo]").forEach(function (r) {
    r.onchange = function () { usarFundo(r.value); };
  });
  let fundoSalvo = "mapa";   // lembra a escolha entre aberturas da cena (por navegador)
  try { fundoSalvo = localStorage.getItem("cena3d.fundo") || "mapa"; } catch (e) {}
  usarFundo(fundoSalvo === "satelite" ? "satelite" : "mapa");
  viewer.scene.skyBox.show=false; viewer.scene.sun.show=false; viewer.scene.moon.show=false;
  viewer.scene.skyAtmosphere.show=false;
  viewer.scene.backgroundColor = Cesium.Color.fromCssColorString("#dfe8ef");
  viewer.scene.globe.baseColor = Cesium.Color.fromCssColorString("#aebfcf");
  viewer.camera.flyTo({ destination: Cesium.Cartesian3.fromDegrees(-47.8828, -15.7939, 4000.0) });
} catch (e) { console.error(e); }
</script>
__MODELO__
__MALHA__
</body>
</html>
"""

_MODELO = """
<script>
(async function () {
  const v = window.__viewer;
  if (!v) return;
  const ESPACOS = __ESPACOS__;      // [{global_id, nome, area_m2, center?, raio?}]
  const AMBIENTES = __AMBIENTES__;  // [{global_id, nome, area_m2, categoria, resultado, rotulo}] — lista clicável
  // Revestimentos avaliados com a caixa da conversão: [{global_id, nome,
  // resultado, rotulo, absortancia, min, max, espessura}] (frame local z-up).
  const REVESTIMENTOS = __REVESTIMENTOS__;
  // Cor pelo RESULTADO, lido do relatório pela página (nunca do artefato de
  // visualização): verde atende, vermelho não atende, cinza não avaliado.
  const COR_RESULTADO = __CORES__;
  function corDe(res) {
    return Cesium.Color.fromCssColorString(COR_RESULTADO[res] || COR_RESULTADO.neutro);
  }
  const resultadoAmb = {};
  (AMBIENTES || []).forEach(function (a) { resultadoAmb[a.global_id] = a.resultado || "neutro"; });
  const transform = __TRANSFORM__;
  const MM = Cesium.Matrix4.fromArray(transform);
  let MMcur = Cesium.Matrix4.clone(MM);   // matriz corrente (base + ajuste visual)
  // A câmera vai direto ao modelo, sem passar pela vista inicial do país
  // enquanto o GLB carrega (o voo até Brasília e o reposicionamento depois).
  try {
    const org = Cesium.Cartographic.fromCartesian(Cesium.Matrix4.getTranslation(MM, new Cesium.Cartesian3()));
    v.camera.cancelFlight();
    v.camera.setView({ destination: Cesium.Cartesian3.fromRadians(org.longitude, org.latitude, org.height + 600.0) });
  } catch (e) { /* matriz sem origem geográfica: fica a vista inicial */ }
  const AJUSTES = __AJUSTES__;            // painel de ajuste visual (E/N/alt/rot)
  const ALTURA_ANCORA = __ALTURA_ANCORA__;

  // Geometria por ambiente: centro LOCAL + raio (zoom) + malha do IfcSpace.
  // O centro é convertido a ECEF sob demanda com a matriz corrente (MMcur),
  // para acompanhar o ajuste visual do modelo.
  const geo = {};
  ESPACOS.forEach(function (e) {
    if (e.center && e.center.length === 3) {
      geo[e.global_id] = {
        centro: Cesium.Cartesian3.fromArray(e.center),
        raio: (typeof e.raio === "number" && e.raio > 0) ? e.raio : 2.0,
        mesh: (e.mesh && e.mesh.verts && e.mesh.faces) ? e.mesh : null,
      };
    }
  });

  // Vértices da malha (locais, m) -> ECEF, aplicando a matriz CORRENTE do modelo.
  function vertsEcef(verts) {
    const n = verts.length, out = new Float64Array(n);
    const p = new Cesium.Cartesian3(), o = new Cesium.Cartesian3();
    for (let i = 0; i < n; i += 3) {
      Cesium.Cartesian3.fromArray(verts, i, p);
      Cesium.Matrix4.multiplyByPoint(MMcur, p, o);
      out[i] = o.x; out[i + 1] = o.y; out[i + 2] = o.z;
    }
    return out;
  }
  // Arestas únicas a partir dos triângulos (para o contorno).
  function arestas(faces) {
    const vistos = new Set(), e = [];
    for (let i = 0; i < faces.length; i += 3) {
      const t = [faces[i], faces[i + 1], faces[i + 2]];
      for (let k = 0; k < 3; k++) {
        let a = t[k], b = t[(k + 1) % 3];
        if (a > b) { const z = a; a = b; b = z; }
        const chave = a + "_" + b;
        if (!vistos.has(chave)) { vistos.add(chave); e.push(a, b); }
      }
    }
    return e;
  }
  function primitiveMalha(mesh, cor, primitiveType, indices) {
    return new Cesium.Primitive({
      geometryInstances: new Cesium.GeometryInstance({
        geometry: new Cesium.Geometry({
          attributes: { position: new Cesium.GeometryAttribute({
            componentDatatype: Cesium.ComponentDatatype.DOUBLE,
            componentsPerAttribute: 3, values: vertsEcef(mesh.verts) }) },
          indices: indices, primitiveType: primitiveType,
          boundingSphere: Cesium.BoundingSphere.fromVertices(vertsEcef(mesh.verts)),
        }),
        attributes: { color: Cesium.ColorGeometryInstanceAttribute.fromColor(cor) },
      }),
      appearance: new Cesium.PerInstanceColorAppearance({
        flat: true, translucent: cor.alpha < 1.0,
      }),
      asynchronous: false,
    });
  }

  let model = null, realceFill = null, realceEdges = null;
  let realceConjunto = null, conjuntoAtivo = false;   // destaque do conjunto (todas as áreas)
  const nos = {};   // GlobalId -> nó do IfcSpace no GLB (mantido oculto)
  let revPrims = [];   // caixas dos revestimentos à vista (seleção ou todas)

  try {
    // GLB publicado à parte (endereço) ou, na falta dele, embutido em base64.
    const GLB_URL = __GLB_URL__;
    let url = GLB_URL;
    if (!url) {
      const b64 = "__GLB__";
      const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
      url = URL.createObjectURL(new Blob([bytes], { type: "model/gltf-binary" }));
    }
    model = await Cesium.Model.fromGltfAsync({
      url: url, modelMatrix: MM,
      upAxis: Cesium.Axis.Y, forwardAxis: Cesium.Axis.X  // convencao validada p/ o GLB do IfcOpenShell
    });
    v.scene.primitives.add(model);
    model.readyEvent.addEventListener(function () {
      ESPACOS.forEach(function (e) {              // oculta os volumes de espaço
        try {
          const n = model.getNode(e.global_id);
          if (n) { n.show = false; nos[e.global_id] = n; }
        } catch (err) { /* getNode indisponível nesta versão */ }
      });
      if (AMBIENTES && AMBIENTES.length) construirPainel(AMBIENTES);
      else if (REVESTIMENTOS.length) construirPainelRevestimentos(REVESTIMENTOS);
      if (AJUSTES) construirPainelAjustes();

      // Reduz a sensibilidade do scroll (padrão do Cesium é 5.0; menor = mais suave).
      v.scene.screenSpaceCameraController._zoomFactor = 3.0;

      vistaInicial(1.5);
    });
  } catch (e) { console.error("modelo:", e); }

  function raioX(ligar) {
    if (model) model.color = ligar ? Cesium.Color.WHITE.withAlpha(0.16) : Cesium.Color.WHITE;
  }
  function removerRealce() {
    if (realceFill) { v.scene.primitives.remove(realceFill); realceFill = null; }
    if (realceEdges) { v.scene.primitives.remove(realceEdges); realceEdges = null; }
    if (realceConjunto) { v.scene.primitives.remove(realceConjunto); realceConjunto = null; }
    conjuntoAtivo = false;
  }
  // Uma instância por malha, cada uma na sua cor, numa primitiva só.
  function instancia(mesh, cor, primitiveType, indices) {
    const ep = vertsEcef(mesh.verts);
    return new Cesium.GeometryInstance({
      geometry: new Cesium.Geometry({
        attributes: { position: new Cesium.GeometryAttribute({
          componentDatatype: Cesium.ComponentDatatype.DOUBLE,
          componentsPerAttribute: 3, values: ep }) },
        indices: indices, primitiveType: primitiveType,
        boundingSphere: Cesium.BoundingSphere.fromVertices(ep),
      }),
      attributes: { color: Cesium.ColorGeometryInstanceAttribute.fromColor(cor) },
    });
  }
  function primitivaDe(instancias, translucida) {
    if (!instancias.length) return null;
    return new Cesium.Primitive({
      geometryInstances: instancias,
      appearance: new Cesium.PerInstanceColorAppearance({ flat: true, translucent: translucida }),
      asynchronous: false,
    });
  }
  // Destaque do conjunto: cada ambiente da regra no volume exato e na cor do resultado.
  function primitivaConjunto(gids) {
    const inst = [];
    gids.forEach(function (gid) {
      const g = geo[gid];
      if (!g || !g.mesh) return;
      inst.push(instancia(g.mesh, corDe(resultadoAmb[gid]).withAlpha(0.45),
                          Cesium.PrimitiveType.TRIANGLES, new Uint32Array(g.mesh.faces)));
    });
    return primitivaDe(inst, true);
  }

  // --- Revestimentos: caixa envolvente sob seleção -------------------------
  // O modelo fica sempre com as cores dele: nenhum nó é ocultado e nada é
  // desenhado por padrão. Ao clicar num revestimento, a caixa que o envolve
  // aparece translúcida, com contorno, na cor do resultado, com o modelo em
  // raio-X como nos ambientes; "destacar todos" mostra todas de uma vez. A caixa segue os eixos do modelo, então a de uma
  // placa de fachada envolve também as aberturas dela.
  const FACES_CAIXA = [0,1,2, 0,2,3, 4,6,5, 4,7,6, 0,4,5, 0,5,1,
                       1,5,6, 1,6,2, 2,6,7, 2,7,3, 3,7,4, 3,4,0];
  const ARESTAS_CAIXA = [0,1, 1,2, 2,3, 3,0, 4,5, 5,6, 6,7, 7,4, 0,4, 1,5, 2,6, 3,7];
  // Folga: a caixa cresce um pouco para fora do elemento, e as faces dela não
  // disputam a mesma superfície com as do revestimento (que segue à vista).
  const FOLGA_CAIXA = 0.02;
  function malhaCaixa(r) {
    const f = FOLGA_CAIXA;
    const a = [r.min[0] - f, r.min[1] - f, r.min[2] - f];
    const b = [r.max[0] + f, r.max[1] + f, r.max[2] + f];
    return { verts: [a[0],a[1],a[2], b[0],a[1],a[2], b[0],b[1],a[2], a[0],b[1],a[2],
                     a[0],a[1],b[2], b[0],a[1],b[2], b[0],b[1],b[2], a[0],b[1],b[2]] };
  }
  let revTodos = false;
  function limparRevestimento() {
    revPrims.forEach(function (p) { v.scene.primitives.remove(p); });
    revPrims = [];
    revTodos = false;
  }
  function desenharCaixas(itens) {
    const faces = [], contornos = [];
    itens.forEach(function (r) {
      if (!r.min || !r.max) return;
      const m = malhaCaixa(r), cor = corDe(r.resultado);
      faces.push(instancia(m, cor.withAlpha(0.35), Cesium.PrimitiveType.TRIANGLES,
                           new Uint16Array(FACES_CAIXA)));
      contornos.push(instancia(m, cor, Cesium.PrimitiveType.LINES, new Uint16Array(ARESTAS_CAIXA)));
    });
    [primitivaDe(faces, true), primitivaDe(contornos, false)]
      .forEach(function (p) { if (p) revPrims.push(v.scene.primitives.add(p)); });
  }
  function selecionarRevestimento(r) {
    document.querySelectorAll("#painel .amb").forEach(function (el) {
      el.classList.toggle("sel", el.dataset.gid === r.global_id);
    });
    limparRevestimento();
    raioX(true);          // como nos ambientes: o modelo translúcido deixa ver a caixa
    if (!r.min || !r.max) { console.warn("sem caixa para", r.global_id); return; }
    desenharCaixas([r]);
    const c = new Cesium.Cartesian3((r.min[0] + r.max[0]) / 2, (r.min[1] + r.max[1]) / 2,
                                    (r.min[2] + r.max[2]) / 2);
    const raio = Math.max(Math.hypot(r.max[0] - r.min[0], r.max[1] - r.min[1],
                                     r.max[2] - r.min[2]) / 2, 1.5);
    const pos = Cesium.Matrix4.multiplyByPoint(MMcur, c, new Cesium.Cartesian3());
    v.camera.flyToBoundingSphere(new Cesium.BoundingSphere(pos, raio),
      { duration: 1.0, offset: new Cesium.HeadingPitchRange(0.0, -0.5, Math.max(raio * 4.0, 10.0)) });
  }
  function destacarTodosRevestimentos() {
    const ligar = !revTodos;
    limparRevestimento();
    document.querySelectorAll("#painel .amb.sel").forEach(function (el) { el.classList.remove("sel"); });
    raioX(ligar);
    if (ligar) { desenharCaixas(REVESTIMENTOS); revTodos = true; vistaInicial(1.0); }
  }
  function destacarConjunto() {
    removerRealce();
    document.querySelectorAll("#painel .amb.sel").forEach(function (el) { el.classList.remove("sel"); });
    const gids = (AMBIENTES || []).map(function (a) { return a.global_id; })
      .filter(function (k) { return geo[k] && geo[k].mesh; });
    const prim = primitivaConjunto(gids);
    if (prim) { realceConjunto = v.scene.primitives.add(prim); conjuntoAtivo = true; }
    raioX(true);
    vistaInicial(1.0);   // enquadra o modelo inteiro (visão consolidada das áreas)
  }
  function vistaInicial(dur) {
    if (!model) return;
    v.camera.flyToBoundingSphere(model.boundingSphere,
      { duration: (dur === undefined ? 1.0 : dur),
        offset: new Cesium.HeadingPitchRange(0.0, -0.5, model.boundingSphere.radius * 6.0) });
  }
  function restaurar() {   // volta à visão inicial e limpa realce/raio-X/seleção
    removerRealce();
    limparRevestimento();
    raioX(false);
    document.querySelectorAll("#painel .amb.sel").forEach(function (el) { el.classList.remove("sel"); });
    vistaInicial(1.0);
  }
  function limpar() {
    removerRealce();
    limparRevestimento();
    raioX(false);
    document.querySelectorAll("#painel .amb.sel").forEach(function (el) { el.classList.remove("sel"); });
  }
  function selecionar(gid) {
    document.querySelectorAll("#painel .amb").forEach(function (el) {
      el.classList.toggle("sel", el.dataset.gid === gid);
    });
    raioX(true);          // edifício translúcido (raio-X) — sempre
    removerRealce();

    const g = geo[gid];
    if (!g) { console.warn("sem geometria para", gid); return; }
    const pos = Cesium.Matrix4.multiplyByPoint(MMcur, g.centro, new Cesium.Cartesian3());
    if (g.mesh) {
      // volume exato do ambiente, na cor do resultado: preenchimento
      // translúcido + contorno das arestas
      const cor = corDe(resultadoAmb[gid]);
      realceFill = v.scene.primitives.add(primitiveMalha(
        g.mesh, cor.withAlpha(0.45),
        Cesium.PrimitiveType.TRIANGLES, new Uint32Array(g.mesh.faces)));
      realceEdges = v.scene.primitives.add(primitiveMalha(
        g.mesh, cor,
        Cesium.PrimitiveType.LINES, new Uint32Array(arestas(g.mesh.faces))));
    }
    v.camera.flyToBoundingSphere(new Cesium.BoundingSphere(pos, Math.max(g.raio, 1.5)),
      { duration: 1.0, offset: new Cesium.HeadingPitchRange(0.0, -0.5, Math.max(g.raio * 4.0, 10.0)) });
  }

  // --- Ajuste visual do posicionamento (apenas exibição) -------------------
  // Desloca/rotaciona o modelo num referencial local Leste-Norte-Cima (ENU)
  // ancorado na origem da matriz base. NÃO altera o IFC nem a análise.
  function aplicarAjustes(dE, dN, dU, rotG) {
    if (!model) return;
    limpar();   // realces antigos ficariam no lugar antigo
    const origem = Cesium.Matrix4.getTranslation(MM, new Cesium.Cartesian3());
    const enu = Cesium.Transforms.eastNorthUpToFixedFrame(origem);
    const enuInv = Cesium.Matrix4.inverse(enu, new Cesium.Matrix4());
    const rot = Cesium.Matrix3.fromRotationZ(Cesium.Math.toRadians(rotG || 0));
    const local = Cesium.Matrix4.fromRotationTranslation(
      rot, new Cesium.Cartesian3(dE || 0, dN || 0, dU || 0));
    let delta = Cesium.Matrix4.multiply(local, enuInv, new Cesium.Matrix4());
    delta = Cesium.Matrix4.multiply(enu, delta, delta);
    MMcur = Cesium.Matrix4.multiply(delta, MM, new Cesium.Matrix4());
    model.modelMatrix = MMcur;
  }

  function construirPainelAjustes() {
    const p = document.createElement("div");
    p.style.cssText = "position:absolute;top:8px;left:8px;width:198px;z-index:10;" +
      "background:rgba(255,255,255,.94);border:1px solid #bbb;border-radius:6px;" +
      "font:12px/1.35 system-ui,sans-serif;box-shadow:0 1px 6px rgba(0,0,0,.2)";
    p.innerHTML = "<h4 style='margin:0;padding:8px 10px;background:#f2f4f7;" +
      "border-bottom:1px solid #e2e6ea;font-size:12px'>Ajuste visual do modelo</h4>";

    const campos = [
      { chave: "e",   rotulo: "Leste (m)",   passo: 0.5 },
      { chave: "n",   rotulo: "Norte (m)",   passo: 0.5 },
      { chave: "u",   rotulo: "Altura (m)",  passo: 0.5 },
      { chave: "rot", rotulo: "Rotação (°)", passo: 1 },
    ];
    const inputs = {};
    campos.forEach(function (c) {
      const row = document.createElement("div");
      row.style.cssText = "display:flex;align-items:center;justify-content:space-between;" +
        "gap:6px;padding:4px 10px";
      const lab = document.createElement("span");
      lab.textContent = c.rotulo;
      const inp = document.createElement("input");
      inp.type = "number"; inp.step = c.passo; inp.value = "0";
      inp.style.cssText = "width:86px;padding:2px 4px;font:12px system-ui,sans-serif";
      inp.oninput = aplicar;
      inputs[c.chave] = inp;
      row.appendChild(lab); row.appendChild(inp);
      p.appendChild(row);
    });

    function aplicar() {
      aplicarAjustes(parseFloat(inputs.e.value) || 0, parseFloat(inputs.n.value) || 0,
                     parseFloat(inputs.u.value) || 0, parseFloat(inputs.rot.value) || 0);
    }

    function botao(texto, titulo, acaoFn) {
      const b = document.createElement("div");
      b.className = "amb acao"; b.textContent = texto; b.title = titulo;
      b.style.cssText = "padding:6px 10px;border-top:1px solid #eee;cursor:pointer;" +
        "color:#345;font-style:italic";
      b.onmouseenter = function () { b.style.background = "#eef3ff"; };
      b.onmouseleave = function () { b.style.background = ""; };
      b.onclick = acaoFn;
      p.appendChild(b);
    }
    if (ALTURA_ANCORA) {
      botao("⬇ colar ao chão (−" + ALTURA_ANCORA.toFixed(1) + " m)",
            "Compensa a altura da âncora do modelo (visualização sem terreno)",
            function () { inputs.u.value = String(-ALTURA_ANCORA); aplicar(); });
    }
    botao("⟲ restaurar vista inicial", "Zera os ajustes e reenquadra a câmera",
          function () {
            inputs.e.value = inputs.n.value = inputs.u.value = inputs.rot.value = "0";
            aplicar();
            vistaInicial(1.0);
          });

    const nota = document.createElement("div");
    nota.style.cssText = "padding:6px 10px;border-top:1px solid #eee;color:#556;font-size:11px";
    nota.textContent = "Apenas visualização — não altera o modelo IFC nem os resultados da análise.";
    p.appendChild(nota);

    document.body.appendChild(p);
  }
  function bolinha(res) {
    return "<span style='display:inline-block;width:9px;height:9px;border-radius:50%;" +
      "margin-right:5px;vertical-align:0;background:" +
      (COR_RESULTADO[res] || COR_RESULTADO.neutro) + "'></span>";
  }
  function construirPainelRevestimentos(itens) {
    const lista = itens.slice().sort(function (x, y) {
      const ordem = { nao_atende: 0, neutro: 1, atende: 2 };
      return (ordem[x.resultado] - ordem[y.resultado]) ||
        (x.nome || "").localeCompare(y.nome || "", "pt", { sensitivity: "base" });
    });
    const p = document.createElement("div"); p.id = "painel";
    const h = document.createElement("h4"); h.textContent = "Revestimentos (" + lista.length + ")";
    p.appendChild(h);
    const bReset = document.createElement("div"); bReset.className = "amb acao"; bReset.textContent = "⟲ restaurar visão";
    bReset.onclick = function () { restaurar(); };
    p.appendChild(bReset);
    const btn = document.createElement("div"); btn.className = "amb acao"; btn.textContent = "◯ limpar seleção";
    btn.onclick = function () { limpar(); };
    p.appendChild(btn);
    const bTodos = document.createElement("div"); bTodos.className = "amb acao"; bTodos.textContent = "▣ destacar todos";
    bTodos.onclick = function () { destacarTodosRevestimentos(); };
    p.appendChild(bTodos);
    lista.forEach(function (r) {
      const row = document.createElement("div"); row.className = "amb"; row.dataset.gid = r.global_id;
      const abs = (typeof r.absortancia === "number")
        ? "absortância " + r.absortancia.toFixed(2).replace(".", ",") + " · " : "";
      const semCaixa = (r.min && r.max) ? "" : " title='sem geometria, fora da cena'";
      row.innerHTML = bolinha(r.resultado) + "<b" + semCaixa + ">" + (r.nome || "(sem nome)") +
        "</b><br><small>" + abs + (r.rotulo || "") + "</small>";
      row.onclick = function () { selecionarRevestimento(r); };
      p.appendChild(row);
    });
    document.body.appendChild(p);
  }
  function construirPainel(ambientes) {
    const norm = function (s) {
      s = (s || "").toLowerCase().normalize("NFD");
      let out = "";
      for (let i = 0; i < s.length; i++) {
        const c = s.charCodeAt(i);
        if (c < 768 || c > 879) out += s[i];   // 0x300..0x36F = marcas combinantes (acentos)
      }
      return out;
    };
    const lista = ambientes.slice().sort(function (x, y) {
      return (x.nome || "").localeCompare(y.nome || "", "pt", { sensitivity: "base" });
    });

    const p = document.createElement("div"); p.id = "painel";
    const h = document.createElement("h4"); h.textContent = "Ambientes (" + lista.length + ")";
    p.appendChild(h);

    const busca = document.createElement("input");
    busca.type = "text"; busca.placeholder = "filtrar por nome…";
    busca.style.cssText = "width:calc(100% - 16px);margin:6px 8px;padding:4px 6px;box-sizing:border-box;font:12px system-ui,sans-serif";
    p.appendChild(busca);
    const cont = document.createElement("div");
    cont.style.cssText = "padding:0 10px 4px;color:#556;font-size:11px";
    p.appendChild(cont);

    const bReset = document.createElement("div"); bReset.className = "amb acao"; bReset.textContent = "⟲ restaurar visão";
    bReset.onclick = function () { restaurar(); };
    p.appendChild(bReset);
    const bConj = document.createElement("div"); bConj.className = "amb acao"; bConj.textContent = "▣ destacar todas as áreas";
    bConj.onclick = function () { if (conjuntoAtivo) { limpar(); } else { destacarConjunto(); } };
    p.appendChild(bConj);
    const btn = document.createElement("div"); btn.className = "amb acao"; btn.textContent = "◯ limpar seleção";
    btn.onclick = function () { limpar(); };
    p.appendChild(btn);

    lista.forEach(function (a) {
      const row = document.createElement("div"); row.className = "amb amb-item"; row.dataset.gid = a.global_id;
      row.dataset.norm = norm(a.nome);
      const area = (typeof a.area_m2 === "number") ? a.area_m2.toFixed(2) + " m²" : "—";
      const cat = a.categoria ? " · " + a.categoria : "";
      const res = a.rotulo ? " · " + a.rotulo : "";
      const semGeo = geo[a.global_id] ? "" : " title='sem geometria, sem zoom'";
      row.innerHTML = bolinha(a.resultado) + "<b" + semGeo + ">" + (a.nome || "(sem nome)") +
        "</b><br><small>" + area + cat + res + "</small>";
      row.onclick = function () { selecionar(a.global_id); };
      p.appendChild(row);
    });

    function filtrar() {
      const termo = norm(busca.value);
      let vis = 0;
      p.querySelectorAll(".amb-item").forEach(function (el) {
        const ok = !termo || el.dataset.norm.indexOf(termo) !== -1;
        el.style.display = ok ? "" : "none";
        if (ok) vis++;
      });
      cont.textContent = termo ? (vis + " de " + lista.length + " ambiente(s)")
                               : (lista.length + " ambiente(s)");
    }
    busca.addEventListener("input", filtrar);
    filtrar();

    document.body.appendChild(p);
  }
})();
</script>
"""

# Limites do município declarado (malha IBGE), desenhados sobre o globo, com
# painel embutido (canto inferior esquerdo) para exibir/ocultar o contorno.
# __VOAR__ = true quando não há modelo posicionável (a câmera enquadra a malha).
_MALHA = """
<script>
(async function () {
  try {
    const v = window.__viewer;
    if (!v) return;
    const gj = __MALHA_GEOJSON__;
    const ds = await Cesium.GeoJsonDataSource.load(gj, {
      stroke: Cesium.Color.fromCssColorString("#155066"),
      strokeWidth: 5,
      fill: Cesium.Color.fromCssColorString("#1F6F8B").withAlpha(0.22),
      clampToGround: true
    });
    v.dataSources.add(ds);
    if (__VOAR__) { v.flyTo(ds); }

    // Liga/desliga da malha no painel "Camadas" (criado junto do viewer,
    // canto inferior esquerdo), abaixo da escolha do mapa de fundo.
    const p = window.__camadas;
    if (!p) return;
    p.appendChild(document.createElement("hr"));
    const rot = document.createElement("label");
    rot.style.cssText = "display:flex;align-items:center;gap:6px;cursor:pointer";
    const cx = document.createElement("input");
    cx.type = "checkbox"; cx.checked = true;
    cx.onchange = function () { ds.show = cx.checked; };
    const txt = document.createElement("span");
    txt.innerHTML = "<span style='display:inline-block;width:10px;height:10px;" +
      "border:2px solid #155066;background:rgba(31,111,139,.25);" +
      "border-radius:2px;vertical-align:-1px'></span> Malha municipal (IBGE)";
    rot.appendChild(cx); rot.appendChild(txt);
    p.appendChild(rot);
  } catch (e) { console.error("malha municipal:", e); }
})();
</script>
"""


def gravar_cena(viz: dict, ambientes: list | None = None,
                malha: dict | None = None, ajustes: bool = False,
                revestimentos: list | None = None) -> str:
    """Grava a cena em app/static/cena.html e devolve a URL servida (com cache-bust).

    ``ambientes`` (opcional) alimenta a lista clicável de ambientes dentro da
    cena; os IfcSpace de ``viz['espacos']`` são ocultados por padrão em qualquer
    caso. ``malha`` (opcional) é o GeoJSON do município declarado; sem modelo
    posicionável, a câmera enquadra a malha. ``ajustes`` habilita o painel de
    ajuste visual do posicionamento (E/N/altura/rotação — só exibição, efêmero;
    inclui o atalho 'colar ao chão' com a altura da âncora). ``revestimentos``
    (opcional) são os itens de :func:`revestimentos_com_caixas`.
    """
    posicionavel = bool(viz and viz.get("posicionavel")
                        and (viz.get("glb_url") or viz.get("glb_b64"))
                        and viz.get("transform"))
    if posicionavel:
        espacos = (viz or {}).get("espacos") or []
        try:
            altura_ancora = float((viz.get("ancora") or {}).get("altura") or 0.0)
        except (TypeError, ValueError):
            altura_ancora = 0.0
        # O GLB entra por último: cada ``replace`` copia a string inteira, e
        # com o GLB dentro (centenas de MB no E3) cada cópia custava segundos.
        modelo = (_MODELO.replace("__TRANSFORM__", json.dumps(viz["transform"]))
                         .replace("__ESPACOS__", json.dumps(espacos))
                         .replace("__AMBIENTES__", json.dumps(ambientes or []))
                         .replace("__REVESTIMENTOS__", json.dumps(revestimentos or []))
                         .replace("__CORES__", json.dumps(COR_RESULTADO))
                         .replace("__AJUSTES__", "true" if ajustes else "false")
                         .replace("__ALTURA_ANCORA__", json.dumps(round(altura_ancora, 2)))
                         .replace("__GLB_URL__", json.dumps(viz.get("glb_url")))
                         .replace("__GLB__", "" if viz.get("glb_url") else viz["glb_b64"]))
    else:
        modelo = ""
    if malha:
        bloco_malha = (_MALHA.replace("__MALHA_GEOJSON__", json.dumps(malha))
                             .replace("__VOAR__", "false" if posicionavel else "true"))
    else:
        bloco_malha = ""
    os.makedirs(_STATIC_DIR, exist_ok=True)
    with open(os.path.join(_STATIC_DIR, "cena.html"), "w", encoding="utf-8") as f:
        antes, depois = _DOC.replace("__MALHA__", bloco_malha).split("__MODELO__")
        f.write(antes)
        f.write(modelo)
        f.write(depois)
    return f"/app/static/cena.html?v={int(time.time())}"


def ambientes_para_cena(detalhe: dict, estado: str | None = None) -> list[dict]:
    """Lista enxuta de ambientes para a cena clicável, cada um com o seu
    resultado (``estado`` é o da regra, que decide a cor na área útil)."""
    resultados = resultado_por_ambiente(detalhe, estado)
    itens = []
    for a in ((detalhe or {}).get("ambientes") or []):
        gid = a.get("global_id")
        if not gid:
            continue
        res = resultados.get(gid, "neutro")
        itens.append({"global_id": gid, "nome": a.get("nome"),
                      "area_m2": a.get("area_m2"),
                      "categoria": a.get("categoria_rotulo"),
                      "resultado": res, "rotulo": ROTULO_RESULTADO[res]})
    return itens


def revestimentos_com_caixas(itens: list[dict], caixas: list[dict]) -> list[dict]:
    """Junta a cada revestimento avaliado (com o resultado vindo do relatório)
    a caixa que a conversão gravou (``revestimentos.json``). Quem não tem
    caixa segue na lista, sem ``min``/``max``, e fica fora da cena."""
    por_gid = {c.get("global_id"): c for c in caixas or [] if c.get("global_id")}
    juntos = []
    for item in itens or []:
        cx = por_gid.get(item.get("global_id")) or {}
        novo = dict(item)
        if cx.get("min") and cx.get("max"):
            novo.update({"min": cx["min"], "max": cx["max"],
                         "espessura": cx.get("espessura", 0.0)})
        juntos.append(novo)
    return juntos


def legenda_cores() -> str:
    """As três cores do resultado, em HTML, para a legenda sob a cena."""
    rotulos = (("atende", "atende"), ("nao_atende", "não atende"),
               ("neutro", "não avaliado"))
    partes = [f"<span style='display:inline-block;width:10px;height:10px;"
              f"border-radius:50%;background:{COR_RESULTADO[k]};"
              f"vertical-align:-1px;margin-right:4px'></span>{r}"
              for k, r in rotulos]
    return ("<span style='font-size:0.875rem;color:#5B6770'>"
            + " &nbsp; ".join(partes) + "</span>")
