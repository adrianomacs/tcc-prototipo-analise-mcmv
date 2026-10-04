"""Dados de exemplo do INEP (microdado + Catálogo de Escolas), em miniatura.

Extraído de ``tests/test_de_inep.py`` — apoio compartilhado, reusado também
por ``tests/test_recorte_municipal.py``.
"""

from __future__ import annotations

CAB_ESCOLA = ("NU_ANO_CENSO;CO_ENTIDADE;NO_ENTIDADE;CO_MUNICIPIO;NO_MUNICIPIO;"
              "SG_UF;TP_DEPENDENCIA;TP_SITUACAO_FUNCIONAMENTO;IN_ESCOLARIZACAO;"
              "IN_PODER_PUBLICO_PARCERIA;IN_COMUM_FUND_AI;IN_COMUM_CRECHE")
CAB_TURMA = ("NU_ANO_CENSO;CO_ENTIDADE;CO_MUNICIPIO;QT_TUR_BAS;QT_TUR_ESP_CE;"
             "QT_TUR_INF_CRE;QT_TUR_INF_PRE;QT_TUR_FUND_AI;QT_TUR_FUND_AF;"
             "QT_TUR_FUND_AI_MULTIETAPA")
CAB_CATALOGO = ("Código INEP,Escola,UF,Município,Endereço,"
                "Conveniada Poder Público,Restrição de Atendimento,"
                "Latitude,Longitude")

#  cod   o que é                                    dep sit escolariza parceria IN_COMUM_*
ESCOLAS = [
    # 1 creche municipal
    "2025;101;EMEI CRECHE;4307807;Estrela;RS;3;1;1;0;0;1",
    # 2 fundamental só anos iniciais — e IN_COMUM_FUND_AI=0 de propósito:
    #   se o adaptador lesse o IN_COMUM_*, esta escola sumiria do ENQ-010.1
    "2025;102;EMEF ANOS INICIAIS;4307807;Estrela;RS;3;1;1;0;0;0",
    # 3 NENHUMA turma de fundamental, mas IN_COMUM_FUND_AI=1 — a armadilha:
    #   lendo o IN_COMUM_* ela entraria falsamente no ENQ-010.1
    "2025;103;EMEI SO PRE ESCOLA;4307807;Estrela;RS;3;1;1;0;1;0",
    # 4 escola de classes exclusivas (todas as turmas são CE)
    "2025;104;ESCOLA ESPECIAL;4307807;Estrela;RS;3;1;1;0;0;0",
    # 5 ativa que não escolariza ninguém
    "2025;105;CENTRO DE ATIVIDADE;4307807;Estrela;RS;3;1;0;0;0;0",
    # 6 PARALISADA e com IN_ESCOLARIZACAO=0 — não pode virar sem_escolarizacao
    "2025;106;EMEF PARALISADA;4307807;Estrela;RS;3;2;0;0;0;0",
    # 7 privada conveniada
    "2025;107;CRECHE CONVENIADA;4307807;Estrela;RS;4;1;1;1;0;1",
    # 8 pública sem coordenada no Catálogo
    "2025;108;EMEF SEM COORDENADA;4307807;Estrela;RS;3;1;1;0;0;0",
    # 9 outro município: não pode aparecer
    "2025;201;ESCOLA DE OUTRO LUGAR;3549904;São José dos Campos;SP;3;1;1;0;0;0",
]
TURMAS = [
    "2025;101;4307807;4;0;3;1;0;0;0",     # creche + pré  -> infantil
    "2025;102;4307807;5;0;0;0;5;0;0",     # só anos iniciais
    "2025;103;4307807;2;0;0;2;0;0;0",     # só pré-escola -> infantil, NÃO fund I
    "2025;104;4307807;3;3;0;0;2;1;0",     # todas as turmas exclusivas
    "2025;105;4307807;0;0;0;0;0;0;0",     # nenhuma turma
    "2025;106;4307807;4;0;0;0;2;2;0",
    "2025;107;4307807;3;0;3;0;0;0;0",
    "2025;108;4307807;6;0;0;0;3;3;0",
    "2025;201;3549904;4;0;0;0;4;0;0",
]
CATALOGO = [
    ('101,EMEI CRECHE,RS,Estrela,"RUA A, 1",Não,'
    'ESCOLA EM FUNCIONAMENTO E SEM RESTRIÇÃO DE ATENDIMENTO,-29.5013,-51.9650'),
    ('102,EMEF ANOS INICIAIS,RS,Estrela,"RUA B, 2",Não,'
    'ESCOLA EM FUNCIONAMENTO E SEM RESTRIÇÃO DE ATENDIMENTO,-29.4990,-51.9701'),
    ('103,EMEI SO PRE ESCOLA,RS,Estrela,"RUA C, 3",Não,'
    'ESCOLA EM FUNCIONAMENTO E SEM RESTRIÇÃO DE ATENDIMENTO,-29.5060,-51.9588'),
    ('104,ESCOLA ESPECIAL,RS,Estrela,"RUA D, 4",Não,'
    'ESCOLA ATENDE EXCLUSIVAMENTE ALUNOS COM DEFICIÊNCIA,-29.5101,-51.9622'),
    ('105,CENTRO DE ATIVIDADE,RS,Estrela,"RUA E, 5",Não,'
    'ESCOLA EXCLUSIVA DE ATIVIDADE COMPLEMENTAR,-29.4955,-51.9744'),
    ('106,EMEF PARALISADA,RS,Estrela,"RUA F, 6",Não,'
    'ESCOLA PARALISADA,-29.4900,-51.9800'),
    ('107,CRECHE CONVENIADA,RS,Estrela,"RUA G, 7",Sim,'
    'ESCOLA EM FUNCIONAMENTO E SEM RESTRIÇÃO DE ATENDIMENTO,-29.4880,-51.9810'),
    # 108 tem coordenada em branco (o Catálogo real usa cadeia de espaços)
    '108,EMEF SEM COORDENADA,RS,Estrela,"RUA H, 8",Não,'
    'ESCOLA EM FUNCIONAMENTO E SEM RESTRIÇÃO DE ATENDIMENTO,'
    + " " * 30 + "," + " " * 30,
    # 999 só existe no Catálogo — divergência entre as duas fontes oficiais
    ('999,ESCOLA FANTASMA,RS,Estrela,"RUA Z, 9",Não,'
    'ESCOLA EM FUNCIONAMENTO E SEM RESTRIÇÃO DE ATENDIMENTO,-29.4800,-51.9900'),
]
