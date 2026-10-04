"""Consistência de localização: cruza as afirmações independentes do modelo.

Um IFC pode declarar a localização de até três formas independentes:
  * endereço postal (IfcPostalAddress) — LoGeoRef 10;
  * lat/long do IfcSite (RefLatitude/RefLongitude) — LoGeoRef 20;
  * CRS projetado (IfcMapConversion + IfcProjectedCRS) — LoGeoRef 50.

Cruzá-las é uma verificação de redundância: divergências fortes denunciam dados
de georreferenciamento incorretos (ex.: o default "Boston" do Revit no IfcSite,
ou um CRS de país errado). O cruzamento é feito em dois eixos: horizontal
(lat/long do IfcSite vs. origem do CRS reprojetada) e vertical (RefElevation do
IfcSite, LoGeoRef 20, vs. OrthogonalHeight do MapConversion, LoGeoRef 50). Tudo
offline, sem dependência de rede — coerente com as premissas do protótipo. A
comparação fina por geocodificação do endereço (online) fica como evolução
futura.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

from core.infra.ifc.georref import ancora as _ancora
from core.infra.ifc.georref import leitor_crs

LIMIAR_DIVERGENCIA_KM = 1.0  # acima disso, fontes de coordenadas são consideradas divergentes
LIMIAR_DIVERGENCIA_ALTURA_M = 1.0  # acima disso, RefElevation e OrthogonalHeight são divergentes


@dataclass
class Localizacao:
    endereco: dict = field(default_factory=dict)
    site_latlon: tuple | None = None     # (lat, lon) do IfcSite
    crs_latlon: tuple | None = None      # (lat, lon) do CRS projetado
    pais_endereco: str | None = None
    pais_crs: str | None = None          # nome da área de uso do CRS (registro EPSG)
    distancia_site_crs_km: float | None = None
    site_altura: float | None = None     # RefElevation do IfcSite, em metros
    crs_altura: float | None = None      # OrthogonalHeight do MapConversion, em metros
    divergencia_altura_m: float | None = None
    avisos: list[str] = field(default_factory=list)

    @property
    def consistente(self) -> bool | None:
        # None quando não houve nenhuma comparação possível.
        if not self._houve_comparacao():
            return None
        return len(self.avisos) == 0

    def _houve_comparacao(self) -> bool:
        return (self.distancia_site_crs_km is not None) or \
               (self.divergencia_altura_m is not None) or \
               (self.pais_endereco is not None and self.pais_crs is not None)

    def to_dict(self) -> dict:
        return {
            "tipo": "localizacao",
            "endereco": self.endereco,
            "site_latlon": self.site_latlon,
            "crs_latlon": self.crs_latlon,
            "pais_endereco": self.pais_endereco,
            "pais_crs": self.pais_crs,
            "distancia_site_crs_km": self.distancia_site_crs_km,
            "site_altura": self.site_altura,
            "crs_altura": self.crs_altura,
            "divergencia_altura_m": self.divergencia_altura_m,
            "consistente": self.consistente,
            "avisos": self.avisos,
        }


def avaliar(modelo: Any, ancora_dict: dict | None = None) -> Localizacao:
    """Cruza endereço, lat/long do site e CRS, devolvendo o diagnóstico."""
    loc = Localizacao()
    if modelo is None:
        return loc

    # 1) Endereço postal
    addr = _endereco(modelo)
    loc.endereco = addr
    loc.pais_endereco = (addr.get("country") or None)

    # 2) Lat/long do IfcSite (LoGeoRef 20)
    loc.site_latlon = _site_latlon(modelo)

    # 3) Ponto do CRS projetado (via âncora, se não vier pronta)
    if ancora_dict is None:
        ancora_dict = _ancora.derivar(modelo).to_dict()
    if ancora_dict.get("modo") == "preciso" and ancora_dict.get("lat") is not None:
        loc.crs_latlon = (ancora_dict["lat"], ancora_dict["lon"])
        loc.pais_crs = _pais_do_crs(ancora_dict.get("epsg"))

    # 4) Alturas: RefElevation (IfcSite, LoGeoRef 20) x OrthogonalHeight (CRS, 50).
    #    Ambas em metros. OrthogonalHeight já vem convertido pelo leitor_crs;
    #    RefElevation é convertido aqui pela escala de comprimento do projeto.
    loc.site_altura = _site_elevacao_m(modelo)
    if loc.crs_latlon is not None:  # há CRS projetado válido
        info = leitor_crs.ler(modelo)
        loc.crs_altura = (info.map_conversion or {}).get("orthogonal_height")

    # --- Cruzamentos ---
    if loc.site_latlon and loc.crs_latlon:
        d = _haversine_km(loc.site_latlon, loc.crs_latlon)
        loc.distancia_site_crs_km = round(d, 3)
        if d > LIMIAR_DIVERGENCIA_KM:
            loc.avisos.append(
                f"Lat/long do IfcSite diverge do CRS em {d:.1f} km — a coordenada do "
                f"site pode ser um valor padrão (ex.: default do exportador)."
            )

    if loc.site_altura is not None and loc.crs_altura is not None:
        dz = abs(loc.site_altura - loc.crs_altura)
        loc.divergencia_altura_m = round(dz, 3)
        if dz > LIMIAR_DIVERGENCIA_ALTURA_M:
            loc.avisos.append(
                f"Altura do IfcSite (RefElevation = {loc.site_altura:.2f} m) diverge da "
                f"altura do CRS (OrthogonalHeight = {loc.crs_altura:.2f} m) em {dz:.2f} m "
                f"— verifique o datum vertical ou um valor padrão do exportador."
            )

    if loc.pais_endereco and loc.pais_crs and not _mesmo_pais(loc.pais_endereco, loc.pais_crs):
        loc.avisos.append(
            f"País do endereço ('{loc.pais_endereco}') difere da área de uso do "
            f"CRS ('{loc.pais_crs}')."
        )
    return loc


# ---------------------------------------------------------------------------
# Extração
# ---------------------------------------------------------------------------

def _endereco(modelo: Any) -> dict:
    try:
        enderecos = list(modelo.by_type("IfcPostalAddress"))
    except Exception:
        return {}
    if not enderecos:
        return {}
    a = enderecos[0]
    linhas = getattr(a, "AddressLines", None) or []
    return {
        "address_lines": [str(x).strip() for x in linhas],
        "town": _limpo(getattr(a, "Town", None)),
        "region": _limpo(getattr(a, "Region", None)),
        "postal_code": _limpo(getattr(a, "PostalCode", None)),
        "country": _limpo(getattr(a, "Country", None)),
    }


def _site_latlon(modelo: Any) -> tuple | None:
    try:
        sites = list(modelo.by_type("IfcSite"))
    except Exception:
        return None
    for site in sites:
        lat = _ancora._dms_para_graus(getattr(site, "RefLatitude", None))
        lon = _ancora._dms_para_graus(getattr(site, "RefLongitude", None))
        if lat is not None and lon is not None:
            return (lat, lon)
    return None


def _site_elevacao_m(modelo: Any) -> float | None:
    """RefElevation do IfcSite convertido para metros (unidade de comprimento do projeto)."""
    try:
        sites = list(modelo.by_type("IfcSite"))
    except Exception:
        return None
    from core.infra.ifc import unidades
    escala = unidades.escala_comprimento(modelo)
    for site in sites:
        elev = getattr(site, "RefElevation", None)
        if isinstance(elev, (int, float)):
            return float(elev) * escala
    return None


def _pais_do_crs(epsg: str | None) -> str | None:
    if not epsg:
        return None
    try:
        from pyproj import CRS
        au = CRS.from_user_input(epsg).area_of_use
        return au.name if au else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------

def _haversine_km(a: tuple, b: tuple) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * 6371.0088 * math.asin(min(1.0, math.sqrt(h)))


_PARADAS = {"the", "of", "onshore", "offshore", "and", "republic"}


def _tokens(texto: str) -> set:
    return {t for t in re.findall(r"[a-z]+", (texto or "").lower()) if t not in _PARADAS and len(t) > 2}


def _mesmo_pais(pais_endereco: str, area_crs: str) -> bool:
    """Heurística offline: há token de país em comum entre as duas descrições."""
    return bool(_tokens(pais_endereco) & _tokens(area_crs))


def _limpo(valor):
    if valor is None:
        return None
    s = str(valor).strip()
    return s or None


def _cli() -> None:
    import argparse
    import json

    import ifcopenshell
    p = argparse.ArgumentParser(description="Cruza endereço, lat/long do site e CRS de um IFC.")
    p.add_argument("ifc")
    args = p.parse_args()
    modelo = ifcopenshell.open(args.ifc)
    print(json.dumps(avaliar(modelo).to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _cli()
