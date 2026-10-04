"""A escada de cenários do Estrela I — um teste de integração por id.

O que este arquivo prende é o **desenho de avaliação** da escada: para cada
cenário da lista fechada (``config/cenarios_estrela_i.yaml``), o resultado que a família dele impõe —
e nada além disso, porque o veredito real das variantes é o do projeto, não
uma escolha do pesquisador ("gabarito não escolhido"):

* **E0** — os vereditos da ficha do caso base, exatos: estado e motivo dos 14
  requisitos, e os números que os decidem (LoGeoRef 40; 300 UH > 100; a
  escola mais próxima a 1.384 m em linha reta > 1.000 m).
* **E1** — o EMP-001 conclui **conforme**; os outros 13 continuam os do E0
  (o degrau troca o veredito, não o estado).
* **E2 / E3** — os requisitos do degrau **concluem**, e os degraus anteriores
  seguem contidos. O veredito também está
  **fixado** (``GABARITO_E2``/``GABARITO_E3``): é o resultado real do projeto,
  conferido com a procedência da segunda rodada. Não foi escolhido pelo
  pesquisador, mas vale como rede de regressão: mudou, é achado. Com os
  ambientes fantasma fora da população (ADR-031), o EDI-004 conta 5 salas e
  8 banheiros, e o EDI-008 conclui sobre as salas reais (4,735 m). Uma exceção, que
  é do motor e não do pesquisador: ``EDI-002`` depende de ``EDI-004`` (área
  útil só se mede com o programa completo), então quando o próprio projeto
  deixa o ``EDI-004`` **NC** o ``EDI-002`` sai ``NA(prerequisito_falho)`` — e
  é isso que o Estrela I faz (os Rooms do RVT da construtora têm
  salas faltando e ambientes fantasma). O gabarito aceita esse par, e só
  ele. Segunda exceção, da mesma natureza: a cobertura do projeto é
  um sistema de painéis ("Vidraça inclinada") que o Revit exporta **sem
  material**, e o desenvolvedor decidiu não alterar elementos do modelo entregue —
  só informação e exportação. A etapa de exceções da Portaria (DN-01) então
  devolve o ``EDI-024`` ``NA(informacao_ausente)`` com TODOS os coverings da
  população em ``material_nao_identificavel``; o gabarito aceita esse caso,
  e só ele (população vazia continua falha). No E3 — o teto — ficam não
  avaliáveis ENQ-010/011 (DN-04) e, nesses casos, EDI-002 e EDI-024:
  **10 de 14** concluídos no Estrela I (12 se o programa e o material
  fechassem).
* **D1–D3** — o motivo/estado que a lista de cenários declara para cada degradação, e só
  ele.
* **V1–V5** — veredito **idêntico ao do pai** pelo critério de "veredito mantido":
  estado e motivo iguais nos 14 requisitos; nas variantes de mesma geometria
  (``numeros_comparaveis``), também os ``valor_encontrado``, com tolerância
  relativa 1e-9.

Cada cenário roda pelo MESMO instrumento do desenvolvedor — ``scripts/rodar_cenario.py``,
carregado pelo caminho como ``test_inspetores.py`` faz —, sobre o
``artefatos/empreendimento.json`` corrente, sem ORS, gravando numa pasta
temporária (a saída em ``artefatos/cenarios/`` não é tocada).
Um cenário cujo arquivo ainda não existe em ``entradas/ifc/estrela_i/`` (ou
``entradas/gis/estrela_i/``) é **pulado com o motivo** — a frase é a do
próprio comando —, e o mesmo vale para o pai de uma variação e para um
``empreendimento.json`` que não esteja declarado conforme a ficha. O E0 é
achado como os outros, por ``E0_*.ifc`` (sem via especial).

Marcador ``integracao``: abre IFC de verdade com IfcOpenShell.
"""

from __future__ import annotations

import importlib.util
import os
import sys

import pytest

from tests.conftest import RAIZ

pytestmark = pytest.mark.integracao

pytest.importorskip("ifcopenshell")


def _carregar(nome: str):
    caminho = os.path.join(RAIZ, "scripts", f"{nome}.py")
    spec = importlib.util.spec_from_file_location(nome, caminho)
    assert spec and spec.loader, caminho
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome] = modulo
    spec.loader.exec_module(modulo)
    return modulo


rc = _carregar("rodar_cenario")
CONFIG = rc.carregar_config()
CENARIOS = rc.cenarios(CONFIG)

# Os ids da escada que se produzem por ARQUIVO (E0–E3, D1–D3, V1–V5). D4 é a
# execução sem rede — condição em que TODOS os cenários já rodam aqui — e
# D5/DD1/DD2 só existem na interface.
IDS = [c["id"] for c in CONFIG["cenarios"]
       if c["arquivo"] in ("modelo", "terreno") or c.get("csv")]

CONFORME, NAO_CONFORME, NAO_AVALIAVEL = "conforme", "nao_conforme", "nao_avaliavel"
PROGRAMA = ("EDI-004", "EDI-004.1", "EDI-002", "EDI-007", "EDI-008", "EDI-009", "EDI-011")
ABSORTANCIA = ("EDI-019", "EDI-024")

# O piso: a ficha do caso base, sem rede.
# ENQ-010/011 saem por ``agregacao_indecisa`` porque, sem provedor, as
# alternativas A ficam em ``metrica_insuficiente`` e as B em
# ``analise_humana_documental`` — causas diferentes, e o pai não herda uma só.
# Com ORS (a rodada oficial) as A reprovam e o pai herda ``analise_humana_
# documental`` da B; o ESTADO é o mesmo nos dois casos (ADR-013, DN-04).
GABARITO_E0 = {
    "EMP-001": (NAO_CONFORME, ""),
    "EDI-004": (NAO_AVALIAVEL, "informacao_ausente"),
    "EDI-004.1": (NAO_AVALIAVEL, "informacao_ausente"),
    "EDI-002": (NAO_AVALIAVEL, "prerequisito_falho"),
    "EDI-007": (NAO_AVALIAVEL, "informacao_ausente"),
    "EDI-008": (NAO_AVALIAVEL, "informacao_ausente"),
    "EDI-009": (NAO_AVALIAVEL, "informacao_ausente"),
    "EDI-011": (NAO_AVALIAVEL, "informacao_ausente"),
    "EDI-019": (NAO_AVALIAVEL, "informacao_ausente"),
    "EDI-024": (NAO_AVALIAVEL, "informacao_ausente"),
    "EMP-025": (NAO_CONFORME, ""),
    "ENQ-009": (NAO_CONFORME, ""),
    "ENQ-010": (NAO_AVALIAVEL, "agregacao_indecisa"),
    "ENQ-011": (NAO_AVALIAVEL, "agregacao_indecisa"),
}


# E2 e E3 fixados com o resultado real (sem rede). Cada degrau contém o anterior, e só as linhas que ele toca mudam.
GABARITO_E2 = {
    **GABARITO_E0,
    "EMP-001": (CONFORME, ""),
    "EDI-004": (NAO_CONFORME, ""),            # Sala: 5 para 8 (programa do projeto)
    "EDI-004.1": (CONFORME, ""),
    "EDI-002": (NAO_AVALIAVEL, "prerequisito_falho"),
    "EDI-007": (CONFORME, ""),
    "EDI-008": (CONFORME, ""),                # salas reais, 4,735 m (ADR-031)
    "EDI-009": (NAO_CONFORME, ""),            # BWC real, 1,485 m < 1,50 m
    "EDI-011": (CONFORME, ""),
}
GABARITO_E3 = {
    **GABARITO_E2,
    "EDI-019": (CONFORME, ""),                # α = 0,35 nas paredes, zona 2R
    "EDI-024": (NAO_AVALIAVEL, "informacao_ausente"),   # cobertura sem material
}
FANTASMAS_DO_ESTRELA_I = 10     # 8 no pavimento tipo, 2 no térreo


# ---------------------------------------------------------------------------
# Execução (uma vez por cenário, por módulo)
# ---------------------------------------------------------------------------

def _fora_da_ficha() -> str:
    """Por que o ``empreendimento.json`` corrente não é o caso base — ``""``
    quando é. Mesma conferência do roteiro da linha de base."""
    from core.dominio.vocabulario import declaracoes as dec
    from core.infra.persistencia import empreendimento_json

    emp = empreendimento_json.ler(os.path.join(RAIZ, "artefatos"))
    if emp is None:
        return "artefatos/empreendimento.json não existe (declare o caso base em 2.1.1)"
    problemas = []
    t = emp.terreno
    if t is None or t.origem != "csv" or t.nivel != "poligonal":
        problemas.append("terreno não é a poligonal do memorial (modo CSV)")
    if emp.declaracoes.get(dec.ARRANJO) != "condominio":
        problemas.append("arranjo não é condomínio")
    if emp.unidades_previstas != 300:
        problemas.append(f"unidades_previstas = {emp.unidades_previstas} (ficha: 300)")
    tipos = [(u.unidades, u.tipologia) for u in emp.unidades_tipo]
    if tipos != [(300, "apartamento")]:
        problemas.append(f"unidades_tipo = {tipos} (ficha: 1 × apartamento × 300)")
    return ("empreendimento.json fora da ficha do caso base: " + "; ".join(problemas)
            if problemas else "")


@pytest.fixture(scope="module")
def cenarios_rodados(tmp_path_factory):
    """``{id: (relatórios, perfil)}``, preenchido sob demanda e uma vez só."""
    cache: dict[str, tuple[dict, list[dict]]] = {}
    pasta = tmp_path_factory.mktemp("cenarios")

    def rodar(id_cenario: str):
        if id_cenario not in cache:
            motivo = rc.faltando(CONFIG, id_cenario)
            if motivo:
                pytest.skip(motivo)
            motivo = _fora_da_ficha()
            if motivo:
                pytest.skip(motivo)
            relatorios = rc.rodar_cenario(CONFIG, id_cenario, ors=False,
                                          saida=str(pasta / id_cenario))
            cache[id_cenario] = (relatorios, rc.perfil(CONFIG, relatorios))
        return cache[id_cenario]

    return rodar


def _vereditos(perfil: list[dict]) -> dict[str, tuple[str, str]]:
    return {l["requisito"]: (l["estado"], l["motivo"]) for l in perfil}


def _linha(relatorios: dict, chave: str, rid: str) -> dict:
    return next(r for r in relatorios[chave]["por_requisito"] if r["requisito"] == rid)


def _concluem(vereditos: dict, ids) -> None:
    """Cada requisito conclui (C ou NC). Única tolerância, do desenho das
    regras: ``EDI-002`` pode sair ``NA(prerequisito_falho)`` **se e somente
    se** ``EDI-004`` concluiu NC — o gate do programa (``depende_de``)
    segurou a área útil. Qualquer outro NA é falha."""
    for rid in ids:
        estado, motivo = vereditos[rid]
        if (rid == "EDI-002" and (estado, motivo) == (NAO_AVALIAVEL, "prerequisito_falho")
                and vereditos.get("EDI-004", ("", ""))[0] == NAO_CONFORME):
            continue
        assert estado in (CONFORME, NAO_CONFORME), (rid, vereditos[rid])


# ---------------------------------------------------------------------------
# Um teste por id — o gabarito é o da família
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("id_cenario", IDS)
def test_cenario(id_cenario, cenarios_rodados):
    relatorios, perfil = cenarios_rodados(id_cenario)
    vereditos = _vereditos(perfil)
    assert list(vereditos) == list(GABARITO_E0), "os 14 requisitos do §15.2, na ordem"
    familia = CENARIOS[id_cenario]["familia"]
    if familia == "enriquecimento":
        _conferir_enriquecimento(id_cenario, relatorios, vereditos)
    elif familia == "degradacao":
        _conferir_degradacao(id_cenario, relatorios, vereditos)
    else:
        _conferir_variacao(id_cenario, perfil, cenarios_rodados)


def _conferir_enriquecimento(id_cenario, relatorios, vereditos):
    if id_cenario == "E0":
        assert vereditos == GABARITO_E0
        # Os números que decidem os três concluídos, como a ficha os registra.
        emp001 = _linha(relatorios, "georref", "EMP-001")
        assert emp001["detalhe"]["nivel"] == 40
        assert set(emp001["detalhe"]["lacunas"]) == {"IfcProjectedCRS", "IfcMapConversion"}
        emp0251 = _linha(relatorios, "qualificacao", "EMP-025.1")
        assert (emp0251["valor_encontrado"], emp0251["valor_esperado"]) == (300, 100)
        enq009 = _linha(relatorios, "enquadramento", "ENQ-009")
        assert rc.numeros_iguais(enq009["valor_encontrado"], 1383.7455186776779)
        assert enq009["valor_encontrado"] > 1000
        # Diagnóstico de extrapolação marcado: 300 UH a partir de geometria de 8.
        diag = {d["chave"]: d for d in relatorios["programa"]["meta"]["diagnosticos"]}
        assert diag["extrapolacao"]["marcado"] is True
        assert diag["extrapolacao"]["valores"] == {"unidades_do_dono": 300,
                                                   "unidades_representadas": 8}
        assert relatorios["programa"]["resumo"]["nao_avaliavel"] == 7
        return

    # Cada degrau contém o anterior: o que ele não toca segue como no E0.
    esperado = dict(GABARITO_E0)
    assert vereditos["EMP-001"][0] == CONFORME, "E1: georreferenciamento correto"
    del esperado["EMP-001"]
    if id_cenario in ("E2", "E3"):
        _concluem(vereditos, PROGRAMA)
        for rid in PROGRAMA:
            del esperado[rid]
    if id_cenario == "E3":
        _concluem(vereditos, ("EDI-019",))
        if vereditos["EDI-024"][0] == NAO_AVALIAVEL:
            _so_por_material(relatorios, vereditos)
        for rid in ABSORTANCIA:
            del esperado[rid]
        concluidos = [rid for rid, (estado, _) in vereditos.items()
                      if estado != NAO_AVALIAVEL]
        fora = 2 + sum(1 for rid in ("EDI-002", "EDI-024")
                       if vereditos[rid][0] == NAO_AVALIAVEL)
        assert len(concluidos) == 14 - fora, \
            ("o teto: só ENQ-010/011 (ADR-014), o EDI-002 com EDI-004 NC e o "
             "EDI-024 sem material da cobertura ficam de fora")
    for rid, veredito in esperado.items():
        assert vereditos[rid] == veredito, (id_cenario, rid)
    if id_cenario in ("E2", "E3"):
        gabarito = GABARITO_E2 if id_cenario == "E2" else GABARITO_E3
        assert vereditos == gabarito, id_cenario
        _conferir_triagem(relatorios)


def _conferir_triagem(relatorios: dict) -> None:
    """O E2 real como integração do ADR-031: os dez fantasmas saem da
    população de toda regra do programa, e as contagens e medidas passam a
    ser as do projeto."""
    programa = {rid: _linha(relatorios, "programa", rid)
                for rid in ("EDI-004", "EDI-007", "EDI-008", "EDI-009", "EDI-011")}
    for rid, linha in programa.items():
        fora = linha["detalhe"]["fora_da_populacao"]
        assert len(fora) == FANTASMAS_DO_ESTRELA_I, (rid, len(fora))
        assert all(len(a["sinais"]) >= 2 for a in fora), rid
    categorias = {c["chave"]: c["qtd"] for c in programa["EDI-004"]["detalhe"]["categorias"]}
    assert (categorias["sala"], categorias["banheiro"]) == (5, 8), categorias
    salas = programa["EDI-008"]["detalhe"]["ambientes"]
    assert len(salas) == 5 and min(a["largura_m"] for a in salas) == 4.735
    banheiros = programa["EDI-009"]["detalhe"]["ambientes"]
    assert len(banheiros) == 8 and max(a["largura_m"] for a in banheiros) == 1.485


def _so_por_material(relatorios: dict, vereditos: dict) -> None:
    """``EDI-024`` não avaliável só é aceito no teto quando a população dos
    ramos EXISTE e todo covering dela caiu em ``material_nao_identificavel``
    (a cobertura do projeto não carrega material). População vazia,
    ou qualquer outra situação, é falha do degrau."""
    assert vereditos["EDI-024"] == (NAO_AVALIAVEL, "informacao_ausente")
    ramo = _linha(relatorios, "bim_gis", "EDI-024.1")["detalhe"]
    coverings = ramo.get("coverings") or []
    assert coverings, "EDI-024: população vazia — o degrau não entregou o ROOFING"
    assert all(c["situacao"] == "material_nao_identificavel" for c in coverings), \
        [(c["nome"], c["situacao"]) for c in coverings]


def _conferir_degradacao(id_cenario, relatorios, vereditos):
    emp001 = _linha(relatorios, "georref", "EMP-001")
    if id_cenario == "D1":
        # Schema aquém: a premissa limita o que se conclui, não o que se abre.
        assert vereditos["EMP-001"][0] == NAO_CONFORME
        assert any("requer IFC4+" in lacuna for lacuna in emp001["detalhe"]["lacunas"])
        assert emp001["detalhe"]["schema"].upper().startswith("IFC2X3")
        _concluem(vereditos, PROGRAMA)
    elif id_cenario == "D2":
        # Nível 50 e ainda assim reprovado: o confronto municipal é o que pega.
        assert vereditos["EMP-001"][0] == NAO_CONFORME
        assert emp001["detalhe"]["nivel"] == 50
        assert emp001["detalhe"]["localizacao_declarada"]["dentro"] is False
    elif id_cenario == "D3":
        # Queda PARCIAL do catálogo: kitchen/living/balcon casam; bedroom e
        # bathroom, não. EDI-009 cai sem banheiro; EDI-004 cai (os dormitórios
        # e o banheiro faltam ao programa); EDI-007/008/011 seguem.
        _concluem(vereditos, ("EDI-007", "EDI-008", "EDI-011"))
        assert vereditos["EDI-009"] == (NAO_AVALIAVEL, "informacao_ausente")
        assert vereditos["EDI-004"][0] != CONFORME
        # Os dez fantasmas renomeados também estão fora: o BWC da origem não
        # pode mais fazer o EDI-009 concluir (ADR-031).
        fora = _linha(relatorios, "programa", "EDI-004")["detalhe"]["fora_da_populacao"]
        assert len(fora) == FANTASMAS_DO_ESTRELA_I
    else:  # pragma: no cover — a lista fechada não tem outra degradação por arquivo
        pytest.fail(f"degradação sem gabarito: {id_cenario}")


def _conferir_variacao(id_cenario, perfil, cenarios_rodados):
    cenario = CENARIOS[id_cenario]
    pai = cenario["pai"]
    if rc.faltando(CONFIG, pai):
        pytest.skip(f"o pai {pai} de {id_cenario} não pode rodar: "
                    + rc.faltando(CONFIG, pai))
    _, perfil_pai = cenarios_rodados(pai)
    base = {l["requisito"]: l for l in perfil_pai}
    divergentes = [f"{l['requisito']}: {rc.celula(base[l['requisito']])} → {rc.celula(l)}"
                   for l in perfil if not rc.mesmo_veredito(base[l["requisito"]], l)]
    assert not divergentes, f"{id_cenario} × {pai} — veredito mudou: {divergentes}"
    if cenario.get("numeros_comparaveis"):
        numeros = [f"{l['requisito']}: {base[l['requisito']]['valor_encontrado']!r} → "
                   f"{l['valor_encontrado']!r}"
                   for l in perfil
                   if not rc.numeros_iguais(base[l["requisito"]]["valor_encontrado"],
                                            l["valor_encontrado"])]
        assert not numeros, f"{id_cenario} × {pai} — números mudaram: {numeros}"
