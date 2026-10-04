"""Testes do núcleo do terreno (Enquadramento — núcleo do Terreno).

Lógica pura: dependem só de shapely/pyproj, não de IFC nem de Streamlit.
Cobrem o que o núcleo promete — CRS métrico correto, medidas no plano, nível de
capacidade, avisos honestos e ida e volta do artefato.
"""

from __future__ import annotations

import math

import pytest

from core.dominio import geometria as crs
from core.dominio import terreno as trn
from core.dominio.contratos.regra import Estado, Regra
from core.dominio.vocabulario import motivos
from core.infra.persistencia import artefato

# Campo Grande/MS — fuso 21S; São Paulo — fuso 23S (âncora conhecida: 31983).
CG_LON, CG_LAT = -54.6215, -20.4712
SP_LON, SP_LAT = -46.6333, -23.5505


def _quadrado(lon: float, lat: float, lado_m: float = 100.0):
    """Quadrado aproximado de ``lado_m`` centrado em (lon, lat), em graus."""
    dlat = lado_m / 2.0 / 111_320.0
    dlon = lado_m / 2.0 / (111_320.0 * math.cos(math.radians(lat)))
    return [(lon - dlon, lat - dlat), (lon + dlon, lat - dlat),
            (lon + dlon, lat + dlat), (lon - dlon, lat + dlat)]


# --- CRS -------------------------------------------------------------------

def test_fuso_utm_conhecido():
    assert crs.fuso_utm(CG_LON) == 21
    assert crs.fuso_utm(SP_LON) == 23


def test_epsg_metrico_sirgas_sul():
    assert crs.epsg_metrico(SP_LON, SP_LAT) == "EPSG:31983"   # âncora: 23S
    assert crs.epsg_metrico(CG_LON, CG_LAT) == "EPSG:31981"   # 21S


def test_epsg_metrico_nomeia_o_fuso_esperado_no_registro_epsg():
    """Guarda contra erro de deslocamento na aritmética dos códigos EPSG."""
    from pyproj import CRS

    assert "23S" in CRS.from_user_input(crs.epsg_metrico(SP_LON, SP_LAT)).name
    assert "21S" in CRS.from_user_input(crs.epsg_metrico(CG_LON, CG_LAT)).name


def test_epsg_metrico_fora_do_sirgas_cai_em_wgs84_utm():
    assert crs.epsg_metrico(2.35, 48.85) == "EPSG:32631"      # Paris, 31N


# --- Construção por poligonal ---------------------------------------------

def test_poligonal_mede_area_e_perimetro_no_plano():
    t = trn.de_poligonal_wgs84(_quadrado(CG_LON, CG_LAT, 100.0),
                               origem=trn.ORIGEM_DESENHADA,
                               precisao=trn.PRECISAO_APROXIMADA)
    assert t.nivel == trn.NIVEL_POLIGONAL
    assert t.area_m2 == pytest.approx(10_000.0, rel=0.01)
    assert t.perimetro_m == pytest.approx(400.0, rel=0.01)
    assert t.crs_metrico == "EPSG:31981"


def test_centro_da_poligonal_coincide_com_o_centro_geometrico():
    t = trn.de_poligonal_wgs84(_quadrado(CG_LON, CG_LAT), origem=trn.ORIGEM_DESENHADA,
                               precisao=trn.PRECISAO_APROXIMADA)
    lat, lon = t.centro_wgs84
    assert lat == pytest.approx(CG_LAT, abs=1e-6)
    assert lon == pytest.approx(CG_LON, abs=1e-6)


def test_anel_fechado_na_entrada_nao_duplica_vertice():
    coords = _quadrado(CG_LON, CG_LAT)
    aberta = trn.de_poligonal_wgs84(coords, origem=trn.ORIGEM_CSV,
                                    precisao=trn.PRECISAO_LEVANTADA)
    fechada = trn.de_poligonal_wgs84(coords + [coords[0]], origem=trn.ORIGEM_CSV,
                                     precisao=trn.PRECISAO_LEVANTADA)
    assert fechada.area_m2 == pytest.approx(aberta.area_m2, rel=1e-9)


def test_poligonal_com_menos_de_tres_vertices_e_recusada():
    with pytest.raises(ValueError):
        trn.de_poligonal_wgs84([(CG_LON, CG_LAT), (CG_LON + 0.001, CG_LAT)],
                               origem=trn.ORIGEM_CSV,
                               precisao=trn.PRECISAO_LEVANTADA)


def test_centroide_fora_da_poligonal_gera_aviso():
    """Lote em 'U': o centróide cai no vazio — mantido, mas declarado."""
    passo = 0.001
    u = [(0, 0), (3, 0), (3, 3), (2, 3), (2, 1), (1, 1), (1, 3), (0, 3)]
    coords = [(CG_LON + x * passo, CG_LAT + y * passo) for x, y in u]
    t = trn.de_poligonal_wgs84(coords, origem=trn.ORIGEM_DESENHADA,
                               precisao=trn.PRECISAO_APROXIMADA)
    assert any("centróide cai fora" in a for a in t.avisos)
    assert t.nivel == trn.NIVEL_POLIGONAL   # segue utilizável


def test_terreno_a_cavaleiro_de_dois_fusos_avisa():
    coords = [(-54.10, -20.40), (-53.90, -20.40), (-53.90, -20.20), (-54.10, -20.20)]
    t = trn.de_poligonal_wgs84(coords, origem=trn.ORIGEM_CSV,
                               precisao=trn.PRECISAO_LEVANTADA)
    assert any("cavaleiro" in a for a in t.avisos)


# --- Construção por ponto e nível de capacidade ---------------------------

def test_ponto_produz_nivel_ponto():
    t = trn.de_ponto_wgs84(CG_LAT, CG_LON)
    assert t.nivel == trn.NIVEL_PONTO
    assert t.poligonal is None
    assert t.area_m2 is None


def test_coordenada_invalida_e_recusada():
    with pytest.raises(ValueError):
        trn.de_ponto_wgs84(-200.0, CG_LON)


def test_atende_distingue_ponto_de_poligonal():
    ponto = trn.de_ponto_wgs84(CG_LAT, CG_LON)
    poli = trn.de_poligonal_wgs84(_quadrado(CG_LON, CG_LAT),
                                  origem=trn.ORIGEM_DESENHADA,
                                  precisao=trn.PRECISAO_APROXIMADA)
    assert ponto.atende("") and poli.atende("")
    assert ponto.atende(trn.NIVEL_PONTO) and poli.atende(trn.NIVEL_PONTO)
    assert not ponto.atende(trn.NIVEL_POLIGONAL)
    assert poli.atende(trn.NIVEL_POLIGONAL)


# --- Artefato --------------------------------------------------------------

def test_ida_e_volta_do_artefato_preserva_geometria(tmp_path):
    original = trn.de_poligonal_wgs84(_quadrado(CG_LON, CG_LAT), origem=trn.ORIGEM_CSV,
                                      precisao=trn.PRECISAO_LEVANTADA,
                                      procedencia={"arquivo": "memorial.csv"})
    artefato.gravar(original, str(tmp_path))
    lido = artefato.ler(str(tmp_path))

    assert lido is not None
    assert lido.nivel == original.nivel
    assert lido.precisao == original.precisao
    assert lido.crs_metrico == original.crs_metrico
    assert lido.procedencia["arquivo"] == "memorial.csv"
    assert lido.centro_wgs84 == pytest.approx(original.centro_wgs84, abs=1e-9)
    # A geometria métrica é reconstruída por reprojeção, não guardada.
    assert lido.poligonal.area == pytest.approx(original.poligonal.area, rel=1e-6)


def test_artefato_ausente_devolve_none(tmp_path):
    assert artefato.ler(str(tmp_path)) is None


def test_artefato_corrompido_devolve_none_em_vez_de_estourar(tmp_path):
    (tmp_path / artefato.NOME_ARQUIVO).write_text("{isso nao e json", encoding="utf-8")
    assert artefato.ler(str(tmp_path)) is None


# --- Motivo do não avaliável ----------------------------------------------

def test_nao_avaliavel_carrega_o_motivo_no_detalhe():
    class _R(Regra):
        id = "TST-001"

    r = _R().nao_avaliavel(motivo=motivos.TERRENO_INSUFICIENTE, mensagem="x")
    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.TERRENO_INSUFICIENTE


def test_nao_avaliavel_sem_motivo_permanece_compativel():
    class _R(Regra):
        id = "TST-002"

    r = _R().nao_avaliavel(mensagem="sem motivo declarado")
    assert r.estado is Estado.NAO_AVALIAVEL
    assert motivos.CHAVE not in r.detalhe


def test_motivo_nao_sobrescreve_detalhe_existente():
    class _R(Regra):
        id = "TST-003"

    r = _R().nao_avaliavel(motivo=motivos.INSUMO_AUSENTE,
                           detalhe={"tipo": "larguras"})
    assert r.detalhe["tipo"] == "larguras"
    assert r.detalhe[motivos.CHAVE] == motivos.INSUMO_AUSENTE


# ---------------------------------------------------------------------------
# O contêiner do terreno (ADR-023)
# ---------------------------------------------------------------------------

def test_terreno_nasce_sem_conteiner():
    t = trn.de_ponto_wgs84(CG_LAT, CG_LON)
    assert t.modelo is None


def test_conteiner_do_terreno_sobrevive_a_ida_e_volta():
    from core.dominio.modelo_bim import ModeloBIM

    t = trn.de_ponto_wgs84(CG_LAT, CG_LON, origem=trn.ORIGEM_IFC,
                           precisao=trn.PRECISAO_LEVANTADA)
    t.modelo = ModeloBIM(caminho="terreno.ifc", schema="IFC4", natureza="terreno")
    volta = trn.Terreno.from_dict(t.to_dict())
    assert volta.modelo == t.modelo
    assert volta.modelo.unidades_representadas == 0, (
        "o modelo só do terreno não representa UH nenhuma (ADR-021)")


def test_conteiner_do_terreno_nao_muda_a_capacidade_do_terreno():
    """Conferência não é veredito (ADR-023): anexar o contêiner não promove um
    terreno de nível ``ponto`` a poligonal."""
    from core.dominio.modelo_bim import ModeloBIM

    t = trn.de_ponto_wgs84(CG_LAT, CG_LON)
    t.modelo = ModeloBIM(caminho="terreno.ifc", natureza="terreno")
    assert t.nivel == trn.NIVEL_PONTO and t.tem_poligonal is False
    assert t.atende(trn.NIVEL_POLIGONAL) is False
