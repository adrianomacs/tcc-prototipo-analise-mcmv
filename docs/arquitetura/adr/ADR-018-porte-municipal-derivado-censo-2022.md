# ADR-018 — `porte_municipal` é derivado do Censo 2022 (SIDRA tab. 4714), nunca declarado pelo usuário
**Status:** Substituída por ADR-030

> **Substituída por ADR-030.** Este ADR e o ADR-024 eram
> a mesma decisão aplicada duas vezes — atributo do território derivado do
> município, nunca declarado, de fonte versionada em snapshot local —, e a
> densidade demográfica pediria a terceira. O ADR-030 é o padrão, com uma linha
> por instância; a população (porte) é a primeira, já no desenho do adendo
> abaixo. A injeção de faixas em `declaracoes`, descrita na Decisão, não foi
> implementada e não é o padrão: viaja a população, e cada regra classifica pela
> tabela do próprio item.

> **Adendo.** A Portaria não tem uma tabela de porte:
> cada item traz a sua (4.I.a do Anexo II corta em 20, 50, 100 e 500 mil; o
> Anexo I, em 100 e 250 mil). Por isso o que chega ao motor é a **população**,
> não um token: `scripts/gerar_municipios.py` grava população e densidade do
> Censo 2022 em `config/municipios_ibge.csv` (procedência no `.json` ao lado);
> `core/infra/gis/csv_municipios.py` lê; `resolver_territorio` a entrega em
> `Contexto.populacao_municipal`, pelo caminho da zona (ADR-024), e cada regra
> classifica pela tabela do próprio item (`core/dominio/conhecimento/
> porte_municipal.py`). As faixas de três valores e a injeção em
> `declaracoes["porte_municipal"]`, descritas abaixo, **não** foram
> implementadas: entram com o primeiro consumidor do Anexo I (ENQ-012/013/016).
> Sem população, o motivo é `porte_indeterminado`.

## Contexto
Requisitos condicionados ao porte do município (ENQ-012, 012.x, 013.x, 016)
precisavam de população municipal, ausente quando esta decisão foi tomada: o
`config/municipios_ibge.csv` só tinha `codigo_ibge;nome;uf;uf_nome`. O usuário já declara UF e município na
tela de georreferenciamento; a pergunta era se o porte deveria ser um campo
digitado ou um valor calculado.

## Decisão
O porte é **fato censitário**, não característica do projeto — sem campo de
sobrescrita, sem "porte declarado". A fonte é o Censo Demográfico 2022 (não a
estimativa anual), via SIDRA tabela 4714 ("População Residente, Área
territorial e Densidade demográfica"), referência 31/07/2022: é dado
censitário (levantado, não estimado por modelo), estável no tempo (o mesmo
terreno analisado hoje e em seis meses recebe o mesmo porte) e auditável
(fonte pública fixa). A cadeia é: usuário declara município → consulta ao
snapshot local (a gerar por `scripts/gerar_municipios.py` estendido) →
população → classificação nas faixas da própria Portaria (`ate_100k`,
`de_100k_a_250k`, `acima_250k`) → injeção em
`ctx.declaracoes["porte_municipal"]`, no mesmo dicionário que o guard de
aplicabilidade já lê — para não ensinar o executor a resolver uma segunda
fonte de aplicabilidade. Sem população disponível, o porte fica
**indeterminado** e as regras dependentes saem NÃO AVALIÁVEL com motivo
explícito — nunca uma faixa chutada.

## Consequências
Fica fácil, quando implementado, condicionar uma regra ao porte com um único
atributo de classe (`aplicabilidade = {"porte_municipal": [...]}`), sem tocar
o motor. Fica fácil aproveitar a mesma consulta SIDRA 4714 para a densidade
demográfica municipal, que o ENQ-001.1 também exige. Fica difícil (propriedade
assumida, não defeito) qualquer regra condicionada ao porte antes que
`scripts/gerar_municipios.py` seja estendido, e nenhuma regra ativa do
recorte dependia dela. Não se pode aceitar
porte digitado pelo usuário nem estimativa anual como substituto do Censo.

## Evidência
- Na redação original, `core/dominio/conhecimento/municipios.py` e
  `scripts/gerar_municipios.py` não traziam população; o adendo acima e o
  ADR-030 descrevem o que foi implementado.
- `core/dominio/conhecimento/porte_municipal.py` (classificação pela tabela
  de cada item) e `core/infra/gis/csv_municipios.py` (leitura da população).
