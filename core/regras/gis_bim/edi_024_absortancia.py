"""EDI-024 — Absortância solar do telhado (Anexo III, Tab. 1, item 4.III.i).

Requisito-**pai** (ADR-026): o item da Portaria é escrito em dois ramos que a
zona bioclimática seleciona — EDI-024.1 (ZB 1, 2 e 3 → ≤ 0,6) e EDI-024.2
(ZB 4 a 8 → ≤ 0,4). Ele não mede nada: decide sobre os dois ramos em modo
``selecao_exclusiva``. Com um só ramo candidato, herda o veredito dele; com
os dois, decide a unanimidade, e **discordância é indecisão** (NÃO AVALIÁVEL,
``analise_humana_documental``), nunca reprovação.

Por que o telhado é sempre o caso de dois candidatos
---------------------------------------------------

A cláusula cita zonas "1, 2 e 3" e "4, 5, 6, 7 e 8" — o zoneamento da NBR
15220-3:2005, que a edição vigente não publica e a Portaria 489/2025 não
migrou. Não se traduz entre edições (DN-08): os dois ramos são candidatos em
**todo** município, e o que este pai conclui é o invariante à leitura —
absortância ≤ 0,4 é conforme sob qualquer zona, > 0,6 é não conforme sob
qualquer zona, e no meio o par discorda e o veredito fica declaradamente em
aberto. No dia em que a Portaria migrar a cláusula, o ramo indeterminado vira
determinado e este pai degenera sem mudar de estrutura.

Quem conta em conformidade e cobertura é **este** requisito (ADR-015/026); os
ramos são membros e ficam fora do denominador, como ENQ-010.1/010.2.

O ``ids_spec`` que esta regra declarava saiu: pelo ADR-007 a regra conclui
sozinha e reporta a informação ausente com motivo; o gancho ``ids_spec`` continua no executor, mas nenhuma regra
o declara.
"""

from __future__ import annotations

from core.dominio.contratos.regra import Dominio
from core.dominio.vocabulario import declaracoes as dec
from core.regras.base import agregacao as ag
from core.regras.registro import registrar


@registrar
class EDI024(ag.RegraAgregacao):
    id = "EDI-024"
    dominio = Dominio.GIS_BIM
    descricao = "Absortância solar do telhado compatível com a zona bioclimática"
    alvo = "resultados de EDI-024.1 e EDI-024.2"
    agrega = ["EDI-024.1", "EDI-024.2"]
    modo = ag.MODO_SELECAO_EXCLUSIVA
    rotulo_membro = "ramo(s)"
    ids_spec = None
    usa_visualizacao = True  # relatorio exibe os revestimentos no modelo
    aplicabilidade = {dec.TIPO_MODELO: dec.COM_EDIFICACAO}
    parametro = {
        "modo": ag.MODO_SELECAO_EXCLUSIVA,
        "ramos": {
            "EDI-024.1": "ZB 1, 2 e 3 (NBR 15220-3:2005): absortância <= 0,6",
            "EDI-024.2": "ZB 4, 5, 6, 7 e 8 (NBR 15220-3:2005): absortância <= 0,4",
        },
        "excecoes": "telha de barro não vitrificada; cobertura verde",
        "ref_portaria": "Anexo III, Tab. 1, item 4.III.i",
    }
