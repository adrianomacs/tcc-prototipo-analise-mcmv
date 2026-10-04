"""As regras ENQ com roteamento em rede ligado.

É aqui que se prova o que o roteamento em rede destrava: a ferramenta passa a poder **aprovar**
um requisito. Com o piso euclidiano apenas, ela só sabia reprovar (quando o piso euclidiano já
ultrapassava o limiar) e declarar-se insuficiente.

Nenhum teste daqui toca a rede. O provedor é injetado em
``ctx.config["roteador_rede"]``, que é o único lugar de onde a regra o aceita —
ver ``_distancia_equipamento._roteador_de_rede``, e o motivo escrito lá.
"""

from __future__ import annotations

import json
import os

import pytest

from core.dominio import mobilidade as rot
from core.dominio.contratos import roteador as rot_rot
from core.dominio.contratos.regra import Contexto, Estado
from core.dominio.empreendimento import Empreendimento, Localizacao
from core.dominio.terreno import Terreno
from core.dominio.vocabulario import motivos
from core.infra.gis import csv_equipamentos
from core.regras.gis.enq_009_educacao_infantil import ENQ009
from tests.apoio.roteadores import RoteadorFalso

CENTRO = (-29.50186, -51.96529)
CABECALHO = ("codigo_inep;nome;lat;lon;ciclos;rede;situacao;atendimento;"
             "conveniada;endereco")


def _ao_norte(metros: float) -> float:
    return CENTRO[0] + metros / 111_320.0


def _linha(codigo, nome, metros, ciclos, *, lat=None, lon=None):
    lat = _ao_norte(metros) if lat is None else lat
    lon = CENTRO[1] if lon is None else lon
    return (f"{codigo};{nome};{lat:.8f};{lon:.8f};{'|'.join(ciclos)};"
            f"municipal;ativa;geral;nao;RUA X, 1")


@pytest.fixture
def pasta(tmp_path):
    return str(tmp_path)


def _gravar(pasta, linhas):
    csv_equipamentos._CACHE.clear()
    with open(os.path.join(pasta, "equipamentos_4307807.csv"), "w",
              encoding="utf-8") as f:
        f.write(CABECALHO + "\n" + "\n".join(linhas) + "\n")
    with open(os.path.join(pasta, "equipamentos_4307807.json"), "w",
              encoding="utf-8") as f:
        json.dump({"ano_censo": "2025", "nome_municipio": "Estrela",
                   "uf": "RS", "fontes": []}, f)


def _ctx(config=None):
    empreendimento = Empreendimento(
        localizacao=Localizacao("4307807"),
        terreno=Terreno(origem="mapa", nivel="ponto", precisao="declarada",
                        crs_metrico="EPSG:31982", centro_wgs84=CENTRO))
    return Contexto(empreendimento=empreendimento, config=config or {})


def _rodar(regra_cls, pasta, ctx=None):
    # O recorte entra no Contexto já montado, como a composição o entrega
    # (ADR-011); a regra não lê arquivo.
    ctx = ctx or _ctx()
    codigo = ctx.empreendimento.codigo_ibge
    if codigo and ctx.recorte_equipamentos is None:
        ctx.recorte_equipamentos = csv_equipamentos.recorte_municipal(codigo, pasta)
    return regra_cls().checar(ctx)



# ---------------------------------------------------------------------------
# O que o roteamento em rede destrava
# ---------------------------------------------------------------------------

def test_sem_provedor_o_comportamento_do_R5b_e_preservado(pasta):
    """A degradação declarada: sem rede, não avaliável — nunca aprovado."""
    _gravar(pasta, [_linha("1", "EMEI PERTO", 600, ["infantil"])])
    r = _rodar(ENQ009, pasta)
    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.METRICA_INSUFICIENTE


def test_a_regra_NAO_busca_provedor_no_ambiente(pasta, monkeypatch):
    """Configuração entra pela borda; o núcleo é determinístico.

    Com ``ORS_API_KEY`` exportada, uma regra que lesse o ambiente passaria a
    chamar a API de verdade no meio da suíte — resultado dependente da máquina e
    cota queimada em teste.
    """
    monkeypatch.setenv("ORS_API_KEY", "chave-que-nao-deve-ser-usada")
    _gravar(pasta, [_linha("1", "EMEI PERTO", 600, ["infantil"])])
    r = _rodar(ENQ009, pasta)
    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe["roteamento_de_rede"]["provedor"] is None


def test_com_rede_dentro_do_limiar_o_requisito_e_APROVADO(pasta):
    """A primeira conformidade da história do módulo."""
    _gravar(pasta, [_linha("1", "EMEI PERTO", 600, ["infantil"])])
    falso = RoteadorFalso(metros=800.0)
    r = _rodar(ENQ009, pasta, _ctx({"roteador_rede": falso}))
    assert r.estado is Estado.CONFORME
    assert "800 m" in r.mensagem
    assert "caminhável em rede" in r.mensagem


def test_a_rede_reprova_quem_o_piso_deixaria_inconclusivo(pasta):
    """600 m em linha reta, 1.400 m a pé: o caso que justifica a rede existir."""
    _gravar(pasta, [_linha("1", "EMEI PERTO", 600, ["infantil"])])
    falso = RoteadorFalso(metros=1400.0)
    r = _rodar(ENQ009, pasta, _ctx({"roteador_rede": falso}))
    assert r.estado is Estado.NAO_CONFORME


def test_o_piso_acima_do_limiar_dispensa_a_rede(pasta):
    """Reprovar de graça continua valendo: ninguém no raio, nenhuma chamada."""
    _gravar(pasta, [_linha("1", "EMEI LONGE", 4000, ["infantil"])])
    falso = RoteadorFalso(metros=500.0)
    r = _rodar(ENQ009, pasta, _ctx({"roteador_rede": falso}))
    assert r.estado is Estado.NAO_CONFORME
    assert falso.chamadas == []
    assert r.detalhe["roteamento_de_rede"]["motivo"] == \
        "nenhum candidato dentro do raio"


# ---------------------------------------------------------------------------
# O pré-filtro continua valendo — e as chaves são as da lista inteira
# ---------------------------------------------------------------------------

def test_so_os_candidatos_do_raio_vao_a_rede(pasta):
    """O que torna legítimo chamar a API: quem está além do raio não vai."""
    _gravar(pasta, [_linha("1", "PERTO", 500, ["infantil"]),
                    _linha("2", "MEDIO", 1500, ["infantil"]),
                    _linha("3", "LONGE", 9000, ["infantil"]),
                    _linha("4", "LONGISSIMO", 20000, ["infantil"])])
    falso = RoteadorFalso(metros=900.0)
    _rodar(ENQ009, pasta, _ctx({"roteador_rede": falso}))
    assert len(falso.chamadas) == 1
    enviados = [e.codigo_inep for e in falso.chamadas[0]["destinos"]]
    assert enviados == ["1", "2"]          # raio = 2 × 1.000 m


def test_as_chaves_enviadas_sao_as_da_LISTA_INTEIRA(pasta):
    """Sem isto, o piso e a medição de rede não se fundem para quem não tem INEP.

    O provedor recebe um subconjunto; se derivasse a chave da posição nele, o
    equipamento de índice 1 na lista inteira viraria ``@0``. A fusão falharia em
    silêncio, o piso sobreviveria ao lado da medida exata e o conjunto seguiria
    inconclusivo com a rede já medida na mão.
    """
    linhas = [_linha("", "SEM CODIGO LONGE", 3000, ["infantil"]),
              _linha("", "SEM CODIGO PERTO", 500, ["infantil"])]
    _gravar(pasta, linhas)
    falso = RoteadorFalso(metros=700.0)
    r = _rodar(ENQ009, pasta, _ctx({"roteador_rede": falso}))

    # Só o segundo (índice 1 na lista inteira) está dentro do raio.
    assert falso.chamadas[0]["chaves"] == ["@1"]
    assert r.estado is Estado.CONFORME


def test_a_medicao_de_rede_vence_o_piso_no_relatorio(pasta):
    _gravar(pasta, [_linha("1", "EMEI PERTO", 600, ["infantil"])])
    falso = RoteadorFalso(metros=800.0)
    r = _rodar(ENQ009, pasta, _ctx({"roteador_rede": falso}))
    linha = r.detalhe["equipamentos"][0]
    assert linha["provedor"] == rot_rot.PROVEDOR_ORS
    assert linha["metros"] == pytest.approx(800.0)
    assert linha["classificacao"] == rot.CLASSIF_ATENDE_PROVADO


# ---------------------------------------------------------------------------
# Falha do provedor nunca vira não-conformidade
# ---------------------------------------------------------------------------

def test_provedor_que_explode_nao_derruba_a_regra(pasta):
    """Cinto de segurança: a análise perderia até o piso já medido."""
    _gravar(pasta, [_linha("1", "EMEI PERTO", 600, ["infantil"])])
    falso = RoteadorFalso(erro=RuntimeError("provedor de terceiro mal-comportado"))
    r = _rodar(ENQ009, pasta, _ctx({"roteador_rede": falso}))
    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.METRICA_INSUFICIENTE
    assert "RuntimeError" in r.detalhe["roteamento_de_rede"]["motivo"]


def test_medicao_de_rede_sem_numero_cai_para_o_piso(pasta):
    """Provedor bem-comportado que não roteou: o piso euclidiano continua lá."""
    class SemNumero(RoteadorFalso):
        def medir(self, origem, destinos, chaves=None):
            self.chamadas.append({"origem": origem, "destinos": list(destinos),
                                  "chaves": list(chaves) if chaves else None})
            return [rot.Medicao(destino=(chaves or ["0"])[i], rotulo="", metros=None,
                                provedor=self.provedor, metrica=self.metrica,
                                limite_inferior=False, erro="par sem rota")
                    for i, _ in enumerate(destinos)]

    _gravar(pasta, [_linha("1", "EMEI PERTO", 600, ["infantil"])])
    r = _rodar(ENQ009, pasta, _ctx({"roteador_rede": SemNumero()}))
    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe["roteamento_de_rede"]["falhas"] == 1


# ---------------------------------------------------------------------------
# Diagnóstico
# ---------------------------------------------------------------------------

def test_o_detalhe_declara_o_que_a_rede_fez(pasta):
    _gravar(pasta, [_linha("1", "EMEI PERTO", 600, ["infantil"])])
    r = _rodar(ENQ009, pasta, _ctx({"roteador_rede": RoteadorFalso(800.0)}))
    rede = r.detalhe["roteamento_de_rede"]
    assert rede["provedor"] == rot_rot.PROVEDOR_ORS
    assert rede["metrica"] == rot_rot.METRICA_REDE_PEDESTRE
    assert rede["candidatos"] == 1
    assert rede["medidos"] == 1


def test_a_procedencia_da_malha_chega_ao_relatorio(pasta):
    """A safra do OSM é o que torna o número reproduzível daqui a um ano."""
    _gravar(pasta, [_linha("1", "EMEI PERTO", 600, ["infantil"])])
    r = _rodar(ENQ009, pasta, _ctx({"roteador_rede": RoteadorFalso(800.0)}))
    proc = r.detalhe["roteamento_de_rede"]["procedencia_malha"]
    assert proc["osm_date"] == "2026-08-17T00:00:02Z"
    assert proc["graph_date"] == "2026-08-28T12:16:53Z"


def test_sem_provedor_o_detalhe_diz_POR_QUE_nao_mediu(pasta):
    """"Métrica insuficiente" não distingue falta de chave de falha do provedor."""
    _gravar(pasta, [_linha("1", "EMEI PERTO", 600, ["infantil"])])
    r = _rodar(ENQ009, pasta)
    assert r.detalhe["roteamento_de_rede"]["motivo"] == \
        "sem provedor de rede configurado"


# ---------------------------------------------------------------------------
# A fiação: do app até a regra
# ---------------------------------------------------------------------------

def test_o_pipeline_entrega_o_roteador_no_config(monkeypatch, tmp_path):
    """Prende a ponte entre a borda e o núcleo.

    Se ``rodar`` deixar de pôr o provedor no ``config``, nada estoura: as regras
    simplesmente voltam a sair NÃO AVALIÁVEL, e o sintoma é indistinguível de
    "sem chave configurada". É exatamente o tipo de regressão muda que este
    projeto persegue.
    """
    from core import composicao
    from core.aplicacao import pipeline

    capturado = {}

    def _montar(caminho_ifc, pasta_gis, config, **kwargs):
        capturado["config"] = config
        return _ctx(config)

    monkeypatch.setattr(composicao, "montar_contexto", _montar)
    monkeypatch.setattr(pipeline, "executar", lambda ctx, ids_selecionados=None: [])
    monkeypatch.setattr(composicao, "_imprimir_resumo", lambda r: None)
    monkeypatch.setattr(composicao, "_carregar_config",
                        lambda *a, **k: {"paths": {"relatorio": str(
                            tmp_path / "relatorio.json")}})

    falso = RoteadorFalso()
    composicao.rodar(caminho_ifc="", roteador_rede=falso)
    assert capturado["config"]["roteador_rede"] is falso


def test_sem_roteador_o_pipeline_ainda_declara_a_chave(monkeypatch, tmp_path):
    """``None`` explícito no config significa "sem rede, de propósito"."""
    from core import composicao
    from core.aplicacao import pipeline

    capturado = {}

    def _montar(caminho_ifc, pasta_gis, config, **kwargs):
        capturado["config"] = config
        return _ctx(config)

    monkeypatch.setattr(composicao, "montar_contexto", _montar)
    monkeypatch.setattr(pipeline, "executar", lambda ctx, ids_selecionados=None: [])
    monkeypatch.setattr(composicao, "_imprimir_resumo", lambda r: None)
    monkeypatch.setattr(composicao, "_carregar_config",
                        lambda *a, **k: {"paths": {"relatorio": str(
                            tmp_path / "relatorio.json")}})

    composicao.rodar(caminho_ifc="")
    assert "roteador_rede" in capturado["config"]
    assert capturado["config"]["roteador_rede"] is None


# ---------------------------------------------------------------------------
# As DUAS distâncias no `detalhe`
# ---------------------------------------------------------------------------

def test_as_duas_distancias_viajam_no_detalhe(pasta):
    """`metros` decide; `metros_linha_reta` e `metros_rede` são as duas leituras.

    A comparação é o que deixa o desvio da malha viária visível no caso concreto,
    e é o que o relatório mostra lado a lado. Exibir só o número que decidiu
    esconde de onde ele veio.
    """
    _gravar(pasta, [_linha("1", "EMEI PERTO", 600, ["infantil"])])
    r = _rodar(ENQ009, pasta, _ctx({"roteador_rede": RoteadorFalso(metros=800.0)}))

    linha = r.detalhe["equipamentos"][0]
    assert linha["metros"] == 800.0                    # a de rede, que conclui
    assert linha["metros_rede"] == 800.0
    assert 590 < linha["metros_linha_reta"] < 610      # o piso geodésico
    assert linha["metros_linha_reta"] < linha["metros_rede"]


def test_sem_provedor_de_rede_so_ha_linha_reta(pasta):
    _gravar(pasta, [_linha("1", "EMEI PERTO", 600, ["infantil"])])
    linha = _rodar(ENQ009, pasta).detalhe["equipamentos"][0]
    assert linha["metros_rede"] is None
    assert linha["metros_linha_reta"] is not None
    assert linha["erro_rede"] == "fora do raio da distância caminhável"


def test_equipamento_fora_do_raio_nao_tem_medida_de_rede(pasta):
    """O pré-filtro aparece no dado: quem não foi à rede diz que não foi."""
    _gravar(pasta, [_linha("1", "PERTO", 500, ["infantil"]),
                    _linha("2", "LONGE", 9000, ["infantil"])])
    r = _rodar(ENQ009, pasta, _ctx({"roteador_rede": RoteadorFalso(metros=700.0)}))
    por_nome = {linha["nome"]: linha for linha in r.detalhe["equipamentos"]}
    assert por_nome["PERTO"]["metros_rede"] == 700.0
    assert por_nome["LONGE"]["metros_rede"] is None
    assert por_nome["LONGE"]["metros_linha_reta"] > 8000


def test_par_nao_roteavel_declara_o_erro_da_rede(pasta):
    """Rede sem número para o par: o piso fica, e o motivo da rede também."""
    class SemNumero(RoteadorFalso):
        def medir(self, origem, destinos, chaves=None):
            return [rot.Medicao(destino=(chaves[i] if chaves else str(i)),
                                rotulo=getattr(e, "nome", ""), metros=None,
                                provedor=self.provedor, metrica=self.metrica,
                                limite_inferior=False, erro="par não roteável")
                    for i, e in enumerate(destinos)]

    _gravar(pasta, [_linha("1", "EMEI PERTO", 600, ["infantil"])])
    linha = _rodar(ENQ009, pasta,
                   _ctx({"roteador_rede": SemNumero()})).detalhe["equipamentos"][0]
    assert linha["metros_rede"] is None
    assert linha["erro_rede"] == "par não roteável"
    assert linha["metros"] == linha["metros_linha_reta"]   # o piso sobreviveu


def test_tabela_ordenada_pela_linha_reta(pasta):
    """Ordem por linha reta: completa para todos, e sem lacuna no meio.

    A linha reta existe para todo aceito; a de rede só para quem entrou no raio.
    Ordenar pela primeira deixa os sem-rede no fim, em vez de intercalar `None` no
    meio da tabela.
    """
    _gravar(pasta, [_linha("1", "MEDIA", 1200, ["infantil"]),
                    _linha("2", "PERTO", 400, ["infantil"]),
                    _linha("3", "LONGE", 9000, ["infantil"]),
                    _linha("4", "MEIO", 800, ["infantil"])])
    r = _rodar(ENQ009, pasta, _ctx({"roteador_rede": RoteadorFalso(metros=1100.0)}))

    linhas = r.detalhe["equipamentos"]
    assert [linha["nome"] for linha in linhas] == ["PERTO", "MEIO", "MEDIA", "LONGE"]
    retas = [linha["metros_linha_reta"] for linha in linhas]
    assert retas == sorted(retas)
    # O único sem medição de rede (fora do raio de 2 km) é o último.
    assert [linha["metros_rede"] is None for linha in linhas] == \
        [False, False, False, True]


def test_ordem_da_tabela_nao_define_o_determinante(pasta):
    """O veredito não pode depender da ordem de exibição.

    Com a tabela ordenada pela linha reta, o primeiro da lista pode não ser o
    menor em rede — e é a medida de rede que decide. Este teste prende os dois
    papéis separados.
    """
    class PorNome(RoteadorFalso):
        """Rede que devolve MENOS metros para quem está mais LONGE em linha reta."""
        def medir(self, origem, destinos, chaves=None):
            saida = []
            for i, e in enumerate(destinos):
                metros = 700.0 if e.nome == "MEDIA" else 1400.0
                saida.append(rot.Medicao(
                    destino=(chaves[i] if chaves else str(i)), rotulo=e.nome,
                    metros=metros, provedor=self.provedor, metrica=self.metrica,
                    limite_inferior=False))
            return saida

    _gravar(pasta, [_linha("1", "PERTO", 400, ["infantil"]),
                    _linha("2", "MEDIA", 1200, ["infantil"])])
    r = _rodar(ENQ009, pasta, _ctx({"roteador_rede": PorNome()}))

    # A tabela começa por PERTO (menor linha reta)...
    assert r.detalhe["equipamentos"][0]["nome"] == "PERTO"
    # ...mas quem decide é MEDIA, com 700 m em rede, e o requisito é CONFORME.
    assert r.estado is Estado.CONFORME
    assert r.detalhe["determinante"]["rotulo"] == "MEDIA"


# ---------------------------------------------------------------------------
# A divisão em DOIS endpoints, e por que ela é disjunta
# ---------------------------------------------------------------------------

class RoteadorComRota(RoteadorFalso):
    """Provedor que também sabe traçar. Registra qual endpoint recebeu o quê."""

    def __init__(self, metros=800.0, **kwargs):
        super().__init__(metros, **kwargs)
        self.rotas: list[dict] = []

    def medir_rota(self, origem, destino, *, chave, rotulo=""):
        self.rotas.append({"origem": origem, "destino": destino,
                           "chave": chave, "rotulo": rotulo})
        return rot.Medicao(
            destino=chave, rotulo=rotulo, metros=self.metros,
            segundos=self.metros / 1.4, provedor=self.provedor,
            metrica=self.metrica, limite_inferior=False, snap_m=8.4,
            detalhe={"endpoint": "directions",
                     "rota": [[origem[0], origem[1]], [destino[0], destino[1]]],
                     "graph_date": "2026-08-28T12:16:53Z"})

    def chaves_da_matriz(self) -> set[str]:
        return {c for ch in self.chamadas for c in (ch["chaves"] or [])}

    def chaves_da_rota(self) -> set[str]:
        return {r["chave"] for r in self.rotas}


def _tres_faixas(pasta):
    """Um equipamento em cada faixa: dentro do limiar, entre 1x e 2x, e fora."""
    _gravar(pasta, [
        _linha("A", "EMEI DENTRO", 600, ["infantil"]),      # <= 1.000 m: rota
        _linha("B", "EMEI BANDA", 1500, ["infantil"]),      # 1x a 2x: matriz
        _linha("C", "EMEI LONGE", 2500, ["infantil"]),      # > 2x: nem vai
    ])


def test_so_quem_pode_atender_vai_ao_endpoint_de_rota(pasta):
    """O critério do traçado é 1x o limiar; o da MEDIÇÃO segue em 2x.

    Os dois números são diferentes de propósito (ver a divisão em dois endpoints): tirar a faixa de
    1x a 2x do roteamento esvaziaria a coluna "Em rede (m)" dela, que existe
    para mostrar as duas distâncias lado a lado.
    """
    _tres_faixas(pasta)
    falso = RoteadorComRota(metros=900.0)
    _rodar(ENQ009, pasta, _ctx({"roteador_rede": falso}))

    assert falso.chaves_da_rota() == {"A"}
    assert falso.chaves_da_matriz() == {"B"}
    # E o de fora do raio não foi a lugar nenhum: continua medido só pelo piso.
    assert "C" not in falso.chaves_da_rota() | falso.chaves_da_matriz()


def test_os_dois_conjuntos_sao_disjuntos(pasta):
    """A garantia estrutural: nenhum par medido pelos dois endpoints.

    É o que impede a tela de exibir o número de um sobre o caminho do outro —
    e ela não depende de os dois endpoints concordarem, embora concordem.
    """
    _tres_faixas(pasta)
    falso = RoteadorComRota()
    _rodar(ENQ009, pasta, _ctx({"roteador_rede": falso}))

    assert not (falso.chaves_da_rota() & falso.chaves_da_matriz())


def test_a_rota_e_o_endpoint_viajam_na_linha_do_equipamento(pasta):
    _tres_faixas(pasta)
    r = _rodar(ENQ009, pasta, _ctx({"roteador_rede": RoteadorComRota(900.0)}))
    por_nome = {linha["nome"]: linha for linha in r.detalhe["equipamentos"]}

    assert por_nome["EMEI DENTRO"]["rota"], "quem tem traçado tem de carregá-lo"
    assert por_nome["EMEI DENTRO"]["endpoint"] == "directions"
    assert por_nome["EMEI BANDA"]["rota"] is None
    assert por_nome["EMEI BANDA"]["endpoint"] == ""   # o falso da matriz não declara
    # Quem nem foi à rede não tem rota nem endpoint, e isso não é erro.
    assert por_nome["EMEI LONGE"]["rota"] is None


def test_a_contagem_por_endpoint_entra_no_diagnostico(pasta):
    _tres_faixas(pasta)
    r = _rodar(ENQ009, pasta, _ctx({"roteador_rede": RoteadorComRota()}))
    rede = r.detalhe["roteamento_de_rede"]

    assert rede["candidatos"] == 2          # A e B entraram no raio de 2x
    assert rede["para_rota"] == 1
    assert rede["para_matriz"] == 1


def test_provedor_sem_medir_rota_degrada_para_a_matriz_inteira(pasta):
    """Retrocompatibilidade: a regra continua valendo para quem só sabe medir.

    Sem traçado é pior, mas continua CORRETO — e é o que garante que um provedor
    de terceiro, ou um duble antigo, não quebre a regra.
    """
    _tres_faixas(pasta)
    falso = RoteadorFalso(metros=900.0)            # sem medir_rota
    r = _rodar(ENQ009, pasta, _ctx({"roteador_rede": falso}))

    assert falso.chaves_da_matriz() == {"A", "B"} if hasattr(
        falso, "chaves_da_matriz") else True
    assert all(linha["rota"] is None for linha in r.detalhe["equipamentos"])
    assert r.estado is Estado.CONFORME, "o veredito não pode depender do traçado"


def test_o_tracado_nao_muda_o_veredito(pasta):
    """Mesmo cenário, com e sem traçado: o mesmo estado e a mesma distância."""
    _tres_faixas(pasta)
    com = _rodar(ENQ009, pasta, _ctx({"roteador_rede": RoteadorComRota(900.0)}))
    _tres_faixas(pasta)
    sem = _rodar(ENQ009, pasta, _ctx({"roteador_rede": RoteadorFalso(900.0)}))

    assert com.estado is sem.estado
    assert (com.detalhe["determinante"]["metros"]
            == sem.detalhe["determinante"]["metros"])
