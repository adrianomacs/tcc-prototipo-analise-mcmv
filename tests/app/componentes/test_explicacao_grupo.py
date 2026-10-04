"""Linha "Ao analisar, o protótipo verifica" (ADR-034, seção 2) — função
pura, por chamada direta."""

from __future__ import annotations

from app.componentes.explicacao_grupo import (legenda_fora_da_analise,
                                              resumo_da_execucao)
from core.aplicacao import grupos as grupos_mod


MEMBROS = {"ENQ-010.1", "ENQ-010.2"}


def _grupo():
    R = grupos_mod.RegraDoGrupo
    return grupos_mod.Grupo(id="g", rotulo="G", regras=[
        R(id="ENQ-009", rotulo="Acesso a escola de educação infantil"),
        R(id="ENQ-010", rotulo="Acesso ao ensino fundamental — Ciclo I"),
        R(id="ENQ-010.1", rotulo="Alternativa A — distância caminhável"),
        R(id="ENQ-010.2", rotulo="Alternativa B — transporte escolar"),
    ])


def test_alternativas_aparecem_pelo_pai_uma_vez_e_sem_ids():
    frase = resumo_da_execucao(_grupo(), ["ENQ-009", "ENQ-010", "ENQ-010.1",
                                          "ENQ-010.2"], MEMBROS)
    assert frase == ("**Ao analisar, o protótipo verifica:** acesso a escola "
                     "de educação infantil; acesso ao ensino fundamental — "
                     "Ciclo I.")
    assert "ENQ" not in frase


def test_filho_com_pai_na_planilha_mas_sem_agregacao_conta_a_parte():
    """EDI-004.1 tem pai na planilha, mas ninguém o agrega: é requisito."""
    frase = resumo_da_execucao(_programa(), ["EDI-004", "EDI-004.1"], set())
    assert "presença do programa mínimo; varanda integrante" in frase


def test_nada_executavel_devolve_vazio():
    assert resumo_da_execucao(_grupo(), [], MEMBROS) == ""


def _programa():
    R = grupos_mod.RegraDoGrupo
    return grupos_mod.Grupo(id="p", rotulo="P", regras=[
        R(id="EDI-004", rotulo="Presença do programa mínimo", aplicabilidade="ambas"),
        R(id="EDI-004.1", rotulo="Varanda integrante",
          aplicabilidade="multifamiliar"),
        R(id="EDI-001", rotulo="Área útil mínima da UH tipo casa",
          aplicabilidade="unifamiliar"),
        R(id="EDI-002", rotulo="Área útil mínima de apartamento",
          aplicabilidade="multifamiliar"),
    ])


def test_fora_da_analise_nomeia_a_verificacao_e_a_tipologia():
    assert legenda_fora_da_analise(_programa(), ["EDI-004", "EDI-004.1",
                                                 "EDI-002"], set()) == (
        "**Fora desta análise:** área útil mínima da UH tipo casa "
        "(aplica-se só a casas).")


def test_alternativas_de_agregacao_nao_entram_na_legenda():
    assert legenda_fora_da_analise(_grupo(), ["ENQ-009", "ENQ-010"],
                                   MEMBROS) == ""


def test_todas_executadas_nao_ha_legenda():
    assert legenda_fora_da_analise(_programa(), ["EDI-004", "EDI-004.1",
                                                 "EDI-001", "EDI-002"],
                                   set()) == ""
