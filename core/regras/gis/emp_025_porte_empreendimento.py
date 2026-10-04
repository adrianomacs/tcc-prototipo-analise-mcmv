"""EMP-025 — porte do empreendimento: limite individual E limite dos contíguos.

Requisito-**pai** do item 4.I.a do Anexo II. A norma exige os dois limites ao
mesmo tempo — o "e" normativo —, e por isso o pai agrega EMP-025.1 e EMP-025.2
em ``MODO_TODOS`` (ADR-015). É o primeiro pai do protótipo nesse modo: os do
Anexo I são "ou" (``MODO_QUALQUER``), os da absortância são seleção exclusiva
(ADR-026).

A aritmética, com ``k = 2``
---------------------------

* EMP-025.1 não conforme → ``n_pot = 1 < 2`` → **NÃO CONFORME**: exceder o
  limite individual reprova, haja contiguidade ou não.
* EMP-025.1 conforme e EMP-025.2 remetida → ``[1, 2]`` contra 2 → **NÃO
  AVALIÁVEL**, com a causa herdada da remessa.

É o teto da DN-04 virado do avesso: nos "ou" do Anexo I a alternativa
remetida impede a reprovação; aqui, num "e", impede a **aprovação**. O
requisito pode ser reprovado pela ferramenta, nunca aprovado. O
``detalhe["reprovabilidade"]`` diz, corretamente, ``reprovavel: True`` (um só
membro irredutível não alcança ``k = 2``); o teto simétrico — nunca aprovável —
ainda não é declarado no detalhe, e está registrado como débito em vez de
calculado aqui: o pai não escreve agregação própria (ADR-015).
"""

from __future__ import annotations

from core.dominio.contratos.regra import Dominio
from core.regras.base import agregacao as ag
from core.regras.registro import registrar


@registrar
class EMP025(ag.RegraAgregacao):
    id = "EMP-025"
    dominio = Dominio.GIS
    descricao = ("Número máximo de UH por empreendimento e por grupo de "
                 "empreendimentos contíguos, conforme o porte do município")
    alvo = "resultados de EMP-025.1 e EMP-025.2"
    agrega = ["EMP-025.1", "EMP-025.2"]
    modo = ag.MODO_TODOS
    rotulo_membro = "limite(s)"
    parametro = {
        "modo": ag.MODO_TODOS,
        "limites": {
            "EMP-025.1": "UH por empreendimento, pelo porte do município",
            "EMP-025.2": "UH do grupo de empreendimentos contíguos (≤ 1 km)",
        },
        "ref_portaria": "Anexo II, Tab. 1, item 4.I.a",
    }
