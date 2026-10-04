"""ENQ-010 — acesso a escola de ensino fundamental, Ciclo I (6 a 10 anos).

Requisito-**pai** do item 3.b do Anexo I: a Portaria o satisfaz por qualquer de
duas alternativas, e a planilha-mãe registra isso na observação do analista —
*"Critério satisfeito por QUALQUER das alternativas"*. Ele não mede nada; decide
sobre ENQ-010.1 (distância caminhável) e ENQ-010.2 (transporte escolar).

O que este requisito demonstra, e que nenhuma das folhas demonstra
-----------------------------------------------------------------

Os dois membros são **heterogêneos**: um é geoprocessado com veredito próprio, o
outro é remetido a parecer humano porque o insumo não é público. A agregação por
limites tem de funcionar sobre essa mistura — e é a mistura, não o par de regras
de distância, que corresponde ao trabalho real do analista.

Consequência declarada: enquanto ENQ-010.2 for remetida, ``n_pot >= 1`` sempre, e
com ``k = 1`` a condição de reprovação (``n_pot < k``) é inalcançável. **Este
requisito pode ser aprovado, nunca reprovado.** Está no ``detalhe`` do resultado,
em ``reprovabilidade``, e há teste de regressão em ``xfail`` estrito para o dia em
que a alternativa B ganhar motor.
"""

from __future__ import annotations

from core.dominio.contratos.regra import Dominio
from core.regras.base import agregacao as ag
from core.regras.registro import registrar


@registrar
class ENQ010(ag.RegraAgregacao):
    id = "ENQ-010"
    dominio = Dominio.GIS
    descricao = "Acesso a escola de ensino fundamental — Ciclo I (6 a 10 anos)"
    alvo = "resultados de ENQ-010.1 e ENQ-010.2"
    agrega = ["ENQ-010.1", "ENQ-010.2"]
    modo = ag.MODO_QUALQUER
    parametro = {
        "modo": ag.MODO_QUALQUER,
        "alternativas": {
            "ENQ-010.1": "distância caminhável <= 1,5 km do centro do terreno",
            "ENQ-010.2": "transporte público escolar em tempo < 20 min",
        },
        "ref_portaria": "Anexo I, Tab. 1, item 3.b",
    }
