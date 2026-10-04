"""Identidade do município na interface: o código e o link do portal.

O código IBGE é a chave — do recorte de equipamentos, das bases oficiais, do
cruzamento com a malha. O link do portal é conveniência, e o motivo de ele ser
*apenas* conveniência está aqui: o portal indexa por **slug do nome**, o que
reintroduz a dependência de acentuação e grafia que o código existe para
eliminar. Estes testes fixam o que produzimos e nomeiam o que não controlamos.
"""

from __future__ import annotations

import pytest

from core.dominio.conhecimento import municipios as mun


@pytest.mark.parametrize("nome, esperado", [
    ("Estrela", "estrela"),
    ("São José dos Campos", "sao-jose-dos-campos"),
    ("Mogi-Guaçu", "mogi-guacu"),
    ("Embu das Artes", "embu-das-artes"),
    ("  Curitiba  ", "curitiba"),
])
def test_slug_remove_acento_e_junta_com_hifen(nome, esperado):
    assert mun.slug_ibge(nome) == esperado


@pytest.mark.parametrize("nome", ["Santa Bárbara d'Oeste", "Alta Floresta D'Oeste",
                                  "Olho d'Água"])
def test_apostrofo_vira_hifen_e_o_link_fica_sob_suspeita(nome):
    """O caso incerto na origem, fixado no comportamento.

    Não confirmamos qual grafia o IBGE usa para nomes com apóstrofo. O que este
    teste garante é que a nossa saída é **determinística** e não quebra — e que,
    se o link falhar, o caminho chaveado pelo código continua disponível.
    """
    slug = mun.slug_ibge(nome)
    assert "'" not in slug and "--" not in slug
    assert slug.startswith(("santa-barbara-d", "alta-floresta-d", "olho-d"))


def test_url_do_portal_usa_uf_minuscula_e_slug():
    m = mun.Municipio("4307807", "Estrela", "RS")
    assert mun.url_portal(m) == \
        "https://cidades.ibge.gov.br/brasil/rs/estrela/panorama"


def test_a_alternativa_pelo_codigo_nao_depende_de_grafia():
    """Quando o slug falha, o código ainda resolve — é o ponto da divisão."""
    assert mun.url_api("4307807").endswith("/municipios/4307807")
    assert mun.slug_ibge("") == ""      # sem nome, sem link; o código permanece


def test_nome_vazio_nao_levanta():
    assert mun.slug_ibge(None) == ""
