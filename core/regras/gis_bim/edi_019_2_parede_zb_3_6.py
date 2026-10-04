"""EDI-019.2 — Absortância da parede externa, ramo ZB 3 a 6: ≤ 0,4 (item 4.II.a.x.2).

Ramo do requisito-pai EDI-019 (ADR-026); mesma mecânica de EDI-019.1 pela base
``core/regras/base/absortancia.py`` — população com hospedeiro ``IfcWall`` e
``Pset_CoveringCommon.IsExternal`` (ADR-027), sem exceção por material
(DN-02) —, com o limite e a faixa deste ramo.

A faixa "3, 4, 5 e 6 (A e B)" está no vocabulário vigente (ADR-030) e, com a
de EDI-019.1, esgota as doze classes: junto com o ramo irmão, este ramo dá
limite à parede em todo município brasileiro.
"""

from __future__ import annotations

from core.dominio.conhecimento.zona_bioclimatica import CLASSES
from core.regras.base import absortancia as base
from core.regras.registro import registrar

ZONAS_3_A_6 = tuple(c for c in CLASSES if c[0] in ("3", "4", "5", "6"))


@registrar
class EDI0192(base.RamoAbsortancia):
    id = "EDI-019.2"
    descricao = "Absortância solar das paredes externas — ramo ZB 3, 4, 5 e 6 (<= 0,4)"
    limite = 0.4
    zonas = ZONAS_3_A_6
    zonas_texto = "3, 4, 5 e 6 (A e B)"
    ref_portaria = "Anexo III, Tab. 1, item 4.II.a.x.2"
    familia = "parede externa"
    excecoes_por_material = False
    parametro = {"absortancia_max": 0.4, "propriedade": "AbsortanciaSolar",
                 "zonas_portaria": "3, 4, 5 e 6 (A e B)",
                 "excecoes": "nenhuma"}

    def populacao(self, leitura):
        return base.populacao_parede(leitura)
