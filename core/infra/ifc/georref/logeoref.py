"""Avaliador do Nivel de Georreferenciamento (LoGeoRef) de um modelo IFC.

Escala de Clemen e Görne (2019): metrica da "profundidade" do
georreferenciamento de um modelo BIM, medida com entidades do IFC padrao.

    10 - endereco postal (IfcPostalAddress)
    20 - coordenadas geograficas em IfcSite (RefLatitude/RefLongitude/RefElevation)
    30 - placement 3+1 do IfcSite (IfcLocalPlacement + true north)
    40 - WorldCoordinateSystem + TrueNorth no IfcGeometricRepresentationContext
    50 - IfcProjectedCRS + IfcMapConversion (introduzidos no IFC4; codigo EPSG)
    60 - pontos de controle comuns (nao implementavel no IFC) -> fora de escopo

IMPORTANTE: as entidades do nivel 50 existem apenas no IFC4+. Em schemas
anteriores (ex.: IFC2X3) o nivel 50 e inalcancavel por limitacao do proprio
schema; o avaliador detecta isso e relata como lacuna especifica.

Este modulo apenas detecta o nivel e relata lacunas; o veredito (EMP-001 exige
o nivel 50) cabe a regra que o consome.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.dominio.conhecimento.georreferenciamento import LOGEOREF_ALVO

ALVO_PADRAO = LOGEOREF_ALVO

ROTULOS = {
    10: "Endereco postal (IfcPostalAddress)",
    20: "Coordenadas geograficas no IfcSite (RefLatitude/RefLongitude)",
    30: "Posicionamento do IfcSite (IfcLocalPlacement + true north)",
    40: "WorldCoordinateSystem + TrueNorth no contexto do IfcProject",
    50: "CRS projetado (IfcProjectedCRS + IfcMapConversion)",
}


@dataclass
class DiagnosticoLoGeoRef:
    nivel: int = 0
    alvo: int = ALVO_PADRAO
    schema: str = ""
    degraus: dict[int, dict] = field(default_factory=dict)
    lacunas: list[str] = field(default_factory=list)
    crs_epsg: str | None = None
    crs_consistente: bool = False
    consistencia_msg: str = ""
    elementos: list[str] = field(default_factory=list)

    @property
    def atinge_alvo(self) -> bool:
        return self.nivel >= self.alvo and self.crs_consistente

    def to_dict(self) -> dict:
        return {
            "tipo": "logeoref",
            "nivel": self.nivel,
            "alvo": self.alvo,
            "schema": self.schema,
            "crs_epsg": self.crs_epsg,
            "crs_consistente": self.crs_consistente,
            "consistencia_msg": self.consistencia_msg,
            "degraus": [{"nivel": n, **self.degraus[n]} for n in sorted(self.degraus)],
            "lacunas": self.lacunas,
        }


def _by_type(modelo: Any, tipo: str) -> list:
    try:
        return list(modelo.by_type(tipo))
    except Exception:
        return []


def _nivel_10(modelo):
    p = bool(_by_type(modelo, "IfcPostalAddress"))
    return p, ([] if p else ["IfcPostalAddress"])


def _nivel_20(modelo):
    for site in _by_type(modelo, "IfcSite"):
        if getattr(site, "RefLatitude", None) is not None and \
           getattr(site, "RefLongitude", None) is not None:
            return True, []
    return False, ["IfcSite.RefLatitude/RefLongitude"]


def _nivel_30(modelo):
    for site in _by_type(modelo, "IfcSite"):
        col = getattr(site, "ObjectPlacement", None)
        if col is not None and col.is_a("IfcLocalPlacement"):
            return True, []
    return False, ["IfcSite.ObjectPlacement (IfcLocalPlacement)"]


def _nivel_40(modelo):
    for ctx in _by_type(modelo, "IfcGeometricRepresentationContext"):
        if ctx.is_a() != "IfcGeometricRepresentationContext":
            continue
        if getattr(ctx, "WorldCoordinateSystem", None) is not None and \
           getattr(ctx, "TrueNorth", None) is not None:
            return True, []
    return False, ["IfcGeometricRepresentationContext.WorldCoordinateSystem + TrueNorth"]


def _nivel_50(modelo, suporta: bool):
    if not suporta:
        return False, ["IfcProjectedCRS/IfcMapConversion (requer IFC4+; o schema atual nao comporta)"], None
    crs = _by_type(modelo, "IfcProjectedCRS")
    conv = _by_type(modelo, "IfcMapConversion")
    faltantes = []
    if not crs:
        faltantes.append("IfcProjectedCRS")
    if not conv:
        faltantes.append("IfcMapConversion")
    epsg = None
    if crs:
        nome = getattr(crs[0], "Name", None)
        epsg = str(nome) if nome else None
    return (len(faltantes) == 0), faltantes, epsg


def _consistencia_crs(epsg: str | None, modelo) -> tuple[bool, str]:
    if not epsg:
        return False, "IfcProjectedCRS sem codigo de CRS (atributo Name vazio)."
    try:
        from pyproj import CRS
        crs = CRS.from_user_input(epsg)
    except Exception:
        return False, f"Codigo de CRS nao reconhecido pelo pyproj: '{epsg}'."

    nome_crs = (crs.name or "").upper()
    metodo = (crs.coordinate_operation.method_name if crs.coordinate_operation else "") or ""
    eh_sirgas = "SIRGAS 2000" in nome_crs
    eh_utm = "UTM" in nome_crs or "TRANSVERSE MERCATOR" in metodo.upper()
    if not eh_sirgas:
        return False, f"CRS '{epsg}' ({crs.name}) nao e SIRGAS 2000."
    if not eh_utm:
        return False, f"CRS '{epsg}' ({crs.name}) nao e uma projecao UTM."

    conv = _by_type(modelo, "IfcMapConversion")
    nota_escala = ""
    if conv:
        c = conv[0]
        if getattr(c, "Eastings", None) in (None, 0) and getattr(c, "Northings", None) in (None, 0):
            return False, "MapConversion com Eastings/Northings nulos."
        plausivel, nota_escala = _escala_plausivel(getattr(c, "Scale", None), modelo)
        if not plausivel:
            return False, nota_escala
    return True, f"CRS consistente: {epsg} (SIRGAS 2000 / UTM).{nota_escala}"


def _escala_plausivel(escala, modelo) -> tuple[bool, str]:
    """``IfcMapConversion.Scale`` plausível é 1, ou o fator da unidade de
    comprimento do projeto (``k`` metros por unidade) em qualquer das duas
    direções, ``k`` e ``1/k``.

    Aceitar só [0,9; 1,1] reprovaria qualquer projeto em pé: o Revit, com unidade de projeto em FOOT, grava ``Scale = 3,2808``
    (= 1/0,3048) com Eastings/Northings em metros — é a convenção INVERSA da
    definição do IFC4 ("escala a aplicar às coordenadas locais para obter as
    do mapa", que daria 0,3048), mas o valor é coerente com a unidade e não é
    erro de georreferenciamento (cenário V2 do estudo de caso). O motor não
    usa ``Scale`` para reprojetar (os offsets são validados pela área de uso
    do CRS em ``leitor_crs``), então a direção só se anota. Projeto em metro
    (``k = 1``) continua exigindo ``Scale ≈ 1``.
    """
    if escala is None:
        return True, ""
    try:
        valor = float(escala)
    except (TypeError, ValueError):
        return False, f"MapConversion com escala nao numerica ({escala!r})."
    from core.infra.ifc import unidades

    k = unidades.escala_comprimento(modelo)
    candidatas = {"1": 1.0}
    if k and abs(k - 1.0) > 1e-9:
        candidatas["k (unidade do projeto -> metro)"] = k
        candidatas["1/k (convencao inversa do exportador)"] = 1.0 / k
    for rotulo, alvo in candidatas.items():
        if abs(valor - alvo) <= 0.01 * alvo:
            nota = ("" if rotulo == "1" else
                    f" Scale = {valor:.6g} corresponde a {rotulo}, com k = {k:.6g};"
                    " a unidade de comprimento do projeto nao e o metro.")
            return True, nota
    return False, (f"MapConversion com escala implausivel ({escala}): nao e 1 nem "
                   f"o fator da unidade de comprimento do projeto ({k:.6g}) em "
                   "nenhuma direcao.")


def avaliar(modelo: Any, alvo: int = ALVO_PADRAO) -> DiagnosticoLoGeoRef:
    diag = DiagnosticoLoGeoRef(alvo=alvo)
    if modelo is None:
        diag.consistencia_msg = "Modelo IFC nao carregado."
        return diag

    schema = (getattr(modelo, "schema", "") or "").upper()
    diag.schema = schema
    suporta_50 = (schema == "") or schema.startswith("IFC4")

    p10, f10 = _nivel_10(modelo)
    p20, f20 = _nivel_20(modelo)
    p30, f30 = _nivel_30(modelo)
    p40, f40 = _nivel_40(modelo)
    p50, f50, epsg = _nivel_50(modelo, suporta_50)

    presencas = {10: (p10, f10), 20: (p20, f20), 30: (p30, f30), 40: (p40, f40), 50: (p50, f50)}
    for n, (presente, faltantes) in presencas.items():
        diag.degraus[n] = {"presente": presente, "rotulo": ROTULOS[n], "faltantes": faltantes}

    niveis_presentes = [n for n, (presente, _) in presencas.items() if presente]
    diag.nivel = max(niveis_presentes) if niveis_presentes else 0

    diag.crs_epsg = epsg
    if p50:
        diag.crs_consistente, diag.consistencia_msg = _consistencia_crs(epsg, modelo)

    for n in sorted(presencas):
        if n <= alvo and not presencas[n][0]:
            diag.lacunas.extend(presencas[n][1])
    if p50 and not diag.crs_consistente:
        diag.lacunas.append(f"Consistencia do CRS: {diag.consistencia_msg}")

    for tipo in ("IfcSite", "IfcProject"):
        for e in _by_type(modelo, tipo):
            gid = getattr(e, "GlobalId", None)
            if gid:
                diag.elementos.append(gid)
    return diag
