"""ADR-004 — ``composicao.rodar(empreendimento=...)`` e a assinatura antiga.

O critério de aceite aqui é "mesmo relatório". Aqui ele é preso dentro da
suíte, sobre um recorte temporário: o caminho novo e o antigo gravam o MESMO
``relatorio.json`` (meta inclusa), e o empreendimento do chamador sai da análise
exatamente como entrou.
"""

from __future__ import annotations

import json

import pytest

from core import composicao
from core.aplicacao import pipeline
from core.dominio.empreendimento import Empreendimento, Localizacao, ModeloBIM
from core.dominio.terreno import Terreno
from core.dominio.unidade_tipo import UnidadeTipo
from core.dominio.vocabulario import declaracoes as dec
from core.infra.gis import csv_equipamentos as leitor
from tests.apoio.roteadores import RoteadorFalso

CENTRO = (-29.50186, -51.96529)
CABECALHO = ("codigo_inep;nome;lat;lon;ciclos;rede;situacao;atendimento;"
             "conveniada;endereco")
ENQ = ["ENQ-009", "ENQ-010", "ENQ-010.1", "ENQ-010.2", "ENQ-011", "ENQ-011.1",
       "ENQ-011.2"]


def _linha(codigo, nome, metros, ciclos):
    lat = CENTRO[0] + metros / 111_320.0
    return (f"{codigo};{nome};{lat:.8f};{CENTRO[1]:.8f};{'|'.join(ciclos)};"
            "municipal;ativa;geral;nao;RUA X, 1")


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    leitor._CACHE.clear()
    (tmp_path / "equipamentos_4307807.csv").write_text(
        CABECALHO + "\n" + "\n".join([
            _linha("1", "EMEI PERTO", 600, ["infantil"]),
            _linha("2", "EMEF LONGE", 2500, ["fundamental_i", "fundamental_ii"]),
        ]) + "\n", encoding="utf-8")
    monkeypatch.setattr(leitor, "PASTA_RECORTES", str(tmp_path))
    destino = {}
    monkeypatch.setattr(composicao, "_carregar_config",
                        lambda *a, **k: {"paths": {"relatorio": destino["rel"]}})
    monkeypatch.setattr(composicao, "_imprimir_resumo", lambda r: None)

    def _rodar(nome, **kw):
        destino["rel"] = str(tmp_path / f"{nome}.json")
        composicao.rodar(**kw)
        dados = json.loads((tmp_path / f"{nome}.json").read_text(encoding="utf-8"))
        dados.pop("gerado_em")
        for r in dados["por_requisito"]:
            (r["detalhe"].get("determinante") or {}).pop("obtido_em", None)
        # meta.empreendimento.id é gerado (uuid4) a cada Empreendimento
        # construído sem `id` explícito — os dois caminhos (antigo/novo) criam
        # objetos DIFERENTES (o antigo por dentro de `empreendimento_de_
        # argumentos`, o novo o que o teste passou), então o id nunca bate
        # entre "antigo" e "novo" por desenho, não por defeito. Provar que o
        # campo existe e tem a forma certa aqui; normalizar antes de comparar
        # os dois relatórios (mesmo padrão de `gerado_em` acima).
        emp_meta = dados["meta"]["empreendimento"]
        assert set(emp_meta) == {"id", "versao"}
        assert emp_meta["id"] and emp_meta["versao"] == 1
        dados["meta"]["empreendimento"] = "___normalizado___"
        return dados

    yield _rodar
    leitor._CACHE.clear()


def _terreno():
    return Terreno(origem="mapa", nivel="ponto", precisao="declarada",
                   crs_metrico="EPSG:31982", centro_wgs84=CENTRO)


DECLARACOES = {dec.UF: "RS", dec.MUNICIPIO: "Estrela", dec.MUNICIPIO_IBGE: "4307807",
               dec.ORIGEM_TERRENO: dec.TERRENO_DE_PONTO}


@pytest.mark.parametrize("rede", [None, "falso"])
def test_caminho_novo_e_antigo_gravam_o_mesmo_relatorio(ambiente, rede):
    roteador = RoteadorFalso(metros=800.0) if rede else None
    terreno = _terreno()
    antigo = ambiente("antigo", caminho_ifc="", ids_selecionados=ENQ,
                      declaracoes=dict(DECLARACOES), terreno=terreno,
                      roteador_rede=roteador)
    emp = Empreendimento(localizacao=Localizacao.de_declaracoes(DECLARACOES),
                         declaracoes=dict(DECLARACOES), terreno=terreno)
    novo = ambiente("novo", empreendimento=emp, ids_selecionados=ENQ,
                    roteador_rede=roteador)
    assert novo == antigo
    # e o recorte foi de fato lido (não é a igualdade de dois "insumo ausente"):
    enq009 = next(r for r in novo["por_requisito"] if r["requisito"] == "ENQ-009")
    assert enq009["detalhe"]["filtragem"]["total"] == 2


def test_a_analise_nao_altera_o_empreendimento_do_chamador(ambiente):
    emp = Empreendimento(localizacao=Localizacao("4307807"),
                         declaracoes={dec.ORIGEM_TERRENO: dec.TERRENO_DE_PONTO},
                         terreno=_terreno())
    antes = emp.to_dict()
    ambiente("x", empreendimento=emp, ids_selecionados=ENQ)
    assert emp.to_dict() == antes and emp.versao == 1
    assert dec.TIPO_MODELO not in emp.declaracoes


def test_o_instantaneo_e_o_mesmo_empreendimento_na_mesma_versao():
    emp = Empreendimento(declaracoes={dec.MUNICIPIO_IBGE: "4307807"})
    emp.renomear("Estrela I")
    foto = pipeline._instantaneo(emp, ModeloBIM(caminho="m.ifc",
                                                natureza=dec.TERRENO))
    assert foto == emp and foto.versao == emp.versao == 2
    assert foto.declaracoes[dec.TIPO_MODELO] == dec.TERRENO
    assert foto.codigo_ibge == "4307807", "a ponte do município"
    assert not hasattr(foto, "modelo"), "o contêiner não mora mais no agregado"


# ---------------------------------------------------------------------------
# D2 — a âncora da execução por argumento nomeado (ADR-021/023)
# ---------------------------------------------------------------------------

def _capturar_contexto(monkeypatch, tmp_path):
    """Roda até montar o Contexto e devolve o que chegou lá."""
    capturado = {}
    real = composicao.montar_contexto

    def _montar(*a, **kw):
        ctx = real(*a, **kw)
        capturado["ctx"] = ctx
        capturado["caminho"] = a[0]
        return ctx

    monkeypatch.setattr(composicao, "montar_contexto", _montar)
    monkeypatch.setattr(pipeline, "executar", lambda ctx, ids_selecionados=None: [])
    monkeypatch.setattr(composicao, "_imprimir_resumo", lambda r: None)
    monkeypatch.setattr(composicao, "_carregar_config", lambda *a, **k: {
        "paths": {"relatorio": str(tmp_path / "r.json")}})
    return capturado


def test_a_ancora_recebida_decide_o_ifc_a_abrir(monkeypatch, tmp_path):
    """O ponto da fase: quem conhece a submissão diz QUAL contêiner analisar, e
    o núcleo deixa de procurá-lo num campo fixo do empreendimento."""
    capturado = _capturar_contexto(monkeypatch, tmp_path)
    emp = Empreendimento(unidades_tipo=[
        UnidadeTipo(nome="Torre A", modelo=ModeloBIM(caminho="da_edificacao.ifc"))])
    ancora = ModeloBIM(caminho="enviado.ifc", natureza=dec.TERRENO,
                       unidades_representadas=4)
    composicao.rodar(empreendimento=emp, conteiner=ancora, ids_selecionados=[])
    assert capturado["caminho"] == "enviado.ifc"
    assert capturado["ctx"].conteiner.caminho == "enviado.ifc"
    assert capturado["ctx"].conteiner.unidades_representadas == 4
    assert capturado["ctx"].empreendimento.declaracoes[dec.TIPO_MODELO] == dec.TERRENO


def test_sem_ancora_o_conteiner_e_o_deduzido_do_agregado(monkeypatch, tmp_path):
    """``None`` = comportamento anterior à âncora recebida: a CLI e a suíte não mudam."""
    capturado = _capturar_contexto(monkeypatch, tmp_path)
    emp = Empreendimento(unidades_tipo=[
        UnidadeTipo(nome="Torre A",
                   modelo=ModeloBIM(caminho="da_edificacao.ifc",
                                    natureza=dec.EDIFICACAO_ISOLADA))])
    composicao.rodar(empreendimento=emp, ids_selecionados=[])
    assert capturado["caminho"] == "da_edificacao.ifc"
    assert capturado["ctx"].conteiner.caminho == "da_edificacao.ifc"


def test_a_assinatura_antiga_continua_levando_o_arquivo_ao_contexto(monkeypatch,
                                                                    tmp_path):
    """A CLI (``--ifc``) não conhece edificação nenhuma; o arquivo apresentado
    viaja como âncora, e é por isso que o EMP-001 segue tendo a natureza."""
    capturado = _capturar_contexto(monkeypatch, tmp_path)
    composicao.rodar(caminho_ifc="da_cli.ifc", tipo_modelo=dec.TERRENO,
                   ids_selecionados=[])
    ctx = capturado["ctx"]
    assert ctx.conteiner.caminho == "da_cli.ifc"
    assert ctx.conteiner.natureza == dec.TERRENO
    assert ctx.empreendimento.unidades_tipo == [], "a adaptação não inventa composição"


def test_ancora_com_argumentos_soltos_e_erro():
    with pytest.raises(ValueError, match="contêiner âncora"):
        composicao.rodar(caminho_ifc="x.ifc", conteiner=ModeloBIM(caminho="y.ifc"))


def test_empreendimento_sem_modelo_e_fluxo_sem_ifc(monkeypatch, tmp_path):
    """Sem contêiner o caminho é "" — nunca a descoberta de um IFC na pasta."""
    capturado = {}

    def _montar(caminho_ifc, pasta_gis, config, **kw):
        capturado["caminho"] = caminho_ifc
        raise RuntimeError("parar aqui")

    monkeypatch.setattr(composicao, "montar_contexto", _montar)
    monkeypatch.setattr(composicao, "_primeiro_ifc",
                        lambda pasta: pytest.fail("não se descobre IFC"))
    with pytest.raises(RuntimeError, match="parar aqui"):
        composicao.rodar(empreendimento=Empreendimento())
    assert capturado["caminho"] == ""


@pytest.mark.parametrize("legado", [
    {"caminho_ifc": ""}, {"tipo_modelo": "terreno"}, {"declaracoes": {}},
    {"terreno": object()}, {"municipio_ibge": "4307807"}])
def test_empreendimento_com_argumentos_soltos_e_erro(legado):
    with pytest.raises(ValueError):
        composicao.rodar(empreendimento=Empreendimento(), **legado)


def test_o_contexto_recebe_o_roteador_tipado(monkeypatch, tmp_path):
    capturado = {}
    real = composicao.montar_contexto

    def _montar(*a, **kw):
        ctx = real(*a, **kw)
        capturado["ctx"] = ctx
        return ctx

    monkeypatch.setattr(composicao, "montar_contexto", _montar)
    monkeypatch.setattr(pipeline, "executar", lambda ctx, ids_selecionados=None: [])
    monkeypatch.setattr(composicao, "_imprimir_resumo", lambda r: None)
    monkeypatch.setattr(composicao, "_carregar_config", lambda *a, **k: {
        "paths": {"relatorio": str(tmp_path / "r.json")}})
    falso = RoteadorFalso()
    composicao.rodar(caminho_ifc="", roteador_rede=falso)
    assert capturado["ctx"].roteador is falso
    assert capturado["ctx"].config["roteador_rede"] is falso


def test_arquivos_consumidos_nomeia_modelo_e_terreno_com_a_impressao():
    """ADR-035: o relatório registra os arquivos submetidos com o SHA-256, só
    com o nome (o caminho é da máquina que rodou)."""
    conteiner = ModeloBIM(caminho="entradas/ifc/estrela_i/E3_teto.ifc",
                          digest="d820")
    terreno = Terreno(origem="csv", nivel="poligonal", precisao="levantada",
                      crs_metrico="EPSG:31982", centro_wgs84=CENTRO,
                      procedencia={"arquivo": "entradas/gis/E0_memorial.csv",
                                   "sha256": "329a"})
    assert pipeline.arquivos_consumidos(conteiner, terreno) == [
        {"papel": "modelo", "arquivo": "E3_teto.ifc", "sha256": "d820"},
        {"papel": "terreno", "arquivo": "E0_memorial.csv", "sha256": "329a"}]


def test_arquivos_consumidos_sem_arquivo_de_origem():
    """Terreno desenhado não tem arquivo; terreno importado antes do registro
    entra sem impressão, para o relatório dizer que ela falta."""
    desenhado = Terreno(origem="desenhada", nivel="poligonal", precisao="aproximada",
                        crs_metrico="EPSG:31982", centro_wgs84=CENTRO)
    assert pipeline.arquivos_consumidos(None, desenhado) == []
    antigo = Terreno(origem="csv", nivel="poligonal", precisao="levantada",
                     crs_metrico="EPSG:31982", centro_wgs84=CENTRO,
                     procedencia={"arquivo": "memorial.csv"})
    assert pipeline.arquivos_consumidos(None, antigo) == [
        {"papel": "terreno", "arquivo": "memorial.csv", "sha256": ""}]


def test_o_relatorio_grava_os_arquivos_consumidos(ambiente):
    dados = ambiente("arquivos", empreendimento=Empreendimento(terreno=_terreno()),
                     ids_selecionados=[])
    assert dados["meta"]["arquivos"] == []
