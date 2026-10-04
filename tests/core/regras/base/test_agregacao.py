"""Agregação por limites e regras remetidas.

O que estes testes prendem, em ordem de importância:

1. **Que `agrega` não gateia.** É o defeito que a agregação existe para não cometer: um
   pai declarado com `depende_de` sairia NÃO AVALIÁVEL por `prerequisito_falho`,
   sem intervalo e com a causa errada, exatamente quando a alternativa A
   reprovasse — e ficaria impedido de aprovar pela alternativa B no dia em que
   ela existisse. Plausível na tela, errado por dentro.
2. **Que membro não avaliável nunca conta contra.** Contá-lo seria reprovar por
   ignorância; é o §4 do recorte na camada da agregação.
3. **Que a filiação declarada bate com a planilha-mãe.** A autoridade normativa
   continua sendo a planilha; o código declara, e o teste confronta.
4. **Que o teto de reprovabilidade é declarado**, com `xfail` estrito para o dia
   em que a alternativa B ganhar motor.
5. **Que na seleção exclusiva discordância é indecisão, não reprovação** (§7,
   ADR-026): o mesmo par de ramos que `todos` reprovaria sai NÃO AVALIÁVEL com
   `analise_humana_documental` — o erro que a DN-08 existe para impedir.
"""

from __future__ import annotations

import json
import os

import pytest

from core.aplicacao.executor import executar
from core.dominio import equipamentos as eq
from core.dominio.contratos.regra import Contexto, Estado, Resultado, Verbo
from core.dominio.empreendimento import Empreendimento, Localizacao
from core.dominio.terreno import Terreno
from core.dominio.vocabulario import motivos
from core.infra.gis import csv_equipamentos
from core.regras.base import agregacao as ag
from core.regras.gis.enq_010_2_transporte_escolar import ENQ0102
from core.regras.registro import regras_registradas
from tests.conftest import RAIZ

CENTRO = (-29.5013, -51.9650)
CABECALHO = ("codigo_inep;nome;latitude;longitude;ciclo;rede;situacao;"
             "atendimento;conveniada;endereco")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ao_norte(metros: float) -> float:
    return CENTRO[0] + metros / 111_320.0


def _linha(codigo, nome, metros, ciclos):
    lat = _ao_norte(metros)
    return (f"{codigo};{nome};{lat:.8f};{CENTRO[1]:.8f};{'|'.join(ciclos)};"
            f"municipal;ativa;geral;nao;RUA X, 1")


def _gravar(pasta, codigo_ibge, linhas):
    csv_equipamentos._CACHE.clear()
    with open(os.path.join(pasta, f"equipamentos_{codigo_ibge}.csv"),
              "w", encoding="utf-8") as f:
        f.write(CABECALHO + "\n" + "\n".join(linhas) + "\n")
    with open(os.path.join(pasta, f"equipamentos_{codigo_ibge}.json"),
              "w", encoding="utf-8") as f:
        json.dump({"ano_censo": "2025", "nome_municipio": "Estrela", "uf": "RS",
                   "fontes": [{"arquivo": "Tabela_Escola_2025_V2.csv"}]}, f)


def _res(rid, estado, motivo="", descricao="", **detalhe) -> Resultado:
    det = dict(detalhe)
    if motivo:
        det[motivos.CHAVE] = motivo
    return Resultado(regra_id=rid, estado=estado, descricao=descricao,
                     detalhe=det)


def _ctx_resultados(**por_id) -> Contexto:
    return Contexto(resultados=dict(por_id))


class _PaiQualquer(ag.RegraAgregacao):
    """Pai de teste, fora do registro (não decorado com @registrar)."""
    id = "TST-000"
    descricao = "pai de teste"
    agrega = ["TST-000.1", "TST-000.2"]
    modo = ag.MODO_QUALQUER


# ---------------------------------------------------------------------------
# 1. A função pura
# ---------------------------------------------------------------------------

def test_um_conforme_decide_o_ou():
    estado, n_conf, n_pot = ag.por_limites(
        [Estado.CONFORME, Estado.NAO_AVALIAVEL], k=1)
    assert estado is Estado.CONFORME
    assert (n_conf, n_pot) == (1, 2)


def test_conforme_nao_espera_o_membro_em_aberto():
    """`n_conf >= k` fecha: nenhum dado novo pode reverter um conforme."""
    estado, _, _ = ag.por_limites(
        [Estado.NAO_CONFORME, Estado.CONFORME, Estado.NAO_AVALIAVEL], k=1)
    assert estado is Estado.CONFORME


def test_todos_avaliados_e_nenhum_atende_reprova():
    estado, n_conf, n_pot = ag.por_limites(
        [Estado.NAO_CONFORME, Estado.NAO_CONFORME], k=1)
    assert estado is Estado.NAO_CONFORME
    assert (n_conf, n_pot) == (0, 0)


def test_membro_em_aberto_impede_a_reprovacao():
    """O coração do §3.7: não avaliável entra em n_pot, nunca contra."""
    estado, n_conf, n_pot = ag.por_limites(
        [Estado.NAO_CONFORME, Estado.NAO_AVALIAVEL], k=1)
    assert estado is Estado.NAO_AVALIAVEL
    assert (n_conf, n_pot) == (0, 1)


def test_membro_nao_executado_conta_como_em_aberto():
    """``None`` é membro sem resultado — e vale o mesmo que não avaliável.

    Tratá-lo como inexistente encolheria n_pot e produziria reprovação a partir
    de um membro que ninguém avaliou.
    """
    estado, n_conf, n_pot = ag.por_limites([Estado.NAO_CONFORME, None], k=1)
    assert estado is Estado.NAO_AVALIAVEL
    assert (n_conf, n_pot) == (0, 1)


def test_exemplo_da_contagem_minima_do_plano():
    """O exemplo do §3.7: 3 confirmados, 6 no melhor cenário, exigidos 4."""
    estados = ([Estado.CONFORME] * 3 + [Estado.NAO_AVALIAVEL] * 3
               + [Estado.NAO_CONFORME] * 2)
    estado, n_conf, n_pot = ag.por_limites(estados, k=4)
    assert estado is Estado.NAO_AVALIAVEL
    assert (n_conf, n_pot) == (3, 6)


def test_contagem_minima_reprova_quando_o_melhor_cenario_nao_alcanca():
    estados = [Estado.CONFORME] + [Estado.NAO_CONFORME] * 5
    estado, n_conf, n_pot = ag.por_limites(estados, k=4)
    assert estado is Estado.NAO_CONFORME
    assert (n_conf, n_pot) == (1, 1)


def test_k_de_cada_modo():
    assert ag.k_de(ag.MODO_QUALQUER, 5) == 1
    assert ag.k_de(ag.MODO_TODOS, 5) == 5
    assert ag.k_de(ag.MODO_CONTAGEM_MINIMA, 8, 2) == 2


def test_contagem_minima_sem_k_declarado_e_erro():
    with pytest.raises(ValueError, match="k_minimo"):
        ag.k_de(ag.MODO_CONTAGEM_MINIMA, 8)


def test_modo_desconhecido_e_erro():
    with pytest.raises(ValueError, match="Modo de agregação"):
        ag.k_de("mais_ou_menos", 3)


def test_agregacao_sem_membros_e_erro():
    with pytest.raises(ValueError, match="sem membros"):
        ag.por_limites([], k=1)


# ---------------------------------------------------------------------------
# 2. A regra de agregação
# ---------------------------------------------------------------------------

def test_pai_conforme_nomeia_a_alternativa_que_decidiu():
    ctx = _ctx_resultados(**{"TST-000.1": _res("TST-000.1", Estado.CONFORME),
                             "TST-000.2": _res("TST-000.2", Estado.NAO_AVALIAVEL,
                                               motivo=motivos.INSUMO_AUSENTE)})
    r = _PaiQualquer().checar(ctx)
    assert r.estado is Estado.CONFORME
    assert "TST-000.1" in r.mensagem
    assert r.detalhe["n_conf"] == 1 and r.detalhe["k"] == 1


def test_pai_indeciso_reporta_o_intervalo_contra_o_limiar():
    ctx = _ctx_resultados(**{
        "TST-000.1": _res("TST-000.1", Estado.NAO_CONFORME),
        "TST-000.2": _res("TST-000.2", Estado.NAO_AVALIAVEL,
                          motivo=motivos.ANALISE_HUMANA_DOCUMENTAL)})
    r = _PaiQualquer().checar(ctx)
    assert r.estado is Estado.NAO_AVALIAVEL
    assert (r.detalhe["n_conf"], r.detalhe["n_pot"], r.detalhe["k"]) == (0, 1, 1)
    # O intervalo aparece na frase, não só no JSON: "quanto falta" é o que o
    # §3.7 quer que o relatório diga.
    assert "0 e 1" in r.mensagem
    assert r.valor_esperado == 1 and r.valor_encontrado == 0


def test_pai_herda_o_motivo_quando_a_pendencia_e_unanime():
    """Herdar preserva a AÇÃO específica ("obtenha a declaração")."""
    ctx = _ctx_resultados(**{
        "TST-000.1": _res("TST-000.1", Estado.NAO_CONFORME),
        "TST-000.2": _res("TST-000.2", Estado.NAO_AVALIAVEL,
                          motivo=motivos.ANALISE_HUMANA_DOCUMENTAL)})
    r = _PaiQualquer().checar(ctx)
    assert r.detalhe[motivos.CHAVE] == motivos.ANALISE_HUMANA_DOCUMENTAL


def test_pai_usa_motivo_generico_quando_as_pendencias_divergem():
    ctx = _ctx_resultados(**{
        "TST-000.1": _res("TST-000.1", Estado.NAO_AVALIAVEL,
                          motivo=motivos.METRICA_INSUFICIENTE),
        "TST-000.2": _res("TST-000.2", Estado.NAO_AVALIAVEL,
                          motivo=motivos.ANALISE_HUMANA_DOCUMENTAL)})
    r = _PaiQualquer().checar(ctx)
    assert r.detalhe[motivos.CHAVE] == motivos.AGREGACAO_INDECISA
    # As duas ações continuam disponíveis, uma por membro.
    acoes = [m["acao"] for m in r.detalhe["membros"]]
    assert all(acoes) and len(set(acoes)) == 2


def test_membro_ausente_do_contexto_e_declarado_nao_executado():
    ctx = _ctx_resultados(**{"TST-000.1": _res("TST-000.1", Estado.NAO_CONFORME)})
    r = _PaiQualquer().checar(ctx)
    assert r.estado is Estado.NAO_AVALIAVEL
    ausente = next(m for m in r.detalhe["membros"] if m["id"] == "TST-000.2")
    assert ausente["executado"] is False
    assert ausente["motivo"] == motivos.MEMBRO_NAO_EXECUTADO
    assert ausente["conta_para"] == ag.CONTA_POTENCIAL


def test_pai_reprova_quando_todos_os_membros_reprovam():
    ctx = _ctx_resultados(**{"TST-000.1": _res("TST-000.1", Estado.NAO_CONFORME),
                             "TST-000.2": _res("TST-000.2", Estado.NAO_CONFORME)})
    r = _PaiQualquer().checar(ctx)
    assert r.estado is Estado.NAO_CONFORME
    assert r.detalhe["reprovabilidade"]["reprovavel"] is True


def test_pai_sem_membros_declarados_e_erro():
    class _Vazio(ag.RegraAgregacao):
        id = "TST-999"
    with pytest.raises(ValueError, match="não declarou membros"):
        _Vazio().checar(_ctx_resultados())


def test_elementos_dos_membros_sobem_para_o_pai():
    m1 = Resultado(regra_id="TST-000.1", estado=Estado.CONFORME,
                   elementos=["G1", "G2"])
    m2 = Resultado(regra_id="TST-000.2", estado=Estado.NAO_CONFORME,
                   elementos=["G3"])
    r = _PaiQualquer().checar(_ctx_resultados(**{"TST-000.1": m1,
                                                "TST-000.2": m2}))
    assert r.elementos == ["G1", "G2", "G3"]


# ---------------------------------------------------------------------------
# 3. As regras remetidas
# ---------------------------------------------------------------------------

def test_remetida_sai_nao_avaliavel_com_a_causa_e_a_acao():
    r = ENQ0102().checar(Contexto())
    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.ANALISE_HUMANA_DOCUMENTAL
    assert r.detalhe["automatizavel"] is False
    assert r.detalhe["insumo"] and r.detalhe["porque"] and r.detalhe["fundamento"]
    assert r.mensagem


def test_remetida_nao_depende_de_terreno_nem_de_municipio():
    """Sem gate: a causa verdadeira não pode ser trocada pela da moldura.

    Com ``exige_terreno``, a regra sairia `terreno_ausente` enquanto a tela não
    tivesse terreno — escondendo que ela nunca vai avaliar, de terreno nenhum.
    """
    assert ENQ0102.exige_terreno == ""
    assert ENQ0102.depende_de == []
    r = ENQ0102().checar(Contexto())
    assert r.detalhe[motivos.CHAVE] == motivos.ANALISE_HUMANA_DOCUMENTAL


def test_as_duas_alternativas_b_nao_sao_o_mesmo_requisito():
    """A assimetria normativa entre os itens 3.b e 3.c, presa em teste.

    O item 3.b admite só transporte ESCOLAR e não manda computar a caminhada; o
    3.c admite escolar OU coletivo e manda computar (Redação 335/2026). A base
    derivada havia achatado a diferença, e achatá-la de novo mudaria o que cada
    requisito exigiria do analista.
    """
    from core.regras.gis.enq_011_2_transporte_escolar_ou_coletivo import ENQ0112

    assert ENQ0102.parametro["computa_caminhada"] is False
    assert ENQ0112.parametro["computa_caminhada"] is True
    assert "coletivo" not in ENQ0102.parametro["modal"]
    assert "coletivo" in ENQ0112.parametro["modal"]


# ---------------------------------------------------------------------------
# 4. O executor: `agrega` ordena e NÃO gateia
# ---------------------------------------------------------------------------

@pytest.fixture
def recorte(tmp_path, monkeypatch):
    """Recorte municipal num diretório temporário, visto pelas regras-folha.

    A pasta vai para o leitor, e ``_ctx_terreno`` entrega o recorte já montado
    no Contexto, como a composição faz (ADR-011).
    """
    monkeypatch.setattr(csv_equipamentos, "PASTA_RECORTES", str(tmp_path))
    return tmp_path


def _ctx_terreno(config=None) -> Contexto:
    terreno = Terreno(origem="mapa", nivel="ponto", precisao="declarada",
                      crs_metrico="EPSG:31982", centro_wgs84=CENTRO)
    empreendimento = Empreendimento(localizacao=Localizacao("4307807"),
                                    terreno=terreno)
    return Contexto(empreendimento=empreendimento, config=config or {},
                    recorte_equipamentos=csv_equipamentos.recorte_municipal(
                        "4307807", csv_equipamentos.PASTA_RECORTES))


def test_pai_roda_depois_dos_membros_e_recebe_os_resultados(recorte):
    _gravar(recorte, "4307807", [_linha("1", "EMEF Perto", 200, [eq.CICLO_FUND_I])])
    resultados = executar(_ctx_terreno(), ids_selecionados=["ENQ-010"])
    # Selecionar o pai puxou os dois membros, sem que a tela os pedisse.
    assert {"ENQ-010", "ENQ-010.1", "ENQ-010.2"} <= set(resultados)
    assert resultados["ENQ-010"].detalhe["total_membros"] == 2


def test_membro_nao_conforme_nao_curto_circuita_o_pai(recorte):
    """A regressão da agregação: `agrega` não é `depende_de`.

    Com a alternativa A reprovada, o pai TEM de agregar — e sair indeciso com o
    intervalo declarado. Se saísse por `prerequisito_falho`, a tela mostraria um
    não avaliável plausível com a causa errada e sem intervalo, e o pai ficaria
    impedido de aprovar pela alternativa B no dia em que ela existisse.
    """
    _gravar(recorte, "4307807", [_linha("1", "EMEF Longe", 4000, [eq.CICLO_FUND_I])])
    resultados = executar(_ctx_terreno(), ids_selecionados=["ENQ-010"])

    assert resultados["ENQ-010.1"].estado is Estado.NAO_CONFORME
    pai = resultados["ENQ-010"]
    assert pai.estado is Estado.NAO_AVALIAVEL
    assert pai.detalhe[motivos.CHAVE] != motivos.PREREQUISITO_FALHO
    assert pai.detalhe[motivos.CHAVE] == motivos.ANALISE_HUMANA_DOCUMENTAL
    assert (pai.detalhe["n_conf"], pai.detalhe["n_pot"]) == (0, 1)


def test_pai_conforme_pela_alternativa_de_distancia(recorte):
    """Com medição em rede dentro do limiar, o pai fecha conforme."""
    _gravar(recorte, "4307807", [_linha("1", "EMEF Perto", 200, [eq.CICLO_FUND_I])])
    from tests.apoio.roteadores import RoteadorFalso

    resultados = executar(
        _ctx_terreno(config={"roteador_rede": RoteadorFalso(metros=300.0)}),
        ids_selecionados=["ENQ-010"])
    assert resultados["ENQ-010.1"].estado is Estado.CONFORME
    assert resultados["ENQ-010"].estado is Estado.CONFORME
    assert resultados["ENQ-010"].detalhe["membros"][0]["conta_para"] == \
        ag.CONTA_CONFIRMADO


def test_pai_indeciso_com_causas_divergentes_quando_falta_a_metrica(recorte):
    """Sem provedor de rede: A fica `metrica_insuficiente`, B remetida.

    Duas causas diferentes, então o motivo do pai é o genérico — e as duas ações
    continuam na tabela de membros.
    """
    _gravar(recorte, "4307807", [_linha("1", "EMEF Perto", 200, [eq.CICLO_FUND_I])])
    resultados = executar(_ctx_terreno(), ids_selecionados=["ENQ-010"])
    assert resultados["ENQ-010.1"].detalhe[motivos.CHAVE] == \
        motivos.METRICA_INSUFICIENTE
    assert resultados["ENQ-010"].detalhe[motivos.CHAVE] == \
        motivos.AGREGACAO_INDECISA


def test_terreno_ausente_nao_transforma_o_pai_em_erro(recorte):
    """O gate do terreno é dos membros; o pai só agrega o que veio deles."""
    _gravar(recorte, "4307807", [_linha("1", "EMEF Perto", 200, [eq.CICLO_FUND_I])])
    ctx = Contexto(empreendimento=Empreendimento(localizacao=Localizacao("4307807")))
    resultados = executar(ctx, ids_selecionados=["ENQ-011"])
    assert resultados["ENQ-011.1"].detalhe[motivos.CHAVE] == \
        motivos.TERRENO_AUSENTE
    pai = resultados["ENQ-011"]
    assert pai.estado is Estado.NAO_AVALIAVEL
    assert pai.detalhe[motivos.CHAVE] == motivos.AGREGACAO_INDECISA
    assert pai.detalhe["n_pot"] == 2


# ---------------------------------------------------------------------------
# 5. O teto de reprovabilidade (decisão D7)
# ---------------------------------------------------------------------------

def test_teto_declarado_no_resultado(recorte):
    _gravar(recorte, "4307807", [_linha("1", "EMEF Longe", 4000, [eq.CICLO_FUND_I])])
    resultados = executar(_ctx_terreno(), ids_selecionados=["ENQ-010"])
    teto = resultados["ENQ-010"].detalhe["reprovabilidade"]
    assert teto["reprovavel"] is False
    assert teto["membros_irredutiveis"] == ["ENQ-010.2"]
    assert "APROVADO" in teto["explicacao"]


@pytest.mark.xfail(strict=True, reason=(
    "ENQ-010.2 é remetida a parecer, então n_pot >= 1 sempre e o pai não pode "
    "reprovar (decisão D7 de 12/09/2026). No dia em que a alternativa B ganhar "
    "motor, este teste passa e ESTE xfail falha — de propósito: é o sinal para "
    "revisar o teto declarado no recorte, no plano e no texto do TCC."))
def test_pai_reprovaria_se_a_alternativa_b_fosse_avaliavel(recorte):
    _gravar(recorte, "4307807", [_linha("1", "EMEF Longe", 4000, [eq.CICLO_FUND_I])])
    resultados = executar(_ctx_terreno(), ids_selecionados=["ENQ-010"])
    assert resultados["ENQ-010"].estado is Estado.NAO_CONFORME


# ---------------------------------------------------------------------------
# 6. A filiação declarada × a planilha-mãe
# ---------------------------------------------------------------------------

def _filhos_da_planilha() -> dict[str, list[str]]:
    openpyxl = pytest.importorskip("openpyxl")
    caminho = os.path.join(RAIZ, "config",
                           "Base_Requisitos_Portaria_MCID_725.xlsx")
    if not os.path.exists(caminho):
        pytest.skip("planilha-mãe ausente neste recorte do repositório")

    wb = openpyxl.load_workbook(caminho, data_only=True, read_only=True)
    ws = wb["Base de Requisitos (granular)"]
    linhas = ws.iter_rows(values_only=True)
    cabecalho = [c for c in next(linhas)]
    col = {nome: i for i, nome in enumerate(cabecalho)}

    filhos: dict[str, list[str]] = {}
    metodo: dict[str, str] = {}
    for linha in linhas:
        rid = str(linha[col["ID"]] or "").strip()
        pai = str(linha[col["Grupo (pai)"]] or "").strip()
        if not rid:
            continue
        metodo[rid] = str(linha[col["Método de verificação"]] or "").strip()
        if pai and pai != rid:
            filhos.setdefault(pai, []).append(rid)
    wb.close()
    return filhos, metodo


def test_membros_declarados_batem_com_a_planilha_mae():
    """A planilha é a autoridade normativa; o código declara e o teste confronta.

    Por que não ler a filiação de uma base enxuta em tempo de execução:
    ela seria DERIVADA (filtrada por regras_ativas.yaml), e fazer o
    veredito depender de um derivado gerado é a família do "cache que mente" que
    o gerador de equipamentos já evita por SHA-256. O código declara; este teste
    é o vínculo. Um ENQ-010.3 acrescentado à planilha quebra aqui, em vez de o
    pai seguir agregando um "ou" incompleto em silêncio.
    """
    filhos, _ = _filhos_da_planilha()
    agregadores = {rid: cls for rid, cls in regras_registradas().items()
                   if getattr(cls, "agrega", None)}
    assert agregadores, "nenhuma regra de agregação registrada"

    for rid, cls in sorted(agregadores.items()):
        assert sorted(cls.agrega) == sorted(filhos.get(rid, [])), (
            f"{rid}: membros declarados {sorted(cls.agrega)} divergem dos "
            f"filhos da planilha {sorted(filhos.get(rid, []))}")


def test_agregador_registrado_e_agregacao_na_planilha():
    """Declarar `agrega` onde a norma não agrega também é divergência."""
    _, metodo = _filhos_da_planilha()
    for rid, cls in regras_registradas().items():
        if getattr(cls, "agrega", None):
            assert metodo.get(rid) == "Agregação", (
                f"{rid} declara 'agrega', mas a planilha registra método "
                f"{metodo.get(rid)!r}")
            assert cls.verbo is Verbo.AGREGACAO


def test_alternativas_b_ativas_no_recorte():
    """Se saírem de regras_ativas.yaml, o pai volta a poder reprovar por engano."""
    import yaml

    with open(os.path.join(RAIZ, "config", "regras_ativas.yaml"),
              encoding="utf-8") as f:
        ativas = set(yaml.safe_load(f)["ativas"])
    assert {"ENQ-010.2", "ENQ-011.2"} <= ativas
    for rid in ("ENQ-010", "ENQ-011", "ENQ-010.1", "ENQ-011.1"):
        assert rid in ativas


def test_grupo_declara_as_sete_verificacoes():
    """A tela deixa de mostrar 5 e produzir 3."""
    from core.aplicacao import grupos as grupos_mod

    grupos = grupos_mod.carregar(os.path.join(RAIZ, "config",
                                              "grupos_requisitos.yaml"))
    ids = grupos["enquadramento"].ids
    assert ids == ["ENQ-009", "ENQ-010", "ENQ-010.1", "ENQ-010.2",
                   "ENQ-011", "ENQ-011.1", "ENQ-011.2"]
    registradas = regras_registradas()
    assert all(rid in registradas for rid in ids), \
        "toda verificação do grupo tem motor: nenhuma fica 'em implementação'"


# ---------------------------------------------------------------------------
# 7. A seleção exclusiva (ADR-026): discordância é indecisão, não reprovação
# ---------------------------------------------------------------------------

class _PaiExclusivo(ag.RegraAgregacao):
    """Pai de seleção exclusiva, fora do registro."""
    id = "TST-EXC"
    descricao = "pai exclusivo de teste"
    agrega = ["TST-EXC.1", "TST-EXC.2"]
    modo = ag.MODO_SELECAO_EXCLUSIVA
    rotulo_membro = "ramo(s)"


class _PaiTodos(ag.RegraAgregacao):
    """O mesmo par de ramos sob `todos` — o contraste que o ADR-026 exige."""
    id = "TST-TOD"
    descricao = "pai 'todos' de teste"
    agrega = ["TST-EXC.1", "TST-EXC.2"]
    modo = ag.MODO_TODOS


def _ramo(rid, veredito, aplicabilidade=ag.RAMO_INDETERMINADA,
          estado=None, motivo="") -> Resultado:
    """Resultado de um RAMO como o pai o recebe: o estado emitido (por padrão
    NÃO AVALIÁVEL, aplicabilidade em aberto) e, no detalhe, o que o ramo
    declara sobre si — se aplica e o veredito sob o próprio limite."""
    det = {ag.CHAVE_APLICABILIDADE: aplicabilidade,
           ag.CHAVE_VEREDITO_RAMO: veredito.value if veredito else ""}
    if estado is None:
        estado = (veredito if aplicabilidade == ag.RAMO_APLICAVEL and veredito
                  else Estado.NAO_AVALIAVEL)
    if estado is Estado.NAO_AVALIAVEL:
        det[motivos.CHAVE] = motivo or motivos.ANALISE_HUMANA_DOCUMENTAL
    return Resultado(regra_id=rid, estado=estado, detalhe=det)


def test_funcao_pura_da_selecao_exclusiva():
    C, NC = Estado.CONFORME, Estado.NAO_CONFORME
    assert ag.selecao_exclusiva([C]) == (C, ag.SELECAO_HERDADO)
    assert ag.selecao_exclusiva([NC]) == (NC, ag.SELECAO_HERDADO)
    assert ag.selecao_exclusiva([None]) == (Estado.NAO_AVALIAVEL, ag.SELECAO_HERDADO)
    assert ag.selecao_exclusiva([C, C]) == (C, ag.SELECAO_UNANIME)
    assert ag.selecao_exclusiva([NC, NC]) == (NC, ag.SELECAO_UNANIME)
    assert ag.selecao_exclusiva([C, NC]) == (Estado.NAO_AVALIAVEL,
                                             ag.SELECAO_DISCORDANTE)
    assert ag.selecao_exclusiva([C, None]) == (Estado.NAO_AVALIAVEL,
                                               ag.SELECAO_PENDENTE)
    assert ag.selecao_exclusiva([]) == (Estado.NAO_AVALIAVEL,
                                        ag.SELECAO_SEM_CANDIDATO)


def test_k_da_selecao_exclusiva_e_um_ramo():
    assert ag.k_de(ag.MODO_SELECAO_EXCLUSIVA, 2) == 1


def test_discordancia_e_indecisao_na_selecao_exclusiva_e_reprovacao_em_todos():
    """O teste que prende o ADR-026 contra o modo `todos`.

    Dois ramos candidatos (a zona não seleciona nenhum — cláusula em vocabulário
    de 2005, DN-08), um conforme e um não conforme sob o próprio limite. Em
    `todos`, `k = 2`, `n_conf = 1`, `n_pot = 1 < k` → o pai REPROVA um projeto
    que a norma talvez aprove. Em `selecao_exclusiva` o mesmo par é INDECISÃO
    declarada, remetida ao parecer.
    """
    # Para o contraste ser exato, os dois pais recebem os MESMOS resultados,
    # com o estado emitido igual ao veredito (é o que `todos` consegue ver).
    ctx = _ctx_resultados(**{
        "TST-EXC.1": _ramo("TST-EXC.1", Estado.CONFORME, estado=Estado.CONFORME),
        "TST-EXC.2": _ramo("TST-EXC.2", Estado.NAO_CONFORME,
                           estado=Estado.NAO_CONFORME),
    })

    todos = _PaiTodos().checar(ctx)
    assert todos.estado is Estado.NAO_CONFORME, "é o erro que a DN-08 proíbe"

    exclusivo = _PaiExclusivo().checar(ctx)
    assert exclusivo.estado is Estado.NAO_AVALIAVEL
    assert exclusivo.detalhe[motivos.CHAVE] == motivos.ANALISE_HUMANA_DOCUMENTAL
    assert exclusivo.detalhe["selecao"] == ag.SELECAO_DISCORDANTE
    assert exclusivo.detalhe["candidatos"] == ["TST-EXC.1", "TST-EXC.2"]
    assert "não é reprovação" in exclusivo.mensagem


def test_unanimidade_conclui_mesmo_sem_saber_o_ramo():
    """Os ramos emitem NÃO AVALIÁVEL (aplicabilidade indeterminada), mas os
    vereditos sob o próprio limite concordam: o pai conclui — é o invariante à
    leitura da DN-08 tendo onde morar."""
    ctx = _ctx_resultados(**{
        "TST-EXC.1": _ramo("TST-EXC.1", Estado.CONFORME),
        "TST-EXC.2": _ramo("TST-EXC.2", Estado.CONFORME),
    })
    r = _PaiExclusivo().checar(ctx)
    assert r.estado is Estado.CONFORME
    assert r.detalhe["selecao"] == ag.SELECAO_UNANIME
    assert "sob qualquer leitura" in r.mensagem

    ctx = _ctx_resultados(**{
        "TST-EXC.1": _ramo("TST-EXC.1", Estado.NAO_CONFORME),
        "TST-EXC.2": _ramo("TST-EXC.2", Estado.NAO_CONFORME),
    })
    r = _PaiExclusivo().checar(ctx)
    assert r.estado is Estado.NAO_CONFORME
    assert r.detalhe["selecao"] == ag.SELECAO_UNANIME


def test_um_so_candidato_o_pai_herda_e_o_inaplicavel_fica_fora():
    ctx = _ctx_resultados(**{
        "TST-EXC.1": _ramo("TST-EXC.1", Estado.NAO_CONFORME, ag.RAMO_APLICAVEL),
        "TST-EXC.2": _ramo("TST-EXC.2", Estado.CONFORME, ag.RAMO_INAPLICAVEL,
                           motivo=motivos.NAO_APLICAVEL),
    })
    r = _PaiExclusivo().checar(ctx)
    assert r.estado is Estado.NAO_CONFORME
    assert r.detalhe["selecao"] == ag.SELECAO_HERDADO
    assert r.detalhe["candidatos"] == ["TST-EXC.1"]
    por_id = {m["id"]: m for m in r.detalhe["membros"]}
    assert por_id["TST-EXC.2"]["conta_para"] == ag.CONTA_NAO_CANDIDATO
    # O inaplicável NÃO influencia: mesmo "conforme" sob o próprio limite,
    # o pai herdou o não conforme do único candidato.


def test_candidato_sem_veredito_proprio_herda_a_causa_dele():
    """Ramo candidato que não concluiu (p. ex. propriedade ausente): o pai não
    conclui e aponta a causa do ramo, como no modo por limites."""
    ctx = _ctx_resultados(**{
        "TST-EXC.1": _ramo("TST-EXC.1", None, motivo=motivos.INFORMACAO_AUSENTE),
        "TST-EXC.2": _ramo("TST-EXC.2", Estado.CONFORME),
    })
    r = _PaiExclusivo().checar(ctx)
    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe["selecao"] == ag.SELECAO_PENDENTE
    assert r.detalhe[motivos.CHAVE] == motivos.INFORMACAO_AUSENTE


def test_ramo_nao_executado_e_candidato_de_veredito_desconhecido():
    ctx = _ctx_resultados(**{
        "TST-EXC.1": _ramo("TST-EXC.1", Estado.CONFORME),
    })
    r = _PaiExclusivo().checar(ctx)
    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.MEMBRO_NAO_EXECUTADO


def test_nenhum_candidato_e_nao_aplicavel():
    ctx = _ctx_resultados(**{
        "TST-EXC.1": _ramo("TST-EXC.1", Estado.CONFORME, ag.RAMO_INAPLICAVEL),
        "TST-EXC.2": _ramo("TST-EXC.2", Estado.CONFORME, ag.RAMO_INAPLICAVEL),
    })
    r = _PaiExclusivo().checar(ctx)
    assert r.estado is Estado.NAO_AVALIAVEL
    assert r.detalhe[motivos.CHAVE] == motivos.NAO_APLICAVEL
    assert r.detalhe["selecao"] == ag.SELECAO_SEM_CANDIDATO


def test_selecao_exclusiva_mantem_o_contrato_do_relatorio():
    """`tipo`/`membros` no detalhe: é por eles que o relatório tira os ramos do
    denominador e conta só o pai (ADR-015/026)."""
    ctx = _ctx_resultados(**{
        "TST-EXC.1": _ramo("TST-EXC.1", Estado.CONFORME),
        "TST-EXC.2": _ramo("TST-EXC.2", Estado.CONFORME),
    })
    r = _PaiExclusivo().checar(ctx)
    assert r.detalhe["tipo"] == ag.TIPO_DIAGNOSTICO
    assert r.detalhe["modo"] == ag.MODO_SELECAO_EXCLUSIVA
    assert [m["id"] for m in r.detalhe["membros"]] == ["TST-EXC.1", "TST-EXC.2"]
    assert all(m["rotulo_aplicabilidade"] for m in r.detalhe["membros"])
