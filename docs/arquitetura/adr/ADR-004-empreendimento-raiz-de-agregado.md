# ADR-004 — `Empreendimento` é a raiz de agregado da análise
**Status:** Aceita

## Contexto
O código não tinha resposta única para "a análise é de quê?". O `Contexto` do
motor fundia num dataclass só o empreendimento (modelo, terreno, município,
declarações) e o ambiente de execução (camadas GIS, georreferenciamento,
config, resultados). A tela do Enquadramento guardava o município dentro de
`terreno.procedencia` — um campo de `Terreno` fazendo o trabalho de uma
entidade inexistente — e o `meta` do relatório espalhava a identidade do
empreendimento por cinco chaves soltas.

## Decisão
`Empreendimento` é entidade de domínio e raiz de agregado: identidade
(`id` uuid4 de 12 hex + `nome` livre), `Localizacao` (VO), `Declaracoes`,
`Terreno` opcional e `ModeloBIM` opcional; `versao` incrementa a cada mudança.
`Contexto = Empreendimento + serviços + resultados`, com os campos antigos
mantidos como **propriedades delegadas** (as regras não mudaram e não sabem
que a entidade existe). A unidade de persistência é
o arquivo `empreendimento.json` da pasta `artefatos/`, que **absorve** o `terreno.json` (lido apenas
como legado). O relatório referencia `meta.empreendimento = {id, versao}`, o
que permite a uma tela dizer "este relatório está desatualizado" sem reabrir o
relatório inteiro. Equipamentos **não** pertencem ao empreendimento: pertencem
ao território (ADR-011).

## Consequências
Fica fácil centralizar as declarações numa tela só (2.1.1), exibir cabeçalho
nas checagens e consolidar resultados de várias checagens sem misturar
empreendimentos. Fica difícil a retrocompatibilidade: as propriedades
delegadas são dívida deliberada, e `Contexto` deixou de ser `@dataclass`
porque propriedade delegada e campo homônimo não convivem. Não se pode passar
`empreendimento=` **e** os campos legados juntos — `Contexto` e
`composicao.rodar` levantam `ValueError`, porque não há regra de precedência que
não seja arbitrária. Dívida conhecida: remover os campos delegados.

## Evidência
- `core/dominio/empreendimento.py` (`Empreendimento`, `Localizacao`, `ModeloBIM`);
  `core/dominio/contratos/regra.py` (`Contexto` e as propriedades delegadas).
- `core/infra/persistencia/empreendimento_json.py` (escrita atômica; leitura
  legada de `terreno.json`).
- `core/aplicacao/pipeline.py:analisar` (`meta["empreendimento"] = referencia()`).
- `tests/core/dominio/test_empreendimento.py`,
  `tests/core/dominio/contratos/test_contexto.py`,
  `tests/core/infra/persistencia/test_empreendimento_json.py`,
  `tests/core/aplicacao/test_pipeline_empreendimento.py`.
