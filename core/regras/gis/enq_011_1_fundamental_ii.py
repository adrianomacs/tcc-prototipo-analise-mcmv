"""ENQ-011.1 — ensino fundamental, anos finais, a até 1,5 km caminhável.

Alternativa **A** do requisito-pai ENQ-011. Mesmo limiar do Ciclo I, ciclo
diferente — e os dois **nunca** se somam: uma escola só de anos iniciais não
cobre este requisito, e é por isso que a fonte é a ``Tabela_Turma``
(``QT_TUR_FUND_AF``).

A separação entre .1 e .2 é a mesma do ENQ-010: aqui a alternativa por
distância; a por transporte público fica fora do recorte, e o pai agrega.
"""

from __future__ import annotations

from core.dominio import equipamentos as eq
from core.regras.base.distancia_equipamento import RegraDistanciaEquipamento
from core.regras.registro import registrar


@registrar
class ENQ0111(RegraDistanciaEquipamento):
    id = "ENQ-011.1"
    descricao = ("Alternativa A — distância caminhável ao ensino fundamental "
                 "Ciclo II (11 a 15 anos)")
    ciclo = eq.CICLO_FUND_II
    limiar_m = 1500.0
    parametro = {"limiar_m": 1500.0, "ciclo": eq.CICLO_FUND_II,
                 "metrica": "distância caminhável em rede"}
