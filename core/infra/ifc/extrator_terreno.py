"""Terreno a partir do modelo BIM — cascata sobre o IfcSite.

Duas entidades, dois conceitos — e a documentação do IFC4.3 é explícita:

* **IfcSite** é *"a defined area of land ... on which the project construction
  is to be completed"*, e sua representação ``FootPrint`` é *"given by either a
  single 2D curve (such as IfcPolyline or IfcCompositeCurve), or by a list of 2D
  curves (in case of inner boundaries)"*. É o **limite** do terreno.
* **IfcGeographicElement** é *"a generalization of all elements within a
  geographical landscape ... such as trees or terrain"*. Com
  ``PredefinedType = TERRAIN``, é o portador que a norma designa para a
  **superfície** do terreno.

Ler o terreno de um ``IfcGeographicElement`` TERRAIN, portanto, **não é aceitar
substituto semântico** — é seguir o padrão (caso de um
modelo real em que o IfcSite não tem geometria e o terreno está num TERRAIN). O que segue vetado é
``IfcSpace``, ``IfcAnnotation`` e afins fazendo o papel de terreno: aí a classe
da entidade está errada, e o modelo recebe **diagnóstico normativo**.

A ressalva que sobrevive é de conteúdo, não de classe: a superfície modelada tem
a **extensão do relevo**, que pode exceder o limite legal do lote. Vem sempre com
aviso.

Cascata, do melhor ao indisponível:

1. **Poligonal do IfcSite** — FootPrint de preferência, Body com aviso.
2. **Poligonal do IfcGeographicElement TERRAIN** — com ressalva de extensão.
   Havendo vários (é normal: terreno de implantação + escavações), vale o de
   **maior área em planta**, nomeando os ignorados. Aceito onde estiver contido:
   exportadores alocam o terreno no pavimento, e a classe estar certa é o que
   importa — a contenção fora do IfcSite é registrada como lacuna.
3. **Ponto pela coordenada do IfcSite** (RefLatitude/RefLongitude) — precisão
   ``declarada``, com aviso de que não é centróide de poligonal.
4. **Ponto pela origem do MapConversion** — último recurso, com aviso forte:
   esse é o **ponto de inserção do modelo**, não o centro do terreno.
5. **Nada** — diagnóstico normativo; CSV e mapa ficam como fonte alternativa de
   insumo, nunca como conserto do modelo.

Os passos 1 e 2 exigem **LoGeoRef 50** (IfcProjectedCRS + IfcMapConversion):
sem CRS projetado a geometria existe no modelo e não pode ser levada ao
território.

**Divergência entre as duas posições do modelo.** Quando o terreno sai do
passo 3 e o modelo traz um IfcMapConversion utilizável, a origem dele é
reprojetada e confrontada com a coordenada do IfcSite. Acima de
``TOLERANCIA_DIVERGENCIA_POSICAO_M``, as duas posições vão para a procedência
do terreno (``divergencia_posicao``) e para o ``detalhe``, e um aviso técnico
entra na lista de avisos. É diagnóstico (ADR-038, na linha do ADR-032): a
precedência da cascata não muda, nenhum veredito depende disso e o extrator não escolhe
entre as duas posições. Quem explica ao usuário, e diz o que fazer, é a tela.

Vários IfcSite: decomposição legítima (``.COMPLEX.`` agregando ``.PARTIAL.``)
usa a raiz da agregação; **sites irmãos independentes** (vários ``.ELEMENT.``
com geometria) são recusados, porque aí a ambiguidade é real.

UNIDADES (ponto sensível, mesmo do resto do projeto): a geometria do
``create_shape`` já vem em **metros**, qualquer que seja a unidade do projeto;
já os pontos lidos direto de uma curva do IFC e a matriz de placement vêm na
**unidade do projeto** e precisam da escala. Os offsets do MapConversion chegam
em metros pelo ``leitor_crs``. Errar isso desloca o terreno por quilômetros.

Uso na linha de comando (é assim que se valida contra um IFC real)::

    python -m core.infra.ifc.extrator_terreno "entradas/ifc/UT_GeoRef_1.ifc"
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from core.dominio import geometria as crs
from core.dominio import terreno as trn
from core.dominio.terreno import formatar_numero
from core.infra.ifc.georref import ancora, leitor_crs, logeoref, transformacao

_log = logging.getLogger(__name__)

NIVEL_EXIGIDO = logeoref.ALVO_PADRAO   # 50
TOLERANCIA_AREA = 0.05                 # 5% no cross-check com o Pset

# Distância, em metros, entre a coordenada do IfcSite e a origem do
# IfcMapConversion acima da qual a divergência é registrada (ADR-038). Fica acima do que
# o arredondamento da latitude/longitude (segundos inteiros, cerca de 30 m) e a
# distância entre o centro do lote e o ponto de inserção do modelo explicam,
# e a um quarto do menor limiar de distância a equipamento do recorte
# (1.000 m), para que uma posição que já pesa na medida não passe em silêncio.
TOLERANCIA_DIVERGENCIA_POSICAO_M = 250.0

# Como o terreno DEVERIA estar modelado — texto reaproveitado nos diagnósticos.
REQUISITO_DE_INFORMACAO = (
    "O terreno deve ser representado por um **IfcSite** com representação "
    "geométrica (`FootPrint`, de preferência, ou `Body`), sob "
    "**IfcProjectedCRS + IfcMapConversion** em SIRGAS 2000 / UTM "
    "(LoGeoRef 50). Alternativamente, o IfcSite deve trazer "
    "`RefLatitude`/`RefLongitude`, o que permite apenas o centro do terreno."
)


@dataclass
class Resolucao:
    """Saída da cascata: o terreno (se houver) e o porquê, sempre."""

    terreno: Any = None
    diagnostico: list[str] = field(default_factory=list)
    detalhe: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.terreno is not None


# ---------------------------------------------------------------------------
# Cascata
# ---------------------------------------------------------------------------

def resolver_arquivo(caminho: str) -> Resolucao:
    """Abre o IFC e resolve o terreno — **ponto de entrada recomendado**.

    Concentra aqui a abertura defensiva para que CLI e interface tenham o mesmo
    comportamento: schema não suportado vira diagnóstico com o nome do schema,
    e não um traceback.
    """
    import os

    from core.infra.ifc import leitor_modelo as leitor_ifc

    modelo, erro = leitor_ifc.abrir_seguro(caminho)
    if erro:
        return Resolucao(diagnostico=[erro], detalhe={
            "arquivo": os.path.basename(caminho),
            "schema": leitor_ifc.schema_declarado(caminho),
            "abertura_falhou": True,
        })
    resolucao = resolver(modelo, nome_arquivo=os.path.basename(caminho))
    if resolucao.terreno is not None:
        # ADR-035: o conteúdo de que o terreno foi lido, para o relatório citá-lo.
        from core.infra import impressao_digital
        resolucao.terreno.procedencia["sha256"] = impressao_digital.sha256(caminho)
    return resolucao


def resolver(modelo: Any, *, nome_arquivo: str = "") -> Resolucao:
    """Deriva o terreno do modelo IFC, ou diz exatamente o que faltou."""
    if modelo is None:
        return Resolucao(diagnostico=["Modelo IFC não carregado."])

    diag = logeoref.avaliar(modelo, alvo=NIVEL_EXIGIDO)
    info = leitor_crs.ler(modelo)
    sites = _sites(modelo)

    detalhe: dict = {
        "arquivo": nome_arquivo,
        "schema": (getattr(modelo, "schema", "") or ""),
        "logeoref": diag.to_dict(),
        "epsg": info.epsg,
        "crs_mensagem": info.mensagem,
        "crs_aviso": info.aviso,
        "escala_comprimento": _escala_projeto(modelo),
        "sites": [_resumo_site(s) for s in sites],
    }

    if not sites:
        return Resolucao(diagnostico=[
            "O modelo não possui **IfcSite** — não há terreno declarado.",
            REQUISITO_DE_INFORMACAO], detalhe=detalhe)

    com_geometria = [s for s in sites if _representacoes(s)]
    detalhe["sites_com_geometria"] = len(com_geometria)
    diagnostico: list[str] = []

    site_geo, aviso_site, recusa = _escolher_site(com_geometria)
    if recusa:
        return Resolucao(diagnostico=[recusa], detalhe=detalhe)
    if aviso_site:
        diagnostico.append(aviso_site)

    terrenos = _terrenos_geograficos(modelo)
    detalhe["terrain_candidatos"] = [
        {"global_id": getattr(t, "GlobalId", None),
         "nome": getattr(t, "Name", None),
         "descricao": getattr(t, "Description", None),
         "contido_em": _onde_esta_contido(modelo, t)} for t in terrenos]

    tem_geometria = bool(site_geo) or bool(terrenos)

    pode_transformar, aviso_crs, impedimento = transformacao_utilizavel(diag, info)
    detalhe["transformacao_utilizavel"] = pode_transformar
    if impedimento:
        detalhe["transformacao_impedimento"] = impedimento

    # 1 e 2) Poligonal — do IfcSite (o limite) ou do TERRAIN (a superfície).
    if tem_geometria and pode_transformar:
        extras_crs = [aviso_crs] if aviso_crs else []

        if site_geo is not None:
            res = _terreno_por_poligonal(modelo, site_geo, info, detalhe,
                                         fonte="IfcSite", avisos_extra=extras_crs)
            if res is not None:
                res.diagnostico = diagnostico
                return res
            diagnostico.append(
                "O IfcSite tem representação geométrica, mas não foi possível "
                "extrair dela um contorno de área utilizável "
                f"({detalhe.get('geometria_erro', 'motivo não identificado')}).")

        if terrenos:
            res = _terreno_por_geografico(modelo, terrenos, info, detalhe,
                                          avisos_crs=extras_crs)
            if res is not None:
                res.diagnostico = diagnostico + list(res.diagnostico)
                return res
            diagnostico.append(
                "Há IfcGeographicElement do tipo TERRAIN, mas não foi possível "
                "extrair dele um contorno de área utilizável "
                f"({detalhe.get('geometria_erro', 'motivo não identificado')}).")

    elif tem_geometria:
        onde = "IfcSite" if site_geo is not None else "IfcGeographicElement TERRAIN"
        diagnostico.append(
            f"O modelo tem geometria de terreno ({onde}), mas {impedimento} — "
            "a geometria existe no modelo e **não pode ser levada ao território**.")

    # 2) Ponto pela coordenada do IfcSite
    coord = ancora.coordenadas_do_site(modelo)
    if coord is not None:
        lat, lon = coord
        t = trn.de_ponto_wgs84(
            lat, lon, origem=trn.ORIGEM_IFC, precisao=trn.PRECISAO_DECLARADA,
            procedencia={"entrada": "RefLatitude/RefLongitude do IfcSite",
                         "logeoref": diag.nivel, "arquivo": nome_arquivo})
        t.avisos.append("Terreno derivado da **coordenada declarada no "
                        "IfcSite**, não de uma poligonal: é o centro informado "
                        "pelo projetista, não o centróide medido do lote.")
        divergencia = _divergencia_de_posicao(coord, info, pode_transformar)
        if divergencia is not None:
            t.procedencia["divergencia_posicao"] = divergencia
            detalhe["divergencia_posicao"] = divergencia
            t.avisos.append(_aviso_de_divergencia(divergencia))
        t.avisos.extend(diagnostico)
        _cross_checks(modelo, com_geometria[0] if com_geometria else sites[0], t, detalhe)
        return Resolucao(terreno=t, diagnostico=diagnostico, detalhe=detalhe)

    # 3) Ponto pela origem do MapConversion (último recurso)
    if pode_transformar:
        mc = info.map_conversion
        e0, n0 = mc.get("eastings"), mc.get("northings")
        if e0 is not None and n0 is not None:
            try:
                lon, lat = crs.reprojetar_ponto(float(e0), float(n0), info.epsg,
                                                crs.CRS_GEOGRAFICO)
            except Exception as exc:
                diagnostico.append(f"Falha ao reprojetar a origem do modelo ({exc!r}).")
            else:
                t = trn.de_ponto_wgs84(
                    lat, lon, origem=trn.ORIGEM_IFC,
                    precisao=trn.PRECISAO_DECLARADA,
                    procedencia={"entrada": "origem do IfcMapConversion",
                                 "epsg_modelo": info.epsg,
                                 "logeoref": diag.nivel, "arquivo": nome_arquivo})
                t.avisos.append(
                    "Terreno derivado da **origem do MapConversion**: esse é o "
                    "ponto de inserção do modelo, **não o centro do terreno**. "
                    "Confira a posição no mapa antes de confirmar.")
                t.avisos.extend(diagnostico)
                return Resolucao(terreno=t, diagnostico=diagnostico, detalhe=detalhe)

    # 4) Nada derivável
    diagnostico.append(
        "Não há no modelo nem geometria de terreno georreferenciada nem "
        "coordenada no IfcSite.")
    for lacuna in (diag.lacunas or []):
        diagnostico.append(f"Lacuna de georreferenciamento: {lacuna}")
    diagnostico.append(REQUISITO_DE_INFORMACAO)
    return Resolucao(diagnostico=diagnostico, detalhe=detalhe)


# ---------------------------------------------------------------------------
# Divergência entre a coordenada do IfcSite e a origem do IfcMapConversion
# ---------------------------------------------------------------------------

def _divergencia_de_posicao(coord_site: tuple[float, float], info,
                            pode_transformar: bool) -> dict | None:
    """As duas posições do modelo, se distarem acima da tolerância; senão ``None``.

    Decisão e tolerância no ADR-038.

    Só há o que comparar quando o modelo traz um IfcMapConversion que se pode
    reprojetar (o mesmo critério do passo 4 da cascata). Falha ao reprojetar
    não derruba nada: o terreno já foi derivado da coordenada do IfcSite, e a
    verificação é um diagnóstico a mais, que fica de fora com um registro no log.

    A distância é geodésica, porque a divergência típica (a localização do
    projeto que não acompanhou as coordenadas compartilhadas) chega a milhares
    de quilômetros, onde a distância num CRS projetado deixa de ter sentido.
    """
    if not pode_transformar:
        return None
    mc = info.map_conversion or {}
    e0, n0 = mc.get("eastings"), mc.get("northings")
    if e0 is None or n0 is None:
        return None
    lat_site, lon_site = coord_site
    try:
        lon_mc, lat_mc = crs.reprojetar_ponto(float(e0), float(n0), info.epsg,
                                              crs.CRS_GEOGRAFICO)
        distancia = _distancia_geodesica_m(lat_site, lon_site, lat_mc, lon_mc)
    except Exception as exc:  # o diagnóstico é acessório; o terreno já existe
        _log.warning("Divergência de posição não avaliada: %r", exc)
        return None
    if distancia <= TOLERANCIA_DIVERGENCIA_POSICAO_M:
        return None
    return {
        "fonte_usada": "ifcsite",
        "ifcsite": {"lat": round(lat_site, 7), "lon": round(lon_site, 7),
                    "entrada": "RefLatitude/RefLongitude do IfcSite"},
        "mapconversion": {"lat": round(lat_mc, 7), "lon": round(lon_mc, 7),
                          "eastings": float(e0), "northings": float(n0),
                          "epsg": info.epsg,
                          "entrada": "origem do IfcMapConversion"},
        "distancia_m": round(distancia, 1),
        "tolerancia_m": TOLERANCIA_DIVERGENCIA_POSICAO_M,
    }


def _distancia_geodesica_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    from pyproj import Geod

    return Geod(ellps="WGS84").inv(lon1, lat1, lon2, lat2)[2]


def _aviso_de_divergencia(divergencia: dict) -> str:
    """O registro técnico do aviso, para a lista de avisos do terreno.

    A explicação ao usuário e a ação recomendada ficam na tela, que conhece o
    município declarado; aqui vai só o fato, com a precedência aplicada.
    """
    d = divergencia["distancia_m"]
    distancia = (f"{formatar_numero(d / 1000.0, 1)} km" if d >= 1000.0
                 else f"{formatar_numero(d, 0)} m")
    return (f"A origem do **IfcMapConversion** cai a {distancia} da coordenada "
            f"do **IfcSite** (tolerância de "
            f"{formatar_numero(divergencia['tolerancia_m'], 0)} m). O terreno foi "
            "posicionado pela coordenada do IfcSite, pela ordem da leitura, e as "
            "duas posições ficam registradas na procedência.")


# ---------------------------------------------------------------------------
# Poligonal
# ---------------------------------------------------------------------------

def _terreno_por_poligonal(modelo, elemento, info, detalhe: dict, *,
                           fonte: str = "IfcSite", avisos_extra=None,
                           coords_prontas=None, metodo_pronto: str = ""):
    """Monta o Terreno a partir da geometria de ``elemento``; None se não der.

    ``coords_prontas`` permite reaproveitar um contorno já extraído (é o caso da
    escolha entre vários TERRAIN, em que a extração serve também para comparar
    as áreas — extrair duas vezes seria desperdício).
    """
    transformar, proc_transf = transformacao.compor_modelo_para_projetado(
        info.map_conversion)
    detalhe["transformacao"] = proc_transf

    if coords_prontas is not None:
        coords_en, metodo, avisos = coords_prontas, metodo_pronto, []
    else:
        coords_en, metodo, avisos = _contorno_do_elemento(modelo, elemento,
                                                          transformar)
    detalhe["metodo_geometria"] = metodo
    if not coords_en or len(coords_en) < 3:
        detalhe["geometria_erro"] = metodo
        return None

    try:
        t_wgs = crs.transformador(info.epsg, crs.CRS_GEOGRAFICO)
        pares_wgs = [t_wgs.transform(e, n) for e, n in coords_en]
    except Exception as exc:
        detalhe["geometria_erro"] = f"falha ao reprojetar de {info.epsg} ({exc!r})"
        return None

    try:
        t = trn.de_poligonal_wgs84(
            pares_wgs, origem=trn.ORIGEM_IFC, precisao=trn.PRECISAO_LEVANTADA,
            procedencia={"entrada": f"poligonal do {fonte}",
                         "fonte_geometria": fonte,
                         "metodo_geometria": metodo,
                         "epsg_modelo": info.epsg,
                         "transformacao": proc_transf,
                         "elemento_global_id": getattr(elemento, "GlobalId", None),
                         "elemento_nome": getattr(elemento, "Name", None),
                         "arquivo": detalhe.get("arquivo", "")})
    except ValueError as exc:
        detalhe["geometria_erro"] = str(exc)
        return None

    # Área medida NO CRS DO MODELO, para quantificar a distorção introduzida
    # pela decisão de remedir no fuso do centróide. Num quadrado de 1 km
    # do arquivo de teste do bSI a diferença foi de 71 m² em 1.000.000 — 71 ppm,
    # a ordem esperada para troca de projeção. É diagnóstico, não veredito: sem
    # esse número, uma área correta parece suspeita.
    area_crs_modelo = _area_em_planta(coords_en)
    if area_crs_modelo and t.area_m2:
        t.procedencia["area_no_crs_do_modelo_m2"] = round(area_crs_modelo, 2)
        ppm = (t.area_m2 - area_crs_modelo) / area_crs_modelo * 1e6
        t.procedencia["desvio_reprojecao_ppm"] = round(ppm, 1)
        detalhe["area_no_crs_do_modelo_m2"] = round(area_crs_modelo, 2)
        detalhe["desvio_reprojecao_ppm"] = round(ppm, 1)

    t.avisos.extend(avisos)
    t.avisos.extend(list(avisos_extra or []))
    t.avisos.extend(proc_transf.get("avisos") or [])
    if info.aviso:
        t.avisos.append(f"Georreferenciamento: {info.aviso}")
    _cross_checks(modelo, elemento, t, detalhe)
    return Resolucao(terreno=t, detalhe=detalhe)


# ---------------------------------------------------------------------------
# Transformação utilizável (≠ conformidade do CRS)
# ---------------------------------------------------------------------------

def transformacao_utilizavel(diag, info) -> tuple[bool, str, str]:
    """``(pode, aviso, impedimento)`` — dá para levar geometria ao território?

    **Distinção que já custou um bug.** ``diag.atinge_alvo`` responde à
    pergunta do EMP-001: georreferenciamento estruturado **e** em SIRGAS 2000,
    como a norma brasileira exige. Para EXTRAIR o terreno, a pergunta é outra e
    menor: existe uma transformação utilizável?

    Um modelo em Gauss-Krüger (``EPSG:5834``, ``EPSG:31467`` — casos reais do
    acervo) atinge o LoGeoRef 50 e **não** é SIRGAS: a poligonal pode ser
    posicionada sem qualquer perda, porque a reprojeção não depende do datum
    declarado. Reprovar a extração por isso confundia conformidade com
    capacidade — e produzia a mensagem absurda "está no LoGeoRef 50 (exigido
    50)". O veredito sobre o CRS é do EMP-001, na checagem de
    Georreferenciamento; aqui ele é **aviso**.
    """
    if diag.nivel < NIVEL_EXIGIDO:
        return False, "", (
            f"o modelo está no **LoGeoRef {diag.nivel}** (exigido "
            f"{NIVEL_EXIGIDO}): faltam IfcProjectedCRS e/ou IfcMapConversion")
    if not info.map_conversion:
        return False, "", "o IfcMapConversion não pôde ser lido"
    if not info.epsg:
        return False, "", (
            f"o IfcProjectedCRS não declara um código EPSG reconhecível "
            f"(nome lido: {info.nome_crs!r})")

    aviso = ""
    if not diag.crs_consistente:
        aviso = (f"O CRS declarado no modelo ({info.epsg}) **não é SIRGAS 2000** "
                 f"— {diag.consistencia_msg or 'datum diverso do exigido'} A "
                 "geometria foi posicionada normalmente (a reprojeção não depende "
                 "do datum), mas a conformidade do CRS é objeto do **EMP-001**, "
                 "na checagem de Georreferenciamento.")
    return True, aviso, ""


# ---------------------------------------------------------------------------
# IfcSite: escolha entre vários
# ---------------------------------------------------------------------------

COMPOSICAO_COMPLEXA = "COMPLEX"


def _composicao(site) -> str:
    valor = getattr(site, "CompositionType", None)
    return str(valor or "").strip(". ").upper()


def _escolher_site(com_geometria: list):
    """``(site, aviso, recusa)`` entre os IfcSite que têm geometria.

    Vários IfcSite não são necessariamente ambiguidade: a norma prevê
    **decomposição de site** (``.COMPLEX.`` agregando ``.PARTIAL.``), e nesse
    caso a raiz da agregação é o terreno. A recusa fica para o que é ambíguo de
    fato: sites irmãos independentes, cada um um terreno.
    """
    if not com_geometria:
        return None, None, None
    if len(com_geometria) == 1:
        return com_geometria[0], None, None

    complexos = [s for s in com_geometria
                 if _composicao(s) == COMPOSICAO_COMPLEXA]
    if len(complexos) == 1:
        outros = len(com_geometria) - 1
        return complexos[0], (
            f"O modelo decompõe o terreno em {len(com_geometria)} IfcSite; "
            f"considerada a raiz da agregação "
            f"(`{getattr(complexos[0], 'Name', None) or complexos[0].GlobalId}`, "
            f"CompositionType COMPLEX) e ignoradas as {outros} partes."), None

    nomes = ", ".join(f"'{getattr(s, 'Name', None) or s.GlobalId}'"
                      for s in com_geometria)
    return None, None, (
        f"O modelo traz **{len(com_geometria)} IfcSite independentes com "
        f"geometria** ({nomes}), sem decomposição que indique qual é a raiz. "
        "Não é possível decidir qual é o terreno do empreendimento: envie o "
        "modelo do terreno em questão.")


# ---------------------------------------------------------------------------
# IfcGeographicElement TERRAIN: a superfície do terreno
# ---------------------------------------------------------------------------

def _e_terreno(elemento) -> bool:
    """True se o elemento geográfico representa terreno.

    Dois padrões observados em modelos reais: ``PredefinedType = TERRAIN``
    (Revit) e o tipo em texto no ``ObjectType`` com
    ``PredefinedType`` vazio (``Building-Landscaping``, da própria bSI).
    """
    predefinido = getattr(elemento, "PredefinedType", None)
    if predefinido is not None and str(predefinido).strip(". ").upper() == "TERRAIN":
        return True

    texto = (getattr(elemento, "ObjectType", None) or "").lower()
    if "terrain" in texto or "terreno" in texto:
        return True

    try:   # o tipo pode carregar o PredefinedType em vez da ocorrência
        import ifcopenshell.util.element as ue

        tipo = ue.get_type(elemento)
        pt = getattr(tipo, "PredefinedType", None)
        return pt is not None and str(pt).strip(". ").upper() == "TERRAIN"
    except Exception:
        return False


def _terrenos_geograficos(modelo) -> list:
    """IfcGeographicElement de terreno, **onde estiverem contidos**.

    A contenção não filtra: exportadores alocam o terreno no pavimento em vez
    do site (caso real observado). A **classe da entidade** é o que
    importa; o lugar em que foi arquivado vira lacuna registrada.
    """
    try:
        elementos = list(modelo.by_type("IfcGeographicElement"))
    except Exception:
        return []
    return [e for e in elementos if _e_terreno(e) and _representacoes(e)]


def _onde_esta_contido(modelo, elemento) -> str | None:
    """Classe IFC da estrutura espacial que contém o elemento, ou None."""
    try:
        rels = list(modelo.by_type("IfcRelContainedInSpatialStructure"))
    except Exception:
        return None
    for rel in rels:
        relacionados = getattr(rel, "RelatedElements", None) or []
        try:
            pertence = any(r is elemento or
                           getattr(r, "GlobalId", None) == getattr(elemento, "GlobalId", None)
                           for r in relacionados)
        except Exception:
            pertence = False
        if pertence:
            estrutura = getattr(rel, "RelatingStructure", None)
            if estrutura is None:
                return None
            try:
                return estrutura.is_a()
            except Exception:
                return None
    return None


def _area_em_planta(coords_en: list) -> float:
    """Área do contorno em coordenadas projetadas (shoelace, m²)."""
    if not coords_en or len(coords_en) < 3:
        return 0.0
    total = 0.0
    for (x1, y1), (x2, y2) in zip(coords_en, coords_en[1:] + coords_en[:1]):
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def _terreno_por_geografico(modelo, terrenos: list, info, detalhe: dict, *,
                            avisos_crs=None):
    """Terreno a partir do IfcGeographicElement TERRAIN de maior área em planta.

    Vários TERRAIN é modelagem normal, não ambiguidade: num modelo real
    observado há o terreno de implantação e duas escavações. O de maior área em planta é o
    terreno; as escavações são recortes internos. Critério determinístico e sem
    heurística de nome — nome depende de idioma e de convenção de escritório.
    """
    transformar, _ = transformacao.compor_modelo_para_projetado(info.map_conversion)

    medidos = []
    for elemento in terrenos:
        coords, metodo, avisos = _contorno_do_elemento(modelo, elemento, transformar)
        if coords and len(coords) >= 3:
            medidos.append((_area_em_planta(coords), elemento, coords, metodo, avisos))

    if not medidos:
        return None

    medidos.sort(key=lambda m: m[0], reverse=True)
    area, elemento, coords, metodo, avisos = medidos[0]

    extras = list(avisos) + list(avisos_crs or [])
    extras.append(
        "Terreno derivado de **IfcGeographicElement TERRAIN** "
        f"(`{getattr(elemento, 'Name', None) or elemento.GlobalId}`), que a "
        "norma designa para a **superfície** do terreno — não para o limite da "
        "parcela. O contorno é a extensão do relevo modelado e pode exceder o "
        "lote: confira a área. O limite legal deveria vir do FootPrint do "
        "IfcSite.")

    if len(medidos) > 1:
        ignorados = ", ".join(
            f"'{getattr(e, 'Name', None) or e.GlobalId}' "
            f"({formatar_numero(a, 0)} m²)" for a, e, _, _, _ in medidos[1:])
        extras.append(f"Havia {len(medidos)} elementos TERRAIN; considerado o de "
                      f"maior área em planta. Ignorados: {ignorados}.")

    contido = _onde_esta_contido(modelo, elemento)
    detalhe["terrain_escolhido"] = {
        "global_id": getattr(elemento, "GlobalId", None),
        "nome": getattr(elemento, "Name", None),
        "area_planta_m2": round(area, 2),
        "contido_em": contido,
        "candidatos": len(medidos),
    }
    if contido and contido != "IfcSite":
        extras.append(
            f"O terreno está contido em **{contido}**, não no IfcSite. A "
            "estrutura espacial da norma prevê o terreno no site — lacuna de "
            "requisito de informação do modelo (o resultado não muda).")

    return _terreno_por_poligonal(
        modelo, elemento, info, detalhe, fonte="IfcGeographicElement",
        avisos_extra=extras, coords_prontas=coords, metodo_pronto=metodo)


def _contorno_do_elemento(modelo, elemento, transformar):
    """(coords_en, metodo, avisos) — FootPrint primeiro, Body com aviso.

    Serve ao IfcSite e ao IfcGeographicElement: os dois carregam representação
    do mesmo jeito, e é o chamador que sabe o significado do que extraiu.
    """
    reps = _representacoes(elemento)
    fp = [r for r in reps if (r.get("identificador") or "").lower() == "footprint"]

    if fp:
        pontos, detalhe_fp = _pontos_de_curva(modelo, elemento, fp[0])
        if pontos:
            return ([transformar(x, y) for x, y in pontos],
                    f"FootPrint ({detalhe_fp})", [])

    # Body (ou FootPrint com curva não suportada): projeção XY da malha.
    pontos, erro = _footprint_por_malha(modelo, elemento)
    if pontos:
        aviso = ("Poligonal obtida pela **projeção da geometria 3D** (sem "
                 "FootPrint explícito). Se essa geometria é a superfície do "
                 "terreno, o contorno pode ser a extensão do relevo, e não o "
                 "limite do lote — confira a área.")
        return ([transformar(x, y) for x, y in pontos],
                "projeção XY da malha", [aviso])

    return [], erro or "representação não interpretável", []


def _pontos_de_curva(modelo, site, rep: dict):
    """Pontos (x, y) de uma curva de FootPrint, na unidade do projeto -> metros.

    Cobre os dois casos que os exportadores de fato produzem: ``IfcPolyline`` e
    ``IfcIndexedPolyCurve``. Outros tipos caem no caminho da malha, com aviso —
    o CLI imprime a classe encontrada, então a lista cresce com evidência, não
    com suposição.
    """
    escala = _escala_projeto(modelo) or 1.0
    matriz = _matriz_placement(site)

    brutos: list[tuple[float, float]] = []
    classe = ""
    for item in rep.get("itens_obj") or []:
        for curva in _curvas(item):
            classe = curva.is_a()
            if classe == "IfcPolyline":
                for pt in (getattr(curva, "Points", None) or []):
                    c = getattr(pt, "Coordinates", None)
                    if c and len(c) >= 2:
                        brutos.append((float(c[0]), float(c[1])))
            elif classe == "IfcIndexedPolyCurve":
                lista = getattr(curva, "Points", None)
                coords = getattr(lista, "CoordList", None) or []
                for c in coords:
                    if c and len(c) >= 2:
                        brutos.append((float(c[0]), float(c[1])))
            if brutos:
                break
        if brutos:
            break

    if not brutos:
        return [], ""

    saida = []
    for x, y in brutos:
        if matriz is not None:
            x, y = (matriz[0][0] * x + matriz[0][1] * y + matriz[0][3],
                    matriz[1][0] * x + matriz[1][1] * y + matriz[1][3])
        saida.append((x * escala, y * escala))
    return saida, f"{classe}, {len(saida)} vértices"


def _curvas(item) -> list:
    """Curvas de um item de representação (direto ou dentro de um CurveSet)."""
    try:
        if item.is_a("IfcGeometricCurveSet") or item.is_a("IfcGeometricSet"):
            return list(getattr(item, "Elements", None) or [])
        return [item]
    except Exception:
        return []


def _footprint_por_malha(modelo, site):
    """Contorno pela união dos triângulos projetados em XY (metros SI)."""
    try:
        from ifcopenshell import geom
    except Exception as exc:
        return [], f"geometria indisponível ({exc!r})"

    ajustes, modo = _settings_world()
    try:
        shape = geom.create_shape(ajustes, site)
    except Exception as exc:
        return [], f"falha em create_shape ({type(exc).__name__}: {exc})"

    g = shape.geometry
    verts = list(g.verts)
    faces = list(g.faces)
    if not verts or not faces:
        return [], "IfcSite sem malha utilizável"

    if not modo:   # sem world-coords: aplica a matriz do próprio shape
        verts = _aplicar_matriz_shape(shape, verts)

    try:
        from shapely.geometry import Polygon
        from shapely.ops import unary_union

        triangulos = []
        for i in range(0, len(faces), 3):
            tri = []
            for j in faces[i:i + 3]:
                tri.append((verts[3 * j], verts[3 * j + 1]))
            poligono = Polygon(tri)
            if poligono.is_valid and poligono.area > 0:
                triangulos.append(poligono)
        if not triangulos:
            return [], "malha do IfcSite sem faces com área em planta"
        uniao = unary_union(triangulos).buffer(0)
        if uniao.geom_type == "MultiPolygon":
            uniao = max(uniao.geoms, key=lambda p: p.area)
        return [(x, y) for x, y in uniao.exterior.coords], ""
    except Exception as exc:
        return [], f"falha ao unir a malha ({type(exc).__name__}: {exc})"


def _settings_world():
    """Settings do create_shape com coordenadas de mundo, se a API permitir."""
    from ifcopenshell import geom

    ajustes = geom.settings()
    for chave in ("use-world-coords", "USE_WORLD_COORDS"):
        try:
            if chave.islower():
                ajustes.set(chave, True)
            else:
                ajustes.set(getattr(ajustes, chave), True)
            return ajustes, chave
        except Exception:
            _log.debug("settings do create_shape: %s não suportado nesta API", chave, exc_info=True)
            continue
    return ajustes, ""


def _aplicar_matriz_shape(shape, verts: list) -> list:
    """Aplica a matriz de posicionamento do shape aos vértices locais."""
    try:
        m = list(getattr(shape.transformation, "matrix", None) or [])
        if hasattr(m, "data"):
            m = list(m.data)
        if len(m) < 12:
            return verts
        saida = []
        for i in range(0, len(verts), 3):
            x, y, z = verts[i], verts[i + 1], verts[i + 2]
            saida.extend([
                m[0] * x + m[3] * y + m[6] * z + m[9],
                m[1] * x + m[4] * y + m[7] * z + m[10],
                m[2] * x + m[5] * y + m[8] * z + m[11]])
        return saida
    except Exception:
        return verts


# ---------------------------------------------------------------------------
# Cross-checks e leitura de metadados
# ---------------------------------------------------------------------------

PSET_REGISTRO = "Pset_LandRegistration"


def _matricula(site) -> tuple[str, str]:
    """``(matrícula, fonte)`` do lote — property set primeiro, atributo depois.

    **Por que a precedência é esta.** O IFC4.3 marca
    ``IfcSite.LandTitleNumber`` como **depreciado** — *"shall not be used for
    export"* —, indicando ``Pset_LandRegistration`` no lugar. Um modelo IFC4.3
    conforme simplesmente **não preenche** o atributo, e ler só ele faria a
    matrícula sumir justamente nos modelos mais novos. Com a premissa do IFC4
    cravada, isso deixou de ser hipótese distante.

    **Por que o atributo continua, como segunda opção.** É o que exportadores
    IFC2X3 e IFC4 de fato preenchem hoje; removê-lo trocaria uma lacuna futura
    por uma lacuna presente.

    O nome da propriedade **não foi suposto**: ``Pset_LandRegistration`` traz
    ``LandID``, ``IsPermanentID`` e ``LandTitleID``, conferidos nos templates de
    schema do próprio IfcOpenShell (0.8.5), idênticos em IFC4, IFC4X3 e
    IFC4X3_ADD2. A matrícula é o ``LandTitleID``; o ``LandID`` identifica o lote
    e é lido à parte, em :func:`_identificacao_do_lote`.
    """
    from core.infra.ifc import leitor_modelo as leitor_ifc

    valor, fonte = leitor_ifc.propriedade_de_pset(site, PSET_REGISTRO, "LandTitleID")
    if valor:
        return str(valor), fonte
    atributo = getattr(site, "LandTitleNumber", None)
    if atributo:
        return str(atributo), "IfcSite.LandTitleNumber (depreciado no IFC4.3)"
    return "", ""


def _identificacao_do_lote(site) -> tuple[str, str]:
    """``(LandID, fonte)`` — o identificador do lote, que **não** é a matrícula.

    São coisas distintas no mesmo pset e vale não fundi-las: o ``LandTitleID`` é
    o título (a matrícula do registro de imóveis), o ``LandID`` identifica a
    parcela de terra. Sem equivalente entre os atributos do IfcSite, então aqui
    não há fallback — ou vem do pset, ou não existe.
    """
    from core.infra.ifc import leitor_modelo as leitor_ifc

    valor, fonte = leitor_ifc.propriedade_de_pset(site, PSET_REGISTRO, "LandID")
    return (str(valor), fonte) if valor else ("", "")


def _cross_checks(modelo, site, terreno, detalhe: dict) -> None:
    """Confrontos de diagnóstico — nunca alteram veredito, só informam."""
    matricula, fonte = _matricula(site)
    if matricula:
        # A chave do `detalhe` deixou de se chamar `land_title_number`: o valor
        # pode não vir mais daquele atributo, e um nome que mente sobre a origem
        # é o defeito que a própria refatoração veio corrigir.
        detalhe["matricula"] = matricula
        detalhe["matricula_fonte"] = fonte
        terreno.procedencia["matricula_ifc"] = matricula
        terreno.procedencia["matricula_fonte"] = fonte

    lote, fonte_lote = _identificacao_do_lote(site)
    if lote:
        detalhe["land_id"] = lote
        detalhe["land_id_fonte"] = fonte_lote
        terreno.procedencia["land_id_ifc"] = lote

    area_pset = _area_do_pset(site)
    if area_pset:
        detalhe["area_pset_m2"] = area_pset
        terreno.procedencia["area_pset_m2"] = area_pset
        if terreno.area_m2:
            desvio = abs(terreno.area_m2 - area_pset) / area_pset
            detalhe["desvio_area"] = desvio
            if desvio > TOLERANCIA_AREA:
                terreno.avisos.append(
                    f"Área medida da poligonal "
                    f"({formatar_numero(terreno.area_m2, 0)} m²) divergente da "
                    f"declarada em Pset_SiteCommon.TotalArea "
                    f"({formatar_numero(area_pset, 0)} m²) — "
                    f"{desvio*100:.0f}% de diferença.")


def _area_do_pset(site) -> float | None:
    try:
        from core.infra.ifc import leitor_modelo as leitor_ifc
        props = leitor_ifc.propriedades_do_elemento(site)
    except Exception:
        return None
    for chave in ("TotalArea", "GrossArea", "GrossPlannedArea"):
        valor = props.get(chave)
        if isinstance(valor, (int, float)) and valor > 0:
            return float(valor)
    return None


def _sites(modelo) -> list:
    try:
        return list(modelo.by_type("IfcSite"))
    except Exception:
        return []


def _representacoes(site) -> list[dict]:
    """Representações do site, com identificador, tipo e classes dos itens."""
    saida: list[dict] = []
    try:
        rep = getattr(site, "Representation", None)
        for r in (getattr(rep, "Representations", None) or []):
            itens = list(getattr(r, "Items", None) or [])
            saida.append({
                "identificador": getattr(r, "RepresentationIdentifier", None),
                "tipo": getattr(r, "RepresentationType", None),
                "itens": [i.is_a() for i in itens],
                "itens_obj": itens,
            })
    except Exception:
        return []
    return saida


def _resumo_site(site) -> dict:
    reps = _representacoes(site)
    matricula, fonte = _matricula(site)
    return {
        "global_id": getattr(site, "GlobalId", None),
        "nome": getattr(site, "Name", None),
        # Mesma resolução do `_cross_checks`, e de propósito: o resumo por site
        # e o diagnóstico consolidado divergirem seria defeito difícil de ver.
        "matricula": matricula,
        "matricula_fonte": fonte,
        "tem_lat_lon": bool(getattr(site, "RefLatitude", None)
                            and getattr(site, "RefLongitude", None)),
        "representacoes": [{k: v for k, v in r.items() if k != "itens_obj"}
                           for r in reps],
    }


def _escala_projeto(modelo) -> float | None:
    try:
        from core.infra.ifc import unidades
        return unidades.escala_comprimento(modelo)
    except Exception:
        return None


def _matriz_placement(site):
    try:
        import ifcopenshell.util.placement as pl
        return pl.get_local_placement(site.ObjectPlacement)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# CLI de diagnóstico — como se valida esta cascata contra um IFC real
# ---------------------------------------------------------------------------

def _cli() -> None:
    import argparse
    import json

    p = argparse.ArgumentParser(
        description="Diagnostica a extração do terreno de um modelo IFC.")
    p.add_argument("ifc", help="Caminho do arquivo IFC.")
    p.add_argument("--json", action="store_true",
                   help="Imprime o detalhe completo em JSON.")
    args = p.parse_args()

    res = resolver_arquivo(args.ifc)
    d = res.detalhe
    if d.get("abertura_falhou"):
        print("=" * 72)
        print(f"ARQUIVO   : {args.ifc}")
        print(f"SCHEMA    : {d.get('schema') or '?'}  ->  NÃO FOI POSSÍVEL ABRIR")
        for m in res.diagnostico:
            print(f"  · {m}")
        return
    lg = d.get("logeoref", {})

    print("=" * 72)
    print(f"ARQUIVO   : {args.ifc}")
    print(f"SCHEMA    : {d.get('schema')}")
    print(f"LoGeoRef  : nível {lg.get('nivel')} (alvo {lg.get('alvo')}) — "
          f"conforme p/ EMP-001 (nível + SIRGAS 2000): "
          f"{bool(lg.get('nivel', 0) >= lg.get('alvo', 50) and lg.get('crs_consistente'))}")
    print(f"TRANSFORM.: utilizável para extrair o terreno: "
          f"{d.get('transformacao_utilizavel')}"
          + (f" — impedimento: {d['transformacao_impedimento']}"
             if d.get("transformacao_impedimento") else ""))
    print(f"CRS       : {d.get('epsg')} | consistente: {lg.get('crs_consistente')}"
          f" | {d.get('crs_mensagem')}")
    if d.get("crs_aviso"):
        print(f"  aviso CRS: {d['crs_aviso']}")
    print(f"UNIDADE   : escala de comprimento do projeto = {d.get('escala_comprimento')}")

    print(f"\nIfcSite encontrados: {len(d.get('sites') or [])} "
          f"(com geometria: {d.get('sites_com_geometria', 0)})")
    for s in d.get("sites") or []:
        print(f"  - {s.get('global_id')} nome={s.get('nome')!r} "
              f"lat/lon={s.get('tem_lat_lon')} matrícula={s.get('matricula')!r}"
              + (f" (de {s['matricula_fonte']})" if s.get("matricula_fonte") else ""))
        for r in s.get("representacoes") or []:
            print(f"      repr id={r.get('identificador')!r} "
                  f"tipo={r.get('tipo')!r} itens={r.get('itens')}")

    terrenos = d.get("terrain_candidatos") or []
    print(f"\nIfcGeographicElement (terreno): {len(terrenos)}")
    for t in terrenos:
        print(f"  - {t.get('global_id')} nome={t.get('nome')!r} "
              f"contido em {t.get('contido_em')} desc={t.get('descricao')!r}")
    if d.get("terrain_escolhido"):
        e = d["terrain_escolhido"]
        print(f"  ESCOLHIDO: {e.get('nome')!r} — área em planta "
              f"{formatar_numero(e.get('area_planta_m2'))} m² (entre "
              f"{e.get('candidatos')} candidato(s)), contido em "
              f"{e.get('contido_em')}")

    if d.get("transformacao"):
        t = d["transformacao"]
        print("\nTRANSFORMAÇÃO modelo -> projetado")
        print(f"  offsets: E={t.get('eastings')} N={t.get('northings')} | "
              f"rotação: {t.get('rotacao_graus'):.4f}° | escala: {t.get('escala')}")
        for a in t.get("avisos") or []:
            print(f"  aviso: {a}")
    if d.get("metodo_geometria"):
        print(f"  método da geometria: {d['metodo_geometria']}")
    if d.get("geometria_erro"):
        print(f"  ERRO na geometria: {d['geometria_erro']}")

    print("\n" + "-" * 72)
    if res.ok:
        t = res.terreno
        print("TERRENO DERIVADO")
        print(f"  {t.resumo()}")
        print(f"  nível={t.nivel} precisão={t.precisao} origem={t.origem}")
        if t.area_m2:
            print(f"  área={formatar_numero(t.area_m2)} m²  "
                  f"perímetro={formatar_numero(t.perimetro_m)} m")
            if d.get("area_no_crs_do_modelo_m2"):
                print(f"  área no CRS do modelo ({d.get('epsg')}): "
                      f"{formatar_numero(d['area_no_crs_do_modelo_m2'])} m² "
                      f"— desvio de reprojeção "
                      f"{d.get('desvio_reprojecao_ppm', 0):+.1f} ppm")
        if d.get("area_pset_m2"):
            print(f"  área declarada no Pset: "
                  f"{formatar_numero(d['area_pset_m2'])} m² "
                  f"(desvio {d.get('desvio_area', 0)*100:.1f}%)")
        for a in t.avisos:
            print(f"  AVISO: {a}")
    else:
        print("TERRENO NÃO DERIVÁVEL")
        for m in res.diagnostico:
            print(f"  · {m}")

    if args.json:
        limpo = {k: v for k, v in d.items() if k != "sites"}
        print("\nDETALHE (JSON)")
        print(json.dumps(limpo, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    _cli()
