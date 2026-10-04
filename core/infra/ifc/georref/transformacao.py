"""Conversão de sistemas de coordenadas com pyproj.

Converte entre o sistema projetado (SIRGAS 2000 / UTM) e coordenadas
geográficas — etapa indispensável tanto para as checagens espaciais quanto para
o posicionamento do modelo na cena de visualização.
"""

from __future__ import annotations

from typing import Any


def transformador(epsg_origem: str, epsg_destino: str) -> Any:
    """Cria um Transformer pyproj entre dois sistemas de coordenadas."""
    from pyproj import Transformer

    return Transformer.from_crs(epsg_origem, epsg_destino, always_xy=True)


def projetado_para_geografico(x: float, y: float, epsg_projetado: str,
                              epsg_geografico: str = "EPSG:4674") -> tuple[float, float]:
    """Converte (E, N) projetado para (long, lat) geográfico (SIRGAS 2000)."""
    t = transformador(epsg_projetado, epsg_geografico)
    lon, lat = t.transform(x, y)
    return lon, lat

# ---------------------------------------------------------------------------
# Do sistema do MODELO para o sistema PROJETADO (IfcMapConversion)
# ---------------------------------------------------------------------------
# Peça que faltava no projeto: até aqui só havia projetado -> geográfico, que
# basta para posicionar a origem do modelo (âncora da visualização). Levar uma
# GEOMETRIA do modelo para o território exige compor a rotação com os offsets,
# e é disso que o Enquadramento depende para extrair a poligonal do IfcSite.
#
# Convenção do IFC (IfcMapConversion): o par (XAxisAbscissa, XAxisOrdinate) é o
# vetor do eixo +X do modelo expresso no sistema projetado. Ele NÃO é
# necessariamente unitário — vários exportadores gravam o vetor cru —, então é
# normalizado aqui; sem isso, um vetor de norma 2 dobraria todas as distâncias.
#
#     E = e0 + escala * (x * cos - y * sen)
#     N = n0 + escala * (x * sen + y * cos)
#
# Unidades: os offsets chegam JÁ EM METROS (o ``leitor_crs`` resolve a unidade
# do MapConversion, inclusive corrigindo exportador inconsistente pela área de
# uso do CRS) e a geometria do ``create_shape`` também vem em metros. Não há
# conversão a fazer aqui — e é exatamente por isso que ela não pode ser feita
# duas vezes.

def compor_modelo_para_projetado(map_conversion: dict) -> tuple[Any, dict]:
    """Devolve ``(transformar, procedencia)`` para levar (x, y) do modelo ao CRS projetado.

    ``transformar(x, y) -> (E, N)``. A ``procedencia`` registra o que foi de
    fato aplicado (offsets, rotação em graus, escala e eventuais avisos), para
    que o resultado possa ser auditado — e para se poder afirmar como a
    geometria foi posicionada.
    """
    import math

    mc = map_conversion or {}
    e0 = float(mc.get("eastings") or 0.0)
    n0 = float(mc.get("northings") or 0.0)

    xa = mc.get("x_axis_abscissa")
    xo = mc.get("x_axis_ordinate")
    avisos: list[str] = []

    if xa is None and xo is None:
        cos_t, sen_t = 1.0, 0.0
        avisos.append("MapConversion sem XAxisAbscissa/XAxisOrdinate: assumido "
                      "eixo X do modelo alinhado ao Leste (rotação zero).")
    else:
        xa = float(xa if xa is not None else 1.0)
        xo = float(xo if xo is not None else 0.0)
        norma = math.hypot(xa, xo)
        if norma == 0.0:
            cos_t, sen_t = 1.0, 0.0
            avisos.append("Vetor do eixo X do MapConversion é nulo: assumida "
                          "rotação zero.")
        else:
            cos_t, sen_t = xa / norma, xo / norma
            if abs(norma - 1.0) > 1e-6:
                avisos.append(f"Vetor do eixo X do MapConversion não era "
                              f"unitário (norma {norma:.6g}); normalizado antes "
                              "de aplicar a rotação.")

    escala = mc.get("scale")
    escala = 1.0 if escala in (None, 0) else float(escala)
    if abs(escala - 1.0) > 1e-9:
        avisos.append(f"Escala do MapConversion diferente de 1 ({escala:g}); "
                      "aplicada conforme a norma.")

    def transformar(x: float, y: float) -> tuple[float, float]:
        x, y = float(x), float(y)
        return (e0 + escala * (x * cos_t - y * sen_t),
                n0 + escala * (x * sen_t + y * cos_t))

    procedencia = {
        "metodo": "IfcMapConversion (rotação normalizada + offsets em metros)",
        "eastings": e0, "northings": n0,
        "rotacao_graus": math.degrees(math.atan2(sen_t, cos_t)),
        "escala": escala, "avisos": avisos,
    }
    return transformar, procedencia
