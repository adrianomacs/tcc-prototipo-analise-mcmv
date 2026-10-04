"""Checagem — Georreferenciamento (EMP-001): "o arquivo enviado contém:"
(ADR-023).

`AppTest` da página de verdade, cobrindo só o que mudou nesta fase — o
seletor que diz, de uma vez, o que o arquivo contém (a natureza, condição de
contorno das regras) e de quem ele é (o alvo, ADR-023) — para os cenários que
ele trata de formas diferentes: sem nada declarado, com unidades tipo, e com
edificações físicas. O smoke-test genérico ("a árvore inteira não quebra") já
está em `test_paginas_renderizam.py`; aqui o interesse é o CONTEÚDO do
seletor.

Isolado de `artefatos/` real via `app.servicos.empreendimento.ARTEFATOS`
apontado para `tmp_path` — mesmo cuidado de `test_informacoes_gerais.py`.
"""

from __future__ import annotations

import importlib
import os

import pytest

pytest.importorskip("streamlit", reason="sem Streamlit não há o que renderizar")
pytestmark = pytest.mark.interface

from streamlit.testing.v1 import AppTest

from app.servicos import analise
from app.servicos import empreendimento as emp_mod
from core.dominio.edificacao import Edificacao
from core.dominio.empreendimento import Empreendimento
from core.dominio.unidade_tipo import UnidadeTipo
from core.dominio.vocabulario import declaracoes as dec
from tests.conftest import RAIZ

CAMINHO_PAGINA = os.path.join(
    RAIZ, "app", "paginas", "checagens", "checagem_georreferenciamento.py")


def _rodar(tmp_path, monkeypatch, emp: Empreendimento) -> AppTest:
    monkeypatch.setattr(emp_mod, "ARTEFATOS", str(tmp_path))
    emp_mod.gravar(emp)
    at = AppTest.from_file(CAMINHO_PAGINA)
    at.run(timeout=60)
    assert not at.exception
    return at


def _seletor(at):
    return at.selectbox(key="alvo__georref")


def test_sem_nada_declarado_so_oferece_terreno_e_todas(tmp_path, monkeypatch):
    at = _rodar(tmp_path, monkeypatch, Empreendimento())

    assert _seletor(at).options == ["Terreno", "Terreno com as edificações"]
    textos = [c.value for c in at.caption]
    assert any("Nenhuma unidade tipo ou edificação declarada" in t
               for t in textos), textos


def test_o_default_continua_sendo_o_modelo_federado(tmp_path, monkeypatch):
    """Era o default antes da R2 (índice 2 de três naturezas) e é o do fluxo
    dourado — mudá-lo mudaria silenciosamente o que o autor analisa."""
    emp = Empreendimento(unidades_tipo=[UnidadeTipo(nome="Casa padrão")])
    at = _rodar(tmp_path, monkeypatch, emp)

    assert _seletor(at).value == "Terreno com as edificações"


def test_unidades_tipo_e_edificacoes_entram_por_nome(tmp_path, monkeypatch):
    tipo = UnidadeTipo(nome="Casa padrão", unidades=10, tipologia=dec.CASA)
    emp = Empreendimento(unidades_tipo=[tipo],
                         edificacoes=[Edificacao(nome="Torre A",
                                                 composicao={tipo.id: 10})])
    at = _rodar(tmp_path, monkeypatch, emp)

    assert _seletor(at).options == [
        "Terreno",
        "Terreno com as edificações",
        "Casa padrão — unidade tipo isolada",
        "Torre A — edificação isolada",
    ]


def test_entidade_sem_nome_aparece_como_sem_nome(tmp_path, monkeypatch):
    emp = Empreendimento(unidades_tipo=[UnidadeTipo(nome="")])
    at = _rodar(tmp_path, monkeypatch, emp)

    assert "(sem nome) — unidade tipo isolada" in _seletor(at).options


def test_escolher_a_unidade_tipo_isolada_nao_lanca_excecao(tmp_path, monkeypatch):
    emp = Empreendimento(unidades_tipo=[UnidadeTipo(nome="A"),
                                        UnidadeTipo(nome="B")])
    at = _rodar(tmp_path, monkeypatch, emp)

    at = _seletor(at).set_value("B — unidade tipo isolada").run(timeout=60)
    assert not at.exception
    assert _seletor(at).value == "B — unidade tipo isolada"


def test_os_rotulos_isolados_traduzem_a_natureza_de_hoje(tmp_path, monkeypatch):
    """Nenhum valor novo entrou no vocabulário de `natureza` (ADR-023): o que
    distingue "unidade tipo isolada" de "edificação isolada" é o DONO, não o
    conteúdo do arquivo — as duas são `edificacao_isolada`."""
    tipo = UnidadeTipo(nome="Casa padrão")
    emp = Empreendimento(unidades_tipo=[tipo],
                         edificacoes=[Edificacao(nome="Torre A",
                                                 composicao={tipo.id: 1})])
    # A página é um script que roda `main()` ao ser importada: o `ARTEFATOS`
    # apontado para `tmp_path` antes do import é o que a mantém longe do
    # artefato real (mesmo cuidado de `_rodar`).
    monkeypatch.setattr(emp_mod, "ARTEFATOS", str(tmp_path))
    emp_mod.gravar(emp)
    pagina = importlib.import_module(
        "app.paginas.checagens.checagem_georreferenciamento")
    opcoes = pagina._opcoes(emp)

    assert opcoes["Terreno"] == (dec.TERRENO, analise.ALVO_TERRENO)
    assert opcoes["Terreno com as edificações"] == (
        dec.TERRENO_COM_EDIFICACOES, analise.ALVO_TODAS)
    assert opcoes["Casa padrão — unidade tipo isolada"] == (
        dec.EDIFICACAO_ISOLADA, analise.alvo_de_unidade_tipo(tipo.id))
    assert opcoes["Torre A — edificação isolada"][0] == dec.EDIFICACAO_ISOLADA
