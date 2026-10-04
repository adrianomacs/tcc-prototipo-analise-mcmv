"""Testes do avaliador LoGeoRef e da blindagem de schema."""

from core.infra.ifc.georref import leitor_crs, logeoref
from tests.apoio.ifc_falso import (
    modelo_ifc2x3,
    modelo_nivel_30,
    modelo_nivel_50,
    modelo_vazio,
)


def test_modelo_vazio_nivel_zero():
    diag = logeoref.avaliar(modelo_vazio())
    assert diag.nivel == 0
    assert not diag.atinge_alvo
    assert "IfcProjectedCRS" in diag.lacunas


def test_nivel_30_detectado():
    diag = logeoref.avaliar(modelo_nivel_30())
    assert diag.nivel == 30
    assert not diag.atinge_alvo


def test_nivel_50_consistente_atinge_alvo():
    diag = logeoref.avaliar(modelo_nivel_50(epsg="EPSG:31983"))
    assert diag.nivel == 50
    assert diag.crs_consistente
    assert diag.atinge_alvo
    assert diag.lacunas == []


def test_nivel_50_crs_inconsistente_nao_atinge():
    diag = logeoref.avaliar(modelo_nivel_50(epsg="EPSG:32723"))
    assert diag.nivel == 50
    assert not diag.crs_consistente
    assert not diag.atinge_alvo


def test_ifc2x3_nao_suporta_nivel_50():
    diag = logeoref.avaliar(modelo_ifc2x3())
    assert diag.schema == "IFC2X3"
    assert diag.nivel == 40            # teto do schema
    assert not diag.atinge_alvo
    assert any("IFC4" in l for l in diag.lacunas)


def test_leitor_crs_nao_quebra_em_ifc2x3():
    info = leitor_crs.ler(modelo_ifc2x3())
    assert info.valido is False
    assert "IFC2X3" in info.mensagem


# ---------------------------------------------------------------------------
# Scale do IfcMapConversion — plausível é 1, k ou 1/k da unidade do projeto
# (cenário V2: Revit em pés grava 3,2808)
# ---------------------------------------------------------------------------

def test_scale_um_e_plausivel_em_projeto_em_metro():
    diag = logeoref.avaliar(modelo_nivel_50(scale=1.0))
    assert diag.crs_consistente and diag.atinge_alvo


def test_scale_estranha_em_projeto_em_metro_reprova():
    """Projeto em metro (k = 1): só Scale ≈ 1 é coerente; 3,28 aqui não tem
    unidade que o explique."""
    diag = logeoref.avaliar(modelo_nivel_50(scale=3.280839895013123))
    assert not diag.crs_consistente
    assert any("implausivel" in l for l in diag.lacunas)


def test_scale_coerente_com_a_unidade_do_projeto_e_plausivel(monkeypatch):
    """Projeto em pé (k = 0,3048 m/unidade): tanto 0,3048 (definição do IFC4)
    quanto 3,2808 (convenção inversa do Revit) são coerentes com a unidade e
    não reprovam; a direção fica anotada na mensagem."""
    monkeypatch.setattr("core.infra.ifc.unidades.escala_comprimento", lambda m: 0.3048)
    for scale in (0.3048, 3.280839895013123):
        diag = logeoref.avaliar(modelo_nivel_50(scale=scale))
        assert diag.crs_consistente and diag.atinge_alvo, scale
        assert "k = 0.3048" in diag.consistencia_msg
    diag = logeoref.avaliar(modelo_nivel_50(scale=2.0))
    assert not diag.crs_consistente
