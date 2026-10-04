# ADR-009 — 3D Tiles é o artefato de geometria; a visualização é de nível 1, com nível 2 sob seleção
**Status:** Aceita

## Contexto
Mostrar o modelo IFC no seu contexto geográfico exige geometria em formato que
um globo virtual carregue e posicione. O glTF/GLB resolve a geometria, mas não
o posicionamento no globo nem o carregamento progressivo; e a visualização não
podia virar dependência da análise — converter um IFC leva minutos, e o
Streamlit reexecuta o script a cada interação.

## Decisão
O artefato de geometria é **3D Tiles 1.1** (`tileset.json` + GLB), não glTF
puro: o posicionamento vai num `transform` 4×4 ECEF calculado a partir da
âncora geográfica, e o CesiumJS carrega e posiciona sem conhecer o núcleo.
A produção (lenta: IFC → GLB → tileset + `ancora.json` + `status.json`) é
separada do consumo (rápido: ler disco e montar o payload) e roda em segundo
plano, sem tocar em estado da sessão do Streamlit.
O escopo é o **nível 1** (posicionamento geográfico do modelo mais painel de
resultados) e o **nível 2** (destaque por elemento, indexado por GlobalId) só
sob seleção e sem tocar no modelo, que carrega sempre com as cores dele. Ao
clicar num elemento da lista do relatório, o destaque aparece na cor do
**resultado** que o relatório gravou (verde atende, vermelho não atende,
cinza não avaliado), por volume exato no ambiente (`espacos.json`) e por
caixa envolvente no revestimento (`revestimentos.json`, alinhada aos eixos do
modelo); "destacar todos" mostra o conjunto. A cena não consome o
`tileset.json` como 3D Tiles: carrega o GLB, publicado como arquivo estático
do app, e usa do tileset só a matriz ECEF. Toda checagem converte o modelo
inteiro, com os revestimentos, porque o acabamento está neles; uma conversão
por IFC serve a todas pelo cache.
Conformidade e posicionabilidade são eixos distintos: a visualização **sempre
tenta posicionar** (modo automático preciso via `IfcProjectedCRS`/
`IfcMapConversion`; aproximado via coordenadas do `IfcSite`; manual quando não
há âncora derivável) e nunca é bloqueada por não conformidade normativa.

## Consequências
Fica fácil trocar o visualizador (ADR-001) e exibir modelo com datum
estrangeiro, explicitando a não conformidade sem esconder o modelo. Fica
difícil o gating de tela: o botão do relatório precisa esperar a conversão, o
que exigiu o metadado `usa_visualizacao` por regra. A pasta de tiles e o job
de conversão são namespaced por `chave` de checagem: **globais**, a cena da
última análise vazaria para o relatório de outra checagem.

## Evidência
- `core/infra/exportadores/tiles3d.py` (`transform_ecef`, tileset 3D Tiles 1.1),
  `gltf.py`, `visualizacao.py` (`gerar_artefatos` × `carregar_payload`).
- Âncora: `core/infra/ifc/georref/ancora.py`; consumo: `app/componentes/cena3d.py`,
  `monitor_viz.py`.
- `Regra.usa_visualizacao` (`core/dominio/contratos/regra.py:328`) usado em
  `app/componentes/resultado.py:220`.
- `tests/core/infra/exportadores/test_tiles3d.py`, `test_gltf.py`,
  `test_visualizacao.py`; `tests/core/infra/ifc/georref/test_ancora.py`,
  `test_transformacao_unidade.py`.
