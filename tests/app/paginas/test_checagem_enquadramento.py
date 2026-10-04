"""Checagem — Enquadramento: o modo único de ponto (clique + coordenadas).

`AppTest` da página de verdade, com o componente de mapa trocado por um falso
que devolve o payload que o teste mandar — o clique num mapa Leaflet não existe
fora do navegador, mas o que a página faz com o ``last_clicked`` que ele
devolve é Python e se prova aqui. O smoke-test genérico da página está em
`test_paginas_renderizam.py`; o interesse aqui é o **contrato do modo**: o
clique preenche latitude e longitude, o ajuste à mão vale mais que um clique
velho que o mapa continua devolvendo a cada reexecução, e confirmar grava um
terreno-ponto declarado.

Isolado de `artefatos/` real via `app.servicos.empreendimento.ARTEFATOS`
apontado para `tmp_path`, como os demais testes de página.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("streamlit", reason="sem Streamlit não há o que renderizar")
pytestmark = pytest.mark.interface

from streamlit.testing.v1 import AppTest

from app.componentes import mapa as mapa_mod
from app.servicos import empreendimento as emp_mod
from tests.conftest import RAIZ

CAMINHO_PAGINA = os.path.join(
    RAIZ, "app", "paginas", "checagens", "checagem_enquadramento.py")

ROTULO_PONTO = "Marcar o centro no mapa"
CHAVE_LAT = "lat__enquadramento"
CHAVE_LON = "lon__enquadramento"

CLIQUE_A = {"lat": -29.500001, "lng": -51.960002}
CLIQUE_B = {"lat": -29.511111, "lng": -51.971111}


class MapaFalso:
    """Substitui ``app.componentes.mapa.mapa``: registra como foi chamado e
    devolve o ``last_clicked`` que o teste pôs em ``clique``."""

    def __init__(self) -> None:
        self.clique: dict | None = None
        self.chamadas: list[dict] = []

    def __call__(self, **kwargs):
        self.chamadas.append(kwargs)
        return {"last_clicked": self.clique} if self.clique else None


@pytest.fixture
def mapa_falso(tmp_path, monkeypatch) -> MapaFalso:
    monkeypatch.setattr(emp_mod, "ARTEFATOS", str(tmp_path))
    falso = MapaFalso()
    monkeypatch.setattr(mapa_mod, "mapa", falso)
    return falso


def _no_modo_de_ponto() -> AppTest:
    at = AppTest.from_file(CAMINHO_PAGINA)
    at.run(timeout=60)
    at.radio(key="modo__enquadramento").set_value(ROTULO_PONTO).run(timeout=60)
    assert not at.exception
    return at


def _botoes(at, rotulo: str):
    return [b for b in at.button if b.label == rotulo]


def test_sao_quatro_modos_e_os_dois_de_ponto_viraram_um():
    at = AppTest.from_file(CAMINHO_PAGINA)
    at.run(timeout=60)
    opcoes = list(at.radio(key="modo__enquadramento").options)
    assert opcoes == ["Desenhar a poligonal no mapa", "Enviar o modelo IFC",
                      "Importar CSV da poligonal do terreno", ROTULO_PONTO]


def test_sem_clique_nao_ha_ponto_a_confirmar(mapa_falso):
    at = _no_modo_de_ponto()

    # Os campos existem, para o usuário poder digitar, mas o valor-padrão
    # (centro do município) não é um ponto escolhido: nada de confirmar.
    assert at.number_input(key=CHAVE_LAT) is not None
    assert not _botoes(at, "Confirmar terreno")
    ultima = mapa_falso.chamadas[-1]
    assert ultima["modo"] == "clicar"
    assert ultima["terreno"] is None


def test_o_clique_preenche_os_campos_e_o_marcador_vai_ao_ponto(mapa_falso):
    at = _no_modo_de_ponto()

    mapa_falso.clique = CLIQUE_A
    at.run(timeout=60)

    assert not at.exception
    assert at.number_input(key=CHAVE_LAT).value == pytest.approx(-29.5, abs=1e-5)
    assert at.number_input(key=CHAVE_LON).value == pytest.approx(-51.96, abs=1e-5)
    assert _botoes(at, "Confirmar terreno")
    ultima = mapa_falso.chamadas[-1]
    assert ultima["terreno"].centro_wgs84 == pytest.approx((-29.5, -51.96), abs=1e-5)


def test_ajuste_a_mao_vale_mais_que_o_clique_velho(mapa_falso):
    at = _no_modo_de_ponto()
    mapa_falso.clique = CLIQUE_A
    at.run(timeout=60)

    # O mapa segue devolvendo o mesmo clique a cada reexecução; o valor
    # digitado depois não pode ser sobrescrito por ele.
    at.number_input(key=CHAVE_LAT).set_value(-29.6).run(timeout=60)

    assert not at.exception
    assert at.number_input(key=CHAVE_LAT).value == pytest.approx(-29.6)
    assert mapa_falso.chamadas[-1]["terreno"].centro_wgs84[0] == pytest.approx(-29.6)


def test_clique_novo_depois_do_ajuste_sobrescreve_os_campos(mapa_falso):
    at = _no_modo_de_ponto()
    mapa_falso.clique = CLIQUE_A
    at.run(timeout=60)
    at.number_input(key=CHAVE_LAT).set_value(-29.6).run(timeout=60)

    mapa_falso.clique = CLIQUE_B
    at.run(timeout=60)

    assert at.number_input(key=CHAVE_LAT).value == pytest.approx(-29.511111, abs=1e-5)
    assert at.number_input(key=CHAVE_LON).value == pytest.approx(-51.971111, abs=1e-5)


def test_digitar_sem_clicar_tambem_define_o_ponto(mapa_falso):
    at = _no_modo_de_ponto()

    at.number_input(key=CHAVE_LAT).set_value(-29.7).run(timeout=60)

    assert _botoes(at, "Confirmar terreno")
    assert mapa_falso.chamadas[-1]["terreno"] is not None


def test_confirmar_grava_terreno_ponto_declarado(mapa_falso):
    at = _no_modo_de_ponto()
    mapa_falso.clique = CLIQUE_A
    at.run(timeout=60)
    at.number_input(key=CHAVE_LON).set_value(-51.95).run(timeout=60)

    (botao,) = _botoes(at, "Confirmar terreno")
    at = botao.click().run(timeout=60)

    assert not at.exception
    terreno = emp_mod.carregar().terreno
    assert terreno is not None
    assert terreno.nivel == "ponto"
    assert terreno.origem == "ponto"
    assert terreno.precisao == "declarada"
    assert terreno.centro_wgs84 == pytest.approx((-29.5, -51.95), abs=1e-5)
    # o estado do modo não vaza para a próxima definição de terreno
    assert "ponto__enquadramento" not in at.session_state
    assert "clique__enquadramento" not in at.session_state
