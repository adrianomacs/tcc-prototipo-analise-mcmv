# Fontes do INEP usadas pelo módulo de Enquadramento

Esta pasta guarda as bases **nacionais** que alimentam
`scripts/gerar_equipamentos.py`. Elas **não são versionadas** (ver `.gitignore`):
somam cerca de 327 MB e são redistribuídas pelo próprio INEP, então versioná-las
seria inchar o repositório com o que já está publicado e é obtível por qualquer
um. O que o repositório guarda é o **recorte derivado por município**, em
`config/equipamentos_<codigo_ibge>.csv`, mais o `.json` de procedência que o
torna conferível.

A **exceção** é o dicionário de dados, que é versionado: tem 240 KB, é a
autoridade sobre o significado de cada variável, e é dele que saem as decisões
de mapeamento explicadas abaixo, em "Por que três fontes, e não uma".

## Os arquivos

| Arquivo | O que é | Origem | Versionado |
|---|---|---|---|
| `Tabela_Escola_2025_V2.csv` | microdados do Censo Escolar 2025 — uma linha por estabelecimento: identidade, dependência administrativa, situação de funcionamento, modalidades | INEP, Censo Escolar da Educação Básica 2025 | não |
| `Tabela_Turma_2025_V2.csv` | microdados do Censo Escolar 2025 — uma linha por estabelecimento com as **contagens de turma por etapa** (`QT_TUR_*`) | idem | não |
| `dicionário_dados_educação_básica.xlsx` | dicionário oficial das variáveis dos microdados, com descrição e vocabulário de cada coluna, por tabela | idem (acompanha o pacote de microdados) | **sim** |
| `Análise - Tabela da lista das escolas - Detalhado.csv` | export nacional do **Catálogo de Escolas**, sem filtros — traz `Latitude`, `Longitude`, `Endereço` e `Conveniada Poder Público` | INEP, Catálogo de Escolas | não |

## Onde obter

* **Microdados do Censo Escolar** (as duas `Tabela_*` e o dicionário, num único
  pacote):
  <https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/censo-escolar>
  Safra usada: **2025**. O nome dos arquivos muda entre safras — em 2024 e
  anteriores o arquivo de escolas se chamava `microdados_ed_basica_<ano>.csv`.
  Por isso `gerar_equipamentos.py` reconhece as fontes por **prefixo**, não por
  nome exato.
* **Catálogo de Escolas** (o export detalhado):
  <https://www.gov.br/inep/pt-br/areas-de-atuacao/pesquisas-estatisticas-e-indicadores/censo-escolar>
  O export deve ser gerado **sem aplicar filtros** no portal — situação,
  categoria administrativa e etapa são tratadas pelo código, e filtrar na origem
  esconderia os descartes que o relatório precisa contabilizar.

Os dois portais são do INEP/MEC e os dados são de uso público. O SHA-256 de cada
arquivo efetivamente usado fica gravado em cada
`config/equipamentos_<codigo>.json`, junto do ano de referência e da data da
geração — é o que permite a um terceiro confirmar que um número deste trabalho
saiu **daqueles** arquivos.

## Por que três fontes, e não uma

Nenhuma responde sozinha. A divulgação pública de 2025 retirou o bloco de
endereço do microdado (não há coordenada) e não traz indicador de oferta de
etapa. Por isso a composição é por campo: identidade, rede e situação vêm do
microdado de escolas; a etapa vem das contagens de turma (turma maior que zero
numa etapa é oferta dela); a coordenada, o endereço e o convênio vêm do
Catálogo. A armadilha é o `IN_COMUM_FUND_AI`: apesar do nome, é indicador de
educação especial, e não de oferta de etapa; tomado como etapa, daria 14 das
29 escolas de Estrela como "fundamental I". Do mesmo modo,
`IN_PODER_PUBLICO_PARCERIA` não é `conveniada`. A decisão está na DN-06, em
`docs/arquitetura/DECISOES_NORMATIVAS.md`.
