# Fontes — ABNT TR 15220-3-1:2024 (zonas bioclimáticas)

Esta pasta guarda os cinco PDFs regionais do Relatório Técnico
**ABNT TR 15220-3-1:2024**, insumo de `scripts/gerar_zonas_bioclimaticas.py`.

| Arquivo | Páginas | Linhas de município |
|---|---|---|
| `ABNT_TR_15220-3-1_2024_Norte.pdf` | 12 | 450 |
| `ABNT_TR_15220-3-1_2024_Nordeste.pdf` | 45 | 1.794 |
| `ABNT_TR_15220-3-1_2024_Centro_Oeste.pdf` | 12 | 467 |
| `ABNT_TR_15220-3-1_2024_Sudeste.pdf` | 42 | 1.668 |
| `ABNT_TR_15220-3-1_2024_Sul.pdf` | 30 | 1.191 |
| **Total** | 141 | **5.570** |

Os SHA-256 de cada arquivo ficam em `config/zonas_bioclimaticas.json`, gravados
a cada execução do gerador.

## Por que não são versionados

Norma ABNT: obra protegida, de aquisição onerosa e redistribuição vedada. O
`.gitignore` exclui `entradas/abnt/*.pdf` — o que se versiona é o **derivado**
(`config/zonas_bioclimaticas.csv`) junto do JSON de procedência, no mesmo padrão
do recorte de equipamentos do INEP. Para regerar a base é preciso obter os PDFs
na ABNT e colocá-los aqui com os nomes acima (o gerador aceita qualquer nome
`*.pdf` nesta pasta; os nomes da tabela são só a convenção adotada).

## O que a tabela traz

Por município: zona bioclimática, latitude, longitude, altitude e cinco médias
anuais (TBS, UR, radiação horizontal global diária, velocidade do vento e
amplitude térmica). A zona é atribuída pelo método da **ABNT NBR 15220-3**.

## Duas ressalvas registradas na leitura

1. **O número de cidades declarado no texto não confere com a tabela.** A norma
   diz fornecer a zona "para cada uma das 5 507 cidades", citando a API de
   localidades do IBGE com acesso em 02/05/2023. A tabela traz **5.570 linhas** —
   exatamente o total de municípios do Brasil naquela data, com a contagem por
   região batendo uma a uma com a do IBGE. A cobertura é integral; o "5 507" é
   erro de redação.

2. **O vocabulário de zona mudou nesta edição.** São 12 classes
   (1M, 1R, 2M, 2R, 3A, 3B, 4A, 4B, 5A, 5B, 6A, 6B), e **não** as oito zonas
   numéricas (Z1–Z8) da ABNT NBR 15220-3:2005. A numeração não se preserva entre
   as edições. Isso tem consequência direta sobre como a Portaria MCID 725 é
   lida — ver a DN-08, em `docs/arquitetura/DECISOES_NORMATIVAS.md`.
