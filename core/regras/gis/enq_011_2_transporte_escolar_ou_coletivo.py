"""ENQ-011.2 — alternativa B do Ciclo II: transporte escolar **ou coletivo**.

Texto do item 3.c, na Redação dada pela Portaria MCID nº 335, de 30 de março de
2026: *"…ou acessível por **transporte público escolar ou coletivo** em tempo
inferior a 20 min, **considerando no cálculo o tempo de deslocamento por
caminhada até o ponto de embarque e após o desembarque**."*

Duas diferenças em relação ao ENQ-010.2, ambas normativas: aqui o **coletivo**
também serve, e aqui a **caminhada** até o embarque e após o desembarque entra na
conta. A cláusula da caminhada veio com a Redação 335/2026, que alterou o item 3.c
e não o 3.b — nossa base derivada havia propagado a cláusula para os dois.

Por que continua não avaliável, mesmo admitindo o coletivo
---------------------------------------------------------

Admitir o coletivo abre, em princípio, a via do GTFS; na prática ela não existe
para este trabalho:

1. **O feed não existe no município do estudo.** Estrela/RS tem transporte
   urbano e nenhum feed.
2. **No Brasil o feed é exceção.** O levantamento do ITDP ouviu 87 municípios
   (28,5% da população) e verificou publicação aberta de GTFS em **três**.
3. **O provedor aberto não atende ao endpoint que usamos.** O perfil de
   transporte público do OpenRouteService exige instância própria com GTFS e não
   é suportado pela matriz; as isócronas de transporte, que seriam o insumo
   natural, devolvem silenciosamente a isócrona de caminhada.
4. **O tempo depende do horário, e a Portaria não nomeia nenhum.**
5. **Ainda restaria o escolar**, que não é dado público de jeito nenhum — então
   mesmo um feed de coletivo resolveria apenas uma das duas vias desta
   alternativa.

E permanece a razão que dispensa as outras: comprovar por transporte escolar
depende de documentação da Prefeitura, e a planilha-mãe marca esta linha com
"Julg. humano complementar: Sim".
"""

from __future__ import annotations

from core.dominio.contratos.regra import Dominio
from core.dominio.vocabulario import motivos
from core.regras.base.remessa import RegraRemetida
from core.regras.registro import registrar


@registrar
class ENQ0112(RegraRemetida):
    id = "ENQ-011.2"
    dominio = Dominio.GIS
    descricao = ("Alternativa B — transporte público escolar ou coletivo até "
                 "escola de ensino fundamental Ciclo II (11 a 15 anos)")
    alvo = "itinerário do transporte escolar ou coletivo e tempo de percurso"
    remete_a = motivos.ANALISE_HUMANA_DOCUMENTAL
    insumo = ("itinerário e horários do transporte público escolar ou coletivo "
              "do município")
    porque = ("Não há feed aberto de transporte coletivo nos municípios do "
              "estudo, e o itinerário do transporte ESCOLAR não é dado público — "
              "a comprovação se dá por declaração ou documentação da Prefeitura. "
              "Além disso, o limiar é de tempo sobre uma rede que varia com o "
              "horário, e a Portaria não fixa horário de referência.")
    fundamento = ("Anexo I, Tab. 1, item 3.c (Redação dada pela Portaria MCID "
                  "nº 335, de 30 de março de 2026)")
    parametro = {
        "modal": "transporte público escolar ou coletivo",
        "tempo_maximo_min": 20,
        # A diferença normativa em relação ao ENQ-010.2, declarada como dado e
        # não só em prosa: aqui a caminhada até o embarque entra na conta.
        "computa_caminhada": True,
        "ref_portaria": "Anexo I, Tab. 1, item 3.c",
    }
