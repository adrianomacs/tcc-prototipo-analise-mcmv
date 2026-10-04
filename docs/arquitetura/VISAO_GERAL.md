# Visão geral da arquitetura

Este documento descreve **como o protótipo é organizado e por quê**. É o
documento normativo da arquitetura: se ele contradiz o código, um dos dois está
errado e precisa ser corrigido. As decisões individuais que o sustentam estão
em `adr/`, uma por arquivo; aqui estão a estrutura, o vocabulário e as
limitações declaradas.

Conferido contra a árvore real: 109 arquivos `.py` em `core/`
(28 em `dominio/`, 33 em `regras/`, 7 em `aplicacao/`, 39 em `infra/` e, fora
dos anéis, `__init__.py` e `composicao.py`) e 67 em `app/`.

## 1. Duas metades e uma fronteira

O protótipo tem um **núcleo de verificação** (`core/`, Python puro) e uma
**interface de uso** (`app/`, Streamlit). O núcleo não conhece a interface:
a comunicação entre os dois é a pasta `artefatos/`, e apenas ela — relatórios
JSON indexados por GlobalId, `empreendimento.json`, 3D Tiles e GeoJSON
(ADR-001). Nenhum módulo de `core/` importa `streamlit`. A evidência do
desacoplamento é a própria pasta `artefatos/`: tudo o que a interface mostra é
lido dali e regerado a cada execução, e a interface não chama regra sem passar
por ela.

Do lado da interface, a fronteira tem um portão: `app/servicos/` é o único
importador de `core/` dentro de `app/` (ADR-003). `app/paginas/` e
`app/componentes/` importam apenas `app.servicos.*` e entre si — regra
protegida por `tests/arquitetura/test_fronteira_app_core.py`, que reprova a
suíte se um `import core` aparecer nessas pastas.

## 2. Camadas são fluxo; anéis são estrutura

A visão comportamental descreve **quatro camadas**: ingestão de dados →
integração de georreferenciamento → motor de regras → saída de dados. Essa
descrição continua correta, mas diz a ordem em que as coisas acontecem numa
execução. A organização física do código é outra coisa — são **quatro anéis**,
com a dependência apontando para dentro sem exceção, e um módulo de composição
fora deles (ADR-002, ADR-037).

Confundir as duas seria fazer um pacote por camada (ingestão,
georreferenciamento, motor, saída), e pacote nomeado por etapa de fluxo não
diz nada sobre dependência — a entidade `Ambiente` acabaria dentro de um
leitor de IFC, e a porta `Roteador` na mesma pasta dos seus adaptadores.

| Camada (fluxo) | O que roda | Onde mora |
|---|---|---|
| I — Ingestão de dados | abrir o IFC, ler camadas GIS, resolver o território pela porta | `composicao.py` (monta), `infra/ifc/`, `infra/gis/`, `aplicacao/resolver_territorio.py` |
| II — Integração de georreferenciamento | CRS do modelo, LoGeoRef (na ingestão), âncora, medição de distância | `composicao.py`, `infra/ifc/georref/`, `infra/rede/`, `dominio/euclidiana.py`, `dominio/geometria.py`, `dominio/mobilidade.py` |
| III — Motor de regras | ordenação topológica, *guards*, execução isolada por regra, agregação | `aplicacao/pipeline.py:analisar`, `aplicacao/executor.py`, `regras/` |
| IV — Saída de dados | relatório JSON, resumo normativo, GeoJSON, 3D Tiles | `composicao.py` (grava), `infra/exportadores/` |

Quem percorre as quatro é o módulo de composição, `core/composicao.py`, na
borda do núcleo (ADR-037): `rodar` tem, no próprio código, os comentários
`# Camadas I e II` e `# Camada IV`, e o caso de uso que ele chama,
`aplicacao/pipeline.py:analisar`, o `# Camada III`.

## 3. Os anéis de `core/`

**`dominio/` — o anel interno.** Entidades (`Empreendimento`, `Terreno`,
`Equipamento`, `Ambiente`), *value objects* (`Localizacao`, `ModeloBIM`,
`Medicao`), os contratos (`contratos/regra.py` com `Regra`, `Resultado`,
`Estado` e `Contexto`) e as portas que a borda implementa
(`contratos/roteador.py` com o `Roteador`, `contratos/fontes_territoriais.py`
com as `FontesTerritoriais`, `contratos/leitura_modelo.py` com a
`LeituraModelo`), a implementação do `Roteador` que não faz I/O
(`euclidiana.py`, a linha reta que é piso da distância caminhável, ADR-013), o
vocabulário canônico (`vocabulario/declaracoes.py`, `vocabulario/motivos.py`,
`vocabulario/tipos_diagnostico.py`),
o conhecimento de referência (`conhecimento/municipios.py`,
`conhecimento/porte_municipal.py`, `conhecimento/catalogo_ambientes.py`) e o
serviço de domínio `ancora.py` (qual unidade tipo — ou edificação, ou terreno —
e qual contêiner a análise está lendo, ADR-021/ADR-023; responde só a partir
do agregado e do contexto). Critério de admissão, mecânico: não
importar `ifcopenshell`, `ifctester`, `urllib`, `geopandas`, nem
`csv`/`yaml`/`json` para I/O, nem `os.path` para arquivo — `shapely` e `pyproj`
são permitidos, são matemática.

**`aplicacao/` — casos de uso.** `pipeline.py` (o caso de uso da verificação:
recebe o `Contexto` pronto, executa o motor e devolve a análise como dado, sem
I/O), `executor.py` (ordenação topológica, *guards*, isolamento de exceção por
regra), `resolver_territorio.py` (`Localizacao` → território, pela porta
`FontesTerritoriais`), `diagnosticos.py`, `completude.py` e `grupos.py`.

**`regras/` — o especificador normativo.** Uma regra = um arquivo (ADR-005):
`bim/` (8 regras, as `edi_*` do programa de necessidades, das áreas e
larguras), `gis/` (10 regras, as `enq_*` e as `emp_025*`), `gis_bim/` (7
regras, o `emp_001` e a absortância das paredes e do telhado, os pais EDI-019
e EDI-024 com os seus ramos, ADR-026), `base/` (as regras-base que carregam
semântica normativa: `agregacao.py`, `remessa.py`, `distancia_equipamento.py`,
`absortancia.py`),
`validacao_ids/` (o gancho de validação IDS, hoje fora do recorte ativo — ver
ADR-007) e `registro.py` (autodescoberta).

**`infra/` — o anel externo.** Adaptadores de I/O, que importam só o domínio:
`ifc/` (leitor do modelo, unidades, extratores, `leitura_ifc.py` com a
implementação da `LeituraModelo`, subpacote `georref/`), `gis/` (vetorial,
INEP, CSV de equipamentos, municípios e zonas, malhas do IBGE, mapa
interativo, `fontes_csv.py` com a implementação das `FontesTerritoriais`),
`rede/` (ORS e o seu cache, a implementação em rede do `Roteador`),
`persistencia/` (repositórios dos artefatos de estado), `exportadores/`
(relatório, GeoJSON, GLB, 3D Tiles) e `caminhos.py`.

**`composicao.py` — fora dos anéis.** O "Main" do núcleo (ADR-037): monta o
`Contexto` (abre o IFC, lê camadas e CRS, calcula o LoGeoRef e a impressão
digital, resolve o território, recebe o `Roteador` da borda), chama o caso de
uso e grava os artefatos; tem a CLI e as fábricas das portas. É o único
módulo que importa todos os anéis, nenhum anel o importa, e é o ponto de
entrada para executar a verificação, pela interface e pela linha de comando.
A direção de todas essas dependências é verificada por
`tests/arquitetura/test_aneis.py`.

## 4. `app/` — a interface

`servicos/` é o gateway (ADR-003) e concentra também as duas exceções
declaradas ao "serviço não desenha": `conversao_3d.py`, que usa
`st.cache_resource`/`session_state` para o job de conversão em segundo plano, e
`provedores.py`, a borda dos segredos — o único módulo do projeto que lê
`st.secrets` e constrói o `Roteador`. `navegacao/` guarda a árvore do menu
**como dado** (ADR-010): `arvore.py` não importa Streamlit, `main.py` é o único
lugar que cria um `st.Page`, e `sidebar.py` desenha os três níveis com widgets
nativos. `componentes/` desenha, `estado/chaves.py` concentra todo acesso a
`st.session_state`, e `paginas/` se divide em `pesquisa/` (o conteúdo da pesquisa),
`checagens/` e `relatorios/`.

## 5. Vocabulário de domínio

Os termos do DDD tático com o que cada um é no código. Esta tabela é a
referência tanto para o desenvolvimento quanto para a leitura da arquitetura.

| Conceito | Papel | Onde | Invariante / observação |
|---|---|---|---|
| `Empreendimento` | raiz de agregado | `dominio/empreendimento.py` | identidade `id` (uuid4, 12 hex) + `nome` livre; `versao` incrementa a cada mudança; é o que o relatório referencia (ADR-004) |
| `Localizacao` | *value object* | `dominio/empreendimento.py` | código IBGE de 7 dígitos; imutável |
| `ModeloBIM` | *value object* | `dominio/modelo_bim.py` | caminho, `schema` publicado, `digest` (SHA-256 do conteúdo, carimbado pelo pipeline ao abrir — ADR-035), natureza, `unidades_representadas` — o único número que uma regra dimensional consome (ADR-021); anexável ao terreno, à unidade tipo e à edificação (ADR-023) |
| `UnidadeTipo` | entidade | `dominio/unidade_tipo.py` | o grupo de UH que se repete: nome, `unidades`, `tipologia`, `ModeloBIM` opcional (ADR-023) |
| `Edificacao` | entidade | `dominio/edificacao.py` | o prédio físico: nome, `ModeloBIM` opcional, `composicao` em unidades tipo; tipologia e nº de UH derivados pela raiz (ADR-023) |
| `Declaracoes` | *value object* | `dominio/vocabulario/declaracoes.py` | só valores do vocabulário; governa **aplicabilidade**, nunca insumo |
| `Terreno` | entidade | `dominio/terreno.py` | `nivel ∈ {ponto, poligonal}`, precisão, origem, procedência; `atende(nivel)` |
| `Equipamento` | entidade | `dominio/equipamentos.py` | pertence ao **território**, não ao empreendimento; `insumo_suspeito` nunca gera falso não conforme |
| `Ambiente` | entidade | `dominio/edificacao.py` | área e largura já em metros (unidades convertidas na ingestão) |
| `Medicao` | *value object* | `dominio/mobilidade.py` | `limite_inferior` decide o que a medição autoriza concluir |
| `Regra`, `Resultado`, `Estado` | contrato + *template method* | `dominio/contratos/regra.py` | metadado declarativo; `checar(ctx)` é o único método a implementar |
| `Contexto` | contexto de execução | `dominio/contratos/regra.py` | `Empreendimento` + serviços + `resultados` (ADR-004) |
| `Roteador` | porta (`Protocol`) | `dominio/contratos/roteador.py` | duas implementações, a de linha reta no domínio (`dominio/euclidiana.py`, piso do ADR-013) e a de rede em `infra/rede/ors.py`; injetado pela borda (ADR-011) |
| `FontesTerritoriais` | porta (`Protocol`) | `dominio/contratos/fontes_territoriais.py` | recorte de equipamentos, zona, população e malha municipal por código IBGE; implementada em `infra/gis/fontes_csv.py`, injetada pela composição (ADR-011) |
| `LeituraModelo` | porta (`Protocol`) | `dominio/contratos/leitura_modelo.py` | o que as regras leem do modelo; implementada em `infra/ifc/leitura_ifc.py`, injetada em `Contexto.leitura_modelo` (ADR-036) |
| `RegraAgregacao`, `RegraRemetida`, `RamoAbsortancia` | regras-base | `regras/base/` | pai de agregação nunca reprova por ignorância; em `selecao_exclusiva` (ADR-026) discordância entre ramos é indecisão, não reprovação |
| `motivos` | vocabulário canônico | `dominio/vocabulario/motivos.py` | fonte única das causas de `NAO_AVALIAVEL` (ADR-006) |
| repositórios | persistência | `infra/persistencia/` | escrita atômica; `empreendimento.json` absorve `terreno.json` |

**Vocabulário de tela** (ADR-034), para a interface e para as figuras:

| Termo | O que é |
|---|---|
| card do empreendimento | descrição em prosa do empreendimento, num card com ícone de casa, logo abaixo de "O que esta checagem verifica" e na 2.1.1; um padrão, variando só condomínio × loteamento; fala em **unidade tipo**, nunca em tipologia |
| consulta | informação de segundo plano de um relatório (origem das medidas, procedência da base, verificações não realizadas), junto da legenda |
| faixa de avisos | avisos de pré-condição no topo da página, com a mensagem-chave em negrito e a cor pela semântica do ADR-034 (c) |
| informações de entrada / cobertura e análise | as duas únicas seções de uma página de checagem |
| card de verificação | abertura do relatório de um requisito: id, estado, descrição, motivo, o que exige, o que foi medido e o que destrava; o único lugar onde o veredito tem cor |
| frase de contexto | explicação em linguagem do usuário, antes do detalhe técnico, com a referência bibliográfica quando houver |
| card de síntese | o resultado de um conjunto de requisitos (uma checagem, o consolidado): veredito com a cor do estado, contagens em requisitos da Portaria e o porquê |
| relatório descritivo | a 2.4.2: texto montado só das análises gravadas, que amarra cada resultado aos insumos consumidos e não substitui o parecer do analista (ADR-035) |
| pendência por destinatário | o que decide um requisito em aberto ou reprovado, endereçado ao proponente, à análise humana ou à configuração da ferramenta e às bases (ADR-035) |
| impressão digital | o SHA-256 de um arquivo submetido, gravado no relatório; o texto cita o nome, e o SHA fica em "Arquivos analisados" (ADR-035) |

## 6. O que o protótipo produz

Três estados e nada mais: `CONFORME`, `NAO_CONFORME`, `NAO_AVALIAVEL` — este
último sempre com a causa anexada, a partir de uma taxonomia fechada de 17
motivos (ADR-006, ADR-033). O relatório agrupa por causa, o que o transforma de
diagnóstico em lista de pendências acionável, e distingue duas coisas que o
usuário confunde: limitação de dado ou de informação, e não conformidade do
projeto.

## 7. Limitações declaradas

Não são acidentes nem pendências disfarçadas; são o escopo desenhado, e
declarado.

1. **Não há camada anticorrupção completa sobre o IfcOpenShell.** As regras
   BIM leem o modelo pela porta `LeituraModelo` (ADR-036), e o anel `regras/`
   não importa o anel externo; mas a porta devolve o que os leitores já
   devolvem (a triagem, a partição dos revestimentos, os elementos IFC), e a
   regra ainda sabe que um revestimento tem property set. Não se confunda
   com a `Edificacao`: desde o ADR-023 ela **existe**, física e magra (nome,
   `ModeloBIM`, composição em unidades tipo), e não é
   tradutora de nada — o que falta é a tradução do modelo IFC para o domínio,
   não a entidade. A `UnidadeHabitacional` como entidade própria, essa sim,
   segue fora do escopo (ADR-023).
2. **A visualização é de nível 1, com nível 2 só sob seleção** —
   posicionamento geográfico e painel de resultados; o destaque por elemento
   aparece ao clicar na lista do relatório, na cor do resultado, sem
   recolorir o modelo (ADR-009).
3. **O caminho legado de `core/regras/base/distancia_equipamento.py`** — o
   roteador injetado por `ctx.config["roteador_rede"]` (`_roteador_de_rede`) —
   existe só para `Contexto` montado à mão, fora da composição; dívida
   deliberada. O recorte de equipamentos vem só pela porta
   `FontesTerritoriais` (ADR-011), e o `Contexto` não tem mais campos
   retrocompatíveis — ver a docstring de `core/dominio/contratos/regra.py`.
4. **A validação por IDS não faz parte do que roda.** O IDS é requisito de
   informação do contratante, a ser exigido do proponente antes da submissão
   (ADR-007). Existe um gancho no executor, e nenhuma regra declara
   `ids_spec`; portanto nenhuma regra depende de IDS, e cada uma conclui a
   partir do modelo.
5. **Um contêiner que representa UH de mais de uma unidade tipo é avaliado em
   agregado**, e UH conforme pode compensar UH não conforme dentro dele
   (ADR-021). Desde o ADR-023 a situação não é mais silenciosa: quando o
   arquivo é anexado a uma `Edificacao` com composição de dois ou mais tipos,
   o diagnóstico de **heterogeneidade** a marca, na tela e em
   `meta.diagnosticos`. O que a zera é requisito de informação, não código —
   um IFC por unidade tipo. Anexado a um `UnidadeTipo`, um arquivo misto
   continua indetectável pelo motor.

## 8. Onde ler mais

`adr/README.md` (índice das decisões, com o teste que protege cada uma),
`DECISOES_NORMATIVAS.md` (como o protótipo lê a Portaria),
`../figuras/README.md` (as figuras, entre elas a da arquitetura) e
`../README.md` (índice geral da documentação).
