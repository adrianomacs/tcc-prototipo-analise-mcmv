"""Classificação de `IfcCovering` — pelo hospedeiro ou, sem ele, pelo próprio covering.

Defeito que este helper existe para consertar: a primeira versão de
`core/regras/gis_bim/edi_024_absortancia.py` (ADR-005) fazia `elementos_por_tipo(
modelo, "IfcCovering")` sem discriminar hospedeiro nenhum — contava o
revestimento de uma parede interna como se fosse telhado. Hoje os ramos
EDI-024.1/024.2 consomem este helper pela base `core/regras/base/absortancia.py`
(ADR-026/027). A absortância é propriedade do
ACABAMENTO (`IfcCovering`), mas o requisito normativo distingue parede externa
de cobertura: quem decide o lado é o elemento HOSPEDEIRO, não o covering em
si. Este módulo só particiona; não decide conformidade nenhuma (isso segue
sendo o `checar()` de cada regra, ADR-005).

Anel `infra/`, não `regras/` — a fronteira pragmática que a limitação 1 da
`VISAO_GERAL.md` §7 já declara (o anel `regras/` importa dos *helpers* de
`infra/ifc/`) e que este módulo usa, sem ampliá-la (ADR-002).

Critério, em duas vias — a do hospedeiro, quando a relação existe, e a da
declaração do próprio covering, quando não existe (emenda ao ADR-027):

1. **Pelo hospedeiro**, via `IfcRelCoversBldgElements`
   (`RelatingBuildingElement` / `RelatedCoverings`):
   - hospedeiro `IfcWall` (a hierarquia do IfcOpenShell resolve subtipos como
     `IfcWallStandardCase` sozinha) → **parede**;
   - hospedeiro `IfcRoof` → **cobertura**;
   - hospedeiro `IfcSlab` é AMBÍGUO — a mesma classe representa piso e laje de
     cobertura — e o desempate é o `PredefinedType` do PRÓPRIO COVERING (não do
     hospedeiro): `ROOFING` → cobertura, `CLADDING` → parede;
   - hospedeiro de outra classe, relação sem hospedeiro declarado, ou
     `IfcSlab` cujo covering não traz `PredefinedType` conclusivo → **NÃO
     CLASSIFICADO** (o hospedeiro existe e contradiz o lado; a declaração do
     covering não o sobrepõe).
2. **Pelo próprio covering**, quando NÃO há relação nenhuma (covering órfão):
   o `PredefinedType` decide o lado — `ROOFING` → **cobertura**, `CLADDING` →
   **parede** —; qualquer outro valor (ausente, `NOTDEFINED`, `USERDEFINED`,
   `CEILING`, …) → **NÃO CLASSIFICADO**. Esta via existe porque o ADR-027 já
   reconhecia que Revit e Archicad raramente autoram a relação, e o estudo de
   caso do Estrela I confirmou (E3: 125 coverings com `IsExternal` e
   `AbsortanciaSolar` declarados, zero `IfcRelCoversBldgElements`): sem ela,
   o requisito de informação seria inatingível por quem o cumpre.

O `PredefinedType` é lido pela regra do IFC4: o da ocorrência quando declarado
(e diferente de `NOTDEFINED`); senão, o do tipo (`IsTypedBy` →
`RelatingType.PredefinedType`). O Revit grava `ROOFING` no `IfcCoveringType` e
`$` na ocorrência — ler só a ocorrência perdia o telhado mesmo com hospedeiro.

O lado nunca é deduzido por geometria nem por nome (ADR-027); a partição diz,
covering a covering, por qual via o lado foi resolvido (`origem`), para o
relatório distinguir "o modelo declarou" de "a relação disse".

A partição vem acompanhada do mapa ``{covering: hospedeiro}``: o lado responde
"parede ou cobertura", mas a externalidade exigida pelo EDI-019 é propriedade
do `IfcWall` hospedeiro (ADR-027), e quem a confere precisa do elemento, não
só da categoria.

O não classificado é sempre REPORTADO, nunca atribuído a um lado por padrão:
atribuir por omissão fabricaria falso conforme — a mesma razão, aqui, que já
governa `Regra.nao_avaliavel` (ADR-006/022) para o restante do motor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CoveringsPorHospedeiro:
    """Partição de `IfcCovering` pelo hospedeiro — ver a docstring do módulo
    para o critério completo. `nao_classificado` nunca é descartado."""
    parede: list[Any] = field(default_factory=list)
    cobertura: list[Any] = field(default_factory=list)
    nao_classificado: list[Any] = field(default_factory=list)
    # ``{covering: hospedeiro}`` dos que TÊM relação. Existe para quem precisa
    # ler propriedade do HOSPEDEIRO e não só saber o lado — é o caso da
    # externalidade da parede (ADR-027): `Pset_WallCommon.IsExternal` é do
    # `IfcWall`, e sem o hospedeiro em mãos não há como conferi-la contra o
    # que o covering declara. Covering órfão não entra no mapa.
    hospedeiro: dict[Any, Any] = field(default_factory=dict)
    # ``{covering: ORIGEM_HOSPEDEIRO | ORIGEM_PREDEFINIDO}`` dos classificados —
    # por qual via o lado foi resolvido. Não classificado não entra.
    origem: dict[Any, str] = field(default_factory=dict)


ORIGEM_HOSPEDEIRO = "hospedeiro"
ORIGEM_PREDEFINIDO = "predefinido"


def classificar_por_hospedeiro(modelo: Any) -> CoveringsPorHospedeiro:
    """Particiona todo `IfcCovering` do modelo em parede / cobertura / não
    classificado: pelo elemento que o hospeda (`IfcRelCoversBldgElements`)
    quando a relação existe, senão pelo `PredefinedType` do próprio covering
    (ver a docstring do módulo). O nome da função é histórico (B2)."""
    from core.infra.ifc.leitor_modelo import elementos_por_tipo

    coverings = elementos_por_tipo(modelo, "IfcCovering")
    if not coverings:
        return CoveringsPorHospedeiro()

    hospedeiro_de = _mapa_hospedeiros(modelo)

    parede: list[Any] = []
    cobertura: list[Any] = []
    nao_classificado: list[Any] = []
    origem: dict[Any, str] = {}
    for covering in coverings:
        if covering in hospedeiro_de:
            categoria = _categoria(covering, hospedeiro_de[covering])
            via = ORIGEM_HOSPEDEIRO
        else:
            categoria = _categoria_pelo_predefinido(covering)
            via = ORIGEM_PREDEFINIDO
        if categoria == "parede":
            parede.append(covering)
            origem[covering] = via
        elif categoria == "cobertura":
            cobertura.append(covering)
            origem[covering] = via
        else:
            nao_classificado.append(covering)

    return CoveringsPorHospedeiro(parede=parede, cobertura=cobertura,
                                  nao_classificado=nao_classificado,
                                  hospedeiro=hospedeiro_de, origem=origem)


def predefinido(covering: Any) -> str | None:
    """O `PredefinedType` do covering pela regra do IFC4: o da ocorrência
    quando declarado (e não `NOTDEFINED`); senão, o do tipo que a tipifica
    (`IsTypedBy[0].RelatingType.PredefinedType`). `None` quando nenhum dos
    dois diz nada. Tolera entidades falsas sem `IsTypedBy`."""
    proprio = getattr(covering, "PredefinedType", None)
    if proprio not in (None, "", "NOTDEFINED"):
        return str(proprio)
    try:
        for rel in getattr(covering, "IsTypedBy", None) or []:
            tipo = getattr(rel, "RelatingType", None)
            do_tipo = getattr(tipo, "PredefinedType", None)
            if do_tipo not in (None, "", "NOTDEFINED"):
                return str(do_tipo)
    except Exception:
        pass
    return None


def _categoria_pelo_predefinido(covering: Any) -> str | None:
    """``"parede"`` | ``"cobertura"`` | `None` para UM covering ÓRFÃO, pelo
    que ele mesmo declara: `ROOFING` → cobertura; `CLADDING` → parede; o
    resto não é lado nenhum."""
    tipo = predefinido(covering)
    if tipo == "ROOFING":
        return "cobertura"
    if tipo == "CLADDING":
        return "parede"
    return None


def _mapa_hospedeiros(modelo: Any) -> dict[Any, Any]:
    """``{covering: hospedeiro}`` a partir de todo `IfcRelCoversBldgElements`
    do modelo. Um covering ÓRFÃO (sem relação nenhuma) simplesmente não entra
    no mapa: `.get()` devolve `None`, e `_categoria` reporta como não
    classificado — órfão nunca é confundido com "hospedeiro reconhecido"."""
    from core.infra.ifc.leitor_modelo import elementos_por_tipo

    mapa: dict[Any, Any] = {}
    for rel in elementos_por_tipo(modelo, "IfcRelCoversBldgElements"):
        hospedeiro = getattr(rel, "RelatingBuildingElement", None)
        for covering in getattr(rel, "RelatedCoverings", None) or []:
            mapa[covering] = hospedeiro
    return mapa


def _categoria(covering: Any, hospedeiro: Any) -> str | None:
    """``"parede"`` | ``"cobertura"`` | `None` (não classificado) para UM
    covering, dado o hospedeiro já resolvido (ou `None`, se órfão)."""
    if hospedeiro is None:
        return None

    def hospedeiro_e(tipo: str) -> bool:
        is_a = getattr(hospedeiro, "is_a", None)
        return callable(is_a) and bool(is_a(tipo))

    if hospedeiro_e("IfcWall"):
        return "parede"
    if hospedeiro_e("IfcRoof"):
        return "cobertura"
    if hospedeiro_e("IfcSlab"):
        # IfcSlab sozinho não decide piso x laje de cobertura (mesma classe
        # nas duas situações) — o desempate é o PredefinedType do COVERING.
        return _categoria_pelo_predefinido(covering)
    return None
