"""EDI-024.2 — Absortância do telhado, ramo ZB 4 a 8: ≤ 0,4 (item 4.III.i.ii).

Ramo do requisito-pai EDI-024 (ADR-026); mesma mecânica de EDI-024.1 pela base
``core/regras/base/absortancia.py`` (população ADR-027, exceções DN-01), com o
limite deste ramo. ``zonas`` vazio pelo mesmo motivo: "4, 5, 6, 7 e 8" é
zoneamento de 2005 e a edição vigente não tem zona 7 nem 8 (DN-08) —
candidato em todo município, aplicabilidade indeterminada, veredito sob ≤ 0,4
entregue ao pai.
"""

from __future__ import annotations

from core.regras.base import absortancia as base
from core.regras.registro import registrar


@registrar
class EDI0242(base.RamoAbsortancia):
    id = "EDI-024.2"
    descricao = "Absortância solar do telhado — ramo ZB 4, 5, 6, 7 e 8 (<= 0,4)"
    limite = 0.4
    zonas = ()                 # cláusula em vocabulário de 2005 (DN-08)
    zonas_texto = "4, 5, 6, 7 e 8"
    ref_portaria = "Anexo III, Tab. 1, item 4.III.i.ii"
    familia = "cobertura"
    parametro = {"absortancia_max": 0.4, "propriedade": "AbsortanciaSolar",
                 "zonas_portaria": "4, 5, 6, 7 e 8",
                 "excecoes": "telha de barro não vitrificada; cobertura verde"}

    def populacao(self, leitura):
        return base.populacao_cobertura(leitura)
