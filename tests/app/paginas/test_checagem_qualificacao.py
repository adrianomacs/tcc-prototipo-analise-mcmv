"""Checagem — Qualificação Urbanística (GIS): o painel do porte.

`AppTest` da página de verdade, no molde de `test_checagem_bim_gis.py`: o
relatório é o que as três regras do EMP-025 gravam, posto em disco em
`artefatos/relatorios/qualificacao.json` (ADR-001) e na sessão.
"""

from __future__ import annotations

import json
import os

import pytest

pytest.importorskip("streamlit", reason="sem Streamlit não há o que renderizar")
pytestmark = pytest.mark.interface

from streamlit.testing.v1 import AppTest

from app.estado import chaves
from app.servicos import empreendimento as emp_mod
from app.servicos import relatorios
from core.dominio.empreendimento import Empreendimento
from tests.app.servicos.test_qualificacao import _relatorio
from tests.conftest import RAIZ

CAMINHO_PAGINA = os.path.join(
    RAIZ, "app", "paginas", "checagens", "checagem_qualificacao.py")


@pytest.fixture
def pasta_rel(tmp_path, monkeypatch):
    monkeypatch.setattr(emp_mod, "ARTEFATOS", str(tmp_path))
    pasta = tmp_path / "relatorios"
    pasta.mkdir()
    monkeypatch.setattr(relatorios, "PASTA_RELATORIOS", str(pasta))
    return pasta


def _abrir(emp: Empreendimento, relatorio: dict | None = None,
           pasta=None) -> AppTest:
    emp_mod.gravar(emp)
    at = AppTest.from_file(CAMINHO_PAGINA)
    if relatorio is not None:
        (pasta / "qualificacao.json").write_text(json.dumps(relatorio),
                                                 encoding="utf-8")
        at.session_state[chaves.chave_relatorio("qualificacao")] = relatorio
    at.run(timeout=60)
    assert not at.exception
    return at


def test_sem_analise_avisa_o_que_falta_e_nao_pergunta_porte(pasta_rel):
    at = _abrir(Empreendimento())
    avisos = " ".join(w.value for w in at.warning)
    assert "Município ainda não declarado" in avisos
    assert "UH previstas" in avisos
    # Derivado, nunca declarado (ADR-030): nenhum campo de porte ou população.
    rotulos = [s.label for s in at.selectbox] + [n.label for n in at.number_input]
    assert not [r for r in rotulos if "porte" in r.lower() or "popula" in r.lower()]
    assert any(b.label == "Analisar" for b in at.button)
    assert "O que o porte do município decidiu" not in [s.value for s in at.subheader]


def test_com_analise_o_resultado_nao_repete_o_relatorio(pasta_rel):
    """O painel do porte saiu (ADR-034): depois de analisar, a tela mostra o
    resultado comum com o acesso ao relatório do EMP-025, e não um segundo
    quadro com população, faixa e limites."""
    at = _abrir(Empreendimento(), _relatorio(300), pasta_rel)
    textos = [m.value for m in at.markdown] + [s.value for s in at.subheader]
    assert not any("O que o porte do município decidiu" in t for t in textos)
    assert "População (Censo 2022)" not in [m.label for m in at.metric]
    assert any(b.label == "Nova análise" for b in at.button)
