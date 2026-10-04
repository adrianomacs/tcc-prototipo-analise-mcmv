"""EDI-019 — Absortância solar das paredes externas (Anexo III, Tab. 1, item 4.II.a.x).

Requisito-**pai** (ADR-026): o item da Portaria é escrito em dois ramos que a
zona bioclimática seleciona — EDI-019.1 (ZB 1 e 2, R e M → ≤ 0,6) e EDI-019.2
(ZB 3 a 6, A e B → ≤ 0,4). Ele não mede nada: decide sobre os dois ramos em
modo ``selecao_exclusiva``, o mesmo que EDI-024 estreou.

Por que este pai é degenerado — e existe assim mesmo
----------------------------------------------------

Ao contrário do telhado, aqui a cláusula **foi migrada**: a redação da Portaria
489/2025 escreve as faixas no vocabulário vigente ("1 e 2 (R e M)", "3, 4, 5 e
6 (A e B)"), que **esgota as doze classes** da ABNT TR 15220-3-1:2024
(ADR-030). Logo a zona sempre seleciona exatamente um ramo: o candidato é
único, o pai herda o veredito dele e o outro sai NÃO AVALIÁVEL por não
aplicável. Não existe município brasileiro em que a parede fique sem limite —
e, portanto, não existe aqui o ``NAO_APLICAVEL`` por zona fora de faixa que o
telhado conhece.

Manter o pai mesmo sem necessidade é decisão registrada no ADR-026: as
quatro regras aparecem na mesma checagem, e uma assimetria de estrutura
entre parede e telhado teria de ser explicada ao leitor sem diferença normativa
que a justificasse. O caminho da unanimidade continua vivo no código, mas aqui
só se alcança quando a **zona não se resolve** — aí os dois ramos viram
candidatos e o pai conclui o que for invariante à leitura.

Quem conta em conformidade e cobertura é **este** requisito (ADR-015/026); os
ramos são membros e ficam fora do denominador.
"""

from __future__ import annotations

from core.dominio.contratos.regra import Dominio
from core.dominio.vocabulario import declaracoes as dec
from core.regras.base import agregacao as ag
from core.regras.registro import registrar


@registrar
class EDI019(ag.RegraAgregacao):
    id = "EDI-019"
    dominio = Dominio.GIS_BIM
    descricao = "Absortância solar das paredes externas compatível com a zona bioclimática"
    alvo = "resultados de EDI-019.1 e EDI-019.2"
    agrega = ["EDI-019.1", "EDI-019.2"]
    modo = ag.MODO_SELECAO_EXCLUSIVA
    rotulo_membro = "ramo(s)"
    ids_spec = None
    usa_visualizacao = True  # relatorio exibe os revestimentos no modelo
    aplicabilidade = {dec.TIPO_MODELO: dec.COM_EDIFICACAO}
    parametro = {
        "modo": ag.MODO_SELECAO_EXCLUSIVA,
        "ramos": {
            "EDI-019.1": "ZB 1 e 2 (R e M): absortância <= 0,6",
            "EDI-019.2": "ZB 3, 4, 5 e 6 (A e B): absortância <= 0,4",
        },
        "excecoes": "nenhuma — 4.II.a.x não excetua material",
        "ref_portaria": "Anexo III, Tab. 1, item 4.II.a.x",
    }
