"""Extracao de ambientes (IfcSpace): Id/nome/area (leitor_ambientes.py) e
largura/comprimento de planta (geometria_ambientes.py) — unificados. Isolado do IfcOpenShell na funcao ``listar``/``medir``; a logica
pura de selecao fica em funcoes auxiliares testaveis sem a biblioteca.

``triar`` separa a **população** que as regras avaliam dos ambientes com
indício de defeito de autoria, os "fantasmas" do exportador (ADR-031).
``listar`` segue devolvendo todos os ``IfcSpace``, porque a visualização
mostra o modelo como ele veio. Quem avalia chama ``triar``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from core.dominio.edificacao import Ambiente

_CHAVES_AREA = ("NetFloorArea", "GrossFloorArea", "NetArea", "GrossArea", "Area")

METODO = "menor lado do retângulo rotacionado mínimo do footprint (projeção XY)"


def listar(modelo: Any) -> list[Ambiente]:
    """Devolve os ambientes (IfcSpace) do modelo com Id, nome, descrição e área."""
    if modelo is None:
        return []
    try:
        espacos = list(modelo.by_type("IfcSpace"))
    except Exception:
        return []

    from core.infra.ifc import unidades
    escala = unidades.escala_area(modelo)
    ambientes: list[Ambiente] = []
    for sp in espacos:
        gid = getattr(sp, "GlobalId", "") or ""
        name = _limpo(getattr(sp, "Name", None))
        long_name = _limpo(getattr(sp, "LongName", None))
        descricao = _limpo(getattr(sp, "Description", None))
        area, fonte = _area_de_psets(_psets_do_espaco(sp), escala)
        classe_ifc = sp.is_a()
        ambientes.append(Ambiente(
            global_id=gid, nome=_nome(name, long_name, gid),
            name=name, long_name=long_name, descricao=descricao,
            area_m2=area, fonte_area=fonte, classe_ifc=classe_ifc,
        ))
    return ambientes


def _nome(name: str | None, long_name: str | None, gid: str) -> str:
    return long_name or name or gid or "(sem nome)"


def _area_de_psets(psets: dict, escala_area: float) -> tuple[float | None, str | None]:
    for chave in _CHAVES_AREA:
        valor = psets.get(chave)
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            return round(float(valor) * escala_area, 4), chave
    for chave, valor in psets.items():
        if (isinstance(valor, (int, float)) and not isinstance(valor, bool)
                and re.search(r"area", str(chave), re.IGNORECASE)):
            return round(float(valor) * escala_area, 4), chave
    return None, None


def _limpo(valor):
    if valor is None:
        return None
    s = str(valor).strip()
    return s or None


def _psets_do_espaco(sp: Any) -> dict:
    try:
        import ifcopenshell.util.element as ue
    except Exception:
        return {}
    try:
        conjuntos = ue.get_psets(sp)
    except Exception:
        return {}
    achatado: dict[str, Any] = {}
    for props in (conjuntos or {}).values():
        for chave, valor in (props or {}).items():
            if chave != "id":
                achatado.setdefault(chave, valor)
    return achatado


def _cli() -> None:
    import argparse
    import json

    import ifcopenshell
    p = argparse.ArgumentParser(description="Lista os ambientes (IfcSpace) de um IFC.")
    p.add_argument("ifc")
    args = p.parse_args()
    modelo = ifcopenshell.open(args.ifc)
    print(json.dumps([a.to_dict() for a in listar(modelo)], ensure_ascii=False, indent=2))


def medir(modelo: Any, global_ids: list[str]) -> dict[str, dict]:
    """Mede largura/comprimento de planta dos IfcSpace pedidos."""
    resultado: dict[str, dict] = {}
    if modelo is None or not global_ids:
        return resultado

    alvo = set(global_ids)
    try:
        from ifcopenshell import geom
        settings = geom.settings()
    except Exception as exc:
        return {gid: {"erro": f"geometria indisponível ({exc!r})"} for gid in alvo}

    try:
        espacos = [sp for sp in modelo.by_type("IfcSpace")
                   if getattr(sp, "GlobalId", None) in alvo]
    except Exception as exc:
        return {gid: {"erro": f"falha ao listar IfcSpace ({exc!r})"} for gid in alvo}

    for sp in espacos:
        gid = sp.GlobalId
        try:
            shape = geom.create_shape(settings, sp)
            g = shape.geometry
            resultado[gid] = _medidas_footprint(list(g.verts), list(g.faces))
        except Exception as exc:
            resultado[gid] = {"erro": f"falha na geometria ({type(exc).__name__}: {exc})"}

    for gid in alvo - set(resultado):
        resultado[gid] = {"erro": "IfcSpace não encontrado no modelo"}
    return resultado


def _medidas_footprint(verts: list[float], faces: list[int]) -> dict:
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    if not verts or not faces:
        return {"erro": "geometria vazia"}

    triangulos = []
    for i in range(0, len(faces), 3):
        pts = []
        for k in range(3):
            j = faces[i + k] * 3
            pts.append((verts[j], verts[j + 1]))
        tri = Polygon(pts)
        if tri.is_valid and tri.area > 1e-9:
            triangulos.append(tri)
    if not triangulos:
        return {"erro": "footprint degenerado (sem triângulos válidos em planta)"}

    footprint = unary_union(triangulos).buffer(0)
    if footprint.is_empty:
        return {"erro": "footprint vazio após a união"}
    if footprint.geom_type == "MultiPolygon":
        footprint = max(footprint.geoms, key=lambda p: p.area)

    ret = footprint.minimum_rotated_rectangle
    coords = list(ret.exterior.coords)
    lado_a = _dist(coords[0], coords[1])
    lado_b = _dist(coords[1], coords[2])
    largura, comprimento = sorted((lado_a, lado_b))

    return {
        "largura_m": round(largura, 3),
        "comprimento_m": round(comprimento, 3),
        "area_footprint_m2": round(footprint.area, 2),
        "metodo": METODO,
    }


def _dist(a: tuple, b: tuple) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


# ---------------------------------------------------------------------------
# Triagem da população (ADR-031)
# ---------------------------------------------------------------------------
#
# Três sinais, e um ambiente só sai da população com DOIS ou mais. Nenhum
# sinal basta sozinho, e cada um por um motivo medido nos 12 arquivos da
# escada do Estrela I:
#   * a sobreposição (S1) é a assinatura mais forte no IFC4, mas o exportador
#     IFC2X3 do Revit põe todo IfcSpace do pavimento no mesmo ponto de
#     inserção (41 ambientes legítimos no D1);
#   * a divergência pegada × área (S2) tem folga grande (pior legítimo 1,0026)
#     e não pega o fantasma mais discreto (Cozinha, 1,09);
#   * a caixa padrão (S3) é convenção de um exportador só.

SOBREPOSICAO = "sobreposicao_no_pavimento"
PEGADA_X_AREA = "pegada_diverge_da_area"
CAIXA_PADRAO = "caixa_padrao_do_exportador"

ROTULO_SINAL = {
    SOBREPOSICAO: "ponto de inserção coincidente com outro ambiente do mesmo pavimento",
    PEGADA_X_AREA: "pegada incompatível com a área declarada",
    CAIXA_PADRAO: "pegada igual à caixa padrão do exportador (6' × 8')",
}

SINAIS_MINIMOS = 2
FATOR_DIVERGENCIA = 1.10               # maior/menor entre pegada e área declarada
CAIXA_PADRAO_M = (1.829, 2.438)        # 6' × 8' em metros (largura, comprimento)
TOLERANCIA_CAIXA_M = 0.005
_CASAS_PONTO = 3                        # coincidência exata, a menos de arredondamento


@dataclass(frozen=True)
class Triagem:
    """O que as regras avaliam (``populacao``) e o que ficou fora (``fora``).

    ``fora`` traz um dicionário por ambiente retirado, com os sinais e os
    números de cada um, para o relatório. ``medidas`` é a geometria de todos
    os ``IfcSpace``, calculada uma vez, para que as regras dimensionais não
    meçam de novo.
    """

    populacao: list = field(default_factory=list)
    fora: list = field(default_factory=list)
    medidas: dict = field(default_factory=dict)

    def nota(self) -> str:
        """A frase que a mensagem da regra acrescenta, ou ``""``."""
        if not self.fora:
            return ""
        return (f" {len(self.fora)} ambiente(s) deixados de fora por parecerem "
                "erro de exportação do modelo: "
                + "; ".join(a["nome"] for a in self.fora) + ".")


def triar(modelo: Any) -> Triagem:
    """Separa a população avaliável dos ambientes fantasma (ADR-031)."""
    ambientes = listar(modelo)
    if not ambientes:
        return Triagem()
    medidas = medir(modelo, [a.global_id for a in ambientes]) or {}
    posicoes = _posicoes(modelo)
    registros = [(a, medidas.get(a.global_id) or {}, posicoes.get(a.global_id))
                 for a in ambientes]
    sinais = sinais_de_fantasma(registros)

    populacao, fora = [], []
    for a, m, _ in registros:
        achados = sinais.get(a.global_id, {})
        if len(achados) >= SINAIS_MINIMOS:
            fora.append({
                "global_id": a.global_id, "nome": a.nome,
                "area_declarada_m2": a.area_m2,
                "area_footprint_m2": m.get("area_footprint_m2"),
                "largura_m": m.get("largura_m"),
                "comprimento_m": m.get("comprimento_m"),
                "sinais": sorted(achados),
                "causa": "; ".join(ROTULO_SINAL[k] for k in sorted(achados)),
                "valores": achados,
            })
        else:
            populacao.append(a)
    return Triagem(populacao=populacao, fora=fora, medidas=medidas)


def sinais_de_fantasma(registros) -> dict[str, dict]:
    """``{global_id: {sinal: valor}}`` para cada ambiente com algum sinal.

    ``registros`` é uma sequência de ``(Ambiente, medida, posicao)``: a medida
    vem de ``medir`` (pode trazer ``erro``) e a posição é
    ``(pavimento, ponto, pai)`` ou ``None``. Lógica pura, sem IfcOpenShell.
    """
    ocupacao: dict[tuple, int] = {}
    for _, _, pos in registros:
        if pos is not None:
            ocupacao[pos] = ocupacao.get(pos, 0) + 1

    sinais: dict[str, dict] = {}
    for a, m, pos in registros:
        achados: dict[str, Any] = {}
        if pos is not None and ocupacao[pos] > 1:
            achados[SOBREPOSICAO] = {"pavimento": pos[0], "ponto": list(pos[1]),
                                     "ambientes_no_ponto": ocupacao[pos]}
        pegada = m.get("area_footprint_m2")
        declarada = a.area_m2
        if (isinstance(pegada, (int, float)) and isinstance(declarada, (int, float))
                and pegada > 0 and declarada > 0):
            razao = max(pegada, declarada) / min(pegada, declarada)
            if razao > FATOR_DIVERGENCIA:
                achados[PEGADA_X_AREA] = {"razao": round(razao, 4),
                                          "fator": FATOR_DIVERGENCIA}
        largura, comprimento = m.get("largura_m"), m.get("comprimento_m")
        if (isinstance(largura, (int, float)) and isinstance(comprimento, (int, float))
                and abs(largura - CAIXA_PADRAO_M[0]) <= TOLERANCIA_CAIXA_M
                and abs(comprimento - CAIXA_PADRAO_M[1]) <= TOLERANCIA_CAIXA_M):
            achados[CAIXA_PADRAO] = {"largura_m": largura, "comprimento_m": comprimento}
        if achados:
            sinais[a.global_id] = achados
    return sinais


def _posicoes(modelo: Any) -> dict[str, tuple]:
    """``{global_id: (pavimento, ponto, pai)}`` dos ``IfcSpace`` com pavimento e ponto.

    O ponto é a origem do ``ObjectPlacement`` do espaço, relativa ao
    posicionamento-pai. Dois ambientes do mesmo pavimento só coincidem se
    compartilham pai e ponto. Lido por ``getattr``, sem
    ``ifcopenshell.util``, para funcionar também com o dublê dos testes.
    """
    try:
        espacos = list(modelo.by_type("IfcSpace"))
    except Exception:
        return {}
    posicoes = {}
    for sp in espacos:
        pavimento = _pavimento(sp)
        ponto = _ponto_de_insercao(sp)
        if pavimento is None or ponto is None:
            continue
        pai = getattr(getattr(sp, "ObjectPlacement", None), "PlacementRelTo", None)
        posicoes[getattr(sp, "GlobalId", "")] = (pavimento, ponto, _chave(pai))
    return posicoes


def _chave(entidade: Any):
    """Identidade estável de uma entidade: o número STEP (``#id``) quando há.

    O IfcOpenShell cria um invólucro Python novo a cada acesso de atributo, e
    o ``id()`` do invólucro não identifica a entidade. O dublê não tem número
    STEP, e aí vale o próprio objeto. A chave só separa pais diferentes e não
    vai para o relatório.
    """
    if entidade is None:
        return None
    try:
        return ("step", entidade.id())
    except Exception:
        return ("obj", id(entidade))


def _pavimento(sp: Any) -> str | None:
    """Nome (ou GlobalId) do pavimento que agrega ou contém o espaço."""
    for rel in (getattr(sp, "Decomposes", None) or ()):
        dono = getattr(rel, "RelatingObject", None)
        if dono is not None:
            return getattr(dono, "Name", None) or getattr(dono, "GlobalId", None)
    for rel in (getattr(sp, "ContainedInStructure", None) or ()):
        dono = getattr(rel, "RelatingStructure", None)
        if dono is not None:
            return getattr(dono, "Name", None) or getattr(dono, "GlobalId", None)
    return None


def _ponto_de_insercao(sp: Any) -> tuple | None:
    try:
        coords = sp.ObjectPlacement.RelativePlacement.Location.Coordinates
        return tuple(round(float(c), _CASAS_PONTO) for c in coords)
    except Exception:
        return None
