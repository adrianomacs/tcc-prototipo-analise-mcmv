"""ADR-023/ADR-021 — o ``ModeloBIM`` como objeto de valor, e o número que ele carrega.

O que se prende aqui:

1. **É valor, não entidade.** Dois contêineres com os mesmos campos são iguais,
   e nenhum deles pode ser alterado no lugar — é o que o ``frozen`` compra e o
   que justifica o pipeline variar o ``schema`` por ``dataclasses.replace``.
2. **``unidades_representadas`` é contagem.** Zero é legítimo (o modelo só do
   terreno não representa UH nenhuma); negativo não é, e lixo tampouco.
3. **A ida e volta não perde o número** — é ele que vai ser o denominador das
   regras dimensionais, e um campo que some na serialização voltaria como zero
   sem ninguém perceber.
"""

from __future__ import annotations

import dataclasses

import pytest

from core.dominio.modelo_bim import ModeloBIM


def test_igualdade_por_valor_e_nao_por_identidade():
    a = ModeloBIM(caminho="a.ifc", schema="IFC4", unidades_representadas=4)
    b = ModeloBIM(caminho="a.ifc", schema="IFC4", unidades_representadas=4)
    assert a == b and a is not b
    assert a != dataclasses.replace(a, unidades_representadas=1)


def test_nao_pode_ser_alterado_no_lugar():
    modelo = ModeloBIM(caminho="a.ifc")
    with pytest.raises(dataclasses.FrozenInstanceError):
        modelo.caminho = "b.ifc"


def test_replace_produz_outro_valor_sem_tocar_o_original():
    """O idioma que o pipeline usa para carimbar o schema lido do arquivo."""
    modelo = ModeloBIM(caminho="a.ifc", unidades_representadas=4)
    carimbado = dataclasses.replace(modelo, schema="IFC4")
    assert (carimbado.schema, modelo.schema) == ("IFC4", "")
    assert carimbado.unidades_representadas == 4


@pytest.mark.parametrize("valor,esperado", [(None, 0), ("", 0), (0, 0), ("4", 4), (4, 4)])
def test_zero_e_legitimo_e_texto_numerico_e_aceito(valor, esperado):
    assert ModeloBIM(unidades_representadas=valor).unidades_representadas == esperado


@pytest.mark.parametrize("valor", [-1, "quatro", 1.5j, [4], {"n": 4}])
def test_contagem_invalida_e_recusada_na_construcao(valor):
    with pytest.raises(ValueError):
        ModeloBIM(unidades_representadas=valor)


def test_ida_e_volta_preserva_as_unidades_representadas():
    modelo = ModeloBIM(caminho="t.ifc", schema="IFC4", natureza="edificacao_isolada",
                       digest="abc", unidades_representadas=4)
    assert ModeloBIM.from_dict(modelo.to_dict()) == modelo
    assert modelo.to_dict()["unidades_representadas"] == 4


def test_ausencia_de_conteiner_viaja_como_none():
    assert ModeloBIM.from_dict(None) is None
    assert ModeloBIM.from_dict({}) is None
