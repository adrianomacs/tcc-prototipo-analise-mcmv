"""Leitura do CSV de memorial descritivo — coordenadas projetadas (ADR-029).

O caso de referência é a planilha de cálculos real do estudo de caso
(``tests/fixtures/memorial_estrela_i.csv``): seis vértices em EPSG:31982, a
distância declarada de cada lado e a área da matrícula (95.907,00 m²). É
contra ela que a conferência vértice a vértice fica presa — se a leitura, a
reprojeção ou a medida mudarem, é aqui que estoura.
"""

from __future__ import annotations

import os

import pytest

from core.dominio import terreno as terreno_mod
from core.infra.gis import csv_memorial as leitor
from tests.conftest import FIXTURES, RAIZ

MEMORIAL_REAL = os.path.join(FIXTURES, "memorial_estrela_i.csv")

# Triângulo válido dentro do fuso 22S (mesma região do caso real).
SIMPLES = (
    "vertice;leste;norte\n"
    "P1;409699,448;6737101,912\n"
    "P2;409777,494;6737077,594\n"
    "P3;410074,415;6738021,410\n"
)


def _csv(tmp_path, texto: str, nome: str = "memorial.csv") -> str:
    caminho = tmp_path / nome
    caminho.write_text(texto, encoding="utf-8")
    return str(caminho)


# ---------------------------------------------------------------------------
# O caso real, vértice a vértice
# ---------------------------------------------------------------------------

def test_planilha_real_produz_o_terreno_do_estudo_de_caso():
    l = leitor.ler(MEMORIAL_REAL, epsg="EPSG:31982",
                   area_declarada_m2="95.907,00",
                   epsg_fonte=leitor.FONTE_EPSG_MUNICIPIO)
    assert l.ok, l.erro
    t = l.terreno
    assert t.origem == terreno_mod.ORIGEM_CSV
    assert t.nivel == terreno_mod.NIVEL_POLIGONAL
    assert t.precisao == terreno_mod.PRECISAO_LEVANTADA
    assert t.crs_metrico == "EPSG:31982"
    assert t.atende("ponto") and t.atende("poligonal")


def test_planilha_real_cabecalho_e_pares_de_vertices():
    # "VÉRTICES", "LESTE (L)", "NORTE(N)": o cabeçalho como vem no projeto de
    # implantação; "M1 — M2" nomeia o LADO e a coordenada é a do primeiro.
    l = leitor.ler(MEMORIAL_REAL, epsg="EPSG:31982")
    assert [v.nome for v in l.vertices] == ["M1", "M2", "M3", "M4", "M5", "M6"]
    assert set(l.colunas_detectadas) == {"vertice", "distancia", "leste", "norte"}


def test_planilha_real_area_conferida_contra_o_memorial():
    l = leitor.ler(MEMORIAL_REAL, epsg="EPSG:31982",
                   area_declarada_m2="95.907,00")
    proc = l.terreno.procedencia
    # Shoelace sobre os próprios vértices, no CRS do memorial.
    assert proc["area_no_crs_do_memorial_m2"] == pytest.approx(95906.03, abs=0.05)
    # A matrícula declara 95.907,00 — divergência de arredondamento (~10 ppm),
    # muito abaixo da tolerância de 0,5%: sem aviso de área.
    assert abs(proc["desvio_area_declarada_pct"]) < 0.01
    assert not [a for a in l.terreno.avisos if "diverge" in a]
    # A remedida no fuso do centróide (ADR-013) é declarada em ppm; aqui o
    # fuso do centróide É o CRS do memorial, então o desvio é ~0.
    assert abs(proc["desvio_reprojecao_ppm"]) < 1.0


def test_planilha_real_todas_as_distancias_conferem():
    l = leitor.ler(MEMORIAL_REAL, epsg="EPSG:31982")
    conf = l.terreno.procedencia["conferencia_distancias"]
    assert conf["lados_declarados"] == 6
    assert conf["lados_conferidos"] == 6
    assert conf["divergencias"] == []


def test_planilha_real_centro_cai_no_lugar_certo():
    l = leitor.ler(MEMORIAL_REAL, epsg="EPSG:31982")
    lat, lon = l.terreno.centro_wgs84
    assert lat == pytest.approx(-29.4874, abs=0.001)
    assert lon == pytest.approx(-51.9293, abs=0.001)


# ---------------------------------------------------------------------------
# Formato e dialeto
# ---------------------------------------------------------------------------

def test_decimal_decidido_por_valor_nao_pelo_dialeto(tmp_path):
    com_ponto = ("vertice;leste;norte\n"
                 "P1;409699.448;6737101.912\n"
                 "P2;409777.494;6737077.594\n"
                 "P3;410074.415;6738021.410\n")
    a = leitor.ler(_csv(tmp_path, SIMPLES, "a.csv"), epsg="EPSG:31982")
    b = leitor.ler(_csv(tmp_path, com_ponto, "b.csv"), epsg="EPSG:31982")
    assert a.ok and b.ok
    assert a.terreno.area_m2 == pytest.approx(b.terreno.area_m2, rel=1e-9)


def test_anel_ja_fechado_no_arquivo(tmp_path):
    fechado = SIMPLES + "P1;409699,448;6737101,912\n"
    l = leitor.ler(_csv(tmp_path, fechado), epsg="EPSG:31982")
    assert l.ok
    assert len(l.vertices) == 3


def test_coluna_obrigatoria_ausente(tmp_path):
    l = leitor.ler(_csv(tmp_path, "vertice;leste\nP1;409699,448\n"),
                   epsg="EPSG:31982")
    assert not l.ok
    assert l.faltando == ["norte"]
    assert "modelo" in l.erro


def test_linha_ilegivel_rejeita_o_arquivo_inteiro(tmp_path):
    # Diferença deliberada em relação ao leitor de equipamentos: um vértice a
    # menos é OUTRA poligonal, então linha rejeitada = arquivo rejeitado.
    quebrado = SIMPLES.replace("P2;409777,494;6737077,594", "P2;;6737077,594")
    l = leitor.ler(_csv(tmp_path, quebrado), epsg="EPSG:31982")
    assert not l.ok
    assert l.rejeitadas and l.rejeitadas[0][0] == 3
    assert "3" in l.erro


def test_menos_de_tres_vertices(tmp_path):
    l = leitor.ler(_csv(tmp_path, "vertice;leste;norte\n"
                                  "P1;409699,448;6737101,912\n"
                                  "P2;409777,494;6737077,594\n"),
                   epsg="EPSG:31982")
    assert not l.ok
    assert "3 vértices" in l.erro


# ---------------------------------------------------------------------------
# Plausibilidade e CRS (ADR-029)
# ---------------------------------------------------------------------------

def test_lat_lon_no_lugar_de_e_n_e_recusado(tmp_path):
    geografico = ("vertice;leste;norte\n"
                  "P1;-51,9315;-29,4924\n"
                  "P2;-51,9307;-29,4926\n"
                  "P3;-51,9276;-29,4841\n")
    l = leitor.ler(_csv(tmp_path, geografico), epsg="EPSG:31982")
    assert not l.ok
    assert "GEOGRÁFICAS" in l.erro and "PROJETADAS" in l.erro


def test_coordenada_local_sem_amarracao_e_recusada(tmp_path):
    local = ("vertice;leste;norte\n"
             "P1;100,0;200,0\nP2;180,0;200,0\nP3;180,0;320,0\n")
    l = leitor.ler(_csv(tmp_path, local), epsg="EPSG:31982")
    assert not l.ok
    assert "amarração" in l.erro


def test_epsg_geografico_e_recusado(tmp_path):
    l = leitor.ler(_csv(tmp_path, SIMPLES), epsg="EPSG:4674")
    assert not l.ok
    assert "PROJETADO" in l.erro


def test_epsg_invalido(tmp_path):
    l = leitor.ler(_csv(tmp_path, SIMPLES), epsg="XPTO")
    assert not l.ok
    assert "EPSG" in l.erro


def test_hemisferio_errado_avisa_pela_area_de_uso(tmp_path):
    # SIRGAS 2000 / UTM 22N com northing do hemisfério sul: o terreno
    # reprojetado cai fora da área de uso oficial do CRS. Aviso, não veto —
    # quem barra a confirmação é o confronto com os limites municipais.
    l = leitor.ler(_csv(tmp_path, SIMPLES), epsg="EPSG:31976")
    assert l.ok
    assert any("área de uso" in a for a in l.terreno.avisos)


# ---------------------------------------------------------------------------
# Procedência e apoios da tela
# ---------------------------------------------------------------------------

def test_procedencia_registra_a_declaracao_do_crs(tmp_path):
    l = leitor.ler(_csv(tmp_path, SIMPLES), epsg="31982",
                   epsg_fonte=leitor.FONTE_EPSG_MUNICIPIO)
    proc = l.terreno.procedencia
    assert proc["epsg_origem"] == "EPSG:31982"          # normalizado
    assert proc["epsg_origem_fonte"] == leitor.FONTE_EPSG_MUNICIPIO
    assert proc["vertices"] == ["P1", "P2", "P3"]


def test_area_declarada_divergente_avisa(tmp_path):
    l = leitor.ler(_csv(tmp_path, SIMPLES), epsg="EPSG:31982",
                   area_declarada_m2="999.999,00")
    assert l.ok
    assert any("diverge" in a for a in l.terreno.avisos)


def test_distancia_divergente_avisa_com_o_lado(tmp_path):
    com_dist = ("vertice;leste;norte;distancia_m\n"
                "P1;409699,448;6737101,912;81,75\n"
                "P2;409777,494;6737077,594;989,42\n"
                "P3;410074,415;6738021,410;500,00\n")   # P3–P1 real ≈ 984 m
    l = leitor.ler(_csv(tmp_path, com_dist), epsg="EPSG:31982")
    assert l.ok
    conf = l.terreno.procedencia["conferencia_distancias"]
    assert conf["lados_declarados"] == 3
    assert len(conf["divergencias"]) == 1
    assert conf["divergencias"][0]["de"] == "P3"
    assert any("divergente" in a for a in l.terreno.avisos)


def test_modelo_baixavel_passa_limpo():
    caminho = os.path.join(RAIZ, "config", "modelo_memorial_descritivo.csv")
    l = leitor.ler(caminho, epsg="EPSG:31981")
    assert l.ok, l.erro
    conf = l.terreno.procedencia["conferencia_distancias"]
    assert conf["lados_declarados"] == 4
    assert conf["divergencias"] == []
    assert not l.terreno.avisos


def test_epsgs_utm_sirgas_para_a_tela():
    opcoes = leitor.epsgs_utm_sirgas()
    codigos = [c for c, _ in opcoes]
    assert "EPSG:31982" in codigos
    assert len(codigos) == len(set(codigos))
    assert all(r.startswith("SIRGAS 2000 / UTM fuso") for _, r in opcoes)


def test_procedencia_registra_a_impressao_digital_do_arquivo():
    """ADR-035: o relatório cita o CSV pelo nome e o amarra pelo conteúdo."""
    import hashlib

    l = leitor.ler(MEMORIAL_REAL, epsg="EPSG:31982")
    with open(MEMORIAL_REAL, "rb") as f:
        assert l.terreno.procedencia["sha256"] == hashlib.sha256(f.read()).hexdigest()
