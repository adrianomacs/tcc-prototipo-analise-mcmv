# ADR-007 — O IDS é requisito de informação do contratante, fora da fronteira do protótipo
**Status:** Aceita

## Contexto
O IDS (*Information Delivery Specification*, buildingSMART) é o padrão aberto
para declarar requisitos de informação de um modelo IFC, e o IfcTester os
verifica. Era tentador tratá-lo como o motor de verificação, ou como o
pré-teste que autoriza cada regra a rodar. Duas coisas impedem: o IDS responde
"a propriedade existe e tem o tipo declarado?", nunca "esta largura atende ao
mínimo da Portaria?"; e, no estágio de maturidade BIM da CAIXA, **não existem
arquivos IDS do PMCMV** para exigir de ninguém.

## Decisão
O IDS é instrumento do **contratante**, a ser fornecido aos proponentes para
que validem o modelo **antes** de submetê-lo — um filtro da porta para fora do
sistema. O protótipo não o usa como pré-teste que impeça a execução: cada regra
produz o próprio veredito a partir do modelo, e informação ausente vira
`NAO_CONFORME` ou `NAO_AVALIAVEL` **com motivo, pela própria regra**. O EMP-001
é o caso exemplar: declara `ids_spec = None` porque é checagem estrutural do
IFC, e sem os dados do `IfcSite` ele roda igual, reportando o nível LoGeoRef
atingido e as lacunas.
A ordem é deliberada e é o argumento do trabalho: são as regras do protótipo
que permitirão debater os requisitos de informação do PMCMV e só então escrever
os arquivos IDS. Quando existirem, o IDS passa a barreira de entrada — e essa
é a evolução prevista, não o estado atual.

## Consequências
Fica fácil ser honesto com o estágio de maturidade: nenhuma regra fica
indisponível por falta de spec, e o relatório é a única fonte de veredito. Fica
difícil distinguir, para o usuário, "seu modelo não declara a informação" de
"seu projeto não atende" — distinção que só o IDS externo dará por completo; o
que o protótipo oferece hoje é a taxonomia de motivos (ADR-006).
Não se pode afirmar que o protótipo valida informação por IDS: o gancho existe,
mas está fora do recorte que roda. E não se migra regra dimensional para IDS —
ele não expressa dimensão, relação espacial nem agregação.

## Evidência
- Nenhuma regra registrada declara `ids_spec`: todas trazem `ids_spec = None`,
  inclusive `emp_001` ("checagem estrutural do IFC; nao depende de propriedade
  nominal") e as três da absortância (EDI-024 e os ramos 024.1/024.2). Nelas,
  o gancho do executor rodaria antes do `checar`, sobre todo `IfcCovering`, e
  falharia sem `ifctester`; a regra reporta a informação ausente por conta
  própria, como este ADR prevê.
- O gancho existe no executor, `core/aplicacao/executor.py` (`if
  regra.ids_spec:` → `motivos.INFORMACAO_AUSENTE`), com o validador em
  `core/regras/validacao_ids/validador.py`, e não é exercitado pelo recorte
  ativo nem por nenhum teste.
- `docs/arquitetura/VISAO_GERAL.md` registra o IDS como gancho disponível,
  fora do recorte ativo.
