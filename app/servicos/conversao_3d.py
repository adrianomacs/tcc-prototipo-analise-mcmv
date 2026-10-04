"""Conversão da visualização 3D em segundo plano (desacoplada da análise).

`pasta_tiles(chave)` vem de `core.infra.caminhos`.

Isolamento por `chave` de checagem: o job de conversão e a pasta de tiles em
disco não são compartilhados entre checagens — do contrário a checagem mais
recente "vazaria" seu modelo/ambientes 3D para o relatório de outra, se ambas
fossem abertas na mesma sessão do Streamlit. Cada
checagem tem seu próprio job (`chaves.chave_viz_job_id`/`chave_viz_future`)
e sua própria subpasta (`core.infra.caminhos.pasta_tiles`).

**A conversão roda em PROCESSO próprio, não em thread** (não em thread). Uma
thread disputaria o GIL com o servidor do Streamlit: a
iteração de geometria do IfcOpenShell é trabalho pesado dentro do mesmo
processo, e enquanto ela rodava o app inteiro ficava sem resposta — menu
inclusive. Um processo separado devolve a responsividade, e não muda o
contrato: a conversa entre o conversor e a interface sempre foi o
``status.json``/artefatos em disco (ADR-001), nunca memória compartilhada —
o ``Future`` guardado na sessão jamais era lido. O que fica na sessão agora
é o handle do processo, usado apenas para detectar morte silenciosa
(processo que terminou sem gravar estado).

**Cache pelo conteúdo do IFC**. A identidade do job era
``sha1(caminho + mtime)``, e o upload regrava o arquivo a cada envio — o mesmo
IFC reenviado convertia de novo (~4 min no T+1). Agora a identidade é o
sha256 do CONTEÚDO mais o que muda o resultado (âncora manual, tipos
excluídos). A conversão concluída é guardada em
``artefatos/cache/tiles/<identidade>/``; um novo envio do mesmo conteúdo copia
de lá para ``pasta_tiles(chave)`` e marca ``pronto`` sem disparar processo. O
contrato não muda: quem lê continua lendo o ``status.json`` da checagem.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys

import streamlit as st

from app.estado import chaves
from core.infra import caminhos, impressao_digital
from core.infra.caminhos import RAIZ, pasta_tiles

# IfcSpace É incluído no GLB: entra oculto e é revelado na seleção. Excluem-se
# só categorias que poluem a cena.
_EXCLUIR_VIZ = ["IfcOpeningElement", "IfcAnnotation", "IfcGrid", "IfcGridAxis"]

# Versão do que a conversão grava na pasta de tiles. Entra na identidade do
# job: mudou o conjunto de artefatos (a 2 acrescentou o ``revestimentos.json``,
# ADR-001), as conversões guardadas no cache deixam de casar e o próximo envio
# converte de novo, em vez de copiar uma pasta que não tem o arquivo novo.
_VERSAO_CONVERSAO = 2


def _job_id(caminho_ifc: str, ancora_manual: dict | None = None,
            excluir: list[str] | None = None) -> str:
    """Identidade da conversão: CONTEÚDO do IFC + parâmetros que mudam o
    resultado. Caminho e mtime não entram — o upload regrava o
    arquivo a cada envio, e o mesmo conteúdo tem de dar a mesma identidade.

    O SHA-256 é o mesmo que o relatório grava (``impressao_digital``,
    ADR-035), uma implementação só. Arquivo ilegível cai no caminho
    (identidade não reaproveitável, mas o disparo segue e o erro aparece pelo
    ``status.json``, como antes)."""
    conteudo = impressao_digital.sha256(caminho_ifc) or f"ilegivel:{caminho_ifc}"
    params = json.dumps({"ancora": ancora_manual,
                         "excluir": _EXCLUIR_VIZ if excluir is None else excluir,
                         "versao": _VERSAO_CONVERSAO},
                        sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(f"{conteudo}|{params}".encode()).hexdigest()[:16]


def _cache_pronto(jid: str) -> str | None:
    """Pasta do cache para ``jid``, se houver conversão ``pronto`` guardada."""
    from core.infra.exportadores import visualizacao

    pasta = caminhos.pasta_cache_tiles(jid)
    status = visualizacao.ler_status(pasta)
    if status.get("estado") == "pronto" and status.get("job_id") == jid:
        return pasta
    return None


def _copiar_pasta(origem: str, destino: str) -> None:
    """Substitui ``destino`` por uma cópia de ``origem``."""
    if os.path.isdir(destino):
        shutil.rmtree(destino, ignore_errors=True)
    shutil.copytree(origem, destino, dirs_exist_ok=True)


def _guardar_no_cache(pasta: str, jid: str) -> None:
    """Guarda a conversão concluída da checagem no cache (uma vez por
    identidade). Grava numa pasta temporária e renomeia, para que um cache
    pela metade nunca seja lido como ``pronto``. Falha de disco não é erro
    da conversão — o relatório já tem o que precisa; só perde o atalho."""
    if _cache_pronto(jid):
        return
    destino = caminhos.pasta_cache_tiles(jid)
    temporario = f"{destino}.tmp{os.getpid()}"
    try:
        shutil.copytree(pasta, temporario, dirs_exist_ok=True)
        if os.path.isdir(destino):
            shutil.rmtree(destino, ignore_errors=True)
        os.replace(temporario, destino)
    except OSError:
        shutil.rmtree(temporario, ignore_errors=True)


def _comando(caminho_ifc: str, pasta: str, job_id: str,
             ancora_manual: dict | None,
             excluir: list[str] | None = None) -> list[str]:
    """Linha de comando do conversor — o CLI de `core.infra.exportadores.
    visualizacao`, no MESMO interpretador que roda o app."""
    args = [sys.executable, "-m", "core.infra.exportadores.visualizacao",
            caminho_ifc, pasta, "--job-id", job_id,
            "--excluir", ",".join(_EXCLUIR_VIZ if excluir is None else excluir)]
    if ancora_manual:
        args += ["--ancora", json.dumps(ancora_manual, ensure_ascii=False)]
    return args


def _disparar(caminho_ifc: str, pasta: str, job_id: str,
              ancora_manual: dict | None, excluir: list[str] | None = None):
    """Dispara o conversor em processo próprio e devolve o handle.

    stdout/stderr vão para ``conversao.log`` na pasta de tiles da checagem —
    o veredito da conversão continua sendo o ``status.json`` (ADR-001); o log
    existe para o traceback não se perder quando o processo morre.
    """
    os.makedirs(pasta, exist_ok=True)
    with open(os.path.join(pasta, "conversao.log"), "wb") as log:
        return subprocess.Popen(
            _comando(caminho_ifc, pasta, job_id, ancora_manual, excluir),
            cwd=str(RAIZ), stdout=log, stderr=subprocess.STDOUT)


def iniciar_conversao(chave: str, caminho_ifc: str,
                      ancora_manual: dict | None = None) -> None:
    """Marca o job da checagem `chave` como 'processando' e dispara a
    conversão num processo separado — ou, se o mesmo conteúdo já foi
    convertido com os mesmos parâmetros, copia do cache e marca 'pronto'
    sem processo nenhum.

    ``ancora_manual`` (posicionamento aproximado) só é usada pelo exportador
    quando o modelo não tem âncora geográfica derivável.
    """
    from core.infra.exportadores import visualizacao

    # O modelo inteiro, revestimentos inclusive, em toda checagem: o acabamento
    # da fachada está neles, e uma conversão só por IFC serve a todas pelo cache.
    excluir = list(_EXCLUIR_VIZ)
    jid = _job_id(caminho_ifc, ancora_manual, excluir)
    st.session_state[chaves.chave_viz_job_id(chave)] = jid
    pasta = pasta_tiles(chave)
    cache = _cache_pronto(jid)
    if cache:
        try:
            _copiar_pasta(cache, pasta)
            st.session_state[chaves.chave_viz_future(chave)] = None
            return
        except OSError:
            pass  # cache inutilizável: converte de novo, como sem cache
    # Estado inicial gravado de forma síncrona: a 1ª renderização já vê 'processando'.
    visualizacao.escrever_status(pasta, estado="processando", job_id=jid)
    try:
        processo = _disparar(caminho_ifc, pasta, jid, ancora_manual, excluir)
    except Exception as exc:  # interpretador/spawn indisponível: erro visível, não eterno
        visualizacao.escrever_status(pasta, estado="erro", job_id=jid, erro=str(exc))
        processo = None
    st.session_state[chaves.chave_viz_future(chave)] = processo


def estado_viz(chave: str) -> str:
    """Estado da conversão da checagem `chave`: processando | pronto | erro."""
    from core.infra.exportadores import visualizacao

    jid = st.session_state.get(chaves.chave_viz_job_id(chave))
    status = visualizacao.ler_status(pasta_tiles(chave))
    if not jid or status.get("job_id") != jid:
        return "processando"  # job recém-disparado ou status de análise anterior
    estado = status.get("estado", "processando")
    if estado == "processando":
        # Morte silenciosa: o processo terminou com erro SEM gravar o status
        # (ex.: interpretador abortado). Sem esta guarda, o botão ficaria em
        # "processando…" para sempre. Saída 0 ainda em 'processando' é só a
        # janela entre a gravação e esta leitura — o próximo tick resolve.
        processo = st.session_state.get(chaves.chave_viz_future(chave))
        poll = getattr(processo, "poll", None)
        if callable(poll) and poll() not in (None, 0):
            return "erro"
    elif estado == "pronto":
        _guardar_no_cache(pasta_tiles(chave), jid)
    return estado


def carregar_payload_viz(chave: str, *, publicar_glb: bool = False) -> dict:
    """`core.infra.exportadores.visualizacao.carregar_payload`, por trás do gateway —
    usado pelas páginas de relatório para montar a cena 3D da checagem `chave`.

    Com ``publicar_glb`` o GLB não vai embutido na cena: é publicado como
    arquivo estático do app e a cena o carrega pelo endereço (``glb_url``).
    Embutido em base64, ele crescia um terço e o HTML do E3 passava do teto
    do Streamlit para arquivo estático; publicado, a cena tem poucos KB.
    Acima do teto nem o GLB sozinho é servido, e o payload diz isso
    (``glb_grande_demais``) para a página explicar em vez de exibir erro.
    """
    from core.infra.exportadores import visualizacao
    if not publicar_glb:
        return visualizacao.carregar_payload(pasta_tiles(chave))
    viz = visualizacao.carregar_payload(pasta_tiles(chave), embutir_glb=False)
    origem = viz.get("glb_caminho")
    if not origem or not os.path.isfile(origem):
        return viz
    tamanho = os.path.getsize(origem)
    viz["glb_mb"] = round(tamanho / (1024 * 1024))
    if tamanho > TETO_ARQUIVO_ESTATICO:
        viz["glb_grande_demais"] = True
        return viz
    viz["glb_url"] = _publicar_glb(chave, origem)
    return viz


# Teto do Streamlit para servir um arquivo estático (constante da biblioteca,
# ``MAX_APP_STATIC_FILE_SIZE``, sem opção de configuração): acima dele a
# resposta é "File is too large".
TETO_ARQUIVO_ESTATICO = 200 * 1024 * 1024


def _publicar_glb(chave: str, origem: str) -> str:
    """Põe o GLB da checagem em ``app/static/modelos/<chave>.glb`` e devolve a
    URL servida, com a data da conversão como cache-bust.

    Só copia quando a conversão mudou (tamanho ou data diferentes): o
    relatório reabre muitas vezes e o GLB do E3 tem 170 MB. Tenta primeiro o
    vínculo físico (mesmo disco, custo zero) e cai na cópia. Grava por nome
    temporário e renomeia, para a cena nunca ler um GLB pela metade.
    """
    pasta = os.path.join(caminhos.APP_DIR, "static", "modelos")
    os.makedirs(pasta, exist_ok=True)
    destino = os.path.join(pasta, f"{chave}.glb")
    st_origem = os.stat(origem)
    try:
        st_destino = os.stat(destino)
        atual = (st_destino.st_size == st_origem.st_size
                 and int(st_destino.st_mtime) == int(st_origem.st_mtime))
    except OSError:
        atual = False
    if not atual:
        temporario = f"{destino}.tmp{os.getpid()}"
        try:
            try:
                os.link(origem, temporario)
            except OSError:
                shutil.copy2(origem, temporario)
            os.replace(temporario, destino)
        except OSError:
            # No Windows, o destino aberto pelo servidor recusa a troca; a
            # cena segue com o GLB publicado antes, e a próxima abertura tenta
            # de novo.
            try:
                os.remove(temporario)
            except OSError:
                pass
    return f"/app/static/modelos/{chave}.glb?v={int(st_origem.st_mtime)}"


def ler_status_viz(chave: str) -> dict:
    """`core.infra.exportadores.visualizacao.ler_status`, por trás do gateway."""
    from core.infra.exportadores import visualizacao
    return visualizacao.ler_status(pasta_tiles(chave))
