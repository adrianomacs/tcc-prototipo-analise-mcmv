"""Cobertura do Protótipo (2.4.1) e Relatório de Checagem (2.4.2).

`AppTest` das duas páginas de verdade, isoladas de `artefatos/` real via
`app.servicos.empreendimento.ARTEFATOS` e `app.servicos.relatorios.
PASTA_RELATORIOS` apontados para `tmp_path` — mesmo cuidado de
`test_informacoes_gerais.py`: sem isso, o teste dependeria do
`empreendimento.json`/`artefatos/relatorios/*.json` reais deste ambiente de
desenvolvimento.

O estado "nenhuma checagem executada" já é coberto por `test_paginas_
renderizam.py` (roda a árvore inteira sem sessão nem artefatos preparados);
aqui o cenário é o oposto: relatórios gravados, batendo (ou não) com o
empreendimento corrente.
"""

from __future__ import annotations

import ast
import json
import os

import pytest

pytest.importorskip("streamlit", reason="sem Streamlit não há o que renderizar")
pytestmark = pytest.mark.interface

from streamlit.testing.v1 import AppTest

from app.servicos import empreendimento as emp_mod
from app.servicos import relatorios
from core.dominio.empreendimento import Empreendimento
from tests.conftest import RAIZ

PASTA_PAGINAS = os.path.join(RAIZ, "app", "paginas", "checagens")
CAMINHO_RESULTADOS = os.path.join(PASTA_PAGINAS, "resultados.py")
CAMINHO_RELATORIO_CHECAGEM = os.path.join(PASTA_PAGINAS, "relatorio_checagem.py")


def _relatorio(referencia: dict, *, total=2, avaliados=2, conforme=2,
              nao_conforme=0, nao_avaliavel=0) -> dict:
    normativo = {"total": total, "avaliados": avaliados, "conforme": conforme,
                "nao_conforme": nao_conforme, "nao_avaliavel": nao_avaliavel,
                "ids": [], "membros": [],
                "conformidade": round(conforme / avaliados, 4) if avaliados else None,
                "cobertura": round(avaliados / total, 4) if total else 0.0}
    resumo = dict(normativo, total_requisitos=total, normativo=normativo)
    return {"meta": {"empreendimento": referencia}, "resumo": resumo,
            "por_requisito": [], "por_elemento": {}}


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    monkeypatch.setattr(emp_mod, "ARTEFATOS", str(tmp_path))
    pasta_rel = tmp_path / "relatorios"
    monkeypatch.setattr(relatorios, "PASTA_RELATORIOS", str(pasta_rel))
    pasta_rel.mkdir()
    emp = Empreendimento(nome="Teste Fase 5")
    emp_mod.gravar(emp)
    return emp, pasta_rel


@pytest.mark.parametrize("caminho", [CAMINHO_RESULTADOS, CAMINHO_RELATORIO_CHECAGEM])
def test_sem_nenhum_relatorio_gravado_mostra_aviso_sem_excecao(ambiente, caminho):
    at = AppTest.from_file(caminho)
    at.run(timeout=60)
    assert not at.exception
    assert at.info, f"{caminho}: esperava um st.info explicando que falta rodar as checagens"


@pytest.mark.parametrize("caminho", [CAMINHO_RESULTADOS, CAMINHO_RELATORIO_CHECAGEM])
def test_relatorio_de_outro_empreendimento_nao_entra(ambiente, caminho):
    _emp, pasta_rel = ambiente
    (pasta_rel / "enquadramento.json").write_text(
        json.dumps(_relatorio({"id": "outro", "versao": 99})), encoding="utf-8")

    at = AppTest.from_file(caminho)
    at.run(timeout=60)

    assert not at.exception
    assert at.info, "relatório de outro empreendimento não deveria contar como consolidado"


def test_cobertura_do_prototipo_consolida_as_checagens_do_empreendimento_corrente(ambiente):
    emp, pasta_rel = ambiente
    ref = emp.referencia()
    (pasta_rel / "enquadramento.json").write_text(
        json.dumps(_relatorio(ref, total=3, avaliados=3, conforme=2, nao_conforme=1)),
        encoding="utf-8")
    (pasta_rel / "programa.json").write_text(
        json.dumps(_relatorio(ref, total=1, avaliados=1, conforme=1)), encoding="utf-8")

    at = AppTest.from_file(CAMINHO_RESULTADOS)
    at.run(timeout=60)

    assert not at.exception
    assert not at.info  # já há dados: nada de "nenhuma checagem executada"
    metricas = {m.label: m.value for m in at.metric}
    assert metricas["Requisitos avaliados"] == "4/4"
    assert metricas["Capacidade de conclusão"] == "100%"
    assert metricas["Conformidade"] == "75%"


def test_relatorio_de_checagem_mostra_card_de_sintese_e_o_texto(ambiente):
    """ADR-035: a 2.4.2 é texto descritivo — card de síntese contado em
    requisitos e os blocos do texto; sem métricas nem expanders por checagem
    (os números e o acesso aos relatórios ficam na 2.4.1)."""
    emp, pasta_rel = ambiente
    ref = emp.referencia()
    (pasta_rel / "enquadramento.json").write_text(
        json.dumps(_relatorio(ref, total=3, avaliados=3, conforme=2, nao_conforme=1)),
        encoding="utf-8")
    (pasta_rel / "programa.json").write_text(
        json.dumps(_relatorio(ref, total=1, avaliados=1, conforme=1)), encoding="utf-8")

    at = AppTest.from_file(CAMINHO_RELATORIO_CHECAGEM)
    at.run(timeout=60)

    assert not at.exception
    assert not at.metric
    # `st.expander(icon=...)` aparece como Status na AppTest: o único é o do topo.
    assert [e.proto.label for e in at.status] == ["O que esta página mostra"]
    textos = [m.value for m in at.markdown]
    card = next(t for t in textos if "Resultado consolidado" in t)
    assert "Não conforme" in card
    assert "3 conformes · 1 não conforme · 0 não avaliáveis, em 4 requisitos da Portaria" in card
    # Seções em subtítulo e o nome de cada checagem em título próprio (ADR-034).
    titulos = [h.value for h in at.subheader]
    for bloco in ("Síntese da análise", "Resultado por checagem", "Pendências"):
        assert bloco in titulos
    assert "#### Enquadramento" in textos
    assert "#### Programa de necessidades" in textos
    assert "#### Georreferenciamento do modelo" not in textos


def test_relatorio_de_checagem_condensa_requisitos_e_resultado_numa_tabela(ambiente):
    """Cada checagem abre com os insumos em prosa e traz os requisitos
    verificados numa tabela com o resultado, no lugar da lista e das frases de
    resultado do parágrafo; não há seção de resumo à parte."""
    emp, pasta_rel = ambiente
    relatorio = _relatorio(emp.referencia(), total=2, avaliados=1, conforme=1,
                           nao_avaliavel=1)
    relatorio["por_requisito"] = [
        {"requisito": "EDI-007", "descricao": "Largura mínima da cozinha",
         "estado": "conforme", "mensagem": "Largura de 1,90 m."},
        {"requisito": "EDI-008", "descricao": "Largura mínima da sala",
         "estado": "nao_avaliavel", "detalhe": {"motivo_nao_avaliavel": "informacao_ausente"},
         "mensagem": "Sem sala."},
    ]
    (pasta_rel / "programa.json").write_text(json.dumps(relatorio), encoding="utf-8")

    at = AppTest.from_file(CAMINHO_RELATORIO_CHECAGEM)
    at.run(timeout=60)

    assert not at.exception
    textos = [m.value for m in at.markdown]
    assert "#### Programa de necessidades" in textos
    assert any(t.endswith("Verificaram-se dois requisitos:") for t in textos)
    tabela = next(t for t in textos if t.startswith("| Requisito | Descrição |"))
    assert "| <span style='white-space:nowrap'>EDI-007</span> | Largura mínima da cozinha | :green[**Conforme**] | Largura de 1,90 m |" in tabela
    assert "| <span style='white-space:nowrap'>EDI-008</span> | Largura mínima da sala | :orange[**Não\u00a0avaliável**] |" in tabela
    # Nem a lista nem as frases de resultado se repetem em prosa.
    assert not any("EDI-007: conforme" in t for t in textos)
    assert "Resumo por requisito" not in [h.value for h in at.subheader]
    # A pendência do EDI-008 (informação ausente) vem em tabela sob a ação, e
    # não em bullets.
    pendencias = next(t for t in textos if t.startswith("| Requisito | Descrição | Detalhe |"))
    assert "<span style='white-space:nowrap'>EDI-008</span> | Largura mínima da sala |" in pendencias
    assert not any(t.startswith("- EDI-008") for t in textos)


# --- Qualificação e BIM + GIS no consolidado -------------------------

def _chaves_de_rotulo(caminho: str) -> list[str]:
    """As chaves de `_ROTULOS` lidas do fonte da página, na ordem — importar a
    página executaria Streamlit."""
    with open(caminho, encoding="utf-8") as f:
        arvore = ast.parse(f.read())
    for no in arvore.body:
        if (isinstance(no, ast.Assign) and len(no.targets) == 1
                and isinstance(no.targets[0], ast.Name)
                and no.targets[0].id == "_ROTULOS"):
            return [k.value for k in no.value.keys]
    raise AssertionError(f"{caminho}: `_ROTULOS` não encontrado")


@pytest.mark.parametrize("caminho", [CAMINHO_RESULTADOS])
def test_rotulos_das_paginas_cobrem_exatamente_as_checagens_somadas(caminho):
    """Chave somada sem rótulo sumiria da tabela por checagem e do expander;
    rótulo sem chave somada mostraria uma checagem fora da soma."""
    assert _chaves_de_rotulo(caminho) == list(relatorios.CHECAGENS)


def _perfil_com_absortancia_e_porte(pasta_rel, ref) -> None:
    for chave, contagens in {
        "georref": {"total": 1, "avaliados": 1, "conforme": 1},
        "qualificacao": {"total": 1, "avaliados": 1, "conforme": 0,
                         "nao_conforme": 1},
        "bim_gis": {"total": 2, "avaliados": 2, "conforme": 1, "nao_conforme": 1},
    }.items():
        (pasta_rel / f"{chave}.json").write_text(
            json.dumps(_relatorio(ref, **contagens)), encoding="utf-8")


def test_cobertura_do_prototipo_soma_qualificacao_e_bim_gis(ambiente):
    emp, pasta_rel = ambiente
    _perfil_com_absortancia_e_porte(pasta_rel, emp.referencia())

    at = AppTest.from_file(CAMINHO_RESULTADOS)
    at.run(timeout=60)

    assert not at.exception
    metricas = {m.label: m.value for m in at.metric}
    assert metricas["Requisitos avaliados"] == "4/4"
    assert metricas["Conformidade"] == "50%"
    tabela = at.dataframe[0].value
    assert list(tabela.index) == ["Qualificação Urbanística",
                                  "Georreferenciamento do Modelo",
                                  "Requisitos de Projeto (BIM + GIS)"]
    assert tabela.loc["Requisitos de Projeto (BIM + GIS)", "Total"] == 2


def test_relatorio_de_checagem_tem_paragrafo_de_qualificacao_e_bim_gis(ambiente):
    emp, pasta_rel = ambiente
    _perfil_com_absortancia_e_porte(pasta_rel, emp.referencia())

    at = AppTest.from_file(CAMINHO_RELATORIO_CHECAGEM)
    at.run(timeout=60)

    assert not at.exception
    textos = [m.value for m in at.markdown]
    assert "#### Qualificação Urbanística" in textos
    assert "#### Requisitos de projeto (BIM + GIS)" in textos


# --- Os diagnósticos da submissão em 2.4.1 (R3, ADR-023 D-K) ---------------

def _com_diagnosticos(referencia: dict, diagnosticos: list) -> dict:
    relatorio = _relatorio(referencia, total=1, avaliados=1, conforme=1)
    relatorio["meta"]["diagnosticos"] = diagnosticos
    return relatorio


def test_cobertura_do_prototipo_mostra_os_diagnosticos_marcados(ambiente):
    """Lidos do relatório GRAVADO, sem recalcular nada — a tela se reproduz a
    partir do que está em disco."""
    emp, pasta_rel = ambiente
    (pasta_rel / "programa.json").write_text(json.dumps(_com_diagnosticos(
        emp.referencia(),
        [{"chave": "extrapolacao", "rotulo": "Veredito extrapolado além do "
          "que o modelo representa", "marcado": True,
          "mensagem": "O veredito fala por 150 UH a partir de geometria que "
                      "representa 1.", "valores": {}},
         {"chave": "heterogeneidade", "rotulo": "Veredito agregado sobre mais "
          "de uma unidade tipo", "marcado": False, "mensagem": "",
          "valores": {}}])), encoding="utf-8")

    at = AppTest.from_file(CAMINHO_RESULTADOS)
    at.run(timeout=60)

    assert not at.exception
    texto = " ".join(m.value for m in at.markdown)
    assert "Veredito extrapolado além do que o modelo representa" in texto
    assert "fala por 150 UH" in texto
    assert "Veredito agregado sobre mais de uma unidade tipo" not in texto, (
        "os não marcados ficam no relatório, não na tela")


def test_sem_diagnostico_marcado_a_secao_nao_aparece(ambiente):
    emp, pasta_rel = ambiente
    (pasta_rel / "programa.json").write_text(json.dumps(_com_diagnosticos(
        emp.referencia(),
        [{"chave": "extrapolacao", "rotulo": "Veredito extrapolado",
          "marcado": False, "mensagem": "", "valores": {}}])),
        encoding="utf-8")

    at = AppTest.from_file(CAMINHO_RESULTADOS)
    at.run(timeout=60)

    assert not at.exception
    assert "O que estas análises não dizem" not in " ".join(
        m.value for m in at.markdown)


def test_relatorio_sem_a_chave_diagnosticos_nao_quebra_a_tela(ambiente):
    """O Georreferenciamento não grava a chave; 2.4.1 tem de continuar de pé."""
    emp, pasta_rel = ambiente
    (pasta_rel / "georref.json").write_text(
        json.dumps(_relatorio(emp.referencia())), encoding="utf-8")

    at = AppTest.from_file(CAMINHO_RESULTADOS)
    at.run(timeout=60)

    assert not at.exception
    assert "O que estas análises não dizem" not in " ".join(
        m.value for m in at.markdown)
