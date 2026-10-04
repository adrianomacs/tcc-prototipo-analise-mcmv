"""Âncora geográfica do modelo (passo 2 da visualização).

Deriva onde o modelo deve ser posicionado no globo, produzindo um artefato de
posicionamento independente do visualizador: origem (lon/lat/altura em WGS 84) e
rotação em torno do eixo vertical.

Modos (do mais preciso ao indisponível):

* "preciso"     — há CRS projetado (IfcProjectedCRS + IfcMapConversion). A origem
                  do modelo (Eastings/Northings) é reprojetada para WGS 84 via
                  pyproj; a rotação vem do eixo X do MapConversion.
* "aproximado"  — sem CRS projetado, mas com lat/long no IfcSite (WGS 84).
* "indisponivel"— sem âncora derivável; caberá ajuste manual na interface.

Não modifica o IFC. A rotação segue a convenção: ângulo do eixo +X do modelo em
relação ao Leste da projeção, em graus, sentido anti-horário (a cena aplica essa
rotação em torno do eixo vertical do referencial local Leste-Norte-Cima).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from core.infra.ifc.georref import leitor_crs

CRS_GEOGRAFICO = "EPSG:4326"  # WGS 84 — datum do globo do CesiumJS


@dataclass
class Ancora:
    modo: str = "indisponivel"          # preciso | aproximado | indisponivel
    lat: float | None = None
    lon: float | None = None
    altura: float = 0.0
    rotacao_graus: float = 0.0
    epsg: str | None = None             # CRS projetado de origem (modo preciso)
    crs_geografico: str = CRS_GEOGRAFICO
    mensagem: str = ""

    @property
    def disponivel(self) -> bool:
        return self.modo != "indisponivel" and self.lat is not None and self.lon is not None

    def to_dict(self) -> dict:
        return {
            "modo": self.modo,
            "lat": self.lat,
            "lon": self.lon,
            "altura": self.altura,
            "rotacao_graus": self.rotacao_graus,
            "epsg": self.epsg,
            "crs_geografico": self.crs_geografico,
            "mensagem": self.mensagem,
        }


def derivar(modelo: Any, *, crs_geografico: str = CRS_GEOGRAFICO) -> Ancora:
    """Deriva a âncora geográfica do modelo IFC."""
    if modelo is None:
        return Ancora(mensagem="Modelo IFC não carregado.")

    info = leitor_crs.ler(modelo)
    if info.valido and info.epsg:
        ancora = _do_crs_projetado(info, crs_geografico)
        if ancora is not None:
            return ancora

    aprox = _do_site(modelo)
    if aprox is not None:
        return aprox

    motivo = info.mensagem or "sem coordenadas no IfcSite"
    return Ancora(mensagem=f"Âncora indisponível ({motivo}); requer ajuste manual.")


def _do_crs_projetado(info: leitor_crs.InfoGeorref, crs_geografico: str) -> Ancora | None:
    mc = info.map_conversion or {}
    e, n = mc.get("eastings"), mc.get("northings")
    if e is None or n is None:
        return None
    try:
        from pyproj import Transformer
        t = Transformer.from_crs(info.epsg, crs_geografico, always_xy=True)
        lon, lat = t.transform(float(e), float(n))
    except Exception as exc:
        return Ancora(mensagem=f"Falha ao reprojetar a origem ({exc!r}).")

    xa = mc.get("x_axis_abscissa")
    xo = mc.get("x_axis_ordinate")
    rot = math.degrees(math.atan2(float(xo), float(xa))) if (xa is not None and xo is not None) else 0.0

    altura = float(mc.get("orthogonal_height") or 0.0)
    return Ancora(modo="preciso", lat=lat, lon=lon, altura=altura, rotacao_graus=rot,
                  epsg=info.epsg, crs_geografico=crs_geografico,
                  mensagem=("Origem reprojetada de {} (modo preciso). {}".format(info.epsg, getattr(info, "aviso", "") or "")).strip())


def _do_site(modelo: Any) -> Ancora | None:
    try:
        sites = list(modelo.by_type("IfcSite"))
    except Exception:
        return None
    for site in sites:
        lat = _dms_para_graus(getattr(site, "RefLatitude", None))
        lon = _dms_para_graus(getattr(site, "RefLongitude", None))
        if lat is not None and lon is not None:
            altura = float(getattr(site, "RefElevation", None) or 0.0)
            return Ancora(modo="aproximado", lat=lat, lon=lon, altura=altura,
                          rotacao_graus=0.0,
                          mensagem="Origem a partir da lat/long do IfcSite (WGS 84, modo aproximado).")
    return None


def _dms_para_graus(dms) -> float | None:
    """Converte (graus, min, seg[, milionésimos]) do IFC em graus decimais.

    O sinal segue a primeira componente não nula (convenção do IFC).
    """
    if not dms:
        return None
    try:
        comp = list(dms)
    except TypeError:
        return None
    if not comp:
        return None
    sinal = -1.0 if any(c < 0 for c in comp) else 1.0
    g = abs(comp[0]) if len(comp) > 0 else 0.0
    m = abs(comp[1]) if len(comp) > 1 else 0.0
    s = abs(comp[2]) if len(comp) > 2 else 0.0
    micro = abs(comp[3]) if len(comp) > 3 else 0.0
    return sinal * (g + m / 60.0 + (s + micro / 1_000_000.0) / 3600.0)


def coordenadas_do_site(modelo: Any) -> tuple[float, float] | None:
    """(lat, lon) declaradas no IfcSite, em graus decimais, ou None.

    Aditiva a este módulo (``_do_site`` segue intocado): o Enquadramento precisa
    da coordenada DO SITE especificamente, e não da âncora que ``derivar``
    escolhe. A diferença é semântica e importa: a âncora prefere a origem do
    MapConversion, que é o ponto de inserção do modelo — não o terreno.
    """
    try:
        sites = list(modelo.by_type("IfcSite")) if modelo is not None else []
    except Exception:
        return None
    for site in sites:
        lat = _dms_para_graus(getattr(site, "RefLatitude", None))
        lon = _dms_para_graus(getattr(site, "RefLongitude", None))
        if lat is not None and lon is not None:
            return (lat, lon)
    return None


def _cli() -> None:
    import argparse
    import json

    import ifcopenshell
    p = argparse.ArgumentParser(description="Deriva a âncora geográfica de um IFC.")
    p.add_argument("ifc")
    args = p.parse_args()
    modelo = ifcopenshell.open(args.ifc)
    print(json.dumps(derivar(modelo).to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _cli()
