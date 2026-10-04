"""Modelos IFC falsos para testar sem IfcOpenShell.

Imitam ``modelo.by_type(tipo)``, ``modelo.schema`` e, nas entidades,
``is_a(tipo)`` e atributos por ``getattr``.
"""

from __future__ import annotations


class FakeEntity:
    def __init__(self, _type, _gid=None, **attrs):
        self._type = _type
        self.GlobalId = _gid
        for k, v in attrs.items():
            setattr(self, k, v)

    def is_a(self, tipo=None):
        return self._type if tipo is None else (self._type == tipo)


class FakeModel:
    def __init__(self, entidades, schema="IFC4"):
        self._entidades = entidades
        self.schema = schema

    def by_type(self, tipo):
        # Imita o IfcOpenShell: tipo inexistente no schema levanta erro.
        if self.schema and not self.schema.upper().startswith("IFC4") and \
           tipo in ("IfcProjectedCRS", "IfcMapConversion"):
            raise RuntimeError(f"Entity with name '{tipo}' not found in schema '{self.schema}'")
        return [e for e in self._entidades if e._type == tipo]


def modelo_vazio() -> FakeModel:
    return FakeModel([])


def _site_e_projeto():
    site = FakeEntity("IfcSite", _gid="S1",
                      RefLatitude=[23, 0, 0], RefLongitude=[46, 0, 0],
                      ObjectPlacement=FakeEntity("IfcLocalPlacement"))
    return [FakeEntity("IfcProject", _gid="P1"), FakeEntity("IfcPostalAddress"), site]


def modelo_nivel_30() -> FakeModel:
    return FakeModel(_site_e_projeto())


def modelo_nivel_50(epsg="EPSG:31983", scale=1.0,
                    eastings=200000.0, northings=7500000.0) -> FakeModel:
    ctx = FakeEntity("IfcGeometricRepresentationContext",
                     WorldCoordinateSystem=object(), TrueNorth=object())
    crs = FakeEntity("IfcProjectedCRS", Name=epsg)
    conv = FakeEntity("IfcMapConversion", Eastings=eastings, Northings=northings,
                      Scale=scale, XAxisAbscissa=1.0, XAxisOrdinate=0.0)
    return FakeModel(_site_e_projeto() + [ctx, crs, conv])


def modelo_ifc2x3() -> FakeModel:
    """Modelo IFC2X3 (sem entidades de CRS do IFC4): teto LoGeoRef 40."""
    ctx = FakeEntity("IfcGeometricRepresentationContext",
                     WorldCoordinateSystem=object(), TrueNorth=object())
    return FakeModel(_site_e_projeto() + [ctx], schema="IFC2X3")

# ---------------------------------------------------------------------------
# Terreno (IfcSite): representações e variantes usadas pelo Enquadramento
# ---------------------------------------------------------------------------

def _polilinha(pontos):
    pts = [FakeEntity("IfcCartesianPoint", Coordinates=tuple(p)) for p in pontos]
    return FakeEntity("IfcPolyline", Points=pts)


def representacao_footprint(pontos):
    """IfcProductDefinitionShape com um FootPrint em IfcPolyline."""
    rep = FakeEntity("IfcShapeRepresentation",
                     RepresentationIdentifier="FootPrint",
                     RepresentationType="Curve2D",
                     Items=[_polilinha(pontos)])
    return FakeEntity("IfcProductDefinitionShape", Representations=[rep])


def _site(gid="S1", lat=(23, 0, 0), lon=(46, 0, 0), representacao=None,
          matricula=None, nome=None):
    return FakeEntity("IfcSite", _gid=gid, Name=nome,
                      RefLatitude=lat, RefLongitude=lon,
                      Representation=representacao,
                      LandTitleNumber=matricula,
                      ObjectPlacement=FakeEntity("IfcLocalPlacement"))


def _crs_e_conversao(epsg="EPSG:31983", eastings=200000.0, northings=7500000.0,
                     xa=1.0, xo=0.0, scale=1.0):
    ctx = FakeEntity("IfcGeometricRepresentationContext",
                     WorldCoordinateSystem=object(), TrueNorth=object())
    crs = FakeEntity("IfcProjectedCRS", Name=epsg)
    conv = FakeEntity("IfcMapConversion", Eastings=eastings, Northings=northings,
                      Scale=scale, XAxisAbscissa=xa, XAxisOrdinate=xo)
    return [ctx, crs, conv]


def modelo_sem_site() -> FakeModel:
    return FakeModel([FakeEntity("IfcProject", _gid="P1")])


def modelo_site_com_footprint(pontos, *, nivel_50=True, lat_lon=True,
                              matricula=None, **conv) -> FakeModel:
    """IfcSite com FootPrint; com ou sem CRS projetado (LoGeoRef 50)."""
    site = _site(representacao=representacao_footprint(pontos),
                 lat=(23, 0, 0) if lat_lon else None,
                 lon=(46, 0, 0) if lat_lon else None,
                 matricula=matricula)
    base = [FakeEntity("IfcProject", _gid="P1"), FakeEntity("IfcPostalAddress"), site]
    return FakeModel(base + (_crs_e_conversao(**conv) if nivel_50 else []))


def modelo_dois_sites_com_footprint(pontos) -> FakeModel:
    a = _site(gid="S1", nome="Gleba A", representacao=representacao_footprint(pontos))
    b = _site(gid="S2", nome="Gleba B", representacao=representacao_footprint(pontos))
    return FakeModel([FakeEntity("IfcProject", _gid="P1"), a, b]
                     + _crs_e_conversao())


def modelo_nivel_50_sem_coordenadas() -> FakeModel:
    """LoGeoRef 50, IfcSite sem lat/lon e sem geometria: só a origem do modelo."""
    site = _site(lat=None, lon=None)
    return FakeModel([FakeEntity("IfcProject", _gid="P1"), site]
                     + _crs_e_conversao())

# ---------------------------------------------------------------------------
# IfcGeographicElement (terreno) e decomposição de site
# ---------------------------------------------------------------------------

def elemento_geografico(nome, pontos, *, predefinido="TERRAIN",
                        object_type=None, descricao=None, gid="G1"):
    """IfcGeographicElement com FootPrint.

    ``predefinido=None`` + ``object_type='terrain'`` imita o padrão do
    Building-Landscaping (tipo em texto, PredefinedType vazio).
    """
    return FakeEntity("IfcGeographicElement", _gid=gid, Name=nome,
                      Description=descricao, ObjectType=object_type,
                      Representation=representacao_footprint(pontos),
                      PredefinedType=predefinido, Tag=None,
                      ObjectPlacement=FakeEntity("IfcLocalPlacement"))


def modelo_terrain(elementos, *, contido_em="IfcBuildingStorey",
                   site_com_footprint=None, lat_lon=True, **conv) -> FakeModel:
    """IfcSite (por padrão SEM geometria) + IfcGeographicElement de terreno.

    ``contido_em`` é a classe da estrutura espacial que contém os elementos —
    o caso real do Revit os coloca no pavimento, não no site.
    """
    site = _site(representacao=(representacao_footprint(site_com_footprint)
                                if site_com_footprint else None),
                 lat=(23, 0, 0) if lat_lon else None,
                 lon=(46, 0, 0) if lat_lon else None)
    estrutura = site if contido_em == "IfcSite" else FakeEntity(contido_em, _gid="ST1")
    rel = FakeEntity("IfcRelContainedInSpatialStructure", _gid="R1",
                     RelatedElements=list(elementos), RelatingStructure=estrutura)
    base = [FakeEntity("IfcProject", _gid="P1"), site, rel]
    if estrutura is not site:
        base.append(estrutura)
    return FakeModel(base + list(elementos) + _crs_e_conversao(**conv))


def modelo_sites_decompostos(pontos_complex, pontos_partial) -> FakeModel:
    """Decomposição legítima: um .COMPLEX. agregando um .PARTIAL., ambos com geometria."""
    raiz = FakeEntity("IfcSite", _gid="SC", Name="terreno (conjunto)",
                      Representation=representacao_footprint(pontos_complex),
                      CompositionType="COMPLEX", RefLatitude=(23, 0, 0),
                      RefLongitude=(46, 0, 0),
                      ObjectPlacement=FakeEntity("IfcLocalPlacement"))
    parte = FakeEntity("IfcSite", _gid="SP", Name="terreno (parte)",
                       Representation=representacao_footprint(pontos_partial),
                       CompositionType="PARTIAL", RefLatitude=(23, 0, 0),
                       RefLongitude=(46, 0, 0),
                       ObjectPlacement=FakeEntity("IfcLocalPlacement"))
    return FakeModel([FakeEntity("IfcProject", _gid="P1"), raiz, parte]
                     + _crs_e_conversao())


def modelo_sites_irmaos(pontos) -> FakeModel:
    """Ambiguidade real: dois .ELEMENT. independentes, cada um com geometria."""
    a = _site(gid="S1", nome="Gleba A", representacao=representacao_footprint(pontos))
    b = _site(gid="S2", nome="Gleba B", representacao=representacao_footprint(pontos))
    for site in (a, b):
        site.CompositionType = "ELEMENT"
    return FakeModel([FakeEntity("IfcProject", _gid="P1"), a, b]
                     + _crs_e_conversao())

# ---------------------------------------------------------------------------
# IfcCovering e o hospedeiro (IfcRelCoversBldgElements) — para o classificador
# de core/infra/ifc/classificacao_covering.py
# ---------------------------------------------------------------------------

def covering(predefinido=None, gid="COV1", predefinido_do_tipo=None):
    """IfcCovering isolado. Sem `rel_cobre` que o ligue a um hospedeiro, fica
    ÓRFÃO — e aí o lado só se resolve pelo `PredefinedType` que ele mesmo
    declara (ou herda do tipo, `predefinido_do_tipo`, como o Revit grava)."""
    cov = FakeEntity("IfcCovering", _gid=gid, PredefinedType=predefinido)
    if predefinido_do_tipo is not None:
        tipo = FakeEntity("IfcCoveringType", _gid=f"{gid}-TIPO",
                          PredefinedType=predefinido_do_tipo)
        cov.IsTypedBy = [FakeEntity("IfcRelDefinesByType", RelatingType=tipo)]
    return cov


def parede(gid="W1"):
    return FakeEntity("IfcWall", _gid=gid)


def telhado(gid="R1"):
    return FakeEntity("IfcRoof", _gid=gid)


def laje(gid="SL1"):
    return FakeEntity("IfcSlab", _gid=gid)


def rel_cobre(hospedeiro, *coverings, gid="REL1"):
    """IfcRelCoversBldgElements: `hospedeiro` cobre um ou mais IfcCovering."""
    return FakeEntity("IfcRelCoversBldgElements", _gid=gid,
                      RelatingBuildingElement=hospedeiro,
                      RelatedCoverings=list(coverings))


def modelo_coverings(*entidades) -> FakeModel:
    """Modelo mínimo com IfcCovering, hospedeiros e relações."""
    return FakeModel([FakeEntity("IfcProject", _gid="P1"), *entidades])

# ---------------------------------------------------------------------------
# IfcSpace com pavimento e ponto de inserção — para a triagem de ambientes
# fantasma de core/infra/ifc/extrator_ambientes.py (ADR-031)
# ---------------------------------------------------------------------------

def pavimento(nome="TIPO", gid="ST1"):
    """IfcBuildingStorey com o próprio IfcLocalPlacement (pai dos espaços)."""
    st = FakeEntity("IfcBuildingStorey", _gid=gid, Name=nome)
    st.ObjectPlacement = FakeEntity("IfcLocalPlacement", PlacementRelTo=None)
    return st


def espaco(gid, nome, pav, ponto=(0.0, 0.0, 0.0)):
    """IfcSpace agregado a ``pav`` (IfcRelAggregates), com a origem do
    ``ObjectPlacement`` em ``ponto``, relativa ao posicionamento do pavimento
    (como o Revit grava)."""
    local = FakeEntity("IfcCartesianPoint", Coordinates=tuple(ponto))
    placement = FakeEntity(
        "IfcLocalPlacement", PlacementRelTo=pav.ObjectPlacement,
        RelativePlacement=FakeEntity("IfcAxis2Placement3D", Location=local))
    return FakeEntity("IfcSpace", _gid=gid, Name=nome, LongName=nome,
                      ObjectPlacement=placement,
                      Decomposes=[FakeEntity("IfcRelAggregates", RelatingObject=pav)])


def modelo_espacos(*espacos) -> FakeModel:
    """Modelo mínimo só com IfcSpace (e o que eles já referenciam)."""
    return FakeModel([FakeEntity("IfcProject", _gid="P1"), *espacos])
