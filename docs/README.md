# docs/ — índice

"O que procuro → onde está." A documentação deste repositório explica a
arquitetura do protótipo e as decisões que a sustentam. Comece pela visão
geral; as decisões individuais estão nos ADRs (sobre o sistema) e nas DNs
(sobre a leitura da Portaria).

## arquitetura/ — "Como o sistema é e por quê?"

- `arquitetura/VISAO_GERAL.md` — a arquitetura: as duas metades (núcleo e
  interface) e a fronteira entre elas, camadas × anéis, os anéis de `core/`,
  `app/` e seu gateway, o vocabulário de domínio e as limitações declaradas.
- `arquitetura/adr/` — registros de decisão **sobre o sistema**, um por
  arquivo, com contexto, decisão, consequências, situação e a seção
  **Evidência** apontando módulo e teste. Índice, estados, relações entre os
  ADRs e modelo em `arquitetura/adr/README.md`. ADR-001 a ADR-011, ADR-036 e
  ADR-037 tratam da arquitetura; ADR-012 a ADR-035 e ADR-038, do domínio, da
  norma e da interface. Os ADR-012, 014, 016, 017 e 025 são remissões às DNs
  em que foram convertidos; o número 019 não tem arquivo (o índice explica).
- `arquitetura/DECISOES_NORMATIVAS.md` — **arquivo único** com as decisões de
  **leitura da Portaria** (DN-01 a DN-09): o que o texto quer dizer quando é
  ambíguo, está defasado ou remete a insumo inexistente, e o que se recusou.

## figuras/ — "Qual é a figura e como regenerá-la?"

- `figuras/README.md` — o que cada figura é, o script que a gera, onde é usada
  e o comando para regenerar (o matplotlib vem do extra `dev`, fora do núcleo).
- `figuras/figura1_fluxo_idealizado.svg` — o fluxo idealizado: três raias de
  atores cortadas pelas duas fases e, abaixo delas, o protótipo com as quatro
  etapas; gerada por `scripts/gerar_figura1.py` e lida pela página "Fluxo
  Idealizado" do protótipo.
- `figuras/figura2_arquitetura.svg` — a visão estrutural em quatro anéis
  concêntricos, adaptada de Martin (2012), com o módulo de composição, a
  camada de serviços e os artefatos fora dos anéis e, à direita, o caminho de
  uma checagem; gerada por `scripts/gerar_figura2.py` e lida pela página
  "Desenvolvimento do protótipo".

Nada em `figuras/` é editado à mão: muda-se o script e regenera-se.

## tcc/ — referências

- `tcc/referencias.yaml` — a lista de referências da pesquisa, no formato
  USP/ESALQ, fonte única da página "Referências" do protótipo; as entradas com
  `validar: true` ainda têm dado a conferir na fonte.

## Regras de convivência

1. O que está em `docs/` é vigente: se um documento contradiz o código, um dos
   dois está errado e precisa ser corrigido.
2. Decisão sobre o sistema vira ADR; decisão sobre como se lê a Portaria vira
   DN. Uma decisão revista não é editada: nasce outra, e a anterior muda de
   estado.
3. Código e testes citam ADR e DN (e os documentos de `docs/arquitetura/`),
   nunca documento de processo.
4. Arquivo novo em `docs/` nasce com linha neste índice.

Duas delas são verificadas por teste:
`tests/arquitetura/test_docs_citados.py` (todo caminho de `docs/` citado em
docstring ou comentário existe) e
`tests/arquitetura/test_caminhos_citados_na_documentacao.py` (documento não
aponta para arquivo que não existe).

## Fora de `docs/`

- `README.md` (raiz) — o que é o protótipo, como instalar e executar.
- `tests/README.md` — como a suíte de testes está organizada.
- `entradas/inep/FONTES.md` e `entradas/abnt/FONTES.md` — de onde vêm as bases
  do INEP e a base das zonas bioclimáticas, e como regerar os derivados.
