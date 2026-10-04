"""Malha municipal (IBGE) — confronto ponto × município declarado.

Verifica se um ponto (lat/lon WGS 84 — a âncora do modelo) está dentro dos
limites oficiais do município declarado pelo usuário. A geometria vem da API
de malhas do IBGE, baixada SOB DEMANDA na primeira análise e cacheada em
disco (``artefatos/cache/malhas/<codigo>.geojson``); nas análises seguintes o
cache é usado, sem rede.

Decisões:
  * ponto-dentro-do-polígono (Shapely, já dependência) contra a malha oficial
    — preciso e leve (um GeoJSON por município);
  * sem rede e sem cache, o confronto NÃO é avaliado (``dentro=None``) — o
    EMP-001 reporta "conforme com ressalva" quando o LoGeoRef 50 foi atingido.
"""

from __future__ import annotations

import gzip
import json
import os
import urllib.request
import zlib
from dataclasses import dataclass

URL_MALHA = ("https://servicodados.ibge.gov.br/api/v3/malhas/municipios/"
             "{codigo}?formato=application/vnd.geo+json")
PASTA_CACHE = os.path.join("artefatos", "cache", "malhas")


@dataclass
class ResultadoMalha:
    dentro: bool | None = None   # True/False = confrontado; None = não avaliado
    fonte: str = ""              # "cache" | "download" | "" (indisponível)
    mensagem: str = ""

    def to_dict(self) -> dict:
        return {"dentro": self.dentro, "fonte": self.fonte, "mensagem": self.mensagem}


def conferir_ponto(codigo_ibge: str, lat: float, lon: float,
                   pasta_cache: str = PASTA_CACHE,
                   timeout: int = 20) -> ResultadoMalha:
    """Confronta o ponto com a malha do município (cache -> download -> None)."""
    geojson, fonte, erro = _obter_malha(str(codigo_ibge).strip(), pasta_cache, timeout)
    if geojson is None:
        return ResultadoMalha(mensagem=f"Malha municipal indisponível ({erro}); "
                                       "confronto não avaliado.")
    try:
        dentro = _ponto_no_geojson(geojson, lat, lon)
    except Exception as exc:
        return ResultadoMalha(mensagem=f"Falha ao processar a malha ({exc!r}); "
                                       "confronto não avaliado.")
    situ = "dentro" if dentro else "fora"
    return ResultadoMalha(dentro=dentro, fonte=fonte,
                          mensagem=f"Âncora do modelo {situ} dos limites do "
                                   f"município (malha IBGE, {fonte}).")


def malha_em_cache(codigo_ibge: str, pasta_cache: str = PASTA_CACHE) -> dict | None:
    """Devolve o GeoJSON do município se já estiver no cache (sem rede).

    Usado pela camada de visualização para desenhar os limites municipais na
    cena — a análise (conferir_ponto) é quem baixa e alimenta o cache.
    """
    caminho = os.path.join(pasta_cache, f"{str(codigo_ibge).strip()}.geojson")
    if not os.path.exists(caminho):
        return None
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def centro_municipio(codigo_ibge: str, pasta_cache: str = PASTA_CACHE,
                     timeout: int = 20) -> tuple[float, float] | None:
    """Centroide (lat, lon) do município — default do posicionamento manual.

    Usa o cache quando existe; senão tenta baixar a malha (e cacheia). Devolve
    ``None`` se a malha estiver indisponível (ex.: sem rede).
    """
    geojson, _, _ = _obter_malha(str(codigo_ibge).strip(), pasta_cache, timeout)
    if geojson is None:
        return None
    try:
        from shapely.geometry import shape
        from shapely.ops import unary_union
        if geojson.get("type") == "FeatureCollection":
            geoms = [shape(f["geometry"]) for f in geojson.get("features", [])
                     if f.get("geometry")]
        elif geojson.get("type") == "Feature":
            geoms = [shape(geojson["geometry"])]
        else:
            geoms = [shape(geojson)]
        c = unary_union(geoms).centroid
        return (float(c.y), float(c.x))  # (lat, lon)
    except Exception:
        return None


def _obter_malha(codigo: str, pasta_cache: str, timeout: int):
    """Devolve (geojson, fonte, erro): tenta o cache em disco e, depois, a API."""
    caminho = os.path.join(pasta_cache, f"{codigo}.geojson")
    if os.path.exists(caminho):
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                return json.load(f), "cache", ""
        except Exception:
            pass  # cache corrompido: tenta baixar de novo

    url = URL_MALHA.format(codigo=codigo)
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "prototipo-mcmv/1.0",
            "Accept": "application/vnd.geo+json, application/json",
            "Accept-Encoding": "gzip",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            bruto = resp.read()
            codif = (resp.headers.get("Content-Encoding") or "").lower()
        geojson = json.loads(_descomprimir(bruto, codif).decode("utf-8"))
    except Exception as exc:
        return None, "", f"{type(exc).__name__}: {exc}"

    try:
        os.makedirs(pasta_cache, exist_ok=True)
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(geojson, f, ensure_ascii=False)
    except Exception:
        pass  # cache é otimização; a análise segue com o download em memória
    return geojson, "download", ""


def _descomprimir(bruto: bytes, codificacao: str) -> bytes:
    """Trata respostas comprimidas (a CDN do IBGE pode comprimir mesmo sem
    Accept-Encoding — o urllib não descomprime sozinho)."""
    if "gzip" in codificacao or bruto[:2] == b"\x1f\x8b":
        return gzip.decompress(bruto)
    if "deflate" in codificacao:
        try:
            return zlib.decompress(bruto)
        except zlib.error:
            return zlib.decompress(bruto, -zlib.MAX_WBITS)  # deflate "cru"
    return bruto


def _ponto_no_geojson(geojson: dict, lat: float, lon: float) -> bool:
    """Ponto-dentro-do-polígono sobre as feições do GeoJSON (WGS 84, lon/lat)."""
    from shapely.geometry import Point, shape
    from shapely.ops import unary_union

    if geojson.get("type") == "FeatureCollection":
        geoms = [shape(f["geometry"]) for f in geojson.get("features", [])
                 if f.get("geometry")]
    elif geojson.get("type") == "Feature":
        geoms = [shape(geojson["geometry"])]
    else:
        geoms = [shape(geojson)]
    if not geoms:
        raise ValueError("GeoJSON sem geometria")

    municipio = unary_union(geoms)
    # ``covers`` inclui a fronteira (ponto exatamente no limite conta como dentro).
    return bool(municipio.covers(Point(float(lon), float(lat))))
