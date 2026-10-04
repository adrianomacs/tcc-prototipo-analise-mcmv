"""Unidades do modelo IFC — fonte única de conversão (condição inicial sempre checada).

Centraliza a conversão de unidades para evitar erros de escala espalhados pelo
código. Dois aprendizados que motivaram este módulo (achados em testes com
modelos em milímetros):

* **Geometria via ``ifcopenshell.geom.create_shape`` já vem em METROS (SI)**,
  independentemente da unidade de comprimento do arquivo. Portanto geometria
  **não** deve ser reescalada — usar as coordenadas como estão.
* **Atributos brutos e quantidades estão nas unidades do projeto**: valores como
  ``IfcSite.RefElevation`` estão na LENGTHUNIT e ``Qto_SpaceBaseQuantities.
  NetFloorArea`` está na AREAUNIT. Cada um converte com a escala da SUA unidade
  — a área **não** é "comprimento²" quando as unidades divergem (ex.: comprimento
  em milímetro, área em metro quadrado).

Todas as funções degradam para 1.0 quando a informação de unidade é
indisponível (nunca levantam), para não interromper o fluxo.
"""

from __future__ import annotations

from typing import Any


def escala_comprimento(modelo: Any) -> float:
    """Metros por unidade de comprimento do projeto (LENGTHUNIT). 1.0 se indisponível.

    Aplicar a atributos brutos de comprimento (ex.: ``RefElevation``). NÃO aplicar
    à geometria do ``create_shape``, que já vem em metros.
    """
    try:
        import ifcopenshell.util.unit as uu
        return float(uu.calculate_unit_scale(modelo))
    except Exception:
        return 1.0


def escala_area(modelo: Any) -> float:
    """Metros quadrados por unidade de área do projeto (AREAUNIT). 1.0 se indisponível.

    Aplicar a quantidades de área (ex.: ``NetFloorArea``). Quando a AREAUNIT não é
    declarada, o IFC assume comprimento²; nesse caso, usa-se ``escala_comprimento²``
    como aproximação de recurso.
    """
    try:
        import ifcopenshell.util.unit as uu
        return float(uu.calculate_unit_scale(modelo, "AREAUNIT"))
    except Exception:
        pass
    try:
        s = escala_comprimento(modelo)
        return s * s
    except Exception:
        return 1.0


def multiplicador_prefixo(prefixo) -> float:
    """Multiplicador SI de um prefixo de unidade (ex.: 'MILLI' -> 0.001). 1.0 se ausente."""
    try:
        import ifcopenshell.util.unit as uu
        return float(uu.get_prefix_multiplier(prefixo))
    except Exception:
        return 1.0


def resumo(modelo: Any) -> dict:
    """Resumo legível das unidades e escalas — útil para checagem/log na ingestão."""
    info: dict[str, Any] = {"escala_comprimento_m": escala_comprimento(modelo),
                            "escala_area_m2": escala_area(modelo),
                            "length_unit": None, "area_unit": None}
    try:
        import ifcopenshell.util.unit as uu
        lu = uu.get_project_unit(modelo, "LENGTHUNIT")
        au = uu.get_project_unit(modelo, "AREAUNIT")
        info["length_unit"] = _rotulo_unidade(lu)
        info["area_unit"] = _rotulo_unidade(au)
    except Exception:
        pass
    return info


def _rotulo_unidade(u) -> str | None:
    if u is None:
        return None
    prefixo = getattr(u, "Prefix", None) or ""
    nome = getattr(u, "Name", None) or ""
    return (f"{prefixo}{nome}".strip() or None)
