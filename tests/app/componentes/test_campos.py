"""Campo não editável (ADR-034): o que ele exibe quando não há valor."""

from __future__ import annotations

from app.componentes.campos import VAZIO, valor_exibido


def test_valor_ausente_vira_travessao_nunca_zero_nem_vazio():
    assert valor_exibido(None) == VAZIO
    assert valor_exibido("  ") == VAZIO


def test_valor_presente_e_exibido_como_texto():
    assert valor_exibido(300) == "300"
    assert valor_exibido("Estrela") == "Estrela"
