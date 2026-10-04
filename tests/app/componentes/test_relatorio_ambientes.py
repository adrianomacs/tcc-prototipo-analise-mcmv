"""Relatório por regra do Programa de necessidades (ADR-034): textos puros."""

from __future__ import annotations

import pytest

pytest.importorskip("streamlit")

from app.componentes import relatorio_ambientes as p  # noqa: E402
from app.componentes.avisos import ALERTA  # noqa: E402
from app.componentes.card_verificacao import montar_card_grupo  # noqa: E402

_FORA = [{"nome": "Laje Técnica", "causa": "caixa padrão",
          "valores": {"sobreposicao_no_pavimento": {"pavimento": "TÉRREO"}}}]


def test_so_os_tipos_do_programa_abrem_este_relatorio():
    for tipo in ("ambientes", "areas_uh", "larguras"):
        assert p.eh_ambientes({"tipo": tipo})
    assert not p.eh_ambientes({"tipo": "logeoref"})
    assert not p.eh_ambientes({})


def test_normalizacao_so_entra_com_mais_de_uma_uh():
    assert p.ponto_normalizacao(1) == ""
    assert "8 UHs que o modelo representa" in p.ponto_normalizacao(8)


def test_um_aviso_so_na_faixa():
    assert p.AVISO_GERAL.nivel == ALERTA


def test_card_do_grupo_escapa_o_texto():
    html = montar_card_grupo("Programa", "Não conforme", "#ea4335", "a < b")
    assert "Programa — Não conforme" in html and "a &lt; b" in html


def test_ambientes_fora_vem_do_detalhe_da_propria_regra():
    assert p.ambientes_fora({"fora_da_populacao": _FORA}) == _FORA
    assert p.ambientes_fora({}) == []


def test_regra_que_consome_uh_leva_normalizacao_e_diagnosticos():
    meta = {"diagnosticos": [{"rotulo": "Estendido", "marcado": True,
                              "mensagem": "m"}]}
    det = {"tipo": "areas_uh", "num_uhs": 8, "fora_da_populacao": _FORA}
    pontos = p.pontos_de_atencao(det, meta)
    assert len(pontos) == 3
    assert p.SECAO_AMBIENTES_FORA in pontos[2]


def test_largura_nao_fala_de_uh_nem_de_diagnostico():
    meta = {"diagnosticos": [{"rotulo": "Estendido", "marcado": True,
                              "mensagem": "m"}]}
    assert p.pontos_de_atencao({"tipo": "larguras"}, meta) == []
    assert len(p.pontos_de_atencao(
        {"tipo": "larguras", "fora_da_populacao": _FORA}, meta)) == 1


def test_tabela_dos_ambientes_fora_traz_guid_motivo_e_dimensoes():
    fora = [{"nome": "Cozinha", "global_id": "G1", "causa": "caixa padrão",
             "area_declarada_m2": 4.8535, "area_footprint_m2": 4.46,
             "largura_m": 1.829, "comprimento_m": 2.438,
             "valores": {"sobreposicao_no_pavimento": {"pavimento": "TIPO"}}}]
    linha = p.linhas_ambientes_fora(fora)[0]
    assert linha["GUID"] == "G1" and linha["Motivo"] == "Caixa padrão"
    assert linha["Pavimento"] == "TIPO" and linha["Largura (m)"] == 1.83


def test_so_diagnosticos_marcados_entram():
    meta = {"diagnosticos": [
        {"rotulo": "Resultado estendido", "marcado": True, "mensagem": "m"},
        {"rotulo": "Outro", "marcado": False}]}
    assert p.pontos_diagnosticos(meta) == ["**Resultado estendido.** m"]


def test_criterio_do_card_usa_o_que_a_regra_gravou_e_escapa():
    r = {"valor_esperado": "largura ≥ 2.40 m",
         "valor_encontrado": "menor largura medida: <2.1> m"}
    texto = p.criterio(r)
    assert texto.startswith("<b>Exige:</b> largura ≥ 2.40 m")
    assert "&lt;2.1&gt;" in texto
    assert p.criterio({}) == ""


def test_legenda_da_cena_segue_a_regra():
    assert "banheiro" in p.legenda_cena({"tipo": "larguras",
                                         "categoria_rotulo": "Banheiro"})
    assert "soma" in p.legenda_cena({"tipo": "areas_uh"})
    assert "programa" in p.legenda_cena({"tipo": "ambientes"})


# ---------------------------------------------------------------------------
# Cor da cena pelo resultado de cada ambiente
# ---------------------------------------------------------------------------

def test_resultado_nas_larguras_segue_o_atende_de_cada_ambiente():
    det = {"tipo": "larguras", "ambientes": [
        {"global_id": "a", "atende": True}, {"global_id": "b", "atende": False},
        {"global_id": "c", "atende": None}]}
    assert p.resultado_por_ambiente(det) == {
        "a": "atende", "b": "nao_atende", "c": "neutro"}


def test_resultado_no_programa_segue_a_categoria():
    det = {"tipo": "ambientes",
           "categorias": [{"chave": "sala", "atende": False, "global_ids": ["s1"]},
                          {"chave": "cozinha", "atende": True, "global_ids": ["k1"]}],
           "ambientes": [{"global_id": "s1"}, {"global_id": "k1"},
                         {"global_id": "x"}]}
    assert p.resultado_por_ambiente(det) == {
        "s1": "nao_atende", "k1": "atende", "x": "neutro"}


def test_resultado_na_area_util_segue_o_estado_da_regra():
    det = {"tipo": "areas_uh", "ambientes": [
        {"global_id": "a", "area_m2": 10.0}, {"global_id": "b", "area_m2": None}]}
    assert p.resultado_por_ambiente(det, "conforme") == {"a": "atende", "b": "neutro"}
    assert p.resultado_por_ambiente(det, "nao_conforme")["a"] == "nao_atende"
    assert p.resultado_por_ambiente(det, "nao_avaliavel")["a"] == "neutro"
