# ADR-027 — O acabamento avaliado por absortância é `IfcCovering` classificado; a relação com o hospedeiro nunca é inferida por heurística
**Status:** Aceita

## Contexto
EDI-019 (parede externa) e EDI-024 (cobertura) avaliam a absortância do
acabamento — tipicamente a pintura. O mercado modela essa camada de duas
formas, e os termos importam: **"parede cebola"** é cada camada (alvenaria,
reboco, emboço, pintura) como elemento IFC independente; **"parede
composta"** é a mesma sequência dentro de um único `IfcWall`, via
`IfcMaterialLayerSet`. No Revit, a via oficial da Autodesk para a pintura
chegar ao IFC é a segunda — "acrescente uma camada à estrutura composta" —, e
não há caminho para reclassificar só essa camada como `IfcCovering`: só
modelando a pintura como `IfcWall` próprio (parede cebola) e sobrescrevendo o
tipo de exportação elemento a elemento. O Archicad (26+) tem via nativa
melhor — mapeamento de tipo IFC por componente/*skin* —, mas ainda exige
configuração deliberada. Em nenhum dos dois o modelador comum autoria a mão a
relação `IfcRelCoversBldgElements` — isso pede ferramenta IFC-nativa (ex.
Bonsai/BlenderBIM), fora do que se exige de um proponente típico.

O estudo de caso confirmou o ponto. O `E3_teto.ifc` do Estrela I, exportado
do Revit com as paredes externas e a cobertura reclassificadas como
`IfcCovering`, `Pset_CoveringCommon.IsExternal = True` e
`Análise_PMCMV.AbsortanciaSolar = 0,5` em todos os 125 coverings, tem **zero**
`IfcRelCoversBldgElements`. Resolvido o LADO (parede × cobertura) só pela
relação, os 125 sairiam "não classificados" e EDI-019/EDI-024 ficariam
`informacao_ausente` num modelo que **entregou** o requisito de informação.
Além disso, o Revit grava `ROOFING` no `IfcCoveringType` com `$` na
ocorrência, e pela regra do IFC4 a ocorrência herda o do tipo: lido só na
ocorrência, o `PredefinedType` não acharia o telhado.

## Decisão
EDI-019/024 exigem, como requisito de informação da CAIXA — este ADR estende
o ADR-007 ao caso da absortância —, que o acabamento esteja modelado como
`IfcCovering` explícito, reclassificado pelo modelador (Revit: parâmetro de
exportação do elemento; Archicad 26+: mapeamento por componente). Para
EDI-024, a classificação exigida inclui `PredefinedType = ROOFING` (valor
nativo do `IfcCoveringTypeEnum`, IFC4.3); não há valor equivalente para
pintura de parede, então EDI-019 não exige um `PredefinedType` de pintura, e
o revestimento de parede se declara por `CLADDING` (abaixo). O
protótipo **nunca** infere o hospedeiro por heurística geométrica nem lê a
camada de dentro da estrutura composta como substituto do `IfcCovering` —
não são checagens para "pinçar" elemento, é requisito de informação cumprido
ou não. A ausência da relação `IfcRelCoversBldgElements` não é defeito a
contornar — é o elemento classificado, não a relação, que carrega o
requisito.

**O lado do covering se resolve em duas vias**, nesta ordem: (1) **pelo
hospedeiro**, quando há `IfcRelCoversBldgElements` — inclusive o desempate do
`IfcSlab` e o "não classificado" para hospedeiro de outra classe ou relação
sem hospedeiro (a relação autorada prevalece, mesmo contradizendo o
covering); (2) **pelo próprio covering**, quando não há relação nenhuma:
`PredefinedType = ROOFING` → cobertura, `CLADDING` → parede; qualquer outro
valor (`USERDEFINED`, `CEILING`, `NOTDEFINED`, ausente) → não classificado. O
`PredefinedType` é lido com a herança do tipo. A via (2) não é afrouxamento:
o que se recusa é atribuir lado *por omissão*, e ela atribui lado *por
declaração do proponente*, no atributo que o schema reservou para isso. Um
covering sem `PredefinedType` continua não classificado. O relatório diz, por
covering, por qual via o lado veio (`origem`: `hospedeiro` | `predefinido`), e
a população de cada ramo conta as duas separadamente (`*_pelo_hospedeiro`,
`*_pelo_predefinido`).

## Consequências
Fica fácil ser honesto sobre o que conta como evidência: o que não vem como o
requisito pede é `NAO_AVALIAVEL` com motivo, nunca adivinhado. Fica
documentado, não corrigido em código, que a exigência custa menos no Archicad
26+ que no Revit — achado de mercado, não defeito do protótipo.
Não se pode dizer que a ausência de `IfcCovering` classificado significa "sem
acabamento": significa "informação não entregue" — só a especificação de
requisitos da CAIXA fecha essa distinção (ADR-007). **A propriedade medida é `AbsortanciaSolar`, exigida pelo NOME e em qualquer
property set.** O IFC não tem propriedade padrão de absortância solar para
superfície opaca — nem em IFC4 nem em IFC4.3; a única é
`Pset_DoorWindowGlazingType.SolarAbsorption`, de envidraçamento.
`ThermalTransmittance`, que os `Pset_*Common` de parede, telhado e covering
oferecem, é outra grandeza (fluxo de calor por condução, W/m²K, contra fração
adimensional da radiação absorvida) e corresponde a outro requisito da própria
Portaria (Tab. 2), então não substitui. `Pset_MaterialOptical.SolarReflectanceFront`
permitiria derivar α = 1 − ρ, mas é propriedade do **material** e pede uma
cadeia de autoria ainda menos provável que a reclassificação do acabamento. O
protótipo, portanto, exige uma propriedade **sua**, `AbsortanciaSolar`, e a lê
pelo NOME em qualquer pset (`leitor_modelo.propriedades_do_elemento`, que
achata todos) — deliberadamente, e não por descuido: enquanto a contratante não
publicar a especificação, exigir um nome de pset inventado pelo verificador
rejeitaria modelos por uma convenção que ninguém combinou. Ausente a
propriedade, `informacao_ausente`; nunca conforme por omissão.

**Externalidade da parede.** A pergunta era se
a externalidade viria de propriedade própria do covering ou da leitura do
hospedeiro. Vem do **covering**: exige-se `Pset_CoveringCommon.IsExternal`, que
não é exigência inventada aqui — é propriedade do pset padrão do `IfcCovering`
desde o IFC4, ao lado das que o requisito já lê (o IFC2X3 não a tem, e o
protótipo já exige IFC4, DN-03). Fazer o requisito depender de
`Pset_WallCommon.IsExternal` repetiria na parede a fragilidade que este ADR
nomeou: a relação `IfcRelCoversBldgElements` raramente é autorada. O
hospedeiro entra como **conferência**, não como fonte — havendo relação e
declaração dos dois lados, elas têm de concordar; discordando, o ramo não
desempata, sai `NAO_AVALIAVEL` com `analise_humana_documental`, porque as duas
declarações são do proponente. Sem `IsExternal` no covering, o requisito de
informação não foi entregue: `informacao_ausente`, jamais geometria. Sem
hospedeiro não há conferência, logo não há divergência possível. **O requisito
de informação para a parede** é o `IfcCovering` com `IsExternal`,
`AbsortanciaSolar` e `PredefinedType = CLADDING` (no elemento ou no tipo) —
o valor nativo do `IfcCoveringTypeEnum` para revestimento de parede, no mesmo
espírito do `ROOFING` exigido para a cobertura. Nada de geometria, nada de
nome.

## Evidência
`core/infra/ifc/classificacao_covering.py` — classifica pelo hospedeiro só
quando a relação existe e pelo `PredefinedType` quando não existe
(`predefinido`, `_categoria_pelo_predefinido`, `origem`), e reporta o resto
sem atribuir por padrão
(`tests/core/infra/ifc/test_classificacao_covering.py`: órfão por
`PredefinedType`, herança do tipo, hospedeiro prevalece);
`core/regras/base/absortancia.py::populacao_cobertura` — aplica
as DUAS condições (hospedeiro de cobertura E `PredefinedType = ROOFING`) e
nomeia no diagnóstico o que ficou de fora; população vazia sai
`informacao_ausente`
(`tests/core/regras/base/test_absortancia.py::test_populacao_exige_hospedeiro_de_cobertura_e_roofing`).
`core/regras/base/absortancia.py::populacao_parede` —
hospedeiro `IfcWall` E `Pset_CoveringCommon.IsExternal`, com a conferência
contra o hospedeiro e o bloqueio por divergência
(`tests/core/regras/base/test_absortancia.py` §5, e a população de cobertura e
de parede pelas duas vias).
Nos dois IFC do Estrela I sem acabamento reclassificado não há covering de
cobertura classificado (só rodapés `SKIRTINGBOARD` e forro `CEILING`,
órfãos): EDI-024 sai `informacao_ausente`, como este ADR prevê. No E3 as
paredes externas inteiras foram exportadas como `IfcCovering` (não uma camada
de pintura), porque o Revit não produz um covering separado da parede sem
remodelar; o protótipo avalia o que foi declarado. A cobertura do E3
("Vidraça inclinada", sistema de painéis) saiu **sem material associado**, e
a etapa 2 do ramo (exceções da Portaria por material, DN-01) a devolve
`material_nao_identificavel` — comportamento previsto, não defeito: o modelo
precisa nomear o material da cobertura. E com `AbsortanciaSolar = 0,5` o
EDI-024 é **indecidível** pela DN-08 (0,4 < α ≤ 0,6 separa os dois ramos que
a norma de 2005 numerava). A ausência de absortância solar no schema foi
conferida por varredura dos *property set templates* de IFC4 e IFC4.3.
ADR-007 é o precedente que este ADR estende.

## Fontes
Exportação de camadas de parede pelo Revit (artigo da Autodesk sobre pintura
não exportada por padrão; Autodesk/revit-ifc#155, sobre a impossibilidade de
forçar uma parede a exportar como `IfcCoveringType`) e pelo Archicad (Ajuda
do Archicad 26/27, mapeamento de tipo IFC por componente).
