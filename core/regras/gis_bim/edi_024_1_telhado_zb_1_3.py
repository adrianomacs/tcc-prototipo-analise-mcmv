"""EDI-024.1 — Absortância do telhado, ramo ZB 1, 2 e 3: ≤ 0,6 (item 4.III.i.i).

Ramo do requisito-pai EDI-024 (ADR-026). Mecânica na base
``core/regras/base/absortancia.py``: população por ``classificacao_covering`` mais
``PredefinedType = ROOFING`` (ADR-027), exceções da Portaria pelo material
(DN-01), veredito sob o próprio limite e aplicabilidade pela zona.

``zonas`` fica vazio de propósito: a faixa "1, 2 e 3" está no zoneamento de
2005, que não se traduz para as doze classes vigentes (DN-08). O ramo é
candidato em todo município, sai NÃO AVALIÁVEL por aplicabilidade
indeterminada e entrega ao pai o veredito que teria sob ≤ 0,6.
"""

from __future__ import annotations

from core.regras.base import absortancia as base
from core.regras.registro import registrar


@registrar
class EDI0241(base.RamoAbsortancia):
    id = "EDI-024.1"
    descricao = "Absortância solar do telhado — ramo ZB 1, 2 e 3 (<= 0,6)"
    limite = 0.6
    zonas = ()                 # cláusula em vocabulário de 2005 (DN-08)
    zonas_texto = "1, 2 e 3"
    ref_portaria = "Anexo III, Tab. 1, item 4.III.i.i"
    familia = "cobertura"
    parametro = {"absortancia_max": 0.6, "propriedade": "AbsortanciaSolar",
                 "zonas_portaria": "1, 2 e 3",
                 "excecoes": "telha de barro não vitrificada; cobertura verde"}

    def populacao(self, leitura):
        return base.populacao_cobertura(leitura)
