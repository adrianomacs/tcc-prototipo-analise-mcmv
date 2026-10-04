"""Isolamento da visualização 3D entre checagens.

Sem o isolamento, `iniciar_conversao`/`estado_viz`/`carregar_payload_viz`
guardavam o job de conversão em chaves GLOBAIS de `st.session_state`
(`chaves.VIZ_JOB_ID`/`VIZ_FUTURE`) e escreviam sempre na mesma pasta em disco
(`core.infra.caminhos.PASTA_TILES`) — a checagem mais recente sobrescrevia o
modelo/ambientes 3D da anterior quando as duas eram abertas na mesma sessão
do Streamlit. Estes testes simulam exatamente esse
cenário — Georreferenciamento e Programa de necessidades abertos na mesma
sessão — sem IfcOpenShell nem processo real: `gerar_artefatos` é substituída
por um dublê síncrono que grava um conteúdo diferente por modelo, e a
leitura de volta (`carregar_payload_viz`/`ler_status_viz`) confirma que cada
checagem enxerga só o próprio. O disparo em processo (`_disparar`) é trocado
por uma chamada direta — a costura existe exatamente para isso.
"""

from __future__ import annotations

import base64
import json
import os

import pytest

pytest.importorskip("streamlit", reason="sem Streamlit não há o que testar")

import core.infra.caminhos as caminhos
from app.estado import chaves
from app.servicos import conversao_3d
from core.infra.exportadores import visualizacao


class _ProcessoConcluido:
    """Dublê do handle de `subprocess.Popen` já terminado com sucesso."""

    def __init__(self, codigo: int = 0):
        self._codigo = codigo

    def poll(self):
        return self._codigo


def _disparo_sincrono(caminho_ifc, pasta, job_id, ancora_manual, excluir=None):
    """Dublê de `_disparar`: roda a conversão na hora, no mesmo processo —
    o teste não depende de timing nem de um processo real."""
    visualizacao.gerar_artefatos(caminho_ifc, pasta, job_id=job_id,
                                 ancora_manual=ancora_manual)
    return _ProcessoConcluido(0)


def _fake_gerar_artefatos(caminho_ifc, pasta_tiles, *, job_id=None,
                          nome="modelo", excluir_tipos=None,
                          incluir_tipos=None, ancora_manual=None):
    """Escreve um GLB cujo conteúdo identifica o IFC de origem — é o que
    prova, na leitura de volta, que cada checagem carrega o SEU modelo."""
    os.makedirs(pasta_tiles, exist_ok=True)
    conteudo = os.path.basename(caminho_ifc).encode("utf-8")
    with open(os.path.join(pasta_tiles, f"{nome}.glb"), "wb") as arq:
        arq.write(conteudo)
    with open(os.path.join(pasta_tiles, "tileset.json"), "w",
             encoding="utf-8") as arq:
        json.dump({"root": {"transform": [1.0] * 16}}, arq)
    visualizacao.escrever_status(pasta_tiles, estado="pronto", job_id=job_id,
                                 posicionavel=True)


@pytest.fixture
def sessao_simulada(tmp_path, monkeypatch):
    """`st.session_state` de mentira + `PASTA_TILES` num diretório temporário
    + conversão substituída pelo dublê síncrono acima."""
    monkeypatch.setattr(caminhos, "PASTA_TILES", str(tmp_path))
    monkeypatch.setattr(caminhos, "PASTA_CACHE_TILES",
                        str(tmp_path / "_cache"))
    monkeypatch.setattr(visualizacao, "gerar_artefatos", _fake_gerar_artefatos)
    monkeypatch.setattr(conversao_3d, "_disparar", _disparo_sincrono)
    sessao: dict = {}
    monkeypatch.setattr(conversao_3d.st, "session_state", sessao)
    return sessao


def _ifc_falso(tmp_path, nome: str) -> str:
    caminho = tmp_path / nome
    # O nome vai no conteúdo: a identidade do job é o
    # conteúdo, e dois modelos diferentes têm de ter conteúdos diferentes.
    caminho.write_text(f"IFC de mentira — {nome}")
    return str(caminho)


def test_pastas_de_tiles_sao_por_checagem(sessao_simulada, tmp_path):
    assert caminhos.pasta_tiles("georref") != caminhos.pasta_tiles("programa")
    assert caminhos.pasta_tiles("georref") == os.path.join(str(tmp_path), "georref")


def test_chaves_de_sessao_do_job_sao_por_checagem(sessao_simulada, tmp_path):
    ifc_georref = _ifc_falso(tmp_path, "modelo_georref.ifc")
    ifc_programa = _ifc_falso(tmp_path, "modelo_programa.ifc")

    conversao_3d.iniciar_conversao("georref", ifc_georref)
    conversao_3d.iniciar_conversao("programa", ifc_programa)

    assert chaves.chave_viz_job_id("georref") in sessao_simulada
    assert chaves.chave_viz_job_id("programa") in sessao_simulada
    # abrir a segunda checagem não apaga nem sobrescreve a chave da primeira
    # (o defeito original era exatamente essa colisão).
    assert (sessao_simulada[chaves.chave_viz_job_id("georref")]
            != sessao_simulada[chaves.chave_viz_job_id("programa")])


def test_duas_checagens_na_mesma_sessao_nao_vazam_visualizacao(
        sessao_simulada, tmp_path):
    """O cenário do achado original: Georreferenciamento é analisado, depois
    Programa de necessidades é analisado com OUTRO modelo, e as duas
    checagens seguem abertas na mesma sessão — cada uma tem de continuar
    mostrando o PRÓPRIO modelo, não o da checagem processada por último."""
    ifc_georref = _ifc_falso(tmp_path, "modelo_georref.ifc")
    ifc_programa = _ifc_falso(tmp_path, "modelo_programa.ifc")

    conversao_3d.iniciar_conversao("georref", ifc_georref)
    conversao_3d.iniciar_conversao("programa", ifc_programa)

    assert conversao_3d.estado_viz("georref") == "pronto"
    assert conversao_3d.estado_viz("programa") == "pronto"

    payload_georref = conversao_3d.carregar_payload_viz("georref")
    payload_programa = conversao_3d.carregar_payload_viz("programa")

    assert base64.b64decode(payload_georref["glb_b64"]) == b"modelo_georref.ifc"
    assert base64.b64decode(payload_programa["glb_b64"]) == b"modelo_programa.ifc"

    status_georref = conversao_3d.ler_status_viz("georref")
    status_programa = conversao_3d.ler_status_viz("programa")
    assert status_georref["job_id"] != status_programa["job_id"]


def test_reprocessar_uma_checagem_nao_afeta_o_estado_da_outra(
        sessao_simulada, tmp_path):
    """Reforça o cenário 3 do achado original: reprocessar (Nova análise) a
    checagem mais recente não deve alterar o estado/modelo da outra, já
    aberta antes — cada `chave` tem seu próprio job_id de sessão."""
    ifc_georref = _ifc_falso(tmp_path, "modelo_georref.ifc")
    ifc_programa_v1 = _ifc_falso(tmp_path, "modelo_programa_v1.ifc")
    ifc_programa_v2 = _ifc_falso(tmp_path, "modelo_programa_v2.ifc")

    conversao_3d.iniciar_conversao("georref", ifc_georref)
    conversao_3d.iniciar_conversao("programa", ifc_programa_v1)
    jid_georref_antes = sessao_simulada[chaves.chave_viz_job_id("georref")]

    conversao_3d.iniciar_conversao("programa", ifc_programa_v2)

    assert sessao_simulada[chaves.chave_viz_job_id("georref")] == jid_georref_antes
    assert conversao_3d.estado_viz("georref") == "pronto"
    payload_georref = conversao_3d.carregar_payload_viz("georref")
    assert base64.b64decode(payload_georref["glb_b64"]) == b"modelo_georref.ifc"

    payload_programa = conversao_3d.carregar_payload_viz("programa")
    assert base64.b64decode(payload_programa["glb_b64"]) == b"modelo_programa_v2.ifc"


# ---------------------------------------------------------------------------
# Conversão em processo próprio
# ---------------------------------------------------------------------------

def test_comando_do_conversor_e_o_cli_do_exportador(tmp_path):
    """O disparo real usa `python -m core.infra.exportadores.visualizacao` —
    mesmo interpretador do app, contrato pelo status.json (ADR-001)."""
    cmd = conversao_3d._comando("m.ifc", str(tmp_path), "abc123",
                                {"lat": -29.0, "lon": -51.0})
    assert cmd[1:3] == ["-m", "core.infra.exportadores.visualizacao"]
    assert "m.ifc" in cmd and "--job-id" in cmd and "abc123" in cmd
    i = cmd.index("--excluir")
    assert "IfcOpeningElement" in cmd[i + 1]
    assert "--ancora" in cmd and '"lat"' in cmd[cmd.index("--ancora") + 1]
    # Sem âncora manual, o argumento nem aparece.
    assert "--ancora" not in conversao_3d._comando("m.ifc", str(tmp_path),
                                                   "abc123", None)


def test_processo_morto_sem_status_vira_erro(sessao_simulada, tmp_path,
                                             monkeypatch):
    """Morte silenciosa: o processo terminou com código != 0 e o status ficou
    em 'processando'. Sem a guarda, o botão ficaria travado para sempre."""
    ifc = _ifc_falso(tmp_path, "modelo.ifc")

    def _morre_sem_gravar(caminho_ifc, pasta, job_id, ancora_manual, excluir=None):
        return _ProcessoConcluido(1)   # terminou mal, sem escrever status

    monkeypatch.setattr(conversao_3d, "_disparar", _morre_sem_gravar)
    conversao_3d.iniciar_conversao("georref", ifc)
    assert conversao_3d.estado_viz("georref") == "erro"


def test_processo_vivo_segue_processando(sessao_simulada, tmp_path,
                                         monkeypatch):
    class _ProcessoVivo:
        def poll(self):
            return None

    def _vivo(caminho_ifc, pasta, job_id, ancora_manual, excluir=None):
        return _ProcessoVivo()

    monkeypatch.setattr(conversao_3d, "_disparar", _vivo)
    ifc = _ifc_falso(tmp_path, "modelo.ifc")
    conversao_3d.iniciar_conversao("georref", ifc)
    assert conversao_3d.estado_viz("georref") == "processando"


def test_falha_no_disparo_grava_erro(sessao_simulada, tmp_path, monkeypatch):
    """Se nem o processo nasce (spawn falhou), o estado é 'erro' visível —
    nunca 'processando' eterno."""
    def _explode(caminho_ifc, pasta, job_id, ancora_manual, excluir=None):
        raise OSError("sem interpretador")

    monkeypatch.setattr(conversao_3d, "_disparar", _explode)
    ifc = _ifc_falso(tmp_path, "modelo.ifc")
    conversao_3d.iniciar_conversao("georref", ifc)
    assert conversao_3d.estado_viz("georref") == "erro"


# ---------------------------------------------------------------------------
# Cache pelo conteúdo do IFC
# ---------------------------------------------------------------------------

@pytest.fixture
def contador_disparos(sessao_simulada, monkeypatch):
    """Conta quantas conversões de fato disparam."""
    disparos: list[str] = []

    def _contando(caminho_ifc, pasta, job_id, ancora_manual, excluir=None):
        disparos.append(job_id)
        return _disparo_sincrono(caminho_ifc, pasta, job_id, ancora_manual, excluir)

    monkeypatch.setattr(conversao_3d, "_disparar", _contando)
    return disparos


def _reenviar(caminho: str) -> None:
    """Simula o upload: regrava o MESMO conteúdo, com mtime novo."""
    with open(caminho, "rb") as arq:
        conteudo = arq.read()
    with open(caminho, "wb") as arq:
        arq.write(conteudo)
    os.utime(caminho, (os.path.getatime(caminho),
                       os.path.getmtime(caminho) + 60))


def test_mesmo_arquivo_reenviado_converte_uma_vez_so(contador_disparos,
                                                     tmp_path):
    ifc = _ifc_falso(tmp_path, "modelo.ifc")
    conversao_3d.iniciar_conversao("georref", ifc)
    assert conversao_3d.estado_viz("georref") == "pronto"  # guarda no cache

    _reenviar(ifc)
    conversao_3d.iniciar_conversao("georref", ifc)

    assert len(contador_disparos) == 1
    assert conversao_3d.estado_viz("georref") == "pronto"
    payload = conversao_3d.carregar_payload_viz("georref")
    assert base64.b64decode(payload["glb_b64"]) == b"modelo.ifc"


def test_cache_serve_outra_checagem_e_outro_nome(contador_disparos, tmp_path):
    """Mesmo conteúdo com outro nome, noutra checagem: sem nova conversão."""
    ifc = _ifc_falso(tmp_path, "modelo.ifc")
    conversao_3d.iniciar_conversao("georref", ifc)
    conversao_3d.estado_viz("georref")

    copia = tmp_path / "copia.ifc"
    copia.write_bytes(open(ifc, "rb").read())
    conversao_3d.iniciar_conversao("programa", str(copia))

    assert len(contador_disparos) == 1
    assert conversao_3d.estado_viz("programa") == "pronto"


def test_arquivo_alterado_converte_de_novo(contador_disparos, tmp_path):
    ifc = _ifc_falso(tmp_path, "modelo.ifc")
    conversao_3d.iniciar_conversao("georref", ifc)
    conversao_3d.estado_viz("georref")

    with open(ifc, "a", encoding="utf-8") as arq:
        arq.write(" — alterado")
    conversao_3d.iniciar_conversao("georref", ifc)

    assert len(contador_disparos) == 2
    assert contador_disparos[0] != contador_disparos[1]


def test_ancora_manual_diferente_converte_de_novo(contador_disparos, tmp_path):
    ifc = _ifc_falso(tmp_path, "modelo.ifc")
    conversao_3d.iniciar_conversao("georref", ifc)
    conversao_3d.estado_viz("georref")

    conversao_3d.iniciar_conversao("georref", ifc,
                                   {"lat": -9.6, "lon": -35.7})
    assert len(contador_disparos) == 2


def test_conversao_com_erro_nao_vai_para_o_cache(sessao_simulada, tmp_path,
                                                 monkeypatch):
    disparos = []

    def _falha(caminho_ifc, pasta, job_id, ancora_manual, excluir=None):
        disparos.append(job_id)
        visualizacao.escrever_status(pasta, estado="erro", job_id=job_id,
                                     erro="geometria inválida")
        return _ProcessoConcluido(0)

    monkeypatch.setattr(conversao_3d, "_disparar", _falha)
    ifc = _ifc_falso(tmp_path, "modelo.ifc")
    conversao_3d.iniciar_conversao("georref", ifc)
    assert conversao_3d.estado_viz("georref") == "erro"
    conversao_3d.iniciar_conversao("georref", ifc)
    assert len(disparos) == 2


# ---------------------------------------------------------------------------
# Identidade do job: SHA-256 de uma fonte só e versão da conversão
# ---------------------------------------------------------------------------

def test_identidade_usa_a_impressao_digital_do_relatorio(tmp_path, monkeypatch):
    """O conteúdo entra pelo mesmo SHA-256 que o relatório grava (ADR-035)."""
    from core.infra import impressao_digital

    ifc = tmp_path / "m.ifc"
    ifc.write_bytes(b"ISO-10303-21;")
    chamadas = []
    original = impressao_digital.sha256

    def espiao(caminho):
        chamadas.append(caminho)
        return original(caminho)

    monkeypatch.setattr(impressao_digital, "sha256", espiao)
    conversao_3d._job_id(str(ifc))
    assert chamadas == [str(ifc)]


def test_identidade_muda_com_a_versao_da_conversao(tmp_path, monkeypatch):
    """Cache de conversão anterior (sem ``revestimentos.json``) não casa."""
    ifc = tmp_path / "m.ifc"
    ifc.write_bytes(b"ISO-10303-21;")
    atual = conversao_3d._job_id(str(ifc))
    monkeypatch.setattr(conversao_3d, "_VERSAO_CONVERSAO",
                        conversao_3d._VERSAO_CONVERSAO - 1)
    assert conversao_3d._job_id(str(ifc)) != atual


def test_identidade_de_arquivo_ilegivel_cai_no_caminho(tmp_path):
    ausente = str(tmp_path / "nao_existe.ifc")
    assert conversao_3d._job_id(ausente) == conversao_3d._job_id(ausente)
    assert conversao_3d._job_id(ausente) != conversao_3d._job_id(ausente + "x")


# ---------------------------------------------------------------------------
# GLB publicado à parte da cena
# ---------------------------------------------------------------------------

def test_glb_publicado_como_arquivo_e_sem_base64(sessao_simulada, tmp_path,
                                                  monkeypatch):
    """A cena recebe o endereço do GLB, não o GLB em base64, e a publicação
    só copia de novo quando a conversão muda."""
    monkeypatch.setattr(caminhos, "APP_DIR", str(tmp_path / "app"))
    ifc = tmp_path / "modelo.ifc"
    ifc.write_bytes(b"ISO-10303-21;")
    conversao_3d.iniciar_conversao("programa", str(ifc))
    viz = conversao_3d.carregar_payload_viz("programa", publicar_glb=True)
    assert viz["glb_b64"] is None
    assert viz["glb_url"].startswith("/app/static/modelos/programa.glb?v=")
    publicado = tmp_path / "app" / "static" / "modelos" / "programa.glb"
    assert publicado.read_bytes() == b"modelo.ifc"
    antes = publicado.stat().st_ino
    conversao_3d.carregar_payload_viz("programa", publicar_glb=True)
    assert publicado.stat().st_ino == antes


def test_glb_acima_do_teto_nao_e_publicado(sessao_simulada, tmp_path, monkeypatch):
    monkeypatch.setattr(caminhos, "APP_DIR", str(tmp_path / "app"))
    monkeypatch.setattr(conversao_3d, "TETO_ARQUIVO_ESTATICO", 3)
    ifc = tmp_path / "modelo.ifc"
    ifc.write_bytes(b"ISO-10303-21;")
    conversao_3d.iniciar_conversao("bim_gis", str(ifc))
    viz = conversao_3d.carregar_payload_viz("bim_gis", publicar_glb=True)
    assert viz["glb_grande_demais"] is True and "glb_url" not in viz
