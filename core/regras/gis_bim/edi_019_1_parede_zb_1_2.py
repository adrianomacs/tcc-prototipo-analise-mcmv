"""EDI-019.1 — Absortância da parede externa, ramo ZB 1 e 2: ≤ 0,6 (item 4.II.a.x.1).

Ramo do requisito-pai EDI-019 (ADR-026). Mecânica na base
``core/regras/base/absortancia.py``: população por ``classificacao_covering``
(hospedeiro ``IfcWall``) mais ``Pset_CoveringCommon.IsExternal`` do próprio
covering (ADR-027), veredito sob o próprio limite e aplicabilidade pela zona.

Duas diferenças em relação aos ramos de telhado, e as duas vêm do texto:

- ``zonas`` traz as classes de 2024 porque a faixa "1 e 2 (R e M)" **está** no
  vocabulário vigente (ADR-030) — a zona seleciona de verdade, e o ramo emite
  veredito próprio quando aplicável, em vez de sair sempre indeterminado.
- ``excecoes_por_material = False``: 4.II.a.x não excetua material nenhum
  (DN-02). A absortância declarada é o único canal; cor não é lida em lugar
  algum, e covering que declara valor acima do limite reprova o ramo.
"""

from __future__ import annotations

from core.dominio.conhecimento.zona_bioclimatica import CLASSES
from core.regras.base import absortancia as base
from core.regras.registro import registrar

# As doze classes da norma vigente repartem-se entre os dois ramos sem sobra
# (ADR-030): "1 e 2 (R e M)" aqui, "3 a 6 (A e B)" em EDI-019.2.
ZONAS_1_E_2 = tuple(c for c in CLASSES if c[0] in ("1", "2"))


@registrar
class EDI0191(base.RamoAbsortancia):
    id = "EDI-019.1"
    descricao = "Absortância solar das paredes externas — ramo ZB 1 e 2 (<= 0,6)"
    limite = 0.6
    zonas = ZONAS_1_E_2
    zonas_texto = "1 e 2 (R e M)"
    ref_portaria = "Anexo III, Tab. 1, item 4.II.a.x.1"
    familia = "parede externa"
    excecoes_por_material = False
    parametro = {"absortancia_max": 0.6, "propriedade": "AbsortanciaSolar",
                 "zonas_portaria": "1 e 2 (R e M)",
                 "excecoes": "nenhuma"}

    def populacao(self, leitura):
        return base.populacao_parede(leitura)
