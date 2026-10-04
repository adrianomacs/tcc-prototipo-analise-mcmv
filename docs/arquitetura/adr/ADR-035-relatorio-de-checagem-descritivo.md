# ADR-035 — O Relatório de Checagem é um texto descritivo montado só das análises gravadas
**Status:** Aceita

## Contexto
A 2.4.2 repetia a Cobertura do Protótipo (2.4.1): as mesmas contagens e as
mesmas tabelas por checagem. Faltava um texto corrido, no estilo de um
parecer, com as pendências separadas por quem tem de agir. Texto gerado sobre
norma erra em silêncio; por isso a regra de montagem é decisão, não detalhe.

## Decisão
O texto é **montado de forma determinística** a partir dos relatórios das
checagens gravados na pasta `artefatos/`, subpasta `relatorios/`, do
empreendimento corrente (ADR-001):
sem modelo de linguagem, sem frase que não decorra de um requisito
verificado. Seis blocos, nesta ordem:
(1) **abertura** — a frase do empreendimento (ADR-034 (d)), quantas das cinco
checagens rodaram, o total de requisitos com as contagens e a versão das
Informações Gerais analisada; (2) **um parágrafo por checagem** — aberto pelos
**insumos que a análise consumiu** (arquivo do modelo ou do terreno, bases,
serviço de cálculo da distância caminhável, data), lidos do relatório gravado e nunca da sessão do Streamlit, para
amarrar cada resultado ao que o produziu; depois o que se verificou (descrição
de cada requisito, com o id) e o resultado de cada um, com o exigido e o
medido montados dos campos que a regra gravou; os não avaliáveis agrupados
pelo rótulo do motivo; (3) **limites da análise** — diagnósticos marcados,
ambientes deixados de fora, checagens não executadas, o recorte e as **notas
padrão** dos casos inconclusivos (abaixo); (4) **pendências por
destinatário**; (5) **arquivos analisados** — nome e SHA-256 de cada
arquivo submetido (modelo IFC, arquivo do terreno), sem repetir; o corpo do
texto cita só o nome, para não quebrar a leitura; (6) **nota de natureza**:
síntese automática, que não substitui o parecer do analista.

**Registro dos arquivos.** Para que a amarração seja inequívoca — nome não
identifica conteúdo, e o mesmo arquivo reexportado é outro —, quem **consome**
o arquivo calcula o SHA-256: o pipeline carimba `ModeloBIM.digest` no
contêiner da execução (como já faz com o `schema`) e o leitor do terreno o
grava na procedência; o relatório ganha `meta.arquivos` (`papel`, `arquivo`
só com o nome, `sha256`). Relatório anterior ao registro aparece com a
impressão "não registrada", nunca inventada.

**Pendências.** Só geram pendência o que decide um requisito da Portaria: o
requisito não conforme e o não avaliável. Alternativa ou ramo de requisito já
decidido **não** gera pendência — o requisito agrupa as vias, e cumprido ou
reprovado está decidido. Num requisito em aberto cujas alternativas são vias
distintas ("ou"/"e"), a pendência é de cada alternativa em aberto; num
requisito de ramos por zona (ADR-026), é do próprio requisito. Não
conformidade vai ao proponente com ação genérica ("revisar a proposta ou
demonstrar o atendimento") e o exigido × medido — o protótipo não sugere
correção. Não avaliável vai pelo motivo:

| Destinatário | Motivos |
|---|---|
| Proponente | `informacao_ausente`, `insumo_do_proponente_ausente`, `inconsistencia_declaratoria`, `terreno_insuficiente`, `terreno_ausente` |
| Análise humana | `verificacao_em_campo`, `analise_humana_documental`, `porte_indeterminado` |
| Ferramenta e bases | `metrica_insuficiente`, `insumo_ausente`, `insumo_suspeito`, `mapeamento_pendente`, `membro_nao_executado`, `erro_de_execucao` |
| Nenhum (só no texto) | `nao_aplicavel`; `prerequisito_falho` (anexado à pendência do pré-requisito); `agregacao_indecisa` (desdobrado nas alternativas) |

A ação de cada motivo é a de `motivos.ACAO`, a mesma da tela. Termo IFC entra
entre parênteses na 1.ª menção (ADR-034 (e)).

**Notas padrão.** Caso que o protótipo deixa inconclusivo por construção
recebe uma explicação fixa, disparada por campo gravado e citada uma vez, com
os requisitos a que se aplica: linha reta como piso da distância (ADR-013);
alternativa remetida por falta de dado público (DN-04); faixa de zona em
vocabulário superado (DN-08); zona do município não resolvida (ADR-030).

**Apresentação na tela.** O parágrafo de cada checagem se parte em
**introdução** (os insumos e a frase que anuncia os requisitos verificados) e
uma **tabela** de requisito, descrição, resultado e detalhe (o exigido e o
medido, ou o que ficou em aberto); as pendências por destinatário também vão em
tabela, sob a frase da ação, e os arquivos analisados em tabela de nome e
SHA-256. É a mesma informação em outro formato: nenhum requisito a mais, nenhuma
frase nova, e `Parecer.texto()` segue o texto de referência, idêntico, com o
parágrafo inteiro. O que a página desenha mora em `Parecer.blocos`, montado
pelos mesmos auxiliares do parágrafo.

## Consequências
O texto é reproduzível e auditável: mesmo relatório, mesmo texto. Motivo novo
na taxonomia quebra o teste de cobertura da tabela até ganhar destinatário.
Mudar mensagem de regra não muda o texto onde há modelo de frase por tipo.
Não se pode: frase escrita à mão sobre um requisito específico, pendência de
via já decidida, citação de ADR/DN no texto, exportação (.docx) sem decisão.

## Evidência
`core/infra/impressao_digital.py`; `pipeline.arquivos_consumidos` e o carimbo em
`montar_contexto` (`core/composicao.py`); `sha256` na procedência de
`core/infra/gis/csv_memorial.py` e de `extrator_terreno.resolver_arquivo`;
`tests/core/infra/test_impressao_digital.py`,
`tests/core/aplicacao/test_pipeline_empreendimento.py`. Texto:
`app/servicos/parecer.py` (construtor puro) e
`tests/app/servicos/test_parecer.py` (um teste por bloco, a tabela contra os
17 motivos, relatórios gerados pelas regras reais) Os blocos da tela:
`tests/app/servicos/test_parecer_blocos.py`. Página:
`app/paginas/checagens/relatorio_checagem.py`, no ADR-034.
