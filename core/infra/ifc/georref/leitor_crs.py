"""Leitura das entidades de georreferenciamento do IFC.

Lê IfcProjectedCRS e IfcMapConversion (introduzidas no IFC4). Em schemas
anteriores (ex.: IFC2X3) essas entidades não existem; nesse caso a leitura
retorna valido=False com mensagem, sem levantar erro.

UNIDADE (ponto sensível). Conforme a norma IFC, Eastings/Northings/Height do
IfcMapConversion são interpretados na unidade do IfcProjectedCRS.MapUnit; se
ausente, na unidade de comprimento do projeto. Vários exportadores (ex.: Revit)
são inconsistentes — chegam a declarar MapUnit=METRE com valores em milímetros.
Para resolver isso de forma objetiva, usa-se a **área de uso oficial do CRS**
(registro EPSG, via pyproj): testam-se as interpretações de unidade plausíveis e
escolhe-se a que posiciona o modelo dentro da extensão válida do CRS,
sinalizando quando o dado declarado era inconsistente.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class InfoGeorref:
    valido: bool = False
    epsg: str | None = None
    nome_crs: str | None = None
    map_conversion: dict[str, Any] | None = None   # offsets já convertidos para metros
    unidade_para_m: float = 1.0                     # fator efetivamente aplicado
    dentro_area_uso: bool | None = None             # None = não verificável
    aviso: str = ""                                 # inconsistências detectadas
    mensagem: str = ""


def ler(modelo: Any) -> InfoGeorref:
    if modelo is None:
        return InfoGeorref(mensagem="modelo IFC nao carregado")

    schema = (getattr(modelo, "schema", "") or "").upper()
    if schema and not schema.startswith("IFC4"):
        return InfoGeorref(mensagem=f"schema {schema} nao comporta CRS projetado (requer IFC4+)")

    try:
        crs_list = list(modelo.by_type("IfcProjectedCRS"))
        conv_list = list(modelo.by_type("IfcMapConversion"))
    except Exception as exc:
        return InfoGeorref(mensagem=f"entidades de CRS indisponiveis no schema: {exc!r}")

    if not crs_list:
        return InfoGeorref(mensagem="IfcProjectedCRS ausente")
    if not conv_list:
        return InfoGeorref(mensagem="IfcMapConversion ausente")

    crs, conv = crs_list[0], conv_list[0]
    nome = getattr(crs, "Name", None)
    epsg = nome if (nome and str(nome).upper().startswith("EPSG:")) else None

    mc, escala, dentro, aviso = _resolver_offsets(modelo, crs, conv, epsg)
    return InfoGeorref(valido=True, epsg=epsg, nome_crs=str(nome) if nome else None,
                       map_conversion=mc, unidade_para_m=escala,
                       dentro_area_uso=dentro, aviso=aviso, mensagem="ok")


# ---------------------------------------------------------------------------
# Resolução de unidade dos offsets, validada pela área de uso do CRS
# ---------------------------------------------------------------------------

def _resolver_offsets(modelo, crs, conv, epsg):
    raw_e = getattr(conv, "Eastings", None)
    raw_n = getattr(conv, "Northings", None)
    raw_h = getattr(conv, "OrthogonalHeight", None)

    escala_mapunit = _escala_mapunit(crs)        # None se ausente/não SI-metro
    escala_projeto = _escala_projeto(modelo)     # None se indisponível (fakes/sem unidade)
    declarada = escala_mapunit if escala_mapunit is not None else \
        (escala_projeto if escala_projeto is not None else 1.0)

    candidatas: list[float] = []
    for s in (declarada, escala_projeto, 1.0):
        if s is not None and all(abs(s - c) > 1e-15 for c in candidatas):
            candidatas.append(s)

    escolhida, dentro, aviso = declarada, None, ""
    area = _area_uso(epsg) if epsg else None
    if area and isinstance(raw_e, (int, float)) and isinstance(raw_n, (int, float)):
        achou = None
        for s in candidatas:
            lon, lat = _reproj(epsg, float(raw_e) * s, float(raw_n) * s)
            if lon is None:
                continue
            if area[0] <= lon <= area[2] and area[1] <= lat <= area[3]:
                achou = s
                break
        if achou is not None:
            escolhida, dentro = achou, True
            if abs(achou - declarada) > 1e-15:
                aviso = ("Unidade do MapConversion inconsistente com os valores: a "
                         f"interpretação declarada cairia fora da área de uso do CRS; "
                         f"reinterpretado pela escala {achou:g} (validado pela área de uso do CRS).")
        else:
            dentro = False
            aviso = ("Coordenadas fora da área de uso do CRS em todas as interpretações "
                     "de unidade testadas; georreferenciamento suspeito.")

    def m(v):
        return float(v) * escolhida if isinstance(v, (int, float)) else None

    mc = {
        "eastings": m(raw_e), "northings": m(raw_n), "orthogonal_height": m(raw_h),
        "x_axis_abscissa": getattr(conv, "XAxisAbscissa", None),
        "x_axis_ordinate": getattr(conv, "XAxisOrdinate", None),
        "scale": getattr(conv, "Scale", None),
    }
    return mc, escolhida, dentro, aviso


def _escala_mapunit(crs) -> float | None:
    from core.infra.ifc import unidades
    try:
        mu = getattr(crs, "MapUnit", None)
        if mu is not None and mu.is_a("IfcSIUnit") and getattr(mu, "Name", None) == "METRE":
            return unidades.multiplicador_prefixo(getattr(mu, "Prefix", None))
    except Exception:
        pass
    return None


def _escala_projeto(modelo) -> float | None:
    from core.infra.ifc import unidades
    return unidades.escala_comprimento(modelo)


def _area_uso(epsg):
    try:
        from pyproj import CRS
        au = CRS.from_user_input(epsg).area_of_use
        if au is None:
            return None
        return (au.west, au.south, au.east, au.north)
    except Exception:
        return None


def _reproj(epsg, e, n):
    try:
        from pyproj import Transformer
        lon, lat = Transformer.from_crs(epsg, "EPSG:4326", always_xy=True).transform(e, n)
        return lon, lat
    except Exception:
        return None, None
