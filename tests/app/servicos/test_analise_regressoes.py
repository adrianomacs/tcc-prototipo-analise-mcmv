"""Regressões de dois defeitos e a origem nova dos dois números
de UH e da tipologia (ADR-021/023)."""

from app.servicos import analise, grupos
from core.aplicacao import pipeline
from core.dominio import ancora
from core.dominio.edificacao import Edificacao
from core.dominio.empreendimento import Empreendimento, Localizacao
from core.dominio.terreno import Terreno
from core.dominio.unidade_tipo import UnidadeTipo
from core.dominio.vocabulario import declaracoes as dec


def _emp(*, unidades_tipo=(), edificacoes=(), terreno=None, **decl):
    return Empreendimento(
        nome="Estrela I",
        localizacao=Localizacao(codigo_ibge="4307807", uf="RS", municipio="Estrela"),
        declaracoes=decl, unidades_tipo=list(unidades_tipo),
        edificacoes=list(edificacoes), terreno=terreno)


def test_instantaneo_espelha_localizacao_nas_declaracoes():
    """Defeito 1: o EMP-001 lê o município de `declaracoes`; sem o espelho, o
    cross-check com a malha IBGE sumia no caminho novo."""
    inst = pipeline._instantaneo(_emp())
    assert inst.declaracoes[dec.MUNICIPIO_IBGE] == "4307807"
    assert inst.declaracoes[dec.UF] == "RS"
    assert inst.declaracoes[dec.MUNICIPIO] == "Estrela"


def test_instantaneo_nao_sobrescreve_declaracao_explicita():
    emp = _emp(**{dec.MUNICIPIO_IBGE: "3549904"})
    assert pipeline._instantaneo(emp).declaracoes[dec.MUNICIPIO_IBGE] == "3549904"


def test_instantaneo_nao_muta_o_empreendimento():
    emp = _emp()
    pipeline._instantaneo(emp)
    assert dec.MUNICIPIO_IBGE not in emp.declaracoes


def test_aplicabilidade_usa_tipologia_do_empreendimento():
    """Defeito 2: só com as declarações locais, EDI-001 (casa) entrava num
    empreendimento de apartamento. Desde o ADR-021 a tipologia vem da
    unidade tipo, e é a mesma fusão que tem de continuar enxergando-a."""
    grupo = grupos.carregar_grupo("programa_necessidades")
    emp = _emp(unidades_tipo=[UnidadeTipo(nome="Torre A", tipologia=dec.APARTAMENTO)],
               **{dec.ARRANJO: dec.LOTEAMENTO})
    locais = {dec.TIPO_MODELO: dec.TERRENO_COM_EDIFICACOES}
    ids = grupos.ids_executaveis(grupo, analise.declaracoes_da_analise(emp, locais))
    assert "EDI-001" not in ids and "EDI-002" in ids


def test_declaracoes_locais_prevalecem():
    emp = _emp(**{dec.TIPO_MODELO: dec.TERRENO})
    fundidas = analise.declaracoes_da_analise(emp, {dec.TIPO_MODELO: dec.EDIFICACAO_ISOLADA})
    assert fundidas[dec.TIPO_MODELO] == dec.EDIFICACAO_ISOLADA


# --- ADR-021: o contêiner da análise, e o que ele carrega -------------------

def test_o_numero_de_uhs_viaja_no_conteiner_e_nao_nas_declaracoes():
    """O que a tela informa sobre o arquivo vira `unidades_representadas` do
    `ModeloBIM` anexado à unidade tipo em análise — e não uma declaração."""
    emp = _emp(unidades_tipo=[UnidadeTipo(nome="Geminada", tipologia=dec.CASA)])
    inst, conteiner = analise._instantaneo_da_analise(
        emp, {dec.TIPO_MODELO: dec.EDIFICACAO_ISOLADA}, "m.ifc",
        unidades_representadas=2)
    assert ancora.conteiner_em_analise(inst).unidades_representadas == 2
    assert inst.unidades_tipo[0].modelo.caminho == "m.ifc"
    assert "num_uhs" not in inst.declaracoes
    # O contêiner também volta SOZINHO, para viajar como âncora
    # de `composicao.rodar` — é dele que o pipeline tira o IFC a abrir, agora
    # que `Empreendimento.modelo` não existe mais.
    assert conteiner.caminho == "m.ifc"
    assert conteiner is inst.unidades_tipo[0].modelo


def test_conteiner_de_terreno_e_ancora_sem_ser_anexado():
    """Sem `Terreno` declarado não há em que pendurá-lo, e a análise o lê
    assim mesmo, porque a âncora é argumento. (Havendo terreno declarado, o
    instantâneo passa a recebê-lo — ADR-023; ver os testes do alvo,
    mais abaixo.)"""
    emp = _emp()
    inst, conteiner = analise._instantaneo_da_analise(
        emp, {dec.TIPO_MODELO: dec.TERRENO}, "t.ifc")
    assert conteiner.caminho == "t.ifc" and conteiner.natureza == dec.TERRENO
    assert inst.unidades_tipo == [] and ancora.conteiner_em_analise(inst) is None


def test_a_unidade_tipo_em_analise_e_a_mesma_e_a_do_chamador_nao_muda():
    emp = _emp(unidades_tipo=[UnidadeTipo(nome="Geminada", tipologia=dec.CASA)])
    antes = emp.unidades_tipo[0]
    inst, _ = analise._instantaneo_da_analise(
        emp, {dec.TIPO_MODELO: dec.EDIFICACAO_ISOLADA}, "m.ifc", 2)
    assert inst.unidades_tipo[0].id == antes.id, "é a mesma unidade tipo"
    assert antes.modelo is None, "o empreendimento da sessão não foi editado"
    assert emp.versao == inst.versao


def test_sem_unidade_tipo_declarada_o_conteiner_ganha_uma_so_para_a_analise():
    emp = _emp()
    inst, _ = analise._instantaneo_da_analise(
        emp, {dec.TIPO_MODELO: dec.EDIFICACAO_ISOLADA}, "m.ifc", 4)
    assert ancora.conteiner_em_analise(inst).unidades_representadas == 4
    assert emp.unidades_tipo == [], "nada foi acrescentado ao objeto do chamador"


def test_instantaneo_do_pipeline_leva_a_tipologia_da_unidade_tipo_ao_guard():
    """O guard de aplicabilidade é declarativo e chaveado por nome; desde o
    ADR-021 quem responde pela dimensão `tipologia` é a unidade tipo."""
    emp = _emp(unidades_tipo=[UnidadeTipo(nome="Torre A", tipologia=dec.APARTAMENTO)])
    assert pipeline._instantaneo(emp).declaracoes[dec.TIPOLOGIA] == (
        dec.APARTAMENTO)


def test_a_tipologia_da_unidade_tipo_vence_a_declaracao_sobrevivente():
    """Artefato do esquema E0 (ADR-023) pode trazer a chave nas declarações; a dona
    do dado passou a ser a entidade, e é ela que governa."""
    emp = _emp(unidades_tipo=[UnidadeTipo(nome="Torre A", tipologia=dec.APARTAMENTO)],
               **{dec.TIPOLOGIA: dec.CASA})
    assert pipeline._instantaneo(emp).declaracoes[dec.TIPOLOGIA] == (
        dec.APARTAMENTO)
    assert analise.declaracoes_da_analise(emp, {})[dec.TIPOLOGIA] == dec.APARTAMENTO


def test_sem_tipologia_na_unidade_tipo_a_dimensao_nao_e_criada_vazia():
    """Dimensão presente e vazia tornaria EDI-001 e EDI-002 inaplicáveis de uma
    vez — que é o oposto de "ninguém declarou"."""
    emp = _emp(unidades_tipo=[UnidadeTipo(nome="Torre A")])
    assert dec.TIPOLOGIA not in pipeline._instantaneo(emp).declaracoes
    assert dec.TIPOLOGIA not in analise.declaracoes_da_analise(emp, {})


# --- ADR-023: o instantâneo do pipeline lê a tipologia pelo DONO da âncora ---

def test_instantaneo_do_pipeline_le_a_tipologia_pelo_dono_do_conteiner():
    """Duas unidades tipo com contêiner: a dedução recusa adivinhar, mas a
    âncora diz qual está sendo lida — e é a tipologia dela que vai ao guard,
    mesmo com o schema já carimbado no contêiner da execução."""
    from dataclasses import replace

    from core.dominio.modelo_bim import ModeloBIM

    casa = ModeloBIM(caminho="casa.ifc", natureza=dec.EDIFICACAO_ISOLADA,
                     unidades_representadas=1)
    apto = ModeloBIM(caminho="apto.ifc", natureza=dec.EDIFICACAO_ISOLADA,
                     unidades_representadas=4)
    emp = _emp(unidades_tipo=[UnidadeTipo(nome="Casa", tipologia=dec.CASA, modelo=casa),
                              UnidadeTipo(nome="Apto", tipologia=dec.APARTAMENTO,
                                          modelo=apto)])
    assert dec.TIPOLOGIA not in pipeline._instantaneo(emp).declaracoes, "sem âncora, ausência"
    aberto = replace(apto, schema="IFC4")
    assert pipeline._instantaneo(emp, aberto).declaracoes[dec.TIPOLOGIA] == (
        dec.APARTAMENTO)
    assert pipeline._instantaneo(emp, casa).declaracoes[dec.TIPOLOGIA] == dec.CASA


# --- ADR-023: o alvo generalizado, a ordem invertida e o Terreno ----

def _terreno() -> Terreno:
    return Terreno(origem="mapa", nivel="ponto", precisao="declarada",
                   crs_metrico="EPSG:31982", centro_wgs84=(-29.5, -51.96))


def _dois_tipos():
    return (UnidadeTipo(nome="Casa padrão", unidades=10, tipologia=dec.CASA),
            UnidadeTipo(nome="Torre", unidades=32, tipologia=dec.APARTAMENTO))


def test_alvo_de_unidade_tipo_escolhe_onde_a_deducao_recusaria():
    """Duas unidades tipo e nenhuma candidata única: a dedução devolve a
    coleção intacta. Com o alvo, a tela já respondeu — e o contêiner vai
    exatamente para quem ela apontou."""
    casa, torre = _dois_tipos()
    emp = _emp(unidades_tipo=[casa, torre])
    inst, conteiner = analise._instantaneo_da_analise(
        emp, {dec.TIPO_MODELO: dec.EDIFICACAO_ISOLADA}, "m.ifc", 4,
        analise.alvo_de_unidade_tipo(torre.id))

    anexados = [u.nome for u in inst.unidades_tipo if u.modelo is conteiner]
    assert anexados == ["Torre"]


def test_o_alvo_manda_na_tipologia_da_analise():
    """A ordem invertida (contêiner → dono → declarações): a tipologia sai do
    DONO do contêiner, não de uma dedução sobre o agregado — que aqui, com
    duas unidades tipo, não teria resposta."""
    casa, torre = _dois_tipos()
    emp = _emp(unidades_tipo=[casa, torre])

    inst, _ = analise._instantaneo_da_analise(
        emp, {dec.TIPO_MODELO: dec.EDIFICACAO_ISOLADA}, "m.ifc", 4,
        analise.alvo_de_unidade_tipo(torre.id))
    assert inst.declaracoes[dec.TIPOLOGIA] == dec.APARTAMENTO

    inst, _ = analise._instantaneo_da_analise(
        emp, {dec.TIPO_MODELO: dec.EDIFICACAO_ISOLADA}, "m.ifc", 1,
        analise.alvo_de_unidade_tipo(casa.id))
    assert inst.declaracoes[dec.TIPOLOGIA] == dec.CASA


def test_alvo_de_edificacao_recebe_o_conteiner_e_da_a_tipologia_derivada():
    """O arquivo misto: pertence à edificação física, e a tipologia é a que a
    raiz deriva da composição (ADR-023)."""
    casa, _ = _dois_tipos()
    edificacao = Edificacao(nome="Torre A", composicao={casa.id: 10})
    emp = _emp(unidades_tipo=[casa], edificacoes=[edificacao])
    inst, conteiner = analise._instantaneo_da_analise(
        emp, {dec.TIPO_MODELO: dec.EDIFICACAO_ISOLADA}, "m.ifc", 2,
        analise.alvo_de_edificacao(edificacao.id))

    assert inst.edificacoes[0].modelo is conteiner
    assert inst.unidades_tipo[0].modelo is None, "o tipo não é o dono aqui"
    assert inst.declaracoes[dec.TIPOLOGIA] == dec.CASA


def test_alvo_que_nao_existe_mais_nao_inventa_entidade():
    """Tela desatualizada, entidade removida entre o formulário e o clique: a
    coleção volta intacta, mesma postura de quando a dedução falha."""
    casa, _ = _dois_tipos()
    emp = _emp(unidades_tipo=[casa])
    inst, _ = analise._instantaneo_da_analise(
        emp, {dec.TIPO_MODELO: dec.EDIFICACAO_ISOLADA}, "m.ifc", 1,
        analise.alvo_de_unidade_tipo("nao-existe"))

    assert [u.modelo for u in inst.unidades_tipo] == [None]
    assert len(inst.unidades_tipo) == 1


def test_todas_anexa_ao_terreno_e_a_todas_as_edificacoes_fisicas():
    casa, _ = _dois_tipos()
    a = Edificacao(nome="Torre A", composicao={casa.id: 5})
    b = Edificacao(nome="Torre B", composicao={casa.id: 5})
    emp = _emp(unidades_tipo=[casa], edificacoes=[a, b], terreno=_terreno())
    inst, conteiner = analise._instantaneo_da_analise(
        emp, {dec.TIPO_MODELO: dec.TERRENO_COM_EDIFICACOES}, "m.ifc", 10,
        analise.ALVO_TODAS)

    assert [e.modelo for e in inst.edificacoes] == [conteiner, conteiner]
    assert inst.terreno.modelo is conteiner
    assert inst.unidades_tipo[0].modelo is None
    # Pares no mesmo nível derivam a mesma tipologia: ela sobrevive (ADR-023).
    assert inst.declaracoes[dec.TIPOLOGIA] == dec.CASA


def test_todas_sem_edificacao_fisica_cai_no_unico_tipo():
    casa, _ = _dois_tipos()
    emp = _emp(unidades_tipo=[casa], terreno=_terreno())
    inst, conteiner = analise._instantaneo_da_analise(
        emp, {dec.TIPO_MODELO: dec.TERRENO_COM_EDIFICACOES}, "m.ifc", 1,
        analise.ALVO_TODAS)

    assert inst.unidades_tipo[0].modelo is conteiner
    assert inst.terreno.modelo is conteiner


def test_todas_com_dois_tipos_e_nenhuma_fisica_nao_escolhe_por_conta():
    """Sem edificação física que dê dono ao arquivo, e com mais de um tipo, a
    tipologia é ausência (`""`) — não um palpite. A heterogeneidade vira
    diagnóstico na fase seguinte."""
    casa, torre = _dois_tipos()
    emp = _emp(unidades_tipo=[casa, torre], terreno=_terreno())
    inst, conteiner = analise._instantaneo_da_analise(
        emp, {dec.TIPO_MODELO: dec.TERRENO_COM_EDIFICACOES}, "m.ifc", 42,
        analise.ALVO_TODAS)

    assert [u.modelo for u in inst.unidades_tipo] == [None, None]
    assert inst.terreno.modelo is conteiner
    assert dec.TIPOLOGIA not in inst.declaracoes


def test_alvo_terreno_anexa_so_ao_terreno():
    """Com "Terreno" o contêiner vai ao `Terreno` do
    INSTANTÂNEO — efêmero, como tudo na análise, e sem veredito nenhum
    dependendo dele."""
    casa, _ = _dois_tipos()
    emp = _emp(unidades_tipo=[casa], terreno=_terreno())
    inst, conteiner = analise._instantaneo_da_analise(
        emp, {dec.TIPO_MODELO: dec.TERRENO}, "t.ifc", 0, analise.ALVO_TERRENO)

    assert inst.terreno.modelo is conteiner
    assert inst.unidades_tipo[0].modelo is None


def test_o_terreno_do_chamador_nao_e_editado_pela_analise():
    casa, _ = _dois_tipos()
    terreno = _terreno()
    emp = _emp(unidades_tipo=[casa], terreno=terreno)
    analise._instantaneo_da_analise(
        emp, {dec.TIPO_MODELO: dec.TERRENO}, "t.ifc", 0, analise.ALVO_TERRENO)

    assert terreno.modelo is None
    assert emp.terreno.modelo is None


def test_natureza_de_edificacao_nao_pendura_no_terreno():
    """O Programa de necessidades manda um arquivo de UH: o terreno não tem
    nada com isso, e `meta.terreno.modelo` continua `null` lá."""
    casa, _ = _dois_tipos()
    emp = _emp(unidades_tipo=[casa], terreno=_terreno())
    inst, conteiner = analise._instantaneo_da_analise(
        emp, {dec.TIPO_MODELO: dec.EDIFICACAO_ISOLADA}, "m.ifc", 1,
        analise.alvo_de_unidade_tipo(casa.id))

    assert inst.terreno.modelo is None
    assert inst.unidades_tipo[0].modelo is conteiner


# --- A tipologia do alvo, antes de haver arquivo -----

def test_tipologia_do_alvo_le_a_do_tipo_apontado():
    """A tela precisa da resposta ANTES do upload, para avisar (ou não) que a
    tipologia está por declarar. A dedução recusa escolher entre duas, com
    razão — mas a tela já sabe qual é, porque o autor apontou."""
    casa, torre = _dois_tipos()
    emp = _emp(unidades_tipo=[casa, torre])

    assert ancora.tipologia_em_analise(emp) == "", "a dedução recusa, e deve"
    assert analise.tipologia_do_alvo(
        emp, analise.alvo_de_unidade_tipo(casa.id)) == dec.CASA
    assert analise.tipologia_do_alvo(
        emp, analise.alvo_de_unidade_tipo(torre.id)) == dec.APARTAMENTO


def test_tipologia_do_alvo_de_edificacao_e_a_derivada_da_composicao():
    casa, _ = _dois_tipos()
    edificacao = Edificacao(nome="Torre A", composicao={casa.id: 10})
    emp = _emp(unidades_tipo=[casa], edificacoes=[edificacao])

    assert analise.tipologia_do_alvo(
        emp, analise.alvo_de_edificacao(edificacao.id)) == dec.CASA


def test_tipologia_do_alvo_sem_alvo_cai_na_deducao():
    """`todas`, `terreno` e a ausência de alvo significam justamente que
    ninguém apontou uma unidade tipo."""
    casa, torre = _dois_tipos()
    emp = _emp(unidades_tipo=[casa, torre])
    uma_so = _emp(unidades_tipo=[casa])

    for alvo in (analise.ALVO_DEDUZIDO, analise.ALVO_TERRENO, analise.ALVO_TODAS):
        assert analise.tipologia_do_alvo(emp, alvo) == ""
        assert analise.tipologia_do_alvo(uma_so, alvo) == dec.CASA


def test_tipologia_do_alvo_de_entidade_que_nao_existe_mais():
    casa, _ = _dois_tipos()
    emp = _emp(unidades_tipo=[casa])

    assert analise.tipologia_do_alvo(
        emp, analise.alvo_de_unidade_tipo("nao-existe")) == ""
    assert analise.tipologia_do_alvo(
        emp, analise.alvo_de_edificacao("nao-existe")) == ""


# --- O aviso de heterogeneidade antes de analisar (R3, ADR-023 D-K) --------

def test_heterogeneidade_do_alvo_so_fala_de_edificacao_com_dois_tipos():
    padrao = UnidadeTipo(nome="Apto padrão", unidades=100,
                         tipologia=dec.APARTAMENTO)
    pcd = UnidadeTipo(nome="Apto PCD", unidades=20, tipologia=dec.APARTAMENTO)
    mista = Edificacao(nome="Torre A", composicao={padrao.id: 50, pcd.id: 10})
    unica = Edificacao(nome="Torre B", composicao={padrao.id: 60})
    vazia = Edificacao(nome="Torre C")
    emp = _emp(unidades_tipo=[padrao, pcd],
               edificacoes=[mista, unica, vazia])

    assert "2 unidades tipo" in analise.heterogeneidade_do_alvo(
        emp, analise.alvo_de_edificacao(mista.id))
    assert analise.heterogeneidade_do_alvo(
        emp, analise.alvo_de_edificacao(unica.id)) == ""
    assert analise.heterogeneidade_do_alvo(
        emp, analise.alvo_de_edificacao(vazia.id)) == ""
    assert analise.heterogeneidade_do_alvo(
        emp, analise.alvo_de_unidade_tipo(padrao.id)) == ""
    assert analise.heterogeneidade_do_alvo(emp, analise.ALVO_DEDUZIDO) == ""


def test_alvo_de_edificacao_que_nao_existe_nao_inventa_aviso():
    """Tela desatualizada, entidade removida entre o formulário e o clique:
    mesma postura de `_com_conteiner` — não se inventa entidade nenhuma."""
    emp = _emp(unidades_tipo=[UnidadeTipo(nome="A", tipologia=dec.CASA)])
    assert analise.heterogeneidade_do_alvo(
        emp, analise.alvo_de_edificacao("nao-existe")) == ""


def test_a_frase_da_tela_e_a_do_relatorio():
    """Duas redações sobre a mesma limitação seria a tela contradizendo o
    relatório que ela própria gerou."""
    from core.aplicacao import diagnosticos as diag

    padrao = UnidadeTipo(nome="A", unidades=10, tipologia=dec.CASA)
    pcd = UnidadeTipo(nome="B", unidades=10, tipologia=dec.CASA)
    mista = Edificacao(nome="Mista", composicao={padrao.id: 5, pcd.id: 5})
    emp = _emp(unidades_tipo=[padrao, pcd], edificacoes=[mista])

    assert (analise.heterogeneidade_do_alvo(
        emp, analise.alvo_de_edificacao(mista.id))
        == diag.mensagem_heterogeneidade(2))
