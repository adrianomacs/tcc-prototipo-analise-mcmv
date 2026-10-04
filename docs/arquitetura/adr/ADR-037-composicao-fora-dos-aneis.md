# ADR-037 — Um módulo de composição fora dos anéis monta e grava; o caso de uso não faz I/O
**Status:** Aceita

## Contexto
`core/aplicacao/pipeline.py` era, ao mesmo tempo, o caso de uso e o "Main" do
núcleo: dentro das suas funções abria o IFC, lia camadas, calculava a
impressão digital, construía o cache do roteamento, gravava o relatório e
servia de linha de comando. Por isso o anel de aplicação importava o anel
externo, e a regra da dependência para dentro (ADR-002) só valia com exceção.

## Decisão
O núcleo tem um único módulo de composição, `core/composicao.py`, fora dos
quatro anéis. Ele monta o `Contexto` (IFC, camadas, CRS, LoGeoRef e a porta de
leitura do modelo, impressão digital, território pela porta
`FontesTerritoriais`, `Roteador` recebido da borda), chama o caso de uso e
entrega a análise ao exportador; tem também a CLI (`python -m core.composicao`)
e as fábricas de produção das portas. É o único que pode importar todos os
anéis, nenhum anel o importa, e é o ponto de entrada para executar a
verificação, pela interface (`app/servicos/`) e pela linha de comando.
`composicao.rodar` tem a assinatura que `pipeline.rodar` tinha. O caso de uso,
`core/aplicacao/pipeline.py:analisar`, recebe o `Contexto` pronto, executa o
motor, monta o `meta` e devolve `Analise(resultados, meta, erro_ingestao)`
como dado. A ordem dos anéis que o teste impõe é domínio, regras, aplicação,
infraestrutura: a aplicação importa regras e domínio, a infraestrutura só o
domínio.

## Consequências
Fica fácil afirmar que a dependência aponta para dentro sem exceção, porque o
que junta os anéis está fora deles, e testar o caso de uso com um `Contexto`
montado em memória. Fica difícil o atalho: nova leitura de arquivo na análise
entra na composição ou numa porta, nunca no caso de uso. `app/servicos/` segue
importando tipos do domínio e leitores de artefato do anel externo (ADR-003);
a composição é a entrada para executar, não o único import do núcleo.

## Evidência
- `core/composicao.py` (`montar_contexto`, `rodar`, `leitura_do_modelo`,
  `fontes_territoriais`, `_cli`); `core/aplicacao/pipeline.py:analisar`.
- `tests/arquitetura/test_aneis.py` (direção dos anéis, composição isenta e
  proibida aos anéis, todo módulo num anel).
