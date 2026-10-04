"""As três regras ENQ de distância a equipamento.

O que estes testes prendem, em ordem de importância:

1. **A classificação das suspeitas.** Lacuna de cadastro trava a
   reprovação mas não a aprovação; coordenada duvidosa trava as duas. Errar isso
   produz falso não-conforme de um lado ou conformidade falsa do outro — os dois
   defeitos que este módulo existe para não cometer.
2. **A independência entre as três regras.** ENQ-009 falhar por insumo não pode
   deixar ENQ-010.1 não avaliável. É a lição da atomização do EDI-004, agora na
   camada GIS.
3. **A reprovação sem chamada de rede**, que é o que o rigor assimétrico compra.
"""

from __future__ import annotations

import json
import os

import pytest

from core.dominio import equipamentos as eq
from core.dominio.contratos.regra import Contexto, Estado
from core.dominio.empreendimento import Empreendimento, Localizacao
from core.dominio.terreno import Terreno
from core.dominio.vocabulario import motivos
from core.infra.gis import csv_equipamentos
from core.regras.gis.enq_009_educacao_infantil import ENQ009
from core.regras.gis.enq_010_1_fundamental_i import ENQ0101
from core.regras.gis.enq_011_1_fundamental_ii import ENQ0111

CENTRO = (-29.5013, -51.9650)
CABECALHO = ("codigo_inep;nome;latitude;longitude;ciclo;rede;situacao;"
             "atendimento;conveniada;endereco")


def _ao_norte(metros: float) -> float:
    return CENTRO[0] + metros / 111_320.0


def _linha(codigo, nome, metros, ciclos, *, rede="municipal", situacao="ativa",
           lat=None, lon=None):
    lat = _ao_norte(metros) if lat is None else lat
    lon = CENTRO[1] if lon is None else lon
    return (f"{codigo};{nome};{lat:.8f};{lon:.8f};{'|'.join(ciclos)};"
            f"{rede};{situacao};geral;nao;RUA X, 1")


@pytest.fixture
def pasta(tmp_path):
    return str(tmp_path)


def _gravar(pasta, codigo_ibge, linhas, *, procedencia=True):
    csv_equipamentos._CACHE.clear()
    caminho = os.path.join(pasta, f"equipamentos_{codigo_ibge}.csv")
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(CABECALHO + "\n" + "\n".join(linhas) + "\n")
    if procedencia:
        with open(os.path.join(pasta, f"equipamentos_{codigo_ibge}.json"),
                  "w", encoding="utf-8") as f:
            json.dump({"ano_censo": "2025", "gerado_em": "2026-09-11T13:05:30-03:00",
                       "nome_municipio": "Estrela", "uf": "RS",
                       "fontes": [{"arquivo": "Tabela_Escola_2025_V2.csv"}]}, f)
    return caminho


def _terreno():
    return Terreno(origem="mapa", nivel="ponto", precisao="declarada",
                   crs_metrico="EPSG:31982", centro_wgs84=CENTRO)


def _ctx(municipio="4307807", terreno=None, config=None):
    terreno = terreno if terreno is not None else _terreno()
    localizacao = Localizacao(municipio) if municipio else None
    empreendimento = Empreendimento(localizacao=localizacao, terreno=terreno)
    return Contexto(empreendimento=empreendimento, config=config or {})


def _rodar(regra_cls, pasta, ctx=None):
    # O recorte entra no Contexto já montado, como a composição o entrega
    # (ADR-011); a regra não lê arquivo.
    ctx = ctx or _ctx()
    codigo = ctx.empreendimento.codigo_ibge
    if codigo and ctx.recorte_equipamentos is None:
        ctx.recorte_equipamentos = csv_equipamentos.recorte_municipal(codigo, pasta)
    return regra_cls().checar(ctx)


# ---------------------------------------------------------------------------
# 1. Caminhos de insumo
# ---------------------------------------------------------------------------

def test_municipio_nao_declarado(pasta):
    r = _rodar(ENQ009, pasta, _ctx(municipio=""))
    assert r.estado is Estado.NAO_AVALIAVEL
    # Declaração do proponente, não conteúdo do modelo (ADR-033).
    assert r.detalhe[motivos.CHAVE] == motivos.INSUMO_DO_PROPONENTE_AUSENTE


def test_recorte_ausente_sugere_como_destravar(pasta):
    r = _rodar(ENQ009, pasta)
    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.INSUMO_AUSENTE
    assert "gerar_equipamentos.py" in r.mensagem
    assert "CSV complementar" in r.mensagem


def test_recorte_existe_mas_ciclo_nao_tem_equipamento(pasta):
    """Conjunto vazio após os filtros é LACUNA: não reprova."""
    _gravar(pasta, "4307807", [_linha("1", "EMEF A", 300, ["fundamental_i"])])
    r = _rodar(ENQ009, pasta)
    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.INSUMO_SUSPEITO


# ---------------------------------------------------------------------------
# 2. Vereditos métricos
# ---------------------------------------------------------------------------

def test_rural_reprova_sem_nenhuma_chamada_de_rede(pasta):
    """O que o rigor assimétrico compra: reprovação de graça e definitiva."""
    _gravar(pasta, "4307807", [
        _linha("1", "EMEI LONGE", 4000, ["infantil"]),
        _linha("2", "EMEI MAIS LONGE", 9000, ["infantil"])])
    r = _rodar(ENQ009, pasta)
    assert r.estado is Estado.NAO_CONFORME
    assert r.valor_esperado == 1000.0
    assert r.valor_encontrado > 1000.0
    assert r.detalhe["candidatos_para_roteamento"] == 0
    assert "linha reta" in r.mensagem


def test_equipamento_perto_nao_aprova_sem_rede(pasta):
    """O coração da assimetria, visto pela regra."""
    _gravar(pasta, "4307807", [_linha("1", "EMEI PERTO", 600, ["infantil"])])
    r = _rodar(ENQ009, pasta)
    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.METRICA_INSUFICIENTE
    assert "permite reprovar" in r.mensagem or "não aprovar" in r.mensagem
    assert motivos.ACAO[motivos.METRICA_INSUFICIENTE][:20] in r.mensagem


def test_o_limiar_de_cada_regra_e_o_da_portaria(pasta):
    """Mesmo equipamento a 1,2 km: reprova no ENQ-009, não reprova nos outros."""
    _gravar(pasta, "4307807", [
        _linha("1", "ESCOLA", 1200, ["infantil", "fundamental_i", "fundamental_ii"])])
    assert _rodar(ENQ009, pasta).estado is Estado.NAO_CONFORME      # limiar 1.000
    assert _rodar(ENQ0101, pasta).estado is Estado.NAO_AVALIAVEL    # limiar 1.500
    assert _rodar(ENQ0111, pasta).estado is Estado.NAO_AVALIAVEL


# ---------------------------------------------------------------------------
# 3. As duas classes de suspeita — o centro da regra
# ---------------------------------------------------------------------------

def test_lacuna_de_cadastro_trava_a_reprovacao(pasta):
    """Ausência de registro não é ausência de escola."""
    _gravar(pasta, "4307807", [_linha("1", "EMEF A", 300, ["fundamental_i"])])
    r = _rodar(ENQ009, pasta)
    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.INSUMO_SUSPEITO
    classes = {s["classe"] for s in r.detalhe["suspeitas"]}
    assert classes == {"lacuna"}


def test_coordenada_duvidosa_trava_TAMBEM_a_aprovacao(pasta):
    """Coordenada errada pode aproximar falsamente — nem aprovar se sustenta.

    Duas escolas de infantil na MESMA coordenada, a 300 m: com métrica de rede
    isso seria CONFORME. Não é: o cadastro está visivelmente errado.
    """
    lat = _ao_norte(300)
    _gravar(pasta, "4307807", [
        _linha("1", "EMEI A", 0, ["infantil"], lat=lat),
        _linha("2", "EMEI B", 0, ["infantil"], lat=lat)])

    regra = ENQ009()
    lido = csv_equipamentos.carregar_recorte("4307807", pasta)
    filtragem = eq.filtrar(lido.equipamentos, ciclo=eq.CICLO_INFANTIL)
    suspeitas = eq.sanidade(filtragem.aceitos, ciclo=eq.CICLO_INFANTIL,
                            total_no_conjunto=filtragem.total)
    assert eq.impede_aprovar(suspeitas) is True
    assert {eq.classe_da_suspeita(s.codigo) for s in suspeitas} == {"coordenada"}

    # e a regra, com uma medição de REDE que aprovaria, não aprova:
    detalhe = {}
    r = regra._veredito("atende", _medicao_de_rede(300.0), suspeitas, detalhe)
    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.INSUMO_SUSPEITO


def test_lacuna_NAO_trava_a_aprovacao(pasta):
    """A metade que a decisão de 11/09 preserva.

    Cadastro incompleto só pode ESCONDER escolas. Achar uma dentro do limiar
    continua sendo prova válida — e travar isso custaria conformidades legítimas
    justamente nos municípios com cadastro parcial, que são os que mais precisam.
    """
    from core.dominio.equipamentos import SUSPEITA_SEM_ETAPA, Suspeita

    regra = ENQ009()
    lacuna = [Suspeita(SUSPEITA_SEM_ETAPA, "cadastro possivelmente incompleto")]
    assert eq.impede_aprovar(lacuna) is False
    r = regra._veredito("atende", _medicao_de_rede(400.0), lacuna, {})
    assert r.estado is Estado.CONFORME


def _medicao_de_rede(metros: float):
    from core.dominio import mobilidade as rot
    from core.dominio.contratos import roteador as rot_rot
    return rot.Medicao(destino="1", rotulo="EMEI A", metros=metros,
                       provedor=rot_rot.PROVEDOR_ORS,
                       metrica=rot_rot.METRICA_REDE_PEDESTRE, limite_inferior=False)


# ---------------------------------------------------------------------------
# 4. Independência entre as regras
# ---------------------------------------------------------------------------

def test_as_tres_regras_nao_se_contaminam(pasta):
    """Lição da atomização do EDI-004, agora na camada GIS.

    Município sem nenhuma escola de infantil, mas com fundamental dos dois
    ciclos longe: o ENQ-009 fica não avaliável por insumo, e isso **não pode**
    impedir os outros dois de reprovarem por conta própria.
    """
    _gravar(pasta, "4307807", [
        _linha("1", "EMEF A", 5000, ["fundamental_i", "fundamental_ii"])])
    assert _rodar(ENQ009, pasta).estado is Estado.NAO_AVALIAVEL
    assert _rodar(ENQ0101, pasta).estado is Estado.NAO_CONFORME
    assert _rodar(ENQ0111, pasta).estado is Estado.NAO_CONFORME


def test_as_tres_declaram_os_ids_do_yaml():
    """Id errado = regra que nunca aparece na tela, sem erro nenhum."""
    assert (ENQ009.id, ENQ0101.id, ENQ0111.id) == ("ENQ-009", "ENQ-010.1", "ENQ-011.1")
    for cls in (ENQ009, ENQ0101, ENQ0111):
        assert cls.exige_terreno == "ponto"
        assert cls.depende_de == []      # §1.2: o gate é o terreno, não o EMP-001


# ---------------------------------------------------------------------------
# 5. Diagnóstico
# ---------------------------------------------------------------------------

def test_detalhe_torna_o_resultado_auditavel(pasta):
    _gravar(pasta, "4307807", [
        _linha("43060706", "EMEI SAO JOAO", 900, ["infantil"]),
        _linha("43060404", "COLEGIO PRIVADO", 200, ["infantil"], rede="privada"),
        _linha("43060420", "EMEI PARALISADA", 300, ["infantil"], situacao="paralisada")])
    r = _rodar(ENQ009, pasta)
    d = r.detalhe
    assert d["municipio_ibge"] == "4307807"
    assert d["limiar_m"] == 1000.0
    assert d["determinante"]["destino"] == "43060706"
    assert d["determinante"]["rotulo"] == "EMEI SAO JOAO"
    assert d["filtragem"]["por_motivo"][eq.DESCARTE_REDE_PRIVADA] == 1
    assert d["filtragem"]["por_motivo"][eq.DESCARTE_SITUACAO_INATIVA] == 1
    assert d["procedencia_recorte"]["ano_censo"] == "2025"
    assert d["terreno"]["origem"] == "mapa"


def test_sinais_nao_verificados_sao_declarados(pasta):
    """Não confundir "não disparou" com "não foi verificado"."""
    _gravar(pasta, "4307807", [_linha("1", "EMEI A", 900, ["infantil"])])
    r = _rodar(ENQ009, pasta)
    nao_verificados = r.detalhe["sinais_nao_verificados"]
    assert eq.SUSPEITA_CONTAGEM_IMPLAUSIVEL in nao_verificados
    assert "população" in nao_verificados[eq.SUSPEITA_CONTAGEM_IMPLAUSIVEL]


def _ctx_com_populacao(habitantes):
    """Contexto do Estrela com a população do Censo, como o pipeline o monta."""
    from core.dominio.conhecimento.porte_municipal import PopulacaoMunicipal
    ctx = _ctx()
    ctx.populacao_municipal = PopulacaoMunicipal("4307807", habitantes)
    return ctx


def test_populacao_do_contexto_ativa_o_sinal_de_contagem(pasta):
    """O sinal sai de "não verificado" e, plausível, não altera nada.

    Uma escola para 30 mil habitantes está acima do piso (1); o resultado tem de
    ser exatamente o de antes, só que sem a declaração de sinal inativo.
    """
    _gravar(pasta, "4307807", [_linha("1", "EMEI A", 900, ["infantil"])])
    sem = _rodar(ENQ009, pasta)
    com = _rodar(ENQ009, pasta, _ctx_com_populacao(30_000))

    assert eq.SUSPEITA_CONTAGEM_IMPLAUSIVEL in sem.detalhe["sinais_nao_verificados"]
    assert eq.SUSPEITA_CONTAGEM_IMPLAUSIVEL not in com.detalhe["sinais_nao_verificados"]
    assert com.detalhe["suspeitas"] == sem.detalhe["suspeitas"] == []
    assert (com.estado, com.valor_encontrado, com.mensagem) == \
        (sem.estado, sem.valor_encontrado, sem.mensagem)


def test_contagem_implausivel_passa_a_disparar_com_a_populacao(pasta):
    """Com população, cadastro esparso vira suspeita de LACUNA e trava reprovar.

    Duas escolas de infantil, ambas além do limiar, num município de 900 mil
    habitantes (piso de 45): sem população a regra reprova; com ela, o cadastro
    não passa na sanidade e a ausência pode ser de registro, não de escola.
    """
    _gravar(pasta, "4307807", [
        _linha("1", "EMEI LONGE", 4000, ["infantil"]),
        _linha("2", "EMEI MAIS LONGE", 9000, ["infantil"])])
    assert _rodar(ENQ009, pasta).estado is Estado.NAO_CONFORME

    r = _rodar(ENQ009, pasta, _ctx_com_populacao(900_000))
    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.INSUMO_SUSPEITO
    codigos = {s["codigo"]: s["classe"] for s in r.detalhe["suspeitas"]}
    assert codigos == {eq.SUSPEITA_CONTAGEM_IMPLAUSIVEL: "lacuna"}
    assert eq.SUSPEITA_CONTAGEM_IMPLAUSIVEL not in r.detalhe["sinais_nao_verificados"]


@pytest.mark.parametrize("valor", [None, 0, -5, True, "33000", 33000.0])
def test_populacao_invalida_conta_como_ausente(pasta, valor):
    """Lixo no lugar da população não pode fabricar suspeita (nem veredito)."""
    _gravar(pasta, "4307807", [_linha("1", "EMEI A", 900, ["infantil"])])
    ctx = _ctx()
    ctx.populacao_municipal = valor
    assert ENQ009()._populacao_municipal(ctx) is None
    r = _rodar(ENQ009, pasta, ctx)
    assert eq.SUSPEITA_CONTAGEM_IMPLAUSIVEL in r.detalhe["sinais_nao_verificados"]
    assert r.detalhe["suspeitas"] == []


def test_populacao_como_inteiro_tambem_e_aceita(pasta):
    """Contexto montado à mão pode trazer os habitantes soltos."""
    ctx = _ctx()
    ctx.populacao_municipal = 33_000
    assert ENQ009()._populacao_municipal(ctx) == 33_000


def test_com_a_populacao_nenhum_sinal_fica_sem_verificar(pasta):
    """Contrato da tela: sem sinal inativo, o expander de verificações some.

    Sem o sinal do centróide municipal, a população
    é a única entrada que pode deixar um sinal sem verificação. Com ela no
    Contexto, ``sinais_nao_verificados`` sai vazio — e é a ausência dele, não um
    texto escondido, que faz o expander não aparecer.
    """
    _gravar(pasta, "4307807", [_linha("1", "EMEI A", 900, ["infantil"])])
    r = _rodar(ENQ009, pasta, _ctx_com_populacao(32_183))
    assert r.detalhe["sinais_nao_verificados"] == {}


# ---------------------------------------------------------------------------
# 5b. A evidência que o relatório exibe
#
# O relatório em tela dividida lê o ``detalhe`` e nada mais — é o que torna o
# JSON reproduzível. Estes testes prendem o contrato que ele consome, e um deles
# prende a invariante que impede a tela de contradizer a regra.
# ---------------------------------------------------------------------------

def _classificacoes(r):
    return {linha["classificacao"] for linha in r.detalhe["equipamentos"]}


def test_cada_equipamento_avaliado_vira_uma_linha_ordenada(pasta):
    _gravar(pasta, "4307807", [
        _linha("43060706", "EMEI LONGE", 900, ["infantil"]),
        _linha("43060707", "EMEI PERTO", 300, ["infantil"]),
        _linha("43060404", "COLEGIO PRIVADO", 200, ["infantil"], rede="privada")])
    d = _rodar(ENQ009, pasta).detalhe

    linhas = d["equipamentos"]
    assert [linha["nome"] for linha in linhas] == ["EMEI PERTO", "EMEI LONGE"]
    assert linhas[0]["codigo_inep"] == "43060707"
    assert linhas[0]["lat"] is not None and linhas[0]["lon"] is not None
    # A privada não é AVALIADA — ela não pode aparecer entre os equipamentos.
    assert all(linha["rede"] == "municipal" for linha in linhas)


def test_a_classificacao_nao_pode_divergir_do_veredito(pasta):
    """A invariante central da evidência.

    Se a tela pintasse de verde um equipamento que a regra não aceitou como
    prova, o usuário leria "atende" ao lado de um NÃO AVALIÁVEL. A classificação
    e o veredito saem os dois de ``rot.classificar``; estes casos prendem isso
    nas três situações que o recorte produz hoje.
    """
    from core.dominio import mobilidade as rot

    # (a) tudo além do limiar: reprova, e toda linha é comprovadamente fora.
    _gravar(pasta, "4307807", [_linha("1", "EMEI LONGE", 4000, ["infantil"])])
    r = _rodar(ENQ009, pasta)
    assert r.estado is Estado.NAO_CONFORME
    assert _classificacoes(r) == {rot.CLASSIF_FORA_PROVADO}

    # (b) dentro do limiar, mas só em linha reta: NENHUMA linha pode ser verde.
    _gravar(pasta, "4307807", [_linha("2", "EMEI PERTO", 600, ["infantil"])])
    r = _rodar(ENQ009, pasta)
    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.METRICA_INSUFICIENTE
    assert _classificacoes(r) == {rot.CLASSIF_DENTRO_DO_PISO}
    assert rot.CLASSIF_ATENDE_PROVADO not in _classificacoes(r)

    # (c) e a regra geral, nos dois sentidos.
    for cls in (ENQ009, ENQ0101, ENQ0111):
        r = _rodar(cls, pasta)
        classes = _classificacoes(r)
        if rot.CLASSIF_ATENDE_PROVADO in classes:
            assert r.detalhe["veredito_metrico"] == rot.VEREDITO_ATENDE
        if classes and classes == {rot.CLASSIF_FORA_PROVADO}:
            assert r.detalhe["veredito_metrico"] == rot.VEREDITO_NAO_ATENDE


def test_classificar_e_confrontar_saem_da_mesma_decisao():
    """Duas leituras da mesma medição não podem discordar."""
    from core.dominio import mobilidade as rot
    from core.dominio.contratos import roteador as rot_rot

    piso_perto = rot.Medicao(destino="1", metros=900.0,
                             provedor=rot_rot.PROVEDOR_EUCLIDIANA,
                             metrica=rot_rot.METRICA_LINHA_RETA, limite_inferior=True)
    rede_perto = _medicao_de_rede(900.0)
    piso_longe = rot.Medicao(destino="2", metros=1200.0,
                             provedor=rot_rot.PROVEDOR_EUCLIDIANA,
                             metrica=rot_rot.METRICA_LINHA_RETA, limite_inferior=True)

    assert rot.classificar(piso_perto, 1000.0) == rot.CLASSIF_DENTRO_DO_PISO
    assert rot.confrontar(piso_perto, 1000.0) == rot.VEREDITO_INCONCLUSIVO
    assert rot.classificar(rede_perto, 1000.0) == rot.CLASSIF_ATENDE_PROVADO
    assert rot.confrontar(rede_perto, 1000.0) == rot.VEREDITO_ATENDE
    assert rot.classificar(piso_longe, 1000.0) == rot.CLASSIF_FORA_PROVADO
    assert rot.confrontar(piso_longe, 1000.0) == rot.VEREDITO_NAO_ATENDE
    assert rot.classificar(None, 1000.0) == rot.CLASSIF_NAO_MEDIDA


def test_o_determinante_e_marcado_uma_unica_vez(pasta):
    """A linha que sustenta o veredito precisa ser identificável na tabela."""
    _gravar(pasta, "4307807", [
        _linha("1", "EMEI A", 4000, ["infantil"]),
        _linha("2", "EMEI B", 6000, ["infantil"]),
        _linha("3", "EMEI C", 8000, ["infantil"])])
    d = _rodar(ENQ009, pasta).detalhe

    marcadas = [linha for linha in d["equipamentos"] if linha["determinante"]]
    assert len(marcadas) == 1
    assert marcadas[0]["destino"] == d["determinante"]["destino"]
    assert marcadas[0]["nome"] == "EMEI A"      # a mais próxima das três


def test_descartados_no_raio_explicam_por_que_nao_contaram(pasta):
    """A pergunta que todo não-conforme levanta: *e aquela escola ali?*"""
    _gravar(pasta, "4307807", [
        _linha("1", "EMEI LONGE", 4000, ["infantil"]),
        _linha("2", "COLEGIO PRIVADO", 200, ["infantil"], rede="privada"),
        _linha("3", "EMEI PARALISADA", 300, ["infantil"], situacao="paralisada"),
        _linha("4", "PRIVADA DISTANTE", 9000, ["infantil"], rede="privada")])
    d = _rodar(ENQ009, pasta).detalhe

    perto = {linha["nome"]: linha for linha in d["descartados_no_raio"]}
    assert set(perto) == {"COLEGIO PRIVADO", "EMEI PARALISADA"}
    assert perto["COLEGIO PRIVADO"]["motivo"] == eq.DESCARTE_REDE_PRIVADA
    assert perto["COLEGIO PRIVADO"]["rotulo_motivo"] == "rede privada"
    assert perto["EMEI PARALISADA"]["motivo"] == eq.DESCARTE_SITUACAO_INATIVA
    # Todos dentro do raio de busca, e a contagem global segue completa.
    assert all(linha["metros"] <= d["raio_de_busca_m"]
               for linha in d["descartados_no_raio"])
    assert d["filtragem"]["por_motivo"][eq.DESCARTE_REDE_PRIVADA] == 2


def test_o_terreno_analisado_viaja_no_resultado(pasta):
    """O relatório desenha o terreno DA ANÁLISE, não o que estiver no disco.

    Redefinir o terreno depois de analisar não pode mudar o mapa de um relatório
    já produzido — é a mesma família do defeito do município divergente.
    """
    _gravar(pasta, "4307807", [_linha("1", "EMEI A", 900, ["infantil"])])
    poligonal = {"type": "Polygon", "coordinates": [[
        [-51.9655, -29.5008], [-51.9645, -29.5008],
        [-51.9645, -29.5018], [-51.9655, -29.5018], [-51.9655, -29.5008]]]}
    t = Terreno(origem="desenhada", nivel="poligonal", precisao="aproximada",
                crs_metrico="EPSG:31982", centro_wgs84=CENTRO,
                poligonal_wgs84=poligonal, area_m2=1234.5)

    d = _rodar(ENQ009, pasta, _ctx(terreno=t)).detalhe["terreno"]
    assert d["origem"] == "desenhada" and d["nivel"] == "poligonal"
    assert d["poligonal_wgs84"] == poligonal
    assert d["centro_wgs84"] == {"lat": CENTRO[0], "lon": CENTRO[1]}
    assert d["area_m2"] == 1234.5


def test_o_detalhe_declara_o_tipo_e_o_criterio(pasta):
    """Sem ``tipo`` o relatório cai no painel genérico — e foi o que acontecia."""
    from core.regras.base import distancia_equipamento as base_mod

    _gravar(pasta, "4307807", [_linha("1", "EMEI A", 900, ["infantil"])])
    d = _rodar(ENQ009, pasta).detalhe
    assert d["tipo"] == base_mod.TIPO_DIAGNOSTICO == "distancia_equipamento"
    assert d["rotulo_ciclo"] == eq.ROTULO_CICLO[eq.CICLO_INFANTIL]
    assert d["municipio"] == {"ibge": "4307807", "nome": "Estrela", "uf": "RS"}
    # O critério viaja pronto para a tela não reescrevê-lo (e envelhecê-lo).
    assert "atendimento" in d["criterio_aceite"]


# ---------------------------------------------------------------------------
# 6. Cache do recorte
# ---------------------------------------------------------------------------

def test_cache_percebe_o_recorte_regerado(pasta):
    """Cache por (caminho, mtime): regerar com o app aberto não serve dado velho."""
    _gravar(pasta, "4307807", [_linha("1", "EMEI LONGE", 9000, ["infantil"])])
    assert _rodar(ENQ009, pasta).estado is Estado.NAO_CONFORME

    import time
    time.sleep(0.01)
    _gravar(pasta, "4307807", [_linha("1", "EMEI PERTO", 500, ["infantil"])])
    assert _rodar(ENQ009, pasta).estado is Estado.NAO_AVALIAVEL


# ---------------------------------------------------------------------------
# 7. A ponte entre a tela e as regras
# ---------------------------------------------------------------------------

def test_o_municipio_e_derivado_das_declaracoes(tmp_path):
    """O seletor já devolve o código; derivar daí evita passá-lo por todo lado.

    O CAMPO do ``Contexto`` continua sendo a fonte para as regras — o
    ``declaracoes`` governa aplicabilidade, não insumo —, e esta derivação é a
    única ponte entre os dois.
    """
    from core import composicao
    from core.dominio.vocabulario import declaracoes as dec

    ctx = composicao.montar_contexto(
        "", None, config={}, declaracoes={dec.MUNICIPIO_IBGE: "4307807"})
    assert ctx.empreendimento.codigo_ibge == "4307807"


def test_o_parametro_explicito_vence_a_declaracao(tmp_path):
    from core import composicao
    from core.dominio.vocabulario import declaracoes as dec

    ctx = composicao.montar_contexto(
        "", None, config={}, declaracoes={dec.MUNICIPIO_IBGE: "4307807"},
        municipio_ibge="3549904")
    assert ctx.empreendimento.codigo_ibge == "3549904"


def test_string_vazia_de_ifc_significa_NAO_HA_ifc(tmp_path):
    """``None`` = "descubra na pasta"; ``""`` = "este fluxo não tem IFC".

    A distinção existe para o Enquadramento, que roda sem modelo. Sem ela, a
    descoberta abriria um IFC qualquer da pasta — às vezes de centenas de MB —
    só para as regras GIS o ignorarem.
    """
    from core import composicao

    ctx = composicao.montar_contexto("", None, config={})
    assert ctx.modelo_ifc is None

    pasta = tmp_path / "ifc"
    pasta.mkdir()
    (pasta / "modelo.ifc").write_text("ISO-10303-21;\n", encoding="utf-8")
    assert composicao._primeiro_ifc(str(pasta)).endswith("modelo.ifc")
    assert composicao._primeiro_ifc(str(tmp_path / "nao-existe")) is None


def test_o_municipio_do_terreno_sobrevive_ao_artefato(tmp_path):
    """A premissa da pré-seleção: o terreno guardado sabe onde foi confirmado.

    A tela grava o município em ``procedencia["municipio_declarado"]`` ao
    confirmar, e reabre os seletores a partir dele. Se a ida e volta pelo
    ``terreno.json`` perdesse esse campo, a tela voltaria a cair no primeiro
    município em ordem alfabética — e a análise rodaria contra o recorte de
    equipamentos de um município que não é o do terreno, parecendo legítima.
    """
    from core.infra.persistencia import artefato

    t = Terreno(origem="mapa", nivel="ponto", precisao="declarada",
                crs_metrico="EPSG:31982", centro_wgs84=CENTRO,
                procedencia={"municipio_declarado": {
                    "uf": "RS", "nome": "Estrela", "ibge": "4307807"}})
    artefato.gravar(t, str(tmp_path))
    relido = artefato.ler(str(tmp_path))

    declarado = relido.procedencia["municipio_declarado"]
    assert declarado["ibge"] == "4307807"
    assert (declarado["uf"], declarado["nome"]) == ("RS", "Estrela")


def test_terreno_antigo_sem_municipio_nao_quebra(tmp_path):
    """Artefato anterior a esta versão: sem o campo, a tela avisa em vez de errar."""
    from core.infra.persistencia import artefato

    t = Terreno(origem="mapa", nivel="ponto", precisao="declarada",
                crs_metrico="EPSG:31982", centro_wgs84=CENTRO)
    artefato.gravar(t, str(tmp_path))
    relido = artefato.ler(str(tmp_path))
    assert (relido.procedencia or {}).get("municipio_declarado") is None
