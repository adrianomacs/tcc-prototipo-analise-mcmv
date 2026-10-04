"""Arquitetura e Desenvolvimento do Protótipo — 1.2.4. Versão estendida do
Passo 3 do método, na mesma ordem, com mais detalhe nos tópicos de IDS,
testes, decisões registradas e limitações de engenharia. Os conceitos são associados aos caminhos do
repositório, o que a página de pesquisa pode fazer sem citar ADR no texto de
tela (ADR-034, emenda das páginas de pesquisa). A figura da arquitetura é
gerada por `scripts/gerar_figura2.py` (ver
docs/figuras/README.md); a página só lê o SVG, não o desenha, e a mostra a
três quartos da largura, centralizada."""

import os

import streamlit as st

from app.servicos import motivos as _motivos
from app.servicos import requisitos as _requisitos

# Raiz do repositório medida a partir deste arquivo (app/paginas/pesquisa/),
# como em fluxo_idealizado.py, para não depender do diretório de onde o
# Streamlit foi lançado.
_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
_FIGURA_2 = os.path.join(_RAIZ, "docs", "figuras", "figura2_arquitetura.svg")


# Contagens do recorte lidas da planilha-mãe, como na página de requisitos; o
# carimbo da planilha é a chave do cache (sem sublinhado, que o cache ignora).
@st.cache_data(show_spinner=False)
def _contagem_recorte(carimbo: float) -> dict[str, int]:
    df = _requisitos.carregar_base_completa()
    if df.empty:
        return {}
    return _requisitos.contar_recorte(df, _requisitos.carregar_ids_ativos())


_rec = _contagem_recorte(_requisitos.carimbo_da_base())
_n_motivos = len(_motivos.ROTULO)

st.write(
    'Se o Framework de Análise descreve o que o sistema precisa fazer, esta'
    ' página mostra como ele foi construído para fazê-lo. Toda a '
    'arquitetura parte de uma exigência do próprio objeto de estudo, a de '
    'que a verificação de requisitos normativos seja auditável, ou seja, '
    'que cada veredito possa ser rastreado até a regra que o produziu, o '
    'insumo que consumiu e a decisão de projeto que definiu o seu '
    'comportamento.'
)

st.subheader('Premissas de projeto')
st.write(
    'Quatro **premissas de projeto** foram fixadas antes da implementação. '
    'A primeira, de natureza metodológica, foi usar apenas ferramentas de '
    'código aberto e padrões abertos, coerente com a natureza de prova de '
    'conceito do trabalho e com a comparação entre abordagens abertas e '
    'proprietárias para a integração BIM-GIS discutida por Piras et al. '
    '(2024). No âmbito BIM, o IFC, como contêiner de informação, e o IDS, '
    'como especificação de requisitos de informação, sustentam a '
    'interoperabilidade. No âmbito GIS, em que a abertura é mais '
    'consolidada, ela se apoia em formatos abertos de dados geoespaciais, '
    'como o GeoJSON e o Shapefile, nas bases públicas de dados territoriais'
    ' e na rede viária colaborativa do OpenStreetMap, além do 3D Tiles como'
    ' formato aberto para levar a geometria do modelo ao território (Chen '
    'et al., 2018).'
)
st.write(
    'A segunda foi a de que o protótipo verificaria um recorte de '
    'requisitos, mas a sua estrutura deveria admitir a expansão até a '
    'totalidade da Portaria sem reescrever o mecanismo de verificação, de '
    'modo que acrescentar um requisito custasse o mesmo que acrescentar um '
    'arquivo. A terceira foi a declaratividade, com o que a norma exige '
    'guardado em arquivos de configuração legíveis e em metadados que cada '
    'regra declara sobre si mesma, separados do código que executa cada '
    'verificação, para que ativar, desativar ou reorganizar requisitos '
    'fosse uma alteração de configuração, e não de programação. A quarta '
    'foi o desacoplamento entre o motor de regras e os mecanismos de '
    'visualização, porque visualizadores e bibliotecas de exibição de '
    'modelos e de informação geográfica surgem com frequência, e o núcleo '
    'de verificação não deveria depender de nenhum deles.'
)
st.write(
    'Sobre essas premissas, o núcleo foi escrito em Python, com o '
    '**IfcOpenShell** para ler os modelos IFC, o GeoPandas, o Shapely e o '
    'pyproj para as operações geográficas e de coordenadas, e o '
    'OpenRouteService, que calcula sobre a rede viária do OpenStreetMap os '
    'percursos e as distâncias entre pontos do mapa. A interface usa o '
    'Streamlit, com mapas em folium e a cena tridimensional em CesiumJS a '
    'partir de 3D Tiles, e a qualidade é sustentada por testes '
    'automatizados em pytest. As dependências e as suas versões mínimas '
    'estão declaradas em `pyproject.toml`.'
)

st.subheader('Duas visões da mesma arquitetura')
st.write(
    'A arquitetura é descrita por **duas visões** complementares, que '
    'respondem a perguntas diferentes. A visão comportamental responde em '
    'que ordem as operações acontecem quando uma checagem é executada, e é '
    'a dos quatro blocos que representam o protótipo na Figura 1, '
    'apresentada no Framework de Análise. O primeiro, a interpretação e '
    'estruturação das regras, antecede a execução e corresponde à base de '
    'requisitos traduzida em arquivos de regra e de configuração, e os três'
    ' seguintes, a preparação e ingestão de dados, a execução pelo motor de'
    ' regras e a saída de dados, ocorrem a cada execução, nessa ordem, como'
    ' nas etapas descritas na literatura de verificação automatizada de '
    'regras (Eastman et al., 2009; Ismail et al., 2017).'
)
st.write(
    'A visão estrutural responde como o código está organizado e o que cada'
    ' parte pode conhecer das outras. Para ela adotou-se a Arquitetura '
    'Limpa de Martin (2017), que organiza o código em anéis concêntricos e '
    'fixa a regra da dependência, pela qual cada anel só conhece os anéis '
    'mais internos. Martin distingue as **políticas**, as regras de negócio'
    ' que dão ao software a sua razão de existir, dos **detalhes**, como '
    'formatos de arquivo, bibliotecas e serviços externos, que mudam por '
    'razões e em ritmos diferentes. No protótipo, a política é o '
    'conhecimento normativo, o que a Portaria exige, e os detalhes são a '
    'leitura de cada formato e a consulta a cada serviço, que mudam com '
    'muito mais frequência do que a norma. Uma organização guiada pela '
    'ordem do fluxo diria quando cada trecho roda, mas não de que ele '
    'depende, e deixaria política e detalhes conviverem no mesmo pacote, '
    'por isso o código foi organizado em anéis, e o fluxo continua '
    'existindo como comportamento, orquestrado por um único módulo de '
    'composição.'
)
st.write(
    'Aliando a estrutura de Martin (2017) aos padrões de modelagem de Evans'
    ' (2003), os quatro anéis têm uma pasta cada. O anel interno, '
    '`core/dominio/`, reúne as entidades, os objetos de valor, os contratos'
    ' que as regras implementam, as portas para o que está fora do núcleo e'
    ' o vocabulário canônico do trabalho. Em volta dele, `core/regras/` '
    'guarda as regras, que constituem o especificador normativo, e '
    '`core/aplicacao/` guarda o caso de uso da verificação, a execução '
    'ordenada das regras e a resolução do território. Na borda, '
    '`core/infra/` reúne os adaptadores de leitura do IFC, das camadas '
    'geoespaciais, do serviço de cálculo da distância caminhável, de '
    'persistência e de exportação. Fora dos anéis, `core/composicao.py` '
    'monta o contexto da análise, injeta as portas, chama o caso de uso e '
    'grava os artefatos, e é o que a interface e a linha de comando chamam.'
)
st.write(
    'O critério de admissão no anel interno é mecânico e, portanto, '
    'conferível, já que nenhum módulo do domínio importa bibliotecas de '
    'leitura de IFC, de geoprocessamento ou de acesso a arquivo e a rede. A'
    ' direção das dependências entre os anéis é verificada por '
    '`tests/arquitetura/test_aneis.py`, que reprova a construção se um '
    'módulo importar um anel mais externo, e a fronteira entre a interface '
    'e o núcleo é verificada da mesma forma, por '
    '`tests/arquitetura/test_fronteira_app_core.py`. A Figura 2 apresenta a'
    ' visão estrutural e, no painel à direita, o caminho de uma checagem '
    'pelos anéis, que é a visão comportamental vista por dentro do núcleo.'
)
_, _meio, _ = st.columns([1, 6, 1])
with _meio:
    if os.path.isfile(_FIGURA_2):
        st.image(_FIGURA_2, width="stretch")
    else:
        st.warning(
            "A figura da arquitetura não foi encontrada. Para gerá-la, rode "
            "`python scripts/gerar_figura2.py` na raiz do projeto.",
            icon=":material/donut_large:",
        )
    st.caption(
        "Figura 2. Arquitetura do protótipo, visão estrutural, com os quatro "
        "anéis do núcleo, o módulo de composição na borda, a camada de "
        "serviços como único ponto de passagem e a pasta de artefatos como "
        "fronteira"
    )
    st.caption("Fonte: Adaptado de Martin (2012)")

st.subheader('Modelo de domínio')
st.write(
    'O primeiro conteúdo a ocupar o centro dos anéis é o domínio. Seguindo '
    'a Arquitetura Limpa, que situa as regras de negócio no centro do '
    'sistema, e o Domain-Driven Design de Evans (2003), que oferece os '
    'elementos para modelá-las, o **modelo de domínio** decide quais '
    'conceitos do processo de análise existem dentro do software, como se '
    'chamam e como se relacionam. Ele separa **entidades**, conceitos com '
    'identidade própria e história, de **objetos de valor**, definidos só '
    'pelos seus atributos. Duas propostas com as mesmas declarações, o '
    'mesmo município e o mesmo número de unidades continuam sendo duas '
    'propostas distintas, cada uma com a sua trajetória de versões e de '
    'relatórios, enquanto todas as propostas situadas em Estrela '
    'compartilham exatamente a mesma localização, e nada muda se uma for '
    'trocada pela outra.'
)
st.write(
    'O empreendimento é a **raiz de agregado**, a entidade pela qual se '
    'acessa e se altera todo o conjunto, e reúne a localização, as '
    'declarações do proponente, o terreno, as unidades tipo, as edificações'
    ' e os modelos BIM, que nunca são manipulados isoladamente. É a ele que'
    ' toda regra se aplica e todo resultado se refere, e cada versão sua '
    'recebe um número, que avança a cada mudança nos componentes. Duas '
    'escolhas do modelo têm efeito direto nos vereditos. O equipamento '
    'público pertence ao território, e não ao empreendimento, e é resolvido'
    ' antes de qualquer regra rodar, e as declarações do proponente decidem'
    ' quais requisitos se aplicam, mas nunca fornecem o valor que a regra '
    'compara com a norma. O vocabulário resultante é o mesmo no código, na '
    'documentação e no texto do TCC, prática que Evans (2003) chama de '
    'linguagem ubíqua.'
)
with st.expander("Entidades e objetos de valor do protótipo",
                 icon=":material/table_chart:"):
    st.markdown("""
| Conceito | Natureza | O que guarda e garante | Onde mora |
|---|---|---|---|
| Empreendimento | Entidade, raiz de agregado | Identidade própria e versão que avança a cada mudança; é o que todo relatório referencia | `core/dominio/empreendimento.py` |
| Terreno | Entidade | Nível de definição (ponto ou poligonal), precisão, origem e procedência | `core/dominio/terreno.py` |
| Edificação | Entidade | O prédio físico, composto por unidades tipo, com tipologia e número de unidades derivados | `core/dominio/edificacao.py` |
| Unidade tipo | Entidade | O grupo de unidades habitacionais que se repete, com nome, quantidade e tipologia | `core/dominio/unidade_tipo.py` |
| Ambiente | Entidade | Área e largura já em metros, com as unidades convertidas na leitura | `core/dominio/edificacao.py` |
| Equipamento público | Entidade | Pertence ao território, não ao empreendimento; cadastro suspeito nunca gera falso não conforme | `core/dominio/equipamentos.py` |
| Localização | Objeto de valor | Município pelo código IBGE de sete dígitos, imutável | `core/dominio/empreendimento.py` |
| Declarações | Objeto de valor | Só valores do vocabulário; governam aplicabilidade, nunca insumo | `core/dominio/vocabulario/declaracoes.py` |
| Modelo BIM | Objeto de valor | Arquivo, esquema, impressão digital e número de unidades que representa, o único número que uma regra dimensional consome | `core/dominio/modelo_bim.py` |
| Medição | Objeto de valor | O limite inferior decide o que a medição autoriza concluir | `core/dominio/mobilidade.py` |
    """)
    st.caption("Modelo de domínio do protótipo, do conceito mais concreto ao mais "
               "abstrato.")

st.subheader('Uma regra, um arquivo, e a norma como dado')
st.write(
    'A segunda premissa se materializa no formato **uma regra, um '
    'arquivo**. Cada requisito implementado é um módulo autocontido, '
    'guardado em `core/regras/bim/`, `core/regras/gis/` ou '
    '`core/regras/gis_bim/` conforme o domínio de informação que ele '
    'declara, com os seus metadados e um único método de verificação. '
    'Os metadados '
    'não servem de documentação, e sim de canal de comunicação entre a '
    'regra e o motor, declarando o identificador do requisito, o domínio de'
    ' informação, os requisitos de que depende, o alvo, o parâmetro '
    'normativo, os insumos que consome e as condições de aplicabilidade, '
    'conforme o contrato de `core/dominio/contratos/regra.py`.'
)
st.write(
    'Para uma regra nova passar a existir para o motor, não há lista a '
    'editar. Ao iniciar, o protótipo percorre a pasta das regras, carrega '
    'cada arquivo e cada regra se inscreve sozinha num cadastro em memória,'
    ' mantido por `core/regras/registro.py`, que associa cada código de '
    'requisito à regra que o verifica. O executor, em '
    '`core/aplicacao/executor.py`, nunca é alterado para acomodar um '
    'requisito, proibição que o trabalho adotou como invariante e que a '
    'suíte verifica. É o princípio aberto/fechado (Martin, 2017), aberto à '
    'extensão e fechado à modificação, e ele importa porque a base da '
    'Portaria, granularizada por método de verificação, pode chegar a '
    'centenas de verificações de complexidade e origem de informação muito '
    'diferentes (Solihin e Eastman, 2015), e uma alteração em código '
    'compartilhado arriscaria os vereditos de outras regras.'
)
st.write(
    'Do mesmo modo, **a norma fica como dado**, em três camadas que não se '
    'confundem com os arquivos das regras. A primeira é a base estruturada '
    'do Passo 1, que continua em planilha, '
    '`config/Base_Requisitos_Portaria_MCID_725.xlsx`, e é exibida pelo '
    'protótipo sem ser executada. A segunda, `config/regras_ativas.yaml`, '
    'lista só os identificadores do recorte ativo e separa existir de estar'
    ' ativo, porque uma regra pode existir como arquivo e ficar fora da '
    'lista, e um identificador pode constar da lista sem regra '
    'implementada, caso em que a interface o mostra como pendente. A '
    'terceira, `config/grupos_requisitos.yaml`, agrupa os identificadores '
    'ativos nas cinco checagens, com nome, descrição, ordem e rótulo de '
    'cada requisito na tela, sem nenhuma informação sobre como a '
    'verificação é feita. Ativar ou desativar um requisito é, portanto, '
    'mudar configuração, o que torna o recorte um parâmetro do experimento,'
    ' e a situação de cada requisito, implementado ou não, nunca é escrita '
    'nesses arquivos, e sim derivada do cadastro em tempo de execução, de '
    'modo que a configuração não pode afirmar algo que o código não '
    'sustente.'
)
with st.expander("Padrões de projeto, com a evidência de cada um no código",
                 icon=":material/code:"):
    st.markdown("""
| Padrão | Evidência |
|---|---|
| **Ports & Adapters** | `Roteador`, `FontesTerritoriais` e `LeituraModelo` são `typing.Protocol` declarados no domínio; `RoteadorORS`, `FontesCSV` e `LeituraIFC` os implementam no anel externo, `RoteadorEuclidiano` no próprio domínio; as regras importam só o contrato |
| **Strategy** | as duas implementações do cálculo da distância caminhável, o serviço em rede e a linha reta, são intercambiáveis em tempo de execução, escolhidas na borda |
| **Injeção de dependência pela borda** | o núcleo nunca lê `st.secrets` nem o ambiente; recebe o roteador já construído (`app/servicos/provedores.py`) |
| **Null Object e degradação declarada** | `roteador=None` não é erro; as regras de distância saem NÃO AVALIÁVEL por `metrica_insuficiente` |
| **Template Method** | a classe-base `Regra` fixa o esqueleto (`checar`, conforme, não conforme, não avaliável); as folhas só declaram parâmetros |
| **Registry + Plugin** | `core/regras/registro.py`, decorador `@registrar` com autodescoberta por `pkgutil`; acrescentar requisito é criar um arquivo |
| **Composite** | agregação de requisitos; o nó de um "ou" é decidido pelos membros (`agrega`, distinto de `depende_de`) |
| **Cadeia de guardas** | o executor aplica aplicabilidade, capacidade do insumo e dependências antes da checagem, cada guarda com motivo próprio |
| **Value Object e DTO** | `Resultado`, `Medicao`, `Terreno`, dataclasses com `to_dict` e `from_dict` explícitos |
| **Facade** | `core/composicao.py`, com `rodar` como ponto de entrada único usado pela interface e pela linha de comando |
| **Contrato por artefato aberto** | `artefatos/empreendimento.json` e os relatórios, com escrita atômica (`tempfile` + `os.replace`); a tela do relatório se reproduz do JSON sem reprocessar |
| **Configuração declarativa** | `config/grupos_requisitos.yaml` e `config/regras_ativas.yaml`; a situação de uma regra deriva do registro em tempo de execução, nunca do YAML sozinho |
| **Assimetria epistêmica como regra de domínio** | a linha reta pode reprovar e nunca aprovar; isso mora no dado (`Medicao.limite_inferior`), não em condicionais espalhadas pelas regras |
""")

st.subheader('Duas metades e uma fronteira explícita')
st.write(
    'O protótipo tem **duas metades**, o núcleo de verificação, em `core/`,'
    ' e a interface de uso, em `app/`, com uma fronteira explícita entre '
    'elas, que materializa a quarta premissa. O núcleo não conhece a '
    'interface, nenhum dos seus módulos importa a biblioteca de construção '
    'de telas, e a comunicação ocorre só por artefatos gravados de forma '
    'atômica em `artefatos/`, em formatos abertos. São eles o relatório de '
    'conformidade de cada checagem, em JSON e indexado pelos '
    'identificadores globais dos elementos do modelo, o estado do '
    'empreendimento, as feições do contexto geográfico em GeoJSON e a '
    'geometria da edificação em 3D Tiles. Do lado da interface, a fronteira'
    ' tem um único ponto de passagem, `app/servicos/`, a única camada '
    'autorizada a importar o núcleo, e a suíte reprova a construção se uma '
    'tela passar a importá-lo diretamente.'
)
st.write(
    'Essa separação produziu três consequências práticas. A camada gráfica '
    'pode ser trocada ou acrescentada sem tocar no núcleo, em linha com as '
    'soluções já demonstradas para integrar modelos BIM a plataformas '
    'WebGIS (Chen et al., 2018). A tela de um resultado pode ser '
    'reconstituída sem reexecutar a análise, o que separa o custo de '
    'verificar do custo de consultar e torna a saída legível por qualquer '
    'ferramenta que leia os formatos empregados, coerente com a natureza de'
    ' apoio à decisão do instrumento, cujo veredito é conferido por um '
    'analista (Preidel e Borrmann, 2018). E o núcleo pode ser testado por '
    'inteiro de forma isolada, sem rede, sem credenciais e sem a interface.'
)

st.subheader('O caso de uso do motor')
st.write(
    'O motor tem um único caso de uso, verificar uma proposta contra o '
    'recorte de requisitos, em `core/aplicacao/pipeline.py`, e é nele que '
    'os níveis de Martin (2017) se completam, pois as entidades do domínio '
    'são orquestradas por regras da aplicação, que só alcançam o mundo '
    'externo por interfaces cujas implementações são detalhes técnicos.'
)
st.write(
    "Toda regra devolve um resultado com **três estados**, conforme, não "
    "conforme e não avaliável, e o terceiro nunca aparece sozinho, vem sempre "
    "com a causa que o produziu, tirada de uma lista fechada de "
    f"{_n_motivos} motivos, em `core/dominio/vocabulario/motivos.py`. Ele é o "
    "que distingue um instrumento de medição de um sistema de aprovação, "
    "porque preserva a diferença entre o projeto não atender ao requisito e "
    "não ter sido possível examiná-lo. No relatório, a causa transforma o "
    "diagnóstico numa lista de pendências endereçada a quem pode resolvê-las, "
    "o proponente, a análise humana ou a configuração da ferramenta e das "
    "bases, e na avaliação permite medir separadamente o que o protótipo "
    "conseguiu concluir e o que concluiu como conforme."
)
st.write(
    'Na execução, as **dependências** entre requisitos são resolvidas na '
    'ordem que as próprias regras declaram, de modo que a área útil de um '
    'apartamento só é verificada depois de identificado o programa de '
    'ambientes, e a falha inesperada de uma regra vira resultado daquele '
    'requisito sem interromper as demais. O georreferenciamento é ao mesmo '
    'tempo requisito e condição técnica para cruzar o modelo com o '
    'território, e por isso a sua ausência afeta só os requisitos que '
    'dependem do território, enquanto os medidos no próprio modelo seguem '
    'normalmente.'
)
if _rec:
    _somam = (f"É por isso que, no recorte, {_rec['requisitos']} requisitos "
              f"somam {_rec['verificacoes']} verificações. ")
else:
    _somam = ""
st.write(
    "Há também requisitos que a Portaria compõe de outros, representados por "
    "um **nó de agregação**, que não verifica nada por conta própria e conclui "
    "a partir dos seus membros. " + _somam +
    "A agregação segue três padrões. No \"ou\", como o acesso à escola a pé "
    "ou por transporte, o nó aprova quando qualquer alternativa atende, mas "
    "só reprova quando todas foram examinadas e nenhuma atendeu, e assim uma "
    "alternativa sem dado público não faz o requisito reprovar por falta de "
    "dado. No \"e\" com um membro remetido à análise humana, como o limite "
    "de unidades por empreendimento e por grupo de empreendimentos contíguos, "
    "o nó pode reprovar, mas não aprovar sozinho. E na seleção por "
    "condicionante, como a absortância por zona bioclimática, só o ramo que "
    "corresponde ao território decide. Esse comportamento mora em "
    "`core/regras/base/agregacao.py`."
)
st.write(
    'O que está fora do núcleo é acessado por três **portas**, interfaces '
    'declaradas em `core/dominio/contratos/`, a leitura do modelo IFC, as '
    'fontes do território e o serviço de cálculo da distância caminhável. '
    'As implementações ficam no anel de infraestrutura, `LeituraIFC` em '
    '`core/infra/ifc/leitura_ifc.py`, `FontesCSV` em '
    '`core/infra/gis/fontes_csv.py` e `RoteadorORS` em '
    '`core/infra/rede/ors.py`, e são injetadas pelo módulo de composição, o'
    ' que permite executar a suíte sem rede e sem arquivo e faz a '
    'indisponibilidade de um serviço aparecer como resultado não avaliável,'
    ' com a causa e a providência declaradas, e não como falha. A distância'
    ' em linha reta, calculada no próprio domínio, em '
    '`core/dominio/euclidiana.py`, é usada apenas como limite inferior do '
    'percurso, porque nenhum caminho é mais curto que a reta. Quando ela já'
    ' passa do limite da Portaria, a reprovação é rigorosa, e quando fica '
    'abaixo, nada se conclui. A implementação recusou o recurso comum de '
    'multiplicar a reta por um fator de desvio e ficou com a medida que '
    'nunca aprova por estimativa.'
)

st.subheader('As checagens do recorte')
st.write(
    'As **cinco checagens** do recorte são os grupos em que esse caso de '
    'uso é apresentado ao usuário, e o que as distingue é o insumo e a '
    'porta que cada uma exercita, na ordem em que o protótipo as oferece.'
)
st.write(
    'No **enquadramento do terreno**, a checagem avalia o acesso a '
    'equipamentos públicos de educação a partir do Censo Escolar do INEP, '
    'considerando só estabelecimentos públicos em atividade e o ciclo de '
    'ensino ofertado, que determina qual requisito cada um pode satisfazer.'
    ' A distância parte do centróide do terreno, com a linha reta como '
    'pré-filtro e o serviço de cálculo da distância caminhável reservado '
    'aos casos em que pode alterar a conclusão, e a alternativa de acesso '
    'por transporte é remetida a parecer com a causa declarada, por não '
    'haver insumo público que permita avaliá-la. As regras estão em '
    '`core/regras/gis/enq_*.py`.'
)
st.write(
    'Na **qualificação urbanística**, o número de unidades declarado é '
    'confrontado com o limite que a Portaria fixa conforme o porte '
    'populacional do município, obtido do Censo Demográfico de 2022 do '
    'IBGE, e o limite ao grupo de empreendimentos contíguos é remetido à '
    'análise humana, por não haver cadastro público de propostas vizinhas '
    '(`core/regras/gis/emp_025*.py`).'
)
st.write(
    'No **georreferenciamento do modelo**, a checagem confronta o modelo '
    'com a exigência de coordenadas em sistema projetado oficial. Como '
    'modelos reais afirmam a sua localização mais de uma vez, nem sempre de'
    ' forma coerente (Azari et al., 2025; Noardo et al., 2020), o protótipo'
    ' lê as afirmações independentes, associa cada uma ao nível '
    'correspondente da escala de georreferenciamento de Clemen e Görne '
    '(2019) e as confronta entre si e com a malha municipal, sinalizando '
    'divergências ao analista. Exige-se o IFC4 para tudo o que dependa de '
    'georreferenciamento, premissa declarada na interface, e um modelo não '
    'conforme continua visualizável, coerente com a verificação como apoio '
    'à decisão (Preidel e Borrmann, 2018). A leitura das afirmações está em'
    ' `core/infra/ifc/georref/` e a regra em '
    '`core/regras/gis_bim/emp_001_georreferenciamento.py`.'
)
st.write(
    'No **programa de necessidades**, a checagem verifica a presença dos '
    'ambientes exigidos, a área útil e as larguras mínimas, por unidade '
    'habitacional. A dificuldade central é a nomenclatura livre de projeto,'
    ' em que um mesmo ambiente pode aparecer como banheiro, sanitário ou '
    'lavabo, resolvida pela correspondência dos nomes normalizados às '
    'categorias do programa mínimo, no catálogo de '
    '`core/dominio/conhecimento/catalogo_ambientes.py`, com o termo '
    'reconhecido registrado no relatório. A identificação nominal é '
    'separada da verificação dimensional, a largura é medida pelo menor '
    'lado do retângulo que envolve o contorno, e os ambientes com indício '
    'de defeito de autoria são listados à parte, sem serem avaliados nem '
    'descartados em silêncio.'
)
st.write(
    'Nos **requisitos de projeto BIM + GIS**, a absortância solar das '
    'paredes externas e da cobertura depende de dois insumos de domínios '
    'diferentes, a zona bioclimática do município, derivada da ABNT NBR '
    '15220-3 e do relatório técnico ABNT TR 15220-3-1 e guardada em '
    '`config/zonas_bioclimaticas.csv`, e a absortância do revestimento '
    'externo lida no modelo. O território decide o limite, e basta um '
    'revestimento acima dele para o requisito reprovar. A ausência do '
    'revestimento como elemento próprio, do tipo da face ou do material '
    'nomeado produz resultado não avaliável com a causa nomeada, o que faz '
    'desta checagem a que mais diretamente expõe o que uma futura '
    'especificação de informação teria de exigir.'
)

st.subheader('O IDS como requisito de informação, não como etapa do software')
st.write(
    'No Framework de Análise, o IDS aparece como o filtro que o proponente '
    'aplica antes da submissão, fora da ferramenta de verificação. No '
    'protótipo ele não é executado, e a razão é a mesma lacuna que o '
    'trabalho investiga, a inexistência de requisitos de informação de '
    'projeto definidos para o programa, sem os quais não há especificação a'
    ' verificar. Cada regra conclui, então, a partir das estruturas nativas'
    ' do IFC e trata a ausência de informação como resultado declarado, e o'
    ' **IDS** fica onde lhe cabe, como **requisito de informação** que a '
    'parte contratante exige do proponente antes da submissão '
    '(buildingSMART International, 2024), coerente com o nível de '
    'necessidade de informação da ISO 7817-1 e com os ciclos de informação '
    'da ABNT NBR ISO 19650.'
)
st.write(
    'A possibilidade não foi excluída da arquitetura. O contrato da regra '
    'tem um campo para a especificação IDS de que ela depende (`ids_spec`, '
    'em `core/dominio/contratos/regra.py`), e o executor, quando o campo '
    'está preenchido, valida o modelo contra a especificação antes de '
    'executar a regra, pelo validador de `core/regras/validacao_ids/`, '
    'tratando a falha como informação ausente. Hoje o campo está vazio em '
    'todas as regras. Há aí uma inversão que também é resultado, porque na '
    'ordem idealizada o IDS viria antes e a verificação depois, mas foi ao '
    'implementar cada regra e observar o que ela precisa ler no modelo que '
    'se tornou possível saber o que uma especificação deveria exigir, de '
    'modo que o IDS nasce do exercício de verificação, e não o antecede.'
)

st.subheader('Estratégia de testes e qualidade')
st.write(
    'Uma verificação automatizada tem um erro difícil de perceber, já que '
    'um veredito errado tem a mesma aparência de um certo, e por isso a '
    '**estratégia de testes** foi tratada como parte da arquitetura, e não '
    'como atividade posterior. A suíte, em `tests/`, espelha a árvore do '
    'código e combina quatro naturezas de teste. Os testes unitários '
    'exercitam cada regra e cada mecanismo com modelos falsos, como os de '
    '`tests/apoio/ifc_falso.py`, sem depender de arquivo em disco. Os '
    'testes de integração executam a cadeia completa, da leitura do arquivo'
    ' ao veredito, sobre as variantes reais do modelo do estudo de caso, '
    'cada uma com o resultado esperado definido antes, e correspondem aos '
    'cenários da Avaliação do Protótipo '
    '(`tests/scripts/test_cenarios_estrela_i.py`). Os testes de propriedade'
    ' protegem garantias que não se conferem caso a caso, como a de que a '
    'distância em linha reta nunca supera a geodésica, confrontada com a '
    'solução de referência em grande número de pares de pontos no '
    'território brasileiro (`tests/core/dominio/test_euclidiana.py`). E os '
    'testes de arquitetura, em `tests/arquitetura/`, prendem as próprias '
    'decisões estruturais, reprovando a construção se uma tela importar o '
    'núcleo diretamente, se um anel importar um anel mais externo ou se um '
    'documento vigente apontar para um arquivo que não existe. Toda a suíte'
    ' roda sem rede e sem credenciais, com respostas reais do serviço de '
    'cálculo da distância caminhável gravadas em `tests/fixtures/`.'
)

st.subheader('Decisões registradas e limitações de engenharia')
st.write(
    'Cada decisão estrutural foi registrada num **registro de decisão de '
    'arquitetura**, com o contexto que a motivou, as consequências '
    'assumidas e o teste que a protege, em `docs/arquitetura/adr/`, e as '
    'leituras da Portaria que exigiram interpretação ficaram num registro '
    'próprio de decisões normativas, '
    '`docs/arquitetura/DECISOES_NORMATIVAS.md`. A separação nasceu da '
    'própria implementação, já que a arquitetura estabiliza com o tempo '
    'enquanto a leitura normativa muda a cada correção do texto legal. É '
    'esse registro que liga decisão, código e verificação e torna a '
    'verificação auditável no sentido dado no início desta página, e sem '
    'ele as afirmações sobre a arquitetura não poderiam ser conferidas '
    'depois.'
)
st.write(
    'Além das limitações do estudo, discutidas em Desafios Técnicos, '
    'algumas **limitações de engenharia** são assumidas e declaradas, e '
    'nenhuma delas altera os resultados apresentados. As regras leem o '
    'modelo por uma porta declarada no domínio, mas essa porta devolve o '
    'que a biblioteca de leitura do IFC já oferece, sem uma camada que '
    'traduza o modelo inteiro para o domínio, fronteira pragmática que '
    'evitou uma tradução prematura, mas acopla as regras BIM ao formato. Um'
    ' arquivo que representa unidades de mais de uma unidade tipo é '
    'avaliado em conjunto, de modo que uma unidade conforme pode compensar '
    'outra que não é, situação que o protótipo sinaliza como diagnóstico, '
    'em `core/aplicacao/diagnosticos.py`, mas que só desaparece com um '
    'modelo por unidade tipo, o que é requisito de informação, e não '
    'código. E a contenção geométrica completa do modelo no terreno não é '
    'verificada, porque, no programa, a unidade tipo se repete e não tem '
    'posição própria, e quem carrega as coordenadas de cada edificação é o '
    'modelo de implantação, ausente do material entregue, o que reduz a '
    'verificação ao aviso sobre a âncora descrito na checagem de '
    'georreferenciamento.'
)
st.write(
    'O repositório, com o código, a documentação de arquitetura, os '
    'registros de decisão e a base completa de requisitos, é '
    'disponibilizado com as instruções para refazer as análises do estudo '
    'de caso e chegar aos mesmos resultados.'
)

st.subheader('Desenvolvimento apoiado por IA generativa')
st.write(
    'O protótipo foi desenvolvido com o apoio de um assistente de **IA '
    'generativa** (Claude, da Anthropic), e as decisões de arquitetura, o '
    'recorte normativo e a redação permaneceram com o autor.'
)
