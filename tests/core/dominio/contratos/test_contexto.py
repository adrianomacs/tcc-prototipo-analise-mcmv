"""``Contexto = Empreendimento + serviços + resultados`` (ADR-004).

Sem campos delegados de retrocompatibilidade, ``Contexto`` só aceita o empreendimento pelo parâmetro
``empreendimento=`` — quem não passar um recebe um ``Empreendimento()`` vazio,
sem ponte nenhuma a partir de campos soltos. Estes testes prendem essa forma
final: o construtor expõe o empreendimento recebido (ou um vazio), e o
restante do arquivo cobre D2 (o roteador tipado).

O ``Contexto`` carrega também o ``conteiner`` — a âncora da
execução (ADR-021/023): a referência ao contêiner que o ``modelo_ifc`` aberto
É. Campo simples, sem dedução nenhuma aqui: quem resolve "explícito ou
deduzido" é ``core.dominio.ancora``, fora do contrato.
"""

from __future__ import annotations

from core.dominio.contratos.regra import Contexto
from core.dominio.empreendimento import Empreendimento, Localizacao, ModeloBIM
from core.dominio.terreno import Terreno
from core.dominio.vocabulario import declaracoes as dec
from core.regras.base.distancia_equipamento import RegraDistanciaEquipamento


def _terreno():
    return Terreno(origem="mapa", nivel="ponto", precisao="declarada",
                   crs_metrico="EPSG:31982", centro_wgs84=(-29.5, -51.96))


def test_ctx_expoe_o_empreendimento_recebido():
    t = _terreno()
    declaracoes = {dec.UF: "RS", dec.MUNICIPIO: "Estrela"}
    emp_novo = Empreendimento(
        localizacao=Localizacao.de_declaracoes(declaracoes, "4307807"),
        declaracoes=declaracoes, terreno=t)
    conteiner = ModeloBIM(schema="IFC4", natureza=dec.TERRENO)
    ctx = Contexto(empreendimento=emp_novo, conteiner=conteiner)

    assert ctx.empreendimento is emp_novo
    assert ctx.empreendimento.terreno is t
    assert ctx.empreendimento.localizacao.codigo_ibge == "4307807"
    assert ctx.empreendimento.localizacao.municipio == "Estrela"
    assert ctx.empreendimento.declaracoes is declaracoes, "o dict é o mesmo objeto"
    assert ctx.conteiner is conteiner


def test_contexto_vazio_tem_os_mesmos_padroes_de_antes():
    ctx = Contexto()
    assert ctx.empreendimento.terreno is None
    assert ctx.empreendimento.codigo_ibge == ""
    assert ctx.empreendimento.declaracoes == {}
    assert ctx.conteiner is None and ctx.empreendimento.localizacao is None
    assert ctx.config == {} and ctx.resultados == {} and ctx.camadas_gis == {}
    assert ctx.georref == {} and ctx.erro_ingestao == "" and ctx.modelo_ifc is None
    assert ctx.recorte_equipamentos is None and ctx.roteador is None


def test_o_construtor_nao_cria_a_ponte_do_municipio():
    """A ponte declarações → município mora em ``montar_contexto``, e só lá."""
    ctx = Contexto(
        empreendimento=Empreendimento(declaracoes={dec.MUNICIPIO_IBGE: "4307807"}))
    assert ctx.empreendimento.codigo_ibge == ""


def test_instancias_nao_compartilham_dicionarios():
    a, b = Contexto(), Contexto()
    a.config["x"] = 1
    a.empreendimento.declaracoes["y"] = 2
    assert b.config == {} and b.empreendimento.declaracoes == {}


def test_mutacoes_do_empreendimento_versionam():
    """O que antes eram os setters delegados de ``Contexto`` — hoje é o
    empreendimento mudado diretamente pelos próprios métodos dele."""
    ctx = Contexto()
    v = ctx.empreendimento.versao
    ctx.empreendimento.definir_terreno(_terreno())
    ctx.empreendimento.localizar(Localizacao("4307807"))
    ctx.empreendimento.declarar({dec.TIPOLOGIA: dec.CASA})
    emp = ctx.empreendimento
    assert emp.terreno is not None and emp.codigo_ibge == "4307807"
    assert emp.declaracoes == {dec.TIPOLOGIA: dec.CASA}
    assert emp.versao == v + 3
    ctx.empreendimento.localizar(None)
    assert emp.localizacao is None


def test_empreendimento_explicito():
    emp = Empreendimento(localizacao=Localizacao("3549904"), terreno=_terreno())
    ctx = Contexto(empreendimento=emp, conteiner=ModeloBIM(natureza=dec.TERRENO))
    assert ctx.empreendimento is emp
    assert ctx.empreendimento.codigo_ibge == "3549904"
    assert ctx.conteiner.natureza == dec.TERRENO


# ---------------------------------------------------------------------------
# D2 — o roteador tipado, com o dict como legado
# ---------------------------------------------------------------------------

def test_roteador_tipado_vence_o_do_config():
    tipado, do_dict = object(), object()
    regra = RegraDistanciaEquipamento()
    assert regra._roteador_de_rede(
        Contexto(config={"roteador_rede": do_dict}, roteador=tipado)) is tipado
    assert regra._roteador_de_rede(
        Contexto(config={"roteador_rede": do_dict})) is do_dict
    assert regra._roteador_de_rede(Contexto()) is None
