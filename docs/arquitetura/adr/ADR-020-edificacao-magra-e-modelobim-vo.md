# ADR-020 — `Edificacao` é entidade magra; `ModeloBIM` é objeto de valor anexável ao terreno e a ela
**Status:** Substituída por ADR-023

> A revisão é **de forma**: a entidade que este ADR chama de `Edificacao`
> passa a ser `UnidadeTipo` (ADR-023), e a `Edificacao` física é outra
> entidade. Sobrevivem intactos: `ModeloBIM` como objeto de valor com
> `unidades_representadas`, o anexo pela natureza declarada, a saída de
> `Empreendimento.modelo`, os fora-de-escopo declarados
> (`UnidadeHabitacional`, camada anticorrupção) e a equivalência das duas
> formas de "quatro torres iguais" — agora quatro `UnidadeTipo` sobre o mesmo
> VO, com a regra de pares do ADR-023; a forma canônica é uma só. A seção
> Evidência descreve o estado anterior ao ADR-023.

## Contexto
O ADR-004 pendurou um `ModeloBIM` opcional no `Empreendimento`. O campo supõe
que uma submissão é **um** contêiner, e a submissão real é fragmentária: o
terreno pode vir desenhado no mapa e a edificação num IFC, ou quatro torres
iguais num arquivo só. Sem entidade para a edificação, a tipologia é declaração
única do empreendimento — empreendimento misto é inexprimível — e não há onde
dizer quantas UHs o arquivo entregue representa. A descrição da arquitetura
chamava `ModeloBIM` de entidade, enquanto a modelagem conceitual o tratava
como objeto de valor; a divergência nunca fora resolvida.

## Decisão
`Edificacao` entra no agregado do `Empreendimento` (ADR-004 continua valendo:
muda o interior do agregado, não a raiz) como entidade **magra** — identidade,
nome, nº de unidades, tipologia e, no máximo, um `ModeloBIM`. `ModeloBIM` passa
a **objeto de valor**, anexável a `Edificacao` e a `Terreno` (0..1 cada), e
ganha `unidades_representadas` (ADR-021). `Empreendimento.modelo` sai.

O contêiner enviado numa tela é anexado pela **natureza declarada**: `terreno`
→ `Terreno`; `edificacao_isolada` → `Edificacao`; `terreno_com_edificacoes` →
os dois, apontando para o mesmo contêiner. O que a análise lê continua sendo o
contêiner âncora da execução (ADR-021), e não um campo fixo — por isso o
EMP-001 não muda de fonte e o veredito do Estrela I é preservado. Havendo
`Terreno.modelo`, ele é **fonte de informação** que confere o terreno declarado
antes (poligonal desenhada, CSV): conferência, não veredito do EMP-001.

Fora de escopo, declarado: `UnidadeHabitacional` como entidade (sem
`IfcZone`/`IfcSpatialZone` nos modelos, nada a preencheria) e camada
anticorrupção sobre o IfcOpenShell — a limitação 1 da `VISAO_GERAL.md` §7
permanece.

## Consequências
Fica fácil exprimir quatro torres iguais das duas formas equivalentes (quatro
`Edificacao` para o mesmo contêiner, ou uma com `unidades = 64` e o contêiner
com `unidades_representadas = 4`) sem modelar "pavimento tipo" nem
`repeticoes`; fica fácil o empreendimento misto; e a divergência sobre a
natureza de `ModeloBIM` resolve-se a favor de VO. Fica difícil a leitura do
`empreendimento.json` antigo, que não tem edificações — resolvida sintetizando
uma (ADR-021); e as duas formas equivalentes exigem teste que prove que
produzem o mesmo diagnóstico. Não se pode mais pendurar modelo no
`Empreendimento`, nem tratar `ModeloBIM` como entidade com identidade própria.

## Evidência
- `core/dominio/edificacao.py`, `core/dominio/modelo_bim.py` (VO *frozen*) e
  `Terreno.modelo`; testes em `tests/core/dominio/`.
- `Empreendimento` **sem** o campo `modelo`: a chave do artefato antigo
  só é reconhecida pela migração, em
  `core/infra/persistencia/empreendimento_json.py` (teste espelho em `tests/`).
- O EMP-001 lê a natureza do contêiner âncora
  (`core/regras/gis_bim/emp_001_georreferenciamento.py`, `core/dominio/ancora.py`,
  `tests/core/regras/gis_bim/test_emp_001.py`) — por isso não mudou de fonte, e o
  veredito do Estrela I foi preservado contra a linha de base.
- Faltava a ponta da interface: declarar a composição e anexar o contêiner
  enviado pela natureza. Até ela existir, quem a exprimia era a migração.
