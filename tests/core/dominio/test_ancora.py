"""ADR-021/ADR-023 — qual unidade tipo, e qual contêiner, a análise está lendo.

São duas perguntas encadeadas, e o que estes testes prendem é a
ordem entre elas: a âncora **recebida** (``Contexto.conteiner``, D2) vence; sem
ela vale a **dedução** a partir do agregado — a unidade tipo em análise e, na
falta dela, o terreno. Os testes de ``tipologia_em_analise`` daqui passam pelo
caminho SEM contêiner (a dedução); a leitura pelos donos do contêiner (ADR-023)
tem testes próprios abaixo. E, nos dois caminhos, uma resposta só: ambiguidade vira
recusa explícita, nunca escolha pela ordem da lista.

O campo legado ``Empreendimento.modelo`` saiu do empreendimento: não há mais
"último recurso" a testar, porque não há mais terceiro lugar onde um contêiner
possa estar escondido.
"""

from __future__ import annotations

from core.dominio import ancora
from core.dominio.contratos.regra import Contexto
from core.dominio.edificacao import Edificacao
from core.dominio.empreendimento import Empreendimento
from core.dominio.modelo_bim import ModeloBIM
from core.dominio.terreno import Terreno
from core.dominio.unidade_tipo import UnidadeTipo
from core.dominio.vocabulario import declaracoes as dec


def _conteiner(uhs=1, caminho="a.ifc"):
    return ModeloBIM(caminho=caminho, natureza=dec.EDIFICACAO_ISOLADA,
                     unidades_representadas=uhs)


def _terreno(modelo=None):
    return Terreno(origem="mapa", nivel="ponto", precisao="declarada",
                   crs_metrico="EPSG:31982", centro_wgs84=(-29.5, -51.96),
                   modelo=modelo)


# --- dedução a partir do agregado -----------------------------------------

def test_sem_unidade_tipo_nao_ha_unidade_tipo_em_analise():
    vazio = Empreendimento()
    assert ancora.unidade_tipo_em_analise(vazio) is None
    assert ancora.tipologia_em_analise(vazio) == ""
    assert ancora.conteiner_em_analise(vazio) is None
    assert ancora.unidades_representadas(Contexto(empreendimento=vazio)) == 0


def test_uma_unidade_tipo_e_a_unidade_tipo():
    torre = UnidadeTipo(nome="Torre A", tipologia=dec.APARTAMENTO,
                       modelo=_conteiner(uhs=4))
    emp = Empreendimento(unidades_tipo=[torre])
    assert ancora.unidade_tipo_em_analise(emp) is torre
    assert ancora.tipologia_em_analise(emp) == dec.APARTAMENTO
    assert ancora.unidades_representadas(Contexto(empreendimento=emp)) == 4


def test_varias_unidades_tipo_com_um_unico_conteiner():
    """Só uma tem geometria a ser lida; é dela que a análise fala."""
    com = UnidadeTipo(nome="Torre A", tipologia=dec.APARTAMENTO,
                     modelo=_conteiner(uhs=4))
    sem = UnidadeTipo(nome="Casa 1", tipologia=dec.CASA)
    emp = Empreendimento(unidades_tipo=[sem, com])
    assert ancora.unidade_tipo_em_analise(emp) is com
    assert ancora.unidades_representadas(Contexto(empreendimento=emp)) == 4


def test_ambiguidade_nao_vira_escolha_pela_ordem_da_lista():
    """Duas candidatas: não há resposta honesta, e inventar uma seria eleger um
    denominador por ordem de lista. O número cai para 0 e a regra aplica o piso
    de 1 — o mesmo conservadorismo de quando nada foi declarado."""
    emp = Empreendimento(unidades_tipo=[
        UnidadeTipo(nome="Torre A", tipologia=dec.APARTAMENTO,
                   modelo=_conteiner(uhs=4, caminho="a.ifc")),
        UnidadeTipo(nome="Torre B", tipologia=dec.CASA,
                   modelo=_conteiner(uhs=8, caminho="b.ifc"))])
    assert ancora.unidade_tipo_em_analise(emp) is None
    assert ancora.tipologia_em_analise(emp) == ""
    assert ancora.conteiner_em_analise(emp) is None
    assert ancora.unidades_representadas(Contexto(empreendimento=emp)) == 0


def test_sem_unidade_tipo_com_conteiner_a_deducao_cai_no_terreno():
    """O ADR-023 pendura no ``Terreno`` o contêiner de natureza ``terreno``;
    sem unidade tipo que traga arquivo, é ele o que a submissão entregou."""
    do_terreno = ModeloBIM(caminho="t.ifc", natureza=dec.TERRENO)
    emp = Empreendimento(terreno=_terreno(do_terreno),
                         unidades_tipo=[UnidadeTipo(nome="Torre A", tipologia=dec.CASA)])
    assert ancora.conteiner_em_analise(emp) is do_terreno
    assert ancora.tipologia_em_analise(emp) == dec.CASA
    assert ancora.unidades_representadas(Contexto(empreendimento=emp)) == 0


def test_o_conteiner_da_unidade_tipo_vence_o_do_terreno():
    """Com os dois anexados (natureza ``terreno_com_edificacoes``), é da
    geometria da UH que a regra dimensional fala."""
    do_terreno = ModeloBIM(caminho="m.ifc", natureza=dec.TERRENO_COM_EDIFICACOES)
    da_unidade_tipo = _conteiner(uhs=2, caminho="m.ifc")
    emp = Empreendimento(terreno=_terreno(do_terreno), unidades_tipo=[
        UnidadeTipo(nome="Torre A", modelo=da_unidade_tipo)])
    assert ancora.conteiner_em_analise(emp) is da_unidade_tipo
    assert ancora.unidades_representadas(Contexto(empreendimento=emp)) == 2


# --- a âncora recebida (D2) ------------------------------------------------

def test_a_ancora_recebida_vence_a_deducao():
    """É o ponto central: quem conhece a submissão responde, e o núcleo não
    adivinha. Sem isto, analisar o contêiner do terreno com uma unidade tipo
    declarada leria o número de UHs da unidade tipo errada."""
    da_unidade_tipo = _conteiner(uhs=4, caminho="edificacao.ifc")
    emp = Empreendimento(unidades_tipo=[UnidadeTipo(nome="Torre A", modelo=da_unidade_tipo)])
    recebido = ModeloBIM(caminho="terreno.ifc", natureza=dec.TERRENO)
    ctx = Contexto(empreendimento=emp, conteiner=recebido)
    assert ancora.conteiner_da_execucao(ctx) is recebido
    assert ancora.unidades_representadas(ctx) == 0
    assert ancora.conteiner_em_analise(emp) is da_unidade_tipo, "a dedução não mudou"


def test_sem_ancora_recebida_vale_a_deducao():
    """O contexto montado à mão — a CLI, a suíte — continua respondido pelo
    agregado: o argumento é aditivo, não substituto."""
    emp = Empreendimento(unidades_tipo=[
        UnidadeTipo(nome="Torre A", modelo=_conteiner(uhs=3))])
    ctx = Contexto(empreendimento=emp)
    assert ancora.conteiner_da_execucao(ctx).unidades_representadas == 3
    assert ancora.unidades_representadas(ctx) == 3


def test_contexto_sem_nada_nao_levanta():
    """Regra montada num contexto vazio não pode quebrar por causa da âncora:
    zero é 'não há entrega a cujo respeito perguntar', e a regra aplica o piso."""
    assert ancora.conteiner_da_execucao(Contexto()) is None
    assert ancora.unidades_representadas(Contexto()) == 0


# --- os donos do contêiner e a precedência (ADR-023) -----------------------

def _apto(nome="Apto padrão", unidades=100, modelo=None):
    return UnidadeTipo(nome=nome, unidades=unidades, tipologia=dec.APARTAMENTO,
                       modelo=modelo)


def test_mesmo_conteiner_compara_o_declarado_e_ignora_schema_e_digest():
    """O pipeline carimba o schema lido no contêiner da execução ANTES de
    montar o instantâneo; sem isto o contêiner nunca acharia o dono a que a
    própria tela o anexou."""
    declarado = _conteiner(uhs=4, caminho="a.ifc")
    aberto = ModeloBIM(caminho="a.ifc", natureza=dec.EDIFICACAO_ISOLADA,
                       unidades_representadas=4, schema="IFC4", digest="abc")
    assert ancora.mesmo_conteiner(declarado, aberto) is True
    assert ancora.mesmo_conteiner(declarado, _conteiner(uhs=8, caminho="a.ifc")) is False
    assert ancora.mesmo_conteiner(declarado, _conteiner(uhs=4, caminho="b.ifc")) is False
    assert ancora.mesmo_conteiner(declarado, None) is False
    assert ancora.mesmo_conteiner(None, None) is False


def test_donos_do_conteiner_lista_todos_por_nivel_sem_escolher():
    vo = _conteiner(uhs=4)
    tipo = _apto(modelo=vo)
    fisica = Edificacao(nome="Torre A", modelo=vo, composicao={tipo.id: 16})
    emp = Empreendimento(terreno=_terreno(vo), unidades_tipo=[tipo, _apto("outro")],
                         edificacoes=[fisica])
    donos = ancora.donos_do_conteiner(emp, vo)
    assert donos["unidades_tipo"] == [tipo]
    assert donos["edificacoes"] == [fisica]
    assert donos["terreno"] is emp.terreno
    vazio = ancora.donos_do_conteiner(emp, _conteiner(caminho="outro.ifc"))
    assert vazio == {"unidades_tipo": [], "edificacoes": [], "terreno": None}


def test_precedencia_tipo_vence_edificacao_e_terreno():
    """O mesmo VO no terreno E na unidade tipo (migração E0
    com terreno_com_edificacoes) — é da UH que o EDI fala."""
    vo = ModeloBIM(caminho="m.ifc", natureza=dec.TERRENO_COM_EDIFICACOES,
                   unidades_representadas=1)
    casa = UnidadeTipo(nome="Casa", unidades=1, tipologia=dec.CASA, modelo=vo)
    emp = Empreendimento(terreno=_terreno(vo), unidades_tipo=[casa])
    assert ancora.tipologia_em_analise(emp, vo) == dec.CASA


def test_precedencia_edificacao_vence_terreno_e_deriva_da_composicao():
    vo = ModeloBIM(caminho="misto.ifc", natureza=dec.EDIFICACAO_ISOLADA,
                   unidades_representadas=6)
    padrao, pcd = _apto("Padrão", 100), _apto("PCD", 20)
    torre = Edificacao(nome="Torre A", modelo=vo,
                       composicao={padrao.id: 50, pcd.id: 10})
    emp = Empreendimento(terreno=_terreno(vo), unidades_tipo=[padrao, pcd],
                         edificacoes=[torre])
    assert ancora.tipologia_em_analise(emp, vo) == dec.APARTAMENTO
    assert ancora.donos_do_conteiner(emp, vo)["unidades_tipo"] == [], (
        "nenhum tipo carrega o arquivo misto; o dono é a física")


def test_terreno_como_unico_dono_nao_tem_tipologia():
    vo = ModeloBIM(caminho="t.ifc", natureza=dec.TERRENO)
    emp = Empreendimento(terreno=_terreno(vo),
                         unidades_tipo=[UnidadeTipo(nome="Casa", tipologia=dec.CASA)])
    assert ancora.tipologia_em_analise(emp, vo) == ""
    assert ancora.tipologia_em_analise(emp) == dec.CASA, "sem contêiner, a dedução"


def test_conteiner_sem_dono_nenhum_cai_na_deducao():
    """Um contêiner que ninguém carrega não diz de que tipo fala."""
    emp = Empreendimento(unidades_tipo=[UnidadeTipo(nome="Casa", tipologia=dec.CASA)])
    assert ancora.tipologia_em_analise(emp, _conteiner(caminho="solto.ifc")) == (
        dec.CASA)


def test_pares_no_mesmo_nivel_com_a_mesma_tipologia_nao_sao_recusados():
    """Caso 5: quatro torres iguais sobre o mesmo contêiner — o par que o
    ADR-023 trata como equivalente à torre única de 64 UH."""
    vo = _conteiner(uhs=4, caminho="tipo.ifc")
    quatro = Empreendimento(unidades_tipo=[
        _apto(f"Torre {i}", 16, modelo=vo) for i in range(4)])
    uma = Empreendimento(unidades_tipo=[_apto("Torre única", 64, modelo=vo)])
    assert ancora.tipologia_em_analise(quatro, vo) == dec.APARTAMENTO
    assert ancora.tipologia_em_analise(uma, vo) == dec.APARTAMENTO
    assert ancora.tipologia_em_analise(quatro) == "", (
        "sem contêiner a dedução continua recusando adivinhar entre quatro")


def test_pares_no_mesmo_nivel_que_divergem_dao_ausencia():
    vo = _conteiner(uhs=4, caminho="tipo.ifc")
    emp = Empreendimento(unidades_tipo=[
        _apto("Torre", 16, modelo=vo),
        UnidadeTipo(nome="Casa", unidades=1, tipologia=dec.CASA, modelo=vo)])
    assert ancora.tipologia_em_analise(emp, vo) == ""


def test_duas_fisicas_em_todas_derivam_a_mesma_tipologia():
    vo = ModeloBIM(caminho="todas.ifc", natureza=dec.TERRENO_COM_EDIFICACOES,
                   unidades_representadas=8)
    padrao = _apto()
    emp = Empreendimento(terreno=_terreno(vo), unidades_tipo=[padrao], edificacoes=[
        Edificacao(nome="Torre A", modelo=vo, composicao={padrao.id: 4}),
        Edificacao(nome="Torre B", modelo=vo, composicao={padrao.id: 4})])
    assert ancora.tipologia_em_analise(emp, vo) == dec.APARTAMENTO


def test_fisica_sem_composicao_como_dona_da_ausencia():
    """Caso 6: a física declarada sem composição recebendo arquivo — a
    tipologia é indeterminada, e o que sai é ausência, não valor."""
    vo = _conteiner(uhs=2, caminho="galpao.ifc")
    emp = Empreendimento(unidades_tipo=[_apto()],
                         edificacoes=[Edificacao(nome="Galpão", modelo=vo)])
    assert ancora.tipologia_em_analise(emp, vo) == ""


# --- a escada da dedução passa pela edificação física -----------------------

def test_deducao_tipo_edificacao_terreno():
    vo_terreno = ModeloBIM(caminho="t.ifc", natureza=dec.TERRENO)
    vo_fisica = _conteiner(uhs=6, caminho="misto.ifc")
    padrao = _apto()
    emp = Empreendimento(terreno=_terreno(vo_terreno), unidades_tipo=[padrao],
                         edificacoes=[Edificacao(nome="Torre A", modelo=vo_fisica,
                                                 composicao={padrao.id: 100})])
    assert ancora.edificacao_em_analise(emp) is emp.edificacoes[0]
    assert ancora.conteiner_em_analise(emp) is vo_fisica, "o tipo não tem contêiner"
    assert ancora.unidades_representadas(Contexto(empreendimento=emp)) == 6
    emp.definir_edificacoes([])
    assert ancora.conteiner_em_analise(emp) is vo_terreno


def test_edificacao_em_analise_recusa_adivinhar_entre_duas_com_conteiner():
    padrao = _apto()
    emp = Empreendimento(unidades_tipo=[padrao], edificacoes=[
        Edificacao(nome="A", modelo=_conteiner(caminho="a.ifc")),
        Edificacao(nome="B", modelo=_conteiner(caminho="b.ifc"))])
    assert ancora.edificacao_em_analise(emp) is None
    assert ancora.conteiner_em_analise(emp) is None
    emp.definir_edificacoes([emp.edificacoes[0], Edificacao(nome="B")])
    assert ancora.edificacao_em_analise(emp) is emp.edificacoes[0]
