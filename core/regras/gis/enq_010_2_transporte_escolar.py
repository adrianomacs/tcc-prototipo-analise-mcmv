"""ENQ-010.2 — alternativa B do Ciclo I: transporte público **escolar**.

Texto do item 3.b, na Retificação publicada no DOU em 13/7/2023: *"…a uma
distância caminhável máxima de 1,5 km, computada a partir do centro do terreno;
**ou acessível por transporte público escolar em tempo inferior a 20 min**."*

O qualificador importa, e nos custou uma rodada de análise para enxergar
-----------------------------------------------------------------------

O item 3.b diz **escolar**; só o item 3.c (ENQ-011.2) admite "escolar ou
coletivo". Nossa base derivada havia achatado a diferença, dando aos dois o mesmo
parâmetro. A consequência é grande: transporte escolar não é linha de transporte
coletivo, é o itinerário do ônibus escolar municipal — dado administrativo da
secretaria de educação, contratado rota por rota. **Não existe em GTFS em lugar
nenhum**, e um roteador de transporte coletivo, ainda que existisse feed,
responderia a outra pergunta.

Por que não é avaliável, em quatro razões independentes
------------------------------------------------------

1. **O insumo não é público.** O itinerário do transporte escolar não é publicado
   como dado aberto; a comprovação costuma ser declaração ou documentação
   específica da Prefeitura, peça por peça.
2. **O provedor aberto não atende.** O perfil de transporte público do
   OpenRouteService não existe na API hospedada, exige instância própria com GTFS
   carregado e **não é suportado pelo endpoint de matriz**, que é onde toda a
   camada de medição do R5c se apoia.
3. **O parâmetro é tempo sobre rede dependente de horário.** A Portaria fixa os
   20 min e não nomeia horário de referência, dia nem frequência mínima. Produzir
   veredito exigiria eleger um instante como verdade — o mesmo defeito do fator de
   desvio, recusado por isso.
4. **A própria base já dizia.** ENQ-010.2 e ENQ-011.2 são as únicas linhas ENQ do
   recorte com "Julg. humano complementar: Sim".

Nenhuma delas é "não deu tempo". Ver ``core/regras/base/remessa.py``.
"""

from __future__ import annotations

from core.dominio.contratos.regra import Dominio
from core.dominio.vocabulario import motivos
from core.regras.base.remessa import RegraRemetida
from core.regras.registro import registrar


@registrar
class ENQ0102(RegraRemetida):
    id = "ENQ-010.2"
    # A planilha classifica como "GIS only": o MÉTODO é geoprocessável (isócrona
    # de transporte + caminhada). O que falta é o INSUMO, e as duas coisas não se
    # confundem — por isso o domínio declarado continua sendo o da planilha.
    dominio = Dominio.GIS
    descricao = ("Alternativa B — transporte público escolar até escola de "
                 "ensino fundamental Ciclo I (6 a 10 anos)")
    alvo = "itinerário do transporte público escolar municipal"
    remete_a = motivos.ANALISE_HUMANA_DOCUMENTAL
    insumo = "itinerário do transporte público escolar municipal"
    porque = ("O itinerário do transporte público ESCOLAR não é dado público: "
              "ele é administrado pela secretaria municipal de educação e a "
              "comprovação se dá por declaração ou documentação específica da "
              "Prefeitura. Não há base aberta, nacional ou municipal, que "
              "permita medir este tempo automaticamente.")
    fundamento = "Anexo I, Tab. 1, item 3.b (Retificação DOU 13/7/2023)"
    parametro = {
        "modal": "transporte público escolar",
        "tempo_maximo_min": 20,
        "computa_caminhada": False,  # a cláusula da caminhada é só do item 3.c
        "ref_portaria": "Anexo I, Tab. 1, item 3.b",
    }
