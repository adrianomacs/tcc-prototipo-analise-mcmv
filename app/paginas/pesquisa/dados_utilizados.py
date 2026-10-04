"""Dados para os Testes — 1.2.5. Versão estendida do Passo 4 do método:
o empreendimento do estudo de caso, o regime excepcional da sua
contratação, a condição existente (terreno e modelo), as bases públicas, o
princípio das variantes com as três famílias e o que o autor fez no E3,
conferido na ficha do caso base. A tabela dos cenários fica na Avaliação do
Protótipo, para não se repetir; a página também não reproduz capturas de
tela, que não acrescentam a quem lê com o protótipo aberto. Página de pesquisa: largura total (ADR-034)."""

import streamlit as st

st.write(
    'O estudo de caso é o **Residencial Estrela I**, submetido ao PMCMV '
    'pela construtora TELESIL no município de Estrela, no Rio Grande do '
    'Sul, primeiro de três módulos e constituído de 300 apartamentos em '
    'edificações de térreo mais um pavimento tipo (T+1), em regime de '
    'condomínio. A construtora cedeu os modelos e os documentos usados na '
    'pesquisa. A seleção decorreu exclusivamente da escassez de '
    'empreendimentos do programa com modelos de informação da construção, '
    'condição que o Estrela I atendia, e por isso ele é tratado como um '
    'caso de estudo, e não como uma amostra que represente os '
    'empreendimentos do programa, sem pretensão de generalização '
    'estatística dos resultados.'
)

st.write(
    'O empreendimento tem uma particularidade, conhecida desde a seleção. '
    'Estrela está entre os municípios atingidos pelas enchentes de 2024 no '
    'Rio Grande do Sul, e a proposta foi contratada sob o **regime '
    'excepcional** da Portaria MCID nº 704/2024, que fixou para o município'
    ' uma meta de até 800 unidades habitacionais, correspondente aos três '
    'módulos, dispensou a qualificação do terreno e parte das exigências do'
    ' enquadramento e afastou o limite de unidades por empreendimento do '
    'regime geral. Como o protótipo verifica o regime geral da Portaria '
    'MCID nº 725/2023, parte dos seus vereditos sobre o Estrela I, no '
    'enquadramento do terreno e no porte do empreendimento, diverge da '
    'decisão real de contratação. É uma **divergência esperada**, que '
    'decorre da delimitação do escopo normativo, e não de falha da '
    'verificação, e mostra que a verificação automatizada alcança a regra '
    'geral enquanto a exceção permanece com o analista.'
)

st.write(
    'O ponto de partida dos testes foi a **condição existente** do projeto,'
    ' o material como a construtora o entregou. O terreno foi caracterizado'
    ' pela poligonal de seis vértices da planilha do projeto de '
    'implantação, em coordenadas SIRGAS 2000 / UTM zona 22S, com cerca de '
    '9,6 hectares, que corresponde à gleba inteira dos três módulos, porque'
    ' o projeto de implantação os abrange em conjunto. As informações '
    'gerais, o município, o arranjo em condomínio, as 300 unidades e a '
    'única unidade tipo, foram declaradas na própria ferramenta.'
)

st.write(
    'O modelo de informação é um único arquivo IFC da unidade tipo, '
    'exportado sem requisitos de informação, ausentes para o PMCMV, e sem '
    'configuração específica de exportação. Ele chega sem '
    'georreferenciamento estruturado, sem o sistema de coordenadas '
    'projetado e a conversão de mapa que o posicionariam no território, no '
    'nível 40 da escala LoGeoRef de Clemen e Görne (2019), e com a '
    'localização do projeto apontando para outro município. Chega também '
    'sem os ambientes, que existem no modelo nativo e não chegaram ao IFC '
    'por características da configuração de exportação do software de '
    'autoria, e sem a classificação dos revestimentos. É o retrato do '
    'projeto como ele chega hoje à análise, quando não há exigências de '
    'modelagem a cumprir.'
)

st.write(
    'O território veio de **bases públicas**. A malha territorial e o Censo'
    ' Demográfico de 2022 do IBGE situam o empreendimento no município e '
    'dão a população que define o porte municipal para o limite de '
    'unidades. O Censo Escolar do INEP fornece os estabelecimentos de '
    'ensino da checagem de proximidade, e o OpenRouteService mede as '
    'distâncias caminháveis sobre a rede viária do OpenStreetMap. A ABNT '
    'NBR 15220-3, pela lista de municípios do seu relatório técnico ABNT TR'
    ' 15220-3-1, situa Estrela na zona bioclimática 2R, que decide os '
    'limites de absortância solar. A existência desses dados publicados '
    'pesou na escolha dos requisitos testados, sobretudo no enquadramento. '
    'O acesso a escolas pôde ser verificado justamente porque há um '
    'cadastro público e localizado delas, enquanto alternativas sem dado '
    'público, como o acesso por transporte, ficaram remetidas à análise '
    'humana.'
)

st.write(
    'A partir do caso base, o autor produziu **variantes** com a '
    'procedência registrada e sob um princípio fixado antes da produção, o '
    'de que as propriedades e as configurações de exportação do modelo '
    'podiam ser alteradas, mas nenhum elemento podia ser criado ou '
    'excluído. Elas se organizam em três famílias. Os enriquecimentos (E0 a'
    ' E3) são cumulativos, e cada degrau acrescenta um requisito de '
    'informação que a parte contratante poderia estabelecer, o '
    'georreferenciamento do modelo, a exportação dos ambientes e a '
    'classificação dos revestimentos. As degradações (D1 a D3) retiram uma '
    'única coisa de um degrau, para que a perda tenha causa atribuível, e '
    'as variações legítimas (V1 a V5) alteram apenas a forma do insumo, sem'
    ' tocar o mérito do requisito, de modo que o veredito esperado é o '
    'mesmo do cenário de origem.'
)

st.write(
    'O degrau E3 é o que mais exigiu intervenção do autor, sempre dentro '
    'desse princípio. As paredes externas e a cobertura do modelo nativo '
    'foram exportadas inteiras como **revestimentos** classificados, as '
    'paredes como revestimento de fachada e a cobertura como telhado, e '
    'receberam a absortância solar, 0,35 nas paredes e 0,65 na cobertura, '
    'valores atribuídos pelo autor porque o projeto não os especifica. A '
    'cobertura, um sistema de painéis de envidraçamento usado como telha, '
    'não tem material associado no modelo entregue, e o autor manteve o '
    'elemento como estava, porque associar um material seria alterar o '
    'elemento. Os efeitos dessas escolhas nos resultados são discutidos na '
    'Avaliação do Protótipo.'
)

st.write(
    'Cada cenário foi executado no protótipo sobre os seus arquivos, com as'
    ' declarações da condição existente, e os arquivos, disponibilizados no'
    ' repositório, tornam os resultados reproduzíveis. O que cada cenário '
    'altera, o cenário de que ele parte e o que se observou estão na '
    'Avaliação do Protótipo.'
)
