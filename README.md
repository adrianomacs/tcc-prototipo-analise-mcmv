# Protótipo de verificação automatizada de requisitos do PMCMV (BIM + GIS)

Prova de conceito que verifica automaticamente parte dos requisitos da
Portaria MCID nº 725/2023 (versão compilada), do Programa Minha Casa, Minha
Vida, integrando modelos BIM no formato aberto IFC e dados geográficos
públicos. O protótipo lê o modelo da edificação e a poligonal do terreno,
consulta as bases do IBGE, do Censo Escolar do INEP e da ABNT, mede a
distância caminhável até as escolas e devolve, para cada requisito, um de
três estados (conforme, não conforme ou não avaliável), sempre com a causa
quando não consegue decidir, para que a falta de informação não se confunda
com não conformidade do projeto.

É o produto técnico do Trabalho de Conclusão de Curso *Integração BIM-GIS
para verificação automatizada de requisitos do PMCMV: arquitetura e prova de
conceito*, do MBA em Engenharia de Software da USP/ESALQ, de Adriano Macedo
Silva, com orientação do Dr. Jorge Carlos Valverde Rebaza.

O vídeo de demonstração está em <https://youtu.be/3q4NTbhkwno>.

## Licença e modelos do estudo de caso

O código é distribuído sob a licença MIT (arquivo `LICENSE`).

Os modelos IFC do estudo de caso, em `entradas/ifc/estrela_i/`, foram cedidos
pela TELESIL para esta pesquisa e são publicados com a sua autorização. As
variantes foram reexportadas pelo autor a partir do material cedido, sem criar
nem excluir elementos, e o `V3_gleba.ifc`, modelo da gleba, foi elaborado pelo
autor. A licença MIT cobre o código e não se estende aos modelos, que estão
aqui para permitir refazer as análises do trabalho.

## Como instalar e rodar

O repositório tem cerca de 360 MB, quase todos dos onze modelos IFC. O
protótipo foi testado com Python 3.12 e 3.14, e a instalação recomendada usa o
[uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/adrianomacs/tcc-prototipo-analise-mcmv.git
cd tcc-prototipo-analise-mcmv
uv venv
source .venv/bin/activate          # no Windows: .venv\Scripts\activate
uv pip install -e ".[dev]" "ifcopenshell==0.8.5" "ifctester==0.8.5" "streamlit==1.64.0"
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # no Windows: copy
streamlit run app/main.py
```

As três versões fixadas no comando de instalação são as do ambiente em que
os resultados do trabalho foram produzidos. Com versões posteriores dessas
bibliotecas, parte da interface e a conversão para a visualização 3D deixam
de funcionar, e a suíte de testes acusa isso. Sem o uv, o mesmo vale com
`python -m venv .venv` e `pip install`.

O `secrets.toml` precisa existir mesmo que você não tenha a chave do serviço
de cálculo da distância caminhável. Basta copiá-lo do `.example`, com a chave
em branco, porque a tela do Enquadramento lê esse arquivo ao abrir.

A interface abre no navegador. Para rodar a análise sem interface, informe
sempre o modelo, porque a pasta `entradas/ifc/` não traz modelo solto para a
descoberta automática.

```bash
python -m core.composicao --ifc entradas/ifc/estrela_i/E0_asis.ifc
```

A verificação do município consulta a malha territorial do IBGE pela
internet, e por isso a primeira análise de cada município precisa de conexão.

## A chave do serviço de cálculo da distância caminhável

As regras de proximidade de escolas medem o caminho a pé pela rede viária com
o [OpenRouteService](https://openrouteservice.org), um serviço gratuito que
exige uma chave pessoal. Para obtê-la, crie uma conta em
<https://openrouteservice.org/dev/#/signup>, confirme o e-mail recebido e, já
conectado, peça um token no painel do serviço (o plano gratuito basta). A
chave vai no `.streamlit/secrets.toml`, na linha `ors_api_key` da seção
`[roteamento]`, ou na variável de ambiente `ORS_API_KEY`. O arquivo
`secrets.toml` está no `.gitignore` e não deve ser publicado.

Sem a chave nada quebra. O protótipo segue com a distância em linha reta e
declara isso, de modo que uma escola que já fica longe demais em linha reta
reprova o requisito, e as demais regras de distância saem como não avaliáveis
por métrica insuficiente, em vez de um resultado inventado.

## Reproduzir os resultados do TCC

### O empreendimento do caso base

Os cenários rodam sobre as declarações do Residencial Estrela I (localização em
Estrela/RS, condomínio, 300 unidades previstas de um apartamento T+1, em duas
edificações de 4 e 296 unidades, e o terreno pela poligonal do memorial
descritivo). Elas estão em `entradas/estrela_i_empreendimento.json`, que deve
ser copiado para a pasta `artefatos/` com o nome `empreendimento.json` antes de
qualquer cenário.

```bash
cp entradas/estrela_i_empreendimento.json artefatos/empreendimento.json   # no Windows: copy
```

Sem essa cópia, `scripts/rodar_cenario.py` para com a mensagem de que o
`empreendimento.json` não existe, e os testes de integração da escada de
cenários pulam com esse motivo. A mesma cópia carrega o caso base na
interface, na página Informações Gerais.

### Os comandos

```bash
python scripts/rodar_cenario.py --listar     # os cenários e os arquivos de cada um
python scripts/rodar_cenario.py E0 --ors     # um cenário, com o serviço de distância
python scripts/gerar_tabelas_cenarios.py     # as tabelas, a partir dos cenários já rodados
pytest -m integracao                         # testes de integração, inclusive a escada contra os gabaritos
```

Para a rodada completa do trabalho, rode `rodar_cenario.py <id> --ors` para
E0, E1, E2, E3, D1, D2, D3, D4, V1, V2, V3, V4 e V5, e depois o script das
tabelas. Cada cenário grava os cinco relatórios e o perfil dos 14 requisitos na
pasta `artefatos/cenarios/<id>/`, e imprime ao final a capacidade de conclusão
(requisitos decididos sobre 14) e a conformidade (conformes sobre decididos).
No ambiente em que o clone limpo foi conferido, cada cenário levou de 4 a 25 segundos.

### O cache do serviço de distância

`artefatos/cache_roteamento/ors.json` é o cache das distâncias caminháveis
medidas na rodada oficial dos cenários. O protótipo consulta esse cache antes
de chamar o serviço, então, com a chave configurada, as distâncias de Estrela
saem idênticas às do trabalho, sem gastar cota e sem depender do
OpenStreetMap do dia. Isso foi conferido num clone limpo, em que os treze
cenários reproduziram a rodada oficial requisito a requisito, sem nenhuma
chamada ao serviço.

O cache não cobre outros terrenos nem outros municípios. Para eles, as
distâncias são calculadas na hora, sobre o OpenStreetMap daquele dia, e podem
mudar com o tempo. Sem a chave, o cache não é usado, e os detalhes de distância
em rede deixam de aparecer, o que é justamente o que o cenário D4 isola. No
nível dos 14 requisitos, porém, a capacidade de conclusão e a conformidade não
mudam, porque a escola de educação infantil já reprova pela linha reta e os
dois requisitos que agregam as alternativas de acesso continuam não
avaliáveis.

### Os cenários do texto

A Tabela 3 do texto descreve os doze cenários com arquivo próprio. A lista que
o código lê é `config/cenarios_estrela_i.yaml`, que traz para cada cenário a
família e o cenário de que ele parte.

| cenário (origem) | o que altera |
|---|---|
| E0 (—) | nada, é o modelo da unidade tipo como entregue e o terreno pela poligonal do projeto de implantação |
| E1 (E0) | modelo reexportado com o sistema de coordenadas projetado e a conversão de mapa que posiciona o bloco na gleba |
| E2 (E1) | ambientes do próprio projeto exportados, com nome e área |
| E3 (E2) | paredes externas e cobertura exportadas como revestimentos classificados, com a absortância solar informada pelo autor (0,35 e 0,65), por o projeto não a especificar |
| D1 (E3) | o mesmo estado exportado no esquema IFC2X3 |
| D2 (E1) | georreferenciamento completo, mas apontando para a localização herdada do material entregue, em outro município |
| D3 (E2) | ambientes renomeados em inglês |
| V1 (E2) | ambientes renomeados com sinônimos usuais, como dormitório, WC e lavanderia |
| V2 (E3) | unidades do projeto em pés e hectares |
| V3 (E0) | terreno descrito por um modelo IFC da gleba, elaborado pelo autor |
| V4 (E3) | exportação com todos os conjuntos de propriedades e quantidades disponíveis |
| V5 (E0) | poligonal restrita à porção do Estrela I, extrapolada da prancha de implantação |

A lista tem ainda quatro cenários que não estão no texto. O D4 roda o E3 sem o
serviço de distância, com o mesmo arquivo, e é o único dos quatro que o
comando executa. O D5 (terreno informado por um ponto no mapa), o DD1
(unidades tipo declaradas cuja soma passa das 300 previstas) e o DD2 (modelo
anexado a uma edificação com dois tipos de unidade) só se produzem na
interface, e o comando os recusa.

### O que corresponde a cada tabela do texto

A Tabela 3 do texto é a descrição dos cenários acima e não sai de nenhum
script.

A Tabela 4 do texto traz, para os enriquecimentos e as degradações, a mudança
observada em relação ao cenário de origem, a capacidade de conclusão e a
conformidade. Os números de cada linha são os que `rodar_cenario.py` imprime
ao fim de cada cenário. O script das tabelas grava na pasta
`artefatos/cenarios/tabelas/`, em Markdown e em CSV, e os nomes dos arquivos
não coincidem com a numeração do texto. O arquivo `tabela_3` é o perfil por
requisito de E0 a E3, com a capacidade de conclusão e a conformidade de cada
degrau, e corresponde às quatro primeiras linhas da Tabela 4 do texto. O
arquivo `tabela_4` traz as degradações D1 a D4, mas sempre comparadas ao E3, e
não ao cenário de origem, de modo que as mudanças do D2 e do D3 que o texto
relata se leem contra o perfil do E1 e do E2. O arquivo `tabela_5` traz as
variações V1 a V5 e se o veredito se manteve em cada uma, o que o texto
apresenta logo depois da Tabela 4. O arquivo `figura_4` traz os dados do
gráfico de conclusão por degrau.

### Os arquivos de entrada e o SHA-256

A rodada oficial registrou o SHA-256 de cada arquivo de entrada nos relatórios
(campo `meta.arquivos`), e os valores abaixo são os dela. Em Linux, macOS ou
WSL, salve a lista num arquivo e confira com `sha256sum -c`, a partir da raiz
do repositório. No PowerShell, `Get-FileHash <arquivo>` mostra o valor de cada
um.

| arquivo | tamanho | SHA-256 |
|---|---:|---|
| `entradas/ifc/estrela_i/E0_asis.ifc` | 11,9 MB | `bf7e330802aa6940a4ca227d6f6e60ba1c086fcbd019d186773243aa2011b50f` |
| `entradas/ifc/estrela_i/E1_georref.ifc` | 11,9 MB | `3c3a5f67b65d08eb4e42a5dc37c41073233e97bebbc9a503bf58c6b39f92da4b` |
| `entradas/ifc/estrela_i/E2_ambientes.ifc` | 12,4 MB | `a7a73c3ae50a36cac6b3ab3e4d367ae6c986deccb8d625fdf54dd1915536c614` |
| `entradas/ifc/estrela_i/E3_teto.ifc` | 68,2 MB | `d8204053d5b6de93848e7302e73cb992ec6ae4a4c7fadeb619893c7a451c2197` |
| `entradas/ifc/estrela_i/D1_ifc2x3.ifc` | 80,4 MB | `6d17cd694c762d435fef13a193e7b7aeaad2aad410134a0190a016d3cae56458` |
| `entradas/ifc/estrela_i/D2_maceio.ifc` | 11,9 MB | `11641f331152e3dadec5c7fc9e0f8a1ca6c009054ffa71938027c06ead09ae40` |
| `entradas/ifc/estrela_i/D3_ingles.ifc` | 12,4 MB | `8a73bb282a8f07059b1a381f4fc1d76990abf51563bf972480ed6769e3d3bf11` |
| `entradas/ifc/estrela_i/V1_sinonimos.ifc` | 12,4 MB | `ccb03afb3df7a70adc77afaf2b855e0f8f3498738d5fb2b4246ba0c379895840` |
| `entradas/ifc/estrela_i/V2_pes.ifc` | 68,3 MB | `61d74723a18c0efc8840f5d7cda86b963fbf16f5a401d9de5b79bea27b20d76a` |
| `entradas/ifc/estrela_i/V3_gleba.ifc` | 7,1 MB | `f666afd4316ccf2a8c5b372150605b3c21265e8eee952492697f264c1f2ae6b4` |
| `entradas/ifc/estrela_i/V4_psets.ifc` | 70,5 MB | `8fd9277ba62db41dd58dbd2ef43036eb7303a16c02c4bc66bb793b831e183f52` |
| `entradas/gis/estrela_i/E0_memorial.csv` | 372 bytes | `329a9d4a0d564acd792d9f3432a0420debd1d551bac5f1c5574026c23cea94d8` |
| `entradas/gis/estrela_i/V5_modulo_i.csv` | 277 bytes | `c85f0fc31b8f42c45e6767722ec085c030a690efa3e909019b33b5febec204f2` |

```
329a9d4a0d564acd792d9f3432a0420debd1d551bac5f1c5574026c23cea94d8  entradas/gis/estrela_i/E0_memorial.csv
c85f0fc31b8f42c45e6767722ec085c030a690efa3e909019b33b5febec204f2  entradas/gis/estrela_i/V5_modulo_i.csv
6d17cd694c762d435fef13a193e7b7aeaad2aad410134a0190a016d3cae56458  entradas/ifc/estrela_i/D1_ifc2x3.ifc
11641f331152e3dadec5c7fc9e0f8a1ca6c009054ffa71938027c06ead09ae40  entradas/ifc/estrela_i/D2_maceio.ifc
8a73bb282a8f07059b1a381f4fc1d76990abf51563bf972480ed6769e3d3bf11  entradas/ifc/estrela_i/D3_ingles.ifc
bf7e330802aa6940a4ca227d6f6e60ba1c086fcbd019d186773243aa2011b50f  entradas/ifc/estrela_i/E0_asis.ifc
3c3a5f67b65d08eb4e42a5dc37c41073233e97bebbc9a503bf58c6b39f92da4b  entradas/ifc/estrela_i/E1_georref.ifc
a7a73c3ae50a36cac6b3ab3e4d367ae6c986deccb8d625fdf54dd1915536c614  entradas/ifc/estrela_i/E2_ambientes.ifc
d8204053d5b6de93848e7302e73cb992ec6ae4a4c7fadeb619893c7a451c2197  entradas/ifc/estrela_i/E3_teto.ifc
ccb03afb3df7a70adc77afaf2b855e0f8f3498738d5fb2b4246ba0c379895840  entradas/ifc/estrela_i/V1_sinonimos.ifc
61d74723a18c0efc8840f5d7cda86b963fbf16f5a401d9de5b79bea27b20d76a  entradas/ifc/estrela_i/V2_pes.ifc
f666afd4316ccf2a8c5b372150605b3c21265e8eee952492697f264c1f2ae6b4  entradas/ifc/estrela_i/V3_gleba.ifc
8fd9277ba62db41dd58dbd2ef43036eb7303a16c02c4bc66bb793b831e183f52  entradas/ifc/estrela_i/V4_psets.ifc
```

O `.gitattributes` marca esses arquivos para que o git não converta as quebras
de linha, e por isso o SHA-256 confere em qualquer sistema operacional.

### A visualização 3D do E3

A interface mostra o modelo em 3D com a cor do resultado de cada elemento. A
conversão do IFC para essa visualização roda em segundo plano, sem bloquear a
análise, e no E3 (68 MB) leva cerca de 30 minutos na primeira vez. Depois ela
fica guardada e abre na hora.

## Testar fora de Estrela/RS

A pasta `config/` traz o recorte de equipamentos de educação de Estrela/RS
(4307807) e das 27 capitais, cada um num par `equipamentos_<código IBGE>.csv` e
`.json`, este com a procedência (safra do Censo Escolar, data da geração e
SHA-256 das fontes). São eles Porto Velho (1100205), Rio Branco (1200401),
Manaus (1302603), Boa Vista (1400100), Belém (1501402), Macapá (1600303),
Palmas (1721000), São Luís (2111300), Teresina (2211001), Fortaleza (2304400),
Natal (2408102), João Pessoa (2507507), Recife (2611606), Maceió (2704302),
Aracaju (2800308), Salvador (2927408), Belo Horizonte (3106200), Vitória
(3205309), Rio de Janeiro (3304557), São Paulo (3550308), Curitiba (4106902),
Florianópolis (4205407), Porto Alegre (4314902), Campo Grande (5002704), Cuiabá
(5103403), Goiânia (5208707) e Brasília (5300108). A população do Censo 2022 e
a zona bioclimática já cobrem todos os municípios do país.

Para outro município, é preciso gerar o recorte a partir das três bases
nacionais do INEP, que não estão no repositório. O `entradas/inep/FONTES.md`
diz onde baixar cada uma (os microdados do Censo Escolar, com as tabelas de
escolas e de turmas, e o export completo do Catálogo de Escolas, sem filtros).
Coloque os três arquivos em `entradas/inep/` e rode

```bash
python scripts/gerar_equipamentos.py --procurar "nome do município" --uf RS
python scripts/gerar_equipamentos.py --municipio <código IBGE>
```

O primeiro comando descobre o código IBGE pelo nome, e o segundo grava o par
`.csv` e `.json` em `config/`. Depois, declare o empreendimento na página
Informações Gerais da interface e informe o terreno no Enquadramento.

## Testes

```bash
pytest                                       # a suíte inteira
pytest -m "not integracao and not interface" # o ciclo rápido
```

A suíte coleta 1.521 testes. Os de integração da escada de cenários pulam com
o motivo quando falta o `empreendimento.json` na pasta `artefatos/`, e um teste
que lê um arquivo de uma rodada anterior, fora do repositório, pula sempre.
O `tests/README.md` explica a organização e os marcadores.

## Estrutura de pastas

```
core/        núcleo de verificação, em anéis (dominio, aplicacao, regras, infra)
app/         interface Streamlit, em que as páginas usam o núcleo só pelos serviços
config/      recorte de requisitos, regras ativas, cenários, municípios, zonas e equipamentos
entradas/    modelos IFC e poligonais do estudo de caso, empreendimento de exemplo e fontes
scripts/     cenários, tabelas, figuras e geradores das bases de referência
tests/       suíte de testes, espelhando core/ e app/
docs/        arquitetura, decisões registradas (ADR e DN) e figuras
artefatos/   saída do protótipo, regerada a cada análise (só o cache e as pastas vão no git)
```

A documentação começa por `docs/README.md`. A arquitetura está em
`docs/arquitetura/VISAO_GERAL.md`, as decisões de arquitetura no índice
`docs/arquitetura/adr/README.md` e a leitura da Portaria em
`docs/arquitetura/DECISOES_NORMATIVAS.md`. A base completa de requisitos
classificados da Portaria, com o método da decomposição, está em
`config/Base_Requisitos_Portaria_MCID_725.xlsx`.

## Como citar

Silva, A.M. 2026. Integração BIM-GIS para verificação automatizada de
requisitos do PMCMV: arquitetura e prova de conceito. Trabalho de Conclusão de
Curso (MBA em Engenharia de Software). Universidade de São Paulo, Escola
Superior de Agricultura "Luiz de Queiroz", Piracicaba, SP, Brasil.

Silva, A.M. 2026. Protótipo de verificação automatizada de requisitos do PMCMV
(BIM + GIS). Disponível em:
<https://github.com/adrianomacs/tcc-prototipo-analise-mcmv>.

Para falar com o autor, escreva para adrianomacs@gmail.com.
