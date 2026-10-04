"""EMP-025 — porte do empreendimento: a folha decidível, a remetida e o "e".

Três coisas se prendem aqui:

1. **EMP-025.1 compara o total DECLARADO com o limite do porte** (ADR-028,
   ADR-030): conforme até o limite, não conforme acima; sem porte, sem
   contagem ou com declarações que se contradizem, NÃO AVALIÁVEL com a causa
   certa — e a inconsistência é o motivo do ADR-022, não um veredito.
2. **EMP-025.2 é remetida** (DN-04) e não depende de nada.
3. **A aritmética do pai em ``MODO_TODOS`` com k = 2** (ADR-015): .1 não
   conforme → pai NÃO CONFORME; .1 conforme e .2 remetida → pai NÃO
   AVALIÁVEL reportando [1, 2] contra 2.
"""

from __future__ import annotations

import pytest

from core.aplicacao.executor import executar
from core.dominio.conhecimento.porte_municipal import PopulacaoMunicipal
from core.dominio.contratos.regra import Contexto, Estado
from core.dominio.edificacao import Edificacao
from core.dominio.empreendimento import Empreendimento, Localizacao
from core.dominio.unidade_tipo import UnidadeTipo
from core.dominio.vocabulario import motivos
from core.regras.base import agregacao as ag
from core.regras.gis.emp_025_1_limite_uh_empreendimento import EMP0251
from core.regras.gis.emp_025_2_limite_uh_contiguos import EMP0252
from core.regras.gis.emp_025_porte_empreendimento import EMP025

ESTRELA = PopulacaoMunicipal(codigo_ibge="4307807", populacao=32183,
                             densidade=173.94)


def _emp(previstas=0, tipos=(), edificacoes=(), codigo="4307807"):
    return Empreendimento(localizacao=Localizacao(codigo) if codigo else None,
                          unidades_previstas=previstas,
                          unidades_tipo=list(tipos),
                          edificacoes=list(edificacoes))


def _ctx(emp, populacao=ESTRELA):
    return Contexto(empreendimento=emp, populacao_municipal=populacao)


# ---------------------------------------------------------------------------
# 1. EMP-025.1
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("previstas, estado", [
    (1, Estado.CONFORME), (100, Estado.CONFORME), (101, Estado.NAO_CONFORME),
    (300, Estado.NAO_CONFORME)])
def test_limite_de_estrela_e_100_uh(previstas, estado):
    """Estrela/RS, 32.183 hab. (Censo 2022): faixa de 20.001 a 50.000, 100 UH."""
    r = EMP0251().checar(_ctx(_emp(previstas)))
    assert r.estado is estado
    assert (r.valor_esperado, r.valor_encontrado, r.unidade) == (100, previstas, "UH")
    assert r.detalhe["faixa"] == "de 20.001 a 50.000 habitantes"
    assert r.detalhe["populacao"] == 32183


def test_o_limite_segue_o_porte_do_municipio():
    grande = PopulacaoMunicipal(codigo_ibge="3549904", populacao=697054)
    r = EMP0251().checar(_ctx(_emp(300, codigo="3549904"), grande))
    assert r.estado is Estado.CONFORME and r.valor_esperado == 300


def test_a_contagem_e_a_declarada_nunca_a_do_modelo():
    """Um IFC de 1 UH não aprova um empreendimento de 300 (ADR-028)."""
    from core.dominio.modelo_bim import ModeloBIM
    tipo = UnidadeTipo(nome="Apto", unidades=300, tipologia="apartamento",
                       modelo=ModeloBIM(caminho="x.ifc", natureza="unidade_tipo",
                                        unidades_representadas=1))
    emp = _emp(300, tipos=[tipo])
    ctx = Contexto(empreendimento=emp, populacao_municipal=ESTRELA,
                   conteiner=tipo.modelo)
    assert EMP0251().checar(ctx).estado is Estado.NAO_CONFORME


def test_municipio_sem_populacao_no_censo_tem_porte_indeterminado():
    r = EMP0251().checar(_ctx(_emp(80, codigo="4307807"), None))
    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.PORTE_INDETERMINADO


def test_municipio_nao_declarado_e_insumo_do_proponente():
    """Falta a declaração, não a população (ADR-033; decisão da D1b.1)."""
    r = EMP0251().checar(_ctx(_emp(80, codigo=""), None))
    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.INSUMO_DO_PROPONENTE_AUSENTE


def test_sem_uh_previstas_declaradas_nao_ha_o_que_comparar():
    r = EMP0251().checar(_ctx(_emp(0)))
    assert r.estado is Estado.NAO_AVALIAVEL
    # ADR-033: declaração ausente é insumo do proponente, não camada pública.
    assert r.detalhe[motivos.CHAVE] == motivos.INSUMO_DO_PROPONENTE_AUSENTE
    assert r.valor_esperado == 100          # o limite já se sabe
    assert "UH previstas" in r.mensagem


def test_unidades_tipo_acima_do_previsto_e_inconsistencia_declaratoria():
    """ADR-022, primeira aritmética: tipos × previsto — mesmo com os dois
    números abaixo do limite, o veredito não escolhe entre eles."""
    r = EMP0251().checar(_ctx(_emp(80, tipos=[UnidadeTipo(nome="A", unidades=90)])))
    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.INCONSISTENCIA_DECLARATORIA
    assert "90" in r.mensagem and "80" in r.mensagem


def test_composicao_acima_das_unidades_do_tipo_e_inconsistencia_declaratoria():
    """ADR-022, segunda aritmética (ADR-023): composição × unidades do tipo."""
    tipo = UnidadeTipo(nome="Casa", unidades=40, tipologia="casa")
    predio = Edificacao(nome="Bloco", composicao={tipo.id: 60})
    r = EMP0251().checar(_ctx(_emp(80, tipos=[tipo], edificacoes=[predio])))
    assert r.detalhe[motivos.CHAVE] == motivos.INCONSISTENCIA_DECLARATORIA
    assert "Casa" in r.mensagem


def test_declaracao_incompleta_e_legitima():
    """Tipos somando MENOS que o previsto não bloqueiam: decide o previsto."""
    r = EMP0251().checar(_ctx(_emp(80, tipos=[UnidadeTipo(nome="A", unidades=10)])))
    assert r.estado is Estado.CONFORME


def test_o_motivo_novo_tem_rotulo_e_acao():
    assert motivos.INCONSISTENCIA_DECLARATORIA in motivos.ROTULO
    assert "Informações Gerais" in motivos.ACAO[motivos.INCONSISTENCIA_DECLARATORIA]


# ---------------------------------------------------------------------------
# 2. EMP-025.2
# ---------------------------------------------------------------------------

def test_contiguos_e_remetida_sem_depender_de_nada():
    r = EMP0252().checar(Contexto())
    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.ANALISE_HUMANA_DOCUMENTAL
    assert r.detalhe["automatizavel"] is False
    assert "perímetro" in r.detalhe["insumo"]


# ---------------------------------------------------------------------------
# 3. O pai — MODO_TODOS, k = 2
# ---------------------------------------------------------------------------

def _pai(previstas):
    return executar(_ctx(_emp(previstas)), ids_selecionados=["EMP-025"])


def test_pai_declara_modo_todos_sobre_as_duas_folhas():
    assert EMP025.modo == ag.MODO_TODOS
    assert EMP025.agrega == ["EMP-025.1", "EMP-025.2"]
    assert ag.k_de(EMP025.modo, len(EMP025.agrega)) == 2


def test_exceder_o_limite_individual_reprova_o_pai():
    res = _pai(300)
    assert res["EMP-025.1"].estado is Estado.NAO_CONFORME
    assert res["EMP-025.2"].estado is Estado.NAO_AVALIAVEL
    pai = res["EMP-025"]
    assert pai.estado is Estado.NAO_CONFORME
    assert (pai.detalhe["n_conf"], pai.detalhe["n_pot"], pai.detalhe["k"]) == (0, 1, 2)


def test_limite_individual_atendido_deixa_o_pai_em_aberto_1_a_2():
    pai = _pai(80)["EMP-025"]
    assert pai.estado is Estado.NAO_AVALIAVEL
    assert [pai.detalhe["n_conf"], pai.detalhe["n_pot"]] == [1, 2]
    assert pai.detalhe["k"] == 2
    # A pendência é uma só — a remessa —, e o pai herda a causa dela.
    assert pai.detalhe[motivos.CHAVE] == motivos.ANALISE_HUMANA_DOCUMENTAL


def test_o_pai_continua_reprovavel():
    """Um membro irredutível não alcança k = 2: a ferramenta reprova."""
    teto = _pai(80)["EMP-025"].detalhe["reprovabilidade"]
    assert teto["reprovavel"] is True
    assert teto["membros_irredutiveis"] == ["EMP-025.2"]


def test_porte_indeterminado_deixa_o_pai_em_aberto_0_a_2():
    res = executar(_ctx(_emp(80), None), ids_selecionados=["EMP-025"])
    pai = res["EMP-025"]
    assert pai.estado is Estado.NAO_AVALIAVEL
    assert [pai.detalhe["n_conf"], pai.detalhe["n_pot"]] == [0, 2]
    # Causas diferentes nos dois membros: o motivo genérico é o honesto.
    assert pai.detalhe[motivos.CHAVE] == motivos.AGREGACAO_INDECISA
