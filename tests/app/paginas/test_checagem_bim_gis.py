"""Checagem — Requisitos de Projeto (BIM + GIS): a absortância por zona.

`AppTest` da página de verdade. O relatório é o que as seis regras de
absortância gravam (``_relatorio``, das regras reais sobre um modelo falso),
posto em disco em `artefatos/relatorios/bim_gis.json` e na sessão, que é o
que diz à tela que houve análise.

Isolado de `artefatos/` real via `app.servicos.empreendimento.ARTEFATOS` e
`app.servicos.relatorios.PASTA_RELATORIOS`, como `test_resultados_consolidados.py`.
"""

from __future__ import annotations

import json
import os

import pytest

pytest.importorskip("streamlit", reason="sem Streamlit não há o que renderizar")
pytestmark = pytest.mark.interface

from streamlit.testing.v1 import AppTest

from app.estado import chaves
from app.servicos import empreendimento as emp_mod
from app.servicos import relatorios
from core.aplicacao.executor import executar
from core.dominio.conhecimento.zona_bioclimatica import ZonaBioclimatica
from core.dominio.empreendimento import Empreendimento
from core.dominio.unidade_tipo import UnidadeTipo
from core.infra.exportadores import relatorio_json
from tests.apoio import ifc_falso as f
from tests.apoio.contexto_bim import contexto_bim
from tests.conftest import RAIZ

CAMINHO_PAGINA = os.path.join(
    RAIZ, "app", "paginas", "checagens", "checagem_bim_gis.py")


IDS = ["EDI-019", "EDI-019.1", "EDI-019.2", "EDI-024", "EDI-024.1", "EDI-024.2"]
META = {"municipio_ibge": "4307807",
        "declaracoes": {"uf": "RS", "municipio": "Estrela",
                        "municipio_ibge": "4307807"}}


def _relatorio(monkeypatch, zona: ZonaBioclimatica | None) -> dict:
    """As seis regras de absortância de verdade sobre um covering de parede,
    um de telhado e um órfão — para a página receber o relatório que o núcleo
    grava, não um ``dict`` escrito à mão."""
    parede, cov_parede = f.parede(), f.covering(gid="COV-PAREDE")
    telhado, cov_telhado = f.telhado(), f.covering(predefinido="ROOFING",
                                                   gid="COV-TELHA")
    orfao = f.covering(gid="COV-ORFAO")
    modelo = f.modelo_coverings(parede, cov_parede, telhado, cov_telhado, orfao,
                                f.rel_cobre(parede, cov_parede, gid="REL-P"),
                                f.rel_cobre(telhado, cov_telhado, gid="REL-T"))
    monkeypatch.setattr("core.infra.ifc.leitor_modelo.propriedades_do_elemento",
                        lambda e: {"AbsortanciaSolar": 0.5})
    monkeypatch.setattr(
        "core.infra.ifc.leitor_modelo.propriedade_de_pset",
        lambda e, pset, *chaves: ((True, f"{pset}.IsExternal")
                                  if pset == "Pset_CoveringCommon" else (None, "")))
    monkeypatch.setattr("core.infra.ifc.leitor_modelo.materiais_do_elemento",
                        lambda e: ["Telha de fibrocimento"])
    resultados = executar(contexto_bim(modelo_ifc=modelo, zona_bioclimatica=zona),
                          ids_selecionados=IDS)
    return relatorio_json.montar(resultados, meta=META)


@pytest.fixture
def pasta_rel(tmp_path, monkeypatch):
    monkeypatch.setattr(emp_mod, "ARTEFATOS", str(tmp_path))
    pasta = tmp_path / "relatorios"
    pasta.mkdir()
    monkeypatch.setattr(relatorios, "PASTA_RELATORIOS", str(pasta))
    return pasta


def _abrir(emp: Empreendimento, relatorio: dict | None = None,
           pasta=None) -> AppTest:
    emp_mod.gravar(emp)
    at = AppTest.from_file(CAMINHO_PAGINA)
    if relatorio is not None:
        (pasta / "bim_gis.json").write_text(json.dumps(relatorio), encoding="utf-8")
        at.session_state[chaves.chave_relatorio("bim_gis")] = relatorio
    at.run(timeout=60)
    assert not at.exception
    return at


def _textos(at) -> str:
    partes = [m.value for m in at.markdown] + [c.value for c in at.caption]
    partes += [w.value for w in at.warning] + [s.value for s in at.success]
    partes += [i.value for i in at.info]
    return "\n".join(str(p) for p in partes)


def test_sem_analise_nao_mostra_painel_e_nao_oferece_terreno(pasta_rel):
    emp = Empreendimento(unidades_tipo=[UnidadeTipo(nome="Casa padrão")])
    at = _abrir(emp)

    (seletor,) = [s for s in at.selectbox if s.key == "alvo__bim_gis"]
    assert "Terreno" not in seletor.options          # sem envoltória, sem regra
    assert "Terreno com as edificações" in seletor.options
    assert "Casa padrão — unidade tipo isolada" in seletor.options
    assert "O que o território decidiu" not in _textos(at)


def test_sem_municipio_avisa_que_a_zona_nao_sera_resolvida(pasta_rel):
    at = _abrir(Empreendimento())
    assert any("Município ainda não declarado" in w.value for w in at.warning)


def test_com_analise_o_resultado_nao_repete_o_relatorio(pasta_rel, monkeypatch):
    """O painel "O que o território decidiu" saiu (ADR-034): depois de
    analisar, a tela mostra o resultado comum com o acesso aos relatórios de
    EDI-019 e EDI-024, e não um segundo quadro com zona e revestimentos."""
    relatorio = _relatorio(monkeypatch, ZonaBioclimatica(classe="2R",
                                                        codigo_ibge="4307807"))
    at = _abrir(Empreendimento(), relatorio, pasta_rel)
    assert "O que o território decidiu" not in _textos(at)
    assert "Zona bioclimática" not in {m.label for m in at.metric}
    assert any(b.label == "Nova análise" for b in at.button)
