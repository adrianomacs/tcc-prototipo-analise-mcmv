"""`regra_do_grupo` — a linha que o "O que esta regra verifica" do relatório
mostra (ADR-034) — e `situacao_no_empreendimento`, o roteiro da página
"Requisitos a serem validados"."""

from __future__ import annotations

from app.servicos import grupos


def test_acha_o_requisito_e_o_grupo_dele():
    achado = grupos.regra_do_grupo("ENQ-009")
    assert achado is not None
    grupo, regra = achado
    assert grupo.id == "enquadramento" and regra.id == "ENQ-009"


def test_requisito_desconhecido_devolve_none():
    assert grupos.regra_do_grupo("NAO-EXISTE") is None


def _situacoes(gid: str, declaracoes: dict) -> dict[str, str]:
    grupo = grupos.carregar_grupo(gid)
    return {r.id: s for r, s in grupos.situacao_no_empreendimento(grupo, declaracoes)}


def test_apartamento_deixa_de_fora_so_o_requisito_de_casas():
    sit = _situacoes("programa_necessidades", {"tipologia": "apartamento"})
    assert sit["EDI-001"] == "Não se aplica, só a casas"
    assert sit["EDI-002"] == grupos.SERA_VERIFICADO


def test_casa_deixa_de_fora_os_requisitos_de_apartamento():
    sit = _situacoes("programa_necessidades", {"tipologia": "casa"})
    assert sit["EDI-002"] == "Não se aplica, só a apartamentos"
    assert sit["EDI-001"] == grupos.SERA_VERIFICADO


def test_membro_de_agregacao_nao_aparece_a_parte():
    sit = _situacoes("enquadramento", {})
    assert set(sit) == {"ENQ-009", "ENQ-010", "ENQ-011"}

