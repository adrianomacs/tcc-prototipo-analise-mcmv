"""ADR-004 — o Empreendimento como raiz de agregado, e o que ele NÃO pode fazer.

O que se prende aqui, em ordem de importância:

1. **A versão só anda por mudança real.** É o que se usa para dizer
   "este relatório está desatualizado"; uma versão que andasse sem mudança (ou
   não andasse com ela) tornaria essa pergunta falsa nos dois sentidos.
2. **Identidade por ``id``**, não por conteúdo: dois empreendimentos com os mesmos
   dados continuam sendo dois.
3. **O anel de domínio não faz I/O** — nem o ``Empreendimento``, nem a regra de
   distância depois do D1.
"""

from __future__ import annotations

import ast
import os

import pytest

from core.dominio.edificacao import Edificacao
from core.dominio.empreendimento import Empreendimento, Localizacao, ModeloBIM
from core.dominio.terreno import Terreno
from core.dominio.unidade_tipo import UnidadeTipo
from core.dominio.vocabulario import declaracoes as dec
from tests.conftest import RAIZ


def _terreno(lat=-29.5, lon=-51.96):
    return Terreno(origem="mapa", nivel="ponto", precisao="declarada",
                   crs_metrico="EPSG:31982", centro_wgs84=(lat, lon))


# ---------------------------------------------------------------------------
# Localizacao (VO)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("codigo", ["", "430780", "43078071", "43O7807", None])
def test_localizacao_exige_codigo_ibge_de_sete_digitos(codigo):
    with pytest.raises(ValueError):
        Localizacao(codigo_ibge=codigo)


def test_localizacao_e_imutavel_e_normaliza_espacos():
    loc = Localizacao(codigo_ibge=" 4307807 ", uf=" RS", municipio="Estrela ")
    assert (loc.codigo_ibge, loc.uf, loc.municipio) == ("4307807", "RS", "Estrela")
    with pytest.raises(Exception):
        loc.codigo_ibge = "3549904"


def test_localizacao_das_declaracoes_e_o_codigo_explicito_vence():
    declaracoes = {dec.UF: "RS", dec.MUNICIPIO: "Estrela",
                   dec.MUNICIPIO_IBGE: "4307807"}
    assert Localizacao.de_declaracoes(declaracoes).codigo_ibge == "4307807"
    assert Localizacao.de_declaracoes(declaracoes, "3549904").codigo_ibge == "3549904"
    assert Localizacao.de_declaracoes({}) is None
    assert Localizacao.de_declaracoes(None) is None


# ---------------------------------------------------------------------------
# Identidade e versão
# ---------------------------------------------------------------------------

def test_id_gerado_curto_e_identidade_por_id():
    a, b = Empreendimento(nome="X"), Empreendimento(nome="X")
    assert len(a.id) == 12 and a.id != b.id
    assert a != b, "mesmos dados não fazem o mesmo empreendimento"
    assert a == Empreendimento(id=a.id, nome="outro nome")
    assert len({a, b, Empreendimento(id=a.id)}) == 2


def test_cada_mudanca_incrementa_a_versao():
    e = Empreendimento()
    assert e.versao == 1
    e.renomear("Estrela I")
    e.localizar(Localizacao("4307807", "RS", "Estrela"))
    e.declarar({dec.TIPOLOGIA: dec.CASA})
    e.definir_terreno(_terreno())
    e.prever_unidades(12)
    assert e.versao == 6


def test_repetir_o_mesmo_valor_nao_incrementa_a_versao():
    """Reconfirmar o que já está lá não é mudança — senão todo rerun do
    Streamlit deixaria os relatórios "desatualizados"."""
    e = Empreendimento(localizacao=Localizacao("4307807"), terreno=_terreno(),
                       declaracoes={dec.ARRANJO: dec.CONDOMINIO})
    e.localizar(Localizacao("4307807"))
    e.definir_terreno(_terreno())
    e.declarar({dec.ARRANJO: dec.CONDOMINIO})
    assert e.versao == 1


def test_codigo_ibge_e_referencia():
    e = Empreendimento(localizacao=Localizacao("4307807"))
    assert e.codigo_ibge == "4307807"
    assert Empreendimento().codigo_ibge == ""
    assert e.referencia() == {"id": e.id, "versao": 1}


# ---------------------------------------------------------------------------
# Serialização (sem I/O)
# ---------------------------------------------------------------------------

def test_ida_e_volta_preserva_identidade_versao_e_partes():
    e = Empreendimento(nome="Estrela I", localizacao=Localizacao("4307807", "RS", "Estrela"),
                       declaracoes={dec.TIPOLOGIA: dec.CASA,
                                    dec.ARRANJO: dec.CONDOMINIO},
                       terreno=_terreno(),
                       unidades_tipo=[UnidadeTipo(
                           nome="Torre A", unidades=4, tipologia=dec.CASA,
                           modelo=ModeloBIM(caminho="a.ifc", schema="IFC4",
                                            natureza=dec.EDIFICACAO_ISOLADA))])
    e.renomear("Estrela I — lote 2")
    volta = Empreendimento.from_dict(e.to_dict())
    assert volta == e and volta.versao == e.versao == 2
    assert volta.to_dict() == e.to_dict()


def test_partes_opcionais_ausentes_viajam_como_none():
    d = Empreendimento().to_dict()
    assert d["localizacao"] is None and d["terreno"] is None
    assert "modelo" not in d, "o contêiner saiu do empreendimento (ADR-023, DT-10)"
    volta = Empreendimento.from_dict(d)
    assert volta.localizacao is None and volta.terreno is None


def test_a_chave_modelo_de_um_artefato_antigo_e_ignorada_pelo_dominio():
    """Reconhecer o contêiner legado é trabalho da MIGRAÇÃO, na persistência
    (ADR-021): o domínio não guarda o que deixou de ser seu, e não tem onde."""
    d = Empreendimento(nome="Estrela I").to_dict()
    d["modelo"] = {"caminho": "m.ifc", "natureza": dec.TERRENO}
    volta = Empreendimento.from_dict(d)
    assert volta.nome == "Estrela I"
    assert not hasattr(volta, "modelo")
    assert "modelo" not in volta.to_dict()


# ---------------------------------------------------------------------------
# Anel de domínio: nada de I/O
# ---------------------------------------------------------------------------

PROIBIDOS_NO_DOMINIO = {"os", "json", "csv", "yaml", "urllib", "ifcopenshell",
                        "ifctester", "geopandas", "tempfile", "pathlib"}


def _imports_e_chamadas(caminho: str) -> tuple[set[str], set[str]]:
    with open(caminho, encoding="utf-8") as f:
        arvore = ast.parse(f.read())
    modulos, chamadas = set(), set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            modulos |= {a.name.split(".")[0] for a in no.names}
        elif isinstance(no, ast.ImportFrom) and no.module and not no.level:
            modulos.add(no.module.split(".")[0])
        elif isinstance(no, ast.Call) and isinstance(no.func, ast.Name):
            chamadas.add(no.func.id)
    return modulos, chamadas


def test_empreendimento_nao_faz_io():
    modulos, chamadas = _imports_e_chamadas(
        os.path.join(RAIZ, "core", "dominio", "empreendimento.py"))
    assert not (modulos & PROIBIDOS_NO_DOMINIO), modulos & PROIBIDOS_NO_DOMINIO
    assert "open" not in chamadas


def test_regra_de_distancia_nao_abre_arquivo_D1():
    """O defeito D1, preso: a regra pergunta ao contexto, não ao disco."""
    modulos, chamadas = _imports_e_chamadas(
        os.path.join(RAIZ, "core", "regras", "base", "distancia_equipamento.py"))
    assert not (modulos & {"os", "json", "csv", "pathlib"}), modulos
    assert "open" not in chamadas


# ---------------------------------------------------------------------------
# O interior do agregado: unidades tipo e os três números de UH (ADR-023/ADR-021)
# ---------------------------------------------------------------------------

def _unidade_tipo(nome="Torre A", unidades=64, representadas=4, tipologia=dec.APARTAMENTO):
    """Uma unidade tipo com contêiner; ``representadas=None`` para uma sem."""
    modelo = (None if representadas is None
              else ModeloBIM(caminho=f"{nome}.ifc", natureza=dec.EDIFICACAO_ISOLADA,
                             unidades_representadas=representadas))
    return UnidadeTipo(nome=nome, unidades=unidades, tipologia=tipologia, modelo=modelo)


def test_empreendimento_nasce_sem_unidades_tipo_e_sem_previsao():
    e = Empreendimento()
    assert e.unidades_tipo == [] and e.unidades_previstas == 0
    assert e.unidades_declaradas == 0


# -- invariante 1: cada UH pertence a exatamente uma unidade tipo ------------

def test_a_mesma_unidade_tipo_nao_entra_duas_vezes():
    """Repetir a unidade tipo contaria as mesmas UHs duas vezes na soma, e o
    confronto com ``unidades_previstas`` acusaria inconsistência onde não há."""
    e, torre = Empreendimento(), _unidade_tipo()
    e.acrescentar_unidade_tipo(torre)
    with pytest.raises(ValueError):
        e.acrescentar_unidade_tipo(torre)
    assert e.unidades_declaradas == 64


def test_colecao_com_repeticao_e_recusada_na_construcao_e_na_troca():
    torre = _unidade_tipo()
    with pytest.raises(ValueError):
        Empreendimento(unidades_tipo=[torre, torre])
    e = Empreendimento()
    with pytest.raises(ValueError):
        e.definir_unidades_tipo([torre, torre])
    assert e.unidades_tipo == []


def test_unidades_tipo_semelhantes_mas_distintas_convivem():
    """Recusar a repetição não é recusar a semelhança: quatro torres iguais
    apontando para o mesmo contêiner são quatro unidades tipo (ADR-023)."""
    e = Empreendimento()
    for i in range(4):
        e.acrescentar_unidade_tipo(_unidade_tipo(nome=f"Torre {i}", unidades=16,
                                             representadas=16))
    assert len(e.unidades_tipo) == 4 and e.unidades_declaradas == 64


def test_remover_unidade_tipo_tira_as_uhs_dela_da_soma():
    e = Empreendimento()
    a, b = _unidade_tipo(nome="A", unidades=10), _unidade_tipo(nome="B", unidades=6)
    e.definir_unidades_tipo([a, b])
    assert e.remover_unidade_tipo(a.id) is True
    assert e.unidades_tipo == [b] and e.unidades_declaradas == 6
    assert e.remover_unidade_tipo("inexistente") is False


# -- invariante 2: sem ModeloBIM não há checagem BIM naquela unidade tipo ----

def test_unidade_tipo_sem_conteiner_nao_impede_as_outras():
    e = Empreendimento()
    com = _unidade_tipo(nome="Bloco 1", unidades=8, representadas=4)
    sem = _unidade_tipo(nome="Bloco 2", unidades=8, representadas=None)
    e.definir_unidades_tipo([com, sem])
    assert [x.checavel_por_bim for x in e.unidades_tipo] == [True, False]
    assert e.unidades_declaradas == 16, "declarar UH não exige entregar modelo"


# -- invariante 3: a soma confrontada com unidades_previstas -----------------

def test_soma_menor_ou_igual_a_previsao_e_consistente():
    e = Empreendimento(unidades_previstas=100)
    e.definir_unidades_tipo([_unidade_tipo(nome="A", unidades=64),
                           _unidade_tipo(nome="B", unidades=36)])
    assert e.unidades_declaradas == 100
    assert e.excedente_declarado == 0 and e.declaracao_consistente is True


def test_soma_maior_que_a_previsao_e_inconsistencia_declaratoria():
    """Declaração × declaração, não declarado × medido (ADR-022)."""
    e = Empreendimento(unidades_previstas=100)
    e.definir_unidades_tipo([_unidade_tipo(nome="A", unidades=64),
                           _unidade_tipo(nome="B", unidades=48)])
    assert e.excedente_declarado == 12 and e.declaracao_consistente is False


def test_sem_previsao_declarada_nao_ha_inconsistencia():
    """Ausência de declaração não é declaração que se contradiz."""
    e = Empreendimento()
    e.acrescentar_unidade_tipo(_unidade_tipo(unidades=64))
    assert e.unidades_previstas == 0
    assert e.excedente_declarado == 0 and e.declaracao_consistente is True


def test_unidades_previstas_e_contagem_nao_negativa():
    e = Empreendimento()
    e.prever_unidades("100")
    assert e.unidades_previstas == 100
    with pytest.raises(ValueError):
        e.prever_unidades(-1)
    with pytest.raises(ValueError):
        Empreendimento(unidades_previstas="cem")


def test_previsao_nao_e_denominador_de_nada():
    """``unidades_previstas`` não escala regra: o número que a regra consome é
    o do contêiner lido, e os dois são livres para divergir (ADR-021)."""
    e = Empreendimento(unidades_previstas=100)
    torre = _unidade_tipo(nome="Torre A", unidades=64, representadas=4)
    e.acrescentar_unidade_tipo(torre)
    assert (e.unidades_previstas, torre.unidades, torre.unidades_representadas) \
        == (100, 64, 4)


def test_as_duas_formas_de_quatro_torres_iguais_dao_o_mesmo_diagnostico():
    """ADR-023: quatro unidades tipo para o mesmo
    contêiner, ou uma de 64 unidades com um contêiner de 4 — exprimíveis as
    duas, e equivalentes."""
    conteiner = ModeloBIM(caminho="tipo.ifc", natureza=dec.EDIFICACAO_ISOLADA,
                          unidades_representadas=4)
    quatro = Empreendimento(unidades_previstas=64)
    quatro.definir_unidades_tipo([UnidadeTipo(nome=f"Torre {i}", unidades=16,
                                           tipologia=dec.APARTAMENTO, modelo=conteiner)
                                for i in range(4)])
    uma = Empreendimento(unidades_previstas=64)
    uma.acrescentar_unidade_tipo(UnidadeTipo(nome="Torre única", unidades=64,
                                          tipologia=dec.APARTAMENTO, modelo=conteiner))
    assert quatro.unidades_declaradas == uma.unidades_declaradas == 64
    assert quatro.excedente_declarado == uma.excedente_declarado == 0
    assert {e.unidades_representadas for e in quatro.unidades_tipo} == {4}
    assert uma.unidades_tipo[0].unidades_representadas == 4


# -- a versão, do lado das unidades tipo ------------------------------------

def test_mexer_na_colecao_de_unidades_tipo_incrementa_a_versao():
    e = Empreendimento()
    e.prever_unidades(100)
    e.acrescentar_unidade_tipo(_unidade_tipo(nome="A"))
    e.remover_unidade_tipo(e.unidades_tipo[0].id)
    assert e.versao == 4


def test_repetir_a_mesma_colecao_nao_incrementa_a_versao():
    a = _unidade_tipo(nome="A")
    e = Empreendimento(unidades_tipo=[a], unidades_previstas=100)
    e.definir_unidades_tipo([a])
    e.prever_unidades(100)
    assert e.versao == 1


def test_unidade_tipo_com_o_mesmo_id_mas_conteudo_novo_faz_a_versao_andar():
    """A igualdade de ``UnidadeTipo`` é por identidade; se a coleção fosse
    comparada por ela, renomear ou anexar contêiner passaria despercebido — e a
    versão pararia de andar justo quando o relatório gravado ficou velho."""
    a = _unidade_tipo(nome="A", unidades=10, representadas=None)
    e = Empreendimento(unidades_tipo=[a])
    renomeada = UnidadeTipo(id=a.id, nome="A — bloco norte", unidades=10,
                           tipologia=a.tipologia)
    assert e.atualizar_unidade_tipo(renomeada) is True
    assert e.versao == 2 and e.unidades_tipo[0].nome == "A — bloco norte"


def test_atualizar_unidade_tipo_ausente_nao_inventa_nem_versiona():
    e = Empreendimento(unidades_tipo=[_unidade_tipo(nome="A")])
    assert e.atualizar_unidade_tipo(_unidade_tipo(nome="B")) is False
    assert len(e.unidades_tipo) == 1 and e.versao == 1


def test_mudar_unidade_tipo_no_lugar_nao_versiona_e_esta_declarado():
    """Mesma fronteira do ``dict`` de declarações: mutação por fora dos métodos
    do agregado não anda a versão. Registrado para não ser descoberto depois."""
    e = Empreendimento(unidades_tipo=[_unidade_tipo(nome="A")])
    e.unidades_tipo[0].nome = "B"
    assert e.versao == 1


# -- serialização ------------------------------------------------------------

def test_ida_e_volta_preserva_unidades_tipo_e_previsao():
    e = Empreendimento(nome="Estrela I", unidades_previstas=100)
    e.definir_unidades_tipo([_unidade_tipo(nome="A", unidades=64),
                           _unidade_tipo(nome="B", unidades=36, representadas=None)])
    volta = Empreendimento.from_dict(e.to_dict())
    assert volta.to_dict() == e.to_dict()
    assert [x.id for x in volta.unidades_tipo] == [x.id for x in e.unidades_tipo]
    assert volta.unidades_previstas == 100 and volta.unidades_declaradas == 100
    assert volta.unidades_tipo[0].modelo.unidades_representadas == 4
    assert volta.unidades_tipo[1].modelo is None


def test_artefato_sem_unidades_tipo_volta_sem_unidades_tipo():
    """O domínio não inventa o que não foi escrito: sintetizar a unidade tipo
    do artefato antigo é migração, e migração é da persistência (ADR-021)."""
    # "num_uhs" em texto: era chave do esquema E0 (ADR-023), e é da
    # persistência reconhecê-la — o domínio só não pode inventar a partir dela.
    antigo = {"id": "abc123abc123", "nome": "Estrela I", "versao": 3,
              "declaracoes": {dec.TIPOLOGIA: dec.CASA, "num_uhs": 2}}
    volta = Empreendimento.from_dict(antigo)
    assert volta.unidades_tipo == [] and volta.unidades_previstas == 0
    assert volta.versao == 3


# ---------------------------------------------------------------------------
# A Edificacao FÍSICA e a composição — os invariantes são da raiz (ADR-023)
# ---------------------------------------------------------------------------

def _tipos():
    """"Apto padrão" (100) e "Apto PCD" (20), apartamento; "Casa" (1), casa."""
    padrao = UnidadeTipo(nome="Apto padrão", unidades=100, tipologia=dec.APARTAMENTO)
    pcd = UnidadeTipo(nome="Apto PCD", unidades=20, tipologia=dec.APARTAMENTO)
    casa = UnidadeTipo(nome="Casa", unidades=1, tipologia=dec.CASA)
    return padrao, pcd, casa


def _com_tipos(previstas=0):
    padrao, pcd, casa = _tipos()
    return Empreendimento(unidades_previstas=previstas,
                          unidades_tipo=[padrao, pcd, casa]), padrao, pcd, casa


def test_empreendimento_nasce_sem_edificacoes():
    e = Empreendimento()
    assert e.edificacoes == []
    assert "edificacoes" in e.to_dict() and e.to_dict()["edificacoes"] == []


def test_a_edificacao_e_opcional_o_loteamento_nao_enumera_predios():
    """Caso 1 do ADR-023: 150 casas, uma unidade tipo, nenhuma edificação."""
    e = Empreendimento(unidades_previstas=150)
    e.acrescentar_unidade_tipo(UnidadeTipo(nome="Casa padrão", unidades=150,
                                           tipologia=dec.CASA))
    assert e.edificacoes == [] and e.unidades_declaradas == 150
    assert e.declaracao_consistente is True


def test_caso_3_duas_torres_com_composicao():
    """Caso 3 do ADR-023: 2 torres × 60 UH, 10 PCD por torre."""
    e, padrao, pcd, _ = _com_tipos(previstas=120)
    torre_a = Edificacao(nome="Torre A", composicao={padrao.id: 50, pcd.id: 10})
    torre_b = Edificacao(nome="Torre B", composicao={padrao.id: 50, pcd.id: 10})
    e.definir_edificacoes([torre_a, torre_b])
    assert e.tipologia_de(torre_a) == e.tipologia_de(torre_b) == dec.APARTAMENTO
    assert e.unidades_compostas(padrao) == 100 and e.unidades_compostas(pcd) == 20
    assert e.unidades_compostas(padrao.id) == 100, "aceita o id também"
    assert torre_a.unidades_compostas == 60


# -- invariante 1: a composição só cita unidades tipo do agregado ------------

def test_composicao_que_cita_tipo_estranho_e_recusada_em_todo_caminho():
    e, padrao, _, _ = _com_tipos()
    estranha = Edificacao(nome="X", composicao={padrao.id: 1, "zzz": 1})
    with pytest.raises(ValueError):
        e.acrescentar_edificacao(estranha)
    with pytest.raises(ValueError):
        e.definir_edificacoes([estranha])
    with pytest.raises(ValueError):
        Empreendimento(unidades_tipo=[padrao], edificacoes=[estranha])
    assert e.edificacoes == [] and e.versao == 1


def test_composicao_vazia_e_legitima_e_a_tipologia_e_ausencia():
    """Caso 6: física declarada sem composição. ``""`` é ausência — o guard
    não bloqueia; quem nomeia "tipologia indeterminada" é o diagnóstico."""
    e, *_ = _com_tipos()
    vazia = Edificacao(nome="Galpão")
    e.acrescentar_edificacao(vazia)
    assert e.tipologia_de(vazia) == "" and vazia.unidades_compostas == 0


# -- invariante 2: os tipos citados têm uma única tipologia -------------------

def test_composicao_mista_casa_e_apartamento_e_recusada():
    """Um prédio casa + apartamento não existe na Portaria (ADR-023)."""
    e, padrao, _, casa = _com_tipos()
    with pytest.raises(ValueError):
        e.acrescentar_edificacao(Edificacao(nome="mista",
                                            composicao={padrao.id: 1, casa.id: 1}))
    with pytest.raises(ValueError):
        Empreendimento(unidades_tipo=[padrao, casa], edificacoes=[
            Edificacao(nome="mista", composicao={padrao.id: 1, casa.id: 1})])


def test_dois_tipos_da_mesma_tipologia_compoem_o_mesmo_predio():
    """"Padrão" e "PCD" são duas unidades tipo da MESMA tipologia — é
    exatamente o que a separação tipologia × unidade tipo permite dizer."""
    e, padrao, pcd, _ = _com_tipos()
    e.acrescentar_edificacao(Edificacao(nome="Torre A",
                                        composicao={padrao.id: 50, pcd.id: 10}))
    assert e.tipologia_de(e.edificacoes[0]) == dec.APARTAMENTO


def test_mudar_a_tipologia_de_um_tipo_composto_nao_pode_tornar_o_predio_misto():
    """O invariante vale nos dois sentidos: também quem muda o tipo é recusado."""
    e, padrao, pcd, _ = _com_tipos()
    e.acrescentar_edificacao(Edificacao(nome="Torre A",
                                        composicao={padrao.id: 50, pcd.id: 10}))
    versao = e.versao
    with pytest.raises(ValueError):
        e.atualizar_unidade_tipo(UnidadeTipo(id=pcd.id, nome="Casa PCD",
                                             unidades=20, tipologia=dec.CASA))
    assert e.versao == versao and e.unidade_tipo_por_id(pcd.id).tipologia == (
        dec.APARTAMENTO)


# -- o cascade: remover um tipo limpa as composições que o citam -------------

def test_remover_tipo_limpa_as_composicoes_e_a_versao_anda_uma_vez():
    e, padrao, pcd, _ = _com_tipos()
    torre = Edificacao(nome="Torre A", composicao={padrao.id: 50, pcd.id: 10})
    e.acrescentar_edificacao(torre)
    versao = e.versao
    assert e.remover_unidade_tipo(pcd.id) is True
    assert e.versao == versao + 1
    assert e.edificacoes[0].composicao == {padrao.id: 50}
    assert e.edificacoes[0].id == torre.id, "é a mesma edificação"
    assert e.unidades_compostas(pcd) == 0


def test_substituir_a_colecao_de_tipos_tambem_faz_o_cascade():
    e, padrao, pcd, casa = _com_tipos()
    e.acrescentar_edificacao(Edificacao(nome="Torre A",
                                        composicao={padrao.id: 50, pcd.id: 10}))
    e.definir_unidades_tipo([padrao, casa])
    assert e.edificacoes[0].composicao == {padrao.id: 50}


def test_remover_edificacao_nao_cai_em_cascata_sobre_os_tipos():
    e, padrao, pcd, _ = _com_tipos()
    torre = Edificacao(nome="Torre A", composicao={padrao.id: 50, pcd.id: 10})
    e.acrescentar_edificacao(torre)
    assert e.remover_edificacao(torre.id) is True
    assert e.edificacoes == [] and len(e.unidades_tipo) == 3
    assert e.remover_edificacao("inexistente") is False


# -- a segunda aritmética (ADR-022): diagnóstico, nunca exceção --------------

def test_composicao_maior_que_as_unidades_do_tipo_e_diagnostico():
    """Declaração incompleta é legítima; números que não fecham são
    diagnóstico (ADR-022), e a raiz só faz a conta."""
    e, padrao, pcd, _ = _com_tipos(previstas=121)
    e.definir_edificacoes([Edificacao(nome="Torre A", composicao={padrao.id: 70}),
                           Edificacao(nome="Torre B", composicao={padrao.id: 70})])
    assert e.unidades_compostas(padrao) == 140
    assert e.excedente_composto(padrao) == 40 and e.excedente_composto(pcd) == 0
    assert e.excedente_declarado == 0, "a primeira aritmética fecha"
    assert e.declaracao_consistente is False, "a segunda não"
    assert e.excedente_composto("inexistente") == 0


def test_composicao_menor_que_as_unidades_do_tipo_nao_e_inconsistencia():
    """Só a Torre A declarada, a B ainda não: composição < unidades é
    declaração incompleta, não contradição."""
    e, padrao, pcd, _ = _com_tipos(previstas=121)
    e.acrescentar_edificacao(Edificacao(nome="Torre A",
                                        composicao={padrao.id: 50, pcd.id: 10}))
    assert e.excedente_composto(padrao) == 0 and e.declaracao_consistente is True


# -- a versão, do lado das edificações ---------------------------------------

def test_mexer_na_colecao_de_edificacoes_incrementa_a_versao():
    e, padrao, _, _ = _com_tipos()
    torre = Edificacao(nome="Torre A", composicao={padrao.id: 50})
    e.acrescentar_edificacao(torre)
    assert e.atualizar_edificacao(Edificacao(id=torre.id, nome="Torre A — norte",
                                             composicao={padrao.id: 50})) is True
    e.remover_edificacao(torre.id)
    assert e.versao == 4
    assert e.atualizar_edificacao(Edificacao(nome="B")) is False and e.versao == 4


def test_repetir_a_mesma_edificacao_nao_incrementa_a_versao():
    e, padrao, _, _ = _com_tipos()
    torre = Edificacao(nome="Torre A", composicao={padrao.id: 50})
    e.definir_edificacoes([torre])
    versao = e.versao
    e.definir_edificacoes([torre])
    e.atualizar_edificacao(torre)
    assert e.versao == versao


def test_a_mesma_edificacao_nao_entra_duas_vezes():
    e, padrao, _, _ = _com_tipos()
    torre = Edificacao(nome="Torre A", composicao={padrao.id: 50})
    e.acrescentar_edificacao(torre)
    with pytest.raises(ValueError):
        e.acrescentar_edificacao(torre)
    with pytest.raises(ValueError):
        Empreendimento(unidades_tipo=[padrao], edificacoes=[torre, torre])


def test_a_serializacao_copia_a_composicao_e_nao_a_compartilha():
    """Mesma regra das ``declaracoes`` em ``to_dict``: o ``dict`` gravado ou
    reconstruído não é o do objeto vivo."""
    e, padrao, _, _ = _com_tipos()
    torre = Edificacao(nome="Torre A", composicao={padrao.id: 50})
    e.acrescentar_edificacao(torre)
    volta = Edificacao.from_dict(torre.to_dict())
    volta.composicao[padrao.id] = 1
    assert torre.composicao == {padrao.id: 50}
    assert torre.to_dict()["composicao"] is not torre.composicao


# -- serialização ------------------------------------------------------------

def test_ida_e_volta_preserva_edificacoes_e_composicao():
    e, padrao, pcd, _ = _com_tipos(previstas=120)
    e.definir_edificacoes([
        Edificacao(nome="Torre A", composicao={padrao.id: 50, pcd.id: 10},
                   modelo=ModeloBIM(caminho="misto.ifc", unidades_representadas=6)),
        Edificacao(nome="Torre B", composicao={padrao.id: 50, pcd.id: 10})])
    volta = Empreendimento.from_dict(e.to_dict())
    assert volta.to_dict() == e.to_dict()
    assert [x.id for x in volta.edificacoes] == [x.id for x in e.edificacoes]
    assert volta.tipologia_de(volta.edificacoes[1]) == dec.APARTAMENTO
    assert volta.edificacoes[0].modelo.unidades_representadas == 6
    assert volta.unidades_compostas(padrao) == 100


def test_a_chave_edificacoes_do_esquema_do_adr020_e_lida_como_fisica_pelo_dominio():
    """O domínio lê a chave pelo que ela significa hoje; reconhecer o esquema
    E1 e mover os itens para ``unidades_tipo`` é da persistência (ADR-023)."""
    antigo = {"id": "abc123abc123", "nome": "Estrela I", "versao": 57,
              "unidades_previstas": 120,
              "edificacoes": [{"id": "d6ff0051603f", "nome": "Bloco A",
                               "unidades": 60, "tipologia": dec.APARTAMENTO,
                               "modelo": None}]}
    volta = Empreendimento.from_dict(antigo)
    assert volta.unidades_tipo == [] and volta.unidades_declaradas == 0
    assert [(x.id, x.nome, x.composicao) for x in volta.edificacoes] == [
        ("d6ff0051603f", "Bloco A", {})]
