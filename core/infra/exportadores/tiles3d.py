"""Empacotamento em 3D Tiles (passo 3 da visualização).

Junta a geometria (GLB, passo 1) com a âncora geográfica (passo 2) num
``tileset.json`` (3D Tiles 1.1) que o CesiumJS carrega e posiciona no globo.

O posicionamento é feito por um `transform` 4x4 (coluna-maior) que leva o
referencial local do modelo para o ECEF (Earth-Centered, Earth-Fixed) no ponto
da âncora, orientado pelo referencial Leste-Norte-Cima (ENU) e girado pela
rotação do modelo. O GLB é Y-up (convenção glTF); o CesiumJS faz a conversão
Y-up -> Z-up do conteúdo antes de aplicar o transform.

Não toca no IFC. Consome apenas GLB + âncora (artefatos abertos).
"""

from __future__ import annotations

import json
import math
import os
import struct

# ---------------------------------------------------------------------------
# Transform ENU -> ECEF
# ---------------------------------------------------------------------------

def transform_ecef(lon: float, lat: float, altura: float = 0.0,
                   rotacao_graus: float = 0.0) -> list[float]:
    """Matriz 4x4 (coluna-maior, 16 floats) que posiciona o modelo no ECEF.

    Colunas: eixo X do modelo, eixo Y, eixo Z (=cima) e a origem, todos em ECEF.
    A rotação gira os eixos X/Y do modelo em torno do eixo vertical (Cima), no
    sentido anti-horário a partir do Leste.
    """
    ox, oy, oz = _geodetico_para_ecef(lon, lat, altura)

    rlon, rlat = math.radians(lon), math.radians(lat)
    sl, cl = math.sin(rlon), math.cos(rlon)
    sf, cf = math.sin(rlat), math.cos(rlat)

    # Vetores do referencial Leste-Norte-Cima (ENU) expressos em ECEF.
    east = (-sl, cl, 0.0)
    north = (-sf * cl, -sf * sl, cf)
    up = (cf * cl, cf * sl, sf)

    th = math.radians(rotacao_graus)
    c, s = math.cos(th), math.sin(th)
    # Eixos do modelo (X horizontal girado th; Y a 90°; Z = cima).
    mx = tuple(c * e + s * n for e, n in zip(east, north))
    my = tuple(-s * e + c * n for e, n in zip(east, north))
    mz = up

    return [
        mx[0], mx[1], mx[2], 0.0,
        my[0], my[1], my[2], 0.0,
        mz[0], mz[1], mz[2], 0.0,
        ox, oy, oz, 1.0,
    ]


def _geodetico_para_ecef(lon: float, lat: float, altura: float) -> tuple[float, float, float]:
    """(lon, lat, h) WGS84 -> (X, Y, Z) ECEF, via pyproj quando disponível."""
    try:
        from pyproj import Transformer
        t = Transformer.from_crs("EPSG:4326", "EPSG:4978", always_xy=True)
        return t.transform(lon, lat, altura)
    except Exception:
        # Fallback analítico (elipsoide WGS84) caso o pyproj não esteja presente.
        a = 6378137.0
        e2 = 6.69437999014e-3
        rlon, rlat = math.radians(lon), math.radians(lat)
        n = a / math.sqrt(1 - e2 * math.sin(rlat) ** 2)
        x = (n + altura) * math.cos(rlat) * math.cos(rlon)
        y = (n + altura) * math.cos(rlat) * math.sin(rlon)
        z = (n * (1 - e2) + altura) * math.sin(rlat)
        return x, y, z


# ---------------------------------------------------------------------------
# Esfera envolvente a partir do GLB
# ---------------------------------------------------------------------------

def _raio_envolvente_do_glb(caminho_glb: str) -> float:
    """Raio de uma esfera centrada na origem local que contém toda a geometria.

    Usa os min/max dos acessores POSITION. Como é a distância à origem, o valor
    independe da conversão Y-up/Z-up (rotação em torno da origem preserva norma).
    """
    with open(caminho_glb, "rb") as f:
        data = f.read()
    if data[:4] != b"glTF":
        return 50.0
    clen = struct.unpack("<I", data[12:16])[0]
    js = json.loads(data[20:20 + clen].decode("utf-8"))

    raio = 0.0
    achou = False
    for mesh in js.get("meshes", []):
        for prim in mesh.get("primitives", []):
            idx = prim.get("attributes", {}).get("POSITION")
            if idx is None:
                continue
            acc = js.get("accessors", [])[idx]
            for vetor in (acc.get("min"), acc.get("max")):
                if vetor and len(vetor) >= 3:
                    achou = True
                    raio = max(raio, math.sqrt(sum(v * v for v in vetor[:3])))
    return raio if achou and raio > 0 else 50.0


# ---------------------------------------------------------------------------
# Geração do tileset
# ---------------------------------------------------------------------------

def gerar_tileset(caminho_glb: str, ancora: dict, destino_tileset: str) -> dict:
    """Gera o tileset.json referenciando ``caminho_glb`` posicionado pela âncora.

    ``ancora`` é o dicionário de :meth:`core.infra.ifc.georref.ancora.Ancora.to_dict`.
    O GLB deve estar na mesma pasta do tileset (uri relativo).
    """
    if not ancora or ancora.get("lat") is None or ancora.get("lon") is None:
        raise ValueError("Âncora sem coordenadas; não é possível posicionar o tileset.")

    transform = transform_ecef(
        float(ancora["lon"]), float(ancora["lat"]),
        float(ancora.get("altura") or 0.0), float(ancora.get("rotacao_graus") or 0.0),
    )
    raio = _raio_envolvente_do_glb(caminho_glb)

    tileset = {
        "asset": {"version": "1.1"},
        "geometricError": max(raio, 1.0),
        "root": {
            "transform": transform,
            "boundingVolume": {"sphere": [0.0, 0.0, 0.0, raio]},
            "geometricError": 0.0,
            "refine": "ADD",
            "content": {"uri": os.path.basename(caminho_glb)},
            "metadata": {"modo_ancora": ancora.get("modo"), "epsg": ancora.get("epsg")},
        },
    }

    os.makedirs(os.path.dirname(os.path.abspath(destino_tileset)), exist_ok=True)
    with open(destino_tileset, "w", encoding="utf-8") as f:
        json.dump(tileset, f, ensure_ascii=False, indent=2)
    return tileset


# ---------------------------------------------------------------------------
# Orquestrador IFC -> tiles (GLB + tileset na mesma pasta)
# ---------------------------------------------------------------------------

def exportar(caminho_ifc: str, pasta_destino: str, *, nome: str = "modelo",
             excluir_tipos=None, incluir_tipos=None,
             ancora_manual: dict | None = None) -> dict:
    """Gera ``pasta_destino/<nome>.glb`` + ``pasta_destino/tileset.json``.

    Retorna um resumo com os caminhos e a âncora utilizada.

    ``ancora_manual`` (opcional) é usada APENAS como fallback quando o modelo
    não tem âncora derivável (posicionamento aproximado informado pelo
    usuário na interface); nunca sobrepõe o georreferenciamento do modelo.
    """
    import ifcopenshell

    from core.infra.exportadores import gltf as exportador_gltf
    from core.infra.ifc.georref import ancora as mod_ancora

    os.makedirs(pasta_destino, exist_ok=True)
    glb = os.path.join(pasta_destino, f"{nome}.glb")
    exportador_gltf.exportar(caminho_ifc, glb, excluir_tipos=excluir_tipos,
                             incluir_tipos=incluir_tipos)

    modelo = ifcopenshell.open(caminho_ifc)
    ancora = mod_ancora.derivar(modelo).to_dict()
    if ancora.get("lat") is None and ancora_manual \
            and ancora_manual.get("lat") is not None:
        ancora = dict(ancora_manual)
        ancora.setdefault("modo", "manual")
        ancora.setdefault("mensagem", "Posicionamento aproximado informado "
                                      "pelo usuário (modelo sem georreferenciamento).")
    if ancora.get("lat") is None:
        return {"glb": glb, "tileset": None, "ancora": ancora,
                "aviso": "Âncora indisponível; posicionamento manual necessário (tileset não gerado)."}

    tileset_path = os.path.join(pasta_destino, "tileset.json")
    gerar_tileset(glb, ancora, tileset_path)
    return {"glb": glb, "tileset": tileset_path, "ancora": ancora}


def _cli() -> None:
    import argparse
    p = argparse.ArgumentParser(description="Empacota um IFC em 3D Tiles (GLB + tileset.json).")
    p.add_argument("ifc")
    p.add_argument("pasta", help="Pasta de destino dos artefatos (ex.: artefatos/tiles).")
    p.add_argument("--nome", default="modelo")
    p.add_argument("--excluir", nargs="*", default=None)
    p.add_argument("--incluir", nargs="*", default=None)
    args = p.parse_args()
    res = exportar(args.ifc, args.pasta, nome=args.nome,
                   excluir_tipos=args.excluir, incluir_tipos=args.incluir)
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _cli()
