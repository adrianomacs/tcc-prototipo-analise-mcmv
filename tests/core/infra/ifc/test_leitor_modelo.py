"""Schema não suportado é DIAGNÓSTICO, não traceback.

    pytest tests/core/infra/ifc/test_leitor_modelo.py

O caso real é o ``UT_GeoRef_1.ifc``, que declara IFC4X3_RC2 — um candidato a
versão que o IfcOpenShell recusa. O Enquadramento já tratava (entra por
``de_ifc.resolver_arquivo``); as telas de **Georreferenciamento** e **Programa
de necessidades** não, porque ``composicao.montar_contexto`` chamava o ``abrir``
cru. Estes testes prendem o caminho novo e, principalmente, as duas fronteiras
que é fácil apagar sem querer:

* não há IFC neste fluxo (Enquadramento) **não** é erro de ingestão;
* header ilegível **não** é veto — quem decide se o arquivo abre é a biblioteca.

Nenhum deles precisa do IfcOpenShell.
"""

from __future__ import annotations

import json
import sys
import types

import pytest

from core import composicao
from core.aplicacao import pipeline
from core.infra.ifc import leitor_modelo as leitor_ifc
from tests.apoio.ifc_falso import FakeEntity

RC2 = ("ISO-10303-21;\nHEADER;\nFILE_SCHEMA (('IFC4X3_RC2'));\nENDSEC;\n"
       "DATA;\nENDSEC;\nEND-ISO-10303-21;\n")


@pytest.fixture
def ifc_rc2(tmp_path):
    alvo = tmp_path / "UT_GeoRef_1.ifc"
    alvo.write_text(RC2, encoding="utf-8")
    return str(alvo)


# ---------------------------------------------------------------------------
# A porta: abrir_seguro
# ---------------------------------------------------------------------------

def test_header_com_release_candidate_e_vetado_pelo_nome(ifc_rc2):
    modelo, erro = leitor_ifc.abrir_seguro(ifc_rc2)
    assert modelo is None
    assert "IFC4X3_RC2" in erro
    assert "IFC4" in erro, "a mensagem tem de dizer o que exportar"


def test_header_ilegivel_chega_a_biblioteca_em_vez_de_ser_vetado(
        monkeypatch, tmp_path):
    """O header só veta o que ele IDENTIFICA como não publicável.

    Recusar um arquivo cujo header a regex não alcançou (encoding incomum,
    cabeçalho acima de 8 KB) seria rejeitar por ignorância um arquivo que a
    biblioteca talvez abrisse — e esta porta serve ao pipeline
    inteiro, não só ao Enquadramento. A autoridade sobre "abre?" é o
    IfcOpenShell; o header só serve para NOMEAR o problema quando ele existe.

    A prova usa um ``ifcopenshell`` FALSO, por três razões: a afirmação testada
    é *a biblioteca foi consultada*, e isso se afirma melhor no positivo do que
    pela ausência de uma mensagem; o teste passa a valer em ambiente sem a
    biblioteca instalada; e o ``open`` real, ao falhar, deixa o ``file.__del__``
    do IfcOpenShell estourar um ``KeyError`` na coleta de lixo — ruído dele, não
    nosso, que o pytest recolhe como ``PytestUnraisableExceptionWarning`` e
    atribui a um teste qualquer, conforme a hora em que o GC rodar.
    """
    alvo = tmp_path / "sem_header.ifc"
    alvo.write_text("isto nao tem FILE_SCHEMA", encoding="utf-8")

    tentativas: list[str] = []
    falso = types.ModuleType("ifcopenshell")
    falso.version = "0.0-falso"

    def _open(caminho, *a, **k):
        tentativas.append(caminho)
        raise RuntimeError("arquivo ilegível")

    falso.open = _open
    monkeypatch.setitem(sys.modules, "ifcopenshell", falso)

    modelo, erro = leitor_ifc.abrir_seguro(str(alvo))

    assert tentativas == [str(alvo)], "o veto do header curto-circuitou a leitura"
    assert modelo is None
    # Falhar, falha (não é um IFC); o que não pode é falhar COM A CAUSA ERRADA —
    # "o schema X não é suportado" sobre um arquivo sem schema nenhum.
    assert "não suporta" not in erro
    assert "arquivo ilegível" in erro


def test_header_com_schema_publicado_tambem_chega_a_biblioteca(
        monkeypatch, tmp_path):
    """A contraprova: o header bom não decide nada sozinho — só não atrapalha."""
    alvo = tmp_path / "bom.ifc"
    alvo.write_text("ISO-10303-21;\nHEADER;\nFILE_SCHEMA (('IFC4'));\nENDSEC;\n",
                    encoding="utf-8")

    sentinela = object()
    falso = types.ModuleType("ifcopenshell")
    falso.version = "0.0-falso"
    falso.open = lambda caminho, *a, **k: sentinela
    monkeypatch.setitem(sys.modules, "ifcopenshell", falso)

    modelo, erro = leitor_ifc.abrir_seguro(str(alvo))
    assert modelo is sentinela and erro == ""


# ---------------------------------------------------------------------------
# A premissa do IFC4 (decisão de escopo)
# ---------------------------------------------------------------------------

def test_georreferencia_estruturada_comeca_no_ifc4():
    for bom in ("IFC4", "ifc4", "IFC4X1", "IFC4X3_ADD2"):
        assert leitor_ifc.georreferencia_estruturada(bom), bom
    for aquem in ("IFC2X3", "IFC2X2"):
        assert not leitor_ifc.georreferencia_estruturada(aquem), aquem
    # Schema vazio não é reprovação: quem decide sobre modelo ausente é a
    # camada que o pediu, e tratar "" como aquém faria a tela acusar premissa
    # descumprida antes de existir arquivo.
    assert leitor_ifc.georreferencia_estruturada("")


def test_a_premissa_nao_vira_veto_na_porta():
    """A distinção que o escopo exige: IFC2X3 é ACEITO, apenas limitado.

    A premissa é sobre o que se pode CONCLUIR de um IFC2X3 (nada de
    georreferenciamento estruturado), não sobre poder abri-lo. Se ela vazar para
    ``schema_suportavel``, o Programa de necessidades — que lê ``IfcSpace`` e
    quantidades, iguais nos dois schemas — passa a recusar arquivos que sempre
    analisou, e a causa seria de outra camada.
    """
    assert "IFC2X3" in leitor_ifc.SCHEMAS_PUBLICADOS
    assert leitor_ifc.schema_suportavel("IFC2X3")
    assert not leitor_ifc.georreferencia_estruturada("IFC2X3")


def test_a_premissa_declara_a_alternativa_recusada():
    """O achado não pode sumir do produto: ele é material do texto.

    Quem vir a recusa na tela tem de saber que a via por property set foi
    LEVANTADA e descartada, não ignorada — é a diferença entre uma limitação e
    uma decisão de escopo, e é ela que a banca cobra.
    """
    texto = leitor_ifc.PREMISSA_IFC4_ALTERNATIVA_RECUSADA
    assert "ePSet_ProjectedCRS" in texto and "ePSet_MapConversion" in texto
    assert "fora do escopo" in texto


def test_schema_publicado_passa_do_veto_do_header():
    assert leitor_ifc.schema_suportavel("IFC4")
    assert leitor_ifc.schema_suportavel("IFC2X3")
    assert leitor_ifc.schema_suportavel("IFC4X3_ADD2")
    assert not leitor_ifc.schema_suportavel("IFC4X3_RC2")


# ---------------------------------------------------------------------------
# Camada I: o erro viaja no Contexto
# ---------------------------------------------------------------------------

def test_montar_contexto_nao_levanta_e_declara_a_causa(ifc_rc2):
    ctx = composicao.montar_contexto(ifc_rc2, None, {})
    assert ctx.modelo_ifc is None
    assert "IFC4X3_RC2" in ctx.erro_ingestao


def test_sem_ifc_no_fluxo_nao_e_erro_de_ingestao():
    """Regressão do Enquadramento, que roda sem modelo POR CONCEPÇÃO.

    ``modelo_ifc is None`` sozinho não distingue "não abriu" de "não há IFC
    aqui". Se os dois casos colapsarem, o Enquadramento para de rodar — e para
    com a mensagem de um arquivo que ninguém enviou.
    """
    assert composicao.montar_contexto("", None, {}).erro_ingestao == ""
    assert composicao.montar_contexto(None, None, {}).erro_ingestao == ""


def test_arquivo_inexistente_tambem_nao_e_erro_de_ingestao(tmp_path):
    """Mantém o comportamento anterior: caminho que não existe vira modelo None
    silenciosamente. Quem apresenta arquivo é a tela, e ela exige o upload."""
    ausente = str(tmp_path / "nao_existe.ifc")
    assert composicao.montar_contexto(ausente, None, {}).erro_ingestao == ""


# ---------------------------------------------------------------------------
# Camada III/IV: nenhuma regra executada, e o relatório anterior preservado
# ---------------------------------------------------------------------------

def test_rodar_nao_executa_regra_nenhuma_quando_o_ifc_nao_abre(
        monkeypatch, tmp_path, ifc_rc2):
    destino = tmp_path / "relatorio.json"
    executou = []

    monkeypatch.setattr(pipeline, "executar",
                        lambda ctx, ids_selecionados=None: executou.append(1))
    monkeypatch.setattr(composicao, "_carregar_config",
                        lambda *a, **k: {"paths": {"relatorio": str(destino)}})

    relatorio = composicao.rodar(caminho_ifc=ifc_rc2, pasta_gis="")

    assert not executou, "nenhuma regra pode rodar sobre um modelo que não abriu"
    assert "IFC4X3_RC2" in relatorio["erro_ingestao"]
    assert relatorio["resultados"] == []
    assert not destino.exists(), "não se grava relatório de análise que não houve"


def test_relatorio_anterior_nao_e_sobrescrito(monkeypatch, tmp_path, ifc_rc2):
    """Uma análise que não aconteceu não pode apagar a que aconteceu.

    É o defeito silencioso desta refatoração: se ``rodar`` gravasse o relatório
    vazio, o usuário perderia o resultado bom ao tentar analisar um arquivo
    ruim — e descobriria depois, sem ligar uma coisa à outra.
    """
    destino = tmp_path / "relatorio.json"
    anterior = {"resultados": [{"requisito": "EMP-001"}]}
    destino.write_text(json.dumps(anterior), encoding="utf-8")

    monkeypatch.setattr(composicao, "_carregar_config",
                        lambda *a, **k: {"paths": {"relatorio": str(destino)}})
    composicao.rodar(caminho_ifc=ifc_rc2, pasta_gis="")

    assert json.loads(destino.read_text(encoding="utf-8")) == anterior


def test_fluxo_sem_ifc_segue_gravando_o_relatorio(monkeypatch, tmp_path):
    """A contraprova do teste acima: sem IFC, ``rodar`` não toma o atalho."""
    destino = tmp_path / "relatorio.json"
    monkeypatch.setattr(pipeline, "executar",
                        lambda ctx, ids_selecionados=None: [])
    monkeypatch.setattr(composicao, "_imprimir_resumo", lambda r: None)
    monkeypatch.setattr(composicao, "_carregar_config",
                        lambda *a, **k: {"paths": {"relatorio": str(destino)}})

    relatorio = composicao.rodar(caminho_ifc="", pasta_gis="")

    assert "erro_ingestao" not in relatorio
    assert destino.exists()


# ---------------------------------------------------------------------------
# materiais_do_elemento — só os NOMES, com conjuntos e camadas expandidos
# ---------------------------------------------------------------------------

def _mat(nome):
    return FakeEntity("IfcMaterial", Name=nome)


def test_nomes_de_material_simples():
    from core.infra.ifc.leitor_modelo import _nomes_de_material
    assert _nomes_de_material(_mat("Telha cerâmica")) == ["Telha cerâmica"]
    assert _nomes_de_material(_mat(None)) == [""]     # sem nome NÃO é descartado
    assert _nomes_de_material(None) == []


def test_nomes_de_material_expandem_camadas_constituintes_e_usage():
    from core.infra.ifc.leitor_modelo import _nomes_de_material
    camadas = FakeEntity("IfcMaterialLayerSet", MaterialLayers=[
        FakeEntity("IfcMaterialLayer", Material=_mat("Reboco")),
        FakeEntity("IfcMaterialLayer", Material=_mat("Tinta")),
    ])
    usage = FakeEntity("IfcMaterialLayerSetUsage", ForLayerSet=camadas)
    assert _nomes_de_material(usage) == ["Reboco", "Tinta"]

    constituintes = FakeEntity("IfcMaterialConstituentSet", MaterialConstituents=[
        FakeEntity("IfcMaterialConstituent", Material=_mat("Barro"))])
    assert _nomes_de_material(constituintes) == ["Barro"]

    lista = FakeEntity("IfcMaterialList", Materials=[_mat("A"), _mat("B")])
    assert _nomes_de_material(lista) == ["A", "B"]


def test_material_de_classe_desconhecida_nao_inventa_nome():
    from core.infra.ifc.leitor_modelo import _nomes_de_material
    assert _nomes_de_material(FakeEntity("IfcMaterialProperties")) == []
