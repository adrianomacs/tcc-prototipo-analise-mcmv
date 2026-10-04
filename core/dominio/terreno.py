"""Terreno do empreendimento — objeto de domínio canônico do Enquadramento.

Premissa da arquitetura: as formas de
entrada não são fluxos paralelos, são **construtores do mesmo objeto**. Nenhuma
regra ENQ sabe se o terreno veio de um IfcSite, de um CSV de memorial ou de uma
poligonal desenhada no mapa — ela lê ``ctx.empreendimento.terreno`` e mede.

Dois campos carregam o que distingue as origens, e ambos aparecem no relatório:

* ``nivel``    — capacidade da entrada: ``poligonal`` ou ``ponto``. É o que o
  metadado ``Regra.exige_terreno`` confronta (gate no executor).
* ``precisao`` — qualidade da geometria: ``levantada`` (memorial, IFC),
  ``declarada`` (coordenada informada) ou ``aproximada`` (desenho no mapa).
  Ortogonal à origem: um CSV de memorial é levantado, um desenho é aproximado.

Pelo ADR-023 o terreno pode ainda carregar um ``modelo`` (``ModeloBIM``,
0..1): o contêiner que o descreve, quando a submissão traz um. Ele **não**
muda a fonte do EMP-001 — serve para conferir o terreno que já foi declarado
por outra via, e conferência não é veredito.

O centro é **calculado no CRS métrico** (ver ``crs.py``). Em lote côncavo o
centróide pode cair fora da poligonal; mantém-se o centróide, porque é o que a
Portaria chama de "centro do terreno", e registra-se o aviso — mesma postura
honesta do campo ``metodo`` nas regras de largura de ambientes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.dominio import geometria as crs
from core.dominio.modelo_bim import ModeloBIM

# --- Nível de capacidade (confrontado por Regra.exige_terreno) -------------
NIVEL_PONTO = "ponto"
NIVEL_POLIGONAL = "poligonal"

# --- Origem do dado --------------------------------------------------------
ORIGEM_IFC = "ifc"
ORIGEM_CSV = "csv"
ORIGEM_DESENHADA = "desenhada"
ORIGEM_PONTO = "ponto"

# --- Precisão da geometria -------------------------------------------------
PRECISAO_LEVANTADA = "levantada"
PRECISAO_DECLARADA = "declarada"
PRECISAO_APROXIMADA = "aproximada"

ROTULO_NIVEL = {
    NIVEL_PONTO: "centro do terreno (sem poligonal)",
    NIVEL_POLIGONAL: "poligonal do terreno",
}
ROTULO_ORIGEM = {
    ORIGEM_IFC: "modelo IFC (IfcSite)",
    ORIGEM_CSV: "CSV de poligonal",
    ORIGEM_DESENHADA: "poligonal desenhada no mapa",
    ORIGEM_PONTO: "coordenada informada",
}
ROTULO_PRECISAO = {
    PRECISAO_LEVANTADA: "levantada",
    PRECISAO_DECLARADA: "declarada",
    PRECISAO_APROXIMADA: "aproximada",
}


@dataclass
class Terreno:
    """O terreno resolvido, pronto para as regras de Enquadramento.

    As geometrias no CRS métrico (``centro`` e ``poligonal``) são propriedades
    derivadas: o estado serializado guarda apenas WGS 84, de modo que
    ``artefatos/terreno.json`` seja legível e portátil, e a reprojeção é feita
    sob demanda ao ler o artefato.
    """

    origem: str
    nivel: str
    precisao: str
    crs_metrico: str
    centro_wgs84: tuple[float, float]              # (lat, lon)
    poligonal_wgs84: dict | None = None            # GeoJSON Polygon (lon, lat)
    area_m2: float | None = None
    perimetro_m: float | None = None
    procedencia: dict = field(default_factory=dict)
    avisos: list[str] = field(default_factory=list)
    # O contêiner que descreve ESTE terreno (ADR-023), 0..1. Fonte de
    # informação que confere o terreno declarado antes — poligonal
    # desenhada, CSV de memorial: conferência, não veredito do EMP-001.
    modelo: ModeloBIM | None = None

    _centro: Any = field(default=None, repr=False, compare=False)
    _poligonal: Any = field(default=None, repr=False, compare=False)

    # -- capacidade ---------------------------------------------------------

    @property
    def tem_poligonal(self) -> bool:
        return self.nivel == NIVEL_POLIGONAL and self.poligonal_wgs84 is not None

    def atende(self, exigencia: str) -> bool:
        """True se este terreno satisfaz a exigência de nível de uma regra.

        ``""`` = a regra não exige terreno; ``"ponto"`` = basta o centro (todo
        terreno tem centro); ``"poligonal"`` = exige a geometria.
        """
        if not exigencia:
            return True
        if exigencia == NIVEL_PONTO:
            return self.centro_wgs84 is not None
        if exigencia == NIVEL_POLIGONAL:
            return self.tem_poligonal
        return True

    # -- geometrias métricas (derivadas) ------------------------------------

    @property
    def centro(self) -> Any:
        """Centro do terreno como ponto Shapely no CRS métrico."""
        if self._centro is None:
            from shapely.geometry import Point

            lat, lon = self.centro_wgs84
            x, y = crs.reprojetar_ponto(lon, lat, crs.CRS_GEOGRAFICO, self.crs_metrico)
            self._centro = Point(x, y)
        return self._centro

    @property
    def poligonal(self) -> Any:
        """Poligonal como polígono Shapely no CRS métrico, ou None."""
        if self._poligonal is None and self.poligonal_wgs84 is not None:
            from shapely.geometry import shape

            geo = shape(self.poligonal_wgs84)
            self._poligonal = crs.reprojetar(geo, crs.CRS_GEOGRAFICO, self.crs_metrico)
        return self._poligonal

    # -- serialização (contrato de artefatos/terreno.json) ------------------

    def to_dict(self) -> dict:
        return {
            "origem": self.origem,
            "nivel": self.nivel,
            "precisao": self.precisao,
            "crs_metrico": self.crs_metrico,
            "centro_wgs84": {"lat": self.centro_wgs84[0], "lon": self.centro_wgs84[1]},
            "poligonal_wgs84": self.poligonal_wgs84,
            "area_m2": self.area_m2,
            "perimetro_m": self.perimetro_m,
            "procedencia": self.procedencia,
            "avisos": list(self.avisos),
            "modelo": self.modelo.to_dict() if self.modelo is not None else None,
        }

    @classmethod
    def from_dict(cls, dados: dict) -> Terreno:
        centro = dados.get("centro_wgs84") or {}
        return cls(
            origem=dados.get("origem", ""),
            nivel=dados.get("nivel", NIVEL_PONTO),
            precisao=dados.get("precisao", PRECISAO_DECLARADA),
            crs_metrico=dados.get("crs_metrico", ""),
            centro_wgs84=(float(centro.get("lat")), float(centro.get("lon"))),
            poligonal_wgs84=dados.get("poligonal_wgs84"),
            area_m2=dados.get("area_m2"),
            perimetro_m=dados.get("perimetro_m"),
            procedencia=dict(dados.get("procedencia") or {}),
            avisos=list(dados.get("avisos") or []),
            modelo=ModeloBIM.from_dict(dados.get("modelo")),
        )

    def resumo(self) -> str:
        """Uma linha legível para cabeçalho de relatório."""
        lat, lon = self.centro_wgs84
        base = (f"{ROTULO_ORIGEM.get(self.origem, self.origem)} — "
                f"{ROTULO_NIVEL.get(self.nivel, self.nivel)}, precisão "
                f"{ROTULO_PRECISAO.get(self.precisao, self.precisao)}; "
                f"centro {lat:.6f}, {lon:.6f} ({self.crs_metrico})")
        if self.area_m2:
            base += f"; área {formatar_numero(self.area_m2)} m²"
        return base


def formatar_numero(valor, decimais: int = 2) -> str:
    """Número no formato brasileiro: milhar com ponto, decimal com vírgula.

    Existe porque o idioma ``f"{v:,.2f}".replace(",", ".")`` — usado em vários
    pontos — produzia **"1.000.071.23"** para 1.000.071,23: o separador de
    milhar virava ponto e o decimal continuava ponto. Um milhão de metros
    quadrados lido como se fosse outra coisa é o tipo de erro que faz o usuário
    desconfiar do número certo (já aconteceu).
    """
    if valor is None:
        return "—"
    texto = f"{float(valor):,.{decimais}f}"
    return texto.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


# ---------------------------------------------------------------------------
# Construtores
# ---------------------------------------------------------------------------

def de_poligonal_wgs84(coordenadas: list[tuple[float, float]], *, origem: str,
                       precisao: str, procedencia: dict | None = None) -> Terreno:
    """Constrói o terreno a partir de uma poligonal em WGS 84.

    ``coordenadas`` são pares **(lon, lat)** em graus decimais — a ordem do
    GeoJSON, para evitar a troca de eixos que é a falha clássica desta etapa.
    O anel é fechado automaticamente; geometria inválida é corrigida por
    ``make_valid`` e o fato é registrado nos avisos.
    """
    from shapely.geometry import Polygon, mapping
    from shapely.validation import make_valid

    pontos = [(float(x), float(y)) for x, y in coordenadas]
    if len(pontos) >= 2 and pontos[0] == pontos[-1]:
        pontos = pontos[:-1]
    if len(set(pontos)) < 3:
        raise ValueError("Uma poligonal exige ao menos 3 vértices distintos.")

    avisos: list[str] = []
    geo = Polygon(pontos)
    if not geo.is_valid:
        corrigida = make_valid(geo)
        if corrigida.geom_type == "MultiPolygon":
            corrigida = max(corrigida.geoms, key=lambda g: g.area)
            avisos.append("Poligonal com auto-interseção: mantida a maior parte "
                          "resultante da correção. Confira o desenho.")
        elif corrigida.geom_type != "Polygon":
            raise ValueError("A poligonal informada não descreve uma área válida.")
        else:
            avisos.append("Poligonal corrigida por make_valid (auto-interseção).")
        geo = corrigida

    lon_min, _lat_min, lon_max, _lat_max = geo.bounds
    provisorio = geo.centroid
    epsg = crs.epsg_metrico(provisorio.x, provisorio.y)

    fusos = crs.fusos_abrangidos(lon_min, lon_max)
    if len(fusos) > 1:
        avisos.append(f"Terreno a cavaleiro dos fusos UTM {fusos}; medido em "
                      f"{epsg} (fuso do centróide).")

    metrica = crs.reprojetar(geo, crs.CRS_GEOGRAFICO, epsg)
    centro_m = metrica.centroid
    if not metrica.contains(centro_m):
        avisos.append("O centróide cai fora da poligonal (lote côncavo). Mantido "
                      "como centro por ser o que a Portaria define; considerar na "
                      "leitura das distâncias.")

    lon_c, lat_c = crs.reprojetar_ponto(centro_m.x, centro_m.y, epsg, crs.CRS_GEOGRAFICO)

    proc = {"metodo_centro": "centróide da poligonal no CRS métrico",
            "fuso_utm": crs.fuso_utm(provisorio.x)}
    proc.update(procedencia or {})

    t = Terreno(
        origem=origem, nivel=NIVEL_POLIGONAL, precisao=precisao, crs_metrico=epsg,
        centro_wgs84=(lat_c, lon_c), poligonal_wgs84=mapping(geo),
        area_m2=round(metrica.area, 2), perimetro_m=round(metrica.length, 2),
        procedencia=proc, avisos=avisos,
    )
    t._poligonal, t._centro = metrica, centro_m
    return t


def de_ponto_wgs84(lat: float, lon: float, *, origem: str = ORIGEM_PONTO,
                   precisao: str = PRECISAO_DECLARADA,
                   procedencia: dict | None = None) -> Terreno:
    """Constrói o terreno apenas com o centro informado (nível ``ponto``).

    Nível reduzido de propósito: as regras que exigem a poligonal ficam não
    avaliáveis com motivo explícito, em vez de serem avaliadas sobre geometria
    inventada.
    """
    lat, lon = float(lat), float(lon)
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        raise ValueError(f"Coordenada fora do intervalo válido: {lat}, {lon}.")

    epsg = crs.epsg_metrico(lon, lat)
    proc = {"metodo_centro": "coordenada informada pelo usuário",
            "fuso_utm": crs.fuso_utm(lon)}
    proc.update(procedencia or {})
    return Terreno(
        origem=origem, nivel=NIVEL_PONTO, precisao=precisao, crs_metrico=epsg,
        centro_wgs84=(lat, lon), procedencia=proc,
    )
