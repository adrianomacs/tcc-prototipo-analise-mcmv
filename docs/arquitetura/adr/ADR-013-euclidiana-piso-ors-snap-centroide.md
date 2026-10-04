# ADR-013 — A euclidiana é piso demonstrável que só reprova; ORS é o único provedor de rede; a origem da medida é sempre o centróide
**Status:** Aceita

## Contexto
A Portaria exige distância caminhável em rede, não em linha reta, para os
requisitos de proximidade a equipamentos (ENQ-009, 010.1, 011.1). A saída
usual — multiplicar a euclidiana por um fator de desvio de 1,2 a 1,4 — foi
considerada e recusada: o número passaria a depender de parâmetro que a
Portaria não define e ninguém auditaria. Em paralelo, cogitou-se um
segundo provedor de rede (Google Routes) como verificação auditável, e o
*snap* à via (aproximar a origem da medida do ponto mais próximo na rede)
parecia correção natural quando o centro do terreno cai longe da rua.

## Decisão
A distância em linha reta é, por construção, um **limite inferior**
demonstrável da distância caminhável (nenhum caminho sobre a superfície é
mais curto que a geodésica entre dois pontos) — nunca uma aproximação. Ela
**reprova** legitimamente quando já ultrapassa o limiar; nunca **aprova**.
Sem provedor de rede e com o piso abaixo do limiar, o veredito é NÃO
AVALIÁVEL (`metrica_insuficiente`), nunca chutado. O único provedor de rede é
o OpenRouteService (perfil `foot-walking`, malha OpenStreetMap) — o Google
Routes foi **RETIRADO** (divergência entre provedores
não produz veredito sem eleger um deles como verdade; a premissa de código
aberto da introdução não convive com dependência proprietária no caminho da
verificação; e o §11.3 dos *Service Specific Terms* do Google veda o uso "in
conjunction with a non-Google map", que painel separado não contorna). A
origem da medida é sempre o **centróide** do terreno, nunca a poligonal nem
um ponto ajustado à via — comando expresso da Portaria (itens 3, 4 e 5 do
Anexo I dizem "computada a partir do centro do terreno"; o item 2.2 diz "a
partir da poligonal" quando é isso que quer). O deslocamento do *snap* é
registrado como diagnóstico (`Medicao.snap_m`) e nunca compensado.

## Consequências
Fica fácil reprovar sem nenhuma chamada de API quando a euclidiana já
ultrapassa o limiar. Fica fácil auditar qual provedor e qual métrica
produziram cada número. Fica difícil produzir veredito em terreno urbano sem
chave de ORS configurada: a maioria dos casos sai NÃO AVALIÁVEL, e isso é
comportamento correto declarado, não falha do módulo. Não se pode introduzir
um segundo provedor de rede sem reabrir a decisão contratual do Google, nem
compensar o *snap* — mesmo quando o centro cai a centenas de metros da via, o
número que sobe é o que a norma manda calcular.

## Evidência
- `core/dominio/mobilidade.py`: `class Medicao` (`limite_inferior`,
  `snap_m`, `provedor`, `metrica`).
- `core/dominio/euclidiana.py` (haversine com o menor raio de curvatura do
  elipsoide, verificada contra Vincenty; implementação da porta sem I/O, por
  isso no domínio, ADR-002).
- `core/infra/rede/ors.py` (`PERFIL_PEDESTRE = "foot-walking"`,
  `class RoteadorORS`, `graph_date`/`osm_date` em `metadata.engine`).
- `core/dominio/vocabulario/motivos.py`: `METRICA_INSUFICIENTE`.
- `core/regras/base/distancia_equipamento.py`.
- `tests/core/dominio/test_euclidiana.py`, `tests/core/infra/rede/test_ors.py`,
  `tests/core/regras/gis/test_enq_distancia.py`.
