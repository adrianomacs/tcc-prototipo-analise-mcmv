"""Gera o snapshot de zonas bioclimáticas por município (config/zonas_bioclimaticas.csv).

Fonte primária: ABNT TR 15220-3-1:2024 — Relatório Técnico que publica a zona
bioclimática de cada município segundo o método da ABNT NBR 15220-3. A ABNT
distribui a tabela apenas em PDF, um arquivo por região geográfica. Os cinco
PDFs ficam em ``entradas/abnt/`` e NÃO são versionados (norma paga, de
redistribuição vedada); ver ``entradas/abnt/FONTES.md``.

Autoridade sobre a lista de municípios: ``config/municipios_ibge.csv`` — o mesmo
snapshot que alimenta os seletores da interface (scripts/gerar_municipios.py).
Assim as duas bases nunca divergem em código, nome ou quantidade.

ATENÇÃO — armadilha de extração. ``pdftotext -layout`` perde o nome de 319
municípios cujo rótulo quebra em duas linhas na célula (ex.: "Boa Esperança do /
Iguaçu", PR): o texto corrido separa as duas metades do nome da linha de dados.
A extração por TABELA do pdfplumber usa as linhas de grade do PDF e devolve a
célula inteira. Não trocar por extração de texto corrido.

Execução (na raiz do projeto):
    python scripts/gerar_zonas_bioclimaticas.py
"""

from __future__ import annotations

import csv
import datetime as dt
import glob
import hashlib
import json
import os
import re
import sys
import unicodedata

ORIGEM = os.path.join("entradas", "abnt")
MUNICIPIOS = os.path.join("config", "municipios_ibge.csv")
DESTINO = os.path.join("config", "zonas_bioclimaticas.csv")
PROCEDENCIA = os.path.join("config", "zonas_bioclimaticas.json")

NORMA = "ABNT TR 15220-3-1:2024"
FONTE_ABNT = "ABNT_TR_15220-3-1_2024"
FONTE_AUSENTE = "AUSENTE"
FONTE_HERANCA = "HERANCA_MUNICIPIO_DE_ORIGEM"

# Municípios instalados DEPOIS da base de localidades que a norma usou
# (2023-05-02) e que, por isso, não têm linha na ABNT. A zona é herdada dos
# municípios de origem quando eles concordam — o território é o mesmo, e não há
# interpretação a fazer; origem divergente NÃO é herdada e o município fica sem
# zona (ADR-030). Cada entrada é conferida uma a uma, como GRAFIAS_DIVERGENTES:
# código novo -> códigos IBGE de origem.
ORIGENS_DE_MUNICIPIO_NOVO = {
    # Boa Esperança do Norte/MT, instalado em 01/01/2025, desmembrado de
    # Sorriso (5107925) e Nova Ubiratã (5106240) — ambos 5B.
    "5101837": ("5107925", "5106240"),
}

CAMPOS = [
    "codigo_ibge", "nome", "uf", "zona_bioclimatica", "fonte",
    "latitude", "longitude", "altitude_m", "tbs_media_anual_c",
    "ur_media_anual_pct", "radiacao_global_diaria_wm2",
    "vento_medio_anual_ms", "amplitude_termica_anual_c",
    "nome_na_abnt", "observacao",
]

UFS = set("AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO "
          "RR SC SP SE TO".split())
ZB = re.compile(r"^[1-8][A-Z]?$")

# Grafias da ABNT que divergem do nome oficial do IBGE. Todas conferidas uma a
# uma e todas 1:1 dentro da UF — não há ambiguidade a resolver em tempo de
# execução. Mapeiam para o código IBGE de 7 dígitos.
GRAFIAS_DIVERGENTES = {
    ("RR", "Sao Luiz"): "1400605",
    ("TO", "Fortaleza do Tabocao"): "1708254",
    ("RN", "Acu"): "2400208",
    ("RN", "Ares"): "2401206",
    ("SE", "Amparo de Sao Francisco"): "2800100",
    ("BA", "Muquem de Sao Francisco"): "2922250",
    ("BA", "Santa Teresinha"): "2928505",
    ("MG", "Barao de Monte Alto"): "3105509",
    ("MG", "Dona Eusebia"): "3122900",
    ("MG", "Sao Thome das Letras"): "3165206",
    ("SP", "Florinia"): "3516101",
    ("MT", "Santo Antonio do Leverger"): "5107800",
}


def normalizar(s: str) -> str:
    """Nome comparável: sem acento, caixa baixa, apóstrofo e hífen como espaço."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("'", " ").replace("-", " ")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


# As chaves acima são normalizadas na carga do módulo, para casar com o que
# normalizar() devolve (a função é definida acima).
GRAFIAS_DIVERGENTES = {(uf, normalizar(nome)): codigo
                       for (uf, nome), codigo in GRAFIAS_DIVERGENTES.items()}


def ler_municipios(caminho: str = MUNICIPIOS) -> list[dict]:
    if not os.path.exists(caminho):
        raise SystemExit(f"ERRO: {caminho} não existe. Rode antes "
                         f"'python scripts/gerar_municipios.py'.")
    with open(caminho, "r", encoding="utf-8", newline="") as f:
        return [linha for linha in csv.DictReader(f, delimiter=";")
                if linha.get("codigo_ibge")]


def extrair_pdfs(origem: str = ORIGEM) -> tuple[list[dict], list[dict]]:
    """Devolve (linhas extraídas, procedência de cada PDF)."""
    try:
        import pdfplumber
    except ImportError:
        raise SystemExit("ERRO: pdfplumber não instalado (pip install pdfplumber).")

    arquivos = sorted(glob.glob(os.path.join(origem, "*.pdf")))
    if not arquivos:
        raise SystemExit(f"ERRO: nenhum PDF em {origem}/ — ver "
                         f"{os.path.join(origem, 'FONTES.md')}.")

    linhas: list[dict] = []
    fontes: list[dict] = []
    for caminho in arquivos:
        with open(caminho, "rb") as f:
            sha = hashlib.sha256(f.read()).hexdigest()
        antes = len(linhas)
        with pdfplumber.open(caminho) as pdf:
            for pagina in pdf.pages:
                for tabela in pagina.extract_tables():
                    for bruta in tabela:
                        celulas = ["" if c is None
                                   else re.sub(r"\s+", " ", c.replace("\n", " ")).strip()
                                   for c in bruta]
                        if len(celulas) != 11 or celulas[0] not in UFS:
                            continue  # cabeçalho, rodapé ou linha de título
                        if not ZB.match(celulas[2]):
                            raise SystemExit(
                                f"ERRO: ZB inesperada em {caminho}: {celulas!r}")
                        linhas.append({
                            "uf": celulas[0],
                            "cidade": celulas[1],
                            "zb": celulas[2],
                            "latitude": celulas[3].replace(",", "."),
                            "longitude": celulas[4].replace(",", "."),
                            "altitude_m": celulas[5].replace(" ", ""),
                            "tbs": celulas[6].replace(",", "."),
                            "ur": celulas[7],
                            "radiacao": celulas[8].replace(" ", ""),
                            "vento": celulas[9].replace(",", "."),
                            "amplitude": celulas[10].replace(",", "."),
                        })
        fontes.append({
            "arquivo": os.path.basename(caminho),
            "sha256": sha,
            "linhas": len(linhas) - antes,
        })
    return linhas, fontes


def casar(linhas: list[dict], municipios: list[dict]) -> dict[str, dict]:
    """Indexa as linhas da ABNT por código IBGE."""
    por_nome = {(m["uf"], normalizar(m["nome"])): m["codigo_ibge"]
                for m in municipios}
    por_codigo: dict[str, dict] = {}
    for linha in linhas:
        chave = (linha["uf"], normalizar(linha["cidade"]))
        codigo = GRAFIAS_DIVERGENTES.get(chave) or por_nome.get(chave)
        if not codigo:
            raise SystemExit(f"ERRO: cidade da ABNT sem município IBGE "
                             f"correspondente: {linha['uf']} {linha['cidade']!r}. "
                             f"Se for grafia nova, acrescente a "
                             f"GRAFIAS_DIVERGENTES conferindo o código.")
        if codigo in por_codigo:
            raise SystemExit(f"ERRO: duas linhas da ABNT para o código {codigo}.")
        por_codigo[codigo] = linha
    return por_codigo


def _herdar(codigo: str, por_codigo: dict[str, dict]) -> tuple[str, list[str]]:
    """Zona herdada dos municípios de origem, e só quando eles CONCORDAM.

    Devolve ``("", [])`` quando o município não tem origem declarada, quando
    alguma origem não tem zona, ou quando as origens divergem — nesses casos
    ele fica sem zona e a regra que a consumir sai NÃO AVALIÁVEL (ADR-030).
    Herança silenciosa é o que a decisão proíbe: quem herda sai marcado em
    ``fonte`` e com as origens nomeadas na observação.
    """
    origens = ORIGENS_DE_MUNICIPIO_NOVO.get(codigo)
    if not origens:
        return "", []
    zonas = {por_codigo[o]["zb"] for o in origens if o in por_codigo}
    if len(zonas) != 1 or len(origens) != sum(1 for o in origens if o in por_codigo):
        return "", []
    return zonas.pop(), list(origens)


def montar(municipios: list[dict], por_codigo: dict[str, dict]) -> list[dict]:
    saida = []
    for m in municipios:
        codigo = m["codigo_ibge"]
        linha = por_codigo.get(codigo)
        registro = {"codigo_ibge": codigo, "nome": m["nome"], "uf": m["uf"]}
        if linha is None:
            registro.update({c: "" for c in CAMPOS[3:]})
            herdada, origens = _herdar(codigo, por_codigo)
            if herdada:
                # Só a ZONA é herdada. As colunas climáticas (latitude, TBS,
                # radiação…) são medidas DO município de origem e não valem
                # para este — copiá-las inventaria dado.
                registro["zona_bioclimatica"] = herdada
                registro["fonte"] = FONTE_HERANCA
                registro["observacao"] = (
                    "município não consta do " + NORMA + "; zona herdada dos "
                    "municípios de origem (" + ", ".join(origens) + "), que "
                    "concordam — ADR-030")
            else:
                registro["fonte"] = FONTE_AUSENTE
                registro["observacao"] = (
                    "município não consta do " + NORMA +
                    "; a tabela usa a base de localidades do IBGE de 2023-05-02")
        else:
            divergente = normalizar(linha["cidade"]) != normalizar(m["nome"])
            registro.update({
                "zona_bioclimatica": linha["zb"],
                "fonte": FONTE_ABNT,
                "latitude": linha["latitude"],
                "longitude": linha["longitude"],
                "altitude_m": linha["altitude_m"],
                "tbs_media_anual_c": linha["tbs"],
                "ur_media_anual_pct": linha["ur"],
                "radiacao_global_diaria_wm2": linha["radiacao"],
                "vento_medio_anual_ms": linha["vento"],
                "amplitude_termica_anual_c": linha["amplitude"],
                "nome_na_abnt": linha["cidade"] if divergente else "",
                "observacao": "grafia divergente na ABNT" if divergente else "",
            })
        saida.append(registro)
    return saida


def gravar(saida: list[dict], fontes: list[dict]) -> None:
    saida.sort(key=lambda r: r["codigo_ibge"])
    with open(DESTINO, "w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=CAMPOS, delimiter=";")
        escritor.writeheader()
        escritor.writerows(saida)

    ausentes = [{"codigo_ibge": r["codigo_ibge"], "uf": r["uf"], "nome": r["nome"]}
                for r in saida if r["fonte"] == FONTE_AUSENTE]
    herdados = [{"codigo_ibge": r["codigo_ibge"], "uf": r["uf"], "nome": r["nome"],
                 "zona_bioclimatica": r["zona_bioclimatica"],
                 "origens": list(ORIGENS_DE_MUNICIPIO_NOVO.get(r["codigo_ibge"], ()))}
                for r in saida if r["fonte"] == FONTE_HERANCA]
    divergentes = [{"codigo_ibge": r["codigo_ibge"], "uf": r["uf"],
                    "nome_ibge": r["nome"], "nome_abnt": r["nome_na_abnt"]}
                   for r in saida if r["nome_na_abnt"]]
    procedencia = {
        "norma": NORMA,
        "gerado_em": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "gerador": {"script": "scripts/gerar_zonas_bioclimaticas.py", "versao": "1.1"},
        "municipios": {
            # Barra normal em qualquer SO: o .json é versionado e não pode mudar
            # só porque a base foi regerada no Windows.
            "autoridade": MUNICIPIOS.replace(os.sep, "/"),
            "total": len(saida),
            "com_zona": len(saida) - len(ausentes),
            "com_zona_da_norma": len(saida) - len(ausentes) - len(herdados),
            "com_zona_herdada": len(herdados),
            "sem_zona": len(ausentes),
        },
        "base_de_localidades_da_norma": {
            "fonte": "IBGE, API de localidades",
            "url": "https://servicodados.ibge.gov.br/api/docs/localidades",
            "acesso_declarado_pela_norma": "2023-05-02",
        },
        "pdfs": fontes,
        "municipios_sem_zona": ausentes,
        "municipios_com_zona_herdada": herdados,
        "grafias_divergentes": divergentes,
        "notas": [
            ("O texto da norma declara cobrir '5 507 cidades'; a tabela traz uma "
            "linha por município da base IBGE de 2023-05-02. O número no texto "
            "não corresponde ao conteúdo da tabela."),
            ("O vocabulário de zona desta edição tem 12 classes (1M, 1R, 2M, 2R, "
            "3A, 3B, 4A, 4B, 5A, 5B, 6A, 6B) e NÃO é o zoneamento numérico de 8 "
            "zonas da ABNT NBR 15220-3:2005. A numeração não se preserva entre "
            "as duas edições (ex.: São Paulo, Z3 na de 2005, é 2M nesta). Ver o "
            "achado sobre o conflito de vocabulário na Portaria MCID 725 em "
            "docs/tcc/achados_desenvolvimento.md."),
            ("Município instalado depois da base de localidades da norma "
            "(2023-05-02) não tem linha na ABNT. Quando os municípios de origem "
            "concordam, a zona é herdada e a linha sai marcada com fonte "
            "HERANCA_MUNICIPIO_DE_ORIGEM, com as origens nomeadas na "
            "observação; origem divergente não é herdada (ADR-030)."),
        ],
    }
    with open(PROCEDENCIA, "w", encoding="utf-8") as f:
        json.dump(procedencia, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main() -> int:
    municipios = ler_municipios()
    linhas, fontes = extrair_pdfs()
    print(f"Extraídas {len(linhas)} linhas de {len(fontes)} PDFs da ABNT.")
    por_codigo = casar(linhas, municipios)
    saida = montar(municipios, por_codigo)
    gravar(saida, fontes)
    sem = sum(1 for r in saida if r["fonte"] == FONTE_AUSENTE)
    print(f"OK: {len(saida)} municípios ({len(saida) - sem} com zona, "
          f"{sem} sem) -> {DESTINO}")
    print(f"     procedência -> {PROCEDENCIA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
