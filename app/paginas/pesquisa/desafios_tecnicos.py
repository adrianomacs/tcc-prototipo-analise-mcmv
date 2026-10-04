"""Desafios Técnicos — 1.2.7. O Passo 6 do método por inteiro,
organizado pelos mesmos temas (sem classificação por agente): a tradução da
Portaria, a especificação de informação ausente, a dependência da construção
e da exportação do modelo, a disponibilidade de dados públicos e a
organização da aplicação, e no fim as três limitações do estudo, para onde a
página de Conclusões remete. Página de pesquisa: largura total (ADR-034)."""

import streamlit as st

st.write(
    'A partir do desenvolvimento e da avaliação do protótipo frente ao '
    'estudo de caso, foi possível mapear dificuldades que ajudam a '
    'compreender o que a verificação automatizada de regras conseguiria '
    'fazer hoje e o que precisaria mudar para que conseguisse mais, de '
    'maneira a se transformar em ferramenta de apoio à decisão dos '
    'analistas técnicos que participam da análise de empreendimentos do '
    'PMCMV.'
)

st.subheader('Traduzir a Portaria em requisitos verificáveis')
st.write(
    'O primeiro desafio surge antes de qualquer código e está em **traduzir'
    ' a Portaria** em requisitos que possam ser verificados e implementados'
    ' como checagens automatizadas. A Portaria MCID nº 725/2023 foi escrita'
    ' para orientar quem projeta e quem analisa, e não para permitir a '
    'elicitação de requisitos que pudessem ser traduzidos para um sistema '
    'de checagem. A dificuldade já havia sido reconhecida por Solihin e '
    'Eastman (2015), que observaram que as regras normativas costumam ser '
    'escritas em linguagem voltada a pessoas e exigem uma interpretação que'
    ' vai além da sintaxe do texto, porque depende de compreender a '
    'intenção da regra, os pressupostos não declarados, o conhecimento '
    'geral que ela supõe e as dependências com outras regras.'
)
st.write(
    'São diversos os casos em que um mesmo dispositivo reúne mais de uma '
    'exigência, mistura o que é mensurável com o que depende de juízo, '
    'admite alternativas nem sempre explícitas e usa termos que nenhuma '
    'base define. A alternativa de acesso à escola por transporte, por '
    'exemplo, fixa um tempo máximo sem indicar horário, dia ou frequência '
    'de referência, e o limite de unidades habitacionais conforme o porte '
    'do município se aplica, no mesmo dispositivo, ao empreendimento e ao '
    'grupo de empreendimentos contíguos, grupo que nenhuma base pública '
    'permite identificar. Decompor a Portaria na base de requisitos do '
    'Passo 1 foi, por isso, um trabalho de interpretação tanto quanto de '
    'organização, e 81 das 335 linhas da base permaneceram como análise '
    'humana. Os mesmos autores registram que essa interpretação, por '
    'depender do conhecimento especializado do domínio, ainda só pode ser '
    'feita manualmente, e que no sistema de verificação de projetos de '
    'Singapura, o CORENET, ela correspondeu a algo entre 20 e 30% do '
    'esforço total, e o precedente nacional mais próximo registrou '
    'requisitos que não puderam ser automatizados por serem abertos ou '
    'ambíguos (Fernandes et al., 2018).'
)

st.subheader('A especificação de informação ausente')
st.write(
    'O desafio de maior alcance é a **ausência de requisitos de '
    'informação** definidos para os modelos do programa, cujos impactos a '
    'Avaliação do Protótipo deixou claros. Dos 14 requisitos aplicáveis ao '
    'Residencial Estrela I, o protótipo decidiu 3 sobre o material '
    'entregue, número que chegou a 10 quando o modelo passou a trazer o '
    'georreferenciamento, os ambientes e os revestimentos classificados. '
    'São informações que, num fluxo regulado de entrega, a parte '
    'contratante poderia exigir por especificação, no espírito dos ciclos '
    'de informação da ABNT NBR ISO 19650 e do nível de necessidade de '
    'informação da ISO 7817-1.'
)

st.subheader('A dependência de como o modelo é construído e exportado')
st.write(
    'Parte dessa informação já existia dentro dos modelos. Os ambientes '
    'estavam no modelo nativo e não chegaram ao arquivo IFC por conta de '
    'configurações de exportação, e dois dos três degraus da escada de '
    'cenários custaram apenas configurações de exportação. O requisito de '
    'informação não recai, portanto, só sobre o que se modela, mas sobre '
    '**o modelo como é construído e exportado**, isto é, sobre o arquivo '
    'efetivamente entregue, que precisa ser verificado como tal, e não '
    'presumido a partir do modelo de origem.'
)
st.write(
    'Outros exemplos apontam na mesma direção e não são particulares de um '
    'projeto, porque decorrem em boa parte das próprias ferramentas de '
    'autoria disponíveis no mercado. A localização do empreendimento pode '
    'aparecer registrada mais de uma vez no mesmo arquivo, nem sempre de '
    'forma coerente, como a coordenada geográfica que permaneceu em outro '
    'município mesmo depois de o sistema de coordenadas projetado ter sido '
    'definido corretamente. As convenções de unidades variam entre '
    'exportadores, e a nomenclatura dos ambientes é livre, o que obrigou o '
    'protótipo a reconhecer variações prováveis dos nomes, uma heurística '
    'ocupando o lugar de uma especificação. A baixa transparência com que '
    'as ferramentas armazenam os parâmetros de georreferenciamento (Noardo '
    'et al., 2020), as ambiguidades no uso das entidades do IFC (Azari et '
    'al., 2025) e as exigências de estruturação e nomenclatura que a '
    'verificação impõe ao modelo (Eastman et al., 2009) já eram descritas '
    'na literatura, e o estudo de caso pôde constatá-las na prática.'
)

st.subheader('A disponibilidade de dados públicos')
st.write(
    'No domínio GIS, a verificação de requisitos territoriais se mostrou '
    'extremamente dependente da **disponibilidade de dados públicos**. O '
    'acesso a escolas pôde ser verificado porque existe um cadastro público'
    ' e localizado dos estabelecimentos de ensino, o Censo Escolar do INEP,'
    ' que mesmo assim exigiu modelagem e relacionamento de dados para '
    'atender ao que a Portaria estabelece. Já a alternativa de acesso por '
    'transporte não foi passível de avaliação, porque itinerários em '
    'formato aberto são raros entre os municípios brasileiros e o '
    'transporte escolar não existe como dado aberto.'
)
st.write(
    'O mesmo limite se estende a boa parte do que a Portaria exige no '
    'enquadramento do terreno, como a infraestrutura urbana instalada, as '
    'redes de água, esgoto e drenagem, a pavimentação e os equipamentos de '
    'saúde, raramente disponíveis como dado geográfico aberto e uniforme '
    'entre municípios, lacuna que tende a ser maior justamente nos '
    'municípios de menor porte. Enquanto esses dados não existirem, ampliar'
    ' os requisitos verificáveis automaticamente dependerá menos da '
    'implementação e da adoção de ferramentas como o protótipo e mais da '
    'produção e da publicação de bases de dados confiáveis que os '
    'sustentem.'
)

st.subheader('Organizar a aplicação para crescer')
st.write(
    'No âmbito da arquitetura, o protótipo exigiu decidir **como organizar '
    'a aplicação** para que pudesse crescer de maneira sustentável. Uma '
    'regra de verificação pode ser escrita de forma direta, lendo o arquivo'
    ' e comparando o valor com a norma, mas uma coleção de regras '
    'construída assim tende a misturar o que a Portaria exige com a maneira'
    ' de ler cada formato e de consultar cada serviço. A organização do '
    'código pela ordem do fluxo de verificação, que de início parecia '
    'natural, mostrou-se limitada diante da premissa de sustentar um '
    'crescimento organizado, e foi substituída pela separação entre as '
    'regras de negócio e os detalhes de formato e de serviço proposta por '
    'Martin (2017), em anéis de dependência, descrita em Arquitetura e '
    'Desenvolvimento do Protótipo.'
)
st.write(
    'Aplicar os princípios da Arquitetura Limpa e do Domain-Driven Design '
    '(Evans, 2003) a um domínio que junta norma, modelo e território foi, '
    'em si, um dos desafios do trabalho, e as duas abordagens mostraram-se '
    'aderentes à natureza do problema, por manterem o conhecimento '
    'normativo separado dos formatos e dos serviços que o alimentam, o que '
    'permite acrescentar novos requisitos sem alterar o mecanismo de '
    'verificação.'
)

st.subheader('Limitações do estudo')
st.write(
    'Três **limitações** delimitam o alcance do que esses desafios permitem'
    ' afirmar. A primeira diz respeito ao alcance dos resultados, porque a '
    'avaliação recaiu sobre um único empreendimento, escolhido por ser um '
    'dos poucos do programa com modelos BIM disponíveis. É um estudo de '
    'caso, cujos resultados mostram o comportamento do protótipo nas '
    'condições estudadas, mas não permitem generalização estatística para o'
    ' conjunto de empreendimentos do programa.'
)
st.write(
    'A segunda está no recorte implementado. As conclusões se referem a um '
    'conjunto bastante restrito de requisitos, eleitos para exercitar '
    'mecanismos de verificação distintos nos domínios BIM, GIS e na '
    'combinação dos dois, e não para cobrir a Portaria, de modo que o que '
    'se observou vale para esses mecanismos, e não para o conjunto dos '
    'requisitos da base.'
)
st.write(
    'A terceira diz respeito ao escopo normativo, porque o protótipo '
    'verifica o regime geral da Portaria MCID nº 725/2023, e não os regimes'
    ' excepcionais de contratação, como o da Portaria MCID nº 704/2024, sob'
    ' o qual o Residencial Estrela I foi contratado. É dessa delimitação, e'
    ' não de falha da verificação, que decorre a divergência entre os '
    'vereditos do protótipo para o enquadramento do terreno e o porte do '
    'empreendimento e a decisão real de contratação.'
)
