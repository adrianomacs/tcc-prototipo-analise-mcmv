"""Triagem de ambientes fantasma do exportador (ADR-031), com o dublê.

Um teste por sinal, e cada um prova duas coisas: o sinal é detectado, e
sozinho ele **não** tira o ambiente da população. Um sinal sozinho não basta,
e há motivo medido para cada um: a sobreposição sozinha é o que o IFC2X3 do
Revit faz com todo espaço, a divergência sozinha pode ser desconto de pilar,
e a caixa padrão sozinha é convenção de um exportador. Os testes de
combinação provam o outro lado: com dois sinais o ambiente sai, e sai
reportado, com os sinais e os números.

O dublê (``tests/apoio/ifc_falso.py``) dá a topologia: pavimento, ponto de
inserção e nome. A área declarada e a geometria vêm de ``monkeypatch``
(``_psets_do_espaco`` e ``medir``), porque o dublê não tem property set nem
kernel geométrico. Sem IfcOpenShell.
"""

from __future__ import annotations

import pytest

from core.infra.ifc import extrator_ambientes as ea
from tests.apoio.ifc_falso import espaco, modelo_espacos, pavimento

CAIXA = {"largura_m": 1.829, "comprimento_m": 2.438, "area_footprint_m2": 4.46,
         "metodo": "x"}


def _medida(largura, comprimento):
    return {"largura_m": largura, "comprimento_m": comprimento,
            "area_footprint_m2": round(largura * comprimento, 2), "metodo": "x"}


@pytest.fixture
def dados(monkeypatch):
    """Instala área declarada e geometria por GlobalId; devolve os dois dicts."""
    areas: dict[str, float] = {}
    medidas: dict[str, dict] = {}
    monkeypatch.setattr(ea, "_psets_do_espaco",
                        lambda sp: {"NetFloorArea": areas[sp.GlobalId]}
                        if sp.GlobalId in areas else {})
    monkeypatch.setattr(ea, "medir",
                        lambda modelo, gids: {g: medidas.get(g, {"erro": "sem medida"})
                                              for g in gids})
    return areas, medidas


def _fora(triagem):
    return {a["global_id"]: a for a in triagem.fora}


# --- S1 · ponto de inserção coincidente no mesmo pavimento ------------------

def test_s1_sobreposicao_detectada_mas_sozinha_nao_retira(dados):
    areas, medidas = dados
    tipo = pavimento("TIPO")
    # Dois ambientes legítimos no MESMO ponto. É o que o exportador IFC2X3 do
    # Revit faz com todos os espaços do pavimento.
    a, b = espaco("A", "Cozinha", tipo), espaco("B", "BWC", tipo)
    areas.update({"A": 4.85, "B": 3.70})
    medidas.update({"A": _medida(1.80, 2.696), "B": _medida(1.485, 2.49)})

    modelo = modelo_espacos(a, b)
    sinais = ea.sinais_de_fantasma(
        [(x, medidas[x.global_id], ea._posicoes(modelo).get(x.global_id))
         for x in ea.listar(modelo)])
    assert set(sinais) == {"A", "B"}
    assert all(list(s) == [ea.SOBREPOSICAO] for s in sinais.values())

    triagem = ea.triar(modelo)
    assert [x.global_id for x in triagem.populacao] == ["A", "B"]
    assert triagem.fora == [] and triagem.nota() == ""


def test_s1_nao_dispara_em_pavimentos_diferentes(dados):
    areas, medidas = dados
    # O mesmo ponto em pavimentos diferentes é o pavimento tipo repetido.
    a = espaco("A", "Sala", pavimento("TÉRREO", "ST0"))
    b = espaco("B", "Sala", pavimento("TIPO", "ST1"))
    # A caixa (S3) está nos dois e a área declarada é a própria pegada (sem
    # S2): se o S1 disparasse entre pavimentos, os dois sairiam.
    areas.update({"A": 4.46, "B": 4.46})
    medidas.update({"A": CAIXA, "B": CAIXA})
    triagem = ea.triar(modelo_espacos(a, b))
    assert len(triagem.populacao) == 2 and triagem.fora == []


# --- S2 · pegada × área declarada além do fator ------------------------------

def test_s2_divergencia_detectada_mas_sozinha_nao_retira(dados):
    areas, medidas = dados
    tipo = pavimento()
    # Pegada de 10 m², área declarada de 8 m² (razão 1,25 > 1,10). Pode ser
    # pilar descontado da área líquida: sozinha, não retira.
    a = espaco("A", "Quarto 1", tipo, ponto=(0.36, -25.12, 0.0))
    areas["A"] = 8.0
    medidas["A"] = _medida(2.5, 4.0)
    triagem = ea.triar(modelo_espacos(a))
    assert [x.global_id for x in triagem.populacao] == ["A"]

    sinais = ea.sinais_de_fantasma([(ea.listar(modelo_espacos(a))[0], medidas["A"], None)])
    assert sinais["A"] == {ea.PEGADA_X_AREA: {"razao": 1.25, "fator": 1.10}}


def test_s2_respeita_o_fator(dados):
    areas, medidas = dados
    a = espaco("A", "Cozinha", pavimento())
    areas["A"] = 4.85                    # o fantasma mais discreto do E2: 1,088
    medidas["A"] = {"largura_m": 1.9, "comprimento_m": 2.5,
                    "area_footprint_m2": 4.46, "metodo": "x"}
    amb = ea.listar(modelo_espacos(a))[0]
    assert ea.sinais_de_fantasma([(amb, medidas["A"], None)]) == {}


# --- S3 · caixa padrão do exportador (6' × 8') -------------------------------

def test_s3_caixa_padrao_detectada_mas_sozinha_nao_retira(dados):
    areas, medidas = dados
    # Um ambiente real que por acaso mede 1,829 × 2,438 e declara a própria
    # pegada: só a caixa, e a caixa corrobora, nunca decide.
    a = espaco("A", "Área de serviço", pavimento(), ponto=(5.56, -25.12, 0.0))
    areas["A"] = 4.46
    medidas["A"] = CAIXA
    triagem = ea.triar(modelo_espacos(a))
    assert [x.global_id for x in triagem.populacao] == ["A"]
    amb = ea.listar(modelo_espacos(a))[0]
    assert list(ea.sinais_de_fantasma([(amb, CAIXA, None)])["A"]) == [ea.CAIXA_PADRAO]


# --- Dois sinais: sai da população, e sai reportado --------------------------

def test_dois_sinais_retiram_e_reportam_com_a_causa(dados):
    areas, medidas = dados
    tipo = pavimento()
    real = espaco("R", "Sala de Estar / Jantar", tipo, ponto=(0.86, -19.29, 0.0))
    # Fantasmas na origem: Sala (S1+S2+S3) e Cozinha (S1+S3, razão 1,088).
    sala = espaco("F1", "Sala de Estar / Jantar", tipo)
    cozinha = espaco("F2", "Cozinha", tipo)
    areas.update({"R": 18.13, "F1": 18.13, "F2": 4.85})
    medidas.update({"R": _medida(4.735, 3.83), "F1": CAIXA, "F2": CAIXA})

    triagem = ea.triar(modelo_espacos(real, sala, cozinha))
    assert [x.global_id for x in triagem.populacao] == ["R"]
    fora = _fora(triagem)
    assert set(fora) == {"F1", "F2"}
    assert fora["F1"]["sinais"] == sorted([ea.SOBREPOSICAO, ea.PEGADA_X_AREA,
                                           ea.CAIXA_PADRAO])
    assert fora["F2"]["sinais"] == sorted([ea.SOBREPOSICAO, ea.CAIXA_PADRAO])
    assert fora["F1"]["valores"][ea.PEGADA_X_AREA]["razao"] == pytest.approx(4.065, abs=1e-3)
    assert fora["F1"]["valores"][ea.SOBREPOSICAO]["ambientes_no_ponto"] == 2
    assert fora["F1"]["area_declarada_m2"] == 18.13
    assert fora["F1"]["area_footprint_m2"] == 4.46
    assert "caixa padrão" in fora["F2"]["causa"]
    assert "2 ambiente(s) deixados de fora" in triagem.nota()
    assert "erro de exportação" in triagem.nota()   # texto de tela sem ADR (ADR-034)


def test_modelo_sem_espacos_ou_opaco_devolve_triagem_vazia():
    assert ea.triar(None) == ea.Triagem()
    assert ea.triar(object()) == ea.Triagem()
