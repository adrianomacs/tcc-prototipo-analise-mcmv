"""Gera o snapshot local de municípios brasileiros (config/municipios_ibge.csv).

Duas fontes do IBGE, dados abertos e sem autenticação:

1. **Lista de municípios** — API de localidades:
   https://servicodados.ibge.gov.br/api/v1/localidades/municipios?view=nivelado
2. **População e densidade do Censo Demográfico 2022** — API de agregados,
   SIDRA tabela 4714 ("População Residente, Área territorial e Densidade
   demográfica"), variáveis 93 (população residente) e 614 (densidade
   demográfica, hab/km²), referência 31/07/2022, os 5.570 municípios numa
   única chamada.

A população é a do **Censo**, nunca a estimativa anual (tabela 6579; indicador
29171 do Cidades@): o porte do município é fato censitário, estável e auditável
(ADR-030). Município instalado depois do Censo (hoje só Boa Esperança do
Norte/MT, 5101837) fica **sem população** — nunca com uma faixa chutada; a
regra que precisar do porte sai NÃO AVALIÁVEL.

Ao lado do CSV grava-se ``config/municipios_ibge.json``, a procedência: fontes,
URLs, tabela, variáveis, data de referência, data da geração e as contagens.

Decisão de arquitetura: a interface consome um snapshot
LOCAL (offline e reprodutível); atualizar a lista = rodar este script de novo.
Apenas biblioteca padrão (urllib), sem dependências novas.

Execução (na raiz do projeto):
    python scripts/gerar_municipios.py
"""

from __future__ import annotations

import csv
import gzip
import json
import os
import sys
import urllib.request
import zlib
from datetime import datetime, timezone

URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios?view=nivelado"
TABELA_CENSO = "4714"
VARIAVEL_POPULACAO = "93"
VARIAVEL_DENSIDADE = "614"
URL_CENSO = ("https://servicodados.ibge.gov.br/api/v3/agregados/"
             f"{TABELA_CENSO}/periodos/2022/variaveis/"
             f"{VARIAVEL_POPULACAO}%7C{VARIAVEL_DENSIDADE}"
             "?localidades=N6%5Ball%5D")
REFERENCIA_CENSO = "2022-07-31"
DESTINO = os.path.join("config", "municipios_ibge.csv")
CAMPOS = ["codigo_ibge", "nome", "uf", "uf_nome",
          "populacao_2022", "densidade_2022"]


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
    if "br" in codificacao:
        raise RuntimeError("resposta em Brotli ('br') — tente novamente; se "
                           "persistir, instale 'brotli' e adapte o script")
    return bruto


def _baixar_json(url: str):
    req = urllib.request.Request(url, headers={
        "User-Agent": "prototipo-mcmv/1.0",
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
    })
    with urllib.request.urlopen(req, timeout=180) as resp:
        bruto = resp.read()
        codificacao = (resp.headers.get("Content-Encoding") or "").lower()
    return json.loads(_descomprimir(bruto, codificacao).decode("utf-8"))


def baixar(url: str = URL) -> list[dict]:
    """A lista de municípios da API de localidades."""
    linhas = []
    for item in _baixar_json(url):
        linhas.append({
            "codigo_ibge": str(item["municipio-id"]),
            "nome": item["municipio-nome"],
            "uf": item["UF-sigla"],
            "uf_nome": item["UF-nome"],
        })
    return linhas


def series_do_censo(dados: list[dict]) -> dict[str, dict[str, str]]:
    """``{variavel: {codigo_ibge: valor}}`` a partir da resposta de agregados.

    O valor fica como o IBGE o escreve (texto, ponto decimal); célula sem
    número (``-``, ``...``, ``X``) é **ausência**, e não zero.
    """
    series: dict[str, dict[str, str]] = {}
    for variavel in dados:
        valores: dict[str, str] = {}
        for resultado in variavel.get("resultados", []):
            for serie in resultado.get("series", []):
                codigo = str(serie["localidade"]["id"])
                valor = str(serie.get("serie", {}).get("2022", "")).strip()
                try:
                    float(valor)
                except ValueError:
                    continue
                valores[codigo] = valor
        series[str(variavel["id"])] = valores
    return series


def juntar(linhas: list[dict], series: dict[str, dict[str, str]]) -> list[dict]:
    """Acrescenta população e densidade a cada município, pelo código de 7 dígitos."""
    populacao = series.get(VARIAVEL_POPULACAO, {})
    densidade = series.get(VARIAVEL_DENSIDADE, {})
    for linha in linhas:
        codigo = linha["codigo_ibge"]
        linha["populacao_2022"] = populacao.get(codigo, "")
        linha["densidade_2022"] = densidade.get(codigo, "")
    return linhas


def procedencia(linhas: list[dict], series: dict[str, dict[str, str]]) -> dict:
    codigos = {x["codigo_ibge"] for x in linhas}
    sem_populacao = sorted(x["codigo_ibge"] for x in linhas
                           if not x["populacao_2022"])
    return {
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "gerador": {"script": "scripts/gerar_municipios.py", "versao": "2.0"},
        "lista_de_municipios": {"fonte": "IBGE, API de localidades",
                                "url": URL, "total": len(linhas)},
        "populacao": {
            "fonte": "IBGE, Censo Demográfico 2022 — SIDRA tabela 4714",
            "url": URL_CENSO,
            "tabela": TABELA_CENSO,
            "variaveis": {VARIAVEL_POPULACAO: "População residente (pessoas)",
                          VARIAVEL_DENSIDADE: "Densidade demográfica (hab/km²)"},
            "data_de_referencia": REFERENCIA_CENSO,
            "nao_e": "estimativa anual (tabela 6579; indicador 29171 do Cidades@)",
            "municipios_na_fonte": len(series.get(VARIAVEL_POPULACAO, {})),
            "com_populacao": len(linhas) - len(sem_populacao),
            "sem_populacao": sem_populacao,
            "na_fonte_e_fora_da_lista": sorted(
                set(series.get(VARIAVEL_POPULACAO, {})) - codigos),
        },
    }


def gravar(linhas: list[dict], destino: str = DESTINO,
           meta: dict | None = None) -> None:
    linhas.sort(key=lambda x: (x["uf"], str(x["nome"])))
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS, delimiter=";")
        w.writeheader()
        w.writerows(linhas)
    if meta is not None:
        with open(os.path.splitext(destino)[0] + ".json", "w",
                  encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
            f.write("\n")


def main() -> int:
    print(f"Baixando municípios do IBGE: {URL}")
    print(f"Baixando população do Censo 2022 (SIDRA {TABELA_CENSO}): {URL_CENSO}")
    try:
        linhas = baixar()
        series = series_do_censo(_baixar_json(URL_CENSO))
    except Exception as exc:
        print(f"ERRO: não foi possível baixar os dados ({exc!r}).")
        print("Verifique a conexão e tente novamente.")
        return 1
    juntar(linhas, series)
    meta = procedencia(linhas, series)
    gravar(linhas, meta=meta)
    ufs = sorted({x["uf"] for x in linhas})
    pop = meta["populacao"]
    print(f"OK: {len(linhas)} municípios em {len(ufs)} UFs -> {DESTINO}")
    print(f"    com população do Censo 2022: {pop['com_populacao']}; "
          f"sem: {', '.join(pop['sem_populacao']) or 'nenhum'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
