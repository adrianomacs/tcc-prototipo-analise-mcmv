# ADR-038 — A divergência entre a coordenada do IfcSite e a origem do IfcMapConversion é diagnóstico, nunca veredito
**Status:** Aceita

## Contexto
O `E1_georref.ifc` tem LoGeoRef 50 correto, com a origem do `IfcMapConversion`
em Estrela/RS, mas guarda no `IfcSite` a latitude e a longitude da condição
existente, em Maceió. Sem poligonal, a cascata do extrator usa a coordenada do
`IfcSite`, o centro informado pelo projetista, antes da origem do
`IfcMapConversion`, o ponto de inserção do modelo. O terreno cai em Maceió, o
confronto com o município o barra, e a mensagem genérica manda corrigir o
modelo sem dizer que ele guarda duas posições.

## Decisão
A precedência da cascata não muda. Quando o terreno sai da coordenada do
`IfcSite` e há um `IfcMapConversion` utilizável, o extrator mede a distância
geodésica entre as duas posições e, acima de **250 m**, grava ambas em
`procedencia["divergencia_posicao"]`, no `detalhe` e num aviso do terreno. Os
250 m superam o arredondamento da latitude em segundos inteiros (cerca de
30 m) e a distância entre o centro do lote e o ponto de inserção, e são um
quarto do menor limiar de distância do recorte (1.000 m).

A tela nomeia a fonte usada, diz se cada posição cai dentro ou fora do
município declarado (só com a malha em cache, sem rede no render) e o que
fazer. A caixa é `ERRO` quando a posição do `IfcSite` cai fora do município,
o que o confronto já impedia, e `ALERTA` nos demais casos (ADR-034 (c)). Não
há estado, motivo ou regra novos, e nenhum veredito depende disso (ADR-032).
O extrator segue sem conhecer o município (ADR-011); o confronto fica na tela,
pelo gateway (ADR-003).

## Consequências
Fica fácil dizer ao usuário o que o modelo tem de errado, e a procedência
guarda as duas posições. Fica de fora, de propósito, escolher o terreno pela
posição que bate com o município. Com poligonal, ou só com o
`IfcMapConversion`, não há o que comparar. O município de cada posição não é
nomeado, porque não há consulta de ponto para município.

## Evidência
- `core/infra/ifc/extrator_terreno.py`: `_divergencia_de_posicao`,
  `TOLERANCIA_DIVERGENCIA_POSICAO_M`.
- `app/componentes/avisos.py`: `aviso_divergencia_posicao`;
  `app/paginas/checagens/checagem_enquadramento.py`: `_aviso_de_divergencia`.
- `tests/core/infra/ifc/test_extrator_terreno.py` (com o E1 real, que pula sem
  o arquivo) e `tests/app/componentes/test_avisos.py`.
