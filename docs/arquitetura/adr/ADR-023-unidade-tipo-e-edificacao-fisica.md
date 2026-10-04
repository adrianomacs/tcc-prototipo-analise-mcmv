# ADR-023 — `UnidadeTipo` é o grupo de UH que se repete; `Edificacao` é o prédio físico, ligado a ela por composição
**Status:** Aceita

> **Herança do ADR-020.** Este ADR herda sem mudança, do ADR-020 que
> substitui, o que o código cita por este número: `ModeloBIM` é VO imutável
> com `unidades_representadas` (ADR-021) — a divergência sobre a natureza de
> `ModeloBIM` resolvida a favor de VO; o contêiner enviado é anexado pela
> **natureza declarada** (`terreno` → `Terreno`; `edificacao_isolada` →
> unidade tipo; `terreno_com_edificacoes` → os dois); `Empreendimento.modelo`
> não existe; `Terreno.modelo` **confere** o terreno declarado por outra via —
> conferência, não veredito do EMP-001; a submissão é fragmentária; quatro tipos
> sobre o mesmo VO equivalem a um com as UH somadas. Os esquemas do
> `empreendimento.json`: **E0** (anterior às entidades), **E1** (`edificacoes`
> com os campos de unidade tipo, o esquema do ADR-020) e **E2** (atual).

## Contexto
A `Edificacao` do ADR-020 — nome, nº de unidades, tipologia, um contêiner —
fazia dois papéis que a base de 299 requisitos separa: a edificação FÍSICA
(`IfcBuilding × IfcBuilding` em EMP-032, pavimentos em EDI-013) e o GRUPO DE
UH QUE SE REPETE (o que EDI-001/002/004 consomem, e onde "140 casas padrão
+ 10 PCD" precisa ser declarado). Os quatro campos descrevem o segundo; o
primeiro não existia. O EIR adotado ("um IFC por tipologia" — planta
distinta, não casa × apartamento) não tinha onde morar, e o pavimento tipo
misto não tinha a quem ser anexado.

## Decisão
A `Edificacao` do ADR-020 passa a chamar-se `UnidadeTipo`, com os mesmos
campos (`nome`, `unidades` — o terceiro número do ADR-021 —, `tipologia`,
`modelo`) e a mesma identidade. Entra uma `Edificacao` **física** magra e
opcional — `nome`, `modelo` (0..1), `composicao` (quantidade de cada unidade
tipo nela). `Empreendimento` (ADR-004 intacto) guarda as duas coleções e
garante que a composição só cita tipos do agregado, de uma mesma tipologia,
que ele deriva para a edificação. `ModeloBIM` segue VO, anexável aos três; a
âncora da execução segue sendo um contêiner por análise
(`composicao.rodar(conteiner=)` não muda), e a aplicação resolve o **dono** do
contêiner com precedência tipo > edificação > terreno, lendo dele a
tipologia. Arquivo que mistura tipos anexa-se à edificação física e é
analisado em agregado com diagnóstico, nunca recusado. Sem regra ativa que
os consuma, não entram: `pavimentos`, `adaptada`, `IfcBuilding`
correspondente, `Quadra`/`Lote`, `UnidadeHabitacional`, ingestão federada.

## Consequências
Fica fácil declarar populações distintas na mesma tipologia, dar dono ao IFC
por unidade tipo e mostrar por análise quando o veredito é agregado; fica
fácil crescer — cada regra territorial acrescenta um campo à `Edificacao` e
uma regra nova ao registro. Fica difícil o rename: testes que registram a
forma antiga mudam por renomeação sob este ADR, sem mudar asserção; e três
esquemas de `empreendimento.json` são migrados em memória, sem a versão
andar. Não se pode pendurar nº de UH nem tipologia na edificação física,
sintetizar edificação física de artefato antigo, nem misturar tipologias
numa composição.

## Evidência
- As duas entidades: `core/dominio/unidade_tipo.py` (`UnidadeTipo`) e
  `core/dominio/edificacao.py` (`Edificacao` física, `composicao`); as duas
  coleções, os invariantes da composição, `tipologia_de`,
  `unidades_compostas`, os dois excedentes e o cascade em
  `core/dominio/empreendimento.py`.
- O dono do contêiner, com precedência tipo > edificação > terreno e a regra
  de pares: `donos_do_conteiner`, `mesmo_conteiner` e
  `tipologia_em_analise(…, conteiner=)` em `core/dominio/ancora.py`;
  `pipeline._instantaneo` entrega o contêiner.
- Os três esquemas (E0/E1/E2) migrados em memória em
  `core/infra/persistencia/empreendimento_json.py`, contra as fixtures reais
  `tests/fixtures/empreendimento_esquema_antigo.json` e
  `tests/fixtures/empreendimento_esquema_adr020.json`.
- O alvo da análise, na interface: `ALVO_TERRENO`/`ALVO_TODAS`/
  `unidade_tipo:<id>`/`edificacao:<id>` e a ordem contêiner → dono →
  declarações em `app/servicos/analise.py`; os dois sub-formulários de
  `app/paginas/checagens/informacoes_gerais.py`; os seletores de
  `checagem_georreferenciamento.py` e `checagem_programa.py`, que traduzem os
  rótulos sem acrescentar valor ao vocabulário de `natureza`.
- Testes: `tests/core/dominio/test_unidade_tipo.py`, `test_edificacao.py`,
  `test_empreendimento.py`; `tests/core/dominio/test_ancora.py`;
  `tests/core/infra/persistencia/test_empreendimento_json.py`;
  `tests/app/servicos/test_analise_regressoes.py`.
- Linha de base do Estrela I: os três relatórios sem nenhuma diferença de
  veredito; o rename não mudou a contagem de testes coletados. A única
  diferença nova de `meta` é `meta.terreno.modelo` do Georreferenciamento
  deixar de ser `null`.

## Relações
Substitui o ADR-020; anota o ADR-021 e o ADR-022.
