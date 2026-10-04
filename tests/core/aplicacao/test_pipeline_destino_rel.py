"""ADR-001 — `composicao.rodar(destino_rel=
...)`.

Único ponto do núcleo tocado aqui: cada checagem passa a poder gravar
o SEU relatório num caminho próprio, em vez de todas sobrescreverem
`artefatos/relatorio.json`. Critério de saída: `destino_rel`
sobrescreve o caminho de gravação quando informado, e o comportamento
default (sem o argumento) continua exatamente o de antes.
"""

from __future__ import annotations

import json

import pytest

from core import composicao
from core.dominio.empreendimento import Empreendimento


@pytest.fixture
def sem_regras(monkeypatch, tmp_path):
    """Contexto mínimo: sem IFC, sem regras selecionadas — `executar`
    devolve `{}` e `montar_contexto` não precisa de nenhuma fixture de
    equipamentos/rede. O que se testa aqui é só ONDE o relatório é gravado,
    não o conteúdo dele (já coberto por `test_pipeline_empreendimento.py`).
    """
    monkeypatch.setattr(
        composicao, "_carregar_config",
        lambda *a, **k: {"paths": {"relatorio": str(tmp_path / "relatorio.json"),
                                   "entradas_gis": str(tmp_path / "gis_vazio")}})
    monkeypatch.setattr(composicao, "_imprimir_resumo", lambda r: None)
    return tmp_path


def test_destino_rel_none_usa_o_caminho_padrao_do_config(sem_regras):
    tmp_path = sem_regras
    relatorio = composicao.rodar(empreendimento=Empreendimento(), ids_selecionados=[])

    padrao = tmp_path / "relatorio.json"
    assert padrao.is_file()
    gravado = json.loads(padrao.read_text(encoding="utf-8"))
    assert gravado["resumo"]["total_requisitos"] == relatorio["resumo"]["total_requisitos"]


def test_destino_rel_explicito_sobrescreve_o_caminho_e_nao_toca_o_padrao(sem_regras):
    tmp_path = sem_regras
    proprio = tmp_path / "relatorios" / "enquadramento.json"

    composicao.rodar(empreendimento=Empreendimento(), ids_selecionados=[],
                   destino_rel=str(proprio))

    assert proprio.is_file()
    assert not (tmp_path / "relatorio.json").exists(), (
        "destino_rel deveria substituir o caminho padrão, não gravar nos dois")


def test_destino_rel_cria_a_pasta_de_destino_se_nao_existir(sem_regras):
    tmp_path = sem_regras
    proprio = tmp_path / "relatorios" / "aninhado" / "georref.json"

    composicao.rodar(empreendimento=Empreendimento(), ids_selecionados=[],
                   destino_rel=str(proprio))

    assert proprio.is_file()


def test_duas_checagens_gravam_em_arquivos_separados(sem_regras):
    """O cenário real: duas checagens do MESMO empreendimento, em
    caminhos diferentes — nenhuma sobrescreve a outra."""
    tmp_path = sem_regras
    rel_enq = tmp_path / "relatorios" / "enquadramento.json"
    rel_geo = tmp_path / "relatorios" / "georref.json"
    emp = Empreendimento()

    r1 = composicao.rodar(empreendimento=emp, ids_selecionados=[], destino_rel=str(rel_enq))
    r2 = composicao.rodar(empreendimento=emp, ids_selecionados=[], destino_rel=str(rel_geo))

    assert rel_enq.is_file() and rel_geo.is_file()
    for r in (r1, r2):
        assert r["meta"]["empreendimento"] == emp.referencia()
