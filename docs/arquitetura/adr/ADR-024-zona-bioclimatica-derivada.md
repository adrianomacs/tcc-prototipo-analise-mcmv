# ADR-024 — `zona_bioclimatica` é derivada da edição vigente da ABNT NBR 15220-3, nunca declarada pelo usuário
**Status:** Substituída por ADR-030

> **Substituída por ADR-030**, que consolida este ADR e
> o ADR-018 num padrão com tabela de instâncias; a zona bioclimática é uma
> linha dela, sem mudança de decisão. A troca de edição da norma, que este ADR
> mandava registrar aqui, passa a ser registrada na linha da instância no
> ADR-030. A leitura das cláusulas em vocabulário de 2005 é a DN-08 (ex-ADR-025).

## Contexto
Uma família de requisitos do Anexo III da Portaria MCID 725 é condicionada à
**zona bioclimática** do sítio: absortância de parede (EDI-019/019.1) e de
telhado (EDI-024/024.1), ático (EDI-023), ventilação (EDI-016/017), esquadrias
(EDI-036.3). A zona não é característica do projeto nem escolha do proponente:
é **atributo do território**, atribuído por norma técnica — mesma natureza do
`porte_municipal` do ADR-018. A pergunta era se seria campo digitado ou valor
resolvido, e de qual edição da norma.

## Decisão
**Fonte, versão e atualização.** A zona vem do snapshot
`config/zonas_bioclimaticas.csv`, gerado por
`scripts/gerar_zonas_bioclimaticas.py` a partir dos cinco PDFs regionais da
**ABNT TR 15220-3-1:2024**, com procedência em `config/zonas_bioclimaticas.json`
(sha256 por PDF, data de geração, base de localidades de 2023-05-02 que a norma
declara usar). É sempre a **edição vigente da norma**, não a que a Portaria
cita. Edição nova se adota regerando o snapshot e **registrando a troca neste
ADR**: ela muda veredito — a de 2024 mudou, e suas doze classes (1M, 1R, 2M,
2R, 3A, 3B, 4A, 4B, 5A, 5B, 6A, 6B) não preservam a numeração das oito zonas de
2005. Versão de norma não é configuração; é decisão datada.

**Derivada, nunca declarada.** `Localizacao.codigo_ibge` → leitura do snapshot
em `core/infra/gis/` → `Contexto.zona_bioclimatica`, resolvida pela aplicação
**antes** do motor (ADR-011). Sem campo de sobrescrita e sem seletor na
interface: o `dominio/` recebe o valor pronto e não faz I/O.

**Duplo papel — e o papel novo.** A ZB (1) **fornece o parâmetro** do requisito
e (2) **decide a aplicabilidade** dele. O segundo é papel novo: quem governa
aplicabilidade hoje é `Declaracoes`, que é **declarado**
(`vocabulario/declaracoes.py`: "governa aplicabilidade, nunca insumo"). A ZB o
faz **sem ser declarada**. O alcance de cada faixa é conferido contra o mapa
vigente, nunca suposto: as faixas de parede da redação de 2025 — "1 e 2 (R e
M)" e "3, 4, 5 e 6 (A e B)" — **esgotam as doze classes**, logo EDI-019/019.1
têm limite em todo município brasileiro e **não existe `NAO_APLICAVEL` por zona
fora de faixa**. As de telhado citam zonas que o mapa vigente não publica — é
o ADR-025.

**Município ausente: herança declarada, nunca silenciosa.** Município instalado
depois da base de localidades da norma não tem linha (hoje só Boa Esperança do
Norte/MT, 5101837, de 01/01/2025). Com zona **unânime** nos municípios de
origem ela é herdada — o território é o mesmo e não há interpretação a fazer
(Boa Esperança do Norte veio de Sorriso e Nova Ubiratã, ambos **5B**) — e a
herança é **visível**: a base a marca em `fonte` e nomeia as origens. Origem
divergente, ou município sem origem identificável, não é herdado: sai NÃO
AVALIÁVEL. A constante do motivo **não** nasce agora — a taxonomia é fechada
por decisão (ADR-006/022) e o motivo entra com o **primeiro emissor**, por ADR
próprio, como o ADR-022 enunciou. Hoje não há emissor: com a herança, os 5.571
municípios do IBGE têm zona.

## Consequências
Fica fácil condicionar uma regra à zona (lê `ctx.zona_bioclimatica`, não abre
arquivo) e defender o resultado: rastreável até o PDF por sha256, com a herança
à vista em vez de escondida. Fica fácil datar a próxima edição da norma.
Fica difícil trocar de edição em silêncio — que é o ponto. Não se pode aceitar
zona digitada pelo usuário, herdar zona sem marcá-la, nem tratar município sem
zona como zona qualquer.

## Evidência
- `config/zonas_bioclimaticas.csv` e `.json`; `scripts/gerar_zonas_bioclimaticas.py`.
- `core/infra/gis/csv_zonas_bioclimaticas.py` (a leitura; o `dominio/` não a faz);
  `core/dominio/conhecimento/zona_bioclimatica.py` (as doze classes, sem I/O).
- `core/aplicacao/resolver_territorio.py`, `pipeline.py:montar_contexto`,
  `Contexto.zona_bioclimatica` em `core/dominio/contratos/regra.py`.
- `tests/core/infra/gis/test_csv_zonas_bioclimaticas.py`,
  `tests/core/dominio/conhecimento/test_zona_bioclimatica.py`,
  `tests/core/aplicacao/test_resolver_territorio.py`.
- Na redação deste ADR nenhuma regra a consumia; o consumo veio com o ADR-026
  e o ADR-030.

## Relações
Estende o ADR-018 e o ADR-011.
