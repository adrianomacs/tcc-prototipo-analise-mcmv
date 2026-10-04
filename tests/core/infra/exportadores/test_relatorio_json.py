"""Conformidade e cobertura do resumo do relatório.

Os dois números (conformidade e cobertura) contam **requisitos da Portaria**, não linhas
executadas. O que estes testes prendem:

1. **Que o membro de uma agregação sai do denominador.** Contar pai e filho conta
   a mesma evidência duas vezes, e as alternativas remetidas a parecer travariam a
   cobertura para sempre num teto que descreve a norma, não a ferramenta.
2. **Que "ter pai na planilha" não é o critério** — EDI-004.1 tem pai e não é
   agregado por ninguém; ele conta.
3. **Que a informação sai dos próprios resultados**, sem registro de regras nem
   arquivo de configuração.
4. **Que conformidade é `None`, não 0%, quando nada foi avaliado.**
"""

from __future__ import annotations

import json

from core.dominio.contratos.regra import Estado, Resultado
from core.infra.exportadores import relatorio_json
from core.regras.base import agregacao as ag


def _r(rid, estado, **detalhe) -> Resultado:
    return Resultado(regra_id=rid, estado=estado, detalhe=dict(detalhe))


def _pai(rid, membros_estados: dict[str, Estado], estado) -> Resultado:
    """Resultado de agregação com o `detalhe` no formato que a regra produz."""
    return _r(rid, estado,
              tipo=ag.TIPO_DIAGNOSTICO,
              membros=[{"id": mid, "estado": e.value} for mid, e in
                       membros_estados.items()])


# ---------------------------------------------------------------------------
# 1. Sem agregação: os dois universos coincidem
# ---------------------------------------------------------------------------

def test_sem_agregacao_o_nivel_normativo_e_o_conjunto_inteiro():
    """Grupos sem pai (Programa de necessidades) ganham os números de graça."""
    resultados = {
        "EDI-004": _r("EDI-004", Estado.CONFORME),
        "EDI-007": _r("EDI-007", Estado.NAO_CONFORME),
        "EDI-008": _r("EDI-008", Estado.NAO_AVALIAVEL),
    }
    resumo = relatorio_json.montar(resultados)["resumo"]
    assert resumo["normativo"]["total"] == 3
    assert resumo["normativo"]["membros"] == []
    assert resumo["conformidade"] == 0.5      # 1 conforme de 2 avaliados
    assert round(resumo["cobertura"], 4) == 0.6667


def test_pai_da_planilha_que_nao_agrega_continua_contando():
    """EDI-004.1 tem `Grupo (pai)` = EDI-004 e NÃO é membro de agregação nenhuma.

    A atomização do EDI-004 o tornou requisito independente, com
    veredito próprio. O critério do denominador é *ser membro de uma agregação*,
    não *ter pai temático na planilha* — se fosse o segundo, este requisito
    desapareceria da conta sem nunca ter sido agregado por ninguém.
    """
    resultados = {
        "EDI-004": _r("EDI-004", Estado.CONFORME),
        "EDI-004.1": _r("EDI-004.1", Estado.NAO_CONFORME),
    }
    resumo = relatorio_json.montar(resultados)["resumo"]
    assert resumo["normativo"]["total"] == 2
    assert "EDI-004.1" in resumo["normativo"]["ids"]


# ---------------------------------------------------------------------------
# 2. Com agregação: o cenário real do R6a
# ---------------------------------------------------------------------------

def _cenario_enquadramento() -> dict[str, Resultado]:
    """O cenário validado em Estrela: 009 reprova, 010 aprova, 011 indeciso."""
    return {
        "ENQ-009": _r("ENQ-009", Estado.NAO_CONFORME),
        "ENQ-010": _pai("ENQ-010", {"ENQ-010.1": Estado.CONFORME,
                                    "ENQ-010.2": Estado.NAO_AVALIAVEL},
                        Estado.CONFORME),
        "ENQ-010.1": _r("ENQ-010.1", Estado.CONFORME),
        "ENQ-010.2": _r("ENQ-010.2", Estado.NAO_AVALIAVEL),
        "ENQ-011": _pai("ENQ-011", {"ENQ-011.1": Estado.NAO_CONFORME,
                                    "ENQ-011.2": Estado.NAO_AVALIAVEL},
                        Estado.NAO_AVALIAVEL),
        "ENQ-011.1": _r("ENQ-011.1", Estado.NAO_CONFORME),
        "ENQ-011.2": _r("ENQ-011.2", Estado.NAO_AVALIAVEL),
    }


def test_membros_saem_do_denominador():
    resumo = relatorio_json.montar(_cenario_enquadramento())["resumo"]
    norm = resumo["normativo"]
    assert norm["ids"] == ["ENQ-009", "ENQ-010", "ENQ-011"]
    assert norm["membros"] == ["ENQ-010.1", "ENQ-010.2",
                              "ENQ-011.1", "ENQ-011.2"]
    assert norm["total"] == 3


def test_os_dois_numeros_do_cenario_real():
    """ENQ-009 não conforme, ENQ-010 conforme, ENQ-011 indeciso."""
    resumo = relatorio_json.montar(_cenario_enquadramento())["resumo"]
    assert resumo["conformidade"] == 0.5        # 1 de 2 avaliados
    assert round(resumo["cobertura"], 4) == 0.6667   # 2 de 3 requisitos


def test_as_contagens_por_estado_seguem_descrevendo_as_LINHAS():
    """Elas têm de fechar com a tabela da tela, que lista as sete verificações."""
    resumo = relatorio_json.montar(_cenario_enquadramento())["resumo"]
    assert resumo["total_requisitos"] == 7
    assert resumo["conforme"] == 2 and resumo["nao_conforme"] == 2
    assert resumo["nao_avaliavel"] == 3


def test_cobertura_nao_e_avaliados_sobre_total_de_linhas():
    """A armadilha de leitura que o docstring de `_resumo` avisa.

    4/7 = 0,5714 é o número ERRADO — e é o que o resumo produzia antes do R6b.
    """
    resumo = relatorio_json.montar(_cenario_enquadramento())["resumo"]
    errado = round(resumo["avaliados"] / resumo["total_requisitos"], 4)
    assert errado == 0.5714
    assert resumo["cobertura"] != errado


def test_alternativa_remetida_nao_trava_a_cobertura_de_um_terreno_bom():
    """O teto que o denominador errado criava: 5/7 para sempre.

    Aqui os três requisitos da Portaria têm veredito — dois conformes e um não
    conforme —, e as duas alternativas remetidas seguem não avaliáveis. A
    cobertura tem de ser 100%: nada do que a norma exige ficou sem resposta.
    """
    resultados = {
        "ENQ-009": _r("ENQ-009", Estado.CONFORME),
        "ENQ-010": _pai("ENQ-010", {"ENQ-010.1": Estado.CONFORME,
                                    "ENQ-010.2": Estado.NAO_AVALIAVEL},
                        Estado.CONFORME),
        "ENQ-010.1": _r("ENQ-010.1", Estado.CONFORME),
        "ENQ-010.2": _r("ENQ-010.2", Estado.NAO_AVALIAVEL),
        "ENQ-011": _pai("ENQ-011", {"ENQ-011.1": Estado.NAO_CONFORME,
                                    "ENQ-011.2": Estado.NAO_AVALIAVEL},
                        Estado.NAO_CONFORME),
        "ENQ-011.1": _r("ENQ-011.1", Estado.NAO_CONFORME),
        "ENQ-011.2": _r("ENQ-011.2", Estado.NAO_AVALIAVEL),
    }
    resumo = relatorio_json.montar(resultados)["resumo"]
    assert resumo["cobertura"] == 1.0
    assert round(resumo["conformidade"], 4) == 0.6667   # 2 de 3
    # Pelo denominador antigo, a mesma análise leria 5/7.
    assert round(resumo["avaliados"] / resumo["total_requisitos"], 4) == 0.7143


# ---------------------------------------------------------------------------
# 3. Bordas
# ---------------------------------------------------------------------------

def test_conformidade_e_None_quando_nada_foi_avaliado():
    """0% afirmaria "nenhum conforme" sobre um conjunto vazio."""
    resultados = {"ENQ-009": _r("ENQ-009", Estado.NAO_AVALIAVEL)}
    resumo = relatorio_json.montar(resultados)["resumo"]
    assert resumo["conformidade"] is None
    assert resumo["cobertura"] == 0.0


def test_resumo_vazio_nao_estoura():
    resumo = relatorio_json.montar({})["resumo"]
    assert resumo["normativo"]["total"] == 0
    assert resumo["conformidade"] is None
    assert resumo["cobertura"] == 0.0


def test_a_informacao_do_denominador_viaja_no_json():
    """O resumo se explica a partir do relatório salvo, sem o registro de regras.

    `membros` sai do `detalhe` dos próprios resultados, então quem lê o
    `relatorio.json` amanhã consegue refazer a conta — mesma propriedade que o
    R5d deu ao relatório das ENQ.
    """
    relatorio = relatorio_json.montar(_cenario_enquadramento())
    salvo = json.loads(json.dumps(relatorio, ensure_ascii=False))
    pais = [r for r in salvo["por_requisito"]
            if (r.get("detalhe") or {}).get("tipo") == ag.TIPO_DIAGNOSTICO]
    membros = {m["id"] for p in pais for m in p["detalhe"]["membros"]}
    assert membros == set(salvo["resumo"]["normativo"]["membros"])


# ---------------------------------------------------------------------------
# 4. Agrupamento por requisito da Portaria
# ---------------------------------------------------------------------------

def test_agrupar_traz_as_alternativas_dentro_do_pai():
    relatorio = relatorio_json.montar(
        _cenario_enquadramento(),
        ordem_exibicao=["ENQ-009", "ENQ-010", "ENQ-010.1", "ENQ-010.2",
                        "ENQ-011", "ENQ-011.1", "ENQ-011.2"])
    grupos = relatorio_json.agrupar(relatorio)

    assert [g["requisito"]["requisito"] for g in grupos] == \
        ["ENQ-009", "ENQ-010", "ENQ-011"]
    assert [m["requisito"] for m in grupos[1]["membros"]] == \
        ["ENQ-010.1", "ENQ-010.2"]
    assert grupos[0]["membros"] == []      # ENQ-009 não agrega ninguém


def test_agrupar_tem_a_mesma_unidade_do_denominador():
    """A tela e os dois números passam a contar a mesma coisa.

    Se divergirem, a tabela lista sete linhas ao lado de uma cobertura calculada
    sobre três, e o leitor soma as colunas erradas.
    """
    relatorio = relatorio_json.montar(_cenario_enquadramento())
    grupos = relatorio_json.agrupar(relatorio)
    assert len(grupos) == relatorio["resumo"]["normativo"]["total"]
    assert [g["requisito"]["requisito"] for g in grupos] == \
        relatorio["resumo"]["normativo"]["ids"]


def test_agrupar_preserva_a_ordem_de_exibicao():
    relatorio = relatorio_json.montar(
        _cenario_enquadramento(),
        ordem_exibicao=["ENQ-011", "ENQ-011.1", "ENQ-011.2", "ENQ-009"])
    grupos = relatorio_json.agrupar(relatorio)
    assert [g["requisito"]["requisito"] for g in grupos][:2] == \
        ["ENQ-011", "ENQ-009"]


def test_agrupar_sem_agregacao_e_uma_linha_por_requisito():
    resultados = {"EDI-004": _r("EDI-004", Estado.CONFORME),
                  "EDI-007": _r("EDI-007", Estado.NAO_CONFORME)}
    grupos = relatorio_json.agrupar(relatorio_json.montar(resultados))
    assert len(grupos) == 2
    assert all(g["membros"] == [] for g in grupos)


def test_agrupar_ignora_membro_ausente_do_relatorio():
    """Membro declarado e não executado não vira linha fantasma."""
    resultados = {
        "ENQ-010": _pai("ENQ-010", {"ENQ-010.1": Estado.CONFORME,
                                    "ENQ-010.2": Estado.NAO_AVALIAVEL},
                        Estado.CONFORME),
        "ENQ-010.1": _r("ENQ-010.1", Estado.CONFORME),
    }
    grupos = relatorio_json.agrupar(relatorio_json.montar(resultados))
    assert len(grupos) == 1
    assert [m["requisito"] for m in grupos[0]["membros"]] == ["ENQ-010.1"]


def test_agrupar_relatorio_vazio():
    assert relatorio_json.agrupar({}) == []
