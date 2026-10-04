"""EMP-025.2 — número máximo de UH do grupo de empreendimentos contíguos.

Segunda metade do "e" do item 4.I.a do Anexo II: além do limite por
empreendimento (EMP-025.1), a soma das UH do grupo de empreendimentos
contíguos não pode passar de 200, 300, 400, 500 ou 750, conforme o porte.

Por que é remetida (DN-04)
--------------------------

O art. 4º, II, define contíguo: *"a menor distância entre o seu perímetro e o
perímetro de outro empreendimento for igual ou inferior a um quilômetro"*,
considerados os empreendimentos de Habitação de Interesse Social **em execução
ou entregues nos últimos 5 anos**, com as fontes da Portaria. O MÉTODO é
geoprocessável — um buffer de 1 km sobre a poligonal. O INSUMO não existe em
forma pública: não há cadastro aberto dos empreendimentos HIS com perímetro,
situação de obra e data de entrega. Sem ele, o grupo de contíguos não se forma.

Deixar a regra fora faria o pai (EMP-025, modo todos) decidir sobre um membro
só e **aprovar** o que a norma não aprovou — o espelho do defeito que a
DN-04 evitou nos "ou" do Anexo I. Presente e remetida, ela mantém o pai em
aberto quando o limite individual é atendido.
"""

from __future__ import annotations

from core.dominio.conhecimento import porte_municipal as porte
from core.dominio.contratos.regra import Dominio, Verbo
from core.dominio.vocabulario import motivos
from core.regras.base.remessa import RegraRemetida
from core.regras.registro import registrar


@registrar
class EMP0252(RegraRemetida):
    id = "EMP-025.2"
    # A planilha classifica como "GIS only": o método é geoprocessável; falta
    # o insumo (DN-04), e as duas coisas não se confundem.
    dominio = Dominio.GIS
    verbo = Verbo.CONTAGEM
    descricao = ("Número máximo de UH do grupo de empreendimentos contíguos, "
                 "conforme o porte populacional do município")
    alvo = "perímetros dos empreendimentos HIS contíguos (≤ 1 km)"
    remete_a = motivos.ANALISE_HUMANA_DOCUMENTAL
    insumo = ("cadastro dos empreendimentos de Habitação de Interesse Social em "
              "execução ou entregues nos últimos 5 anos, com perímetro")
    porque = ("Não há cadastro público dos empreendimentos HIS em execução ou "
              "entregues nos últimos 5 anos com o perímetro de cada um — e é "
              "dele que se forma o grupo de contíguos (≤ 1 km entre perímetros, "
              "art. 4º, II). O método é geoprocessável; o insumo não existe.")
    fundamento = "Anexo II, Tab. 1, item 4.I.a; art. 4º, II"
    parametro = {
        "limites_por_faixa": [
            {"faixa": f.rotulo, "limite_do_grupo_de_contiguos": f.valores[1]}
            for f in porte.PORTE_EMPREENDIMENTO_4_I_A],
        "contiguidade_km": 1.0,
        "universo": "HIS em execução ou entregues nos últimos 5 anos",
        "ref_portaria": "Anexo II, Tab. 1, item 4.I.a; art. 4º, II",
    }
