"""Testes da entrada por IFC (Enquadramento — R3).

Duas metades, e a distinção é honesta:

* a **matemática** da transformação modelo -> projetado e as **decisões da
  cascata** são testadas aqui, com números conferidos à mão e modelos falsos —
  inclusive a extração da poligonal quando o FootPrint é um ``IfcPolyline``,
  que não precisa do IfcOpenShell;
* a extração por **malha 3D** (``create_shape``) só roda com IfcOpenShell e
  arquivo real: é validada pelo CLI
  (``python -m core.infra.ifc.extrator_terreno <arquivo.ifc>``), não por teste.
"""

from __future__ import annotations

import math

import pytest

from core.dominio import terreno as trn
from core.infra.ifc import extrator_terreno as de_ifc
from core.infra.ifc.georref import transformacao
from tests.apoio import ifc_falso as _fakes

# Coordenadas dos fakes: EPSG:31983 (SIRGAS 2000 / UTM 23S), E=200000 N=7500000.
E0, N0 = 200000.0, 7500000.0


def _quadrado_local(lado: float = 100.0):
    """Quadrado de ``lado`` metros na origem do modelo (coordenadas locais)."""
    return [(0.0, 0.0), (lado, 0.0), (lado, lado), (0.0, lado)]


# ===========================================================================
# Transformação modelo -> projetado
# ===========================================================================

def test_sem_rotacao_apenas_desloca():
    t, _ = transformacao.compor_modelo_para_projetado(
        {"eastings": E0, "northings": N0, "x_axis_abscissa": 1.0,
         "x_axis_ordinate": 0.0, "scale": 1.0})
    assert t(10.0, 5.0) == pytest.approx((E0 + 10.0, N0 + 5.0))


def test_rotacao_de_90_graus_leva_x_para_o_norte():
    t, proc = transformacao.compor_modelo_para_projetado(
        {"eastings": E0, "northings": N0, "x_axis_abscissa": 0.0,
         "x_axis_ordinate": 1.0})
    assert t(10.0, 0.0) == pytest.approx((E0, N0 + 10.0))
    assert proc["rotacao_graus"] == pytest.approx(90.0)


def test_vetor_do_eixo_nao_unitario_e_normalizado_e_avisado():
    """Sem normalizar, um vetor de norma 2 dobraria todas as distâncias."""
    t, proc = transformacao.compor_modelo_para_projetado(
        {"eastings": 0.0, "northings": 0.0, "x_axis_abscissa": 2.0,
         "x_axis_ordinate": 0.0})
    assert t(10.0, 0.0) == pytest.approx((10.0, 0.0))
    assert any("unitário" in a for a in proc["avisos"])


def test_rotacao_de_45_graus():
    t, proc = transformacao.compor_modelo_para_projetado(
        {"eastings": 0.0, "northings": 0.0, "x_axis_abscissa": 1.0,
         "x_axis_ordinate": 1.0})
    assert proc["rotacao_graus"] == pytest.approx(45.0)
    assert t(math.sqrt(2.0), 0.0) == pytest.approx((1.0, 1.0))


def test_escala_do_mapconversion_e_aplicada_e_avisada():
    t, proc = transformacao.compor_modelo_para_projetado(
        {"eastings": 0.0, "northings": 0.0, "x_axis_abscissa": 1.0,
         "x_axis_ordinate": 0.0, "scale": 2.0})
    assert t(10.0, 0.0) == pytest.approx((20.0, 0.0))
    assert any("Escala" in a for a in proc["avisos"])


def test_eixo_ausente_assume_rotacao_zero_e_avisa():
    t, proc = transformacao.compor_modelo_para_projetado(
        {"eastings": E0, "northings": N0})
    assert t(1.0, 0.0) == pytest.approx((E0 + 1.0, N0))
    assert any("rotação zero" in a for a in proc["avisos"])


def test_vetor_nulo_nao_estoura():
    t, proc = transformacao.compor_modelo_para_projetado(
        {"eastings": 0.0, "northings": 0.0, "x_axis_abscissa": 0.0,
         "x_axis_ordinate": 0.0})
    assert t(3.0, 4.0) == pytest.approx((3.0, 4.0))
    assert any("nulo" in a for a in proc["avisos"])


# ===========================================================================
# Cascata
# ===========================================================================

def test_modelo_sem_ifcsite_nao_deriva_e_ensina_o_que_falta():
    res = de_ifc.resolver(_fakes.modelo_sem_site())
    assert not res.ok
    assert any("IfcSite" in m for m in res.diagnostico)
    assert any("IfcProjectedCRS" in m for m in res.diagnostico)


def test_footprint_com_logeoref_50_produz_poligonal_levantada():
    modelo = _fakes.modelo_site_com_footprint(_quadrado_local(100.0))
    res = de_ifc.resolver(modelo, nome_arquivo="fake.ifc")

    assert res.ok, res.diagnostico
    t = res.terreno
    assert t.nivel == trn.NIVEL_POLIGONAL
    assert t.origem == trn.ORIGEM_IFC
    assert t.precisao == trn.PRECISAO_LEVANTADA
    assert t.area_m2 == pytest.approx(10_000.0, rel=0.01)
    assert t.perimetro_m == pytest.approx(400.0, rel=0.01)
    assert "FootPrint" in res.detalhe["metodo_geometria"]
    assert res.detalhe["transformacao"]["eastings"] == E0


def test_poligonal_do_ifc_cai_no_fuso_do_crs_do_modelo():
    """A medida é refeita no CRS que o protótipo escolhe; para estes offsets,
    o fuso coincide com o EPSG:31983 declarado no modelo."""
    modelo = _fakes.modelo_site_com_footprint(_quadrado_local())
    t = de_ifc.resolver(modelo).terreno
    assert t.crs_metrico == "EPSG:31983"
    assert t.procedencia["epsg_modelo"] == "EPSG:31983"


def test_rotacao_do_mapconversion_nao_altera_area():
    """Giro no plano preserva medida — guarda contra erro de sinal na rotação."""
    reto = de_ifc.resolver(_fakes.modelo_site_com_footprint(
        _quadrado_local())).terreno
    girado = de_ifc.resolver(_fakes.modelo_site_com_footprint(
        _quadrado_local(), xa=0.0, xo=1.0)).terreno
    assert girado.area_m2 == pytest.approx(reto.area_m2, rel=1e-6)
    assert girado.centro_wgs84 != reto.centro_wgs84   # mesmo tamanho, outro lugar


def test_geometria_sem_georreferenciamento_degrada_para_ponto_e_explica():
    """Há poligonal no modelo, mas sem CRS projetado ela não vai ao território."""
    modelo = _fakes.modelo_site_com_footprint(_quadrado_local(), nivel_50=False)
    res = de_ifc.resolver(modelo)

    assert res.ok
    assert res.terreno.nivel == trn.NIVEL_PONTO
    assert any("LoGeoRef" in m for m in res.diagnostico)
    assert any("não pode ser levada ao território" in m for m in res.diagnostico)
    assert any("LoGeoRef" in a for a in res.terreno.avisos)


def test_site_apenas_com_coordenada_produz_ponto_declarado():
    res = de_ifc.resolver(_fakes.modelo_nivel_30())
    assert res.ok
    t = res.terreno
    assert t.nivel == trn.NIVEL_PONTO
    assert t.precisao == trn.PRECISAO_DECLARADA
    assert any("coordenada declarada no" in a for a in t.avisos)


def test_sem_coordenada_no_site_usa_a_origem_do_modelo_com_aviso_forte():
    res = de_ifc.resolver(_fakes.modelo_nivel_50_sem_coordenadas())
    assert res.ok
    t = res.terreno
    assert t.nivel == trn.NIVEL_PONTO
    assert any("ponto de inserção do modelo" in a for a in t.avisos)
    assert t.procedencia["entrada"] == "origem do IfcMapConversion"


def test_dois_sites_sem_compositiontype_declarado_sao_recusados():
    """Sem CompositionType não há como saber se é decomposição: recusa.

    Complementa ``test_sites_irmaos_independentes_sao_recusados`` (que declara
    .ELEMENT.): aqui o atributo está ausente, como em exportador desleixado.
    """
    modelo = _fakes.modelo_dois_sites_com_footprint(_quadrado_local())
    res = de_ifc.resolver(modelo)
    assert not res.ok
    assert any("2 IfcSite independentes" in m for m in res.diagnostico)
    assert any("envie o modelo do terreno" in m for m in res.diagnostico)
    assert res.detalhe["sites_com_geometria"] == 2


def test_matricula_do_site_entra_na_procedencia():
    modelo = _fakes.modelo_site_com_footprint(_quadrado_local(),
                                              matricula="12.345")
    t = de_ifc.resolver(modelo).terreno
    assert t.procedencia["matricula_ifc"] == "12.345"


def test_resumo_dos_sites_expoe_as_representacoes_para_o_diagnostico():
    """O CLI imprime isso — é como descobrimos o que os IFC reais trazem."""
    modelo = _fakes.modelo_site_com_footprint(_quadrado_local())
    d = de_ifc.resolver(modelo).detalhe
    rep = d["sites"][0]["representacoes"][0]
    assert rep["identificador"] == "FootPrint"
    assert rep["itens"] == ["IfcPolyline"]
    assert "itens_obj" not in rep      # objetos IFC não vazam para o detalhe

# ===========================================================================
# Abertura do arquivo: schema não suportado é DIAGNÓSTICO, não traceback
# ===========================================================================

def test_schema_declarado_le_os_dois_formatos_de_header(tmp_path):
    from core.infra.ifc import leitor_modelo as leitor_ifc

    casos = {
        "com_espaco.ifc": "ISO-10303-21;\nHEADER;\nFILE_SCHEMA (('IFC4X3_RC2'));\nENDSEC;",
        "sem_espaco.ifc": "ISO-10303-21;\nHEADER;\nFILE_SCHEMA(('IFC4'));\nENDSEC;",
    }
    esperado = {"com_espaco.ifc": "IFC4X3_RC2", "sem_espaco.ifc": "IFC4"}
    for nome, conteudo in casos.items():
        alvo = tmp_path / nome
        alvo.write_text(conteudo, encoding="utf-8")
        assert leitor_ifc.schema_declarado(str(alvo)) == esperado[nome]


def test_schema_declarado_em_arquivo_sem_header_devolve_vazio(tmp_path):
    from core.infra.ifc import leitor_modelo as leitor_ifc

    alvo = tmp_path / "qualquer.txt"
    alvo.write_text("isto nao e um IFC", encoding="utf-8")
    assert leitor_ifc.schema_declarado(str(alvo)) == ""
    assert leitor_ifc.schema_declarado(str(tmp_path / "inexistente.ifc")) == ""


def test_arquivo_com_schema_nao_suportado_vira_diagnostico(tmp_path):
    """Caso real: UT_GeoRef_1.ifc declara IFC4X3_RC2 e o IfcOpenShell recusa.

    O protótipo tem de NOMEAR o schema e dizer o que fazer, em vez de estourar.
    """
    alvo = tmp_path / "rc2.ifc"
    alvo.write_text("ISO-10303-21;\nHEADER;\nFILE_SCHEMA (('IFC4X3_RC2'));\n"
                    "ENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n",
                    encoding="utf-8")

    res = de_ifc.resolver_arquivo(str(alvo))
    assert not res.ok
    assert res.detalhe["abertura_falhou"] is True
    assert res.detalhe["schema"] == "IFC4X3_RC2"
    assert any("IFC4X3_RC2" in m for m in res.diagnostico)
    assert any("IFC4" in m and "_RC" in m for m in res.diagnostico)

# ===========================================================================
# IfcGeographicElement TERRAIN — a superfície do terreno
# ===========================================================================

def _quadrado_deslocado(lado: float, dx: float = 0.0, dy: float = 0.0):
    return [(dx, dy), (dx + lado, dy), (dx + lado, dy + lado), (dx, dy + lado)]


def test_reconhece_terreno_por_predefinedtype_e_por_objecttype():
    """Dois padrões reais: PredefinedType=TERRAIN (Revit) e texto no ObjectType (bSI)."""
    quad = _quadrado_local()
    por_tipo = _fakes.elemento_geografico("Terreno MCMV-Rural", quad)
    por_texto = _fakes.elemento_geografico("house - site - soil", quad,
                                           predefinido=None, object_type="terrain")
    em_portugues = _fakes.elemento_geografico("Sólido topográfico", quad,
                                              predefinido=None,
                                              object_type="terreno natural")
    vegetacao = _fakes.elemento_geografico("grass", quad, predefinido=None,
                                           object_type="vegetation")

    assert de_ifc._e_terreno(por_tipo)
    assert de_ifc._e_terreno(por_texto)
    assert de_ifc._e_terreno(em_portugues)
    assert not de_ifc._e_terreno(vegetacao)


def test_terreno_vem_do_geographic_element_quando_o_site_nao_tem_geometria():
    """Caso rural: IfcSite sem representação, terreno no TERRAIN."""
    terreno = _fakes.elemento_geografico("Terreno MCMV-Rural",
                                         _quadrado_local(100.0))
    res = de_ifc.resolver(_fakes.modelo_terrain([terreno]))

    assert res.ok, res.diagnostico
    t = res.terreno
    assert t.nivel == trn.NIVEL_POLIGONAL
    assert t.area_m2 == pytest.approx(10_000.0, rel=0.01)
    assert t.procedencia["fonte_geometria"] == "IfcGeographicElement"
    assert any("superfície" in a and "não para o limite" in a for a in t.avisos)


def test_entre_varios_terrain_vale_o_de_maior_area_em_planta():
    """Modelo rural com implantação + duas escavações, todas TERRAIN."""
    implantacao = _fakes.elemento_geografico(
        "Terreno - Implantação", _quadrado_local(100.0), gid="G-IMP")
    escavacao = _fakes.elemento_geografico(
        "Terreno - Escavação do embasamento",
        _quadrado_deslocado(20.0, 10.0, 10.0), gid="G-ESC")
    calcada = _fakes.elemento_geografico(
        "Terreno - Escavação da calçada",
        _quadrado_deslocado(8.0, 50.0, 5.0), gid="G-CAL")

    res = de_ifc.resolver(_fakes.modelo_terrain([escavacao, implantacao, calcada]))

    assert res.ok, res.diagnostico
    escolhido = res.detalhe["terrain_escolhido"]
    assert escolhido["global_id"] == "G-IMP"
    assert escolhido["candidatos"] == 3
    assert res.terreno.area_m2 == pytest.approx(10_000.0, rel=0.01)
    assert any("Ignorados" in a and "Escavação" in a for a in res.terreno.avisos)


def test_terreno_contido_no_pavimento_e_aceito_mas_a_lacuna_e_registrada():
    """O exportador aloca o terreno no pavimento; a classe está certa, o lugar não."""
    terreno = _fakes.elemento_geografico("Terreno", _quadrado_local())
    res = de_ifc.resolver(_fakes.modelo_terrain([terreno],
                                                contido_em="IfcBuildingStorey"))

    assert res.ok
    assert res.detalhe["terrain_escolhido"]["contido_em"] == "IfcBuildingStorey"
    assert any("contido em **IfcBuildingStorey**" in a and "lacuna" in a
               for a in res.terreno.avisos)


def test_terreno_contido_no_site_nao_gera_aviso_de_lacuna():
    terreno = _fakes.elemento_geografico("Terreno", _quadrado_local())
    res = de_ifc.resolver(_fakes.modelo_terrain([terreno], contido_em="IfcSite"))

    assert res.ok
    assert res.detalhe["terrain_escolhido"]["contido_em"] == "IfcSite"
    assert not any("lacuna" in a for a in res.terreno.avisos)


def test_footprint_do_site_tem_precedencia_sobre_o_terrain():
    """O IfcSite é o LIMITE; o TERRAIN é a superfície. O limite vence."""
    terreno = _fakes.elemento_geografico("Terreno", _quadrado_local(300.0))
    modelo = _fakes.modelo_terrain([terreno],
                                   site_com_footprint=_quadrado_local(100.0))
    res = de_ifc.resolver(modelo)

    assert res.ok
    assert res.terreno.procedencia["fonte_geometria"] == "IfcSite"
    assert res.terreno.area_m2 == pytest.approx(10_000.0, rel=0.01)


def test_geometria_de_terrain_sem_georreferenciamento_tambem_degrada():
    terreno = _fakes.elemento_geografico("Terreno", _quadrado_local())
    modelo = _fakes.modelo_terrain([terreno])
    modelo._entidades = [e for e in modelo._entidades
                         if e._type not in ("IfcProjectedCRS", "IfcMapConversion")]
    res = de_ifc.resolver(modelo)

    assert res.ok
    assert res.terreno.nivel == trn.NIVEL_PONTO
    assert any("IfcGeographicElement TERRAIN" in m and "LoGeoRef" in m
               for m in res.diagnostico)


# ===========================================================================
# Vários IfcSite: decomposição legítima × ambiguidade real
# ===========================================================================

def test_decomposicao_de_site_usa_a_raiz_complex():
    res = de_ifc.resolver(_fakes.modelo_sites_decompostos(
        _quadrado_local(200.0), _quadrado_local(50.0)))

    assert res.ok, res.diagnostico
    assert res.terreno.procedencia["elemento_nome"] == "terreno (conjunto)"
    assert res.terreno.area_m2 == pytest.approx(40_000.0, rel=0.01)
    assert any("raiz da agregação" in m for m in res.diagnostico)


def test_sites_irmaos_independentes_sao_recusados():
    res = de_ifc.resolver(_fakes.modelo_sites_irmaos(_quadrado_local()))

    assert not res.ok
    assert any("2 IfcSite independentes" in m for m in res.diagnostico)
    assert any("envie o modelo do terreno" in m for m in res.diagnostico)

# ===========================================================================
# Transformação utilizável × conformidade do CRS
# ===========================================================================
# Bug real: o gate usava ``logeoref.atinge_alvo``, que exige SIRGAS
# 2000. Modelos em Gauss-Krüger (EPSG:5834 e EPSG:31467, ambos no acervo) têm
# LoGeoRef 50 e não são SIRGAS — a extração era reprovada por confundir
# conformidade com capacidade, produzindo a mensagem absurda "está no LoGeoRef
# 50 (exigido 50)".

# Gauss-Krüger zona 3 (Alemanha), com coordenadas plausíveis para o CRS.
GK_CONV = {"epsg": "EPSG:31467", "eastings": 3450000.0, "northings": 5400000.0}


def test_crs_nao_sirgas_ainda_produz_poligonal():
    modelo = _fakes.modelo_site_com_footprint(_quadrado_local(100.0), **GK_CONV)
    res = de_ifc.resolver(modelo)

    assert res.ok, res.diagnostico
    assert res.terreno.nivel == trn.NIVEL_POLIGONAL
    assert res.terreno.area_m2 == pytest.approx(10_000.0, rel=0.01)
    assert res.terreno.procedencia["epsg_modelo"] == "EPSG:31467"


def test_capacidade_e_conformidade_sao_avaliadas_em_separado():
    """O mesmo modelo: transformação utilizável **e** CRS não conforme."""
    res = de_ifc.resolver(
        _fakes.modelo_site_com_footprint(_quadrado_local(), **GK_CONV))

    assert res.detalhe["transformacao_utilizavel"] is True
    assert res.detalhe["logeoref"]["crs_consistente"] is False


def test_crs_nao_sirgas_vira_aviso_que_remete_ao_emp_001():
    res = de_ifc.resolver(
        _fakes.modelo_site_com_footprint(_quadrado_local(), **GK_CONV))

    avisos = res.terreno.avisos
    assert any("não é SIRGAS 2000" in a for a in avisos)
    assert any("EMP-001" in a for a in avisos)
    assert any("reprojeção não depende do datum" in a for a in avisos)


def test_crs_sirgas_nao_gera_aviso_de_datum():
    res = de_ifc.resolver(_fakes.modelo_site_com_footprint(_quadrado_local()))
    assert not any("SIRGAS" in a for a in res.terreno.avisos)


def test_impedimento_nomeia_a_causa_e_nao_se_contradiz():
    """Sem as entidades de CRS, a mensagem diz o que falta — e o nível não
    pode aparecer como igual ao exigido (era o sintoma do bug)."""
    modelo = _fakes.modelo_site_com_footprint(_quadrado_local(), nivel_50=False)
    res = de_ifc.resolver(modelo)

    msgs = " ".join(res.diagnostico)
    assert "faltam IfcProjectedCRS" in msgs
    assert f"LoGeoRef {de_ifc.NIVEL_EXIGIDO}** (exigido" not in msgs
    assert res.detalhe["transformacao_utilizavel"] is False
    assert "IfcProjectedCRS" in res.detalhe["transformacao_impedimento"]

# ===========================================================================
# Formatação numérica e desvio de reprojeção
# ===========================================================================
# Caso real: um quadrado de 1 km do arquivo de teste do bSI saiu como
# "1.000.071.23 m²" — o idioma `f"{v:,.2f}".replace(",", ".")` transformava o
# separador de milhar em ponto e deixava o decimal em ponto também. Área certa
# lida como número absurdo.

def test_formatar_numero_no_padrao_brasileiro():
    from core.dominio.terreno import formatar_numero

    assert formatar_numero(1_000_071.23) == "1.000.071,23"
    assert formatar_numero(1_000_000, 0) == "1.000.000"
    assert formatar_numero(0.5) == "0,50"
    assert formatar_numero(999.9, 1) == "999,9"
    assert formatar_numero(None) == "—"


def test_area_no_crs_do_modelo_e_registrada_junto_com_o_desvio():
    """Quantifica a distorção de remedir noutro CRS — sem esse número, uma
    área correta parece suspeita."""
    modelo = _fakes.modelo_site_com_footprint(_quadrado_local(100.0), **GK_CONV)
    t = de_ifc.resolver(modelo).terreno

    # No CRS do modelo o quadrado é exato: 100 m x 100 m.
    assert t.procedencia["area_no_crs_do_modelo_m2"] == pytest.approx(10_000.0,
                                                                      abs=0.01)
    ppm = t.procedencia["desvio_reprojecao_ppm"]
    assert abs(ppm) < 2000            # troca de projeção: ordem de dezenas/centenas de ppm
    assert t.area_m2 != t.procedencia["area_no_crs_do_modelo_m2"]


def test_desvio_de_reprojecao_e_irrelevante_para_os_limiares_da_portaria():
    """O desvio existe e é medido; a decisão de remedir no fuso do centróide
    se sustenta porque ele é ordens de grandeza menor que os limiares."""
    modelo = _fakes.modelo_site_com_footprint(_quadrado_local(1000.0), **GK_CONV)
    t = de_ifc.resolver(modelo).terreno

    lado_equivalente = t.area_m2 ** 0.5
    # Um quadrado de 1 km: o erro no lado tem de ficar bem abaixo de 1 metro.
    assert abs(lado_equivalente - 1000.0) < 1.0



# ===========================================================================
# Divergência entre a coordenada do IfcSite e a origem do IfcMapConversion
# ===========================================================================

def _dms(graus: float):
    """Graus decimais -> (graus, min, seg, milionésimos), com o sinal em todas
    as componentes, como o IFC grava."""
    sinal = -1 if graus < 0 else 1
    total = abs(graus)
    g = int(total)
    m = int((total - g) * 60)
    seg_total = ((total - g) * 60 - m) * 60
    s = int(seg_total)
    micro = round((seg_total - s) * 1_000_000)
    return tuple(sinal * c for c in (g, m, s, micro))


def _origem_do_mapconversion(modelo=None):
    """(lat, lon) da origem do MapConversion dos fakes (EPSG:31983)."""
    from core.dominio import geometria as crs
    lon, lat = crs.reprojetar_ponto(E0, N0, "EPSG:31983", crs.CRS_GEOGRAFICO)
    return lat, lon


def _modelo_com_site_a(metros_ao_norte: float):
    """LoGeoRef 50 sem poligonal, com o IfcSite ``metros_ao_norte`` acima da
    origem do MapConversion (1 grau de latitude ~ 110,6 a 111,7 km)."""
    lat, lon = _origem_do_mapconversion()
    modelo = _fakes.modelo_nivel_50()
    site = modelo.by_type("IfcSite")[0]
    site.RefLatitude = list(_dms(lat + metros_ao_norte / 111_000.0))
    site.RefLongitude = list(_dms(lon))
    return modelo


def test_divergencia_grava_as_duas_posicoes_sem_mudar_a_precedencia():
    """O caso do E1: a lat/lon do IfcSite e a origem do MapConversion apontam
    para lugares diferentes. O terreno segue saindo do IfcSite; o que muda é que
    as duas posições ficam registradas."""
    res = de_ifc.resolver(_fakes.modelo_nivel_50())
    assert res.ok
    t = res.terreno

    # Precedência intacta: o centro é a coordenada do IfcSite (23, 46 nos fakes).
    assert t.centro_wgs84 == pytest.approx((23.0, 46.0))
    assert t.procedencia["entrada"] == "RefLatitude/RefLongitude do IfcSite"

    div = t.procedencia["divergencia_posicao"]
    assert div["fonte_usada"] == "ifcsite"
    assert (div["ifcsite"]["lat"], div["ifcsite"]["lon"]) == pytest.approx((23.0, 46.0))
    lat_mc, lon_mc = _origem_do_mapconversion()
    assert (div["mapconversion"]["lat"], div["mapconversion"]["lon"]) == pytest.approx(
        (lat_mc, lon_mc), abs=1e-6)
    assert div["mapconversion"]["epsg"] == "EPSG:31983"
    assert div["mapconversion"]["eastings"] == E0
    assert div["distancia_m"] > de_ifc.TOLERANCIA_DIVERGENCIA_POSICAO_M
    assert div["tolerancia_m"] == de_ifc.TOLERANCIA_DIVERGENCIA_POSICAO_M
    assert res.detalhe["divergencia_posicao"] == div
    assert any("IfcMapConversion" in a and "IfcSite" in a for a in t.avisos)

    # A tela guarda o terreno em cache e o empreendimento o grava em JSON: as
    # duas posições têm de sobreviver ao vai e volta.
    import json
    volta = trn.Terreno.from_dict(json.loads(json.dumps(t.to_dict())))
    assert volta.procedencia["divergencia_posicao"] == div


def test_divergencia_dentro_da_tolerancia_nao_e_registrada():
    res = de_ifc.resolver(_modelo_com_site_a(100.0))
    assert res.ok
    assert "divergencia_posicao" not in res.terreno.procedencia
    assert "divergencia_posicao" not in res.detalhe
    assert not any("IfcMapConversion" in a for a in res.terreno.avisos)


def test_a_tolerancia_e_o_limite_entre_registrar_e_nao_registrar():
    abaixo = de_ifc.resolver(_modelo_com_site_a(
        de_ifc.TOLERANCIA_DIVERGENCIA_POSICAO_M - 20.0)).terreno
    acima = de_ifc.resolver(_modelo_com_site_a(
        de_ifc.TOLERANCIA_DIVERGENCIA_POSICAO_M + 20.0)).terreno
    assert "divergencia_posicao" not in abaixo.procedencia
    div = acima.procedencia["divergencia_posicao"]
    assert div["distancia_m"] == pytest.approx(
        de_ifc.TOLERANCIA_DIVERGENCIA_POSICAO_M + 20.0, abs=5.0)


def test_sem_mapconversion_nao_ha_o_que_comparar():
    res = de_ifc.resolver(_fakes.modelo_nivel_30())
    assert res.ok
    assert "divergencia_posicao" not in res.terreno.procedencia


def test_com_poligonal_a_divergencia_nao_e_registrada():
    """A poligonal tem precedência sobre a coordenada do IfcSite; a divergência
    só interessa quando é a coordenada que posiciona o terreno."""
    modelo = _fakes.modelo_site_com_footprint(_quadrado_local(100.0))
    res = de_ifc.resolver(modelo)
    assert res.ok and res.terreno.nivel == trn.NIVEL_POLIGONAL
    assert "divergencia_posicao" not in res.terreno.procedencia


def test_falha_ao_reprojetar_a_origem_nao_derruba_o_terreno(monkeypatch):
    def _falha(*_a, **_k):
        raise RuntimeError("projeção indisponível")
    monkeypatch.setattr(de_ifc.crs, "reprojetar_ponto", _falha)

    res = de_ifc.resolver(_fakes.modelo_nivel_50())
    assert res.ok
    assert "divergencia_posicao" not in res.terreno.procedencia


def test_distancia_geodesica_de_um_grau_de_latitude_no_equador():
    assert de_ifc._distancia_geodesica_m(0.0, 0.0, 1.0, 0.0) == pytest.approx(
        110_574.0, rel=1e-3)


@pytest.mark.integracao
def test_e1_georref_real_registra_maceio_e_estrela():
    """ADR-038: o E1 corretamente georreferenciado (origem em Estrela/RS) guarda no
    IfcSite a lat/lon da condição existente (Maceió). O terreno continua saindo
    do IfcSite, e a divergência é registrada com as duas posições."""
    import os
    pytest.importorskip("ifcopenshell")
    raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))))
    caminho = os.path.join(raiz, "entradas", "ifc", "estrela_i", "E1_georref.ifc")
    if not os.path.exists(caminho):
        pytest.skip("entradas/ifc/estrela_i/E1_georref.ifc não existe")

    res = de_ifc.resolver_arquivo(caminho)

    assert res.ok, res.diagnostico
    lat, lon = res.terreno.centro_wgs84
    assert (lat, lon) == pytest.approx((-9.6076, -35.7022), abs=1e-3)   # Maceió
    div = res.terreno.procedencia["divergencia_posicao"]
    assert (div["mapconversion"]["lat"], div["mapconversion"]["lon"]) == pytest.approx(
        (-29.4919, -51.9313), abs=1e-3)                                  # Estrela/RS
    assert div["distancia_m"] == pytest.approx(2_775_594.0, rel=1e-3)
