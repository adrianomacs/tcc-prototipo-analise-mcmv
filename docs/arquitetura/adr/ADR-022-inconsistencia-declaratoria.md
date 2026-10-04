# ADR-022 — "Inconsistência declaratória" entra na taxonomia do não avaliável
**Status:** Substituída por ADR-033

> A revisão é **de extensão**: o ADR-033 acrescenta um 17º motivo
> (`insumo_do_proponente_ausente`). Este motivo, seu rótulo, sua ação e o
> alcance "declaração × declaração" seguem como abaixo.

> **Implementação.** O primeiro emissor é EMP-025.1
> (ADR-028), sobre as duas aritméticas acima. Com ele, a divergência
> de `IsExternal` entre o `IfcCovering` e a parede que o hospeda
> (`core/regras/base/absortancia.py`), que saía como
> `analise_humana_documental`, passou a este motivo: também é declaração ×
> declaração, e a correção é do proponente. O diagnóstico homônimo do
> relatório (`meta`) segue com rótulo próprio.

> Segunda aritmética coberta pelo mesmo motivo (ADR-023): soma da composição
> das edificações físicas maior que `unidades` do tipo. Continua declaração
> × declaração. A constante entra no vocabulário com o primeiro emissor — a
> regra que consumir os totais declarados (EMP-028 ou EMP-025); até lá,
> `Aceita (não implementada)`, e o diagnóstico homônimo do relatório usa
> rótulo próprio, em `meta`, não em `Resultado.detalhe`.

## Contexto
O ADR-006 fechou a taxonomia das causas de `NAO_AVALIAVEL` em 15 motivos, cada
um com rótulo e ação que o destrava. A separação dos três números de UH
(ADR-021) torna exprimível uma situação que antes não tinha como aparecer: a soma
de `Edificacao.unidades` maior que `Empreendimento.unidades_previstas` — o
proponente declarando, em dois lugares, números que não fecham. Nenhum dos 15
motivos a nomeia: não falta insumo, não falta métrica, não falta pré-requisito,
e a agregação não está indecisa. Sem motivo próprio, o caso sairia como
`insumo_ausente` (falso) ou como veredito calculado sobre um número que o
próprio projeto contradiz.

## Decisão
A taxonomia ganha um 16º motivo, `inconsistencia_declaratoria` — "Números
declarados inconsistentes entre si" —, com ação de interface que remete à
correção da declaração, não ao fornecimento de insumo.

Tudo o mais do ADR-006 permanece: três estados e só três; a causa continua
viajando em `Resultado.detalhe["motivo_nao_avaliavel"]`; `Regra.nao_avaliavel
(motivo=…)` continua sendo o único caminho para produzir o estado com a causa
anexada; o relatório continua agrupando por ela. Muda a **extensão** da lista,
e é por isso que esta é decisão nova e não edição: a taxonomia é fechada por
decisão, então acrescentar item revisa o ADR-006, que passa a
`Substituída por ADR-022`.

O motivo cobre **declaração × declaração**. Divergência entre o que foi
declarado e o que o modelo mede é outra coisa — conferência, diagnóstico do
empreendimento — e não entra aqui.

## Consequências
Fica fácil transformar declaração que se contradiz em pendência acionável, em
vez de veredito calculado sobre número inconsistente ou de um "não avaliável"
com causa errada. Fica difícil a disciplina do motivo: é o segundo da lista,
depois de `agregacao_indecisa`, cuja ação não nomeia um insumo — e o primeiro
cuja correção é do proponente, não do analista. Não se pode usá-lo para
divergência entre declarado e medido, nem emitir a inconsistência como um
quarto estado.

## Evidência
Decisão anterior ao código; a implementação está na nota do início. O que ela
estende: as 15 constantes, `ROTULO` e `ACAO` em
`core/dominio/vocabulario/motivos.py`; `Estado`, `Resultado.detalhe` e
`Regra.nao_avaliavel` em `core/dominio/contratos/regra.py`; o agrupamento por
causa em `core/infra/exportadores/relatorio_json.py`; e
`tests/core/aplicacao/test_executor.py`.

## Relações
Revisa o ADR-006.
