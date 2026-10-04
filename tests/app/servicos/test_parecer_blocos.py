"""Os blocos do Relatório de Checagem (2.4.2): o parágrafo de cada checagem
repartido em introdução e linhas por requisito, para a tela mostrar a tabela
(ADR-035). O texto do parecer não muda: `Parecer.texto()` segue o dos
parágrafos, coberto por `test_parecer.py`; aqui se confere que os blocos dizem
o mesmo que o parágrafo."""

from __future__ import annotations

from app.servicos import parecer


def _relatorio(linhas: list[dict]) -> dict:
    return {"meta": {}, "resumo": {}, "por_requisito": linhas, "por_elemento": {}}


def _linhas() -> list[dict]:
    return [
        {"requisito": "EDI-007", "descricao": "Largura mínima da cozinha",
         "estado": "conforme", "mensagem": "Largura de 1,90 m."},
        {"requisito": "EDI-009", "descricao": "Largura mínima do banheiro",
         "estado": "nao_conforme", "mensagem": "Largura de 1,40 m."},
        {"requisito": "EDI-008", "descricao": "Largura mínima da sala",
         "estado": "nao_avaliavel", "detalhe": {"motivo_nao_avaliavel": "informacao_ausente"},
         "mensagem": "Sem sala."},
    ]


def _bloco():
    p = parecer.montar({"programa": _relatorio(_linhas())}, dependencias={})
    assert len(p.blocos) == 1
    return p, p.blocos[0]


def test_bloco_segue_o_titulo_e_a_ordem_dos_paragrafos():
    p, bloco = _bloco()
    assert bloco.titulo == p.checagens[0][0]
    assert [linha.requisito for linha in bloco.linhas] == ["EDI-007", "EDI-009", "EDI-008"]


def test_introducao_anuncia_os_requisitos_e_e_parte_do_paragrafo():
    p, bloco = _bloco()
    assert bloco.introducao.endswith("Verificaram-se três requisitos:")
    # A introdução é o começo do parágrafo, sem a lista que a tabela substitui.
    assert p.checagens[0][1].startswith(bloco.introducao[:-1])


def test_linha_traz_estado_e_o_detalhe_do_paragrafo():
    p, bloco = _bloco()
    conforme, nao_conforme, aberto = bloco.linhas
    assert (conforme.estado, conforme.detalhe) == ("conforme", "Largura de 1,90 m")
    assert nao_conforme.estado == "nao_conforme"
    assert aberto.estado == "nao_avaliavel"
    # O motivo da taxonomia, e não o recurso de "motivo não declarado".
    assert aberto.detalhe == "Informação ausente no modelo"
    paragrafo = p.checagens[0][1]
    for linha in bloco.linhas:
        assert linha.detalhe[:1].lower() + linha.detalhe[1:] in paragrafo


def test_checagem_sem_requisito_verificado_fica_so_com_a_introducao():
    p = parecer.montar({"programa": _relatorio([])}, dependencias={})
    bloco = p.blocos[0]
    assert bloco.linhas == ()
    assert bloco.introducao == p.checagens[0][1]
