"""ADR-023 (D-K) — ``meta.diagnosticos`` no relatório, e só onde deve.

O que estes testes prendem é o acoplamento entre o gate e a EXECUÇÃO: a chave
aparece quando as regras executadas leem UH, e não quando a tela pediu que
lessem. As duas coisas divergem — o executor puxa dependências que ninguém
selecionou —, e é a execução que diz o que foi de fato lido.

O outro ponto é negativo e vale contra a linha de base do Estrela I: no
Georreferenciamento o relatório continua **sem a chave**, byte a byte o que
sempre foi. Um relatório que ganha chave nova sem ter o que pôr nela é uma
diferença a explicar a cada comparação futura.
"""

from __future__ import annotations

import json

import pytest

from core import composicao
from core.aplicacao import pipeline
from core.dominio.contratos.regra import Estado, Resultado
from core.dominio.empreendimento import Empreendimento
from core.dominio.modelo_bim import ModeloBIM
from core.dominio.unidade_tipo import UnidadeTipo
from core.dominio.vocabulario import declaracoes as dec


@pytest.fixture
def rodar_com(monkeypatch, tmp_path):
    """Roda o pipeline com um conjunto de resultados forjado, sem IFC nem GIS."""
    def _rodar(ids_executados, **kw):
        resultados = {id_regra: Resultado(regra_id=id_regra,
                                          estado=Estado.CONFORME)
                      for id_regra in ids_executados}
        monkeypatch.setattr(pipeline, "executar",
                            lambda ctx, ids_selecionados=None: resultados)
        monkeypatch.setattr(composicao, "_imprimir_resumo", lambda r: None)
        monkeypatch.setattr(composicao, "_carregar_config", lambda *a, **k: {
            "paths": {"relatorio": str(tmp_path / "r.json")}})
        composicao.rodar(**kw)
        return json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
    return _rodar


def _programa():
    """Um tipo de 150 UH com um contêiner que representa 1 — o caso 1 do §4."""
    conteiner = ModeloBIM(caminho="", natureza=dec.EDIFICACAO_ISOLADA,
                          unidades_representadas=1)
    tipo = UnidadeTipo(nome="Casa padrão", unidades=150, tipologia=dec.CASA,
                       modelo=conteiner)
    return Empreendimento(unidades_previstas=150, unidades_tipo=[tipo]), conteiner


def test_a_chave_aparece_na_analise_que_le_uh(rodar_com):
    emp, conteiner = _programa()
    relatorio = rodar_com(["EDI-004", "EDI-007"], empreendimento=emp,
                          conteiner=conteiner, ids_selecionados=[])
    diagnosticos = relatorio["meta"]["diagnosticos"]
    assert len(diagnosticos) == 5
    extrapolacao, = [d for d in diagnosticos if d["chave"] == "extrapolacao"]
    assert extrapolacao["marcado"]
    assert extrapolacao["valores"] == {"unidades_do_dono": 150,
                                       "unidades_representadas": 1}


def test_a_chave_nao_aparece_no_georreferenciamento(rodar_com):
    """EMP-001 não lê UH: o relatório continua o que sempre foi."""
    emp, conteiner = _programa()
    relatorio = rodar_com(["EMP-001"], empreendimento=emp, conteiner=conteiner,
                          ids_selecionados=[])
    assert "diagnosticos" not in relatorio["meta"]


def test_o_gate_le_o_executado_e_nao_o_selecionado(rodar_com):
    """O executor puxa dependências que ninguém selecionou; é o que rodou que
    decide."""
    emp, conteiner = _programa()
    relatorio = rodar_com(["EDI-002"], empreendimento=emp, conteiner=conteiner,
                          ids_selecionados=["EDI-007"])
    assert "diagnosticos" in relatorio["meta"]


def test_nenhum_diagnostico_vira_veredito(rodar_com):
    """D-K: marcam, não reprovam — o resumo não sabe que eles existem."""
    emp, conteiner = _programa()
    relatorio = rodar_com(["EDI-004"], empreendimento=emp, conteiner=conteiner,
                          ids_selecionados=[])
    assert any(d["marcado"] for d in relatorio["meta"]["diagnosticos"])
    assert relatorio["resumo"]["nao_conforme"] == 0
    assert relatorio["resumo"]["nao_avaliavel"] == 0
    assert [r["estado"] for r in relatorio["por_requisito"]] == ["conforme"]
