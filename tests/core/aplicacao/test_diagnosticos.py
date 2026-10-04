"""ADR-023 (D-K) — os cinco diagnósticos, que marcam e não reprovam.

O que estes testes prendem, antes de qualquer número: **nenhum diagnóstico é
veredito**. Eles vivem em ``meta``, têm rótulo próprio e não tocam a taxonomia
do ADR-006/022 — é por isso que o teste do rótulo está aqui junto dos da
aritmética, e não à parte.

Depois, a aritmética de cada um, nos casos que o desenho da ``UnidadeTipo``
nomeia: a extrapolação legítima de sempre (caso 1), o pavimento tipo misto
(caso 3), a edificação sem composição (caso 6) e o empreendimento só com
terreno (caso 7).
"""

from __future__ import annotations

from core.aplicacao import diagnosticos as diag
from core.dominio.edificacao import Edificacao
from core.dominio.empreendimento import Empreendimento
from core.dominio.modelo_bim import ModeloBIM
from core.dominio.terreno import Terreno
from core.dominio.unidade_tipo import UnidadeTipo
from core.dominio.vocabulario import declaracoes as dec
from core.dominio.vocabulario import motivos


def _conteiner(uhs=1, caminho="a.ifc", natureza=dec.EDIFICACAO_ISOLADA):
    return ModeloBIM(caminho=caminho, natureza=natureza,
                     unidades_representadas=uhs)


def _terreno(modelo=None):
    return Terreno(origem="mapa", nivel="ponto", precisao="declarada",
                   crs_metrico="EPSG:31982", centro_wgs84=(-29.5, -51.96),
                   modelo=modelo)


def _de(diagnosticos, chave):
    (achado,) = [d for d in diagnosticos if d.chave == chave]
    return achado


# --- o que eles NÃO são ----------------------------------------------------

def test_rotulos_proprios_nao_colidem_com_a_taxonomia_do_nao_avaliavel():
    """D-K: rótulo próprio, distinto dos motivos do ADR-006/022.

    Em particular o da inconsistência declaratória, que se chama "números
    declarados não fecham" (D-L) justamente para não ser confundido com o
    motivo homônimo do ADR-022 — que ainda não entrou no vocabulário, e só
    entra com o primeiro emissor.
    """
    constantes = {v for k, v in vars(motivos).items()
                  if k.isupper() and isinstance(v, str)}
    assert set(diag.ROTULO) & constantes == set()
    assert diag.NUMEROS_NAO_FECHAM == "numeros_declarados_nao_fecham"


def test_todos_os_cinco_sempre_aparecem_com_marcado():
    """Um diagnóstico que some quando não dispara não tem como ser conferido."""
    emp = Empreendimento(unidades_tipo=[UnidadeTipo(nome="T", unidades=1,
                                                    tipologia=dec.CASA)])
    cinco = diag.avaliar(emp, None)
    assert [d.chave for d in cinco] == [
        diag.EXTRAPOLACAO, diag.COBERTURA_DA_ANALISE, diag.NUMEROS_NAO_FECHAM,
        diag.HETEROGENEIDADE, diag.TIPOLOGIA_INDETERMINADA]
    assert all(isinstance(d.marcado, bool) for d in cinco)


# --- extrapolação ----------------------------------------------------------

def test_extrapolacao_e_o_caso_1_do_plano():
    """150 casas declaradas, um IFC que representa 1: a submissão normal."""
    conteiner = _conteiner(uhs=1)
    tipo = UnidadeTipo(nome="Casa padrão", unidades=150, tipologia=dec.CASA,
                       modelo=conteiner)
    emp = Empreendimento(unidades_tipo=[tipo])
    achado = _de(diag.avaliar(emp, conteiner), diag.EXTRAPOLACAO)
    assert achado.marcado
    assert achado.valores == {"unidades_do_dono": 150,
                              "unidades_representadas": 1}


def test_sem_extrapolacao_quando_o_modelo_representa_tudo():
    conteiner = _conteiner(uhs=4)
    tipo = UnidadeTipo(nome="Casa", unidades=4, tipologia=dec.CASA,
                       modelo=conteiner)
    emp = Empreendimento(unidades_tipo=[tipo])
    assert not _de(diag.avaliar(emp, conteiner), diag.EXTRAPOLACAO).marcado


def test_as_quatro_torres_iguais_somam_como_uma_de_64():
    """ADR-023: as duas formas são equivalentes, e o diagnóstico não as separa."""
    conteiner = _conteiner(uhs=4)
    quatro = [UnidadeTipo(nome=f"Torre {i}", unidades=16,
                          tipologia=dec.APARTAMENTO, modelo=conteiner)
              for i in "ABCD"]
    uma = [UnidadeTipo(nome="Torres", unidades=64, tipologia=dec.APARTAMENTO,
                       modelo=conteiner)]
    assert (diag.unidades_do_dono(Empreendimento(unidades_tipo=quatro), conteiner)
            == diag.unidades_do_dono(Empreendimento(unidades_tipo=uma), conteiner)
            == 64)


def test_dono_edificacao_fala_pela_soma_da_composicao():
    conteiner = _conteiner(uhs=6)
    padrao = UnidadeTipo(nome="Apto padrão", unidades=100,
                         tipologia=dec.APARTAMENTO)
    pcd = UnidadeTipo(nome="Apto PCD", unidades=20, tipologia=dec.APARTAMENTO)
    torre = Edificacao(nome="Torre A", modelo=conteiner,
                       composicao={padrao.id: 50, pcd.id: 10})
    emp = Empreendimento(unidades_tipo=[padrao, pcd], edificacoes=[torre])
    achado = _de(diag.avaliar(emp, conteiner), diag.EXTRAPOLACAO)
    assert achado.valores["unidades_do_dono"] == 60
    assert achado.marcado


# --- cobertura desta análise ----------------------------------------------

def test_cobertura_da_analise_e_a_fatia_do_previsto():
    conteiner = _conteiner(uhs=1)
    tipo = UnidadeTipo(nome="Casa padrão", unidades=140, tipologia=dec.CASA,
                       modelo=conteiner)
    emp = Empreendimento(unidades_previstas=150, unidades_tipo=[tipo])
    achado = _de(diag.avaliar(emp, conteiner), diag.COBERTURA_DA_ANALISE)
    assert achado.marcado
    assert achado.valores["cobertura"] == 140 / 150


def test_sem_previsao_declarada_a_cobertura_e_indefinida_e_nao_zero():
    """Ausência de declaração não é cobertura zero."""
    conteiner = _conteiner(uhs=1)
    tipo = UnidadeTipo(nome="Casa", unidades=10, tipologia=dec.CASA,
                       modelo=conteiner)
    achado = _de(diag.avaliar(Empreendimento(unidades_tipo=[tipo]), conteiner),
                 diag.COBERTURA_DA_ANALISE)
    assert achado.valores["cobertura"] is None
    assert not achado.marcado


def test_cobertura_total_nao_marca():
    conteiner = _conteiner(uhs=1)
    tipo = UnidadeTipo(nome="Casa", unidades=150, tipologia=dec.CASA,
                       modelo=conteiner)
    emp = Empreendimento(unidades_previstas=150, unidades_tipo=[tipo])
    assert not _de(diag.avaliar(emp, conteiner),
                   diag.COBERTURA_DA_ANALISE).marcado


# --- números declarados não fecham (ADR-022, D-L) --------------------------

def test_soma_dos_tipos_maior_que_o_previsto():
    emp = Empreendimento(
        unidades_previstas=100,
        unidades_tipo=[UnidadeTipo(nome="A", unidades=80, tipologia=dec.CASA),
                       UnidadeTipo(nome="B", unidades=40, tipologia=dec.CASA)])
    achado = _de(diag.avaliar(emp, None), diag.NUMEROS_NAO_FECHAM)
    assert achado.marcado
    assert achado.valores["excedente_declarado"] == 20


def test_composicao_maior_que_as_unidades_do_tipo():
    tipo = UnidadeTipo(nome="Apto", unidades=10, tipologia=dec.APARTAMENTO)
    torre = Edificacao(nome="Torre", composicao={tipo.id: 30})
    emp = Empreendimento(unidades_tipo=[tipo], edificacoes=[torre])
    achado = _de(diag.avaliar(emp, None), diag.NUMEROS_NAO_FECHAM)
    assert achado.marcado
    assert achado.valores["excedente_composto"] == {tipo.id: 20}


def test_declaracao_que_fecha_nao_marca():
    emp = Empreendimento(
        unidades_previstas=150,
        unidades_tipo=[UnidadeTipo(nome="A", unidades=140, tipologia=dec.CASA),
                       UnidadeTipo(nome="B", unidades=10, tipologia=dec.CASA)])
    assert not _de(diag.avaliar(emp, None), diag.NUMEROS_NAO_FECHAM).marcado


# --- heterogeneidade -------------------------------------------------------

def test_heterogeneidade_e_o_caso_3_do_plano():
    """Pavimento tipo misto anexado à Torre A: dois tipos num veredito só."""
    conteiner = _conteiner(uhs=6)
    padrao = UnidadeTipo(nome="Apto padrão", unidades=100,
                         tipologia=dec.APARTAMENTO)
    pcd = UnidadeTipo(nome="Apto PCD", unidades=20, tipologia=dec.APARTAMENTO)
    torre = Edificacao(nome="Torre A", modelo=conteiner,
                       composicao={padrao.id: 50, pcd.id: 10})
    emp = Empreendimento(unidades_tipo=[padrao, pcd], edificacoes=[torre])
    achado = _de(diag.avaliar(emp, conteiner), diag.HETEROGENEIDADE)
    assert achado.marcado
    assert achado.valores["unidades_tipo_no_escopo"] == sorted(
        [padrao.id, pcd.id])


def test_caso_2_do_plano_nao_e_heterogeneo():
    """Um IFC por tipo: cada análise é homogênea por construção."""
    conteiner = _conteiner(uhs=1)
    padrao = UnidadeTipo(nome="Casa padrão", unidades=140, tipologia=dec.CASA,
                         modelo=conteiner)
    pcd = UnidadeTipo(nome="Casa PCD", unidades=10, tipologia=dec.CASA)
    emp = Empreendimento(unidades_tipo=[padrao, pcd])
    assert not _de(diag.avaliar(emp, conteiner), diag.HETEROGENEIDADE).marcado


def test_edificacao_de_um_tipo_so_nao_e_heterogenea():
    conteiner = _conteiner(uhs=6)
    tipo = UnidadeTipo(nome="Apto", unidades=100, tipologia=dec.APARTAMENTO)
    torre = Edificacao(nome="Torre", modelo=conteiner,
                       composicao={tipo.id: 60})
    emp = Empreendimento(unidades_tipo=[tipo], edificacoes=[torre])
    assert not _de(diag.avaliar(emp, conteiner), diag.HETEROGENEIDADE).marcado


def test_conteiner_sem_dono_sobre_dois_tipos_e_heterogeneo():
    """"Terreno com as edificações" sem física declarada (D-K, segunda forma)."""
    conteiner = _conteiner(uhs=2, natureza=dec.TERRENO_COM_EDIFICACOES)
    emp = Empreendimento(
        unidades_tipo=[UnidadeTipo(nome="A", unidades=10, tipologia=dec.CASA),
                       UnidadeTipo(nome="B", unidades=10, tipologia=dec.CASA)])
    assert _de(diag.avaliar(emp, conteiner), diag.HETEROGENEIDADE).marcado


# --- tipologia indeterminada (§3) -----------------------------------------

def test_edificacao_sem_composicao_recebendo_arquivo_e_o_caso_6():
    conteiner = _conteiner(uhs=6)
    vazia = Edificacao(nome="Torre sem composição", modelo=conteiner)
    emp = Empreendimento(unidades_tipo=[UnidadeTipo(nome="A", unidades=10,
                                                    tipologia=dec.CASA)],
                         edificacoes=[vazia])
    achado = _de(diag.avaliar(emp, conteiner), diag.TIPOLOGIA_INDETERMINADA)
    assert achado.marcado
    assert achado.valores == {"nivel_do_dono": "edificacoes", "tipologia": ""}


def test_tipo_com_tipologia_nao_marca_indeterminada():
    conteiner = _conteiner(uhs=1)
    tipo = UnidadeTipo(nome="Casa", unidades=1, tipologia=dec.CASA,
                       modelo=conteiner)
    emp = Empreendimento(unidades_tipo=[tipo])
    assert not _de(diag.avaliar(emp, conteiner),
                   diag.TIPOLOGIA_INDETERMINADA).marcado


# --- caso 7: só terreno ----------------------------------------------------

def test_empreendimento_so_com_terreno_nao_marca_nada():
    conteiner = _conteiner(uhs=0, natureza=dec.TERRENO)
    emp = Empreendimento(terreno=_terreno(modelo=conteiner))
    assert not any(d.marcado for d in diag.avaliar(emp, conteiner))


# --- o gate: só as análises que leem UH ------------------------------------

def test_so_diagnostica_quem_consome_unidades_representadas():
    assert diag.consome_unidades_representadas(["EDI-004", "EDI-007"])
    assert not diag.consome_unidades_representadas(["EMP-001"])
    assert not diag.consome_unidades_representadas([])
    assert not diag.consome_unidades_representadas(None)


def test_para_meta_vazio_no_georreferenciamento():
    conteiner = _conteiner(uhs=0, natureza=dec.TERRENO_COM_EDIFICACOES)
    emp = Empreendimento(terreno=_terreno(modelo=conteiner))
    assert diag.para_meta(emp, conteiner, ["EMP-001"]) == []


def test_para_meta_serializa_os_cinco_no_programa():
    conteiner = _conteiner(uhs=1)
    tipo = UnidadeTipo(nome="Casa", unidades=150, tipologia=dec.CASA,
                       modelo=conteiner)
    emp = Empreendimento(unidades_tipo=[tipo])
    registros = diag.para_meta(emp, conteiner, ["EDI-004", "EDI-002"])
    assert len(registros) == 5
    assert set(registros[0]) == {"chave", "rotulo", "marcado", "mensagem",
                                 "valores"}
    assert registros[0]["rotulo"] == diag.ROTULO[diag.EXTRAPOLACAO]
