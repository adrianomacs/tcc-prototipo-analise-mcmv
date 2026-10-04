"""Avaliação do Protótipo — 1.2.6. Versão estendida do Passo 5 do método,
em quatro partes:
o desenho da avaliação, os cenários, os resultados e a leitura. As duas
tabelas de resultados têm as colunas de mudança esperada e
observada, apresentadas em HTML com os estados em cor, porque a
página não segue a formatação de trabalho acadêmico (ADR-034, emenda das páginas de
pesquisa). Os números são a fotografia da rodada oficial dos cenários sobre
o Estrela I, escritos à mão: são um
retrato no tempo. As medidas contam requisitos da Portaria, não verificações
(ADR-015). D4, D5, DD1 e DD2 seguem em ``config/cenarios_estrela_i.yaml`` e
nos testes, mas não entram aqui, porque o texto não os traz."""

import re

import streamlit as st

from app.componentes.paineis import COR_ESTADO

# Colunas da tabela de mudança esperada e observada do Passo 5. Cada
# linha: cenário, origem, mudança esperada, mudança observada, capacidade de
# conclusão esperada e observada, conformidade esperada e observada.
_ENRIQUECIMENTOS = [
    ("E0", "—", "—", "—", "—", "3/14", "—", "0/3"),
    ("E1", "E0", "EMP-001 de NC para C", "EMP-001 de NC para C",
     "3/14", "3/14", "1/3", "1/3"),
    ("E2", "E1",
     "Os sete requisitos do programa de necessidades passam a decididos",
     ("Seis passam a decididos, EDI-004.1, 007, 008 e 011 como C e EDI-004 "
      "e 009 como NC; EDI-002 segue NA (pré-requisito)"),
     "10/14", "9/14", "—", "5/9"),
    ("E3", "E2", "EDI-019 e EDI-024 passam a decididos",
     "EDI-019 de NA para C; EDI-024 segue NA (informação ausente)",
     "12/14", "10/14", "—", "6/10"),
]
_DEGRADACOES = [
    ("D1", "E3",
     "EMP-001 de C para NC, por exigir IFC4; programa segue avaliado",
     ("EMP-001 de C para NC; programa segue avaliado; EDI-019 de C para NA "
      "(informação ausente)"),
     "10/14", "9/14", "5/10", "4/9"),
    ("D2", "E1", "EMP-001 de C para NC, pelo confronto com a malha municipal",
     "EMP-001 de C para NC, pelo confronto com a malha municipal",
     "3/14", "3/14", "0/3", "0/3"),
    ("D3", "E2", "EDI-009 de NC para NA; EDI-007, 008 e 011 seguem avaliados",
     "EDI-009 de NC para NA (informação ausente); os demais seguem avaliados",
     "8/14", "8/14", "5/8", "5/8"),
]
_NENHUM = "Nenhum veredito alterado"
_MESMOS = "Nenhum veredito alterado, com os mesmos valores medidos"
_VARIACOES = [
    ("V1", "E2", _NENHUM, _NENHUM, "9/14", "9/14", "5/9", "5/9"),
    ("V2", "E3", _NENHUM, _MESMOS, "10/14", "10/14", "6/10", "6/10"),
    ("V3", "E0", _NENHUM, _NENHUM, "3/14", "3/14", "0/3", "0/3"),
    ("V4", "E3", _NENHUM, _MESMOS, "10/14", "10/14", "6/10", "6/10"),
    ("V5", "E0", _NENHUM,
     "Nenhum veredito alterado, com as distâncias deslocadas",
     "3/14", "3/14", "0/3", "0/3"),
]

_CABECALHO = ("Cenário (origem)", "Mudança esperada", "Mudança observada",
              "Capacidade de conclusão esperada",
              "Capacidade de conclusão observada",
              "Conformidade esperada", "Conformidade observada")
_ESTADO_DA_SIGLA = {"C": "conforme", "NC": "nao_conforme",
                    "NA": "nao_avaliavel"}
_DIFERENCA = "rgba(251, 188, 4, 0.18)"
# Larguras fixas, para as duas tabelas alinharem as mesmas colunas.
_COLUNAS = "<colgroup>" + "".join(
    f'<col style="width:{w}%">' for w in (9, 20, 27, 11, 11, 11, 11)
) + "</colgroup>"


def _selo(sigla: str) -> str:
    cor = COR_ESTADO[_ESTADO_DA_SIGLA[sigla]]
    return (f'<span style="background:{cor};color:#1A1A1A;padding:0 6px;'
            f'border-radius:4px;font-weight:600;white-space:nowrap">'
            f'{sigla}</span>')


def _com_selos(texto: str) -> str:
    return re.sub(r"\b(NC|NA|C)\b", lambda m: _selo(m.group(1)), texto)


def _tabela(grupos: list[tuple[str | None, list[tuple]]]) -> str:
    """Tabela HTML com as colunas do texto. A medida observada que difere da
    esperada ganha fundo âmbar, que é a leitura que a página propõe."""
    borda = "1px solid rgba(128, 128, 128, 0.35)"
    cel = f"padding:6px 10px;border-bottom:{borda};vertical-align:top"
    num = cel + ";text-align:center;white-space:nowrap"
    cab = "".join(f'<th style="{cel};text-align:left;font-weight:600">{c}</th>'
                  for c in _CABECALHO)
    linhas = []
    for titulo, cenarios in grupos:
        if titulo:
            linhas.append(
                f'<tr><td colspan="7" style="{cel};font-weight:600;'
                f'background:rgba(128, 128, 128, 0.10)">{titulo}</td></tr>')
        for cid, origem, esp, obs, cap_e, cap_o, conf_e, conf_o in cenarios:
            def medida(esperada: str, observada: str) -> str:
                difere = esperada not in ("—", observada)
                fundo = f";background:{_DIFERENCA}" if difere else ""
                return (f'<td style="{num}">{esperada}</td>'
                        f'<td style="{num}{fundo}"><b>{observada}</b></td>')
            linhas.append(
                f'<tr><td style="{cel};white-space:nowrap"><b>{cid}</b> '
                f'({origem})</td>'
                f'<td style="{cel}">{_com_selos(esp)}</td>'
                f'<td style="{cel}">{_com_selos(obs)}</td>'
                f'{medida(cap_e, cap_o)}{medida(conf_e, conf_o)}</tr>')
    return (f'<div style="overflow-x:auto;margin-bottom:0.5rem">'
            f'<table style="width:100%;border-collapse:collapse;'
            f'font-size:0.92rem;table-layout:fixed">{_COLUNAS}'
            f'<thead><tr style="border-bottom:{borda}">{cab}</tr></thead><tbody>{"".join(linhas)}</tbody></table></div>')


_LEGENDA = (
    f"{_selo('C')} conforme · {_selo('NC')} não conforme · {_selo('NA')} "
    f"não avaliável, com a causa entre parênteses · "
    f'<span style="background:{_DIFERENCA};padding:0 6px;border-radius:4px">'
    f"medida observada diferente da esperada</span>")

st.write(
    "A avaliação responde a uma pergunta diferente da do acerto de cada regra, "
    "que é papel dos testes automatizados. A partir do desenvolvimento do "
    "protótipo e dos cenários estabelecidos para o estudo de caso, ela se "
    "concentrou em verificar quanto o protótipo consegue concluir sobre o "
    "empreendimento, a partir do material efetivamente entregue, e de que "
    "maneira essa capacidade se altera quando a informação disponível melhora "
    "ou piora."
)

st.subheader("O desenho da avaliação")
st.write(
    "Para isso, adotaram-se duas medidas, a **capacidade de conclusão**, que "
    "é a parcela dos requisitos aplicáveis que o protótipo conseguiu decidir, "
    "julgados conformes ou não conformes a partir do material disponível, e a "
    "**conformidade**, que é a parcela dos requisitos decididos que o projeto "
    "atende."
)
c1, c2 = st.columns(2)
with c1:
    st.latex(r"\text{capacidade de conclusão} = "
             r"\frac{\text{conformes} + \text{não conformes}}"
             r"{\text{requisitos aplicáveis}}")
with c2:
    st.latex(r"\text{conformidade} = "
             r"\frac{\text{conformes}}{\text{conformes} + \text{não conformes}}")
st.write(
    "Os requisitos que permanecem não avaliáveis ficam fora do cálculo da "
    "conformidade, porque contá-los faria um requisito não verificado pesar "
    "como se o projeto não o atendesse, confundindo a falta de informação com "
    "o descumprimento da norma. Em compensação, o protótipo registra para "
    "cada um deles a causa que impediu a conclusão, de modo que o resultado "
    "de um cenário mostra quantos requisitos foram decididos e também por que "
    "os demais não o foram."
)
st.write(
    "As duas medidas contam o requisito da Portaria que recebe veredito, e "
    "não as verificações que o protótipo executa. Um requisito composto de "
    "alternativas ou de ramos conta uma vez só, pelo resultado do seu nó de "
    "agregação, e por isso decompor um requisito em mais verificações não "
    "altera as medidas. Por essa régua, a varanda como parte do programa "
    "(EDI-004.1) conta como requisito próprio, por ter veredito próprio, e a "
    "área útil mínima da casa (EDI-001) deixa de contar por não se aplicar a "
    "um condomínio de apartamentos, o que resulta, por coincidência, nos "
    "mesmos 14 requisitos do recorte implementado no protótipo."
)
st.write(
    "Para cada cenário, a **mudança esperada** em relação ao cenário de que "
    "ele parte foi registrada no desenho da avaliação antes da produção dos "
    "arquivos, na forma dos requisitos que deveriam mudar de estado e do "
    "estado que deveriam alcançar. Nos degraus em que o veredito depende do "
    "projeto real, esperou-se apenas que o requisito passasse a ser decidido, "
    "sem antecipar se conforme ou não conforme, e nas variações legítimas, "
    "que alteram só a forma do insumo, a mudança esperada é a manutenção de "
    "todos os vereditos. A leitura de cada cenário compara a mudança esperada "
    "com a **mudança observada**, o que permite separar o aumento da "
    "capacidade de conclusão que vem por construção daquilo que o desenho da "
    "avaliação não antecipou."
)

st.subheader("Os cenários")
st.write(
    "A variável do experimento não é o protótipo, e sim o nível de "
    "informação disponível. Os cenários partem da **condição existente** "
    "(E0), o material como chegou à análise, e se organizam em três famílias. "
    "Os degraus de enriquecimento (E1 a E3) acrescentam, de forma cumulativa, "
    "uma informação que a parte contratante poderia exigir do proponente, e o "
    "último deles, o E3, configura o **teto** da capacidade de conclusão "
    "esperada. As **degradações** (D1 a D3) retiram de um degrau uma única "
    "característica, para que cada perda tenha causa atribuível, e as "
    "**variações legítimas** (V1 a V5) mudam só a forma do insumo, à espera "
    "do mesmo veredito."
)
st.write(
    "Todos os arquivos foram produzidos pelo autor a partir dos modelos "
    "nativos cedidos pela construtora, sem alterar os elementos do projeto, e "
    "cada cenário foi executado no protótipo sobre os seus arquivos, com as "
    "declarações da condição existente."
)
with st.expander("O que cada cenário altera", icon=":material/folder_open:"):
    st.markdown("""
| Cenário (origem) | O que altera |
|---|---|
| **E0** (—) | Nada. O modelo da unidade tipo como entregue, sem georreferenciamento estruturado, sem os ambientes e sem a classificação dos revestimentos, e o terreno pela poligonal do projeto de implantação |
| **E1** (E0) | O modelo reexportado com o sistema de coordenadas projetado, SIRGAS 2000 / UTM zona 22S, e a conversão de mapa que posiciona o bloco na gleba |
| **E2** (E1) | Os ambientes do próprio projeto exportados, com nome e área, sem nenhum ambiente criado pelo autor |
| **E3** (E2) | Paredes externas e cobertura exportadas como revestimentos classificados, com a absortância solar informada pelo autor (0,35 e 0,65), por o projeto não a especificar |
| **D1** (E3) | O mesmo estado exportado no esquema IFC2X3 |
| **D2** (E1) | Georreferenciamento completo, mas apontando para a localização herdada do material entregue, em outro município |
| **D3** (E2) | Ambientes renomeados em inglês |
| **V1** (E2) | Ambientes renomeados com sinônimos usuais, como dormitório, WC e lavanderia |
| **V2** (E3) | Unidades do projeto em pés e hectares |
| **V3** (E0) | Terreno descrito por um modelo IFC da gleba, elaborado pelo autor |
| **V4** (E3) | Exportação com todos os conjuntos de propriedades e quantidades disponíveis |
| **V5** (E0) | Poligonal restrita à porção do Estrela I, extrapolada da prancha de implantação |
""")

st.subheader("Os resultados")
st.write(
    "A primeira tabela apresenta, para os degraus de enriquecimento e para as "
    "degradações, a mudança esperada e a observada em relação ao cenário de "
    "que cada um parte, com as duas medidas esperadas e observadas lado a lado."
)
st.markdown(_tabela([("Enriquecimentos", _ENRIQUECIMENTOS),
                     ("Degradações", _DEGRADACOES)]),
            unsafe_allow_html=True)
st.markdown(
    f'<div style="font-size:0.85rem;margin-bottom:1rem">{_LEGENDA}. O '
    "travessão na medida esperada indica que o desenho da avaliação não "
    "antecipou o veredito, por depender do projeto real.</div>",
    unsafe_allow_html=True)
st.write(
    "A segunda tabela traz as variações legítimas, em que a mudança esperada "
    "é, por definição, nenhuma, e as medidas esperadas são as do cenário de "
    "origem."
)
st.markdown(_tabela([(None, _VARIACOES)]), unsafe_allow_html=True)

st.subheader("A leitura dos resultados")
st.write(
    "Na **condição existente**, o protótipo decide 3 dos 14 requisitos, todos "
    "como não conformes, e não produz nenhuma conformidade. O "
    "georreferenciamento reprova porque o modelo chega no nível 40 da escala "
    "LoGeoRef (Clemen e Görne, 2019), sem sistema de coordenadas projetado. O "
    "porte do empreendimento reprova porque as 300 unidades previstas superam "
    "o limite de 100 unidades por empreendimento fixado para municípios de "
    "até 50 mil habitantes, faixa em que Estrela se enquadra com 32.183 "
    "habitantes no Censo Demográfico de 2022, e o acesso à educação infantil "
    "reprova porque as escolas ficam acima do limite de 1.000 m. Os outros 11 "
    "requisitos saem como não avaliáveis, cada um com a sua causa, nove por "
    "ausência de informação no modelo, sete pelos ambientes, um deles por "
    "pré-requisito, e dois pelos revestimentos, e dois por dependerem de dado "
    "que não é público, "
    "remetidos ao analista como pendências. A análise do material como ele "
    "chega se converte, assim, numa lista de pendências com a causa de cada "
    "uma."
)
st.write(
    "As reprovações do enquadramento e do porte se repetem em todos os "
    "cenários, porque não dependem do modelo, e decorrem da excepcionalidade "
    "do empreendimento. Estrela está entre os municípios atingidos pelas "
    "enchentes de 2024 no Rio Grande do Sul, e o Estrela I foi contratado sob "
    "o regime excepcional da Portaria MCID nº 704/2024, que fixou para o "
    "município uma meta de até 800 unidades habitacionais, correspondente aos "
    "três módulos, e afastou o limite de unidades por empreendimento do "
    "regime geral. Como o protótipo verifica o regime geral da Portaria MCID "
    "nº 725/2023, esses vereditos divergem da decisão real de contratação por "
    "delimitação do escopo normativo, e não por falha da verificação."
)
st.write(
    "Ao longo dos degraus, o aumento da capacidade de conclusão é esperado "
    "por construção, já que cada um acrescenta a informação que um grupo de "
    "regras consome, e a leitura relevante está na diferença entre o esperado "
    "e o observado. No E1, a mudança observada coincide com a esperada, o "
    "georreferenciamento passa de não conforme a conforme com a reexportação "
    "do modelo com o sistema de coordenadas projetado e a conversão de mapa, "
    "e nada mais se altera. A capacidade de conclusão se mantém em 3 de 14, e "
    "a conformidade passa a 1 dos 3 requisitos decididos."
)
st.write(
    "No E2, com a exportação dos ambientes, esperava-se que os sete "
    "requisitos do programa de necessidades passassem a decididos, e seis o "
    "foram. Passam a conformes a varanda como parte do programa, as larguras "
    "mínimas da cozinha e da sala e as dimensões mínimas da varanda, e a não "
    "conformes o programa mínimo de ambientes, porque o modelo traz cinco "
    "salas para as oito unidades que representa, e a largura mínima do "
    "banheiro, medida em 1,485 m contra o mínimo de 1,50 m. A área útil do "
    "apartamento segue não avaliável porque depende de o programa fechar. O "
    "protótipo separou ainda dez ambientes com indício de defeito de autoria "
    "e os listou à parte, sem avaliá-los, o que evitou que a largura de uma "
    "sala inexistente produzisse um não conforme. A capacidade de conclusão "
    "passa a 9 de 14, e a conformidade a 5 dos 9 decididos."
)
st.write(
    "No E3, com os revestimentos classificados, a absortância das paredes "
    "externas foi decidida como conforme, com o valor de 0,35 abaixo do "
    "limite de 0,6 da zona bioclimática de Estrela. Como o valor foi "
    "atribuído pelo autor para exercitar a regra, o resultado demonstra a "
    "verificação e não atesta a especificação real do projeto. A absortância "
    "da cobertura permanece não avaliável mesmo com o valor de 0,65 "
    "informado, porque a cobertura do modelo entregue, um sistema de painéis "
    "de envidraçamento usado como telha, não tem material associado, e a "
    "regra depende dele para aplicar as exceções da Portaria. Corrigir essa "
    "modelagem exigiria alterar elementos do modelo, o que o princípio "
    "adotado na produção das variantes não admite."
)
st.write(
    "O cenário E3 fica, assim, em 10 dos 14 requisitos decididos, com 6 "
    "conformes, abaixo dos 12 previstos no desenho da avaliação, por duas "
    "lacunas da própria entrega, o programa de ambientes que não fecha e a "
    "cobertura sem material. Os dois requisitos de acesso ao ensino "
    "fundamental não são decididos em nenhum degrau, como esperado. A "
    "alternativa a pé é examinada e não atende, a alternativa por transporte "
    "depende de dado que não é público, e o requisito só reprova depois de "
    "examinadas todas as alternativas, de modo que esse limite vem da "
    "disponibilidade de dados, e não da informação do proponente."
)
st.write(
    "As **degradações** retiraram, cada uma, uma única característica de um "
    "cenário da escada. No D2, o modelo tem a estrutura completa de "
    "georreferenciamento e ainda assim reprova, porque a sua âncora cai em "
    "outro município, erro que só o confronto com a malha municipal revela. "
    "No D3, com os ambientes em inglês, a queda é parcial, porque o catálogo "
    "de nomes reconhece parte dos termos, como os da cozinha, da sala e da "
    "varanda, e não reconhece os do dormitório, do banheiro e da área de "
    "serviço, de modo que a largura do banheiro deixa de ser avaliada e o "
    "programa mínimo segue não conforme, agora também pelos ambientes não "
    "reconhecidos. No D1, a exportação em IFC2X3 produziu a mudança esperada, "
    "a reprovação do georreferenciamento por exigir IFC4, e uma segunda, não "
    "prevista, a perda da absortância das paredes, porque o esquema anterior "
    "não traz o conjunto de propriedades que identifica o revestimento como "
    "externo. O programa de necessidades segue avaliado, já que os ambientes "
    "são representados da mesma forma nos dois esquemas, e a premissa do IFC4 "
    "limita, portanto, o que se conclui, sem bloquear o restante da análise."
)
st.write(
    "Nas cinco **variações legítimas**, a mudança observada coincidiu com a "
    "esperada, nenhum veredito se alterou, e as duas medidas repetiram as do "
    "cenário de origem. No V2 e no V4 repetiram-se também as áreas, as "
    "larguras e as distâncias medidas, o que mostra que a conversão de "
    "unidades e a leitura das propriedades não dependem da forma do insumo. "
    "No V5, a restrição da poligonal deslocou o centro do terreno em cerca de "
    "440 m e alterou as distâncias, com a escola de ensino fundamental mais "
    "próxima a 2.158 m pela rede viária, sem alterar nenhum veredito."
)
st.write(
    "Nos cenários em que a mudança observada diferiu da esperada, a causa "
    "estava na estrutura de dados do modelo entregue ou nas configurações de "
    "exportação, e foi declarada pelo protótipo. Em conjunto, os cenários "
    "mostram que o protótipo concluiu quando a informação estava disponível, "
    "deixou de concluir, ou reprovou, quando ela faltava ou estava errada, sem "
    "produzir veredito por falta de dado, e manteve o veredito diante de "
    "mudanças que não afetam o mérito do requisito. A distância entre os 3 "
    "requisitos decididos na condição existente e os 10 do cenário E3 "
    "corresponde à informação que a parte contratante poderia exigir do "
    "proponente, e dois dos três degraus, o georreferenciamento e os "
    "ambientes, dependeram apenas de configurações de exportação, e não de "
    "modelagem adicional, o que liga os resultados da avaliação aos desafios "
    "discutidos na página Desafios Técnicos."
)
with st.expander("Como refazer os cenários", icon=":material/terminal:"):
    st.markdown(
        "Os cenários são declarados como dado em "
        "`config/cenarios_estrela_i.yaml`, que fixa para cada um a família, o "
        "cenário de origem e o papel do arquivo. Os arquivos seguem a "
        "convenção `entradas/ifc/estrela_i/<id>_*.ifc` e "
        "`entradas/gis/estrela_i/<id>_*.csv`, e o que um cenário não traz em "
        "arquivo próprio ele herda do cenário de origem. O comando "
        "`python scripts/rodar_cenario.py <id> --ors` roda as cinco checagens "
        "sobre as declarações do empreendimento, sem alterá-las, e grava em "
        "`artefatos/cenarios/<id>/` os mesmos relatórios que as telas leem, "
        "com as distâncias pelo serviço de cálculo da distância caminhável. O "
        "script `scripts/gerar_tabelas_cenarios.py` reúne os relatórios de "
        "todos os cenários no perfil dos 14 requisitos, e o teste de "
        "integração `tests/scripts/test_cenarios_estrela_i.py` confere o "
        "resultado de cada família. Os números desta página reproduzem a "
        "rodada oficial dos cenários."
    )
