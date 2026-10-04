"""Relatório do EMP-001 (ADR-034): os textos puros da página."""

from __future__ import annotations

import pytest

pytest.importorskip("streamlit")

from app.componentes import relatorio_georref as g  # noqa: E402
from app.componentes.avisos import ALERTA, ORIENTACAO  # noqa: E402


def _degraus(ate: int) -> list[dict]:
    return [{"nivel": n, "presente": n <= ate, "rotulo": f"r{n}"}
            for n in (10, 20, 30, 40, 50)]


def _detalhe(nivel=40, pos=None, declarada=None) -> dict:
    return {"nivel": nivel, "alvo": 50, "degraus": _degraus(nivel),
            "posicionamento_terreno": pos or {},
            "localizacao_declarada": declarada or {}}


_ESTRELA = {"municipio": "Estrela", "uf": "RS", "avaliado": True}


def test_contexto_cita_a_referencia_da_lista_do_tcc():
    assert "Clemen e Görne (2019)" in g.CONTEXTO_LOGEOREF


def test_criterio_traz_exigido_e_medido():
    texto = g.criterio_logeoref(_detalhe(40, declarada=_ESTRELA))
    assert "nível 50" in texto and "dentro de Estrela/RS" in texto
    assert "<b>Medido:</b> nível 40." in texto


def test_criterio_so_mede_o_municipio_a_partir_do_alvo():
    fora = dict(_ESTRELA, dentro=False)
    assert "posição fora" not in g.criterio_logeoref(_detalhe(40, declarada=fora))
    assert "posição fora de Estrela/RS" in g.criterio_logeoref(
        _detalhe(50, declarada=fora))


def test_resultado_lista_o_que_tem_e_o_que_falta():
    texto = g.texto_resultado(_detalhe(40))
    assert "nível **40** de 50" in texto
    assert "o endereço postal" in texto
    assert "falta o sistema de coordenadas projetado" in texto


def test_resultado_no_alvo():
    assert "atinge o nível **50**" in g.texto_resultado(_detalhe(50))


def test_ancora_fora_do_terreno_vira_alerta_na_faixa():
    pos = {"estado": "fora", "distancia_m": 11.73, "tolerancia_m": 5.0}
    avisos = g.avisos_emp001(_detalhe(50, pos=pos))
    assert [a.nivel for a in avisos] == [ALERTA]
    assert "11,73 m" in avisos[0].consequencia
    assert "não altera o resultado" in avisos[0].consequencia


def test_posicao_nao_conferida_so_orienta_no_alvo():
    pos = {"estado": "nao_avaliado", "motivo": "nenhum terreno declarado."}
    assert g.avisos_emp001(_detalhe(40, pos=pos)) == []
    avisos = g.avisos_emp001(_detalhe(50, pos=pos))
    assert [a.nivel for a in avisos] == [ORIENTACAO]


def test_municipio_divergente_abaixo_do_alvo_avisa_sem_mudar_o_veredito():
    fora = dict(_ESTRELA, dentro=False)
    avisos = g.avisos_emp001(_detalhe(40, declarada=fora))
    assert len(avisos) == 1 and "fora de Estrela/RS" in avisos[0].chave
    # No alvo o confronto é o veredito: mora no card, não na faixa.
    assert g.avisos_emp001(_detalhe(50, declarada=fora)) == []


def test_posicao_no_terreno_nao_fala_em_tipologia():
    texto = g.texto_posicao_no_terreno({"estado": "nao_aplicavel"})
    assert "unidade tipo" in texto and "tipologia" not in texto


def test_posicao_no_municipio_concorda_com_o_sujeito():
    aprox = dict(_ESTRELA, dentro=False, ancora={"modo": "aproximado"})
    assert "caem fora de Estrela/RS" in g.texto_posicao_no_municipio(aprox)
