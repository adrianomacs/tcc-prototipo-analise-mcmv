"""Faixa de avisos (ADR-034 (c)): a forma da mensagem e a semântica fechada."""

from __future__ import annotations

import pytest

from app.componentes import avisos


def test_mensagem_chave_em_negrito_seguida_de_consequencia_e_acao():
    aviso = avisos.Aviso(avisos.ALERTA, "Município ainda não declarado.",
                         "O mapa abre longe.", "Declare-o em Informações Gerais.")
    assert avisos.texto_do_aviso(aviso) == (
        "**Município ainda não declarado.** O mapa abre longe. Declare-o em "
        "Informações Gerais.")


def test_consequencia_e_acao_sao_opcionais():
    assert avisos.texto_do_aviso(
        avisos.Aviso(avisos.ORIENTACAO, "Envie o modelo IFC.")) == (
        "**Envie o modelo IFC.**")


def test_nivel_fora_da_semantica_e_recusado():
    """Quatro caixas e nada mais — em particular, nada de uma quinta para o
    veredito, que só tem cor no card de verificação."""
    with pytest.raises(ValueError):
        avisos.Aviso("conforme", "x")


def test_aviso_de_rede_e_alerta_quando_nao_configurado(monkeypatch):
    monkeypatch.setattr(avisos, "roteador_de_rede", lambda: None)
    aviso = avisos.aviso_de_rede()
    assert aviso is not None and aviso.nivel == avisos.ALERTA
    assert "secrets.toml" in aviso.referencia
    assert "secrets.toml" not in avisos.texto_do_aviso(aviso)


def test_aviso_de_rede_some_quando_configurado(monkeypatch):
    monkeypatch.setattr(avisos, "roteador_de_rede", lambda: object())
    assert avisos.aviso_de_rede() is None


def test_consolidado_parcial_nomeia_o_que_falta_e_some_quando_nada_falta():
    aviso = avisos.aviso_consolidado_parcial(["Programa de Necessidades"])
    assert aviso.nivel == avisos.ALERTA
    assert aviso.chave == "Consolidado parcial."
    assert "Programa de Necessidades" in aviso.consequencia
    assert avisos.aviso_consolidado_parcial([]) is None


# ---------------------------------------------------------------------------
# Divergência entre a coordenada do IfcSite e a origem do IfcMapConversion
# ---------------------------------------------------------------------------

def _divergencia(distancia_m=2_775_594.4):
    """A procedência que o extrator grava para o E1 (Maceió × Estrela/RS)."""
    return {
        "fonte_usada": "ifcsite",
        "ifcsite": {"lat": -9.607571, "lon": -35.70224,
                    "entrada": "RefLatitude/RefLongitude do IfcSite"},
        "mapconversion": {"lat": -29.4918541, "lon": -51.9312766,
                          "eastings": 409724.401, "northings": 6737157.9595,
                          "epsg": "EPSG:31982",
                          "entrada": "origem do IfcMapConversion"},
        "distancia_m": distancia_m, "tolerancia_m": 250.0}


def _aviso_div(site_dentro, mapa_dentro, municipio="Estrela/RS", **kw):
    return avisos.aviso_divergencia_posicao(
        kw.pop("divergencia", _divergencia()), municipio=municipio,
        ifcsite_dentro=site_dentro, mapconversion_dentro=mapa_dentro)


def test_divergencia_do_e1_e_erro_e_diz_qual_posicao_esta_no_municipio():
    """O caso de divergência: IfcSite em Maceió, origem do MapConversion em Estrela."""
    aviso = _aviso_div(False, True)
    texto = avisos.texto_do_aviso(aviso)

    assert aviso.nivel == avisos.ERRO
    assert texto.startswith("**O modelo aponta dois lugares diferentes para o "
                            "projeto.**")
    assert "2.775,6 km" in texto
    assert "cai fora de Estrela/RS" in texto and "cai dentro dele" in texto
    assert "**IfcSite**" in texto and "**IfcMapConversion**" in texto
    assert "não pode ser confirmado" in texto
    assert "Corrija a localização do projeto no software de autoria" in texto
    assert "memorial descritivo" in texto


def test_divergencia_com_as_duas_posicoes_fora_muda_a_acao():
    aviso = _aviso_div(False, False)
    assert aviso.nivel == avisos.ERRO
    assert "Nenhuma das duas posições cai em Estrela/RS" in aviso.consequencia
    assert "Confira o município declarado" in aviso.acao


def test_divergencia_com_a_origem_nao_conferida_nao_afirma_onde_ela_cai():
    aviso = _aviso_div(False, None)
    assert aviso.nivel == avisos.ERRO
    assert "não pôde ser conferida" in aviso.consequencia
    assert "cai dentro" not in aviso.consequencia


def test_divergencia_com_o_ifcsite_dentro_do_municipio_e_so_alerta():
    """O terreno segue: a incoerência é do dado, e a mensagem diz de onde as
    distâncias vão partir."""
    aviso = _aviso_div(True, True)
    assert aviso.nivel == avisos.ALERTA
    assert "As duas posições caem dentro de Estrela/RS" in aviso.consequencia
    assert "a partir da posição do IfcSite" in aviso.consequencia
    assert "não pode ser confirmado" not in aviso.consequencia


def test_divergencia_sem_confronto_com_o_municipio_e_alerta_sem_afirmar_nada():
    aviso = _aviso_div(None, None, municipio="")
    assert aviso.nivel == avisos.ALERTA
    assert "cai fora" not in aviso.consequencia
    assert "cai dentro" not in aviso.consequencia


def test_divergencia_em_metros_quando_abaixo_de_um_quilometro():
    aviso = _aviso_div(None, None, divergencia=_divergencia(640.4))
    assert "a 640 m da origem" in aviso.consequencia
    assert "distância 640 m" in aviso.referencia


def test_referencia_da_divergencia_traz_as_duas_posicoes_e_a_tolerancia():
    ref = _aviso_div(False, True).referencia
    assert "IfcSite -9,607571, -35,702240" in ref
    assert "IfcMapConversion -29,491854, -51,931277" in ref
    assert "EPSG:31982" in ref and "E 409.724 m" in ref and "N 6.737.158 m" in ref
    assert "tolerância 250 m" in ref


@pytest.mark.parametrize("site,mapa", [(False, True), (False, False),
                                       (False, None), (True, True), (None, None)])
def test_divergencia_segue_o_registro_do_texto_de_tela(site, mapa):
    """Registro do texto de tela: sem dois-pontos nem travessão encadeando ideias, sem lista;
    termo técnico em negrito dentro da frase."""
    aviso = _aviso_div(site, mapa)
    corpo = avisos.texto_do_aviso(aviso)
    assert ":" not in corpo and "—" not in corpo and "–" not in corpo
    assert "\n" not in corpo and "- " not in corpo


def test_divergencia_do_terreno_confronta_as_duas_posicoes_com_o_municipio():
    class _T:
        procedencia = {"divergencia_posicao": _divergencia()}
    chamadas = []

    def dentro(lat, lon):
        chamadas.append((lat, lon))
        return lat < -20.0   # só a origem do MapConversion (Estrela, -29,49) está no município

    aviso = avisos.aviso_divergencia_do_terreno(
        _T, municipio="Estrela/RS", dentro_do_municipio=dentro)

    assert chamadas == [(-9.607571, -35.70224), (-29.4918541, -51.9312766)]
    assert aviso.nivel == avisos.ERRO
    assert "A posição do IfcSite cai fora de Estrela/RS" in aviso.consequencia


def test_terreno_sem_divergencia_nao_tem_aviso():
    class _T:
        procedencia = {"entrada": "RefLatitude/RefLongitude do IfcSite"}
    assert avisos.aviso_divergencia_do_terreno(
        _T, municipio="X/UF", dentro_do_municipio=lambda *_: None) is None
