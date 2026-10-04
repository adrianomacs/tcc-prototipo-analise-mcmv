"""ENQ-011 — acesso a escola de ensino fundamental, Ciclo II (11 a 15 anos).

Requisito-**pai** do item 3.c do Anexo I, mesma mecânica do ENQ-010: satisfeito
por qualquer das duas alternativas, sem medir nada por conta própria.

A diferença em relação ao ENQ-010 está na alternativa B, e é normativa, não de
implementação: o item 3.c admite transporte escolar **ou coletivo** e manda
computar a caminhada até o embarque e após o desembarque (Redação dada pela
Portaria MCID nº 335, de 30 de março de 2026), enquanto o item 3.b fala apenas de
transporte escolar. Ver ``enq_011_2_transporte_escolar_ou_coletivo.py``.

O teto de reprovabilidade é o mesmo, pela mesma razão: com a alternativa B
remetida a parecer, este requisito pode ser aprovado e nunca reprovado.
"""

from __future__ import annotations

from core.dominio.contratos.regra import Dominio
from core.regras.base import agregacao as ag
from core.regras.registro import registrar


@registrar
class ENQ011(ag.RegraAgregacao):
    id = "ENQ-011"
    dominio = Dominio.GIS
    descricao = "Acesso a escola de ensino fundamental — Ciclo II (11 a 15 anos)"
    alvo = "resultados de ENQ-011.1 e ENQ-011.2"
    agrega = ["ENQ-011.1", "ENQ-011.2"]
    modo = ag.MODO_QUALQUER
    parametro = {
        "modo": ag.MODO_QUALQUER,
        "alternativas": {
            "ENQ-011.1": "distância caminhável <= 1,5 km do centro do terreno",
            "ENQ-011.2": "transporte público escolar ou coletivo em tempo "
                         "< 20 min, computada a caminhada até o embarque e "
                         "após o desembarque",
        },
        "ref_portaria": "Anexo I, Tab. 1, item 3.c",
    }
