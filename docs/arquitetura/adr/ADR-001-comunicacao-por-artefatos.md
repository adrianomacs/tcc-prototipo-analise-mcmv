# ADR-001 — Núcleo e interface comunicam-se apenas por artefatos em formatos abertos
**Status:** Aceita

## Contexto
Duas metades de naturezas distintas: um núcleo de verificação em Python
(IfcOpenShell, GeoPandas, pyproj) e uma interface que exibe mapas e cena 3D em
navegador (Streamlit, Leaflet, CesiumJS). O Streamlit reexecuta o script a cada
interação e uma conversão de geometria leva minutos — chamar o motor de dentro
do renderizador acoplaria a lógica normativa ao ciclo de vida de um framework
visual e tornaria cada clique um reprocessamento.

## Decisão
O núcleo não conhece a interface: a comunicação entre os dois é a pasta
`artefatos/`, e apenas ela — `relatorio.json` / `relatorios/<chave>.json`
(com índice `GlobalId → estados`), `empreendimento.json`, `terreno.json`,
3D Tiles e GeoJSON. Nenhum módulo de `core/` importa `streamlit`. Artefato de
estado é gravado atomicamente (temporário + `os.replace`), para que leitura
concorrente nunca veja JSON parcial.

## Consequências
Fica fácil trocar ou acrescentar interface sem tocar no núcleo, reabrir
análise sem reprocessar, e testar o núcleo sem UI e sem rede. Fica difícil o
estado da sessão do Streamlit, que passa pelo disco e exige escrita atômica e política de
invalidação (ADR-004). Não se pode fazer o núcleo ler `st.secrets` ou
`session_state`, nem a interface chamar regra sem passar pelo artefato.
Corolário: artefato é saída regerável, logo não versionado; o que tiver de
servir de evidência do estudo de caso é copiado para fora de `artefatos/`.

## Evidência
- `core/__init__.py`; `grep -rn "streamlit" core/` só acha prosa de docstring.
- `core/infra/exportadores/{relatorio_json,geojson,gltf,tiles3d,visualizacao}.py`.
- Escrita atômica: `core/infra/persistencia/{artefato,empreendimento_json}.py`.
- A pasta `artefatos/` é o único ponto de contato: arquivo `relatorio.json`,
  subpastas `relatorios/` e `tiles/`, todos regerados a cada execução.
- `tests/arquitetura/test_fronteira_app_core.py`: só `app/servicos` importa
  o núcleo; páginas e componentes leem o que ele gravou.
- `tests/core/infra/exportadores/` (`test_relatorio_json.py`, `test_tiles3d.py`,
  `test_gltf.py`, `test_visualizacao.py`),
  `tests/core/infra/persistencia/test_empreendimento_json.py`,
  `tests/core/aplicacao/test_pipeline_destino_rel.py`.

## Arquivos submetidos no relatório
O relatório de cada checagem passa a registrar os arquivos submetidos que a
análise recebeu, com o SHA-256 calculado por quem os consumiu
(`meta.arquivos`) — é o que permite ao Relatório de Checagem amarrar cada
resultado ao insumo sem reler a sessão do Streamlit. Decisão e motivo no ADR-035.

## Pasta de visualização de cada checagem
Inventário da pasta `artefatos/`, subpasta `tiles/<chave>/`:
`modelo.glb` (um nó por elemento, nomeado pelo `GlobalId`), `tileset.json`
(a matriz ECEF), `ancora.json`, `espacos.json` (centro, raio e malha de cada
`IfcSpace`), `revestimentos.json` (caixa mín./máx. de cada `IfcCovering`,
lida do próprio GLB) e `status.json`, gravado por último. Regra: **artefato
de visualização traz geometria para exibir, nunca julgamento**; a cor do
destaque vem do `detalhe` do relatório, e o relatório não ganha campo para
servir à tela. A página publica o GLB na pasta estática do Streamlit
(`app/static/modelos/`, criada na execução) para a cena carregá-lo por
endereço.

