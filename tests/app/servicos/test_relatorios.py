"""ADR-001 — `app.servicos.relatorios`:
leitura por checagem, filtro pelo empreendimento corrente e consolidação.

Sem `AppTest`: nenhuma das funções testadas aqui desenha nada (são a parte
de `servicos/`, sem Streamlit) — mais rápido e mais preciso testar direto,
como `test_fase3_regras.py` já faz para `app.componentes.resultado`.
"""

from __future__ import annotations

import ast
import json
import os

import pytest

pytest.importorskip("streamlit", reason="sem Streamlit não há o que testar aqui")

from app.servicos import empreendimento as emp_servico
from app.servicos import grupos, relatorios
from tests.conftest import RAIZ


def _relatorio(referencia: dict, *, total=2, avaliados=2, conforme=1,
              nao_conforme=1, nao_avaliavel=0) -> dict:
    return {
        "meta": {"empreendimento": referencia},
        "resumo": {"normativo": {
            "total": total, "avaliados": avaliados, "conforme": conforme,
            "nao_conforme": nao_conforme, "nao_avaliavel": nao_avaliavel,
        }},
    }


@pytest.fixture
def pasta_relatorios(tmp_path, monkeypatch):
    pasta = tmp_path / "relatorios"
    monkeypatch.setattr(relatorios, "PASTA_RELATORIOS", str(pasta))
    return pasta


def _gravar(pasta, chave, relatorio):
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / f"{chave}.json").write_text(json.dumps(relatorio), encoding="utf-8")


# ---------------------------------------------------------------------------
# caminho / ler
# ---------------------------------------------------------------------------

def test_caminho_usa_a_pasta_de_relatorios_e_a_chave(pasta_relatorios):
    assert relatorios.caminho("enquadramento") == str(pasta_relatorios / "enquadramento.json")


def test_ler_devolve_none_quando_o_arquivo_nao_existe(pasta_relatorios):
    assert relatorios.ler("georref") is None


def test_ler_devolve_o_relatorio_gravado(pasta_relatorios):
    ref = {"id": "abc123", "versao": 1}
    _gravar(pasta_relatorios, "programa", _relatorio(ref))
    assert relatorios.ler("programa")["meta"]["empreendimento"] == ref


# ---------------------------------------------------------------------------
# relatorios_do_empreendimento_corrente — a regra de invalidação (§4.3)
# aplicada ao CONJUNTO, não por checagem.
# ---------------------------------------------------------------------------

def test_sem_nenhum_relatorio_gravado_devolve_vazio(pasta_relatorios, monkeypatch):
    monkeypatch.setattr(emp_servico, "referencia_atual", lambda: {"id": "x", "versao": 1})
    assert relatorios.relatorios_do_empreendimento_corrente() == {}


def test_so_entram_os_relatorios_do_empreendimento_e_versao_correntes(
        pasta_relatorios, monkeypatch):
    atual = {"id": "abc123", "versao": 3}
    monkeypatch.setattr(emp_servico, "referencia_atual", lambda: atual)

    _gravar(pasta_relatorios, "enquadramento", _relatorio(atual))              # bate
    _gravar(pasta_relatorios, "georref", _relatorio({"id": "abc123", "versao": 2}))  # versão velha
    _gravar(pasta_relatorios, "programa", _relatorio({"id": "outro", "versao": 3}))  # outro empreendimento

    encontrados = relatorios.relatorios_do_empreendimento_corrente()

    assert set(encontrados) == {"enquadramento"}


def test_relatorio_sem_meta_empreendimento_fica_de_fora(pasta_relatorios, monkeypatch):
    """Relatório antigo (sem `meta.empreendimento`) não quebra
    a comparação — só não entra no consolidado."""
    monkeypatch.setattr(emp_servico, "referencia_atual", lambda: {"id": "x", "versao": 1})
    _gravar(pasta_relatorios, "enquadramento", {"meta": {}, "resumo": {}})

    assert relatorios.relatorios_do_empreendimento_corrente() == {}


# ---------------------------------------------------------------------------
# consolidar — soma o bloco normativo de cada relatório.
# ---------------------------------------------------------------------------

def test_consolidar_de_dicionario_vazio_e_zerado():
    consolidado = relatorios.consolidar({})
    assert consolidado == {
        "total": 0, "avaliados": 0, "conforme": 0, "nao_conforme": 0,
        "nao_avaliavel": 0, "conformidade": None, "cobertura": 0.0,
    }


def test_consolidar_soma_os_totais_normativos_das_checagens():
    ref = {"id": "abc", "versao": 1}
    encontrados = {
        "enquadramento": _relatorio(ref, total=3, avaliados=3, conforme=2, nao_conforme=1),
        "georref": _relatorio(ref, total=1, avaliados=1, conforme=1, nao_conforme=0),
        "programa": _relatorio(ref, total=4, avaliados=2, conforme=1, nao_conforme=1,
                               nao_avaliavel=2),
    }

    consolidado = relatorios.consolidar(encontrados)

    assert consolidado["total"] == 8
    assert consolidado["avaliados"] == 6
    assert consolidado["conforme"] == 4
    assert consolidado["nao_conforme"] == 2
    assert consolidado["nao_avaliavel"] == 2
    assert consolidado["conformidade"] == round(4 / 6, 4)
    assert consolidado["cobertura"] == round(6 / 8, 4)


def test_consolidar_bate_com_a_soma_das_telas_individuais():
    """Consolidado = soma das
    telas — comparado aqui direto contra os blocos normativos de origem,
    sem passar pela UI."""
    ref = {"id": "abc", "versao": 1}
    encontrados = {
        "enquadramento": _relatorio(ref, total=5, avaliados=4, conforme=3, nao_conforme=1,
                                    nao_avaliavel=1),
        "programa": _relatorio(ref, total=2, avaliados=2, conforme=2, nao_conforme=0),
    }

    consolidado = relatorios.consolidar(encontrados)

    soma_total = sum(r["resumo"]["normativo"]["total"] for r in encontrados.values())
    soma_avaliados = sum(r["resumo"]["normativo"]["avaliados"] for r in encontrados.values())
    soma_conforme = sum(r["resumo"]["normativo"]["conforme"] for r in encontrados.values())

    assert consolidado["total"] == soma_total
    assert consolidado["avaliados"] == soma_avaliados
    assert consolidado["conforme"] == soma_conforme


# ---------------------------------------------------------------------------
# As cinco checagens que gravam relatório por chave entram na soma.
# A Qualificação (EMP-025) e a BIM + GIS (EDI-019/EDI-024) gravavam o seu
# relatório (ADR-001), mas `CHECAGENS` só listava três: 2.4.1/2.4.2 omitiam
# três dos 14 requisitos do recorte.
# ---------------------------------------------------------------------------

_PASTA_CHECAGENS = os.path.join(RAIZ, "app", "paginas", "checagens")


def _constantes_da_pagina(arquivo: str) -> dict[str, str]:
    """`CHAVE` e `GRUPO_ID` lidos do FONTE da página, sem importá-la — a
    página executa Streamlit no import. É a página que declara com que chave
    grava e que grupo roda; o teste não repete essa tabela à mão."""
    with open(os.path.join(_PASTA_CHECAGENS, arquivo), encoding="utf-8") as f:
        arvore = ast.parse(f.read())
    achadas: dict[str, str] = {}
    for no in arvore.body:
        if (isinstance(no, ast.Assign) and len(no.targets) == 1
                and isinstance(no.targets[0], ast.Name)
                and no.targets[0].id in ("CHAVE", "GRUPO_ID")
                and isinstance(no.value, ast.Constant)):
            achadas[no.targets[0].id] = no.value.value
    return achadas


def _grupo_por_chave() -> dict[str, str]:
    """`{chave do relatório: id do grupo}` de toda página de checagem que roda
    um grupo — `informacoes_gerais.py` tem `CHAVE` mas não `GRUPO_ID` (grava
    o `Empreendimento`, não um relatório) e fica de fora."""
    mapa: dict[str, str] = {}
    for arquivo in sorted(os.listdir(_PASTA_CHECAGENS)):
        if not arquivo.endswith(".py"):
            continue
        constantes = _constantes_da_pagina(arquivo)
        if "CHAVE" in constantes and "GRUPO_ID" in constantes:
            mapa[constantes["CHAVE"]] = constantes["GRUPO_ID"]
    return mapa


def test_checagens_inclui_toda_pagina_que_grava_relatorio_por_chave():
    """A checagem nova não pode voltar a gravar relatório sem entrar no
    consolidado — foi assim que uma checagem ficou de fora."""
    assert set(relatorios.CHECAGENS) == set(_grupo_por_chave())
    assert {"bim_gis", "qualificacao"} <= set(relatorios.CHECAGENS)


def test_os_grupos_das_checagens_somadas_sao_disjuntos():
    """A condição de `consolidar` (somar sem deduplicar) provada sobre o YAML
    de verdade: nenhum requisito em dois grupos somados."""
    ids_por_chave = {}
    for chave, gid in _grupo_por_chave().items():
        grupo = grupos.carregar_grupo(gid)
        assert grupo is not None, f"{chave}: grupo '{gid}' ausente do YAML"
        ids_por_chave[chave] = set(grupo.ids)

    chaves = sorted(ids_por_chave)
    for i, a in enumerate(chaves):
        for b in chaves[i + 1:]:
            comuns = ids_por_chave[a] & ids_por_chave[b]
            assert not comuns, f"{a} e {b} somariam {sorted(comuns)} duas vezes"

    assert {"EDI-019", "EDI-024"} <= ids_por_chave["bim_gis"]
    assert "EMP-025" in ids_por_chave["qualificacao"]


def _com_ids(referencia: dict, ids: list[str], **contagens) -> dict:
    relatorio = _relatorio(referencia, total=len(ids), **contagens)
    relatorio["resumo"]["normativo"]["ids"] = ids
    return relatorio


def test_relatorios_de_bim_gis_e_qualificacao_entram_no_consolidado(
        pasta_relatorios, monkeypatch):
    atual = {"id": "abc123", "versao": 7}
    monkeypatch.setattr(emp_servico, "referencia_atual", lambda: atual)
    _gravar(pasta_relatorios, "bim_gis", _relatorio(atual))
    _gravar(pasta_relatorios, "qualificacao", _relatorio(atual))

    assert set(relatorios.relatorios_do_empreendimento_corrente()) == {
        "bim_gis", "qualificacao"}


def test_consolidar_soma_as_cinco_checagens_sem_dupla_contagem():
    """Perfil do recorte do Estrela I (14 requisitos: 3 ENQ, EMP-025, EMP-001,
    7 do programa, EDI-019 e EDI-024). O total consolidado é o número de
    requisitos DISTINTOS — e EDI-019, EDI-024 e EMP-025 estão nele."""
    ref = {"id": "abc", "versao": 1}
    encontrados = {
        "enquadramento": _com_ids(ref, ["ENQ-009", "ENQ-010", "ENQ-011"],
                                  avaliados=1, conforme=0, nao_conforme=1,
                                  nao_avaliavel=2),
        "qualificacao": _com_ids(ref, ["EMP-025"], avaliados=1, conforme=0,
                                 nao_conforme=1),
        "georref": _com_ids(ref, ["EMP-001"], avaliados=1, conforme=1,
                            nao_conforme=0),
        "programa": _com_ids(ref, ["EDI-004", "EDI-004.1", "EDI-002", "EDI-007",
                                   "EDI-008", "EDI-009", "EDI-011"],
                             avaliados=7, conforme=5, nao_conforme=2),
        "bim_gis": _com_ids(ref, ["EDI-019", "EDI-024"], avaliados=2,
                            conforme=1, nao_conforme=1),
    }

    consolidado = relatorios.consolidar(encontrados)

    distintos = set().union(*(r["resumo"]["normativo"]["ids"]
                              for r in encontrados.values()))
    assert {"EDI-019", "EDI-024", "EMP-025"} <= distintos
    assert consolidado["total"] == len(distintos) == 14
    assert consolidado["avaliados"] == 12
    assert consolidado["conforme"] == 7
    assert consolidado["nao_conforme"] == 5
    assert consolidado["nao_avaliavel"] == 2
    assert consolidado["conformidade"] == round(7 / 12, 4)
    assert consolidado["cobertura"] == round(12 / 14, 4)
