# ADR-033 — "Insumo do proponente ausente" entra na taxonomia do não avaliável
**Status:** Aceita

## Contexto
A taxonomia fechada (ADR-006/022) tem 16 motivos e um só para insumo não
fornecido, `insumo_ausente`, cujo rótulo e ação falam de **camada geoespacial**. Dois casos ficavam sem nome. A EMP-025.1 sem
`unidades_previstas` (ADR-028) saía com `insumo_ausente`, que o ADR-022 já
chamava de falso para caso declaratório, e o pai EMP-025 herdava rótulo e ação
de camada. As treze regras ativas que leem o modelo (EMP-001, oito do programa,
quatro ramos da absortância) saíam, sem modelo, NÃO AVALIÁVEL **sem motivo** —
a exceção que desmentia o ADR-006. Generalizar `insumo_ausente` foi recusado:
a ação passaria a depender de uma segunda chave, e o agrupamento por causa
juntaria "falta camada pública" com "falta o que só o proponente entrega".

## Decisão
A taxonomia ganha um 17º motivo, `insumo_do_proponente_ausente`: falta um
insumo que **só o proponente fornece** — o modelo IFC ou uma declaração
(Informações Gerais). A ação é única e remete à mensagem da regra, que já diz
qual dos dois falta. `insumo_ausente` volta a ser estritamente geoespacial.
Tudo o mais do ADR-006/022 permanece: três estados, causa em
`Resultado.detalhe["motivo_nao_avaliavel"]`, `Regra.nao_avaliavel(motivo=…)`
como único caminho, relatório agrupando por ela. A lista cresce por decisão,
então este ADR revisa o ADR-022, que passa a `Substituída por ADR-033`.

## Consequências
Fica fácil ler a taxonomia por **quem destrava**: dado público ou analista
(`insumo_ausente`, `mapeamento_pendente`, …), proponente (este motivo e
`inconsistencia_declaratoria`), campo ou parecer, e o próprio protótipo
(`membro_nao_executado`, `erro_de_execucao`) — a distinção entre limitação do
protótipo e lacuna do projeto que o ADR-006 promete. Nenhuma regra ativa sai
mais NÃO AVALIÁVEL sem motivo. Fica difícil (aceito) distinguir, pelo motivo
só, modelo ausente de declaração ausente: a mensagem distingue. Não se pode
usá-lo para conteúdo que falta **dentro** do modelo (`informacao_ausente`) nem
para camada pública (`insumo_ausente`).

## Evidência
`core/dominio/vocabulario/motivos.py`; os emissores são o EMP-001,
`core/regras/base/absortancia.py`, as regras do programa em `core/regras/bim/`
e a EMP-025.1. Um teste por família: `tests/core/regras/gis_bim/test_emp_001.py`,
`test_edi_004_programa_necessidades.py`, `tests/core/regras/base/test_absortancia.py`,
`tests/core/regras/gis/test_emp_025.py`.

## Relações
Revisa o ADR-022.

## Município não declarado
Município não declarado também é insumo do proponente: as regras de distância
a equipamento (ENQ-009/010.1/011.1) deixaram `informacao_ausente` e a EMP-025.1
deixou `porte_indeterminado` nesse caso. `porte_indeterminado` fica só para o
município sem população no Censo 2022 (ADR-030). Rótulos e ações dos motivos
seguem o ADR-034. Testes:
`tests/core/regras/gis/test_enq_distancia.py::test_municipio_nao_declarado`,
`tests/core/regras/gis/test_emp_025.py::test_municipio_nao_declarado_e_insumo_do_proponente`.
