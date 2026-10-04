# ADR-006 — Três estados de saída; o "não avaliável" sempre com motivo da taxonomia
**Status:** Substituída por ADR-022

> A revisão é **de extensão**: o ADR-022 acrescenta um 16º motivo
> (`inconsistencia_declaratoria`) à taxonomia. Os três estados, a causa em
> `Resultado.detalhe` e `Regra.nao_avaliavel(motivo=…)` seguem como abaixo.

## Contexto
Um verificador binário (conforme / não conforme) mente por omissão: a maior
parte dos requisitos do PMCMV depende de insumo que pode faltar, de camada não
classificada, de terreno ainda não desenhado ou de vistoria em campo. Marcar
esses casos como não conforme produziria falso não-conforme e contaminaria as
métricas de desempenho do protótipo. Mas saber que algo é "não avaliável" sem
saber **por quê** também não serve: cada causa pede uma ação diferente.

## Decisão
`Estado` tem exatamente três valores — `CONFORME`, `NAO_CONFORME`,
`NAO_AVALIAVEL`. A causa **não** é um quarto estado: ela viaja como taxonomia
em `Resultado.detalhe["motivo_nao_avaliavel"]`, com vocabulário fechado em
`core/dominio/vocabulario/motivos.py` (15 motivos na redação original, cada um com rótulo e
ação que o destrava: `insumo_ausente`, `mapeamento_pendente`,
`terreno_insuficiente`, `prerequisito_falho`, `porte_indeterminado`,
`metrica_insuficiente`, `agregacao_indecisa`, `verificacao_em_campo`,
`analise_humana_documental`, …). `Regra.nao_avaliavel(motivo=…)` é o único
caminho para produzir o estado com a causa anexada, e o relatório agrupa por
ela.

## Consequências
Fica fácil transformar o relatório em lista de pendências acionável, e não num
muro de "não avaliável"; e fica fácil distinguir limitação do protótipo de
lacuna do projeto analisado — distinção de que a avaliação dos resultados
precisa. Fica barato de manter: um motivo novo é uma constante, não uma
mudança no executor, no relatório e nas métricas de uma vez. Não se pode
emitir `NAO_AVALIAVEL` sem motivo (fora de erro de execução), nem criar um
quarto estado para expressar nuance.

## Evidência
- `core/dominio/contratos/regra.py` (`Estado`, `Resultado.detalhe`,
  `Regra.nao_avaliavel(motivo=…)`).
- `core/dominio/vocabulario/motivos.py` (`CHAVE`, constantes, `ROTULO`).
- Agrupamento por causa: `core/infra/exportadores/relatorio_json.py`.
- `tests/core/aplicacao/test_executor.py`,
  `tests/core/regras/gis/test_enq_distancia.py`, `test_enq_distancia_rede.py`,
  `tests/core/regras/base/test_agregacao.py`,
  `tests/core/dominio/test_euclidiana.py`, `tests/core/dominio/test_terreno.py`,
  `tests/core/infra/gis/test_inep.py`.
