# ADR-034 — Página de checagem e página de relatório seguem uma anatomia única
**Status:** Aceita

## Contexto
Cada checagem e cada relatório tinha sido desenhado isoladamente: seções
numeradas diferentes, avisos espalhados entre topo, formulário e ação, mapa
e cena em meia largura (esmagados em notebook), jargão IFC/GIS exposto de
chofre e o empreendimento resumido em "· · ·". O Enquadramento (GIS) e o
banner de veredito do relatório das ENQ já eram o padrão desejado.

## Decisão
**Checagem** (toda página que roda regras), de cima para baixo: título ·
expander recolhido "O que esta checagem verifica" · **card do
empreendimento** · **faixa de avisos** · **Informações de entrada** ·
**Cobertura e análise** (títulos sem número), sem linha divisória entre os blocos do topo. Na 1.ª,
todo insumo, o upload do IFC é campo dela, sem item próprio; o que vem da
2.1.1 aparece em campo **não editável** com link. Na 2.ª, as métricas de
cobertura ("Requisitos do grupo" × "Avaliáveis", em requisitos da Portaria —
alternativa de agregação não conta à parte, como no relatório), com a legenda "Fora desta análise: …" (rótulo e, se for o caso,
a tipologia) quando nem todas entram e, **numa linha só**, o que será executado ao lado do botão
(**Analisar** em toda página, depois Nova análise) — "Ao analisar, o
protótipo verifica: …" pelos rótulos dos requisitos, sem ids, com a nota curta abaixo; então o resultado
com acesso ao relatório de cada requisito e as particularidades da regra.
**Relatório**: voltar e "O que esta regra verifica" **na mesma linha** ·
avisos · **card de verificação** (id, estado, descrição, motivo, Exige/Medido, o que destrava)
· frase de contexto · detalhe do resultado · mapa ou cena · legenda e,
junto dela, a **consulta** (informação de segundo plano: origem das medidas,
procedência da base, verificações não realizadas) · tabela longa ·
uma linha e o título **"Outras informações"**, e só abaixo dela os expanders
técnicos e o JSON, por último. Abre **na mesma aba**, voltar e menu
sempre disponíveis. **Um relatório por requisito, sem exceção de grupo**:
não há relatório consolidado; a cena de um relatório carrega só
os elementos que aquela regra julgou (o `ambientes` do `detalhe`), e a base
comum de um grupo (no Programa, os ambientes deixados de fora do ADR-031 e
os atributos IFC) se repete em "Outras informações" de cada relatório.

**Toda página da seção "Checagens do Protótipo"** (Informações Gerais,
Requisitos a serem validados, as checagens e os resultados 2.4.x) e todo
relatório seguem este ADR: **largura total** da janela e, sob o título, o
expander "O que esta página mostra" (ou "faz", numa página de declaração) —
página nova da seção nasce assim. As páginas de pesquisa também ocupam a
largura total: toda a aplicação se adapta à janela, sem largura de
leitura, pela uniformidade e para poupar rolagem; a anatomia (expander,
card, seções) segue valendo só para a seção
de checagens e para os relatórios.
(a) **Empilhado** em todo relatório (mapa e cena 3D), largura total; a
definição do terreno segue lado a lado. (b) **520 px** para mapa e cena de
relatório; tabela longa ≈300 px ou expander; o mapa de edição mantém 460.
(c) Veredito **só** no card, pelas cores de estado; `error` = não dá para
seguir; `warning` = segue, com resultado limitado ou dado incoerente;
`info` = orientação e estado vazio; `success` = ação do usuário concluída.
Mensagem: 1.ª frase em negrito (o quê), consequência, o que fazer —
curta e direta. **Texto de tela é para o fluxo de uso**: não cita ADR,
caminho de arquivo, comando nem a razão de desenvolvimento de um campo (isso
mora na docstring); campo derivado aparece no mesmo formato dos vizinhos,
não editável. Sempre
visível: card, avisos, contexto, métricas, mapa/cena, tabela por requisito.
Em expander: entidades IFC, GlobalId, EPSG, níveis, procedência, mecânica da
decisão, lista > ~10 linhas; abre sozinho quando contém problema. Aviso de
**pré-condição** vai à faixa; aviso que **nasce do insumo enviado** fica
junto do campo. Vários avisos técnicos do mesmo insumo viram **um** aviso em
linguagem do usuário (o que fazer), com os textos técnicos num expander
abaixo. (d) **Card do empreendimento**: a frase num card destacado, com
ícone de casa e fundo no azul-petróleo da identidade (nenhuma cor de aviso
nem de estado), logo abaixo de "O que esta checagem verifica", em toda
checagem, e também na 2.1.1 (sem o link), para o proponente ver o que está
declarando. Frase única, variando só condomínio × loteamento: "O
empreendimento analisado, o {nome}, está situado em {município}/{UF} e é um
condomínio de {apartamentos} que totaliza {N} UHs, dividido nas edificações
{A} ({n} UHs) e {B} ({n} UHs), com a unidade tipo {X}" — loteamento: "é um
loteamento de {N} UHs em {casas}, com a unidade tipo {X}", sem edificações.
Omite o não declarado; até três edificações pelo nome, depois "dividido em
{n} edificações ({primeira} a {última})". O que se repete é **unidade tipo**,
nunca "tipologia" (no domínio, casa × apartamento). UHs declaradas ×
previstas segue aviso à parte, logo sob o card: declarar **a mais** é
contradição (ADR-022) e sai `warning`; declarar **a menos** não contradiz,
só limita o alcance dos resultados, e sai `info`, sem motivo nem veredito.
(e) Termo técnico ganha frase de contexto na 1.ª aparição,
com referência **da lista de referências da pesquisa**
(`docs/tcc/referencias.yaml`), nunca inventada: LoGeoRef
(Clemen; Görne, 2019), georreferenciamento no IFC4 (buildingSMART
Australasia, 2020; Jaud et al., 2022), EPSG e IfcSite (Clemen; Görne,
2019), requisito de informação (ABNT NBR ISO 19650; ISO 7817-1), regra
remetida (Preidel; Borrmann, 2018; Fernandes et al., 2018), 3D Tiles (Chen
et al., 2018). Sem fonte no texto: frase sem citação (rede × linha reta,
zona bioclimática, porte, IfcSpace/IfcCovering). A tela **não fala de IDS**
(ADR-007): falta de informação se diz ausente e a conferir no modelo autoral.

| Tela | Como a anatomia se aplica |
|---|---|
| 2.1.1 Informações Gerais | uma seção só, "Identificação do empreendimento"; card no topo, sem link; avisos à faixa; números que não fecham em caixa de alerta sob o card; largura total; "O que esta página faz" |
| Requisitos a serem validados | roteiro por checagem, na ordem do menu, com a situação de cada requisito no empreendimento declarado; card e faixa de avisos |
| Enquadramento | seções; card; faixa; linha de execução; avisos do IFC consolidados; frase de contexto sobre LoGeoRef no texto do modo IFC |
| Qualificação Urbanística | seção 1 não editável; cobertura e linha de execução; sem painel do porte, que repetiria o relatório do EMP-025 |
| Georreferenciamento | seções fundidas; cobertura e linha de execução; posicionamento aproximado na seção 2 |
| Programa de necessidades | seções fundidas; avisos à faixa; cobertura e linha de execução |
| Validações BIM + GIS | seções fundidas; aviso à faixa; frase de contexto; sem painel da decisão territorial, que repetiria o relatório da absortância |
| 2.4.1 Cobertura do Protótipo | largura total; "O que esta página mostra"; consolidado parcial à faixa; análise por checagem; tabela e limites sob "Outras informações" |
| 2.4.2 Relatório de Checagem | relatório descritivo (ADR-035): card de síntese e o texto, sem card do empreendimento; card de síntese no "Resultado final" comum e métricas com legenda única, em requisitos; seções em subtítulo com filete, requisitos de cada checagem, pendências e arquivos em tabela |
| Rel. EMP-001 | empilhado a 520 px; card; aviso do ADR-032 à faixa; frase de contexto; níveis e procedência em expander |
| Rel. ENQ-009/010.1/011.1 e pais ENQ-010/011 | empilhado a 520 px; padrão de relatório; consulta junto da legenda |
| Rel. EMP-025 | card; frase de contexto; relatório próprio |
| Rel. absortância (EDI-019/024 e ramos) | card; frase de contexto; cena dos `IfcCovering` (520 px, empilhada), com a caixa na cor do resultado sob seleção (ADR-009) |
| Rel. por regra do Programa (EDI-004/004.1/001/002/007/008/009/011) | sem relatório consolidado; card de cada regra com Exige/Medido; aviso "Por que este aviso" com normalização e diagnósticos só nas regras que usam UHs; cena só com os ambientes da regra (EDI-001/002: os da soma); ambientes deixados de fora e atributos IFC em "Outras informações" de cada um |

Todos os relatórios têm voltar e "O que esta regra verifica" na mesma
linha, e todas as checagens o card do empreendimento sem divisórias.

**Páginas de pesquisa**: documentam a pesquisa,
e não o fluxo de uso, e por isso a proibição de citar caminho de arquivo e
comando, em (c), não vale para elas. Podem citar caminhos do repositório para
associar o conceito explicado ao que existe no código, mas não citam ADR no
texto de tela.

## Consequências
A tela de checagem não repete o relatório: o que o relatório de um
requisito mostra não ganha segundo quadro na checagem. Não há card que
explique o resultado do grupo do Programa: a síntese do grupo é o
"Resultado final" da checagem e a 2.4.2. Cada tela nova herda o padrão em
vez de inventá-lo. Não se pode: veredito em `st.success`/`st.error`,
citação fora da lista de referências, campo novo no `detalhe` ou no JSON
para servir à tela (exige decisão própria).

## Evidência
Referência de partida: `app/paginas/checagens/checagem_enquadramento.py` e
`_banner_veredito` em `app/paginas/relatorios/relatorio.py`; componentes
comuns em `app/componentes/`.
