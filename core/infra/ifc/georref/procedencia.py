"""Proveniência dos dados de georreferenciamento (rastreabilidade IFC).

Compila, de forma legível, DE ONDE cada informação usada pelo EMP-001 veio:
a **classe IFC**, o **atributo** e o **valor** — bruto (como autorado no IFC) e,
quando aplicável, normalizado (graus decimais, metros, EPSG). É um artefato de
transparência para o relatório: não altera o veredito da regra; apenas expõe os
insumos que a alimentaram.

Cobre as entidades relevantes ao georreferenciamento:
  * IfcPostalAddress   (LoGeoRef 10)
  * IfcSite            (LoGeoRef 20 — RefLatitude/RefLongitude/RefElevation)
  * IfcProjectedCRS    (LoGeoRef 50 — código EPSG, datum, projeção, unidade)
  * IfcMapConversion   (LoGeoRef 50 — Eastings/Northings/OrthogonalHeight/eixo/escala)

Saída: ``{"tipo": "procedencia", "unidade_projeto": str|None, "linhas": [...]}``,
onde cada linha é ``{classe, propriedade, valor, fonte}`` (``fonte`` = "atributo"
para o valor lido do IFC, ou "derivado" para valores calculados a partir dele).
"""

from __future__ import annotations

from typing import Any

from core.infra.ifc.georref import ancora as _ancora

# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------

def _by_type(modelo: Any, tipo: str) -> list:
    try:
        return list(modelo.by_type(tipo))
    except Exception:
        return []


def _rotulo_unidade(modelo: Any) -> str | None:
    """Nome legível da unidade de comprimento do projeto (ex.: 'MILLIMETRE')."""
    try:
        import ifcopenshell.util.unit as uu
        u = uu.get_project_unit(modelo, "LENGTHUNIT")
        if u is None:
            return None
        prefixo = getattr(u, "Prefix", None) or ""
        nome = getattr(u, "Name", None) or ""
        return f"{prefixo}{nome}".strip() or None
    except Exception:
        return None


def _dms_bruto(dms) -> str | None:
    """Formata o compound (graus, min, seg[, milionésimos]) como 51° 42′ 27″."""
    try:
        comp = [int(x) for x in list(dms)]
    except (TypeError, ValueError):
        return None
    if not comp:
        return None
    g = comp[0]
    m = abs(comp[1]) if len(comp) > 1 else 0
    s = abs(comp[2]) if len(comp) > 2 else 0
    micro = abs(comp[3]) if len(comp) > 3 else 0
    seg = s + micro / 1_000_000.0
    seg_txt = f"{seg:.0f}″" if micro == 0 else f"{seg:.6f}″"
    return f"{g}° {m}′ {seg_txt}"


def _num(v) -> str | None:
    """Formata coeficientes pequenos (eixo, escala) sem notação científica."""
    if not isinstance(v, (int, float)):
        return None
    return f"{v:g}"


def _fmt_medida(v) -> str | None:
    """Formata medidas (coordenadas, alturas) por extenso, sem notação científica."""
    if not isinstance(v, (int, float)):
        return None
    if float(v).is_integer():
        return str(int(v))
    return f"{v:.3f}".rstrip("0").rstrip(".")


# ---------------------------------------------------------------------------
# Extração
# ---------------------------------------------------------------------------

def extrair(modelo: Any) -> dict:
    """Compila a tabela de proveniência (classe IFC → propriedade → valor)."""
    resultado = {"tipo": "procedencia", "unidade_projeto": None, "linhas": []}
    if modelo is None:
        return resultado

    from core.infra.ifc import unidades
    linhas: list[dict] = resultado["linhas"]
    unidade = _rotulo_unidade(modelo)
    resultado["unidade_projeto"] = unidade
    escala = unidades.escala_comprimento(modelo)

    def add(classe: str, propriedade: str, valor, fonte: str = "atributo") -> None:
        if valor is None or valor == "":
            return
        linhas.append({"classe": classe, "propriedade": propriedade,
                       "valor": str(valor), "fonte": fonte})

    _postal_address(modelo, add)
    _site(modelo, add, escala, unidade)
    _projected_crs(modelo, add)
    _map_conversion(modelo, add, unidade)
    _derivados(modelo, add)
    return resultado


def _postal_address(modelo, add) -> None:
    for a in _by_type(modelo, "IfcPostalAddress"):
        linhas_end = getattr(a, "AddressLines", None) or []
        add("IfcPostalAddress", "AddressLines", ", ".join(str(x) for x in linhas_end))
        for attr in ("Town", "Region", "PostalCode", "Country"):
            add("IfcPostalAddress", attr, getattr(a, attr, None))
        break  # o primeiro endereço basta para a proveniência


def _site(modelo, add, escala, unidade) -> None:
    for site in _by_type(modelo, "IfcSite"):
        add("IfcSite", "Name", getattr(site, "Name", None))
        add("IfcSite", "GlobalId", getattr(site, "GlobalId", None))

        for attr in ("RefLatitude", "RefLongitude"):
            dms = getattr(site, attr, None)
            bruto = _dms_bruto(dms)
            dec = _ancora._dms_para_graus(dms)
            if bruto and dec is not None:
                add("IfcSite", attr, f"{bruto}  ({dec:.6f}°)")

        elev = getattr(site, "RefElevation", None)
        if isinstance(elev, (int, float)):
            u = f" {unidade}" if unidade else ""
            valor = f"{_fmt_medida(elev)}{u}"
            if escala is not None:
                valor += f"  ({elev * escala:.3f} m)"
            add("IfcSite", "RefElevation", valor)
        if getattr(site, "RefLatitude", None) is not None:
            break  # usa o primeiro site georreferenciado


def _projected_crs(modelo, add) -> None:
    for crs in _by_type(modelo, "IfcProjectedCRS"):
        for attr in ("Name", "Description", "GeodeticDatum", "VerticalDatum",
                     "MapProjection", "MapZone"):
            add("IfcProjectedCRS", attr, getattr(crs, attr, None))
        mu = getattr(crs, "MapUnit", None)
        if mu is not None:
            prefixo = getattr(mu, "Prefix", None) or ""
            nome = getattr(mu, "Name", None) or ""
            add("IfcProjectedCRS", "MapUnit", f"{prefixo}{nome}".strip() or None)
        break


def _map_conversion(modelo, add, unidade) -> None:
    for conv in _by_type(modelo, "IfcMapConversion"):
        u = f" {unidade}" if unidade else ""
        for attr in ("Eastings", "Northings", "OrthogonalHeight"):
            v = getattr(conv, attr, None)
            if isinstance(v, (int, float)):
                add("IfcMapConversion", attr, f"{_fmt_medida(v)}{u}")
        for attr in ("XAxisAbscissa", "XAxisOrdinate", "Scale"):
            add("IfcMapConversion", attr, _num(getattr(conv, attr, None)))
        break


def _derivados(modelo, add) -> None:
    """Valores calculados a partir dos atributos brutos (transparência do cálculo)."""
    try:
        anc = _ancora.derivar(modelo)
    except Exception:
        return
    if anc.modo == "preciso":
        if anc.lat is not None and anc.lon is not None:
            add("IfcMapConversion", "Origem reprojetada → WGS 84 (lat, lon)",
                f"{anc.lat:.6f}, {anc.lon:.6f}", fonte="derivado")
        add("IfcMapConversion", "Rotação do modelo (eixo X → Leste)",
            f"{anc.rotacao_graus:.3f}°", fonte="derivado")
        if anc.epsg:
            add("IfcProjectedCRS", "CRS de origem (EPSG)", anc.epsg, fonte="derivado")


def _cli() -> None:
    import argparse
    import json

    import ifcopenshell
    p = argparse.ArgumentParser(description="Compila a proveniência de georreferenciamento de um IFC.")
    p.add_argument("ifc")
    args = p.parse_args()
    modelo = ifcopenshell.open(args.ifc)
    print(json.dumps(extrair(modelo), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _cli()
