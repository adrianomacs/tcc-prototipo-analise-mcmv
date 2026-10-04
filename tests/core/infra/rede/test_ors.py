"""R5c — o provedor de rede (ORS) e o cache das medições.

Nenhum teste daqui toca a rede: o transporte é injetado. São duas famílias, e a
distinção entre elas importa.

* Contra ``ors_matrix_estrela.json``, **sintética**: exercitam o parser, o lote,
  o cache e o que cada falha vira, inclusive os ramos que uma chamada real não
  produz sob encomenda (o ``null`` da matriz, a rede reprovando quem o piso
  aprovaria).
* Contra ``ors_matrix_real.json``, **gravada do serviço** pelo script
  ``scripts/gravar_fixture_ors.py``: provam que o formato lido é o formato que o
  ORS devolve. Sem elas, todo o resto provaria apenas que o parser corresponde à
  nossa leitura da documentação — que já foi o estado deste arquivo, e está registrado aqui
  porque a diferença é fácil de esquecer.
"""

from __future__ import annotations

import json
import urllib.error
from dataclasses import dataclass

import pytest

from core.dominio import euclidiana as eu
from core.dominio import mobilidade as ct
from core.dominio.contratos import roteador as ct_rot
from core.infra.rede import cache_ors as ca
from core.infra.rede import ors as orsm
from tests.conftest import FIXTURES

FIXTURE = FIXTURES / "ors_matrix_estrela.json"
ORIGEM = (-29.50186, -51.96529)


@dataclass
class FakeEquipamento:
    nome: str = ""
    lat: float | None = None
    lon: float | None = None
    codigo_inep: str | None = None


def resposta_gravada() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class TransporteFake:
    """Devolve respostas na ordem, e guarda o que foi pedido."""

    def __init__(self, *respostas, erro: Exception | None = None) -> None:
        self.respostas = list(respostas)
        self.erro = erro
        self.chamadas: list[dict] = []

    def __call__(self, url, corpo, cabecalhos, timeout_s):
        self.chamadas.append({"url": url, "corpo": corpo,
                              "cabecalhos": cabecalhos})
        if self.erro is not None:
            raise self.erro
        return self.respostas.pop(0) if self.respostas else {}


def _ao_norte(metros: float) -> float:
    return ORIGEM[0] + metros / 111_320.0


def tres_escolas() -> list[FakeEquipamento]:
    return [
        FakeEquipamento("EMEI Centro", -29.49702, -51.95661, "43000001"),
        FakeEquipamento("EMEF Oeste", -29.50944, -51.97812, "43000002"),
        FakeEquipamento("EMEF Ilha", -29.48001, -51.99001, "43000003"),
    ]


def roteador(transporte, **kwargs) -> orsm.RoteadorORS:
    return orsm.RoteadorORS("chave-de-teste", transporte=transporte, **kwargs)


# ---------------------------------------------------------------------------
# O que o provedor declara
# ---------------------------------------------------------------------------

def test_o_roteador_declara_que_conclui():
    """``limite_inferior = False`` é a única coisa que muda para as regras."""
    r = roteador(TransporteFake())
    assert r.limite_inferior is False
    assert r.metrica == ct_rot.METRICA_REDE_PEDESTRE
    assert r.provedor == ct_rot.PROVEDOR_ORS


def test_satisfaz_o_protocolo_do_contrato():
    assert isinstance(roteador(TransporteFake()), ct_rot.Roteador)


def test_sem_chave_nao_se_constroi_um_roteador_pela_metade():
    with pytest.raises(ValueError):
        orsm.RoteadorORS("")


# ---------------------------------------------------------------------------
# A requisição
# ---------------------------------------------------------------------------

def test_as_coordenadas_vao_em_lon_lat():
    """Trocar a ordem não estoura — devolve número plausível e errado."""
    t = TransporteFake(resposta_gravada())
    roteador(t).medir(ORIGEM, tres_escolas())
    corpo = t.chamadas[0]["corpo"]
    assert corpo["locations"][0] == [-51.96529, -29.50186]
    assert corpo["locations"][1] == [-51.95661, -29.49702]


def test_uma_unica_chamada_para_todos_os_destinos():
    """É a razão de usar a matriz em vez do directions."""
    t = TransporteFake(resposta_gravada())
    roteador(t).medir(ORIGEM, tres_escolas())
    assert len(t.chamadas) == 1
    corpo = t.chamadas[0]["corpo"]
    assert corpo["sources"] == [0]
    assert corpo["destinations"] == [1, 2, 3]


def test_pede_distancia_duracao_metros_e_o_snap():
    t = TransporteFake(resposta_gravada())
    roteador(t).medir(ORIGEM, tres_escolas())
    corpo = t.chamadas[0]["corpo"]
    assert set(corpo["metrics"]) == {"distance", "duration"}
    assert corpo["units"] == "m"
    assert corpo["resolve_locations"] is True


def test_a_chave_vai_no_cabecalho_de_autorizacao():
    t = TransporteFake(resposta_gravada())
    roteador(t).medir(ORIGEM, tres_escolas())
    assert t.chamadas[0]["cabecalhos"]["Authorization"] == "chave-de-teste"


def test_a_url_carrega_o_perfil_pedestre():
    t = TransporteFake(resposta_gravada())
    roteador(t).medir(ORIGEM, tres_escolas())
    assert t.chamadas[0]["url"].endswith("/v2/matrix/foot-walking")


# ---------------------------------------------------------------------------
# A leitura da resposta
# ---------------------------------------------------------------------------

def test_le_distancia_e_duracao_da_resposta():
    m = roteador(TransporteFake(resposta_gravada())).medir(ORIGEM, tres_escolas())
    por_chave = {x.destino: x for x in m}
    assert por_chave["43000001"].metros == pytest.approx(1043.27)
    assert por_chave["43000001"].segundos == pytest.approx(751.2)
    assert por_chave["43000002"].metros == pytest.approx(1620.44)


def test_o_snap_registrado_e_o_da_ORIGEM():
    """§5: o deslocamento que interessa é o do centro do terreno até a via.

    O do destino também é lido, mas vai para o ``detalhe`` — confundir os dois
    faria o diagnóstico do R7 medir a escola em vez do terreno.
    """
    m = roteador(TransporteFake(resposta_gravada())).medir(ORIGEM, tres_escolas())
    primeira = next(x for x in m if x.destino == "43000001")
    assert primeira.snap_m == pytest.approx(34.12)
    assert primeira.detalhe["snap_destino_m"] == pytest.approx(8.44)


def test_o_snap_e_diagnostico_e_NAO_desconta_da_distancia():
    """A decisão do §5 escrita como teste: mantém-se o centróide.

    Com 34 m de snap na origem, a distância devolvida continua sendo a do
    provedor. Qualquer tentativa futura de "corrigir" o número subtraindo o snap
    derruba este teste — que é exatamente o ponto.
    """
    m = roteador(TransporteFake(resposta_gravada())).medir(ORIGEM, tres_escolas())
    primeira = next(x for x in m if x.destino == "43000001")
    assert primeira.metros == pytest.approx(1043.27)


def test_uma_medicao_por_destino_na_ordem_recebida():
    escolas = tres_escolas()
    m = roteador(TransporteFake(resposta_gravada())).medir(ORIGEM, escolas)
    assert [x.destino for x in m] == ["43000001", "43000002", "43000003"]


def test_o_nome_viaja_como_rotulo():
    m = roteador(TransporteFake(resposta_gravada())).medir(ORIGEM, tres_escolas())
    assert m[0].rotulo == "EMEI Centro"


# ---------------------------------------------------------------------------
# O que cada falha vira — e nenhuma delas vira reprovação
# ---------------------------------------------------------------------------

def test_par_sem_rota_vira_medicao_sem_numero():
    """``null`` na matriz é ausência de medição, não zero e não "longe"."""
    m = roteador(TransporteFake(resposta_gravada())).medir(ORIGEM, tres_escolas())
    ilha = next(x for x in m if x.destino == "43000003")
    assert ilha.metros is None
    assert ilha.valida is False
    assert "sem rota" in ilha.erro


def test_par_sem_rota_impede_a_reprovacao_do_conjunto():
    """A garantia que importa: falta de número nunca vira NÃO CONFORME."""
    m = roteador(TransporteFake(resposta_gravada())).medir(ORIGEM, tres_escolas())
    veredito, _ = ct.confrontar_conjunto(m, 1000.0)
    assert veredito == ct.VEREDITO_INCONCLUSIVO


def test_falha_de_rede_nao_vira_reprovacao():
    """Serviço fora do ar, chave recusada, cota estourada: tudo inconclusivo."""
    t = TransporteFake(erro=urllib.error.URLError("conexão recusada"))
    m = roteador(t).medir(ORIGEM, tres_escolas())
    assert len(m) == 3
    assert all(x.metros is None for x in m)
    veredito, _ = ct.confrontar_conjunto(m, 1000.0)
    assert veredito == ct.VEREDITO_INCONCLUSIVO


def test_json_quebrado_nao_derruba_a_analise():
    t = TransporteFake(erro=ValueError("Expecting value: line 1 column 1"))
    m = roteador(t).medir(ORIGEM, tres_escolas())
    assert all(x.erro for x in m)


def test_resposta_vazia_nao_inventa_numero():
    m = roteador(TransporteFake({})).medir(ORIGEM, tres_escolas())
    assert all(x.metros is None for x in m)


def test_equipamento_sem_coordenada_nao_vai_ao_provedor_e_nao_some():
    escolas = tres_escolas()
    escolas.insert(0, FakeEquipamento("Sem coordenada", None, None, "43000000"))
    t = TransporteFake(resposta_gravada())
    m = roteador(t).medir(ORIGEM, escolas)
    assert len(m) == 4
    assert len(t.chamadas[0]["corpo"]["locations"]) == 4      # origem + 3
    sem = next(x for x in m if x.destino == "43000000")
    assert sem.erro == "equipamento sem coordenada"


# ---------------------------------------------------------------------------
# Lotes
# ---------------------------------------------------------------------------

def _resposta_de(n: int, base: float = 500.0) -> dict:
    return {"distances": [[base + i for i in range(n)]],
            "durations": [[(base + i) / 1.4 for i in range(n)]],
            "sources": [{"snapped_distance": 5.0}],
            "destinations": [{"snapped_distance": 1.0} for _ in range(n)]}


def _escolas(n: int) -> list[FakeEquipamento]:
    return [FakeEquipamento(f"E{i}", -29.5 + i / 1000, -51.9 - i / 1000,
                            f"430{i:05d}") for i in range(n)]


def test_lote_grande_e_dividido_em_varias_chamadas():
    t = TransporteFake(_resposta_de(2), _resposta_de(2), _resposta_de(1))
    m = roteador(t, max_destinos=2).medir(ORIGEM, _escolas(5))
    assert len(t.chamadas) == 3
    assert len(m) == 5
    assert all(x.metros is not None for x in m)


def test_falha_de_um_lote_nao_derruba_os_outros():
    """Lote pequeno falha pequeno — a razão do MAX_DESTINOS_POR_CHAMADA."""
    class Intermitente(TransporteFake):
        def __call__(self, url, corpo, cabecalhos, timeout_s):
            self.chamadas.append({"url": url, "corpo": corpo,
                                  "cabecalhos": cabecalhos})
            if len(self.chamadas) == 2:
                raise urllib.error.URLError("timeout")
            return _resposta_de(len(corpo["destinations"]))

    m = roteador(Intermitente(), max_destinos=2).medir(ORIGEM, _escolas(5))
    medidos = [x for x in m if x.metros is not None]
    assert len(medidos) == 3
    assert len(m) == 5


# ---------------------------------------------------------------------------
# Fusão com o piso euclidiano — a razão de a chave importar
# ---------------------------------------------------------------------------

def test_a_medicao_de_rede_vence_o_piso_do_mesmo_equipamento():
    """O caso que justifica o R5c existir: o piso aprovaria, a rede reprova."""
    escolas = tres_escolas()
    pisos = eu.RoteadorEuclidiano().medir(ORIGEM, escolas)
    rede = roteador(TransporteFake(resposta_gravada())).medir(ORIGEM, escolas)

    piso_primeira = next(x for x in pisos if x.destino == "43000001")
    assert piso_primeira.metros < 1000.0          # o piso aprovaria

    melhor = ct.melhor_por_destino(pisos + rede)
    assert melhor["43000001"].provedor == ct_rot.PROVEDOR_ORS
    assert melhor["43000001"].metros == pytest.approx(1043.27)

    veredito, determinante = ct.confrontar_conjunto(pisos + rede, 1000.0)
    assert veredito == ct.VEREDITO_NAO_ATENDE
    assert determinante.metros == pytest.approx(1043.27)


def test_o_piso_cobre_o_destino_que_o_provedor_nao_conseguiu_rotear():
    """Os dois provedores se completam, e é isso que salva o veredito.

    A ilha volta da matriz como ``null`` — sem medição de rede. Isso **não**
    deixa o conjunto inconclusivo, porque o piso euclidiano dela continua
    valendo e já está acima do limiar: ela está provadamente fora, medida em
    linha reta. O ``melhor_por_destino`` mantém o piso onde a rede falhou, e a
    reprovação segue legítima.

    Se o piso não cobrisse o buraco, uma falha pontual do provedor num
    equipamento distante bastaria para impedir qualquer reprovação — e todo
    terreno rural voltaria a sair NÃO AVALIÁVEL.
    """
    escolas = tres_escolas()
    pisos = eu.RoteadorEuclidiano().medir(ORIGEM, escolas)
    rede = roteador(TransporteFake(resposta_gravada())).medir(ORIGEM, escolas)

    melhor = ct.melhor_por_destino(pisos + rede)
    ilha = melhor["43000003"]
    assert ilha.provedor == ct_rot.PROVEDOR_EUCLIDIANA
    assert ilha.valida and ilha.metros > 1000.0
    assert ct.classificar(ilha, 1000.0) == ct.CLASSIF_FORA_PROVADO


def test_a_rede_dentro_do_limiar_aprova_o_que_o_piso_nao_aprovava():
    """A primeira linha verde: é isto que o R5c destrava."""
    escolas = [tres_escolas()[0]]
    pisos = eu.RoteadorEuclidiano().medir(ORIGEM, escolas)
    assert ct.confrontar_conjunto(pisos, 1500.0)[0] == ct.VEREDITO_INCONCLUSIVO

    rede = roteador(TransporteFake(resposta_gravada())).medir(ORIGEM, escolas)
    veredito, determinante = ct.confrontar_conjunto(pisos + rede, 1500.0)
    assert veredito == ct.VEREDITO_ATENDE
    assert determinante.provedor == ct_rot.PROVEDOR_ORS
    assert ct.classificar(determinante, 1500.0) == ct.CLASSIF_ATENDE_PROVADO


def test_chave_posicional_de_uma_sublista_NAO_funde_sozinha():
    """A posição é da lista recebida — por isso fatiar exige declarar as chaves.

    Não é defeito do provedor: é o que "chave posicional" quer dizer. Quem fatia
    a lista é o único que conhece a correspondência com a original, e o sintoma
    de esquecer disso é mudo — o piso sobrevive ao lado da medição de rede, o
    conjunto segue inconclusivo e nada estoura.
    """
    sem_codigo = [FakeEquipamento("A", -29.49702, -51.95661),
                  FakeEquipamento("B", -29.50944, -51.97812)]
    pisos = eu.RoteadorEuclidiano().medir(ORIGEM, sem_codigo)
    rede = roteador(TransporteFake(_resposta_de(1))).medir(ORIGEM, sem_codigo[1:])

    assert [m.destino for m in pisos] == ["@0", "@1"]
    assert [m.destino for m in rede] == ["@0"]          # a colisão
    melhor = ct.melhor_por_destino(pisos + rede)
    assert melhor["@1"].provedor == ct_rot.PROVEDOR_EUCLIDIANA   # não fundiu


def test_com_chaves_declaradas_a_sublista_funde_com_o_piso():
    """O contorno, e o que a regra faz: ver candidatos_indexados."""
    sem_codigo = [FakeEquipamento("A", -29.49702, -51.95661),
                  FakeEquipamento("B", -29.50944, -51.97812)]
    pisos = eu.RoteadorEuclidiano().medir(ORIGEM, sem_codigo)
    rede = roteador(TransporteFake(_resposta_de(1))).medir(
        ORIGEM, sem_codigo[1:], chaves=["@1"])

    melhor = ct.melhor_por_destino(pisos + rede)
    assert len(melhor) == 2
    assert melhor["@1"].provedor == ct_rot.PROVEDOR_ORS
    assert melhor["@0"].provedor == ct_rot.PROVEDOR_EUCLIDIANA


def test_candidatos_indexados_carrega_o_indice_da_lista_inteira():
    escolas = [FakeEquipamento("LONGE", _ao_norte(3000), ORIGEM[1]),
               FakeEquipamento("PERTO", _ao_norte(500), ORIGEM[1])]
    dentro, raio = eu.candidatos_indexados(ORIGEM, escolas, 1000.0)
    assert [t[2] for t in dentro] == [1]
    assert raio == 2000.0


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def test_o_mesmo_par_nao_volta_ao_provedor():
    c = ca.CacheRoteamento()
    t = TransporteFake(resposta_gravada(), resposta_gravada())
    escolas = tres_escolas()
    roteador(t, cache=c).medir(ORIGEM, escolas)
    roteador(t, cache=c).medir(ORIGEM, escolas)
    # A ilha (null) não foi guardada; só ela volta a ser perguntada.
    assert len(t.chamadas) == 2
    assert len(t.chamadas[1]["corpo"]["destinations"]) == 1


def test_medicao_vinda_do_cache_se_declara():
    c = ca.CacheRoteamento()
    escolas = tres_escolas()
    roteador(TransporteFake(resposta_gravada()), cache=c).medir(ORIGEM, escolas)
    m = roteador(TransporteFake(resposta_gravada()), cache=c).medir(ORIGEM, escolas)
    primeira = next(x for x in m if x.destino == "43000001")
    assert primeira.detalhe["do_cache"] is True
    assert primeira.metros == pytest.approx(1043.27)


def test_par_sem_rota_nao_entra_no_cache():
    """Guardar um "sem rota" congelaria um defeito temporário da malha."""
    c = ca.CacheRoteamento()
    roteador(TransporteFake(resposta_gravada()), cache=c).medir(ORIGEM, tres_escolas())
    assert c.resumo()["entradas"] == 2


def test_o_cache_persiste_em_disco_e_e_relido(tmp_path):
    caminho = tmp_path / "sub" / "ors.json"
    c1 = ca.CacheRoteamento(caminho)
    roteador(TransporteFake(resposta_gravada()), cache=c1).medir(ORIGEM, tres_escolas())
    assert caminho.exists()

    c2 = ca.CacheRoteamento(caminho)
    t = TransporteFake(resposta_gravada())
    roteador(t, cache=c2).medir(ORIGEM, tres_escolas())
    assert len(t.chamadas[0]["corpo"]["destinations"]) == 1   # só a ilha


def test_cache_corrompido_nao_derruba_a_analise(tmp_path):
    caminho = tmp_path / "ors.json"
    caminho.write_text("{isto não é json", encoding="utf-8")
    c = ca.CacheRoteamento(caminho)
    m = roteador(TransporteFake(resposta_gravada()), cache=c).medir(ORIGEM, tres_escolas())
    assert next(x for x in m if x.destino == "43000001").metros == pytest.approx(1043.27)


def test_o_arredondamento_da_chave_e_declarado_no_valor():
    c = ca.CacheRoteamento()
    roteador(TransporteFake(resposta_gravada()), cache=c).medir(ORIGEM, tres_escolas())
    m = roteador(TransporteFake(resposta_gravada()), cache=c).medir(ORIGEM, tres_escolas())
    primeira = next(x for x in m if x.destino == "43000001")
    assert primeira.detalhe["arredondamento_m"] == ca.ARREDONDAMENTO_M


def test_deslocamento_de_um_metro_ainda_acerta_o_cache():
    """Sem isso o cache nunca acertaria: o centróide recalculado varia na ponta."""
    c = ca.CacheRoteamento()
    roteador(TransporteFake(resposta_gravada()), cache=c).medir(ORIGEM, tres_escolas())
    t = TransporteFake(resposta_gravada())
    quase = (ORIGEM[0] + 0.000002, ORIGEM[1])
    roteador(t, cache=c).medir(quase, tres_escolas())
    assert len(t.chamadas[0]["corpo"]["destinations"]) == 1


def test_a_chave_do_cache_separa_perfis_e_endpoints():
    """Perfis respondem números diferentes; endpoints respondem COISAS
    diferentes — a matriz só o número, o directions número e geometria."""
    a = ca.chave_par("ors", "foot-walking", ORIGEM, (-29.4, -51.9), "matrix")
    b = ca.chave_par("ors", "driving-car", ORIGEM, (-29.4, -51.9), "matrix")
    c = ca.chave_par("ors", "foot-walking", ORIGEM, (-29.4, -51.9), "directions")
    assert len({a, b, c}) == 3


# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

def test_sem_chave_nenhuma_a_fabrica_devolve_none():
    """A degradação aprovada: quem não tem rede não finge que tem."""
    assert orsm.de_configuracao(segredos={}, ambiente={}) is None


def test_le_a_chave_do_secrets():
    r = orsm.de_configuracao(segredos={"roteamento": {"ors_api_key": "abc"}},
                             ambiente={})
    assert r is not None and r.chave == "abc"


def test_le_a_chave_do_ambiente_quando_nao_ha_secrets():
    r = orsm.de_configuracao(segredos=None, ambiente={"ORS_API_KEY": "xyz"})
    assert r is not None and r.chave == "xyz"


def test_o_secrets_tem_precedencia_sobre_o_ambiente():
    r = orsm.de_configuracao(segredos={"roteamento": {"ors_api_key": "do-toml"}},
                             ambiente={"ORS_API_KEY": "do-ambiente"})
    assert r.chave == "do-toml"


def test_chave_em_branco_e_o_mesmo_que_nao_ter():
    assert orsm.de_configuracao(segredos={"roteamento": {"ors_api_key": "  "}},
                                ambiente={}) is None


class MapaNaoDict:
    """Imita o ``AttrDict`` do ``st.secrets``: é Mapping, não subclasse de dict.

    Existe porque ``isinstance(x, dict)`` fazia a chave sumir em silêncio dentro
    do app — a análise degradava para a euclidiana como se não houvesse chave
    nenhuma, e o único sintoma era o requisito sair NÃO AVALIÁVEL.
    """

    def __init__(self, **dados):
        self._d = dados

    def get(self, k, padrao=None):
        v = self._d.get(k, padrao)
        return MapaNaoDict(**v) if isinstance(v, dict) else v


def test_le_a_chave_de_um_mapa_que_nao_e_dict():
    segredos = MapaNaoDict(roteamento={"ors_api_key": "de-attrdict"})
    assert not isinstance(segredos, dict)
    r = orsm.de_configuracao(segredos=segredos, ambiente={})
    assert r is not None and r.chave == "de-attrdict"


def test_le_a_chave_solta_no_topo_do_secrets():
    """Arranjo comum em projeto Streamlit; aceitar custa três linhas."""
    r = orsm.de_configuracao(segredos={"ors_api_key": "no-topo"}, ambiente={})
    assert r is not None and r.chave == "no-topo"


def test_a_secao_tem_precedencia_sobre_o_topo():
    r = orsm.de_configuracao(
        segredos={"ors_api_key": "topo", "roteamento": {"ors_api_key": "secao"}},
        ambiente={})
    assert r.chave == "secao"


def test_secao_com_outro_nome_nao_e_adivinhada():
    """Tolerância tem limite: [ors] não vira [roteamento] por conta própria."""
    assert orsm.de_configuracao(segredos={"ors": {"ors_api_key": "x"}},
                                ambiente={}) is None


# ---------------------------------------------------------------------------
# Contra a GRAVAÇÃO REAL — o que o transporte injetado não podia provar
# ---------------------------------------------------------------------------
#
# Gravada por scripts/gravar_fixture_ors.py, com chave real, do
# terreno urbano de Estrela/RS. Os testes acima provam que o parser lê o que a
# gente ACHA que o serviço responde; estes provam que o serviço responde isso.

REAL = FIXTURES / "ors_matrix_real.json"


def resposta_real() -> dict:
    return json.loads(REAL.read_text(encoding="utf-8"))


def tres_pontos_reais() -> list[FakeEquipamento]:
    """Os mesmos três destinos da gravação, na mesma ordem."""
    return [FakeEquipamento(f"Destino {i}", lat, lon, f"TESTE{i}")
            for i, (lat, lon) in enumerate([(-29.49702, -51.95661),
                                            (-29.50944, -51.97812),
                                            (-29.48001, -51.99001)])]


def test_a_resposta_real_tem_os_campos_que_o_parser_espera():
    d = resposta_real()
    assert {"distances", "durations", "sources", "destinations"} <= set(d)
    assert isinstance(d["distances"][0], list)
    assert "snapped_distance" in d["sources"][0]
    assert "snapped_distance" in d["destinations"][0]


def test_o_parser_le_a_resposta_real():
    m = roteador(TransporteFake(resposta_real())).medir(ORIGEM, tres_pontos_reais())
    assert [x.metros for x in m] == pytest.approx([1732.49, 1687.52, 10842.88])
    assert [x.segundos for x in m] == pytest.approx([1247.39, 1215.01, 7806.82])
    assert all(x.valida for x in m)


def test_o_snap_da_origem_real_e_o_mesmo_para_todos_os_destinos():
    """Confirma que o campo lido é o da ORIGEM, e não o de cada destino.

    Na gravação real a origem encaixou a 8,55 m da Rua Coronel Flores, enquanto
    os destinos encaixaram a 10,76, 168,63 e 23,17 m. Se o parser estivesse
    lendo o destino, os três ``snap_m`` seriam diferentes entre si.
    """
    m = roteador(TransporteFake(resposta_real())).medir(ORIGEM, tres_pontos_reais())
    assert [x.snap_m for x in m] == pytest.approx([8.55, 8.55, 8.55])
    assert [x.detalhe["snap_destino_m"] for x in m] == pytest.approx(
        [10.76, 168.63, 23.17])


def test_a_procedencia_da_malha_viaja_no_resultado():
    """A safra do OSM é o que torna o número reproduzível — ver _procedencia."""
    m = roteador(TransporteFake(resposta_real())).medir(ORIGEM, tres_pontos_reais())
    assert m[0].detalhe["graph_date"] == "2026-08-28T12:16:53Z"
    assert m[0].detalhe["osm_date"] == "2026-08-17T00:00:02Z"
    assert m[0].detalhe["version"] == "9.10.0"


def test_a_procedencia_sobrevive_ao_cache():
    """Medição relida do cache continua dizendo contra qual malha foi feita."""
    c = ca.CacheRoteamento()
    pontos = tres_pontos_reais()
    roteador(TransporteFake(resposta_real()), cache=c).medir(ORIGEM, pontos)
    m = roteador(TransporteFake(resposta_real()), cache=c).medir(ORIGEM, pontos)
    assert m[0].detalhe["do_cache"] is True
    assert m[0].detalhe["graph_date"] == "2026-08-28T12:16:53Z"


def test_a_resposta_real_reprova_contra_mil_metros():
    """O veredito que o script imprimiu, travado como teste."""
    m = roteador(TransporteFake(resposta_real())).medir(ORIGEM, tres_pontos_reais())
    veredito, determinante = ct.confrontar_conjunto(m, 1000.0)
    assert veredito == ct.VEREDITO_NAO_ATENDE
    assert determinante.metros == pytest.approx(1687.52)


def test_resposta_sem_metadata_nao_inventa_procedencia():
    m = roteador(TransporteFake({"distances": [[500.0]],
                                 "sources": [{"snapped_distance": 1.0}]})).medir(
        ORIGEM, tres_pontos_reais()[:1])
    assert "graph_date" not in m[0].detalhe
    assert m[0].metros == pytest.approx(500.0)


# ===========================================================================
# O PEDIDO de rota (o parser da resposta vem depois da fixture real)
# ===========================================================================
#
# Estes testes existem ANTES do parser de propósito. O lado do pedido é
# testável sem resposta nenhuma, e é onde mora a armadilha que já custou uma
# nota no `_pedir`: trocada a ordem lon/lat, nada estoura — o serviço devolve
# uma rota plausível entre dois pontos errados.

def test_url_de_rota_pede_a_variante_geojson():
    """A escolha do GeoJSON é o que nos poupa de escrever um decodificador de
    polilinha — e um decodificador é parser, e parser é superfície de erro."""
    r = roteador(TransporteFake({}))
    assert r.url_directions.endswith("/v2/directions/foot-walking/geojson")
    assert r.url_directions.startswith(r.url_base)


def test_corpo_de_rota_inverte_para_lon_lat_na_ordem_origem_destino():
    origem, destino = (-29.50186, -51.96529), (-29.49702, -51.95661)
    corpo = orsm.RoteadorORS.corpo_directions(origem, destino)

    assert corpo["coordinates"] == [[-51.96529, -29.50186],
                                    [-51.95661, -29.49702]]
    # Longitude primeiro, e a longitude do Rio Grande do Sul é ~-52: se a
    # inversão cair, o primeiro valor vira ~-29 e a rota sai de outro país.
    assert corpo["coordinates"][0][0] < -50
    assert corpo["coordinates"][0][1] > -40


def test_corpo_de_rota_nao_pede_instrucoes():
    """Rota falada não é exibida em lugar nenhum, e engordaria o relatorio.json.

    O corpo é o MESMO que `scripts/gravar_fixture_ors.py --directions` envia —
    é por isso que ele mora aqui e não no script. Fixture gravada com outro
    corpo testaria um formato que a produção nunca recebe.
    """
    corpo = orsm.RoteadorORS.corpo_directions((-29.5, -51.9), (-29.4, -51.8))
    assert corpo["instructions"] is False
    assert set(corpo) == {"coordinates", "instructions"}


def test_o_accept_da_rota_casa_com_o_sufixo_geojson_da_url():
    """Registro de uma falha REAL, não de uma leitura da documentação.

    A primeira chamada ao endpoint de rota voltou **HTTP 406** com
    ``code 2007 — "This response format is not supported"``, com a chave
    correta (chave recusada devolve 403). O ORS negocia formato pelo par
    (sufixo da URL, cabeçalho Accept), e ``application/json`` — que é o certo
    para a matriz — é recusado no ``/geojson``.

    O teste trava os dois lados do par: se alguém "simplificar" os cabeçalhos
    para um só, a matriz continua funcionando e só a rota quebra, em produção.
    """
    r = roteador(TransporteFake({}))
    rota = r.cabecalhos_directions()
    matriz = r._cabecalhos()

    assert r.url_directions.endswith("/geojson")
    assert "geo+json" in rota["Accept"]
    assert matriz["Accept"] == "application/json"
    assert rota["Accept"] != matriz["Accept"]
    # O que NÃO muda entre os dois: autenticação e o tipo do corpo enviado.
    assert rota["Authorization"] == matriz["Authorization"]
    assert rota["Content-Type"] == matriz["Content-Type"]


# ===========================================================================
# A RESPOSTA de rota, lida da gravação REAL
# ===========================================================================

FIXTURE_ROTA = FIXTURES / "ors_directions_real.json"
DESTINO_ROTA = (-29.49702, -51.95661)     # o mesmo par da fixture da matriz


def resposta_rota() -> dict:
    return json.loads(FIXTURE_ROTA.read_text(encoding="utf-8"))


def test_a_resposta_de_rota_real_tem_o_que_o_parser_espera():
    """Trava o FORMATO. Se o serviço mudar, quebra aqui e não na tela."""
    d = resposta_rota()
    feicao = d["features"][0]
    assert feicao["geometry"]["type"] == "LineString"
    assert feicao["properties"]["summary"]["distance"] == pytest.approx(1732.5)
    # Pontos de 2 dimensões, sem elevação: o parser desempacota [lon, lat].
    assert {len(p) for p in feicao["geometry"]["coordinates"]} == {2}


def test_o_parser_inverte_para_lat_lon_e_le_a_distancia():
    lida = orsm.RoteadorORS.ler_rota(resposta_rota())
    assert lida["metros"] == pytest.approx(1732.5)
    assert lida["segundos"] == pytest.approx(1247.4)
    assert len(lida["coordenadas"]) == 38
    lat, lon = lida["coordenadas"][0]
    # Latitude ~-29 e longitude ~-52: invertido, os dois trocam de ordem de
    # grandeza e a rota some do mapa sem erro nenhum.
    assert -30 < lat < -29 and -52 < lon < -51


def test_os_extremos_da_geometria_sao_os_pontos_ENCAIXADOS_na_via():
    """O achado que dispensou a matriz para este subconjunto.

    Os extremos da rota batem, dígito a dígito, com ``sources[0].location`` e
    ``destinations[0].location`` da matriz do MESMO par — não é aproximação. É
    o que torna o ``snap`` derivável do directions, e com ele o diagnóstico do
    snap sobrevive à troca de endpoint.
    """
    matriz = json.loads(
        (FIXTURES / "ors_matrix_real.json")
        .read_text(encoding="utf-8"))
    lida = orsm.RoteadorORS.ler_rota(resposta_rota())

    lat0, lon0 = lida["coordenadas"][0]
    latf, lonf = lida["coordenadas"][-1]
    assert [lon0, lat0] == matriz["sources"][0]["location"]
    assert [lonf, latf] == matriz["destinations"][0]["location"]


def test_os_dois_endpoints_concordam_no_mesmo_par():
    """Evidência, não garantia — e é por isso que os conjuntos são disjuntos.

    A concordância medida é o que mostra que trocar de endpoint não custa
    acurácia; a disjunção é o que garante que a tela não exiba um número de um
    endpoint sobre um caminho do outro.
    """
    matriz = json.loads(
        (FIXTURES / "ors_matrix_real.json")
        .read_text(encoding="utf-8"))
    da_matriz = matriz["distances"][0][0]
    da_rota = orsm.RoteadorORS.ler_rota(resposta_rota())["metros"]
    assert da_rota == pytest.approx(da_matriz, abs=0.1)


def test_medir_rota_deriva_o_snap_e_bate_com_o_da_matriz():
    m = roteador(TransporteFake(resposta_rota())).medir_rota(
        ORIGEM, DESTINO_ROTA, chave="43000001", rotulo="EMEI Centro")

    assert m.valida and m.metros == pytest.approx(1732.5)
    assert m.detalhe["endpoint"] == "directions"
    assert len(m.detalhe["rota"]) == 38
    # 8,55 m é o snapped_distance que a matriz reportou para a mesma origem; a
    # derivação usa haversine própria, então bate na casa do metro, não no
    # centésimo.
    assert m.snap_m == pytest.approx(8.55, abs=0.5)
    assert m.detalhe["snap_destino_m"] == pytest.approx(10.76, abs=0.5)


def test_medir_rota_usa_a_url_e_o_accept_do_geojson():
    t = TransporteFake(resposta_rota())
    roteador(t).medir_rota(ORIGEM, DESTINO_ROTA, chave="x")
    pedido = t.chamadas[0]
    assert pedido["url"].endswith("/v2/directions/foot-walking/geojson")
    assert "geo+json" in pedido["cabecalhos"]["Accept"]
    assert pedido["corpo"]["coordinates"][0] == [ORIGEM[1], ORIGEM[0]]


def test_os_avisos_do_provedor_nao_se_perdem():
    """A resposta real trouxe um `warnings` sem que se pedisse nada extra.

    Este é inócuo, mas o campo é o mesmo em que o ORS avisaria sobre qualidade
    da rota — e um aviso do provedor que some entre a resposta e o relatório é
    informação perdida no lugar exato em que ela importaria.
    """
    m = roteador(TransporteFake(resposta_rota())).medir_rota(
        ORIGEM, DESTINO_ROTA, chave="x")
    assert any("roadaccessrestrictions" in a
               for a in m.detalhe["avisos_do_provedor"])


def test_a_procedencia_da_malha_viaja_tambem_na_rota():
    m = roteador(TransporteFake(resposta_rota())).medir_rota(
        ORIGEM, DESTINO_ROTA, chave="x")
    assert m.detalhe["graph_date"] == "2026-08-28T12:16:53Z"
    assert m.detalhe["osm_date"] == "2026-08-17T00:00:02Z"


def test_falha_de_rede_na_rota_vira_medicao_sem_numero():
    m = roteador(TransporteFake(erro=OSError("rede fora"))).medir_rota(
        ORIGEM, DESTINO_ROTA, chave="x")
    assert not m.valida and m.metros is None
    assert "rede fora" in m.erro
    assert m.detalhe["endpoint"] == "directions"


def test_resposta_de_rota_sem_geometria_nao_inventa_tracado():
    m = roteador(TransporteFake({"type": "FeatureCollection", "features": []})
                 ).medir_rota(ORIGEM, DESTINO_ROTA, chave="x")
    assert not m.valida
    assert "sem geometria" in m.erro


def test_o_cache_da_rota_guarda_a_GEOMETRIA_e_nao_so_o_numero():
    """A falha silenciosa que o endpoint na chave existe para evitar.

    Um acerto de cache que devolvesse só o número deixaria a tela sem traçado e
    sem erro — e o relatório continuaria se reproduzindo do JSON, mas errado.
    """
    c = ca.CacheRoteamento()
    r1 = roteador(TransporteFake(resposta_rota()), cache=c)
    r1.medir_rota(ORIGEM, DESTINO_ROTA, chave="x")

    # Segundo roteador SEM resposta no transporte: só pode vir do cache.
    m = roteador(TransporteFake(), cache=c).medir_rota(
        ORIGEM, DESTINO_ROTA, chave="x")
    assert m.detalhe["do_cache"] is True
    assert m.metros == pytest.approx(1732.5)
    assert len(m.detalhe["rota"]) == 38


def test_matriz_e_rota_nao_se_contaminam_no_cache():
    """Mesmo par, mesmo perfil, endpoints diferentes: duas entradas.

    Sem isto, um par medido pela matriz seria servido a quem pediu rota — número
    certo, geometria ausente, nenhum erro.
    """
    c = ca.CacheRoteamento()
    roteador(TransporteFake(resposta_gravada()), cache=c).medir(
        ORIGEM, [FakeEquipamento("EMEI Centro", *DESTINO_ROTA, "43000001")])
    guardado_da_matriz = dict(c._dados)

    m = roteador(TransporteFake(resposta_rota()), cache=c).medir_rota(
        ORIGEM, DESTINO_ROTA, chave="43000001")
    assert len(c._dados) == len(guardado_da_matriz) + 1
    assert m.detalhe.get("do_cache") is not True, "veio da matriz por engano"
    assert len(m.detalhe["rota"]) == 38
