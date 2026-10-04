"""ADR-023/ADR-021 — a ``UnidadeTipo`` magra e o que ela responde sozinha.

É a antiga ``Edificacao`` com o nome certo (ADR-023): o grupo de UH que se
repete, não o prédio. Os testes são os mesmos daquela entidade, por rename —
asserções intactas, muda o construtor e o nome da classe.

O que se prende aqui:

1. **Sem ``ModeloBIM`` não há checagem BIM nesta unidade tipo** — e a ausência
   é dela, não do empreendimento: uma unidade tipo sem contêiner não apaga a
   geometria das outras. É a consequência direta de a submissão ser
   fragmentária (ADR-023).
2. **Identidade, como no ``Empreendimento``** (ADR-004): duas unidades tipo
   com os mesmos dados continuam sendo duas, e é por isso que a coleção da
   raiz pode recusar a repetição sem recusar a semelhança.
3. **``unidades`` é contagem, e não é o denominador** — o denominador é o
   ``unidades_representadas`` do contêiner (ADR-021). Os dois vivem lado a lado
   de propósito: a diferença entre eles é a extrapolação declarada.
"""

from __future__ import annotations

import pytest

from core.dominio.modelo_bim import ModeloBIM
from core.dominio.unidade_tipo import UnidadeTipo
from core.dominio.vocabulario import declaracoes as dec

# ---------------------------------------------------------------------------
# Identidade
# ---------------------------------------------------------------------------

def test_id_gerado_curto_e_identidade_por_id():
    a, b = UnidadeTipo(nome="Torre A"), UnidadeTipo(nome="Torre A")
    assert len(a.id) == 12 and a.id != b.id
    assert a != b, "mesmos dados não fazem a mesma unidade tipo"
    assert a == UnidadeTipo(id=a.id, nome="outro nome")
    assert len({a, b, UnidadeTipo(id=a.id)}) == 2


def test_nome_e_tipologia_normalizam_espacos():
    e = UnidadeTipo(nome="  Torre A  ", tipologia=f" {dec.APARTAMENTO} ")
    assert (e.nome, e.tipologia) == ("Torre A", dec.APARTAMENTO)
    assert UnidadeTipo(nome=None).nome == ""


# ---------------------------------------------------------------------------
# Sem ModeloBIM não há checagem BIM NESTA unidade tipo
# ---------------------------------------------------------------------------

def test_unidade_tipo_sem_conteiner_nao_e_checavel_por_bim():
    e = UnidadeTipo(nome="Bloco 2", unidades=8, tipologia=dec.APARTAMENTO)
    assert e.modelo is None
    assert e.checavel_por_bim is False
    assert e.unidades_representadas == 0, (
        "sem contêiner não há entrega a cujo respeito perguntar — e zero, não "
        "as unidades declaradas, é o que a regra encontraria")


def test_unidade_tipo_com_conteiner_e_checavel():
    e = UnidadeTipo(nome="Bloco 1", unidades=8, tipologia=dec.APARTAMENTO,
                   modelo=ModeloBIM(caminho="b1.ifc", unidades_representadas=4))
    assert e.checavel_por_bim is True and e.unidades_representadas == 4


def test_a_ausencia_de_conteiner_e_de_uma_unidade_tipo_so():
    """A submissão é fragmentária: uma unidade tipo sem modelo não apaga as outras."""
    com = UnidadeTipo(nome="Bloco 1", modelo=ModeloBIM(caminho="b1.ifc",
                                                      unidades_representadas=4))
    sem = UnidadeTipo(nome="Bloco 2")
    assert [e.checavel_por_bim for e in (com, sem)] == [True, False]


# ---------------------------------------------------------------------------
# unidades: contagem, e distinta do denominador
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("valor,esperado", [(None, 0), ("", 0), (0, 0), ("64", 64)])
def test_unidades_e_contagem_nao_negativa(valor, esperado):
    assert UnidadeTipo(unidades=valor).unidades == esperado


@pytest.mark.parametrize("valor", [-1, "sessenta", [64]])
def test_unidades_invalidas_sao_recusadas(valor):
    with pytest.raises(ValueError):
        UnidadeTipo(unidades=valor)


def test_unidades_e_unidades_representadas_sao_numeros_diferentes():
    """O pavimento tipo que se repete: 64 UHs faladas sobre 4 UHs lidas (ADR-021)."""
    torre = UnidadeTipo(nome="Torre A", unidades=64, tipologia=dec.APARTAMENTO,
                       modelo=ModeloBIM(caminho="tipo.ifc", unidades_representadas=4))
    assert (torre.unidades, torre.unidades_representadas) == (64, 4)


# ---------------------------------------------------------------------------
# Serialização (sem I/O)
# ---------------------------------------------------------------------------

def test_ida_e_volta_preserva_identidade_e_conteiner():
    e = UnidadeTipo(nome="Torre A", unidades=64, tipologia=dec.APARTAMENTO,
                   modelo=ModeloBIM(caminho="tipo.ifc", schema="IFC4",
                                    natureza=dec.EDIFICACAO_ISOLADA,
                                    unidades_representadas=4))
    volta = UnidadeTipo.from_dict(e.to_dict())
    assert volta == e and volta.to_dict() == e.to_dict()
    assert volta.modelo == e.modelo


def test_unidade_tipo_sem_conteiner_viaja_com_modelo_none():
    d = UnidadeTipo(nome="Bloco 2").to_dict()
    assert d["modelo"] is None
    assert UnidadeTipo.from_dict(d).modelo is None


def test_ausencia_de_unidade_tipo_viaja_como_none():
    assert UnidadeTipo.from_dict(None) is None and UnidadeTipo.from_dict({}) is None


def test_from_dict_gera_id_quando_o_artefato_nao_tem():
    assert len(UnidadeTipo.from_dict({"nome": "Torre A"}).id) == 12
