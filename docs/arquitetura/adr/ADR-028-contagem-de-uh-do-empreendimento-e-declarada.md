# ADR-028 — Limite de UH por empreendimento se confere pelo total declarado da proposta, nunca pelo modelo
**Status:** Aceita

## Contexto
O item 4.I.a do Anexo II limita o número de UH **por empreendimento**, conforme
o porte do município (EMP-025.1). O ADR-021 deu dono a três números de UH e
decidiu que a regra **dimensional** consome só `unidades_representadas`, o do
contêiner lido. EMP-025.1 não é dimensional: pergunta sobre o empreendimento
inteiro. Com `unidades_representadas`, um IFC de 1 UH representando um tipo
de 300 aprovaria, por construção, um empreendimento que estoura o limite:
**falso conforme** em toda submissão fragmentária, ou seja, na submissão normal.

## Decisão
EMP-025.1 compara `Empreendimento.unidades_previstas` (o total declarado da
proposta, ADR-021) com o limite da faixa de porte. É a primeira regra a
consumir esse número; o modelo não entra nela. A regra passa a ser
**declaração × território** (GIS only na base de requisitos, não GIS + BIM). Sem
`unidades_previstas`, NÃO AVALIÁVEL (`insumo_do_proponente_ausente`, ADR-033;
antes dele, `insumo_ausente`). Se o total for contradito
por outra declaração do proponente (as unidades tipo somam mais que ele, ou a
composição passa das unidades de um tipo), NÃO AVALIÁVEL por
`inconsistencia_declaratoria`: é o primeiro emissor do ADR-022. Soma **menor**
que o previsto é declaração incompleta, legítima, e não bloqueia.

## Consequências
Fica fácil conferir o limite antes de existir modelo, e o veredito fala do
número sobre o qual a norma pergunta. Fica difícil (limitação aceita) confrontar
o declarado com o modelado: a conferência declarado × medido não é este motivo
(ADR-022) nem esta regra. `unidades_previstas` segue sem natureza (`estimada` ×
`comprometida`, ADR-021): o veredito vale para o número que o proponente
declarou. Não se pode ler `unidades_previstas` como denominador de regra
dimensional (o ADR-021 permanece), nem usar `unidades_representadas` para
limite de porte.

## Evidência
- `core/regras/gis/emp_025_1_limite_uh_empreendimento.py`;
  `Empreendimento.declaracao_consistente` em `core/dominio/empreendimento.py`.
- `INCONSISTENCIA_DECLARATORIA` em `core/dominio/vocabulario/motivos.py`.
- `tests/core/regras/gis/test_emp_025.py`
  (`::test_a_contagem_e_a_declarada_nunca_a_do_modelo`, `::test_unidades_tipo_acima_do_previsto_e_inconsistencia_declaratoria`).

## Relações
Anota o ADR-021.
