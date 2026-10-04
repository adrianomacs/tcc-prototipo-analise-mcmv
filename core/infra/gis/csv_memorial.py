"""Terreno a partir de CSV de memorial descritivo — coordenadas PROJETADAS.

A planilha de cálculos de um projeto de implantação lista os vértices da
poligonal em E/N (UTM), com a distância de cada lado e a área da matrícula.
Este adaptador a transforma no ``Terreno`` canônico: reprojeta para WGS 84 e
entrega ao construtor do domínio (``terreno.de_poligonal_wgs84``), que não
conhece EPSG de arquivo nem faz I/O (ADR-002).

**O CRS não vem do arquivo e não é deduzido do dado** (ADR-029): o mesmo par
E/N existe em todos os fusos UTM, nos dois hemisférios, então quem importa
declara o EPSG — a tela sugere o do município declarado. A validação é em
camadas: faixa plausível de E/N, área de uso oficial do CRS declarado (via
pyproj, o mesmo raciocínio do ``leitor_crs``) e, na confirmação do terreno, o
confronto com os limites municipais.

Três diferenças deliberadas em relação ao leitor de equipamentos
(``csv_equipamentos``):

* **linha rejeitada = arquivo rejeitado.** Num cadastro, pular um registro
  ilegível é perda anunciada; numa poligonal, um vértice a menos é OUTRA
  geometria — o erro segue com o número da linha, mas nada é importado.
* **conferência vértice a vértice.** Se o arquivo traz a coluna de distâncias
  do memorial, cada lado calculado é conferido contra o declarado; se o
  usuário informa a área da matrícula, ela é conferida contra a área medida no
  CRS de origem. Divergência é aviso com números, nunca correção silenciosa.
* **a distorção de reprojeção é declarada.** A área final é remedida no fuso
  do centróide (ADR-013 via domínio); a diferença para a área no CRS de origem
  fica na procedência em ppm, como no extrator de IFC — sem esse número, uma
  área correta parece suspeita.

Reuso de ``csv_equipamentos``: ``_ler_texto`` (encoding), ``_dialeto``
(separador), ``_numero`` (decimal decidido POR VALOR — um ``;`` de campo com
``.`` decimal mudaria a ordem de grandeza da coordenada) e ``normalizar``.
A detecção de colunas é própria porque a de lá é amarrada ao vocabulário de
equipamentos (débito registrado: extrair um detector parametrizado quando um
terceiro leitor aparecer).

Uso na linha de comando::

    python -m core.infra.gis.csv_memorial "memorial.csv" --epsg EPSG:31982 \
        --area "95.907,00"
"""

from __future__ import annotations

import csv
import io
import math
import os
import re
from dataclasses import dataclass, field

from core.dominio import geometria as crs_mod
from core.dominio import terreno as terreno_mod
from core.infra import impressao_digital
from core.infra.gis.csv_equipamentos import _dialeto, _ler_texto, _numero, normalizar

CAMPOS_OBRIGATORIOS = ("leste", "norte")
CAMPOS_OPCIONAIS = ("vertice", "distancia")

# Aliases de cabeçalho, já normalizados. A ordem é preferência declarada
# (mesma lição do leitor de equipamentos). "leste_l" e "norte_n" são a forma
# normalizada de "LESTE (L)" / "NORTE(N)" — o cabeçalho da planilha de
# cálculos real de um projeto de implantação.
ALIASES: dict[str, tuple[str, ...]] = {
    "vertice": ("vertice", "vertices", "ponto", "pontos", "marco", "estaca",
                "vertex", "id"),
    "leste": ("leste", "leste_l", "este", "east", "coord_e", "coordenada_leste",
              "utm_e", "e", "x"),
    "norte": ("norte", "norte_n", "north", "coord_n", "coordenada_norte",
              "utm_n", "n", "y"),
    "distancia": ("distancia", "distancias", "distancia_m", "dist", "lado",
                  "comprimento"),
}

# Faixas plausíveis de coordenadas UTM em metros. Fora disso, ou o arquivo é
# lat/lon (e este modo não é o lugar), ou é coordenada local/topográfica —
# recusada porque sem amarração não há território (ADR-029).
FAIXA_E = (100_000.0, 900_000.0)
FAIXA_N = (0.0, 10_000_000.0)

# Tolerâncias de conferência contra o memorial. Distância declarada em
# centímetros e coordenada em milímetros arredondam até ~5 mm por lado; 5 cm
# separa arredondamento de erro de digitação. Para a área, 0,5 % cobre o
# arredondamento da matrícula (o caso real diverge ~10 ppm) sem engolir um
# vértice trocado.
TOLERANCIA_DISTANCIA_M = 0.05
TOLERANCIA_AREA_DECLARADA = 0.005

FONTE_EPSG_MUNICIPIO = "sugerido_do_municipio"
FONTE_EPSG_USUARIO = "informado_pelo_usuario"

# Modelo baixável na tela — mesmo papel do config/modelo_equipamentos.csv.
CAMINHO_MODELO = os.path.join("config", "modelo_memorial_descritivo.csv")

# "M1 — M2": a planilha de implantação nomeia o LADO, e a coordenada da linha
# é a do primeiro vértice do par. Divide em travessão (com ou sem espaço) ou
# em hífen ENTRE espaços — "M-1" sem espaços permanece inteiro.
_PAR_DE_VERTICES = re.compile(r"\s+[-—–−]\s+|\s*[—–−]\s*")


@dataclass
class Vertice:
    nome: str
    e: float
    n: float
    distancia_m: float | None    # declarada no memorial, até o vértice seguinte
    linha: int                   # número da linha no arquivo (para mensagens)


@dataclass
class LeituraMemorial:
    """Saída da leitura: o terreno pronto, ou o diagnóstico de por que não."""

    terreno: terreno_mod.Terreno | None = None
    vertices: list[Vertice] = field(default_factory=list)
    rejeitadas: list[tuple[int, str]] = field(default_factory=list)
    colunas_detectadas: dict[str, str] = field(default_factory=dict)
    faltando: list[str] = field(default_factory=list)
    dialeto: dict = field(default_factory=dict)
    avisos: list[str] = field(default_factory=list)
    conferencia: dict = field(default_factory=dict)
    erro: str = ""

    @property
    def ok(self) -> bool:
        return self.terreno is not None


# ---------------------------------------------------------------------------
# Detecção e interpretação
# ---------------------------------------------------------------------------

def detectar_colunas(cabecalho: list[str]) -> tuple[dict[str, str], list[str]]:
    """``(campo -> coluna_original, campos_obrigatorios_faltando)``.

    Duas passadas — aliases exatos na ordem declarada, depois busca aproximada
    — pela mesma razão do leitor de equipamentos: a aproximação de um campo
    não pode tomar a coluna que o alias exato de outro reclamaria depois.
    Alias de uma letra ("e", "n", "x", "y") só participa da passada exata.
    """
    normalizados = {col: normalizar(col) for col in cabecalho}
    detectadas: dict[str, str] = {}

    for campo, aliases in ALIASES.items():
        achou = False
        for alias in aliases:
            for col, norm in normalizados.items():
                if norm == alias and col not in detectadas.values():
                    detectadas[campo] = col
                    achou = True
                    break
            if achou:
                break

    for campo, aliases in ALIASES.items():
        if campo in detectadas:
            continue
        for col, norm in normalizados.items():
            if col in detectadas.values():
                continue
            if any(a in norm or norm in a for a in aliases if len(a) > 3):
                detectadas[campo] = col
                break

    faltando = [c for c in CAMPOS_OBRIGATORIOS if c not in detectadas]
    return detectadas, faltando


def _nome_do_vertice(bruto: str, ordinal: int) -> str:
    """"M1 — M2" -> "M1"; célula vazia vira V<ordinal>."""
    texto = (bruto or "").strip()
    if not texto:
        return f"V{ordinal}"
    partes = [p for p in _PAR_DE_VERTICES.split(texto) if p.strip()]
    return partes[0].strip() if partes else texto


def _normalizar_epsg(epsg: str) -> str:
    texto = str(epsg or "").strip().upper()
    if texto.isdigit():
        return f"EPSG:{texto}"
    return texto


def epsgs_utm_sirgas() -> list[tuple[str, str]]:
    """Opções de SIRGAS 2000 / UTM para a tela — ``(codigo, rotulo)``.

    Sul primeiro (cobre quase todo o país), norte depois. Os códigos vêm das
    âncoras de ``geometria`` — a mesma conta do ``epsg_metrico``.
    """
    opcoes = []
    for fuso in crs_mod._SIRGAS_SUL_FUSOS:
        codigo = f"EPSG:{crs_mod._SIRGAS_SUL_BASE + fuso}"
        opcoes.append((codigo, f"SIRGAS 2000 / UTM fuso {fuso}S — {codigo}"))
    for fuso in crs_mod._SIRGAS_NORTE_FUSOS:
        codigo = f"EPSG:{crs_mod._SIRGAS_NORTE_BASE + fuso}"
        opcoes.append((codigo, f"SIRGAS 2000 / UTM fuso {fuso}N — {codigo}"))
    return opcoes


def modelo_csv() -> str:
    """Conteúdo do modelo baixável (``config/modelo_memorial_descritivo.csv``)."""
    with open(CAMINHO_MODELO, encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------

def ler(caminho: str, *, epsg: str,
        area_declarada_m2: float | str | None = None,
        epsg_fonte: str = FONTE_EPSG_USUARIO) -> LeituraMemorial:
    """Lê o CSV do memorial e devolve o ``Terreno`` — ou o diagnóstico.

    ``epsg`` é a declaração do usuário (ADR-029). ``area_declarada_m2`` aceita
    número ou texto no formato do memorial ("95.907,00").
    """
    texto, encoding = _ler_texto(caminho)
    dialeto = _dialeto(texto[:8192])
    dialeto["encoding"] = encoding

    leitor = csv.reader(io.StringIO(texto), delimiter=dialeto["separador"])
    linhas_brutas = list(leitor)
    linhas = [(i, l) for i, l in enumerate(linhas_brutas, start=1)
              if any((c or "").strip() for c in l)]
    resultado = LeituraMemorial(dialeto=dialeto)
    if not linhas:
        resultado.faltando = list(CAMPOS_OBRIGATORIOS)
        resultado.erro = "Arquivo vazio."
        return resultado

    cabecalho = [c.strip() for c in linhas[0][1]]
    detectadas, faltando = detectar_colunas(cabecalho)
    resultado.colunas_detectadas = detectadas
    resultado.faltando = faltando
    if faltando:
        resultado.erro = ("Colunas obrigatórias não encontradas: "
                          + ", ".join(faltando)
                          + ". Baixe o modelo de CSV para ver o formato esperado.")
        return resultado

    indice = {campo: cabecalho.index(col) for campo, col in detectadas.items()}

    def celula(linha: list[str], campo: str) -> str:
        i = indice.get(campo)
        if i is None or i >= len(linha):
            return ""
        return (linha[i] or "").strip()

    vertices: list[Vertice] = []
    for numero_linha, linha in linhas[1:]:
        e = _numero(celula(linha, "leste"))
        n = _numero(celula(linha, "norte"))
        if e is None or n is None:
            resultado.rejeitadas.append(
                (numero_linha, "coordenada ausente ou ilegível"))
            continue
        distancia = (_numero(celula(linha, "distancia"))
                     if "distancia" in indice else None)
        nome = _nome_do_vertice(celula(linha, "vertice"), len(vertices) + 1)
        vertices.append(Vertice(nome=nome, e=e, n=n,
                                distancia_m=distancia, linha=numero_linha))

    if resultado.rejeitadas:
        # Num cadastro, linha rejeitada é registro a menos; numa poligonal é
        # OUTRA geometria. Nada é importado — o erro diz exatamente onde.
        linhas_ruins = ", ".join(str(n) for n, _ in resultado.rejeitadas)
        resultado.erro = (f"Linha(s) {linhas_ruins} sem coordenada legível. "
                          "Um vértice a menos mudaria a poligonal, então nada "
                          "foi importado — corrija o arquivo e reenvie.")
        return resultado

    # Anel já fechado no arquivo: descarta a repetição do primeiro vértice.
    if len(vertices) >= 2:
        v0, vf = vertices[0], vertices[-1]
        if math.hypot(vf.e - v0.e, vf.n - v0.n) < 1e-3:
            vertices = vertices[:-1]

    resultado.vertices = vertices
    if len(vertices) < 3:
        resultado.erro = "Uma poligonal exige ao menos 3 vértices distintos."
        return resultado

    # --- Plausibilidade das coordenadas (ADR-029: sem amarração não há
    # território; lat/lon tem os próprios modos de entrada) ------------------
    if all(abs(v.e) <= 180.0 and abs(v.n) <= 90.0 for v in vertices):
        resultado.erro = (
            "Os valores parecem coordenadas GEOGRÁFICAS (latitude/longitude). "
            "Este modo espera coordenadas PROJETADAS (E/N em metros, UTM) — "
            "para lat/lon, use os modos de mapa ou de coordenadas do centro.")
        return resultado
    fora = [v for v in vertices
            if not (FAIXA_E[0] <= v.e <= FAIXA_E[1]
                    and FAIXA_N[0] <= v.n <= FAIXA_N[1])]
    if fora:
        v = fora[0]
        resultado.erro = (
            f"Coordenada fora da faixa UTM plausível (linha {v.linha}: "
            f"E={v.e:g}, N={v.n:g}). Coordenadas locais/topográficas não têm "
            "amarração geodésica e não são aceitas.")
        return resultado

    # --- CRS declarado ------------------------------------------------------
    codigo_epsg = _normalizar_epsg(epsg)
    try:
        from pyproj import CRS
        crs_origem = CRS.from_user_input(codigo_epsg)
    except Exception:
        resultado.erro = f"Código EPSG não reconhecido: {epsg!r}."
        return resultado
    if crs_origem.is_geographic:
        resultado.erro = (f"{codigo_epsg} é um CRS geográfico (graus). Este "
                          "modo espera um CRS PROJETADO (E/N em metros).")
        return resultado

    # --- Medidas no CRS de origem (o que o memorial mediu) ------------------
    from shapely.geometry import Polygon

    anel = [(v.e, v.n) for v in vertices]
    fonte = Polygon(anel)
    area_fonte = fonte.area
    perimetro_fonte = fonte.length

    # --- Reprojeção para WGS 84 e construção no domínio ---------------------
    transformar = crs_mod.transformador(codigo_epsg, crs_mod.CRS_GEOGRAFICO)
    coordenadas = [transformar.transform(v.e, v.n) for v in vertices]

    # Área de uso oficial do CRS declarado — mesmo raciocínio do leitor_crs.
    area_uso = getattr(crs_origem, "area_of_use", None)
    aviso_area_uso = None
    if area_uso is not None:
        lon_c = sum(lon for lon, _ in coordenadas) / len(coordenadas)
        lat_c = sum(lat for _, lat in coordenadas) / len(coordenadas)
        if not (area_uso.west <= lon_c <= area_uso.east
                and area_uso.south <= lat_c <= area_uso.north):
            aviso_area_uso = (
                f"O terreno reprojetado cai FORA da área de uso oficial de "
                f"{codigo_epsg} ({area_uso.name}). Confira o fuso e o "
                "hemisfério declarados — o confronto com os limites do "
                "município vai barrar a confirmação se estiverem errados.")

    procedencia = {
        "arquivo": caminho,
        # ADR-035: o conteúdo que produziu o terreno, para o relatório citá-lo.
        "sha256": impressao_digital.sha256(caminho),
        "epsg_origem": codigo_epsg,
        "epsg_origem_fonte": epsg_fonte,
        "colunas": dict(detectadas),
        "vertices": [v.nome for v in vertices],
        "area_no_crs_do_memorial_m2": round(area_fonte, 2),
        "perimetro_no_crs_do_memorial_m": round(perimetro_fonte, 2),
    }

    try:
        t = terreno_mod.de_poligonal_wgs84(
            coordenadas, origem=terreno_mod.ORIGEM_CSV,
            precisao=terreno_mod.PRECISAO_LEVANTADA, procedencia=procedencia)
    except ValueError as exc:
        resultado.erro = str(exc)
        return resultado

    # Distorção de reprojeção: área remedida no fuso do centróide (ADR-013,
    # via domínio) contra a área no CRS do memorial, em ppm.
    if t.area_m2 and area_fonte:
        ppm = (t.area_m2 - area_fonte) / area_fonte * 1e6
        t.procedencia["desvio_reprojecao_ppm"] = round(ppm, 1)

    if aviso_area_uso:
        t.avisos.append(aviso_area_uso)

    _conferir_area_declarada(t, area_fonte, area_declarada_m2, resultado)
    _conferir_distancias(t, vertices, resultado)

    resultado.terreno = t
    resultado.avisos = list(t.avisos)
    return resultado


def _conferir_area_declarada(t, area_fonte: float, declarada, resultado) -> None:
    """Área da matrícula × área medida sobre os próprios vértices."""
    if declarada is None or declarada == "":
        return
    valor = _numero(declarada) if isinstance(declarada, str) else float(declarada)
    if valor is None or valor <= 0:
        t.avisos.append(f"Área declarada ilegível ({declarada!r}); conferência "
                        "de área não realizada.")
        return
    desvio = (area_fonte - valor) / valor
    t.procedencia["area_declarada_m2"] = round(valor, 2)
    t.procedencia["desvio_area_declarada_pct"] = round(desvio * 100, 4)
    resultado.conferencia["area_declarada_m2"] = round(valor, 2)
    resultado.conferencia["desvio_area_declarada_pct"] = round(desvio * 100, 4)
    if abs(desvio) > TOLERANCIA_AREA_DECLARADA:
        t.avisos.append(
            f"Área medida dos vértices "
            f"({terreno_mod.formatar_numero(area_fonte)} m²) diverge "
            f"{desvio * 100:+.2f}% da área declarada no memorial "
            f"({terreno_mod.formatar_numero(valor)} m²). Confira os vértices "
            "e o memorial.")


def _conferir_distancias(t, vertices: list[Vertice], resultado) -> None:
    """Cada lado calculado × a distância declarada no memorial (se houver)."""
    declaradas = [v for v in vertices if v.distancia_m is not None]
    if not declaradas:
        return
    divergencias = []
    for i, v in enumerate(vertices):
        if v.distancia_m is None:
            continue
        seguinte = vertices[(i + 1) % len(vertices)]
        calculada = math.hypot(seguinte.e - v.e, seguinte.n - v.n)
        if abs(calculada - v.distancia_m) > TOLERANCIA_DISTANCIA_M:
            divergencias.append({
                "de": v.nome, "para": seguinte.nome,
                "declarada_m": round(v.distancia_m, 3),
                "calculada_m": round(calculada, 3)})
    conf = {"lados_declarados": len(declaradas),
            "lados_conferidos": len(declaradas) - len(divergencias),
            "divergencias": divergencias}
    t.procedencia["conferencia_distancias"] = conf
    resultado.conferencia["distancias"] = conf
    if divergencias:
        d = divergencias[0]
        t.avisos.append(
            f"{len(divergencias)} lado(s) com distância calculada divergente "
            f"da declarada no memorial (primeiro: {d['de']}–{d['para']}, "
            f"declarada {terreno_mod.formatar_numero(d['declarada_m'], 2)} m, "
            f"calculada {terreno_mod.formatar_numero(d['calculada_m'], 2)} m). "
            "Confira a digitação dos vértices.")


# ---------------------------------------------------------------------------
# CLI de diagnóstico
# ---------------------------------------------------------------------------

def _cli() -> None:
    import argparse
    import json

    p = argparse.ArgumentParser(
        description="Diagnostica a leitura de um CSV de memorial descritivo.")
    p.add_argument("csv", help="Caminho do arquivo CSV.")
    p.add_argument("--epsg", required=True,
                   help="CRS das coordenadas E/N (ex.: EPSG:31982).")
    p.add_argument("--area", default=None,
                   help='Área declarada no memorial, em m² (ex.: "95.907,00").')
    p.add_argument("--json", action="store_true",
                   help="Imprime o Terreno serializado ao final.")
    args = p.parse_args()

    leitura = ler(args.csv, epsg=args.epsg, area_declarada_m2=args.area)
    print("=" * 72)
    print(f"ARQUIVO  : {args.csv}")
    print(f"DIALETO  : separador {leitura.dialeto.get('separador')!r} · "
          f"encoding {leitura.dialeto.get('encoding')} · "
          f"decimal decidido por valor")
    print("\nCOLUNAS DETECTADAS")
    for campo in CAMPOS_OBRIGATORIOS + CAMPOS_OPCIONAIS:
        col = leitura.colunas_detectadas.get(campo)
        print(f"  {campo:<10} -> {col!r}" if col
              else f"  {campo:<10} -> (não encontrada)")
    for numero, motivo in leitura.rejeitadas:
        print(f"  linha {numero}: {motivo}")
    if leitura.erro:
        print(f"\nERRO: {leitura.erro}")
        return

    t = leitura.terreno
    proc = t.procedencia
    print(f"\nVÉRTICES : {len(leitura.vertices)} "
          f"({', '.join(v.nome for v in leitura.vertices)})")
    print(f"ÁREA     : {terreno_mod.formatar_numero(proc['area_no_crs_do_memorial_m2'])} m² "
          f"no CRS do memorial ({proc['epsg_origem']})")
    print(f"           {terreno_mod.formatar_numero(t.area_m2)} m² remedida em "
          f"{t.crs_metrico} ({proc.get('desvio_reprojecao_ppm', 0):+.1f} ppm)")
    if "area_declarada_m2" in proc:
        print(f"           {terreno_mod.formatar_numero(proc['area_declarada_m2'])} m² "
              f"declarada no memorial "
              f"({proc['desvio_area_declarada_pct']:+.4f}%)")
    conf = proc.get("conferencia_distancias")
    if conf:
        print(f"LADOS    : {conf['lados_conferidos']} de "
              f"{conf['lados_declarados']} conferem com o memorial "
              f"(tolerância {TOLERANCIA_DISTANCIA_M} m)")
        for d in conf["divergencias"]:
            print(f"  {d['de']}–{d['para']}: declarada {d['declarada_m']} m, "
                  f"calculada {d['calculada_m']} m")
    print(f"\nTERRENO  : {t.resumo()}")
    for aviso in t.avisos:
        print(f"  AVISO: {aviso}")
    if args.json:
        print(json.dumps(t.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _cli()
