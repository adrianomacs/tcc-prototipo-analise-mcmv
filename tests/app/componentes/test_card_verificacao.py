"""Card de verificação (ADR-034): o que ele carrega e o que ele escapa."""

from __future__ import annotations

from app.componentes.card_verificacao import montar_card
from app.componentes.paineis import COR_ESTADO
from app.servicos import motivos


def test_card_traz_id_estado_descricao_e_criterio():
    html = montar_card({"requisito": "ENQ-009", "estado": "nao_conforme",
                        "descricao": "Escola a até 1 km"}, {},
                       "<b>Exige:</b> 1.000 m")
    assert "ENQ-009 — Não conforme" in html
    assert "Escola a até 1 km" in html and "<b>Exige:</b> 1.000 m" in html
    assert COR_ESTADO["nao_conforme"] in html


def test_card_acrescenta_o_rotulo_do_motivo_quando_nao_avaliavel():
    motivo = motivos.VERIFICACAO_EM_CAMPO
    html = montar_card({"requisito": "X", "estado": "nao_avaliavel",
                        "descricao": "d"}, {motivos.CHAVE: motivo})
    assert motivos.rotulo(motivo) in html


def test_texto_do_requisito_e_escapado():
    html = montar_card({"requisito": "<i>", "estado": "conforme",
                        "descricao": "a < b"})
    assert "<i>" not in html and "a &lt; b" in html


def test_card_tem_margem_inferior_antes_do_contexto():
    assert "margin-bottom:" in montar_card({"requisito": "X", "estado": "conforme"})
