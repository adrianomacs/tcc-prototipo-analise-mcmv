"""Relatório da absortância (ADR-034): os textos puros da página."""

from __future__ import annotations

import pytest

pytest.importorskip("streamlit")

from app.componentes import relatorio_absortancia as a  # noqa: E402
from app.componentes.avisos import ALERTA  # noqa: E402


def _ramo(rid, limite, zonas, aplic, coverings=(), valor=None, motivo=""):
    return {"requisito": rid, "estado": "nao_avaliavel",
            "valor_encontrado": valor, "mensagem": "m",
            "detalhe": {"tipo": "absortancia", "limite": limite,
                        "zonas_texto": zonas,
                        "zona_resolvida": {"classe": "2R"},
                        "aplicabilidade_do_ramo": aplic,
                        "motivo_nao_avaliavel": motivo,
                        "populacao": {"total_coverings": 5,
                                      "alvo": [c["global_id"] for c in coverings]},
                        "coverings": list(coverings)}}


_C = {"global_id": "g1", "nome": "Reboco", "materiais": ["Pintura"],
      "absortancia": 0.35, "rotulo_situacao": "atende ao limite"}
_PAREDE = [_ramo("EDI-019.1", 0.6, "1 e 2", "aplicavel", [_C], 0.35),
           _ramo("EDI-019.2", 0.4, "3 a 6", "inaplicavel", [_C], 0.35)]
_TELHADO = [_ramo("EDI-024.1", 0.6, "1, 2 e 3", "indeterminada"),
            _ramo("EDI-024.2", 0.4, "4 a 8", "indeterminada")]


def test_despacho_e_familia():
    assert a.eh_absortancia(_PAREDE)
    assert not a.eh_absortancia([{"detalhe": {"tipo": "remetida"}}])
    assert a.eh_telhado(_TELHADO) and not a.eh_telhado(_PAREDE)


def test_criterio_traz_limites_zona_e_medido():
    texto = a.criterio_absortancia(_PAREDE, a.maior_absortancia(_PAREDE))
    assert "≤ <b>0,6</b> nas zonas 1 e 2" in texto
    assert "zona do município: 2R, limite 0,6" in texto
    assert "maior absortância 0,35" in texto


def test_telhado_sem_ramo_aplicavel_nao_inventa_limite():
    texto = a.criterio_absortancia(_TELHADO)
    assert "sem correspondência" in texto and "Medido" not in texto


def test_resultado_sem_revestimento_declarado():
    assert "Nenhum dos 5" in a.texto_resultado(_TELHADO)
    assert "**1** de 5" in a.texto_resultado(_PAREDE)


def test_uma_linha_por_revestimento_com_coluna_por_limite():
    linhas = a.linhas_revestimentos(_PAREDE)
    assert len(linhas) == 1
    assert linhas[0]["Absortância"] == "0,35"
    assert {"Até 0,6", "Até 0,4"} <= set(linhas[0])


def test_inconsistencia_declaratoria_vira_alerta():
    bloqueado = [_ramo("EDI-019.1", 0.6, "1 e 2", "aplicavel",
                       motivo="inconsistencia_declaratoria")]
    assert [x.nivel for x in a.avisos_absortancia(bloqueado)] == [ALERTA]
    assert a.avisos_absortancia(_PAREDE) == []


def test_destaque_verde_e_vermelho_por_coluna_de_limite():
    linhas = [{"Até 0,6": "atende ao limite", "Até 0,4": "acima do limite"},
              {"Até 0,6": "material não identificável",
               "Até 0,4": "material não identificável"}]
    assert a.destaques_revestimentos(linhas) == {
        "Até 0,4": ["falha", None], "Até 0,6": ["ok", None]}


def _cov(gid, valor, situacao):
    return {"global_id": gid, "nome": gid, "absortancia": valor,
            "situacao": situacao, "rotulo_situacao": situacao}


def test_parede_acima_do_limite_da_zona_e_explicada():
    covs = [_cov("a", 0.35, "atende"), _cov("b", 0.72, "nao_atende")]
    ramos = [_ramo("EDI-019.1", 0.6, "1 e 2", "aplicavel", covs, 0.72)]
    texto = a.texto_acima_do_limite(ramos)
    assert "**1 de 2 revestimento(s) de paredes externas" in texto
    assert "limite de 0,6** (da zona do município)" in texto
    assert "0,72" in texto and "Basta um" in texto


def test_sem_revestimento_acima_nao_ha_frase():
    assert a.texto_acima_do_limite(_PAREDE) == ""


def test_telhado_usa_o_maior_limite():
    covs = [_cov("t", 0.7, "nao_atende")]
    ramos = [_ramo("EDI-024.1", 0.6, "1, 2 e 3", "indeterminada", covs, 0.7),
             _ramo("EDI-024.2", 0.4, "4 a 8", "indeterminada", covs, 0.7)]
    assert "limite de 0,6** (o maior limite" in a.texto_acima_do_limite(ramos)


def test_contagens_da_populacao_traduzidas():
    linhas = a.linhas_populacao({"criterio": "x", "total_coverings": 117,
                                 "alvo": ["g"] * 115, "cobertura": 2})
    assert linhas[0] == {"Revestimentos": "Revestimentos no modelo",
                         "Quantidade": 117}
    assert {"Revestimentos": "Entraram na verificação", "Quantidade": 115} in linhas


# ---------------------------------------------------------------------------
# Cor da cena pelo resultado de cada revestimento
# ---------------------------------------------------------------------------

def _cov(gid, abs_, situacao):
    return {"global_id": gid, "nome": gid, "absortancia": abs_,
            "situacao": situacao, "rotulo_situacao": situacao}


def _por_gid(itens):
    return {i["global_id"]: i["resultado"] for i in itens}


def test_cena_decide_pelo_ramo_aplicavel():
    """O ramo aplicável à zona decide; o inaplicável não pinta nada."""
    ramos = [_ramo("EDI-019.1", 0.6, "1 e 2", "aplicavel",
                   [_cov("a", 0.35, "atende"), _cov("b", 0.7, "nao_atende"),
                    _cov("c", None, "sem_absortancia")]),
             _ramo("EDI-019.2", 0.4, "3 a 6", "inaplicavel",
                   [_cov("a", 0.35, "atende"), _cov("b", 0.7, "nao_atende"),
                    _cov("c", None, "sem_absortancia")])]
    assert _por_gid(a.revestimentos_para_cena(ramos)) == {
        "a": "atende", "b": "nao_atende", "c": "neutro"}


def test_cena_do_telhado_so_pinta_o_que_decide_em_qualquer_zona():
    """Sem ramo aplicável, verde só abaixo dos dois limites e vermelho só
    acima dos dois; entre eles, em aberto (neutro)."""
    ramos = [_ramo("EDI-024.1", 0.6, "1, 2 e 3", "indeterminada",
                   [_cov("baixo", 0.3, "atende"), _cov("meio", 0.5, "atende"),
                    _cov("alto", 0.8, "nao_atende"),
                    _cov("barro", 0.7, "excecao")]),
             _ramo("EDI-024.2", 0.4, "4 a 8", "indeterminada",
                   [_cov("baixo", 0.3, "atende"), _cov("meio", 0.5, "nao_atende"),
                    _cov("alto", 0.8, "nao_atende"),
                    _cov("barro", 0.7, "excecao")])]
    itens = {i["global_id"]: i for i in a.revestimentos_para_cena(ramos)}
    assert {g: i["resultado"] for g, i in itens.items()} == {
        "baixo": "atende", "meio": "neutro", "alto": "nao_atende",
        "barro": "neutro"}
    assert "em aberto" in itens["meio"]["rotulo"]


def test_legenda_da_cena_dos_revestimentos():
    assert "nada a destacar" in a.legenda_cena([], 0)
    item = [{"global_id": "g"}]
    assert "sem destaque" in a.legenda_cena(item, 0)
    assert "cor do seu resultado" in a.legenda_cena(item, 1)
    assert "1 revestimento(s) sem geometria" in a.legenda_cena(item * 2, 1)
