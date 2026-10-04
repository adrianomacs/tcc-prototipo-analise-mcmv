"""ADR-030 — o porte é a população do Censo, classificada pela tabela de cada item.

Prende-se aqui o que o domínio sabe sem abrir arquivo: a população viaja com a
procedência, e a tabela do item 4.I.a do Anexo II cai nas faixas certas nas
fronteiras — os limites da Portaria são inteiros e contíguos ("até 20.000" /
"de 20.001"), e o inclusivo em cima é o que não deixa buraco.
"""

from __future__ import annotations

import pytest

from core.dominio.conhecimento import porte_municipal as porte

TABELA = porte.PORTE_EMPREENDIMENTO_4_I_A


@pytest.mark.parametrize("populacao, por_empreendimento, contiguos", [
    (1, 50, 200),
    (20_000, 50, 200),
    (20_001, 100, 300),
    (32_183, 100, 300),        # Estrela/RS, Censo 2022
    (50_000, 100, 300),
    (50_001, 150, 400),
    (100_000, 150, 400),
    (100_001, 250, 500),
    (500_000, 250, 500),
    (500_001, 300, 750),
    (697_054, 300, 750),       # São José dos Campos/SP, Censo 2022
    (11_451_999, 300, 750),
])
def test_faixas_do_item_4_I_a_nas_fronteiras(populacao, por_empreendimento, contiguos):
    assert porte.faixa(populacao, TABELA).valores == (por_empreendimento, contiguos)


def test_a_tabela_do_item_tem_cinco_faixas_e_topo_aberto():
    assert len(TABELA) == 5
    assert TABELA[-1].ate is None
    assert [f.ate for f in TABELA[:-1]] == sorted(f.ate for f in TABELA[:-1])


def test_tabela_sem_topo_aberto_e_erro():
    fechada = (porte.FaixaDePorte("até 10", 10, (1,)),)
    with pytest.raises(ValueError):
        porte.faixa(11, fechada)


def test_populacao_viaja_com_a_procedencia_do_censo():
    p = porte.PopulacaoMunicipal(codigo_ibge="4307807", populacao=32183,
                                 densidade=173.94)
    assert "Censo Demográfico 2022" in p.fonte and "4714" in p.fonte
    assert p.referencia == "2022-07-31"


@pytest.mark.parametrize("valor, erro", [(0, ValueError), (-5, ValueError),
                                         (1.5, TypeError), (True, TypeError),
                                         ("32183", TypeError)])
def test_populacao_invalida_e_recusada(valor, erro):
    with pytest.raises(erro):
        porte.PopulacaoMunicipal(codigo_ibge="0000000", populacao=valor)
