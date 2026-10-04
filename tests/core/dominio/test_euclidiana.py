"""Camada de roteamento — o piso, o pré-filtro e o veredito assimétrico.

Estes testes existem para uma afirmação, e é ela que o R5 inteiro apoia: **a
distância em linha reta reprova legitimamente e não aprova nunca**. Se essa
assimetria se inverter em algum refactor, o módulo passa a produzir conformidade
falsa — exatamente o defeito que este projeto existe para não cometer.

O primeiro bloco é numérico e não é cerimônia: a assimetria só vale se a fórmula
for mesmo um piso. Uma haversine com raio médio erra para mais em parte do país,
e um erro para mais quebra as duas propriedades de uma vez.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import pytest

from core.dominio import euclidiana as eu
from core.dominio import mobilidade as ct
from core.dominio.contratos import roteador as ct_rot
from core.dominio.vocabulario import motivos


@dataclass
class FakeEquipamento:
    """O mínimo que o roteador lê de um ``Equipamento``."""
    codigo_inep: str
    lat: float | None
    lon: float | None
    nome: str = ""


# ---------------------------------------------------------------------------
# 1. A fórmula é mesmo um piso?
# ---------------------------------------------------------------------------

_A = 6_378_137.0
_F = 1 / 298.257223563
_B = _A * (1 - _F)


def _vincenty(lat1, lon1, lat2, lon2):
    """Geodésica no elipsoide WGS 84 — referência independente da implementação."""
    L = math.radians(lon2 - lon1)
    U1 = math.atan((1 - _F) * math.tan(math.radians(lat1)))
    U2 = math.atan((1 - _F) * math.tan(math.radians(lat2)))
    sU1, cU1, sU2, cU2 = math.sin(U1), math.cos(U1), math.sin(U2), math.cos(U2)
    lam = L
    for _ in range(200):
        sl, cl = math.sin(lam), math.cos(lam)
        ss = math.sqrt((cU2 * sl) ** 2 + (cU1 * sU2 - sU1 * cU2 * cl) ** 2)
        if ss == 0:
            return 0.0
        cs = sU1 * sU2 + cU1 * cU2 * cl
        sig = math.atan2(ss, cs)
        sa = cU1 * cU2 * sl / ss
        c2a = 1 - sa ** 2
        c2sm = cs - 2 * sU1 * sU2 / c2a if c2a != 0 else 0.0
        C = _F / 16 * c2a * (4 + _F * (4 - 3 * c2a))
        anterior = lam
        lam = L + (1 - C) * _F * sa * (
            sig + C * ss * (c2sm + C * cs * (-1 + 2 * c2sm ** 2)))
        if abs(lam - anterior) < 1e-13:
            break
    u2 = c2a * (_A ** 2 - _B ** 2) / _B ** 2
    Aa = 1 + u2 / 16384 * (4096 + u2 * (-768 + u2 * (320 - 175 * u2)))
    Bb = u2 / 1024 * (256 + u2 * (-128 + u2 * (74 - 47 * u2)))
    dsig = Bb * ss * (c2sm + Bb / 4 * (
        cs * (-1 + 2 * c2sm ** 2)
        - Bb / 6 * c2sm * (-3 + 4 * ss ** 2) * (-3 + 4 * c2sm ** 2)))
    return _B * Aa * (sig - dsig)


def test_a_distancia_nunca_supera_a_geodesica_no_brasil():
    """A propriedade da qual tudo depende, amostrada no território de interesse.

    Se algum par violar isto, a euclidiana deixa de poder reprovar: ela estaria
    afirmando "está além do limiar" sobre um equipamento que talvez esteja
    dentro.
    """
    random.seed(20260911)
    violacoes = []
    for _ in range(4000):
        lat = random.uniform(-34, 5)
        lon = random.uniform(-74, -34)
        metros = random.uniform(50, 5000)
        azimute = random.uniform(0, 2 * math.pi)
        lat2 = lat + (metros * math.cos(azimute)) / 111_320.0
        lon2 = lon + (metros * math.sin(azimute)) / (
            111_320.0 * math.cos(math.radians(lat)))
        piso = eu.distancia_piso_m((lat, lon), (lat2, lon2))
        if piso > _vincenty(lat, lon, lat2, lon2) + 1e-9:
            violacoes.append((lat, lon, lat2, lon2))
    assert violacoes == [], f"{len(violacoes)} par(es) em que o piso superou a geodésica"


def test_a_subestimacao_e_pequena_o_bastante_para_ser_util():
    """Piso bom demais (zero) também não serviria — ele precisa ser apertado.

    Até ~1% de folga mantém a reprovação praticamente tão frequente quanto seria
    com a geodésica exata.
    """
    piso = eu.distancia_piso_m((-29.5013, -51.9650), (-29.4990, -51.9701))
    exata = _vincenty(-29.5013, -51.9650, -29.4990, -51.9701)
    assert 0.98 <= piso / exata <= 1.0


def test_distancia_conhecida_bate_com_a_referencia():
    """Duas escolas reais de Estrela/RS, contra a geodésica de Vincenty."""
    piso = eu.distancia_piso_m((-29.48005904, -51.95758271),
                               (-29.50931, -51.96718))
    assert piso == pytest.approx(
        _vincenty(-29.48005904, -51.95758271, -29.50931, -51.96718), rel=0.01)


def test_mesmo_ponto_da_zero():
    assert eu.distancia_piso_m((-29.5, -51.9), (-29.5, -51.9)) == 0.0


def test_simetrica():
    a, b = (-29.5013, -51.9650), (-23.1791, -45.8872)
    assert eu.distancia_piso_m(a, b) == pytest.approx(eu.distancia_piso_m(b, a))


# ---------------------------------------------------------------------------
# 2. O veredito assimétrico
# ---------------------------------------------------------------------------

def _medicao(metros, *, limite_inferior, destino="1", erro=None):
    return ct.Medicao(destino=destino, metros=metros,
                      provedor=ct_rot.PROVEDOR_EUCLIDIANA if limite_inferior
                      else ct_rot.PROVEDOR_ORS,
                      metrica=ct_rot.METRICA_LINHA_RETA if limite_inferior
                      else ct_rot.METRICA_REDE_PEDESTRE,
                      limite_inferior=limite_inferior, erro=erro)


def test_piso_acima_do_limiar_reprova():
    """Se o mínimo possível já ultrapassa, o valor real também ultrapassa."""
    assert ct.confrontar(_medicao(1200.0, limite_inferior=True), 1000.0) \
        is ct.VEREDITO_NAO_ATENDE


def test_piso_abaixo_do_limiar_NAO_aprova():
    """O coração da assimetria. Aprovar aqui seria conformidade falsa."""
    assert ct.confrontar(_medicao(800.0, limite_inferior=True), 1000.0) \
        is ct.VEREDITO_INCONCLUSIVO


def test_medicao_exata_conclui_dos_dois_lados():
    assert ct.confrontar(_medicao(800.0, limite_inferior=False), 1000.0) \
        is ct.VEREDITO_ATENDE
    assert ct.confrontar(_medicao(1200.0, limite_inferior=False), 1000.0) \
        is ct.VEREDITO_NAO_ATENDE


def test_a_assimetria_depende_do_dado_e_nao_do_numero():
    """Mesma distância, vereditos diferentes — e a diferença está no campo.

    É isto que permite plugar um provedor novo sem tocar em regra nenhuma: ele
    declara de que lado erra, e o veredito se ajusta sozinho.
    """
    for metros in (1.0, 500.0, 999.999):
        assert ct.confrontar(_medicao(metros, limite_inferior=True), 1000.0) \
            is ct.VEREDITO_INCONCLUSIVO
        assert ct.confrontar(_medicao(metros, limite_inferior=False), 1000.0) \
            is ct.VEREDITO_ATENDE


@pytest.mark.parametrize("metros, esperado", [
    (999.9, ct.VEREDITO_ATENDE),
    (1000.0, ct.VEREDITO_ATENDE),      # "a até X metros" inclui X
    (1000.1, ct.VEREDITO_NAO_ATENDE),
])
def test_fronteira_do_limiar_e_inclusiva(metros, esperado):
    assert ct.confrontar(_medicao(metros, limite_inferior=False), 1000.0) is esperado


def test_medicao_invalida_e_inconclusiva():
    assert ct.confrontar(None, 1000.0) is ct.VEREDITO_INCONCLUSIVO
    assert ct.confrontar(_medicao(None, limite_inferior=False), 1000.0) \
        is ct.VEREDITO_INCONCLUSIVO
    assert ct.confrontar(_medicao(10.0, limite_inferior=False, erro="timeout"),
                         1000.0) is ct.VEREDITO_INCONCLUSIVO


# ---------------------------------------------------------------------------
# 3. Veredito do CONJUNTO — "existe equipamento a até X metros?"
# ---------------------------------------------------------------------------

def test_basta_um_conclusivo_dentro_do_limiar():
    v, m = ct.confrontar_conjunto([
        _medicao(3000.0, limite_inferior=False, destino="a"),
        _medicao(400.0, limite_inferior=False, destino="b"),
    ], 1000.0)
    assert v is ct.VEREDITO_ATENDE and m.destino == "b"


def test_todos_alem_do_limiar_reprovam_mesmo_so_com_piso():
    """O caso que dispensa qualquer chamada de API."""
    v, m = ct.confrontar_conjunto([
        _medicao(2500.0, limite_inferior=True, destino="a"),
        _medicao(1800.0, limite_inferior=True, destino="b"),
    ], 1000.0)
    assert v is ct.VEREDITO_NAO_ATENDE and m.destino == "b"


def test_pisos_abaixo_do_limiar_nao_aprovam_o_conjunto():
    v, m = ct.confrontar_conjunto([
        _medicao(900.0, limite_inferior=True, destino="a"),
        _medicao(700.0, limite_inferior=True, destino="b"),
    ], 1000.0)
    assert v is ct.VEREDITO_INCONCLUSIVO and m.destino == "b"


def test_candidato_sem_medicao_impede_a_reprovacao():
    """Reprovar com um candidato em aberto seria reprovar por ignorância.

    O equipamento sem número pode estar a 200 m; a ausência do dado não é
    evidência contra ele.
    """
    v, _ = ct.confrontar_conjunto([
        _medicao(2500.0, limite_inferior=True, destino="a"),
        _medicao(None, limite_inferior=False, destino="b", erro="falha"),
    ], 1000.0)
    assert v is ct.VEREDITO_INCONCLUSIVO


def test_conjunto_vazio_e_inconclusivo():
    assert ct.confrontar_conjunto([], 1000.0) == (ct.VEREDITO_INCONCLUSIVO, None)


def test_medicao_exata_vence_o_piso_do_mesmo_equipamento():
    """Um equipamento roteado tem piso E medição em rede; vale a que conclui."""
    medicoes = [
        _medicao(600.0, limite_inferior=True, destino="a"),
        _medicao(1400.0, limite_inferior=False, destino="a"),
    ]
    assert len(ct.melhor_por_destino(medicoes)) == 1
    v, m = ct.confrontar_conjunto(medicoes, 1000.0)
    assert v is ct.VEREDITO_NAO_ATENDE
    assert m.metrica == ct_rot.METRICA_REDE_PEDESTRE and m.metros == 1400.0


def test_a_rede_pode_reprovar_quem_o_piso_aprovaria():
    """O caso que justifica o roteamento existir: 600 m em reta, 1,4 km a pé."""
    so_piso, _ = ct.confrontar_conjunto(
        [_medicao(600.0, limite_inferior=True, destino="a")], 1000.0)
    com_rede, _ = ct.confrontar_conjunto([
        _medicao(600.0, limite_inferior=True, destino="a"),
        _medicao(1400.0, limite_inferior=False, destino="a"),
    ], 1000.0)
    assert so_piso is ct.VEREDITO_INCONCLUSIVO
    assert com_rede is ct.VEREDITO_NAO_ATENDE


# ---------------------------------------------------------------------------
# 4. Pré-filtro
# ---------------------------------------------------------------------------

CENTRO = (-29.5013, -51.9650)


def _a_metros(metros: float, codigo: str) -> FakeEquipamento:
    """Equipamento aproximadamente a N metros ao norte do centro."""
    return FakeEquipamento(codigo, CENTRO[0] + metros / 111_320.0, CENTRO[1])


def test_o_raio_nunca_fica_abaixo_do_limiar():
    """A invariante que torna o descarte legítimo.

    Se o raio pudesse ser menor que o limiar, o pré-filtro esconderia
    equipamentos que atendem e o "não atende" viraria falso não-conforme.
    """
    for fator in (2.0, 1.0, 0.5, 0.0, -3.0):
        assert eu.raio_de_busca(1000.0, fator) >= 1000.0


def test_candidatos_ordenados_e_limitados_ao_raio():
    equipamentos = [_a_metros(300, "perto"), _a_metros(1800, "medio"),
                    _a_metros(9000, "longe")]
    dentro, raio = eu.candidatos(CENTRO, equipamentos, 1000.0)
    assert raio == 2000.0
    assert [e.codigo_inep for e, _ in dentro] == ["perto", "medio"]
    assert dentro[0][1] < dentro[1][1]


def test_quem_fica_de_fora_esta_provadamente_alem_do_limiar():
    """O descartado tem piso > raio >= limiar, logo rede > limiar."""
    equipamentos = [_a_metros(9000, "longe")]
    dentro, raio = eu.candidatos(CENTRO, equipamentos, 1000.0)
    assert dentro == []
    assert eu.distancia_piso_m(CENTRO, (equipamentos[0].lat,
                                        equipamentos[0].lon)) > raio >= 1000.0


def test_equipamento_sem_coordenada_nao_entra_no_prefiltro():
    dentro, _ = eu.candidatos(
        CENTRO, [FakeEquipamento("sem", None, None), _a_metros(300, "ok")], 1000.0)
    assert [e.codigo_inep for e, _ in dentro] == ["ok"]


# ---------------------------------------------------------------------------
# 5. O roteador euclidiano como provedor
# ---------------------------------------------------------------------------

def test_roteador_declara_que_devolve_piso():
    r = eu.RoteadorEuclidiano()
    assert isinstance(r, ct_rot.Roteador)
    assert r.limite_inferior is True
    assert r.metrica == ct_rot.METRICA_LINHA_RETA


def test_medir_devolve_uma_medicao_por_destino_com_carimbo():
    medicoes = eu.RoteadorEuclidiano().medir(
        CENTRO, [_a_metros(300, "a"), _a_metros(1800, "b")])
    assert [m.destino for m in medicoes] == ["a", "b"]
    assert all(m.obtido_em and m.provedor == ct_rot.PROVEDOR_EUCLIDIANA
               for m in medicoes)
    assert all(m.valida and not m.conclusiva for m in medicoes)


def test_equipamento_sem_coordenada_vira_medicao_com_erro_e_nao_some():
    """Sumir com ele silenciosamente permitiria reprovar sem ter medido tudo."""
    medicoes = eu.RoteadorEuclidiano().medir(
        CENTRO, [FakeEquipamento("sem", None, None)])
    assert len(medicoes) == 1
    assert not medicoes[0].valida and medicoes[0].erro
    assert ct.confrontar_conjunto(medicoes, 1000.0)[0] is ct.VEREDITO_INCONCLUSIVO


def test_medicao_serializa_para_o_relatorio():
    m = eu.RoteadorEuclidiano().medir(CENTRO, [_a_metros(300, "a")])[0]
    d = m.to_dict()
    assert d["limite_inferior"] is True
    assert d["metrica"] == ct_rot.METRICA_LINHA_RETA
    assert set(d) >= {"destino", "metros", "provedor", "metrica",
                      "limite_inferior", "obtido_em"}


# ---------------------------------------------------------------------------
# 6. O motivo novo
# ---------------------------------------------------------------------------

def test_metrica_insuficiente_tem_rotulo_e_acao():
    """Um não avaliável sem ação declarada não vira pendência acionável."""
    assert motivos.rotulo(motivos.METRICA_INSUFICIENTE)
    assert motivos.METRICA_INSUFICIENTE in motivos.ACAO
    assert "serviço de cálculo da distância caminhável" in motivos.ACAO[motivos.METRICA_INSUFICIENTE].lower()


def test_metrica_insuficiente_e_distinto_de_insumo_ausente():
    """Causas diferentes pedem ações diferentes — aqui o insumo existe."""
    assert motivos.METRICA_INSUFICIENTE != motivos.INSUMO_AUSENTE
    assert motivos.ACAO[motivos.METRICA_INSUFICIENTE] != \
        motivos.ACAO[motivos.INSUMO_AUSENTE]


# ---------------------------------------------------------------------------
# 7. Identidade do destino — o defeito de chave de dedupe, agora preso
# ---------------------------------------------------------------------------

def test_dois_equipamentos_sem_codigo_nao_colapsam_numa_chave():
    """Chave de dedupe errada funde registros distintos — e em silêncio.

    O código INEP é **opcional** no CSV do usuário, e "EMEI CENTRO" em dois
    distritos do mesmo município é banal. Se o nome virasse chave, os dois
    colapsariam: o mais distante esconderia o mais próximo, e — pior — um que
    sequer foi medido sumiria atrás de um que foi. Mesma família do defeito
    achado no R4a, agora na camada de medição.
    """
    iguais = [FakeEquipamento(None, CENTRO[0] + 0.01, CENTRO[1], "EMEI CENTRO"),
              FakeEquipamento(None, CENTRO[0] + 0.02, CENTRO[1], "EMEI CENTRO")]
    medicoes = eu.RoteadorEuclidiano().medir(CENTRO, iguais)
    assert len({m.destino for m in medicoes}) == 2
    assert len(ct.melhor_por_destino(medicoes)) == 2


def test_equipamento_nao_medido_nao_some_atras_de_um_homonimo():
    """O caso que produzia falso não-conforme antes da correção."""
    equipamentos = [
        FakeEquipamento(None, CENTRO[0] + 0.027, CENTRO[1], "EMEI CENTRO"),  # ~3 km
        FakeEquipamento(None, None, None, "EMEI CENTRO"),                    # sem coord
    ]
    medicoes = eu.RoteadorEuclidiano().medir(CENTRO, equipamentos)
    veredito, _ = ct.confrontar_conjunto(medicoes, 1000.0)
    assert veredito is ct.VEREDITO_INCONCLUSIVO


def test_codigo_inep_e_a_chave_quando_existe():
    medicoes = eu.RoteadorEuclidiano().medir(CENTRO, [_a_metros(300, "43060404")])
    assert medicoes[0].destino == "43060404"


def test_chave_posicional_quando_falta_o_codigo():
    e = FakeEquipamento(None, CENTRO[0], CENTRO[1], "SEM CODIGO")
    assert eu.chave_destino(e, 7) == "@7"
    assert eu.chave_destino(FakeEquipamento("  ", 0, 0), 3) == "@3"


def test_o_nome_viaja_como_rotulo_e_nao_como_chave():
    """O relatório precisa do nome; o veredito não pode depender dele."""
    m = eu.RoteadorEuclidiano().medir(
        CENTRO, [FakeEquipamento("43060404", CENTRO[0], CENTRO[1], "EMEI SAO JOAO")])[0]
    assert m.destino == "43060404"
    assert m.rotulo == "EMEI SAO JOAO"
    assert m.to_dict()["rotulo"] == "EMEI SAO JOAO"


# ---------------------------------------------------------------------------
# 8. Composição correta: medir TUDO, pré-filtrar só quem vai à rede
# ---------------------------------------------------------------------------

def test_nenhum_candidato_no_raio_ainda_assim_reprova():
    """A reprovação de graça — e o defeito que a escondia.

    Achado rodando contra o recorte real de Estrela: num terreno
    rural, NENHUM equipamento cai no raio. Medindo só os candidatos do raio, o
    conjunto medido fica vazio e o veredito sai "inconclusivo" — quando todos
    estão demonstravelmente além do limiar. O pré-filtro tinha jogado fora
    exatamente a prova da reprovação.

    A composição correta é medir o conjunto INTEIRO em linha reta (é de graça) e
    usar o pré-filtro só para escolher a quem pedir a rede.
    """
    longe = [_a_metros(8000, "a"), _a_metros(9500, "b")]

    a_rotear, raio = eu.candidatos(CENTRO, longe, 1000.0)
    assert a_rotear == [] and raio == 2000.0      # ninguém precisa ir à rede

    # ERRADO: medir só os candidatos do raio.
    errado, _ = ct.confrontar_conjunto(
        eu.RoteadorEuclidiano().medir(CENTRO, [e for e, _ in a_rotear]), 1000.0)
    assert errado is ct.VEREDITO_INCONCLUSIVO

    # CERTO: medir todos; o pré-filtro decide só quem vai à rede.
    certo, determinante = ct.confrontar_conjunto(
        eu.RoteadorEuclidiano().medir(CENTRO, longe), 1000.0)
    assert certo is ct.VEREDITO_NAO_ATENDE
    assert determinante.destino == "a"


def test_o_prefiltro_nao_muda_o_veredito_do_conjunto():
    """A invariante do raio, verificada pelo EFEITO e não pela aritmética.

    Rotear só quem passou no pré-filtro tem de dar o mesmo veredito que rotear
    todo mundo. É isso que autoriza economizar chamadas de API sem economizar
    rigor. Se um dia divergir, o raio encolheu abaixo do limiar.
    """
    limiar = 1000.0
    equipamentos = [_a_metros(800, "perto"), _a_metros(5000, "longe")]
    pisos = eu.RoteadorEuclidiano().medir(CENTRO, equipamentos)
    a_rotear, _ = eu.candidatos(CENTRO, equipamentos, limiar)
    assert [e.codigo_inep for e, _ in a_rotear] == ["perto"]

    def rede(destino, metros):
        return ct.Medicao(destino=destino, metros=metros,
                          provedor=ct_rot.PROVEDOR_ORS,
                          metrica=ct_rot.METRICA_REDE_PEDESTRE,
                          limite_inferior=False)

    for metros_perto, esperado in ((950.0, ct.VEREDITO_ATENDE),
                                   (1100.0, ct.VEREDITO_NAO_ATENDE)):
        economico = ct.confrontar_conjunto(
            pisos + [rede("perto", metros_perto)], limiar)[0]
        exaustivo = ct.confrontar_conjunto(
            pisos + [rede("perto", metros_perto), rede("longe", 6000.0)],
            limiar)[0]
        assert economico is esperado
        assert economico is exaustivo


def test_piso_acima_do_limiar_dispensa_a_rede_mesmo_com_candidatos_no_raio():
    """Caso que meu primeiro teste errou, e que vale registrar.

    Um equipamento com piso de 1.190 m **não pode** atender a um limiar de
    1.000 m — o piso já ultrapassa. Eu havia escrito "1.200 m ainda pode
    atender" e o teste falhou contra o código, que estava certo. A confusão é
    fácil de cometer: o raio de busca (2× o limiar) traz o equipamento para a
    lista de candidatos à rede, mas estar na lista não é estar dentro do limiar.
    """
    limiar = 1000.0
    equipamentos = [_a_metros(1200, "a"), _a_metros(2500, "b")]
    a_rotear, _ = eu.candidatos(CENTRO, equipamentos, limiar)
    assert len(a_rotear) == 1            # "a" entra no raio de 2.000 m...

    veredito, determinante = ct.confrontar_conjunto(
        eu.RoteadorEuclidiano().medir(CENTRO, equipamentos), limiar)
    assert veredito is ct.VEREDITO_NAO_ATENDE   # ...e ainda assim reprova
    assert determinante.metros > limiar
