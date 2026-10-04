"""Gera a figura do fluxo idealizado para as fases de enquadramento
do terreno e de análise do empreendimento, em SVG e PNG.

A mesma figura sai em PNG a 300 dpi e na página "Fluxo
Idealizado" do protótipo (SVG), por isso é desenhada por código e versionada
com o repositório. Três raias de atores (parte contratante, proponente e
analista) ficam acima, cortadas pelas duas fases. O protótipo fica abaixo,
destacado das raias e das fases, com as quatro etapas da verificação
automatizada, porque atende às duas fases e não pertence a nenhuma delas; os
atores o alimentam e recebem dele o retorno. O IDS fica com a parte
contratante, fora do protótipo, e é consumido pelo proponente (ADR-007); a
saída traz os três estados do resultado (ADR-006).

Uso, na raiz do repositório (exige o extra de desenvolvimento, que traz o
matplotlib):

    pip install -e ".[dev]"
    python scripts/gerar_figura1.py

Saída em docs/figuras/figura1_fluxo_idealizado.svg e .png. O resultado é
determinístico na mesma máquina (sal fixo do SVG, sem data nos metadados); a
fonte é Arial, ou Liberation Sans, de mesmas métricas, onde o Arial não
existir. O script confere, ao final, que nenhum texto transborda da sua caixa.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib as mpl
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle

RAIZ = Path(__file__).resolve().parents[1]
DESTINO = RAIZ / "docs" / "figuras"
NOME = "figura1_fluxo_idealizado"

# Geometria em milímetros, origem no canto superior esquerdo (y cresce para
# baixo). Largura útil de 16 cm.
# Geometria em milímetros, origem no canto superior esquerdo (y cresce para
# baixo). Largura útil de 16 cm.
LARGURA, ALTURA = 160.0, 119.2
Y_TOPO = 6.5  # as coordenadas começam aqui; o cabeçalho ocupa só a linha das fases
DPI = 300
FONTE_PT = 8

# Colunas: rótulos, requisitos (antes das fases), enquadramento e análise.
X_ROTULO = 7.0
X_ENQ = 36.0  # início da fase de enquadramento
X_ANA = 98.0  # início da fase de análise (seleção da proposta)

# Raias de atores (topo, base) e o bloco do protótipo, destacado abaixo delas.
RAIA_CONTRATANTE = (11.0, 41.0)
RAIA_PROPONENTE = (41.0, 66.0)
RAIA_ANALISTA = (66.0, 85.0)
BLOCO_PROTOTIPO = (92.0, 120.0)

# Cores: um neutro só para todas as ações dos atores (inclusive o IDS), o
# azul-petróleo escuro para o protótipo e contorno forte para o marco entre as
# fases. As bases públicas entram como rótulo da seta que chega à etapa (2). As cores de
# domínio (GIS/BIM) ficam na Tabela 1 e no Passo 1, onde são explicadas.
NEUTRO = ("#f1f5f9", "#475569")
MARCO = ("#ffffff", "#0f172a")
PROTOTIPO = ("#155e75", "#0e4a5c")
FUNDO_PROTOTIPO = "#eef5f7"
BARRA_PROTOTIPO = "#cfe2e8"
COR_TEXTO = "#0f172a"
COR_SECUNDARIA = "#475569"
COR_LINHA = "#334155"
COR_GRADE = "#cbd5e1"

_caixas: list[tuple[str, tuple[float, float, float, float], object]] = []


def _configurar():
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Liberation Sans", "DejaVu Sans"],
            "font.size": FONTE_PT,
            "svg.fonttype": "path",
            "svg.hashsalt": "figura1-fluxo-idealizado",
            "path.simplify": False,
        }
    )
    fig = Figure(figsize=(LARGURA / 25.4, ALTURA / 25.4), dpi=DPI)
    FigureCanvasAgg(fig)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, LARGURA)
    ax.set_ylim(Y_TOPO + ALTURA, Y_TOPO)
    ax.axis("off")
    return fig, ax


def texto(ax, x, y, s, **kw):
    base = {"fontsize": FONTE_PT, "color": COR_TEXTO, "ha": "center", "va": "center",
            "linespacing": 1.15}
    base.update(kw)
    return ax.text(x, y, s, **base)


def caixa(ax, x0, x1, y0, y1, cores, s, tracejada=False, espessura=0.9, **kw):
    """Caixa arredondada com o texto centrado; registra-se para a conferência
    de transbordo no fim."""
    preenchimento, contorno = cores
    ax.add_patch(
        FancyBboxPatch(
            (x0, y0), x1 - x0, y1 - y0,
            boxstyle="round,pad=0,rounding_size=1.2",
            facecolor=preenchimento, edgecolor=contorno, linewidth=espessura,
            linestyle=(0, (3, 1.6)) if tracejada else "solid", zorder=3,
        )
    )
    t = texto(ax, (x0 + x1) / 2, (y0 + y1) / 2, s, zorder=4, **kw)
    _caixas.append((s, (x0, x1, y0, y1), t))
    return t


def decisao(ax, cx, cy, r=4.2):
    """Losango de decisão (pendências?), no neutro."""
    ax.add_patch(Polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)],
                         closed=True, facecolor=NEUTRO[0], edgecolor=NEUTRO[1],
                         linewidth=0.9, zorder=3))


def seta(ax, pontos, sobre=False):
    """Seta ortogonal por uma lista de pontos; a ponta fica no último.

    `sobre=True` desenha um halo branco por baixo, para que a linha passe por
    cima de outra que ela cruza sem que as duas se confundam."""
    z = 6 if sobre else 5
    xs, ys = zip(*pontos)
    if sobre:
        ax.plot(xs[:-1], ys[:-1], color="white", linewidth=3.0, solid_capstyle="butt",
                zorder=z - 0.5)
    if len(pontos) > 2:
        ax.plot(xs[:-1], ys[:-1], color=COR_LINHA, linewidth=0.8,
                solid_joinstyle="miter", zorder=z)
    ax.add_patch(
        FancyArrowPatch(
            pontos[-2], pontos[-1], arrowstyle="-|>", mutation_scale=7,
            color=COR_LINHA, linewidth=0.8, shrinkA=0, shrinkB=0, zorder=z,
        )
    )


def rotulo(ax, x, y, s, **kw):
    """Rótulo de seta, em itálico e com fundo branco para não brigar com a linha."""
    base = {"fontsize": FONTE_PT, "color": COR_SECUNDARIA, "style": "italic",
            "bbox": {"facecolor": "white", "edgecolor": "none", "pad": 0.5}, "zorder": 7}
    base.update(kw)
    return texto(ax, x, y, s, **base)

def desenhar_grade(ax):
    topo, base = RAIA_CONTRATANTE[0], RAIA_ANALISTA[1]
    ax.add_patch(Rectangle((0, topo), X_ROTULO, base - topo,
                           facecolor="#f8fafc", edgecolor="none", zorder=0))
    for y in (topo, RAIA_PROPONENTE[0], RAIA_ANALISTA[0], base):
        ax.plot((0, LARGURA), (y, y), color=COR_GRADE, linewidth=0.6, zorder=1)
    ax.plot((X_ROTULO, X_ROTULO), (topo, base), color=COR_GRADE, linewidth=0.6, zorder=1)
    for (y0, y1), nome in (
        (RAIA_CONTRATANTE, "parte\ncontratante"),
        (RAIA_PROPONENTE, "proponente"),
        (RAIA_ANALISTA, "analista"),
    ):
        t = texto(ax, X_ROTULO / 2, (y0 + y1) / 2, nome, rotation=90, fontweight="bold",
                  linespacing=1.0)
        _caixas.append((nome, (0.0, X_ROTULO, y0, y1), t))

    # Fases e as divisórias, que cortam só as raias dos atores.
    texto(ax, (X_ENQ + X_ANA) / 2, 8.9, "Enquadramento do terreno", fontweight="bold",
          fontsize=9.5)
    texto(ax, (X_ANA + LARGURA) / 2, 8.9, "Análise do empreendimento", fontweight="bold",
          fontsize=9.5)
    for x in (X_ENQ, X_ANA):
        ax.plot((x, x), (topo, base), color=COR_SECUNDARIA, linewidth=0.8,
                linestyle=(0, (4, 2)), zorder=2)


def desenhar_contratante(ax):
    caixa(ax, 11.0, 34.0, 13.5, 24.0, NEUTRO, "Base de\nrequisitos da\nPortaria")
    caixa(ax, 11.0, 34.0, 27.5, 34.8, NEUTRO, "Requisitos de\ninformação (IDS)")
    seta(ax, [(22.5, 24.0), (22.5, 27.5)])
    rotulo(ax, 24.0, 25.8, "vira", ha="left")

    caixa(ax, 50.0, 74.0, 14.0, 25.0, NEUTRO, "Informa os\nresultados\nao MCID")
    caixa(ax, 128.0, 151.0, 14.0, 25.0, NEUTRO, "Publicação dos\nresultados e\ncontratação")

    # Elo entre as fases: o MCID publica a seleção das propostas.
    caixa(ax, 83.0, 113.0, 16.2, 22.8, MARCO, "seleção das propostas\n(portaria do MCID)",
          espessura=1.3)
    seta(ax, [(74.0, 19.5), (83.0, 19.5)])
    seta(ax, [(113.0, 19.5), (125.0, 19.5), (125.0, 46.0)])
    rotulo(ax, 123.5, 30.0, "proposta\nselecionada", ha="right")


def desenhar_proponente(ax):
    caixa(ax, 38.5, 72.0, 44.0, 62.5, NEUTRO,
          "Disponibiliza informações\npara o enquadramento\n(poligonal do terreno por\n"
          "matrícula, implantação\nou levantamento)")
    caixa(ax, 102.0, 136.0, 46.0, 58.5, NEUTRO,
          "Disponibiliza informações\npara a análise (modelos\nIFC e dados declarados)")
    # As duas entregas consomem os requisitos de informação (IDS).
    ax.plot((50.0, 50.0), (44.0, 39.8), color=COR_LINHA, linewidth=0.8, zorder=5)
    ax.plot((106.0, 106.0), (46.0, 39.8), color=COR_LINHA, linewidth=0.8, zorder=5)
    seta(ax, [(106.0, 39.8), (22.5, 39.8), (22.5, 34.8)])
    rotulo(ax, 78.0, 39.8, "consome")


def desenhar_analista(ax):
    cy = 75.0
    # Enquadramento.
    caixa(ax, 45.0, 73.0, 69.5, 80.5, NEUTRO,
          "Conferir o relatório\ne indicar o resultado\ndo enquadramento")
    seta(ax, [(73.0, cy), (77.8, cy)])
    decisao(ax, 82.0, cy)
    rotulo(ax, 82.0, 82.6, "pendências?")
    seta(ax, [(82.0, cy - 4.2), (82.0, 53.0), (72.0, 53.0)])
    rotulo(ax, 83.4, 67.5, "sim", ha="left")
    seta(ax, [(86.2, cy), (92.0, cy), (92.0, 30.0), (68.0, 30.0), (68.0, 25.0)], sobre=True)
    rotulo(ax, 92.8, 58.0, "não", ha="left")
    seta(ax, [(42.0, 62.5), (42.0, BLOCO_PROTOTIPO[0] + 8.0)])
    rotulo(ax, 43.3, 83.0, "alimenta", ha="left")

    # Análise.
    caixa(ax, 108.0, 136.0, 69.5, 80.5, NEUTRO,
          "Conferir o relatório\ne indicar o resultado\nda análise")
    seta(ax, [(136.0, cy), (140.8, cy)])
    decisao(ax, 145.0, cy)
    rotulo(ax, 145.0, 82.6, "pendências?")
    seta(ax, [(145.0, cy - 4.2), (145.0, 52.0), (136.0, 52.0)])
    rotulo(ax, 146.4, 67.5, "sim", ha="left")
    seta(ax, [(149.2, cy), (155.5, cy), (155.5, 19.5), (151.0, 19.5)])
    rotulo(ax, 154.7, 36.0, "não", ha="right")
    seta(ax, [(104.0, 58.5), (104.0, 89.8), (71.0, 89.8), (71.0, BLOCO_PROTOTIPO[0] + 8.0)],
         sobre=True)
    rotulo(ax, 105.3, 63.0, "alimenta", ha="left")


def desenhar_prototipo(ax):
    y0, y1 = BLOCO_PROTOTIPO
    envelope = FancyBboxPatch((1.0, y0), 158.0, y1 - y0,
                              boxstyle="round,pad=0,rounding_size=2.0",
                              facecolor=FUNDO_PROTOTIPO, edgecolor=PROTOTIPO[1],
                              linewidth=1.2, zorder=1.2)
    ax.add_patch(envelope)
    # Barra de título na largura inteira do envelope: o nome vale para as
    # quatro etapas juntas, e não para a etapa que estiver embaixo dele.
    barra = Rectangle((1.0, y0), 158.0, 3.9, facecolor=BARRA_PROTOTIPO,
                      edgecolor="none", zorder=1.3)
    ax.add_patch(barra)
    barra.set_clip_path(envelope)
    ax.plot((1.0, 159.0), (y0 + 3.9, y0 + 3.9), color=PROTOTIPO[1], linewidth=0.6,
            zorder=1.4)
    texto(ax, 80.0, y0 + 2.0, "Protótipo", fontweight="bold", color=PROTOTIPO[1], zorder=1.5)
    e0, e1 = y0 + 8.0, y1 - 4.0
    etapas = (
        (3.5, 35.5, "(1) interpretação\ne estruturação\ndas regras"),
        (40.0, 75.0, "(2) preparação e\ningestão de dados"),
        (80.5, 115.0, "(3) execução pelo\nmotor de regras"),
        (120.5, 156.5, "(4) saída de dados\nconforme ·\nnão conforme ·\nnão avaliável"),
    )
    for x0, x1, s in etapas:
        caixa(ax, x0, x1, e0, e1, PROTOTIPO, s, color="white")
    meio = (e0 + e1) / 2
    for xa, xb in ((35.5, 40.0), (75.0, 80.5), (115.0, 120.5)):
        seta(ax, [(xa, meio), (xb, meio)])

    # Base de requisitos alimenta a interpretação das regras.
    seta(ax, [(11.0, 18.8), (9.8, 18.8), (9.8, e0)])
    rotulo(ax, 11.3, 58.0, "alimenta", ha="left")

    # Retorno da saída aos analistas das duas fases.
    seta(ax, [(124.0, e0), (124.0, 80.5)])
    seta(ax, [(150.0, e0), (150.0, 87.3), (59.0, 87.3), (59.0, 80.5)])
    rotulo(ax, 137.0, 87.3, "retorna")

    # Bases públicas, de fora das raias, alimentam a preparação dos dados;
    # ficam como rótulo da seta, sem caixa, para não gastar altura.
    seta(ax, [(57.5, y1 + 5.0), (57.5, e1)])
    rotulo(ax, 59.3, y1 + 3.3, "bases públicas (IBGE, INEP, OpenStreetMap, ABNT)",
           ha="left")


def conferir_transbordo(fig):
    """Falha se algum texto sair da caixa (folga mínima de 0,4 mm)."""
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    esc = 25.4 / DPI
    problemas = []
    for s, (x0, x1, y0, y1), t in _caixas:
        bb = t.get_window_extent(r)
        w, h = bb.width * esc, bb.height * esc
        if w > (x1 - x0) - 0.8 or h > (y1 - y0) - 0.4:
            problemas.append(f"{s!r}: texto {w:.1f}×{h:.1f} mm em caixa "
                             f"{x1 - x0:.1f}×{y1 - y0:.1f} mm")
    return problemas


def gerar(destino: Path = DESTINO) -> list[Path]:
    _caixas.clear()
    fig, ax = _configurar()
    desenhar_grade(ax)
    desenhar_contratante(ax)
    desenhar_proponente(ax)
    desenhar_analista(ax)
    desenhar_prototipo(ax)
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
