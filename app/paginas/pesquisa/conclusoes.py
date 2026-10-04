"""Conclusões e Considerações — 1.2.8. O fecho do trabalho, com o detalhe que os Passos 3, 5
e 6 do método sustentam: os números dos cenários, a verificação dos
anéis por teste e os requisitos que dependem de dado territorial inexistente.
As limitações do estudo ficam em Desafios Técnicos, para onde a página
remete. Sem citações, como as Considerações Finais. Página de pesquisa:
largura total (ADR-034)."""

import streamlit as st

st.subheader("Conclusões")
st.write(
    'O desenvolvimento do protótipo e a sua aplicação ao estudo de caso '
    'indicam que a automatização de parte da verificação de requisitos da '
    'Portaria MCID nº 725/2023, sustentada por uma arquitetura de software '
    'modular e apoiada em padrões abertos, é viável quando integra o modelo'
    ' BIM de um empreendimento a dados geográficos públicos. Indicam também'
    ' que ela pode funcionar como **ferramenta de apoio à decisão**, '
    'liberando o analista das conferências repetitivas para as questões que'
    ' dependem de juízo técnico, sem substituir o seu parecer. Nos cenários'
    ' do estudo de caso, o protótipo decidiu 3 dos 14 requisitos aplicáveis'
    ' sobre o material como foi entregue, todos como não conformes, e '
    'chegou a 10 quando o modelo passou a trazer a informação que uma '
    'especificação exigiria, passando também a confirmar o que o projeto '
    'atende, e não apenas a apontar o que falta.'
)
st.write(
    'A organização da aplicação em **anéis de dependência**, com a norma '
    'tratada como conhecimento separado dos formatos e dos serviços e a '
    'direção das dependências verificada por teste automatizado, mostrou-se'
    ' viável e essencial para que o recorte possa crescer sem reescrever o '
    'que já existe, já que acrescentar um requisito exige apenas o seu '
    'arquivo de regra e a sua inclusão na configuração.'
)
st.write(
    'O principal condicionante encontrado não é tecnológico, e sim a '
    '**ausência de insumos e de requisitos de informação** formalizados no '
    'âmbito do PMCMV. Dos três degraus que levaram o estudo de caso de 3 a '
    '10 requisitos decididos, dois dependeram apenas de configurações de '
    'exportação do modelo, e não de modelagem adicional, o que mostra '
    'quanto do limite está no que é pedido ao proponente, e não no que a '
    'ferramenta consegue ler. O próprio protótipo se mostra um meio de '
    'construir esses requisitos, porque, ao definir como uma regra '
    'verifica, define também que informação o modelo precisa trazer, e é '
    'nesse sentido que o trabalho pode oferecer subsídios à parte '
    'contratante.'
)
st.write(
    'Muito além dos requisitos de informação, próprios do domínio BIM, '
    'parte do que a Portaria exige depende de **dados sobre o território**,'
    ' do domínio GIS, que não existem como cadastros públicos. É o caso das'
    ' alternativas de acesso à escola por transporte e do limite de '
    'unidades para o grupo de empreendimentos contíguos, que o protótipo '
    'remete à análise humana com a causa declarada por não haver base '
    'pública que as sustente, lacuna que limita o potencial de automação '
    'independentemente do que o proponente entregue.'
)
st.write(
    'Dessa forma, o avanço da verificação automatizada no programa depende '
    'de uma articulação que vai muito além do desenvolvimento de '
    'ferramentas e passa por políticas que ampliem o acesso a bases '
    'públicas e a sua confiabilidade, bem como pela criação de requisitos '
    'de informação claros para o PMCMV, de maneira que as portarias e os '
    'dispositivos que o regem possam ser redigidos de forma aderente a eles'
    ' e traduzidos com mais facilidade em requisitos verificáveis. As '
    'limitações que delimitam o alcance dessas conclusões, o estudo de um '
    'único empreendimento, o recorte restrito de requisitos e a verificação'
    ' apenas do regime geral da Portaria, estão discutidas em Desafios '
    'Técnicos.'
)

st.subheader("Trabalhos futuros")
st.write(
    'O trabalho permite vislumbrar desdobramentos e pesquisas futuras. O '
    'primeiro é **redigir requisitos de informação** e as respectivas '
    'especificações IDS a partir das regras já implementadas, testando-os '
    'em novos projetos. O segundo é **ampliar o recorte de regras**, '
    'incorporando novas checagens a partir da base de requisitos '
    'consolidada, o que a arquitetura admite sem reescrever o mecanismo de '
    'verificação. O terceiro é **aplicar o protótipo a outros '
    'empreendimentos e municípios**, para testá-lo frente a diferentes '
    'cenários de disponibilidade de dados e validar se o seu uso pode de '
    'fato se materializar como suporte à tomada de decisão dos técnicos '
    'envolvidos nos processos de análise.'
)
