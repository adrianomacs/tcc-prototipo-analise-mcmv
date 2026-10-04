"""Relatório do EMP-025 (ADR-034): os textos puros da página."""

from __future__ import annotations

import pytest

pytest.importorskip("streamlit")

from app.componentes import relatorio_porte as p  # noqa: E402
from app.componentes.avisos import ALERTA  # noqa: E402

_IND = {"tipo": "porte_empreendimento", "limite": 100,
        "limite_grupo_contiguos": 300, "unidades_previstas": 300,
        "faixa": "de 20.001 a 50.000 habitantes", "populacao": 32183}
_MEMBROS = [{"requisito": "EMP-025.1", "estado": "nao_conforme",
             "detalhe": _IND},
            {"requisito": "EMP-025.2", "estado": "nao_avaliavel",
             "detalhe": {"tipo": "remetida"}}]


def test_despacho_reconhece_o_porte():
    assert p.eh_porte(_MEMBROS)
    assert not p.eh_porte([{"requisito": "ENQ-010.1",
                            "detalhe": {"tipo": "distancia_equipamento"}}])


def test_membro_por_id():
    assert p.membro(_MEMBROS, "EMP-025.2")["estado"] == "nao_avaliavel"
    assert p.membro(_MEMBROS, "X") == {}


def test_criterio_traz_os_dois_limites_e_o_medido():
    texto = p.criterio_porte(_IND)
    assert "<b>100 UH</b>" in texto and "<b>300 UH</b>" in texto
    assert "de 20.001 a 50.000 habitantes" in texto
    assert "<b>Medido:</b> 300 UHs previstas" in texto


def test_criterio_vazio_sem_limite():
    assert p.criterio_porte({}) == ""


def test_decisao_nem_no_melhor_cenario():
    texto = p.texto_decisao({"k": 2, "n_conf": 0, "n_pot": 1,
                             "total_membros": 2})
    assert "no máximo 1" in texto and "não é atendido" in texto


def test_decisao_indecisa_so_pode_reprovar():
    texto = p.texto_decisao({"k": 2, "n_conf": 1, "n_pot": 2,
                             "total_membros": 2})
    assert "nunca aprová-lo" in texto


def test_inconsistencia_vira_alerta():
    avisos = p.avisos_porte({"inconsistencias": ["300 previstas × 280 nos tipos"]})
    assert [a.nivel for a in avisos] == [ALERTA]
    assert p.avisos_porte({}) == []


def test_contexto_nomeia_a_fonte_do_porte_e_o_item_da_portaria():
    assert "Censo Demográfico 2022" in p.CONTEXTO_PORTE
    assert "item 4.I.a" in p.CONTEXTO_PORTE


def test_nome_do_municipio_para_a_metrica():
    assert p.nome_municipio({"nome": "Estrela", "uf": "RS"}) == "Estrela/RS"
    assert p.nome_municipio({}) == "—"
