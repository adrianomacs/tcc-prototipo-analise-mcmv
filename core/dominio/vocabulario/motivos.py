"""Taxonomia das causas de NÃO AVALIÁVEL.

Saber que um requisito é "não avaliável" sem saber **por quê** não serve para
nada: as causas pedem ações completamente diferentes — fornecer uma camada,
classificar atributos, desenhar a poligonal, mandar um técnico a campo. Criar um
quarto valor em ``Estado`` mexeria no motor, no relatório e nas métricas de uma
vez; então o estado continua sendo um dos três e a **causa** viaja em
``Resultado.detalhe[CHAVE]``, com o relatório agrupando por ela.

O efeito prático é o relatório deixar de ser diagnóstico e virar lista de
pendências: cada não avaliável aponta o que o destrava.

``METRICA_INSUFICIENTE`` é o caso mais sutil da lista: o insumo
existe, está completo e foi medido — o que falta é **poder de conclusão** da
métrica. A distância em linha reta é um piso da distância caminhável, então ela
reprova legitimamente quando já ultrapassa o limiar, mas não aprova quando fica
abaixo. Ver ``core/dominio/mobilidade.py``.

``AGREGACAO_INDECISA`` é irmão dele um nível acima: nem o insumo nem
a métrica são o obstáculo — é o **conjunto de resultados** que não alcança o
limiar nem o exclui. Ele é a exceção da taxonomia, o único motivo cuja ação não
nomeia um insumo, e por isso é o **último recurso**: quando os membros pendentes
travam pela mesma causa, o pai herda a causa deles, para que a ação siga
específica. Ver ``core/regras/base/agregacao.py``.
"""

from __future__ import annotations

CHAVE = "motivo_nao_avaliavel"

NAO_APLICAVEL = "nao_aplicavel"
PREREQUISITO_FALHO = "prerequisito_falho"
INFORMACAO_AUSENTE = "informacao_ausente"
TERRENO_AUSENTE = "terreno_ausente"
TERRENO_INSUFICIENTE = "terreno_insuficiente"
INSUMO_AUSENTE = "insumo_ausente"
INSUMO_SUSPEITO = "insumo_suspeito"
METRICA_INSUFICIENTE = "metrica_insuficiente"
AGREGACAO_INDECISA = "agregacao_indecisa"
MEMBRO_NAO_EXECUTADO = "membro_nao_executado"
MAPEAMENTO_PENDENTE = "mapeamento_pendente"
PORTE_INDETERMINADO = "porte_indeterminado"
VERIFICACAO_EM_CAMPO = "verificacao_em_campo"
ANALISE_HUMANA_DOCUMENTAL = "analise_humana_documental"
ERRO_DE_EXECUCAO = "erro_de_execucao"
# ADR-022: o 16º motivo, e o primeiro cuja correção é do PROPONENTE. Cobre só
# declaração × declaração (a soma das unidades tipo passa do previsto; a
# composição das edificações passa das unidades do tipo; o covering e a parede
# que o hospeda declaram externalidade oposta). Divergência entre o declarado e
# o medido é conferência, não isto.
INCONSISTENCIA_DECLARATORIA = "inconsistencia_declaratoria"
# ADR-033: o 17º motivo. Falta um insumo que SÓ o proponente fornece — o modelo
# IFC ou uma declaração de Informações Gerais. A mensagem da regra diz qual dos
# dois; a ação é uma só. ``INSUMO_AUSENTE`` fica estritamente geoespacial, e
# conteúdo que falta DENTRO do modelo continua ``INFORMACAO_AUSENTE``.
INSUMO_DO_PROPONENTE_AUSENTE = "insumo_do_proponente_ausente"

ROTULO = {
    NAO_APLICAVEL: "Não aplicável às condições declaradas",
    PREREQUISITO_FALHO: "Depende de outra verificação não aprovada",
    INFORMACAO_AUSENTE: "Informação ausente no modelo",
    TERRENO_AUSENTE: "Terreno não definido",
    TERRENO_INSUFICIENTE: "Terreno sem a definição da poligonal",
    INSUMO_AUSENTE: "Base geográfica indisponível",
    INSUMO_SUSPEITO: "Base geográfica com indício de lacuna",
    METRICA_INSUFICIENTE: ("Só foi possível realizar a medição da distância em "
                           "linha reta, insuficiente para aprovação"),
    AGREGACAO_INDECISA: "Alternativas inconclusivas",
    MEMBRO_NAO_EXECUTADO: "Alternativa do requisito não executada",
    MAPEAMENTO_PENDENTE: "Camada enviada sem classificação dos atributos",
    PORTE_INDETERMINADO: "População do município indisponível",
    VERIFICACAO_EM_CAMPO: "Depende de vistoria in loco",
    ANALISE_HUMANA_DOCUMENTAL: "Depende de parecer do analista",
    ERRO_DE_EXECUCAO: "Falha na execução da checagem",
    INCONSISTENCIA_DECLARATORIA: "Números declarados se contradizem",
    INSUMO_DO_PROPONENTE_AUSENTE: ("Falta disponibilizar o modelo IFC ou "
                                   "declaração do proponente para a checagem"),
}

# O que o usuário pode fazer para destravar cada motivo (texto de interface,
# ADR-034: sem caminho de arquivo nem comando).
ACAO = {
    INFORMACAO_AUSENTE: ("O modelo deve ser revisado e entregue com as "
                         "informações necessárias para a checagem."),
    TERRENO_AUSENTE: "Defina o terreno na tela de checagem.",
    TERRENO_INSUFICIENTE: ("Informe a poligonal do terreno por algum método "
                           "que não seja baseado somente na indicação do "
                           "centro."),
    INSUMO_AUSENTE: "Forneça a base geográfica exigida.",
    INSUMO_SUSPEITO: ("Complemente o cadastro de equipamentos; a base "
                      "automática parece incompleta para este município."),
    METRICA_INSUFICIENTE: ("Configure o serviço de cálculo da distância "
                           "caminhável, que permite avaliar o trajeto a pé. "
                           "A distância em linha reta só permite reprovar, "
                           "nunca aprovar."),
    # Só aparece quando os membros pendentes têm causas DIFERENTES — pendência
    # unânime é herdada pelo pai, para que a ação continue específica (ver
    # ``agregacao.RegraAgregacao._motivo``). Daí a ação aqui remeter à lista de
    # membros em vez de nomear um insumo: são vários, e cada um pede outra coisa.
    AGREGACAO_INDECISA: "Veja, no relatório do requisito, o que falta em cada "
                        "alternativa — elas travam por motivos diferentes.",
    MEMBRO_NAO_EXECUTADO: "Esta alternativa ainda não é verificada pelo protótipo.",
    MAPEAMENTO_PENDENTE: "Classifique os valores dos atributos da camada.",
    # Município não declarado é INSUMO_DO_PROPONENTE_AUSENTE (ADR-033); este
    # motivo fica só para o município sem população no Censo 2022 (ADR-030).
    PORTE_INDETERMINADO: ("Município criado depois do Censo 2022 não tem "
                          "população publicada, e o porte não é estimado. A "
                          "verificação fica para o analista."),
    VERIFICACAO_EM_CAMPO: ("Recomenda-se que seja realizada vistoria in loco "
                           "de enquadramento."),
    ANALISE_HUMANA_DOCUMENTAL: ("Recomenda-se análise detalhada de um analista "
                                "técnico."),
    INCONSISTENCIA_DECLARATORIA: ("Corrija em Informações Gerais: dois números "
                                  "declarados se contradizem, e o resultado não "
                                  "escolhe entre eles."),
    INSUMO_DO_PROPONENTE_AUSENTE: ("Envie o modelo IFC na tela de checagem ou "
                                   "complete Informações Gerais, conforme a "
                                   "mensagem."),
    ERRO_DE_EXECUCAO: ("Rode a checagem de novo; se a falha persistir, é "
                       "defeito do protótipo a corrigir."),
}


def rotulo(motivo: str) -> str:
    return ROTULO.get(motivo, motivo or "")
