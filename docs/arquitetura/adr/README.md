# ADRs — registros de decisão de arquitetura

Um ADR (*Architecture Decision Record*) registra **uma** decisão estrutural: o
problema que a motivou, o que se decidiu, o que isso torna mais fácil e mais
difícil, e onde a decisão está materializada em código e em teste. Formato
curto (Nygard), em português, com alvo de 40 linhas (os mais densos chegam a
~48; passar disso é sinal de que há duas decisões no mesmo arquivo).

## Por que ADRs neste repositório

Os ADRs são a âncora estável das decisões de arquitetura: código e teste
citam ADR (ou DN), e a decisão fica registrada num lugar só, com o motivo.

A seção **Evidência** é o que torna cada ADR útil duas vezes: no
desenvolvimento, diz qual teste protege a decisão; para quem lê, dá a
rastreabilidade decisão → código → teste.

## O que NÃO entra aqui

Decisão sobre **como se lê o texto da Portaria** — o que uma cláusula ambígua
quer dizer, que edição de norma externa vale, o que fazer com alternativa sem
insumo público — vai para `../DECISOES_NORMATIVAS.md`, **arquivo único**, como
entrada DN-NN de ≤ 20 linhas. ADR fica para decisão sobre o **sistema**.

O motivo: arquitetura estabiliza e leitura normativa não, de modo que
misturá-las faria esta série crescer na velocidade da implementação da
norma. Uma pergunta de leitura que **gera** uma decisão de sistema vira duas
entradas que se citam — a DN diz o que a norma quer dizer, o ADR diz como o
motor faz. Os ADRs **012, 014, 016, 017, 019 e 025** eram normativos e
antecediam a regra: viraram as **DN-03 a DN-08**, e o arquivo de cada um
ficou como remissão. O ADR-019 não tem arquivo: convertido na DN-07, saiu
com ela quando a FRE deixou de ser fonte do protótipo, e o número não se
reaproveita.

## Estados

`Aceita` · `Substituída por ADR-XXX` · `Convertida em DN-NN` · `Recusada` ·
`Retirado` (só a linha do índice fica, para o número não ser reaproveitado).
Uma decisão revista não é editada: escreve-se um ADR novo e o antigo passa a
`Substituída por`. `Convertida em DN-NN` é o ADR que registrava leitura
normativa e migrou para `../DECISOES_NORMATIVAS.md`: o arquivo fica reduzido a
remissão, e código e teste citam a DN.

## Índice

### Arquitetura (série 001–011)

| # | Título | Status |
|---|---|---|
| [001](ADR-001-comunicacao-por-artefatos.md) | Núcleo e interface comunicam-se apenas por artefatos em formatos abertos | Aceita |
| [002](ADR-002-core-em-aneis.md) | `core/` organizado em anéis; as quatro camadas são fluxo, não pacotes | Aceita |
| [003](ADR-003-gateway-app-servicos.md) | `app/servicos/` é o único importador de `core/` dentro de `app/` | Aceita |
| [004](ADR-004-empreendimento-raiz-de-agregado.md) | `Empreendimento` é a raiz de agregado da análise | Aceita |
| [005](ADR-005-uma-regra-um-arquivo.md) | Uma regra = um arquivo, com registro por autodescoberta; a subpasta acompanha o domínio declarado | Aceita |
| [006](ADR-006-tres-estados-e-motivos.md) | Três estados de saída; o "não avaliável" sempre com motivo da taxonomia | Substituída por ADR-022 |
| [007](ADR-007-ids-requisito-de-informacao.md) | O IDS é requisito de informação do contratante, fora da fronteira do protótipo | Aceita (estendida pelo ADR-027) |
| [008](ADR-008-emp-001-portao-espacial.md) | EMP-001 é portão da trilha espacial, não abortador global | Aceita |
| [009](ADR-009-3d-tiles-nivel-1.md) | 3D Tiles é o artefato de geometria; a visualização é de nível 1, com nível 2 sob seleção | Aceita |
| [010](ADR-010-navegacao-como-dado.md) | Navegação como dado: árvore de três níveis com renderizador nativo | Aceita |
| [011](ADR-011-territorio-resolvido-pela-aplicacao.md) | A aplicação resolve o território antes do motor; provedores são injetados | Aceita |

### Domínio, norma e interface (série 012–038)

| # | Título | Status |
|---|---|---|
| [012](ADR-012-premissa-ifc4-georreferenciamento.md) | Georreferenciamento exige IFC4; via por property set em IFC2X3 recusada | Convertida em DN-03 |
| [013](ADR-013-euclidiana-piso-ors-snap-centroide.md) | A euclidiana é piso que só reprova; ORS é o único provedor de rede; a origem da medida é sempre o centróide | Aceita |
| [014](ADR-014-alternativa-sem-insumo-publico-e-remetida.md) | Alternativa normativa sem insumo público vira regra remetida, não requisito ausente | Convertida em DN-04 |
| [015](ADR-015-agregacao-por-limites.md) | Agregação por limites `[n_conf, n_pot]`; conformidade e cobertura contam requisitos da Portaria | Aceita (estendida pelo ADR-026) |
| [016](ADR-016-recorte-educacao-publico-ativo.md) | O recorte avalia só equipamentos de educação, públicos e ativos; conveniadas entram como sensibilidade | Convertida em DN-05 |
| [017](ADR-017-censo-escolar-fonte-canonica.md) | Equipamento de educação vem de três fontes do Censo Escolar por precedência por campo; base nacional não versionada | Convertida em DN-06 |
| [018](ADR-018-porte-municipal-derivado-censo-2022.md) | `porte_municipal` é derivado do Censo 2022 (SIDRA tab. 4714), nunca declarado pelo usuário | Substituída por ADR-030 |
| 019 | *(retirado com a DN-07 que o sucedera: a FRE deixou de ser fonte do protótipo)* | Retirado |
| [020](ADR-020-edificacao-magra-e-modelobim-vo.md) | `Edificacao` é entidade magra; `ModeloBIM` é objeto de valor anexável ao terreno e a ela | Substituída por ADR-023 |
| [021](ADR-021-tres-numeros-de-uh.md) | São três os números de UH; a regra consome só `unidades_representadas` | Aceita (anotada pelo ADR-028) |
| [022](ADR-022-inconsistencia-declaratoria.md) | "Inconsistência declaratória" entra na taxonomia do não avaliável | Substituída por ADR-033 |
| [023](ADR-023-unidade-tipo-e-edificacao-fisica.md) | `UnidadeTipo` é o grupo de UH que se repete; `Edificacao` é o prédio físico, ligado a ela por composição | Aceita |
| [024](ADR-024-zona-bioclimatica-derivada.md) | `zona_bioclimatica` é derivada da edição vigente da ABNT NBR 15220-3, nunca declarada pelo usuário | Substituída por ADR-030 |
| [025](ADR-025-vocabulario-normativo-superado.md) | Cláusula em vocabulário normativo superado não é traduzida; conclui-se só o que é invariante à leitura | Convertida em DN-08 |
| [026](ADR-026-ramos-por-zona-sob-pai.md) | Requisito com parâmetro condicionado à zona é um pai com ramos filhos; o pai conclui por seleção exclusiva | Aceita |
| [027](ADR-027-covering-classificado-e-requisito-de-informacao.md) | O acabamento avaliado por absortância é `IfcCovering` classificado; a relação com o hospedeiro nunca é inferida por heurística | Aceita |
| [028](ADR-028-contagem-de-uh-do-empreendimento-e-declarada.md) | Limite de UH por empreendimento se confere pelo total declarado da proposta, nunca pelo modelo | Aceita |
| [029](ADR-029-crs-do-memorial-declarado.md) | O CRS do CSV de memorial é declarado na importação, nunca deduzido das coordenadas | Aceita |
| [030](ADR-030-atributo-territorial-derivado.md) | Atributo do território é derivado do município, nunca declarado, de fonte versionada em snapshot local | Aceita (consolida o ADR-018 e o ADR-024) |
| [031](ADR-031-ambiente-fantasma-sai-da-populacao.md) | Ambiente com indício de defeito de autoria sai da população das regras e é reportado, nunca avaliado | Aceita |
| [032](ADR-032-posicionamento-no-terreno-e-aviso.md) | O confronto da âncora do modelo com a poligonal do terreno é aviso, nunca veredito | Aceita |
| [033](ADR-033-insumo-do-proponente-ausente.md) | "Insumo do proponente ausente" entra na taxonomia do não avaliável | Aceita |
| [034](ADR-034-padrao-de-pagina-de-checagem-e-de-relatorio.md) | Página de checagem e página de relatório seguem uma anatomia única | Aceita |
| [035](ADR-035-relatorio-de-checagem-descritivo.md) | O Relatório de Checagem é um texto descritivo montado só das análises gravadas | Aceita |
| [036](ADR-036-porta-de-leitura-do-modelo.md) | As regras leem o modelo BIM por uma porta do domínio; o LoGeoRef é calculado na ingestão | Aceita |
| [037](ADR-037-composicao-fora-dos-aneis.md) | Um módulo de composição fora dos anéis monta e grava; o caso de uso não faz I/O | Aceita |
| [038](ADR-038-divergencia-de-posicao-do-modelo.md) | A divergência entre a coordenada do IfcSite e a origem do IfcMapConversion é diagnóstico, nunca veredito | Aceita |

## Relações entre os ADRs

- **Taxonomia do não avaliável:** ADR-006 → ADR-022 (16º motivo) → ADR-033
  (17º motivo); cada extensão revisa a anterior, porque a lista é fechada por
  decisão.
- **Unidades e edificações:** ADR-004 (raiz de agregado) → ADR-020, ADR-021 e
  ADR-022 → ADR-023 (`UnidadeTipo` e `Edificacao` física), que substitui o
  ADR-020 e anota o ADR-021 e o ADR-022; o ADR-028 anota o ADR-021 e é o
  primeiro emissor do ADR-022.
- **Atributos do território:** ADR-018 (porte) e ADR-024 (zona bioclimática)
  → ADR-030, padrão com tabela de instâncias.
- **Absortância:** DN-08 (ex-ADR-025) → ADR-026 (pai com ramos por zona,
  quarto modo de agregação do ADR-015) e ADR-027 (acabamento como
  `IfcCovering` classificado, que estende o ADR-007).
- **Anéis:** ADR-002, com o ADR-036 (porta de leitura do modelo) e o ADR-037
  (composição fora dos anéis), verificado por `tests/arquitetura/test_aneis.py`.
- **Tela:** ADR-034 (anatomia das páginas) e ADR-035 (relatório descritivo).
- **Parte de sistema das DN:** a premissa IFC4 (DN-03, ex-ADR-012) está no
  ADR-008; a alternativa remetida (DN-04, ex-ADR-014), no ADR-015.

## Modelo para um ADR novo

```markdown
# ADR-NNN — <título afirmativo, no presente>
**Status:** Aceita

## Contexto
O problema, em 3–6 linhas. O que existia antes e por que não servia.

## Decisão
O que se faz, no presente do indicativo. Uma decisão por ADR.

## Consequências
O que fica mais fácil, o que fica mais difícil, e o que NÃO se pode
fazer daqui em diante. Exceções declaradas entram aqui, nomeadas.

## Evidência
Módulos que materializam a decisão e testes que a protegem. Conferido
contra o código na data do ADR — nada aqui é citado de memória.

## Relações
ADRs que esta decisão substitui, revisa, anota, estende ou completa (quando houver).
```

Arquivo novo aqui só nasce com a linha correspondente no índice acima e em
`docs/README.md`.
