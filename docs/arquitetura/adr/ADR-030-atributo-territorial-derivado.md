# ADR-030 — Atributo do território é derivado do município, nunca declarado, de fonte versionada em snapshot local
**Status:** Aceita (consolida o ADR-018 e o ADR-024)

## Contexto
Parte dos requisitos da Portaria depende de atributos do **território**, não
do projeto: o porte populacional (limite de UH do Anexo II, 4.I.a; equipamentos
do Anexo I), a zona bioclimática (absortância, ventilação e esquadrias do Anexo
III), a densidade demográfica (ENQ-001.1). O ADR-018 e o ADR-024 responderam
duas vezes à mesma pergunta — campo digitado ou valor resolvido? — com a mesma
resposta, e o terceiro atributo pediria um terceiro ADR.

## Decisão
**Derivado, nunca declarado.** Sem campo de sobrescrita e sem seletor na
interface. A cadeia é uma só: `Localizacao.codigo_ibge` → leitura do snapshot
em `core/infra/gis/` → campo do `Contexto`, resolvido pela aplicação **antes**
do motor (ADR-011) e gateado pelo município declarado, nunca pelo terreno. O
`dominio/` recebe o valor pronto, com a procedência, e não faz I/O (ADR-002).

**Fonte versionada em snapshot local.** `config/<base>.csv` + `.json` de
procedência (URL ou sha256 de cada fonte, data de referência, data de
geração), regerado por script em `scripts/`. Trocar de fonte ou de edição
muda veredito: é decisão datada, registrada na linha da instância, não
configuração. O alcance de cada faixa da Portaria é conferido contra a base
vigente, nunca suposto.

**Sem valor, nada é chutado.** Herdar o valor dos municípios de origem é regra
**da instância**, marcada na base e nunca silenciosa. **Viaja o dado**, não uma
classificação: cada regra classifica pela tabela do próprio item.

| Instância | Fonte e edição | Snapshot → `Contexto` | Sem valor | Consome |
|---|---|---|---|---|
| População (porte) | Censo 2022, SIDRA 4714 (31/07/2022), nunca a estimativa anual | `municipios_ibge.csv` → `populacao_municipal` | NÃO AVALIÁVEL, `porte_indeterminado`; sem herança (o Censo não contou município posterior) | EMP-025.1 |
| Zona bioclimática | ABNT TR 15220-3-1:2024 — a edição **vigente**, não a que a Portaria cita | `zonas_bioclimaticas.csv` → `zona_bioclimatica` | herança só com origens unânimes, marcada em `fonte`; sem ela, os dois ramos ficam candidatos (ADR-026) | EDI-019, EDI-024 e ramos |
| Densidade demográfica | a mesma consulta SIDRA 4714 | `municipios_ibge.csv` → `PopulacaoMunicipal.densidade` | — | prevista: ENQ-001.1 |

A instância seguinte não pede ADR: pede uma linha nesta tabela.

## Consequências
Fica fácil condicionar uma regra a um atributo do território (lê o
`Contexto`, não abre arquivo) e defender o resultado, rastreável até a fonte.
Atributo derivado pode **governar aplicabilidade** sem ser declarado — papel
que antes só `Declaracoes` tinha. Fica difícil trocar de edição em silêncio,
que é o ponto. As faixas de parede da redação de 2025 esgotam as doze classes
(não há `NAO_APLICAVEL` por zona); as de telhado são a DN-08. O recorte de
equipamentos (DN-06) segue a mesma disciplina de snapshot, mas não é instância:
é coleção por município e admite CSV do usuário. Não se pode aceitar valor
digitado, herdar sem marcar, nem injetar atributo derivado em `declaracoes`.

## Evidência
- Bases: `scripts/gerar_municipios.py` → `config/municipios_ibge.csv`/`.json`;
  `scripts/gerar_zonas_bioclimaticas.py` → `config/zonas_bioclimaticas.csv`/`.json`.
- Leitores únicos: `core/infra/gis/csv_municipios.py`,
  `core/infra/gis/csv_zonas_bioclimaticas.py`. Valores de domínio, sem I/O:
  `core/dominio/conhecimento/porte_municipal.py` (`PopulacaoMunicipal`, faixas
  por item) e `core/dominio/conhecimento/zona_bioclimatica.py` (doze classes).
- Resolução: `core/aplicacao/resolver_territorio.py`
  (`populacao_para_empreendimento`, `zona_para_empreendimento`) e os campos do
  `Contexto` em `core/dominio/contratos/regra.py`. Consumidores:
  `core/regras/gis/emp_025_1_limite_uh_empreendimento.py`,
  `core/regras/base/absortancia.py`.
- `tests/core/aplicacao/test_resolver_territorio.py`
  (`::test_o_porte_nao_tem_caminho_por_declaracao`,
  `::test_a_zona_nao_tem_caminho_por_declaracao`,
  `::test_zona_NAO_se_gateia_por_terreno`);
  `tests/core/infra/gis/test_csv_municipios.py::test_municipio_instalado_depois_do_censo_fica_sem_populacao`;
  `tests/core/infra/gis/test_csv_zonas_bioclimaticas.py`;
  `tests/core/dominio/conhecimento/test_porte_municipal.py`,
  `test_zona_bioclimatica.py`.

## Relações
Consolida o ADR-018 e o ADR-024, que ficam como `Substituída por ADR-030`.
