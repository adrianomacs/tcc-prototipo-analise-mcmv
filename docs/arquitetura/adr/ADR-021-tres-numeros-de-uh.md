# ADR-021 — São três os números de UH; a regra consome só `unidades_representadas`
**Status:** Aceita

> O dono do terceiro número ("por quantas UH o veredito fala") passou a
> chamar-se `UnidadeTipo.unidades` (ADR-023). A decisão — a regra consome um
> só número, `unidades_representadas` — não muda. A limitação das
> Consequências (compensação entre UH dentro de uma mesma entidade)
> **permanece**; o que o ADR-023 acrescenta é torná-la visível quando o
> arquivo é anexado a uma edificação física com composição declarada
> (diagnóstico de heterogeneidade). Um arquivo misto anexado a um
> `UnidadeTipo` continua indetectável — é o EIR que o evita, não o motor.

> **Anotado pelo ADR-028**: a regra **dimensional** consome só
> `unidades_representadas`; o limite de porte (EMP-025.1), que não é
> dimensional, consome `unidades_previstas` — o primeiro consumidor dela.

## Contexto
`NUM_UHS` mora em `Declaracoes` e as regras EDI leem dali (`minimo =
area_util_min_m2 * num_uhs`; cada categoria do programa multiplicada pelo mesmo
número). O campo funde três grandezas — quantas UHs o empreendimento terá,
quantas o contêiner submetido representa, por quantas o veredito fala —, erra o
denominador sempre que a submissão é fragmentária e **escala parâmetro
normativo**, contra o invariante do protótipo ("as declarações governam
aplicabilidade, nunca insumo"). `TIPOLOGIA`, declaração única, torna
empreendimento misto inexprimível.

## Decisão
Cada número ganha dono. `Empreendimento.unidades_previstas` é fato declarado da
proposta, nunca extraível de modelo; `ModeloBIM.unidades_representadas` é
propriedade da entrega (1 para a casa isolada, 4 para o pavimento tipo, 0 para
o modelo só do terreno); `Edificacao.unidades` é por quantas UHs o veredito
fala — a extrapolação que antes acontecia implícita.

**A regra consome um só número: `unidades_representadas` do contêiner
analisado**, porque EDI-004 pergunta sobre a geometria que está sendo lida;
`unidades_previstas` não entra em veredito dimensional nenhum. `NUM_UHS` e
`TIPOLOGIA` saem de `Declaracoes` — a tipologia passa a ser da `Edificacao`. E
a âncora da execução chega por **argumento nomeado aditivo** de
`composicao.rodar`, com default `None` preservando o comportamento atual (mesmo
padrão do `destino_rel`): a tela resolve qual contêiner analisar, a CLI segue
funcionando.

`unidades_previstas` nasce **sem** natureza (`estimada` × `comprometida`):
nenhuma regra do recorte a consome — trabalho futuro. Um `empreendimento.json`
sem edificações é lido sintetizando **uma** `Edificacao` ("Edificação 1"), com
`unidades`/`tipologia` das declarações antigas e `unidades_representadas =
NUM_UHS` — comportamento preservado bit a bit, sem script de migração.

## Consequências
Fica fácil o denominador correto na submissão fragmentária, o empreendimento
misto, e as declarações voltarem a governar só aplicabilidade. Fica difícil o
caso heterogêneo: tipologias diferentes **dentro** de uma mesma `Edificacao`
ainda podem se compensar e produzir `CONFORME` possivelmente falso — limitação
declarada, não resolvida aqui. Não se pode usar `unidades_previstas` como
denominador, nem ler número de UHs das declarações.

## Evidência
- Os três números têm dono: `Empreendimento.unidades_previstas`,
  `ModeloBIM.unidades_representadas`, `Edificacao.unidades`.
- A regra consome um só, por `core/dominio/ancora.py`:
  `core/regras/bim/edi_001_002_area_util_uh.py` e
  `core/regras/bim/edi_004_programa_necessidades.py`.
- A âncora por argumento nomeado: `conteiner=` em `core/composicao.py`,
  resolvida em `app/servicos/analise.py`, guardada em `Contexto.conteiner`.
- `NUM_UHS` fora de `core/dominio/vocabulario/declaracoes.py`; a chave do
  esquema antigo mora em `core/infra/persistencia/empreendimento_json.py`.
- `tests/core/dominio/test_ancora.py`, `test_pipeline_empreendimento.py` e
  `tests/app/servicos/test_analise_regressoes.py`.
- Linha de base do Estrela I: `programa` 7 de 7 conforme com 1 UH representada,
  `EDI-002` 56,81 m² ≥ 41,50 m² — inalterados pela mudança.
