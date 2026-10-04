"""ENQ-010.1 — ensino fundamental, anos iniciais, a até 1,5 km caminhável.

Alternativa **A** do requisito-pai ENQ-010, que é satisfeito por qualquer de
suas alternativas. A alternativa B (transporte público) está fora do recorte, e o pai
entra por agregação.

Este requisito depende da ``Tabela_Turma``: o Catálogo de Escolas
informa "Ensino Fundamental" sem separar anos iniciais de anos finais, e
traduzir a etapa indistinta para os dois ciclos contaria como cobertura de anos
finais uma escola que só tem anos iniciais. A distinção vem da ``Tabela_Turma``
do Censo Escolar (``QT_TUR_FUND_AI``).
"""

from __future__ import annotations

from core.dominio import equipamentos as eq
from core.regras.base.distancia_equipamento import RegraDistanciaEquipamento
from core.regras.registro import registrar


@registrar
class ENQ0101(RegraDistanciaEquipamento):
    id = "ENQ-010.1"
    descricao = ("Alternativa A — distância caminhável ao ensino fundamental "
                 "Ciclo I (6 a 10 anos)")
    ciclo = eq.CICLO_FUND_I
    limiar_m = 1500.0
    parametro = {"limiar_m": 1500.0, "ciclo": eq.CICLO_FUND_I,
                 "metrica": "distância caminhável em rede"}
