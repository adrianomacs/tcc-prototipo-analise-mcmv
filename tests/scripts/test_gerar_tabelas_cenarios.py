"""As três tabelas e a Figura 4 de ``scripts/gerar_tabelas_cenarios.py``, sobre
relatórios forjados — sem IFC, sem pipeline.

O que se prende é a FORMA das tabelas de resultado:
Tabela 3 com os dois eixos no rodapé (cobertura e conformidade), Tabela 4 só
com o que mudou contra o teto, Tabela 5 com "veredito mantido" (e os números, nas variantes de mesma
geometria), e o gerador rodando com os cenários que existirem — coluna que
falta some, nada é inventado.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import os
import sys

import pytest

from tests.conftest import RAIZ


def _carregar(nome: str):
    caminho = os.path.join(RAIZ, "scripts", f"{nome}.py")
    spec = importlib.util.spec_from_file_location(nome, caminho)
    assert spec and spec.loader, caminho
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome] = modulo
    spec.loader.exec_module(modulo)
    return modulo


gt = _carregar("gerar_tabelas_cenarios")
rc = gt.rc

# Um relatório mínimo por checagem: só o que ``perfil`` lê.
REQUISITOS = {
    "georref": ["EMP-001"],
    "programa": ["EDI-004", "EDI-004.1", "EDI-002", "EDI-007", "EDI-008",
                 "EDI-009", "EDI-011"],
    "bim_gis": ["EDI-019", "EDI-024"],
    "qualificacao": ["EMP-025"],
    "enquadramento": ["ENQ-009", "ENQ-010", "ENQ-011"],
}


def _relatorio(ids, vereditos, numeros=None):
    linhas = []
    for rid in ids:
        estado, motivo = vereditos.get(rid, ("nao_avaliavel", "informacao_ausente"))
        linhas.append({"requisito": rid, "estado": estado,
                       "detalhe": ({"motivo_nao_avaliavel": motivo} if motivo else {}),
                       "valor_encontrado": (numeros or {}).get(rid), "mensagem": ""})
    return {"resumo": {"normativo": {"ids": list(ids)}}, "por_requisito": linhas}


def _gravar_cenario(config, id_cenario, vereditos, numeros=None):
    pasta = os.path.join(config["pastas"]["saida"], id_cenario)
    os.makedirs(pasta, exist_ok=True)
    for chave, ids in REQUISITOS.items():
        with open(os.path.join(pasta, f"{chave}.json"), "w", encoding="utf-8") as f:
            json.dump(_relatorio(ids, vereditos, numeros), f)


PISO = {"EMP-001": ("nao_conforme", ""), "EMP-025": ("nao_conforme", ""),
        "ENQ-009": ("nao_conforme", ""),
        "ENQ-010": ("nao_avaliavel", "agregacao_indecisa"),
        "ENQ-011": ("nao_avaliavel", "agregacao_indecisa"),
        "EDI-002": ("nao_avaliavel", "prerequisito_falho")}
TETO = {**PISO, "EMP-001": ("conforme", ""),
        **{rid: ("conforme", "") for rid in REQUISITOS["programa"] + REQUISITOS["bim_gis"]}}


@pytest.fixture
def config(tmp_path):
    cfg = rc.carregar_config()
    cfg["pastas"] = {"ifc": str(tmp_path / "ifc"), "gis": str(tmp_path / "gis"),
                     "saida": str(tmp_path / "saida")}
    os.makedirs(cfg["pastas"]["ifc"])
    os.makedirs(cfg["pastas"]["gis"])
    return cfg


def _ler_csv(pasta, nome):
    with open(os.path.join(pasta, f"{nome}.csv"), encoding="utf-8", newline="") as f:
        return list(csv.reader(f, delimiter=";"))


def test_so_com_o_e0_as_tres_tabelas_saem_e_dizem_o_que_falta(config, tmp_path):
    _gravar_cenario(config, "E0", PISO)
    pasta = str(tmp_path / "tabelas")
    perfis = gt.gerar(config, pasta)
    assert list(perfis) == ["E0"]

    t3 = _ler_csv(pasta, "tabela_3")
    assert t3[0] == ["checagem", "requisito", "E0"]
    assert len(t3) == 1 + 14 + 2
    assert t3[-2] == ["cobertura", "", "3/14"]
    assert t3[-1] == ["conformidade", "", "0/3"]
    assert t3[2] == ["Programa de necessidades", "EDI-004", "NA(informacao_ausente)"]

    # Sem o teto, a Tabela 4 sai vazia com a razão; a 5 lista as cinco
    # variações como "não produzida"; a Figura 4 fica sem a linha do teto.
    assert _ler_csv(pasta, "tabela_4") == []
    with open(os.path.join(pasta, "tabela_4.md"), encoding="utf-8") as f:
        assert "E3" in f.read()
    t5 = _ler_csv(pasta, "tabela_5")
    assert [l[0] for l in t5[1:]] == ["V1", "V2", "V3", "V4", "V5"]   # a variação do Bloco A não faz parte da lista
    assert {l[3] for l in t5[1:]} == {"não produzida"}
    f4 = _ler_csv(pasta, "figura_4")
    assert f4[1] == ["E0", "0", "3", "11", "3", "14", "", "2"]


def test_tabela_4_so_traz_as_celulas_que_mudaram_contra_o_teto(config, tmp_path):
    _gravar_cenario(config, "E0", PISO)
    _gravar_cenario(config, "E3", TETO)
    d3 = {**TETO, "EDI-009": ("nao_avaliavel", "informacao_ausente"),
          "EDI-004": ("nao_conforme", "")}
    _gravar_cenario(config, "D3", d3)
    pasta = str(tmp_path / "tabelas")
    gt.gerar(config, pasta)

    t4 = _ler_csv(pasta, "tabela_4")
    assert t4[0] == ["checagem", "requisito", "E3 (teto)", "D3"]
    assert [l[1:] for l in t4[1:]] == [
        ["EDI-004", "C", "NC"],
        ["EDI-009", "C", "NA(informacao_ausente)"]]

    f4 = _ler_csv(pasta, "figura_4")
    assert [l[0] for l in f4[1:]] == ["E0", "E3"]
    assert f4[2] == ["E3", "10", "2", "2", "12", "14", "12", "2"]
    assert f4[1][6] == "12"       # a linha do teto acompanha todos os degraus


def test_tabela_5_veredito_mantido_e_numeros_nas_variantes_de_mesma_geometria(
        config, tmp_path):
    numeros = {"ENQ-009": 1383.7455186776779, "EMP-025": 0}
    _gravar_cenario(config, "E0", PISO, numeros)
    _gravar_cenario(config, "E3", TETO, numeros)
    # V5 (pai E0, números não comparáveis): mesmo veredito, distância diferente.
    _gravar_cenario(config, "V5", PISO, {**numeros, "ENQ-009": 1200.0})
    # V2 (pai E3, mesma geometria): mesmo veredito, 1 ULP de diferença — igual.
    _gravar_cenario(config, "V2", TETO, {**numeros, "ENQ-009": 1383.7455186776777})
    # V4 também serve ao caso "veredito que mudou" desde que a variação do Bloco A foi riscada:
    # aqui o V4 muda um número E um veredito, e a Tabela 5 tem de dizer os dois.
    _gravar_cenario(config, "V4", {**TETO, "EDI-011": ("nao_conforme", "")},
                    {**numeros, "ENQ-009": 1400.0})
    # V1 (pai E2) gravada sem o pai: não há com que comparar.
    _gravar_cenario(config, "V1", TETO, numeros)
    pasta = str(tmp_path / "tabelas")
    gt.gerar(config, pasta)

    t5 = {l[0]: l for l in _ler_csv(pasta, "tabela_5")[1:]}
    assert t5["V5"][3:5] == ["comparada", "sim"]
    assert t5["V2"][3:5] == ["comparada", "sim"]
    assert t5["V4"][3:5] == ["comparada", "não"]
    assert "números: ENQ-009" in t5["V4"][5]
    assert "EDI-011: C → NC" in t5["V4"][5]
    assert t5["V1"][3] == "sem o pai"        # E2 não foi gravado
    assert t5["V3"][3] == "não produzida"
