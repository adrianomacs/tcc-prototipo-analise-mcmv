"""A lógica pura de ``scripts/rodar_cenario.py``: achar o arquivo de cada
cenário, herdar do pai o que ele não traz, e dizer POR QUE um cenário não pode
rodar — sem abrir IFC nenhum.

O que se prende aqui é o contrato de busca da ficha do caso base (seção
"Variantes"): ``<id>_*.ifc`` em ``entradas/ifc/estrela_i/`` e ``<id>_*.csv``
em ``entradas/gis/estrela_i/``; o modelo BIM e o terreno vêm do pai quando o
cenário não os traz; a frase de "falta" é a mesma que o teste de integração
usa no ``skip``. A execução de verdade (pipeline sobre o arquivo real) está em
``test_cenarios_estrela_i.py``, com o marcador ``integracao``.
"""

from __future__ import annotations

import importlib.util
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


rc = _carregar("rodar_cenario")


@pytest.fixture
def config(tmp_path):
    """A lista fechada real, com as pastas apontadas para um diretório vazio."""
    cfg = rc.carregar_config()
    cfg["pastas"] = {"ifc": str(tmp_path / "ifc"), "gis": str(tmp_path / "gis"),
                     "saida": str(tmp_path / "saida")}
    os.makedirs(cfg["pastas"]["ifc"])
    os.makedirs(cfg["pastas"]["gis"])
    return cfg


def _toca(caminho: str) -> None:
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("")


def test_lista_fechada_tem_os_ids_do_paragrafo_15():
    cfg = rc.carregar_config()
    ids = [c["id"] for c in cfg["cenarios"]]
    # A variação do Bloco A não faz parte da lista de cenários.
    assert ids == ["E0", "E1", "E2", "E3", "D1", "D2", "D3", "D4", "D5", "DD1", "DD2",
                   "V1", "V2", "V3", "V4", "V5"]
    assert all(c["pai"] is None if c["id"] == "E0" else c["pai"] in ids
               for c in cfg["cenarios"])


def test_e0_e_achado_pelo_prefixo_como_os_outros(config):
    """Sem via especial para o caso base: o E0 exige
    ``E0_*.ifc`` na pasta das variantes, e sem ele o cenário não roda."""
    assert "E0_*.ifc" in rc.faltando(config, "E0")
    assert "caso_base" not in config or "ifc" not in config["caso_base"]
    proprio = os.path.join(config["pastas"]["ifc"], "E0_asis.ifc")
    _toca(proprio)
    assert rc.faltando(config, "E0") == ""
    assert rc.modelo_de(config, "E0") == proprio


def test_cenario_sem_arquivo_diz_qual_arquivo_falta(config):
    assert "E1_*.ifc" in rc.faltando(config, "E1")
    assert "V5_*.csv" in rc.faltando(config, "V5")
    assert "tela" in rc.faltando(config, "D5")
    assert "E3_*.ifc" in rc.faltando(config, "D4")     # roda sobre o pai


def test_modelo_e_terreno_herdados_do_pai(config):
    _toca(os.path.join(config["pastas"]["ifc"], "E0_asis.ifc"))
    e3 = os.path.join(config["pastas"]["ifc"], "E3_teto.ifc")
    _toca(e3)
    # D4 (sem arquivo próprio) lê o modelo do E3; V5 (CSV) lê o modelo do E0.
    assert rc.modelo_de(config, "D4") == e3
    assert rc.faltando(config, "D4") == ""
    csv = os.path.join(config["pastas"]["gis"], "V5_modulo_i.csv")
    _toca(csv)
    assert rc.modelo_de(config, "V5") == rc.modelo_de(config, "E0")
    assert rc.fonte_do_terreno(config, "V5") == ("csv", csv)
    # Sem CSV nem IFC de terreno, o terreno é o do empreendimento.json.
    assert rc.fonte_do_terreno(config, "E3") == ("empreendimento", None)


def test_v3_e_terreno_por_ifc_sobre_o_modelo_do_e0(config):
    e0 = os.path.join(config["pastas"]["ifc"], "E0_asis.ifc")
    v3 = os.path.join(config["pastas"]["ifc"], "V3_gleba.ifc")
    _toca(e0)
    _toca(v3)
    assert rc.fonte_do_terreno(config, "V3") == ("ifc", v3)
    assert rc.modelo_de(config, "V3") == e0


def test_dois_arquivos_para_o_mesmo_id_e_erro_de_pasta(config):
    _toca(os.path.join(config["pastas"]["ifc"], "E1_a.ifc"))
    _toca(os.path.join(config["pastas"]["ifc"], "E1_b.ifc"))
    with pytest.raises(SystemExit):
        rc.arquivo_do_cenario(config, "E1", "ifc")


def test_perfil_conta_requisitos_pelo_normativo_e_nao_linhas(config):
    """A unidade é a do ``resumo.normativo.ids``: membros de agregação não viram linha."""
    relatorios = {"enquadramento": {
        "resumo": {"normativo": {"ids": ["ENQ-009", "ENQ-010"]}},
        "por_requisito": [
            {"requisito": "ENQ-009", "estado": "nao_conforme", "detalhe": {},
             "valor_encontrado": 1383.7, "mensagem": ""},
            {"requisito": "ENQ-010", "estado": "nao_avaliavel",
             "detalhe": {"motivo_nao_avaliavel": "agregacao_indecisa"},
             "valor_encontrado": 0, "mensagem": ""},
            {"requisito": "ENQ-010.1", "estado": "nao_avaliavel",
             "detalhe": {"motivo_nao_avaliavel": "metrica_insuficiente"}},
        ]}}
    perfil = rc.perfil(config, relatorios)
    assert [(l["requisito"], l["estado"], l["motivo"]) for l in perfil] == [
        ("ENQ-009", "nao_conforme", ""),
        ("ENQ-010", "nao_avaliavel", "agregacao_indecisa")]
    assert rc.celula(perfil[0]) == "NC"
    assert rc.celula(perfil[1]) == "NA(agregacao_indecisa)"


def test_mesmo_veredito_e_numeros_com_tolerancia():
    a = {"estado": "nao_conforme", "motivo": "", "valor_encontrado": 677.0840789893033}
    b = {"estado": "nao_conforme", "motivo": "", "valor_encontrado": 677.0840789893032}
    assert rc.mesmo_veredito(a, b)
    assert rc.numeros_iguais(a["valor_encontrado"], b["valor_encontrado"])   # 1 ULP
    assert not rc.numeros_iguais(677.0, 678.0)
    assert not rc.mesmo_veredito(a, {"estado": "nao_avaliavel", "motivo": ""})
