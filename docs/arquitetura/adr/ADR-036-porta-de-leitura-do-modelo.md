# ADR-036 — As regras leem o modelo BIM por uma porta do domínio; o LoGeoRef é calculado na ingestão
**Status:** Aceita

## Contexto
O ADR-002 declarou uma exceção à regra da dependência para dentro: as regras
BIM importavam os *helpers* de `core/infra/ifc/` (triagem de ambientes,
classificação dos revestimentos, propriedades, âncora, consistência e
procedência do georreferenciamento), e o EMP-001 importava a malha municipal
de `core/infra/gis/`. A justificativa era a camada anticorrupção fora do
escopo. Com a exceção, a propriedade "tudo aponta para dentro" não podia ser
verificada por teste sem uma lista de isenções.

## Decisão
O que as regras perguntam ao modelo passa por uma porta do domínio,
`LeituraModelo` (`core/dominio/contratos/leitura_modelo.py`), implementada por
`LeituraIFC` (`core/infra/ifc/leitura_ifc.py`) e injetada pela composição em
`Contexto.leitura_modelo`, como o `Roteador` (ADR-011). A conferência da âncora
contra o município entra pela porta `FontesTerritoriais`, em
`Contexto.fontes_territoriais`. O LoGeoRef é calculado uma vez, na ingestão,
ao lado do CRS (`composicao.leitura_do_modelo`, alvo `LOGEOREF_ALVO` da DN-03),
e o EMP-001 só julga o diagnóstico; erro no cálculo não derruba a ingestão e
vira `erro_de_execucao` do EMP-001, como antes. A leitura continua tardia: cada
método roda dentro do `checar`, e o executor segue isolando exceção por regra.
A porta **não** é a camada anticorrupção completa: devolve o que os leitores já
devolvem (a triagem com `Ambiente` do domínio, a partição dos revestimentos,
os elementos IFC para as consultas de propriedade). Ela decide quem lê o
arquivo; traduzir o modelo inteiro para entidades do domínio segue fora do
escopo.

## Consequências
Fica fácil afirmar, e testar, que nenhum módulo de `core/regras/` importa o
anel externo. Fica fácil trocar o leitor de IFC sem tocar em regra. Fica
difícil o atalho: uma regra que precise de uma leitura nova do modelo
acrescenta o método à porta e à implementação, em vez de importar o leitor. Um
`Contexto` montado à mão com modelo precisa trazer a porta; os testes usam
`tests/apoio/contexto_bim.py`, que chama a mesma função da composição.

## Evidência
- `core/dominio/contratos/leitura_modelo.py`, `core/infra/ifc/leitura_ifc.py`,
  `core/dominio/conhecimento/georreferenciamento.py`.
- `core/composicao.py:leitura_do_modelo` e `montar_contexto`.
- `tests/apoio/contexto_bim.py`; `tests/core/regras/gis_bim/test_emp_001.py`.
