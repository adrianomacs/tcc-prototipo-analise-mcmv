"""Gera a figura da arquitetura do protótipo, em visão estrutural,
em SVG e PNG.

A figura adapta o princípio do diagrama de anéis concêntricos de Martin (2012)
ao conteúdo real do repositório, sem reproduzir o desenho original. São quatro
anéis, de dentro para fora domínio, regras, aplicação e infraestrutura, na
ordem que `tests/arquitetura/test_aneis.py` impõe, com as setas de dependência
apontando sempre para dentro e nenhuma tracejada, porque a regra vale sem
exceção (ADR-002, ADR-036, ADR-037). Fora dos anéis ficam o módulo de
composição, porta de entrada para executar a verificação (ADR-037), a interface
com `app/servicos` como único ponto de passagem (ADR-003), a pasta `artefatos/`
como fronteira com a visualização (ADR-001) e, em neutro, as ferramentas que
cada adaptador envolve. À direita, o painel "Caminho de uma checagem" carrega a
visão comportamental, no lugar da antiga Figura 3.

A família visual é a da Figura 1 (`scripts/gerar_figura1.py`): o azul-petróleo
do protótipo em gradação, do centro para a borda, e neutros para o que está
fora do núcleo. O conteúdo dos anéis é escrito em arco, com o contorno do texto
dobrado sobre a circunferência, porque numa faixa de 8 mm uma linha reta não
tem corda útil para mais de uma palavra.

Uso, na raiz do repositório (exige o extra de desenvolvimento, que traz o
matplotlib):

    pip install -e ".[dev]"
    python scripts/gerar_figura2.py

Saída em docs/figuras/figura2_arquitetura.svg e .png. O resultado é
determinístico na mesma máquina (sal fixo do SVG, sem data nos metadados); a
fonte é Arial, ou Liberation Sans, de mesmas métricas, onde o Arial não
existir. O script confere, ao final, que nenhum texto transborda da sua caixa,
do seu anel ou do seu setor, e recusa gerar a figura se transbordar.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import matplotlib as mpl
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties
from matplotlib.patches import (
    Circle,
    Ellipse,
    FancyArrowPatch,
    FancyBboxPatch,
    PathPatch,
    Rectangle,
)
from matplotlib.path import Path as MplPath
from matplotlib.textpath import TextPath, TextToPath

RAIZ = Path(__file__).resolve().parents[1]
DESTINO = RAIZ / "docs" / "figuras"
NOME = "figura2_arquitetura"

# Geometria em milímetros, origem no canto superior esquerdo (y cresce para
# baixo). Largura útil de 16 cm.
LARGURA, ALTURA = 160.0, 120.0
DPI = 300
FONTE_PT = 8
PT_MM = 25.4 / 72  # 1 pt em mm
FONTES = ["Arial", "Liberation Sans", "DejaVu Sans"]


def _familia_disponivel() -> str:
    """A primeira fonte da lista que existe na máquina, para não pedir ao
    matplotlib uma família ausente a cada linha escrita em arco."""
    from matplotlib import font_manager
    nomes = {f.name for f in font_manager.fontManager.ttflist}
    return next((f for f in FONTES if f in nomes), "DejaVu Sans")

# Anéis: centro e raio externo de cada um, do centro para fora.
CX, CY = 61.0, 71.5
R_DOMINIO, R_REGRAS, R_APLICACAO, R_INFRA = 25.5, 33.0, 40.5, 48.0

# Cores. O azul-petróleo da Figura 1 em gradação (mais escuro, mais central) e
# os neutros da Figura 1 para tudo o que fica fora do núcleo.
PETROLEO = "#155e75"
PETROLEO_ESCURO = "#0e4a5c"
TOM = {
    "dominio": PETROLEO,
    "regras": "#7fb1c1",
    "aplicacao": "#b5d4de",
    "infra": "#e1eef2",
}
NEUTRO = ("#f1f5f9", "#475569")
COR_TEXTO = "#0f172a"
COR_SECUNDARIA = "#475569"
COR_LINHA = "#334155"
COR_GRADE_PAINEL = "#cbd5e1"

_caixas: list[tuple[str, tuple[float, float, float, float], object]] = []
_problemas: list[str] = []
_setores: dict[str, list[tuple[float, float, str]]] = {}


def _configurar():
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": [_familia_disponivel()],
            "font.size": FONTE_PT,
            "svg.fonttype": "path",
            "svg.hashsalt": "figura2-arquitetura",
            "path.simplify": False,
        }
    )
    fig = Figure(figsize=(LARGURA / 25.4, ALTURA / 25.4), dpi=DPI)
    FigureCanvasAgg(fig)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, LARGURA)
    ax.set_ylim(ALTURA, 0)
    ax.set_aspect("equal")
    ax.axis("off")
    return fig, ax


# --- Texto reto e caixas (o mesmo regime da Figura 1) -----------------------

def texto(ax, x, y, s, **kw):
    base = {"fontsize": FONTE_PT, "color": COR_TEXTO, "ha": "center", "va": "center",
            "linespacing": 1.15}
    base.update(kw)
    return ax.text(x, y, s, **base)


def caixa(ax, x0, x1, y0, y1, cores, s=None, espessura=0.9, **kw):
    preenchimento, contorno = cores
    ax.add_patch(
        FancyBboxPatch(
            (x0, y0), x1 - x0, y1 - y0,
            boxstyle="round,pad=0,rounding_size=1.2",
            facecolor=preenchimento, edgecolor=contorno, linewidth=espessura, zorder=3,
        )
    )
    if s is None:
        return None
    t = texto(ax, (x0 + x1) / 2, (y0 + y1) / 2, s, zorder=4, **kw)
    _caixas.append((s, (x0, x1, y0, y1), t))
    return t


def linhas(ax, x0, x1, y0, y1, itens, **kw):
    """Linhas empilhadas e centradas numa caixa, cada uma com o seu estilo;
    `itens` é uma lista de (texto, dict de estilo). Registra-se cada linha na
    conferência de transbordo com a largura da caixa."""
    passo = FONTE_PT * PT_MM * 1.15
    topo = (y0 + y1) / 2 - passo * (len(itens) - 1) / 2
    for i, (s, estilo) in enumerate(itens):
        base = dict(kw)
        base.update(estilo)
        t = texto(ax, (x0 + x1) / 2, topo + i * passo, s, zorder=4, **base)
        _caixas.append((s, (x0, x1, topo + i * passo - passo / 2,
                            topo + i * passo + passo / 2 + 0.4), t))


def seta(ax, pontos, cor=COR_LINHA, sobre=False, espessura=0.8):
    z = 6 if sobre else 5
    xs, ys = zip(*pontos)
    if sobre:
        ax.plot(xs, ys, color="white", linewidth=3.0, solid_capstyle="butt",
                zorder=z - 0.5)
    if len(pontos) > 2:
        ax.plot(xs[:-1], ys[:-1], color=cor, linewidth=espessura,
                solid_joinstyle="miter", zorder=z)
    ax.add_patch(
        FancyArrowPatch(
            pontos[-2], pontos[-1], arrowstyle="-|>", mutation_scale=7,
            color=cor, linewidth=espessura, shrinkA=0, shrinkB=0, zorder=z,
        )
    )


def rotulo(ax, x, y, s, **kw):
    base = {"fontsize": FONTE_PT, "color": COR_SECUNDARIA, "style": "italic",
            "bbox": {"facecolor": "white", "edgecolor": "none", "pad": 0.5}, "zorder": 7}
    base.update(kw)
    return texto(ax, x, y, s, **base)


# --- Texto em arco -----------------------------------------------------------

def polar(r, theta):
    """Ponto a `r` mm do centro, no ângulo `theta` em graus, medido no sentido
    horário a partir do alto (0 = 12 h, 90 = 3 h)."""
    a = math.radians(theta)
    return CX + r * math.sin(a), CY - r * math.cos(a)


def _fonte(peso="normal", estilo="normal"):
    return FontProperties(family=_familia_disponivel(), weight=peso, style=estilo,
                          size=FONTE_PT)


def arco(ax, segmentos, r, theta, anel, cor=COR_TEXTO, tamanho=FONTE_PT,
         limites=None, janela=None):
    """Escreve uma linha de texto ao longo da circunferência de raio `r`,
    centrada no ângulo `theta`. `segmentos` é uma lista de (texto, peso,
    estilo), para misturar negrito e normal na mesma linha. Na metade de cima
    o texto corre no sentido horário e na de baixo no anti-horário, e nas duas
    se lê da esquerda para a direita. O contorno de cada glifo é dobrado sobre
    o arco, o que preserva o espaçamento das letras.

    `limites` = (r_min, r_max) do anel e `janela` = (theta_a, theta_b) do
    setor: a conferência reprova se o texto sair de um ou do outro."""
    esc = tamanho * PT_MM / tamanho  # unidades do TextPath (pt) para mm
    medidor = TextToPath()
    cima = math.cos(math.radians(theta)) >= -0.02
    x = 0.0
    partes = []
    for s, peso, estilo in segmentos:
        prop = _fonte(peso, estilo)
        prop.set_size(tamanho)
        w = medidor.get_text_width_height_descent(s, prop, ismath=False)[0]
        tp = TextPath((0, 0), s, size=tamanho, prop=prop)
        partes.append((x, tp))
        x += w
    largura = x * esc
    meio_vertical = 0.36 * tamanho * PT_MM  # meia altura das minúsculas e maiúsculas
    rs, ths = [], []
    for x0, tp in partes:
        vs = []
        for vx, vy in tp.vertices:
            u = (x0 + vx) * esc - largura / 2
            v = vy * esc - meio_vertical
            if cima:
                th, rr = theta + math.degrees(u / r), r + v
            else:
                th, rr = theta - math.degrees(u / r), r - v
            rs.append(rr)
            ths.append(th)
            vs.append(polar(rr, th))
        if len(vs):
            ax.add_patch(PathPatch(MplPath(vs, tp.codes), facecolor=cor, edgecolor="none",
                                   linewidth=0, zorder=4))
    rotulo_txt = "".join(s for s, _, _ in segmentos)
    if limites and rs:
        if min(rs) < limites[0] + 0.3 or max(rs) > limites[1] - 0.3:
            _problemas.append(f"{rotulo_txt!r}: raio {min(rs):.1f}–{max(rs):.1f} fora do "
                              f"anel {limites[0]:.1f}–{limites[1]:.1f}")
    if janela and ths:
        if min(ths) < janela[0] or max(ths) > janela[1]:
            _problemas.append(f"{rotulo_txt!r}: ângulo {min(ths):.0f}–{max(ths):.0f} fora "
                              f"do setor {janela[0]:.0f}–{janela[1]:.0f}")
    if janela:
        _setores.setdefault(anel, []).append((janela[0], janela[1], rotulo_txt))
    return largura


def bloco_em_arco(ax, anel, r0, r1, theta, janela, linhas_arco, cor=COR_TEXTO):
    """Duas (ou uma) linhas em arco num setor do anel entre `r0` e `r1`. A
    primeira linha fica do lado de fora na metade de cima e do lado de dentro
    na de baixo, para que a leitura desça sempre de uma linha para a outra."""
    cima = math.cos(math.radians(theta)) >= -0.02
    passo = FONTE_PT * PT_MM * 1.12
    meio = (r0 + r1) / 2
    n = len(linhas_arco)
    for i, segs in enumerate(linhas_arco):
        desloc = (n - 1) / 2 * passo - i * passo
        r = meio + desloc if cima else meio - desloc
        arco(ax, segs, r, theta, anel, cor=cor, limites=(r0, r1), janela=janela)


def N(s):
    return (s, "normal", "normal")


def B(s):
    return (s, "bold", "normal")


def I(s):
    return (s, "normal", "italic")


# --- Os anéis ----------------------------------------------------------------
# Conteúdo generalizado: os anéis dizem o papel de cada parte, sem
# nomes de pasta nem listas de regras; o detalhe fica na
# página do protótipo e em docs/arquitetura/VISAO_GERAL.md.

def desenhar_aneis(ax):
    for nome, r in (("infra", R_INFRA), ("aplicacao", R_APLICACAO),
                    ("regras", R_REGRAS), ("dominio", R_DOMINIO)):
        ax.add_patch(Circle((CX, CY), r, facecolor=TOM[nome], edgecolor=PETROLEO_ESCURO,
                            linewidth=0.9 if nome == "infra" else 0.7, zorder=1))


def desenhar_dominio(ax):
    """Centro, texto reto: as seis entidades e os quatro objetos de valor do
    texto, em dois blocos, e os contratos com as portas."""
    passo = FONTE_PT * PT_MM * 1.15
    meio_passo = passo * 0.55
    itens = [
        ("Domínio", {"fontweight": "bold", "fontsize": 9}), None,
        ("Empreendimento, Terreno,", {}),
        ("Edificação, Unidade tipo,", {}),
        ("Ambiente, Equipamento público", {}), None,
        ("Localização, Modelo BIM,", {}),
        ("Declarações, Medição", {}), None,
        ("contratos e portas", {"style": "italic"}),
    ]
    altura = sum(passo if i else meio_passo for i in itens)
    y = CY - altura / 2
    for item in itens:
        if item is None:
            y += meio_passo
            continue
        s, estilo = item
        base = {"color": "white", "zorder": 4}
        base.update(estilo)
        t = texto(ax, CX, y + passo / 2, s, **base)
        _caixas.append((s, ("circulo", R_DOMINIO - 0.8, y, y + passo), t))
        y += passo


def desenhar_regras(ax):
    r0, r1 = R_DOMINIO, R_REGRAS
    bloco_em_arco(ax, "regras", r0, r1, 0, (-45, 45),
                  [[("Regras", "bold", "normal")], [N("uma regra, um arquivo")]])
    bloco_em_arco(ax, "regras", r0, r1, 180, (140, 220),
                  [[N("requisitos da Portaria")]])


def desenhar_aplicacao(ax):
    r0, r1 = R_REGRAS, R_APLICACAO
    bloco_em_arco(ax, "aplicacao", r0, r1, 0, (-48, 48),
                  [[B("Aplicação")], [N("caso de uso da verificação")]])
    bloco_em_arco(ax, "aplicacao", r0, r1, 180, (138, 222),
                  [[N("execução ordenada das regras")],
                   [N("resolução do território")]])


def desenhar_infra(ax):
    r0, r1 = R_APLICACAO, R_INFRA
    bloco_em_arco(ax, "infra", r0, r1, 0, (-20, 20), [[B("Infraestrutura")]])
    bloco_em_arco(ax, "infra", r0, r1, 90, (55, 125), [[N("leitura do modelo IFC")]])
    bloco_em_arco(ax, "infra", r0, r1, 167, (135, 200), [[N("camadas geoespaciais")]])
    bloco_em_arco(ax, "infra", r0, r1, 233, (204, 262),
                  [[N("serviço de cálculo da")], [N("distância caminhável")]])
    bloco_em_arco(ax, "infra", r0, r1, 304, (266, 342),
                  [[N("persistência e exportação")]])


def desenhar_ferramentas(ax):
    """As ferramentas que cada adaptador envolve, encostadas por fora do anel
    externo, no setor do adaptador; não são anel do núcleo."""
    r = R_INFRA + 2.3
    lim = (R_INFRA, R_INFRA + 5.0)
    arco(ax, [I("IfcOpenShell")], r, 72, "ferramentas", cor=COR_SECUNDARIA,
         limites=lim, janela=(55, 90))
    arco(ax, [I("GeoPandas, Shapely e pyproj")], r, 130, "ferramentas",
         cor=COR_SECUNDARIA, limites=lim, janela=(106, 154))
    arco(ax, [I("OpenRouteService sobre OpenStreetMap")], r, 237, "ferramentas",
         cor=COR_SECUNDARIA, limites=lim, janela=(204, 270))


def desenhar_dependencias(ax):
    """Uma seta genérica por fronteira, sempre para dentro. Às 8 h, a
    aplicação depende das regras e as regras do domínio; às 4 h, a
    infraestrutura depende só do domínio e atravessa os anéis do meio."""
    th = 240
    seta(ax, [polar(R_APLICACAO - 1.2, th), polar(R_REGRAS - 1.0, th)])
    seta(ax, [polar(R_REGRAS - 1.2, th), polar(R_DOMINIO + 0.1, th)])
    th = 130
    seta(ax, [polar(R_INFRA - 1.2, th), polar(R_DOMINIO + 0.1, th)])


# --- Fora dos anéis ----------------------------------------------------------

def desenhar_interface(ax):
    y0, y1 = 2.0, 14.5
    sec = {"style": "italic", "color": COR_SECUNDARIA}
    caixa(ax, 1.0, 20.0, y0, y1, NEUTRO)
    linhas(ax, 1.0, 20.0, y0, y1, [("Visualizador", {"fontweight": "bold"}),
                                    ("3D", {"fontweight": "bold"}),
                                    ("CesiumJS", sec)])
    caixa(ax, 23.0, 44.0, y0, y1, NEUTRO)
    linhas(ax, 23.0, 44.0, y0, y1, [("Interface", {"fontweight": "bold"}),
                                     ("de uso", {"fontweight": "bold"}),
                                     ("Streamlit", sec)])
    caixa(ax, 48.0, 78.0, y0, y1, NEUTRO)
    linhas(ax, 48.0, 78.0, y0, y1, [("Camada de serviços", {"fontweight": "bold"}),
                                     ("único ponto", {}),
                                     ("de passagem", {})])
    seta(ax, [(44.0, 8.25), (48.0, 8.25)])
    seta(ax, [(78.0, 8.25), (82.0, 8.25)])


def desenhar_composicao(ax):
    x0, x1, y0, y1 = 82.0, 109.5, 2.0, 25.5
    caixa(ax, x0, x1, y0, y1, ("white", PETROLEO_ESCURO), espessura=1.1)
    linhas(ax, x0, x1, y0, y1, [
        ("Módulo de", {"fontweight": "bold", "color": PETROLEO_ESCURO}),
        ("composição", {"fontweight": "bold", "color": PETROLEO_ESCURO}),
        ("fora dos anéis", {"style": "italic", "color": COR_SECUNDARIA}),
        ("monta, executa", {}),
        ("e grava", {}),
    ])
    # Para a aplicação, atravessando a infraestrutura, e para a infraestrutura.
    x = 85.5
    seta(ax, [(x, y1), (x, CY - math.sqrt(R_APLICACAO ** 2 - (x - CX) ** 2))])
    x = 100.0
    seta(ax, [(x, y1), (x, CY - math.sqrt(R_INFRA ** 2 - (x - CX) ** 2))])


def cilindro(ax, x0, x1, y0, y1, cores):
    preenchimento, contorno = cores
    h = 3.0
    ax.add_patch(Rectangle((x0, y0 + h / 2), x1 - x0, y1 - y0 - h, facecolor=preenchimento,
                           edgecolor="none", zorder=3))
    ax.plot((x0, x0), (y0 + h / 2, y1 - h / 2), color=contorno, linewidth=1.1, zorder=3.1)
    ax.plot((x1, x1), (y0 + h / 2, y1 - h / 2), color=contorno, linewidth=1.1, zorder=3.1)
    ax.add_patch(Ellipse(((x0 + x1) / 2, y1 - h / 2), x1 - x0, h, facecolor=preenchimento,
                         edgecolor=contorno, linewidth=1.1, zorder=2.9))
    ax.add_patch(Ellipse(((x0 + x1) / 2, y0 + h / 2), x1 - x0, h, facecolor=preenchimento,
                         edgecolor=contorno, linewidth=1.1, zorder=3.2))


def desenhar_artefatos(ax):
    x0, x1, y0, y1 = 0.8, 25.4, 21.0, 38.5
    cilindro(ax, x0, x1, y0, y1, ("white", COR_LINHA))
    linhas(ax, x0, x1, y0 + 2.6, y1, [
        ("Artefatos", {"fontweight": "bold"}),
        ("JSON, GeoJSON", {}),
        ("e 3D Tiles", {}),
    ])
    # Leitura sem reprocessar, pela interface e pelo visualizador autônomo.
    # A seta nasce na borda da tampa elíptica do cilindro, e não na linha do
    # topo do retângulo que a envolve, para tocar o cilindro também perto da
    # lateral.
    def tampa(x):
        a_, h_ = (x1 - x0) / 2, 1.5
        return y0 + h_ - h_ * math.sqrt(max(0.0, 1 - ((x - (x0 + x1) / 2) / a_) ** 2))
    seta(ax, [(10.5, tampa(10.5)), (10.5, 14.5)])
    seta(ax, [(24.6, tampa(24.6)), (24.6, 14.5)])
    rotulo(ax, 26.4, 17.9, "leitura sem reprocessar", ha="left")
    # Gravação atômica, a partir da persistência e da exportação.
    p = polar(R_INFRA, 300)
    seta(ax, [p, (p[0] - 3.0, p[1]), (p[0] - 3.0, y1 + 0.2)])
    rotulo(ax, 2.0, 46.5, "gravação\natômica", ha="left", bbox=None)


# --- Painel: o caminho de uma checagem ---------------------------------------

def _etiqueta(ax, x, y, nome, tons):
    """Quadradinhos na cor do anel onde a etapa roda, seguidos do nome."""
    for i, tom in enumerate(tons):
        ax.add_patch(Rectangle((x + i * 3.0, y - 1.1), 2.2, 2.2, facecolor=tom,
                               edgecolor=PETROLEO_ESCURO, linewidth=0.5, zorder=4))
    return texto(ax, x + len(tons) * 3.0 + 0.3, y, nome, ha="left", fontweight="bold",
                 color=PETROLEO_ESCURO, zorder=4)


def desenhar_painel(ax):
    x0, x1 = 117.5, 159.5
    t = texto(ax, (x0 + x1) / 2, 4.2, "Caminho de uma checagem", fontweight="bold",
              fontsize=8.5, color=PETROLEO_ESCURO)
    _caixas.append(("título do painel", (x0, x1, 2.0, 6.8), t))
    passo = FONTE_PT * PT_MM * 1.15
    etapas = [
        ("Composição", ["white"],
         ["monta o contexto e injeta", "as portas do domínio"]),
        ("Infraestrutura", [TOM["infra"]],
         ["lê o modelo IFC, as camadas", "e o georreferenciamento"]),
        ("Aplicação e regras", [TOM["aplicacao"], TOM["regras"]],
         ["executa as regras em ordem,", "cada uma isolada"]),
        ("Infraestrutura", [TOM["infra"]],
         ["grava os resultados como", "artefatos em formatos abertos"]),
        ("Interface", [NEUTRO[0]],
         ["mostra conforme, não", "conforme e não avaliável,", "com o motivo"]),
    ]
    y = 8.0
    vao = 3.6
    for i, (nome, tons, corpo) in enumerate(etapas):
        h = passo * (len(corpo) + 1) + 2.2
        caixa(ax, x0, x1, y, y + h, NEUTRO)
        t = _etiqueta(ax, x0 + 1.6, y + 1.1 + passo / 2, nome, tons)
        _caixas.append((nome, (x0, x1, y, y + h), t))
        for j, s in enumerate(corpo):
            yl = y + 1.1 + passo * (j + 1.5)
            t = texto(ax, x0 + 1.6, yl, s, ha="left", zorder=4)
            _caixas.append((s, (x0 + 1.2, x1 - 0.4, yl - passo / 2, yl + passo / 2 + 0.4), t))
        y += h
        if i < len(etapas) - 1:
            seta(ax, [((x0 + x1) / 2, y), ((x0 + x1) / 2, y + vao)])
            y += vao

    # Nota lateral: o que a figura afirma e o repositório verifica.
    y += 5.0
    ax.plot((x0, x1), (y - 2.5, y - 2.5), color=COR_GRADE_PAINEL, linewidth=0.6, zorder=2)
    nota = ["A dependência aponta sempre", "para dentro e testes",
            "automatizados reprovam o", "código se um anel depender",
            "de outro mais externo ou se a", "interface acessar o núcleo",
            "fora da camada de serviços."]
    for j, s in enumerate(nota):
        yl = y + passo * (j + 0.5)
        t = texto(ax, x0 + 0.3, yl, s, ha="left", style="italic", color=COR_SECUNDARIA,
                  zorder=4)
        _caixas.append((s, (x0, x1, yl - passo / 2, yl + passo / 2 + 0.4), t))
    y += passo * len(nota)
    if y > ALTURA - 0.5:
        _problemas.append(f"painel termina em y={y:.1f} mm, abaixo da figura")


# --- Conferência --------------------------------------------------------------

def conferir_transbordo(fig):
    """Falha se algum texto sair da sua caixa (folga de 0,4 mm), do círculo do
    domínio, do anel ou do setor; ou se dois setores do mesmo anel se
    sobrepuserem."""
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    esc = 25.4 / DPI
    problemas = list(_problemas)
    for s, geo, t in _caixas:
        bb = t.get_window_extent(r)
        w, h = bb.width * esc, bb.height * esc
        if geo[0] == "circulo":
            _, raio, ya, yb = geo
            # cantos da linha, em mm, a partir do centro do círculo
            xc = w / 2
            for yy in (ya + 0.3, yb - 0.3):
                if math.hypot(xc, yy - CY) > raio:
                    problemas.append(f"{s!r}: {w:.1f} mm de largura sai do domínio")
                    break
            continue
        x0, x1, y0, y1 = geo
        if w > (x1 - x0) - 0.8 or h > (y1 - y0) - 0.4:
            problemas.append(f"{s!r}: texto {w:.1f}×{h:.1f} mm em caixa "
                             f"{x1 - x0:.1f}×{y1 - y0:.1f} mm")
    for anel, setores in _setores.items():
        unicos = sorted({(a, b) for a, b, _ in setores})
        for (a0, b0), (a1, b1) in zip(unicos, unicos[1:]):
            if a1 < b0:
                problemas.append(f"setores sobrepostos no anel {anel}: "
                                 f"{a0:.0f}–{b0:.0f} e {a1:.0f}–{b1:.0f}")
    return problemas


def gerar(destino: Path = DESTINO) -> list[Path]:
    _caixas.clear()
    _problemas.clear()
    _setores.clear()
    fig, ax = _configurar()
    desenhar_aneis(ax)
    desenhar_dominio(ax)
    desenhar_regras(ax)
    desenhar_aplicacao(ax)
    desenhar_infra(ax)
    desenhar_ferramentas(ax)
    desenhar_dependencias(ax)
    desenhar_interface(ax)
    desenhar_composicao(ax)
    desenhar_artefatos(ax)
    desenhar_painel(ax)
    problemas = conferir_transbordo(fig)
    if problemas:
        raise SystemExit("Texto transbordando:\n  " + "\n  ".join(problemas))
    destino.mkdir(parents=True, exist_ok=True)
    svg = destino / f"{NOME}.svg"
    png = destino / f"{NOME}.png"
    fig.savefig(svg, format="svg", metadata={"Date": None, "Creator": None})
    fig.savefig(png, format="png", dpi=DPI, facecolor="white",
                metadata={"Software": None})
    return [svg, png]


if __name__ == "__main__":
    destino = Path(sys.argv[1]) if len(sys.argv) > 1 else DESTINO
    for caminho in gerar(destino):
        print(caminho)
