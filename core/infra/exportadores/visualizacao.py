"""Artefatos de visualização (passo 4): produção (lenta) e consumo (rápido).

Duas responsabilidades, deliberadamente separadas para desacoplar a **análise**
da **visualização 3D**:

* :func:`gerar_artefatos` — parte **lenta** (IFC -> GLB -> tileset). Escreve os
  artefatos abertos em ``pasta_tiles`` (``modelo.glb`` + ``tileset.json`` +
  ``ancora.json``) e um ``status.json`` com o estado do job. É o que roda em
  segundo plano, disparado após a exibição do resultado da análise. Só escreve
  em disco: não conhece Streamlit nem toca em estado de sessão (seguro para
  rodar numa thread sem ``ScriptRunContext``).
* :func:`carregar_payload` — parte **rápida**. Lê os artefatos do disco e monta
  o pacote que a página dedicada consome (GLB em base64 + transform ECEF,
  ambientes do ``espacos.json`` e caixas do ``revestimentos.json``).

A comunicação núcleo <-> visualização permanece pelos artefatos em disco, como
descrito no README ("desacoplado por artefatos em formatos abertos").

``gerar_payload`` é mantida como conveniência (produz e carrega numa chamada só)
para uso em scripts e testes.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
from typing import Any

_log = logging.getLogger(__name__)

_ARQ_STATUS = "status.json"
_ARQ_ANCORA = "ancora.json"
_ARQ_ESPACOS = "espacos.json"
_ARQ_REVESTIMENTOS = "revestimentos.json"
# Teto de triângulos por ambiente para embutir a malha no espacos.json
# (ambientes são prismas simples; acima disso, cai no realce por centro/raio).
_MAX_TRI_MALHA = 4000


# ---------------------------------------------------------------------------
# Estado do job de conversão (contrato em disco)
# ---------------------------------------------------------------------------

def _caminho_status(pasta_tiles: str) -> str:
    return os.path.join(pasta_tiles, _ARQ_STATUS)


def escrever_status(pasta_tiles: str, *, estado: str, job_id: str | None = None,
                    posicionavel: bool | None = None, erro: str | None = None) -> dict:
    """Grava ``pasta_tiles/status.json`` com o estado atual da conversão.

    ``estado`` é um de ``processando`` | ``pronto`` | ``erro``. ``job_id`` casa o
    status com a análise corrente (evita exibir tiles de uma análise anterior).
    """
    os.makedirs(pasta_tiles, exist_ok=True)
    dados = {
        "estado": estado,
        "job_id": job_id,
        "posicionavel": posicionavel,
        "erro": erro,
        "atualizado_em": time.time(),
    }
    with open(_caminho_status(pasta_tiles), "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    return dados


def ler_status(pasta_tiles: str) -> dict:
    """Lê o status da conversão; devolve ``{estado: 'ausente'}`` se não houver."""
    try:
        with open(_caminho_status(pasta_tiles), "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"estado": "ausente", "job_id": None}


# ---------------------------------------------------------------------------
# Produção (lenta) — roda em segundo plano
# ---------------------------------------------------------------------------

def gerar_artefatos(caminho_ifc: str, pasta_tiles: str, *, job_id: str | None = None,
                    nome: str = "modelo", excluir_tipos=None, incluir_tipos=None,
                    ancora_manual: dict | None = None) -> dict:
    """Produz GLB + tileset em ``pasta_tiles`` e atualiza o ``status.json``.

    Parte cara do fluxo (iteração de geometria do IfcOpenShell). Ao final grava
    o estado ``pronto`` (ou ``erro``, repropagando a exceção). Persiste também a
    âncora em ``ancora.json`` para restaurar a legenda na página dedicada.
    ``ancora_manual`` é o fallback de posicionamento aproximado — só é usada
    quando o modelo não tem âncora derivável (ver exportador_3dtiles.exportar).
    """
    from core.infra.exportadores import tiles3d as t3d

    try:
        res = t3d.exportar(caminho_ifc, pasta_tiles, nome=nome,
                           excluir_tipos=excluir_tipos, incluir_tipos=incluir_tipos,
                           ancora_manual=ancora_manual)
        if res.get("ancora"):
            with open(os.path.join(pasta_tiles, _ARQ_ANCORA), "w", encoding="utf-8") as f:
                json.dump(res["ancora"], f, ensure_ascii=False)
        _gravar_espacos(caminho_ifc, pasta_tiles)
        _gravar_revestimentos(caminho_ifc, pasta_tiles, nome=nome)
        escrever_status(pasta_tiles, estado="pronto", job_id=job_id,
                        posicionavel=res.get("tileset") is not None)
        return res
    except Exception as exc:
        escrever_status(pasta_tiles, estado="erro", job_id=job_id, erro=str(exc))
        raise


def _gravar_espacos(caminho_ifc: str, pasta_tiles: str) -> None:
    """Persiste a lista de ambientes (IfcSpace) para a cena ocultá-los/realçá-los.

    Escrito sempre na conversão, independentemente das regras selecionadas: a
    cena usa esta lista para ocultar os volumes de espaço por padrão (mantendo a
    visão limpa) e para o destaque por clique no relatório de ambientes.
    """
    try:
        import ifcopenshell

        from core.infra.ifc import extrator_ambientes as leitor_ambientes
        modelo = ifcopenshell.open(caminho_ifc)
        geo = _geometria_espacos(modelo)  # {global_id: {center, raio}} em metros (frame local)
        espacos = []
        for a in leitor_ambientes.listar(modelo):
            item = {"global_id": a.global_id, "nome": a.nome, "area_m2": a.area_m2}
            item.update(geo.get(a.global_id, {}))  # center/raio quando houver geometria
            espacos.append(item)
        with open(os.path.join(pasta_tiles, _ARQ_ESPACOS), "w", encoding="utf-8") as f:
            json.dump(espacos, f, ensure_ascii=False)
    except Exception:  # nunca derruba a conversão por causa da lista de espaços
        pass


def _gravar_revestimentos(caminho_ifc: str, pasta_tiles: str, *,
                          nome: str = "modelo") -> None:
    """Persiste a caixa de cada ``IfcCovering`` para o destaque na cena.

    A caixa sai do GLB que a conversão acabou de gravar, não de uma nova
    passada de geometria: é o mín./máx. do acessor ``POSITION`` do nó que
    leva o ``GlobalId`` do revestimento, já no frame local z-up do IFC (o
    mesmo dos centros do ``espacos.json``). O arquivo carrega geometria para
    exibir, nunca julgamento: a cor de cada caixa vem da ``situacao`` que o
    relatório gravou (ADR-001). Como a lista de espaços,
    nunca derruba a conversão; sem o arquivo, a cena fica sem destaque.
    """
    try:
        import ifcopenshell

        modelo = ifcopenshell.open(caminho_ifc)
        nomes = {c.GlobalId: (getattr(c, "Name", None) or "")
                 for c in modelo.by_type("IfcCovering")
                 if getattr(c, "GlobalId", None)}
        caixas = caixas_do_glb(os.path.join(pasta_tiles, f"{nome}.glb"), set(nomes))
        itens = [{"global_id": gid, "nome": nomes.get(gid, ""), **cx}
                 for gid, cx in sorted(caixas.items())]
        with open(os.path.join(pasta_tiles, _ARQ_REVESTIMENTOS), "w",
                  encoding="utf-8") as f:
            json.dump(itens, f, ensure_ascii=False)
    except Exception:
        _log.debug("destaque 3D: revestimentos não gravados", exc_info=True)


def caixas_do_glb(caminho_glb: str, global_ids: set[str]) -> dict[str, dict]:
    """``{GlobalId: {min, max, espessura}}`` dos nós do GLB com esses nomes.

    Lê só o bloco JSON do GLB: o glTF exige ``min``/``max`` no acessor
    ``POSITION``, então a caixa não precisa dos vértices (o telhado do E3 tem
    milhões de triângulos). Um nó com várias primitivas une as caixas.
    ``espessura`` é a menor dimensão da caixa (informativa).
    """
    import struct

    if not global_ids:
        return {}
    with open(caminho_glb, "rb") as f:
        cabecalho = f.read(20)
        if cabecalho[:4] != b"glTF":
            return {}
        tamanho = struct.unpack("<I", cabecalho[12:16])[0]
        gltf = json.loads(f.read(tamanho))
    acessores = gltf.get("accessors") or []
    malhas = gltf.get("meshes") or []
    caixas: dict[str, dict] = {}
    for no in gltf.get("nodes") or []:
        gid = no.get("name")
        if gid not in global_ids or "mesh" not in no:
            continue
        mins, maxs = [], []
        for prim in malhas[no["mesh"]].get("primitives") or []:
            a = acessores[prim["attributes"]["POSITION"]]
            if "min" in a and "max" in a:
                mins.append(a["min"])
                maxs.append(a["max"])
        if not mins:
            continue
        mn = [round(min(m[i] for m in mins), 4) for i in range(3)]
        mx = [round(max(m[i] for m in maxs), 4) for i in range(3)]
        caixas[gid] = {"min": mn, "max": mx,
                       "espessura": round(min(mx[i] - mn[i] for i in range(3)), 4)}
    return caixas


def _geometria_espacos(modelo) -> dict:
    """Centro e raio (esfera envolvente) de cada IfcSpace, em metros, frame local.

    Coordenadas na convenção z-up do IFC — a mesma que o CesiumJS obtém após
    converter o GLB (y-up) de volta para z-up antes de aplicar a matriz ECEF —,
    de modo que ``modelMatrix * center`` posicione a esfera de destaque sobre o
    ambiente. Espaços sem geometria são omitidos (ficam sem zoom/realce).
    """
    resultado: dict = {}
    try:
        from ifcopenshell import geom
        # ``create_shape`` devolve geometria em METROS (SI), qualquer que seja a
        # unidade de comprimento do arquivo — portanto NÃO se reescala aqui.
        settings = geom.settings()
        try:
            settings.set("use-world-coords", True)      # ifcopenshell 0.8 (string)
        except Exception:
            try:
                settings.set(geom.settings.USE_WORLD_COORDS, True)  # fallback (enum)
            except Exception:
                pass
        for sp in modelo.by_type("IfcSpace"):
            try:
                # IMPORTANTE: manter ``shape`` vivo enquanto se lê ``verts``. O
                # buffer de ``geometry.verts`` é liberado junto com o shape; usar
                # ``create_shape(...).geometry.verts`` como temporário devolve
                # lixo (memória liberada). Materializamos os vértices em floats
                # Python enquanto o shape está referenciado.
                shape = geom.create_shape(settings, sp)
                v = shape.geometry.verts
                f = shape.geometry.faces
                if not v or len(v) < 3:
                    continue
                xs = [float(v[i]) for i in range(0, len(v), 3)]
                ys = [float(v[i]) for i in range(1, len(v), 3)]
                zs = [float(v[i]) for i in range(2, len(v), 3)]
                cx = (min(xs) + max(xs)) / 2
                cy = (min(ys) + max(ys)) / 2
                cz = (min(zs) + max(zs)) / 2
                raio = max((max(xs) - min(xs)), (max(ys) - min(ys)),
                           (max(zs) - min(zs))) / 2
                gid = getattr(sp, "GlobalId", "")
                if not gid:
                    continue
                item = {"center": [round(cx, 4), round(cy, 4), round(cz, 4)],
                        "raio": round(max(raio, 0.5), 3)}
                # Malha triangulada do ambiente (vértices já em metros + índices),
                # para recriar o volume exato na cena. Materializada com o shape
                # vivo; omitida se for grande demais para o payload.
                n_tri = len(f) // 3
                if 0 < n_tri <= _MAX_TRI_MALHA:
                    item["mesh"] = {
                        "verts": [round(float(v[i]), 3) for i in range(len(v))],
                        "faces": [int(f[i]) for i in range(len(f))],
                    }
                resultado[gid] = item
            except Exception:
                _log.debug("destaque 3D: ambiente %s ignorado", gid, exc_info=True)
                continue
    except Exception:
        pass
    return resultado


# ---------------------------------------------------------------------------
# Consumo (rápido) — a página dedicada lê os artefatos do disco
# ---------------------------------------------------------------------------

def carregar_payload(pasta_tiles: str, *, nome: str = "modelo",
                     embutir_glb: bool = True) -> dict[str, Any]:
    """Lê os artefatos e devolve ``{glb_b64, transform, ancora, posicionavel}``.

    ``posicionavel`` é False quando não há tileset (sem âncora derivável) ou
    quando os artefatos ainda não existem. Com ``embutir_glb=False`` o GLB
    não é lido: o payload traz ``glb_caminho`` para quem o entrega à parte
    (um GLB de 170 MB em base64 passa dos 200 MB que o servidor do app
    entrega por arquivo; ADR-001).
    """
    glb_path = os.path.join(pasta_tiles, f"{nome}.glb")
    if not os.path.exists(glb_path):
        return {"glb_b64": None, "transform": None, "ancora": None,
                "posicionavel": False, "erro": "artefatos de visualizacao ausentes"}

    glb_b64 = None
    if embutir_glb:
        with open(glb_path, "rb") as f:
            glb_b64 = base64.b64encode(f.read()).decode("ascii")

    transform = None
    tileset_path = os.path.join(pasta_tiles, "tileset.json")
    if os.path.exists(tileset_path):
        with open(tileset_path, "r", encoding="utf-8") as f:
            transform = json.load(f)["root"]["transform"]

    ancora = None
    ancora_path = os.path.join(pasta_tiles, _ARQ_ANCORA)
    if os.path.exists(ancora_path):
        try:
            with open(ancora_path, "r", encoding="utf-8") as f:
                ancora = json.load(f)
        except json.JSONDecodeError:
            ancora = None

    espacos = []
    espacos_path = os.path.join(pasta_tiles, _ARQ_ESPACOS)
    if os.path.exists(espacos_path):
        try:
            with open(espacos_path, "r", encoding="utf-8") as f:
                espacos = json.load(f) or []
        except json.JSONDecodeError:
            espacos = []

    # Ausente em conversão antiga: a cena segue, sem destaque (ADR-001).
    revestimentos = []
    revestimentos_path = os.path.join(pasta_tiles, _ARQ_REVESTIMENTOS)
    if os.path.exists(revestimentos_path):
        try:
            with open(revestimentos_path, "r", encoding="utf-8") as f:
                revestimentos = json.load(f) or []
        except json.JSONDecodeError:
            revestimentos = []

    return {
        "glb_b64": glb_b64,
        "glb_caminho": glb_path,
        "transform": transform,
        "ancora": ancora,
        "espacos": espacos,
        "revestimentos": revestimentos,
        "posicionavel": transform is not None,
    }


# ---------------------------------------------------------------------------
# Conveniência: produz e carrega numa chamada só (scripts e testes)
# ---------------------------------------------------------------------------

def gerar_payload(caminho_ifc: str, pasta_tiles: str, *, nome: str = "modelo",
                  excluir_tipos=None, incluir_tipos=None) -> dict[str, Any]:
    """Gera os artefatos e devolve o payload já carregado (fluxo síncrono)."""
    gerar_artefatos(caminho_ifc, pasta_tiles, nome=nome,
                    excluir_tipos=excluir_tipos, incluir_tipos=incluir_tipos)
    return carregar_payload(pasta_tiles, nome=nome)


# ---------------------------------------------------------------------------
# CLI — a conversão como processo próprio
# ---------------------------------------------------------------------------

def _cli() -> None:
    """Roda a conversão de um IFC para a pasta de tiles indicada.

    É por aqui que o app dispara a conversão em PROCESSO separado (ver
    `app/servicos/conversao_3d.py`): dentro do processo do Streamlit, a
    iteração de geometria disputava o GIL e congelava a interface. O contrato
    com quem chama continua sendo o ``status.json`` (ADR-001): `gerar_artefatos`
    grava ``pronto`` ou ``erro`` — inclusive quando esta CLI sai com código 1.
    """
    import argparse

    p = argparse.ArgumentParser(
        description="Converte um modelo IFC para visualização (GLB + 3D Tiles).")
    p.add_argument("ifc", help="Caminho do modelo IFC.")
    p.add_argument("pasta_tiles", help="Pasta de saída dos artefatos da checagem.")
    p.add_argument("--job-id", default=None, help="Identidade do job (status.json).")
    p.add_argument("--excluir", default="",
                   help="Tipos IFC a excluir da cena, separados por vírgula.")
    p.add_argument("--ancora", default=None,
                   help="JSON do posicionamento manual (fallback sem âncora derivável).")
    args = p.parse_args()

    excluir = [t for t in args.excluir.split(",") if t.strip()] or None
    ancora = json.loads(args.ancora) if args.ancora else None
    try:
        gerar_artefatos(args.ifc, args.pasta_tiles, job_id=args.job_id,
                        excluir_tipos=excluir, ancora_manual=ancora)
    except Exception:
        raise SystemExit(1)  # o status 'erro' já foi gravado por gerar_artefatos


if __name__ == "__main__":
    _cli()
