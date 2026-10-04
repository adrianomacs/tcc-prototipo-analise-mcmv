"""Checagem — Programa de necessidades: "as UHs deste arquivo são de:"
(ADR-023).

`AppTest` da página de verdade, cobrindo só o que mudou nesta fase — a antiga
"natureza do modelo" (sempre `dec.COM_EDIFICACAO` na prática, ver o cabeçalho
do módulo) virou a pergunta concreta de QUEM são as UHs, só exibida quando há
mais de um alvo possível — nos três cenários que o formulário trata de formas
diferentes: nenhum alvo, um só e vários. O smoke-test genérico já está em
`test_paginas_renderizam.py`; aqui o interesse é o CONTEÚDO do formulário.

Isolado de `artefatos/` real via `app.servicos.empreendimento.ARTEFATOS`
apontado para `tmp_path` — mesmo cuidado de `test_informacoes_gerais.py`.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("streamlit", reason="sem Streamlit não há o que renderizar")
pytestmark = pytest.mark.interface

from streamlit.testing.v1 import AppTest

from app.servicos import empreendimento as emp_mod
from core.dominio.edificacao import Edificacao
from core.dominio.empreendimento import Empreendimento
from core.dominio.unidade_tipo import UnidadeTipo
from core.dominio.vocabulario import declaracoes as dec
from tests.conftest import RAIZ

CAMINHO_PAGINA = os.path.join(
    RAIZ, "app", "paginas", "checagens", "checagem_programa.py")


def _rodar(tmp_path, monkeypatch, emp: Empreendimento) -> AppTest:
    monkeypatch.setattr(emp_mod, "ARTEFATOS", str(tmp_path))
    emp_mod.gravar(emp)
    at = AppTest.from_file(CAMINHO_PAGINA)
    at.run(timeout=60)
    assert not at.exception
    return at


def _seletores_de_alvo(at):
    return [s for s in at.selectbox if s.key == "alvo__programa"]


def test_sem_unidade_tipo_avisa_e_nao_mostra_seletor(tmp_path, monkeypatch):
    at = _rodar(tmp_path, monkeypatch, Empreendimento())

    assert not _seletores_de_alvo(at)
    avisos = [w.value for w in at.warning]
    assert any("Nenhuma unidade tipo declarada" in a for a in avisos), avisos


def test_uma_unidade_tipo_anexa_direto_sem_perguntar(tmp_path, monkeypatch):
    emp = Empreendimento(unidades_tipo=[UnidadeTipo(nome="Casa padrão")])
    at = _rodar(tmp_path, monkeypatch, emp)

    assert not _seletores_de_alvo(at)
    textos = [c.value for c in at.caption]
    assert any("será anexado a **Casa padrão (unidade tipo)**" in t
               for t in textos), textos


def test_varios_alvos_pergunta_por_nome(tmp_path, monkeypatch):
    padrao = UnidadeTipo(nome="Padrão", unidades=140, tipologia=dec.CASA)
    pcd = UnidadeTipo(nome="PCD", unidades=10, tipologia=dec.CASA)
    emp = Empreendimento(
        unidades_tipo=[padrao, pcd],
        edificacoes=[Edificacao(nome="Torre A",
                                composicao={padrao.id: 8, pcd.id: 2})])
    at = _rodar(tmp_path, monkeypatch, emp)

    (seletor,) = _seletores_de_alvo(at)
    assert seletor.label == "As UHs deste arquivo são de:"
    assert seletor.options == ["Padrão (unidade tipo)", "PCD (unidade tipo)",
                               "Torre A (edificação — arquivo misto)"]


def test_edificacao_sem_composicao_fica_de_fora(tmp_path, monkeypatch):
    """Dela a raiz não deriva tipologia nem UH: oferecê-la seria oferecer um
    dono do qual esta checagem não tem o que dizer (ADR-023)."""
    emp = Empreendimento(unidades_tipo=[UnidadeTipo(nome="Casa padrão")],
                         edificacoes=[Edificacao(nome="Torre vazia")])
    at = _rodar(tmp_path, monkeypatch, emp)

    assert not _seletores_de_alvo(at), "só há um alvo: a unidade tipo"
    textos = [c.value for c in at.caption]
    assert any("Casa padrão (unidade tipo)" in t for t in textos), textos


def test_numero_de_uhs_do_arquivo_comeca_em_um(tmp_path, monkeypatch):
    emp = Empreendimento(unidades_tipo=[UnidadeTipo(nome="Casa padrão")])
    at = _rodar(tmp_path, monkeypatch, emp)

    (numero,) = at.number_input
    assert numero.label == "Quantas UHs o modelo enviado representa?"
    assert numero.value == 1


def test_escolher_outro_alvo_no_seletor_nao_lanca_excecao(tmp_path, monkeypatch):
    emp = Empreendimento(unidades_tipo=[UnidadeTipo(nome="A"),
                                        UnidadeTipo(nome="B")])
    at = _rodar(tmp_path, monkeypatch, emp)

    (seletor,) = _seletores_de_alvo(at)
    at = seletor.set_value("B (unidade tipo)").run(timeout=60)
    assert not at.exception
    assert _seletores_de_alvo(at)[0].value == "B (unidade tipo)"


# --- Regressão observada em tela ------------------------------

def test_duas_unidades_tipo_com_tipologia_nao_acusam_falta_de_declaracao(
        tmp_path, monkeypatch):
    """A tipologia do aviso é a do ALVO escolhido, não uma dedução sobre o
    empreendimento inteiro: com duas unidades tipo, cada uma com a sua, a
    dedução devolve `""` — e o aviso acusava falta de declaração onde havia
    duas."""
    emp = Empreendimento(
        unidades_tipo=[UnidadeTipo(nome="Casa", tipologia=dec.CASA),
                       UnidadeTipo(nome="Apto", tipologia=dec.APARTAMENTO)],
        declaracoes={dec.ARRANJO: dec.LOTEAMENTO})
    at = _rodar(tmp_path, monkeypatch, emp)

    avisos = [w.value for w in at.warning]
    assert not any("ipologia" in a for a in avisos), avisos


def test_trocar_o_alvo_para_um_tipo_sem_tipologia_faz_o_aviso_voltar(
        tmp_path, monkeypatch):
    sem_tipologia = UnidadeTipo(nome="Sem tipologia")
    emp = Empreendimento(
        unidades_tipo=[UnidadeTipo(nome="Casa", tipologia=dec.CASA),
                       sem_tipologia],
        declaracoes={dec.ARRANJO: dec.LOTEAMENTO})
    at = _rodar(tmp_path, monkeypatch, emp)
    assert not [w for w in at.warning if "ipologia" in w.value]

    (seletor,) = _seletores_de_alvo(at)
    at = seletor.set_value("Sem tipologia (unidade tipo)").run(timeout=60)
    assert not at.exception
    avisos = [w.value for w in at.warning]
    assert any("ipologia" in a for a in avisos), avisos


# --- Heterogeneidade: o aviso ANTES de analisar (R3, ADR-023 D-K) ----------

def test_escolher_edificacao_mista_avisa_na_hora_da_escolha(tmp_path,
                                                            monkeypatch):
    """Caso 3 do §4: o autor compõe uma edificação com dois tipos, escolhe-a e
    tem de saber ali — antes de enviar arquivo — que o veredito será agregado.
    Até a R2 esse aviso só existia em `meta`, depois de analisar."""
    padrao = UnidadeTipo(nome="Apto padrão", unidades=100,
                         tipologia=dec.APARTAMENTO)
    pcd = UnidadeTipo(nome="Apto PCD", unidades=20, tipologia=dec.APARTAMENTO)
    emp = Empreendimento(
        unidades_tipo=[padrao, pcd],
        edificacoes=[Edificacao(nome="Torre A",
                                composicao={padrao.id: 50, pcd.id: 10})])
    at = _rodar(tmp_path, monkeypatch, emp)

    (seletor,) = _seletores_de_alvo(at)
    at = seletor.set_value("Torre A (edificação — arquivo misto)").run(timeout=60)
    assert not at.exception
    avisos = [w.value for w in at.warning]
    assert any("reúne 2 unidades tipo" in a
               for a in avisos), avisos


def test_caso_2_do_plano_nao_avisa_heterogeneidade(tmp_path, monkeypatch):
    """Um IFC por unidade tipo: cada análise é homogênea, e avisar seria ruído."""
    padrao = UnidadeTipo(nome="Casa padrão", unidades=140, tipologia=dec.CASA)
    pcd = UnidadeTipo(nome="Casa PCD", unidades=10, tipologia=dec.CASA)
    emp = Empreendimento(unidades_tipo=[padrao, pcd],
                         declaracoes={dec.ARRANJO: dec.LOTEAMENTO})
    at = _rodar(tmp_path, monkeypatch, emp)

    avisos = [w.value for w in at.warning]
    assert not any("Veredito agregado" in a for a in avisos), avisos


def test_edificacao_de_um_tipo_so_nao_avisa(tmp_path, monkeypatch):
    unico = UnidadeTipo(nome="Apto", unidades=100, tipologia=dec.APARTAMENTO)
    emp = Empreendimento(
        unidades_tipo=[unico],
        edificacoes=[Edificacao(nome="Torre", composicao={unico.id: 60})],
        declaracoes={dec.ARRANJO: dec.LOTEAMENTO})
    at = _rodar(tmp_path, monkeypatch, emp)

    (seletor,) = _seletores_de_alvo(at)
    at = seletor.set_value("Torre (edificação — arquivo misto)").run(timeout=60)
    assert not at.exception
    assert not any("Veredito agregado" in w.value for w in at.warning)
