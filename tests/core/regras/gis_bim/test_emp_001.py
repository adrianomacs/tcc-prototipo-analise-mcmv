"""Testes da regra EMP-001 (georreferenciamento) — ADR-008.

Reúne os testes que verificam o veredito de `EMP001().checar(...)` diretamente,
hoje separados por que módulo eles exercitam para chegar lá: o diagnóstico
LoGeoRef (`core.infra.ifc.georref.logeoref`, via modelos falsos) e o validador
de consistência de localização (`core.infra.ifc.georref.consistencia`, via um
modelo IFC real). Aqui o assunto é a regra em si, não o módulo que ela consome.
"""

from __future__ import annotations

import pytest

from core.dominio.contratos.regra import Estado
from core.dominio.empreendimento import Empreendimento, ModeloBIM
from core.dominio.vocabulario import motivos
from core.regras.gis_bim.emp_001_georreferenciamento import EMP001
from tests.apoio.contexto_bim import contexto_bim
from tests.apoio.ifc_falso import modelo_ifc2x3, modelo_nivel_30, modelo_nivel_50

# D3 (ADR-023): a natureza do modelo vem do CONTÊINER ÂNCORA da
# execução — `Contexto.conteiner` —, e não mais de um campo do empreendimento.
# O que ela governa continua sendo só a narrativa; a barra é o LoGeoRef 50.


def test_emp001_conforme_no_nivel_50():
    ctx = contexto_bim(modelo_ifc=modelo_nivel_50(),
                       conteiner=ModeloBIM(natureza="terreno"))
    r = EMP001().checar(ctx)
    assert r.estado is Estado.CONFORME
    assert r.detalhe.get("nivel") == 50


def test_emp001_nao_conforme_abaixo_do_50():
    ctx = contexto_bim(modelo_ifc=modelo_nivel_30(),
                       conteiner=ModeloBIM(natureza="edificacao_isolada"))
    r = EMP001().checar(ctx)
    assert r.estado is Estado.NAO_CONFORME
    assert "Faltam" in r.mensagem


def test_emp001_nao_conforme_em_ifc2x3():
    ctx = contexto_bim(modelo_ifc=modelo_ifc2x3(),
                       conteiner=ModeloBIM(natureza="terreno"))
    r = EMP001().checar(ctx)
    assert r.estado is Estado.NAO_CONFORME
    assert r.detalhe.get("schema") == "IFC2X3"


def test_emp001_nao_avaliavel_sem_modelo():
    r = EMP001().checar(contexto_bim(modelo_ifc=None))
    assert r.estado is Estado.NAO_AVALIAVEL


# --- integração (constrói IFC real; pula sem IfcOpenShell) ----------------

@pytest.mark.integracao
def test_emp001_inclui_localizacao_no_detalhe():
    pytest.importorskip("ifcopenshell")
    from tests.apoio.ifc_real import modelo_georreferenciado

    m = modelo_georreferenciado((42, 21, 31, 181945), (-71, -3, -24, -263305),
                                "The Netherlands")
    r = EMP001().checar(contexto_bim(
        modelo_ifc=m, conteiner=ModeloBIM(natureza="edificacao_isolada")))
    assert "localizacao" in r.detalhe
    assert r.detalhe["localizacao"]["distancia_site_crs_km"] > 1000
    assert any("IfcSite" in a for a in r.detalhe["localizacao"]["avisos"])


# --- confronto com a localização declarada (município) — ADR-008 ----------
#
# Estes casos isolam ``_confrontar_localizacao``, hoje só exercitada pela
# ficha de integração acima (que apenas confere que a chave existe no
# detalhe, sem passar por declaração de município). Aqui a âncora e a malha
# IBGE são substituídas (monkeypatch) para cobrir os três desfechos que a
# docstring da regra promete: dentro do município, fora dele, e confronto não
# avaliável (ressalva, sem reprovar o que já é normativamente conforme).

from core.dominio.vocabulario import declaracoes as dec
from core.infra.gis.ibge_malhas import ResultadoMalha
from core.infra.ifc.georref.ancora import Ancora


def _empreendimento_com_municipio():
    return Empreendimento(
        declaracoes={dec.MUNICIPIO_IBGE: "2704302", dec.UF: "AL",
                     dec.MUNICIPIO: "Maceió"})


def _ctx_com_municipio():
    return contexto_bim(modelo_ifc=modelo_nivel_50(),
                        conteiner=ModeloBIM(natureza="terreno"),
                        empreendimento=_empreendimento_com_municipio())


def test_emp001_conforme_ancora_dentro_do_municipio_declarado(monkeypatch):
    monkeypatch.setattr(
        "core.infra.ifc.georref.ancora.derivar",
        lambda modelo, **kw: Ancora(modo="preciso", lat=-9.66, lon=-35.73))
    monkeypatch.setattr(
        "core.infra.gis.ibge_malhas.conferir_ponto",
        lambda codigo, lat, lon: ResultadoMalha(
            dentro=True, fonte="cache",
            mensagem="Âncora do modelo dentro dos limites do município (malha IBGE, cache)."))

    ctx = _ctx_com_municipio()
    r = EMP001().checar(ctx)
    assert r.estado is Estado.CONFORME
    assert "Posicionamento confirmado dentro de Maceió/AL" in r.mensagem
    assert r.detalhe["localizacao_declarada"]["dentro"] is True


def test_emp001_nao_conforme_ancora_fora_do_municipio_declarado(monkeypatch):
    # LoGeoRef 50 atingido (georreferenciamento presente), mas o
    # posicionamento diverge da localização declarada -> não conforme; o
    # papel duplo do EMP-001 (ADR-008) distingue essa causa da falta de
    # estrutura de georreferenciamento.
    monkeypatch.setattr(
        "core.infra.ifc.georref.ancora.derivar",
        lambda modelo, **kw: Ancora(modo="preciso", lat=-8.0, lon=-34.9))
    monkeypatch.setattr(
        "core.infra.gis.ibge_malhas.conferir_ponto",
        lambda codigo, lat, lon: ResultadoMalha(
            dentro=False, fonte="cache",
            mensagem="Âncora do modelo fora dos limites do município (malha IBGE, cache)."))

    ctx = _ctx_com_municipio()
    r = EMP001().checar(ctx)
    assert r.estado is Estado.NAO_CONFORME
    assert "FORA dos limites de Maceió/AL" in r.mensagem
    assert r.detalhe["localizacao_declarada"]["dentro"] is False


def test_emp001_conforme_com_ressalva_quando_malha_indisponivel(monkeypatch):
    # Âncora derivável, mas sem malha (rede/cache indisponível) -> confronto
    # não avaliado; o núcleo normativo (LoGeoRef 50) já foi atendido, então
    # permanece conforme, com a ressalva explícita na mensagem (não um
    # quarto estado, por ADR-006).
    monkeypatch.setattr(
        "core.infra.ifc.georref.ancora.derivar",
        lambda modelo, **kw: Ancora(modo="preciso", lat=-9.66, lon=-35.73))
    monkeypatch.setattr(
        "core.infra.gis.ibge_malhas.conferir_ponto",
        lambda codigo, lat, lon: ResultadoMalha(
            mensagem="Malha municipal indisponível (sem rede); confronto não avaliado."))

    ctx = _ctx_com_municipio()
    r = EMP001().checar(ctx)
    assert r.estado is Estado.CONFORME
    assert "RESSALVA" in r.mensagem
    assert r.detalhe["localizacao_declarada"]["avaliado"] is False


def test_emp001_conforme_com_ressalva_quando_ancora_nao_derivavel(monkeypatch):
    # Âncora geográfica não derivável do modelo (sem CRS projetado nem
    # lat/lon no IfcSite) -> confronto nem chega a consultar a malha; mesma
    # ressalva de conforme.
    monkeypatch.setattr(
        "core.infra.ifc.georref.ancora.derivar",
        lambda modelo, **kw: Ancora(modo="indisponivel", mensagem="sem origem reprojetável"))

    ctx = _ctx_com_municipio()
    r = EMP001().checar(ctx)
    assert r.estado is Estado.CONFORME
    assert "RESSALVA" in r.mensagem
    assert "ancora geografica nao derivavel" in r.detalhe["localizacao_declarada"]["motivo"]


def test_emp001_sem_declaracao_de_municipio_nao_confronta(monkeypatch):
    # Sem UF/município declarado, o comportamento é o original (nenhuma
    # tentativa de confronto) — guarda de regressão para o `cross is None`.
    ctx = contexto_bim(modelo_ifc=modelo_nivel_50(),
                       conteiner=ModeloBIM(natureza="terreno"))
    r = EMP001().checar(ctx)
    assert r.estado is Estado.CONFORME
    assert "localizacao_declarada" not in r.detalhe


# --- aviso de posicionamento: âncora × poligonal do terreno — ADR-032 -------
#
# A âncora (origem do IfcMapConversion) é confrontada com a poligonal do
# Terreno declarado, no CRS métrico da poligonal, com tolerância de 5 m. É
# AVISO: o primeiro teste prende que o veredito do EMP-001 é o mesmo com e
# sem poligonal, em todos os desfechos do confronto com o município. Os três
# pontos são os do Estrela I (EPSG:31982): M1 (a gleba autoral ancora sobre
# ele — a divisa), a âncora do E1 da primeira rodada (translação de 18,64 m,
# 11,73 m fora da gleba) e a do E1 corrigido (6,89 m para dentro).

import os

from core.regras.gis_bim.emp_001_georreferenciamento import (
    POS_DENTRO,
    POS_FORA,
    POS_NAO_APLICAVEL,
    POS_NAO_AVALIADO,
    TOLERANCIA_POSICIONAMENTO_M,
)

_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))
_MEMORIAL = os.path.join(_RAIZ, "tests", "fixtures", "memorial_estrela_i.csv")

_EN_M1 = (409699.448, 6737101.912)
_EN_E1_R00 = (409706.41461584816, 6737162.8664360559)
_EN_E1_CORRIGIDO = (409724.40099123662, 6737157.9595266152)


def _latlon(e, n):
    from core.dominio import geometria
    lon, lat = geometria.reprojetar_ponto(e, n, "EPSG:31982", "EPSG:4326")
    return lat, lon


def _terreno_memorial():
    from core.infra.gis import csv_memorial
    leitura = csv_memorial.ler(_MEMORIAL, epsg="EPSG:31982")
    assert leitura.ok, leitura.erro
    return leitura.terreno


def _ancora_em(monkeypatch, en, modo="preciso"):
    lat, lon = _latlon(*en)
    monkeypatch.setattr(
        "core.infra.ifc.georref.ancora.derivar",
        lambda modelo, **kw: Ancora(modo=modo, lat=lat, lon=lon))


def _malha(monkeypatch, dentro):
    msg = {True: "dentro", False: "fora", None: "Malha indisponível (sem rede)."}[dentro]
    monkeypatch.setattr(
        "core.infra.gis.ibge_malhas.conferir_ponto",
        lambda codigo, lat, lon: ResultadoMalha(
            dentro=dentro, fonte="cache" if dentro is not None else "", mensagem=msg))


def _ctx(natureza="terreno", terreno=None, municipio=True, modelo=None):
    decl = ({dec.MUNICIPIO_IBGE: "4307807", dec.UF: "RS", dec.MUNICIPIO: "Estrela"}
            if municipio else {})
    return contexto_bim(modelo_ifc=modelo if modelo is not None else modelo_nivel_50(),
                        conteiner=ModeloBIM(natureza=natureza),
                        empreendimento=Empreendimento(declaracoes=decl, terreno=terreno))


@pytest.mark.parametrize("natureza", ["terreno", "terreno_com_edificacoes",
                                      "edificacao_isolada", ""])
@pytest.mark.parametrize("en", [_EN_M1, _EN_E1_R00, _EN_E1_CORRIGIDO, (0.0, 0.0)])
@pytest.mark.parametrize("municipio,dentro_mun", [(True, True), (True, False),
                                                  (True, None), (False, None)])
@pytest.mark.parametrize("fabrica", [modelo_nivel_50, modelo_nivel_30])
def test_veredito_do_emp001_nao_depende_da_poligonal(monkeypatch, natureza, en,
                                                     municipio, dentro_mun, fabrica):
    # ADR-032: o confronto com a poligonal nunca muda o veredito — nem
    # reprova o que o município aprovou, nem aprova o que ele reprovou.
    _ancora_em(monkeypatch, en)
    _malha(monkeypatch, dentro_mun)
    terreno = _terreno_memorial()

    sem = EMP001().checar(_ctx(natureza, None, municipio, fabrica()))
    com = EMP001().checar(_ctx(natureza, terreno, municipio, fabrica()))
    assert com.estado is sem.estado
    assert com.detalhe.get("motivo") == sem.detalhe.get("motivo")
    assert com.valor_encontrado == sem.valor_encontrado
    assert com.detalhe.get("localizacao_declarada") == sem.detalhe.get("localizacao_declarada")


def test_ancora_sobre_o_vertice_m1_e_compativel(monkeypatch):
    # A gleba autoral ancora exatamente sobre M1: a divisa. Distância 0 —
    # compatível, qualquer que seja a convenção de "dentro" na borda.
    _ancora_em(monkeypatch, _EN_M1)
    _malha(monkeypatch, True)
    r = EMP001().checar(_ctx("terreno", _terreno_memorial()))
    pos = r.detalhe["posicionamento_terreno"]
    assert pos["estado"] == POS_DENTRO
    assert pos["distancia_m"] == pytest.approx(0.0, abs=0.01)
    assert pos["tolerancia_m"] == TOLERANCIA_POSICIONAMENTO_M == 5.0
    assert "referência compatível com o terreno" in r.mensagem
    assert "contido" not in r.mensagem


def test_ancora_do_e1_da_primeira_rodada_cai_fora_e_so_avisa(monkeypatch):
    # §17.4 dos achados: translação de 18,64 m levou a âncora 11,73 m para
    # fora da gleba. A tolerância de 5 m pega; o veredito segue conforme.
    _ancora_em(monkeypatch, _EN_E1_R00)
    _malha(monkeypatch, True)
    r = EMP001().checar(_ctx("terreno", _terreno_memorial()))
    pos = r.detalhe["posicionamento_terreno"]
    assert r.estado is Estado.CONFORME
    assert pos["estado"] == POS_FORA
    assert pos["distancia_m"] == pytest.approx(11.73, abs=0.05)
    assert "AVISO" in r.mensagem
    assert pos["justificativa"]  # assimetria município × poligonal, por escrito


def test_ancora_do_e1_corrigido_e_compativel(monkeypatch):
    _ancora_em(monkeypatch, _EN_E1_CORRIGIDO)
    _malha(monkeypatch, True)
    r = EMP001().checar(_ctx("terreno_com_edificacoes", _terreno_memorial()))
    assert r.detalhe["posicionamento_terreno"]["estado"] == POS_DENTRO


def test_edificacao_isolada_nunca_fica_fora(monkeypatch):
    # Decisão 3 refinada (ADR-032): a tipologia não tem posição própria
    # (ADR-023) -> "não aplicável"; com âncora precisa e poligonal, a
    # distância fica registrada só como informação.
    _ancora_em(monkeypatch, _EN_E1_R00)
    _malha(monkeypatch, True)
    r = EMP001().checar(_ctx("edificacao_isolada", _terreno_memorial()))
    pos = r.detalhe["posicionamento_terreno"]
    assert pos["estado"] == POS_NAO_APLICAVEL
    assert pos["distancia_m"] is None
    assert pos["distancia_informativa_m"] == pytest.approx(11.73, abs=0.05)
    assert "fora" not in pos["mensagem"].lower()


@pytest.mark.parametrize("caso", ["ancora_aproximada", "sem_natureza",
                                  "sem_terreno", "terreno_ponto", "ancora_indisponivel"])
def test_nao_avaliado_com_motivo(monkeypatch, caso):
    from core.dominio import terreno as terreno_mod
    _ancora_em(monkeypatch, _EN_M1,
               modo="aproximado" if caso == "ancora_aproximada" else "preciso")
    if caso == "ancora_indisponivel":
        monkeypatch.setattr("core.infra.ifc.georref.ancora.derivar",
                            lambda modelo, **kw: Ancora(modo="indisponivel"))
    _malha(monkeypatch, True)
    terreno = {"sem_terreno": None,
               "terreno_ponto": terreno_mod.de_ponto_wgs84(*_latlon(*_EN_M1))
               }.get(caso, _terreno_memorial())
    natureza = "" if caso == "sem_natureza" else "terreno"
    r = EMP001().checar(_ctx(natureza, terreno))
    pos = r.detalhe["posicionamento_terreno"]
    assert pos["estado"] == POS_NAO_AVALIADO
    assert pos["motivo"]


@pytest.mark.integracao
def test_e1_da_primeira_rodada_real_fica_fora_da_gleba(monkeypatch):
    # O arquivo real (entradas/, não versionado): pula sem ele.
    pytest.importorskip("ifcopenshell")
    caminho = os.path.join(_RAIZ, "entradas", "ifc", "estrela_i", "R00", "E1_georref.ifc")
    if not os.path.exists(caminho):
        pytest.skip("entradas/ifc/estrela_i/R00/E1_georref.ifc não existe")
    import ifcopenshell
    _malha(monkeypatch, True)
    r = EMP001().checar(_ctx("terreno", _terreno_memorial(),
                             modelo=ifcopenshell.open(caminho)))
    pos = r.detalhe["posicionamento_terreno"]
    assert r.estado is Estado.CONFORME
    assert pos["estado"] == POS_FORA
    assert pos["distancia_m"] == pytest.approx(11.73, abs=0.05)


def test_sem_modelo_o_motivo_e_insumo_do_proponente_ausente():
    """ADR-033: sem o modelo, a causa é o que só o proponente entrega."""
    r = EMP001().checar(contexto_bim(modelo_ifc=None))
    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.INSUMO_DO_PROPONENTE_AUSENTE
