"""ENQ-009 — escola de educação infantil a até 1 km caminhável do terreno.

Âncora do recorte: é o requisito que a base marca como *"Distância
caminhável (rede), não euclidiana"*, e o que o analista da CAIXA hoje confere à
mão no Google Maps.

**Creche OU pré-escola atendem**: a Portaria trata
a educação infantil como faixa única de 0 a 5 anos, ao contrário do fundamental,
cujos dois ciclos são requisitos distintos e jamais somados. A congruência é com
o texto normativo, não com a estrutura do dado — no microdado as duas etapas vêm
em colunas separadas (``QT_TUR_INF_CRE`` e ``QT_TUR_INF_PRE``), e é o adaptador
que as reúne num ciclo só.
"""

from __future__ import annotations

from core.dominio import equipamentos as eq
from core.regras.base.distancia_equipamento import RegraDistanciaEquipamento
from core.regras.registro import registrar


@registrar
class ENQ009(RegraDistanciaEquipamento):
    id = "ENQ-009"
    descricao = "Acesso a escola de educação infantil (0 a 5 anos)"
    ciclo = eq.CICLO_INFANTIL
    limiar_m = 1000.0
    parametro = {"limiar_m": 1000.0, "ciclo": eq.CICLO_INFANTIL,
                 "metrica": "distância caminhável em rede"}
