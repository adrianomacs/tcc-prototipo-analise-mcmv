# ADR-002 — `core/` organizado em anéis; as quatro camadas são fluxo, não pacotes
**Status:** Aceita

## Contexto
Antes desta decisão, `core/` tinha um pacote por etapa do fluxo (`ingestao`, `georref`,
`motor`, `saida`). A mistura domínio × adaptador era sistemática: a entidade
`Ambiente` vivia dentro de um leitor de IFC, os VOs de georreferenciamento ao
lado de um cliente HTTP, a porta `Roteador` na pasta dos seus adaptadores.
Pacote nomeado por etapa de fluxo não diz nada sobre dependência.

## Decisão
`core/` tem quatro anéis, com a dependência apontando para dentro, na ordem
que `tests/arquitetura/test_aneis.py` impõe: `dominio/` (entidades, VOs,
contratos e portas, vocabulário, conhecimento) não importa nenhum outro anel;
`regras/` importa só `dominio/`; `aplicacao/` importa `regras/` e `dominio/`;
`infra/` é o anel externo e importa só `dominio/`. Fora deles fica um único
módulo de composição, `core/composicao.py` (ADR-037), que nenhum anel importa.
Critério de admissão em `dominio/`, mecânico: não importar `ifcopenshell`,
`ifctester`, `urllib`, `geopandas`, `csv`/`yaml`/`json` para I/O nem
`os.path` para arquivo (`shapely` e `pyproj` são permitidos — são
matemática). As quatro camadas (ingestão → georreferenciamento → motor →
saída) permanecem como **visão comportamental**: são o fluxo que
`core/composicao.py:rodar` percorre, não a organização dos pacotes.
Anéis = estrutura; camadas = comportamento.

## Consequências
Fica fácil saber onde um módulo novo mora ("o que ele importa?", não "em que
etapa roda?") e testar o domínio sem fixture em disco. Fica difícil manter a
leitura "quatro camadas = quatro pacotes", que deixou de ser verdadeira. A
regra vale sem exceção: (a) as regras BIM leem o modelo pela porta
`LeituraModelo` (ADR-036), e não pelos *helpers* de `infra/ifc/`; (b) a chave
do diagnóstico que o exportador do relatório reconhece mora no vocabulário do
domínio (`dominio/vocabulario/tipos_diagnostico.py`), e não em
`regras/base/agregacao`; (c) o I/O do CSV de municípios mora em
`infra/gis/csv_municipios.py`, e não em `dominio/conhecimento/municipios.py`.
O teste-guarda dos anéis prende a regra.

## Evidência
- Árvore real: `core/{dominio,regras,aplicacao,infra}/` e `core/composicao.py`.
- `tests/arquitetura/test_aneis.py` (varredura por `ast`, inclusive import
  local; reprova aresta para fora e módulo fora dos anéis).
- Camadas como fluxo: `# Camadas I e II` e `# Camada IV` em
  `core/composicao.py:rodar`, `# Camada III` em `core/aplicacao/pipeline.py:analisar`.
- `tests/arquitetura/test_imports_legados.py` (nenhum import dos pacotes antigos
  sobrevive).
