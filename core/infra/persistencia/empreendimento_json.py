"""Repositório do Empreendimento — ``artefatos/empreendimento.json``.

A unidade de persistência da sessão (ADR-004).
**Absorve o ``terreno.json``**: o terreno
passa a ser uma parte do empreendimento gravado, e o arquivo antigo só é lido
como legado, para migração.

Mesmo contrato do ``artefato.py`` que ele generaliza: escrita atômica (arquivo
temporário + ``os.replace``), para que uma leitura concorrente — o Streamlit
reexecuta o script a cada interação — nunca veja JSON parcial; e leitura que
devolve ``None`` em vez de levantar quando o arquivo falta ou está ilegível.

A migração do ``terreno.json``
------------------------------

Sem ``empreendimento.json`` e com ``terreno.json``, ``ler`` devolve um
empreendimento **em memória** com aquele terreno — e com a localização que a
tela já gravava em ``terreno.procedencia["municipio_declarado"]``, o campo do
Terreno que fazia o trabalho de uma entidade que não existia. Nada é
gravado na leitura: o ``id`` só se fixa na primeira ``gravar``. Até lá, cada
leitura legada gera um ``id`` novo, o que é correto — ainda não há empreendimento
persistido para ter identidade.

Os três esquemas do ``empreendimento.json`` (ADR-023)
---------------------------------------------------

Todos migrados **em memória**, na leitura, sem script em disco e sem a
``versao`` andar; nenhuma ``Edificacao`` física é jamais sintetizada.
Discriminação (``unidades_tipo`` presente → E2; senão ``edificacoes`` presente
→ E1; senão E0):

* **E0** — sem a chave ``edificacoes`` (o primeiro esquema): a tipologia e o
  número de UHs eram declarações do empreendimento e o contêiner pendurava-se
  na raiz. Sintetiza-se **uma** ``UnidadeTipo`` ("Unidade tipo 1") com esses
  dados (ADR-021), e o contêiner passa a ser anexado pela natureza declarada
  (ADR-023): ``terreno`` ao ``Terreno``, ``edificacao_isolada`` à unidade tipo,
  ``terreno_com_edificacoes`` aos dois.
* **E1** — ``edificacoes`` presente e ``unidades_tipo`` ausente (anterior ao
  ADR-023, gravado entre os commits ``d59ccf2`` e ``0d9d168``): cada item era
  uma unidade tipo com o nome antigo. Cada um vira ``UnidadeTipo`` com o
  **mesmo** ``id``, nome, unidades, tipologia e ``modelo`` — o ``from_dict`` da
  ``Edificacao`` física ignoraria dois campos e ficaria com o contêiner —, e a
  coleção ``edificacoes`` fica vazia depois de mover tudo.
* **E2** — o esquema vigente, que **sempre** grava ``unidades_tipo``, mesmo
  vazia, para nunca ser confundido com E1.

A chave ``modelo`` na raiz é do E0, e este módulo é o **único** que a
reconhece: o ``Empreendimento`` não tem mais onde guardá-la.
Ela é lida do dicionário cru, anexada a quem o ADR-023 manda — e não volta a
ser gravada. Um artefato já migrado e regravado não a tem, e por isso a leitura
dele não passa mais por aqui.

Ausência de declaração não vira declaração: sem nada a dizer sobre uma unidade
tipo (sem número de UHs, sem tipologia e sem contêiner de edificação), nenhuma
é sintetizada. O piso de 1 UH que as regras EDI aplicam ao ``num_uhs`` ausente
é regra delas, não da persistência — inventá-lo aqui seria gravar como
declarado um número que ninguém declarou.

As telas de entrada do terreno ainda gravam o ``terreno.json`` pelo
``artefato.py``.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import replace
from datetime import datetime, timezone

from core.dominio.empreendimento import Empreendimento, Localizacao
from core.dominio.modelo_bim import ModeloBIM, contagem_de_uh
from core.dominio.unidade_tipo import UnidadeTipo
from core.dominio.vocabulario import declaracoes as dec
from core.infra.persistencia import artefato as legado_terreno

NOME_ARQUIVO = "empreendimento.json"
NOME_UNIDADE_TIPO_SINTETIZADA = "Unidade tipo 1"
# A chave que o esquema E0 usava para o nº de UHs. Ela mora
# aqui, e não no vocabulário de declarações, porque o ADR-021 a tirou de lá: o
# número deixou de ser declaração e virou propriedade da entrega
# (``ModeloBIM.unidades_representadas``). Reconhecê-la é trabalho de migração,
# e migração é deste módulo — mantê-la no vocabulário faria o código novo
# continuar enxergando como dimensão declarativa o que já não é uma.
CHAVE_NUM_UHS_LEGADA = "num_uhs"


def caminho(pasta_artefatos: str) -> str:
    return os.path.join(pasta_artefatos, NOME_ARQUIVO)


def gravar(empreendimento: Empreendimento, pasta_artefatos: str) -> str:
    """Grava o empreendimento (atomicamente) e devolve o caminho do arquivo."""
    os.makedirs(pasta_artefatos, exist_ok=True)
    destino = caminho(pasta_artefatos)
    dados = empreendimento.to_dict()
    dados["gravado_em"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    fd, tmp = tempfile.mkstemp(dir=pasta_artefatos, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
        os.replace(tmp, destino)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return destino


def ler(pasta_artefatos: str) -> Empreendimento | None:
    """O empreendimento gravado; o migrado do ``terreno.json``; ou ``None``.

    Um ``empreendimento.json`` ilegível devolve ``None`` — e **não** cai para o
    ``terreno.json``: ressuscitar um terreno antigo por cima de um empreendimento
    corrompido mostraria ao usuário um estado que ele já tinha substituído.
    """
    origem = caminho(pasta_artefatos)
    if os.path.exists(origem):
        try:
            with open(origem, "r", encoding="utf-8") as f:
                dados = json.load(f)
            empreendimento = Empreendimento.from_dict(dados)
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            return None
        # A chave ``unidades_tipo`` é a assinatura do E2 e é lida PRIMEIRO: um
        # artefato que a traz nunca é migrado, tenha ou não ``edificacoes``.
        if "unidades_tipo" in dados:
            return empreendimento
        if "edificacoes" in dados:
            migrar_esquema_e1(empreendimento, dados)
        else:
            migrar_esquema_e0(
                empreendimento, ModeloBIM.from_dict(dados.get("modelo")))
        return empreendimento
    return migrar_terreno_legado(pasta_artefatos)


def migrar_esquema_e0(empreendimento: Empreendimento,
                      modelo: ModeloBIM | None = None) -> None:
    """Sintetiza a "Unidade tipo 1" de um artefato do esquema E0, em memória.

    ``modelo`` é o contêiner que o artefato antigo guardava na raiz (a chave
    ``modelo``, que o ``Empreendimento`` não tem mais). Vem do
    dicionário cru porque é dado de arquivo, não do objeto: o domínio já não o
    conhece, e é exatamente essa a fronteira.

    Muda o empreendimento **no lugar**, sem passar pelos mutadores do agregado e
    sem incrementar a ``versao``: isto é reconstrução do que o arquivo já dizia
    noutro vocabulário, não mudança do empreendimento. Fazer a versão andar na
    leitura marcaria como desatualizado todo relatório já gravado, e nada teria
    mudado de fato.

    Idempotente por construção: só é chamada quando o artefato não tem a chave
    ``edificacoes``, e o que se grava depois traz ``unidades_tipo`` (E2).
    """
    declaracoes = empreendimento.declaracoes or {}
    unidades = _unidades_declaradas(declaracoes)
    tipologia = str(declaracoes.get(dec.TIPOLOGIA) or "").strip()
    natureza = modelo.natureza if modelo is not None else str(
        declaracoes.get(dec.TIPO_MODELO) or "")

    tem_edificacao = natureza in dec.COM_EDIFICACAO

    conteiner = None
    if modelo is not None:
        # ``unidades_representadas`` é o campo que o esquema antigo não tinha:
        # o contêiner de uma submissão com edificação representa as UHs que
        # foram declaradas; o modelo só do terreno não representa nenhuma.
        conteiner = replace(modelo,
                            unidades_representadas=unidades if tem_edificacao else 0)

    if (conteiner is not None
            and natureza in (dec.TERRENO, dec.TERRENO_COM_EDIFICACOES)
            and empreendimento.terreno is not None
            and empreendimento.terreno.modelo is None):
        empreendimento.terreno.modelo = conteiner

    if not (unidades or tipologia or tem_edificacao):
        return                      # nada declarado sobre unidade tipo nenhuma

    empreendimento.unidades_tipo = [UnidadeTipo(
        nome=NOME_UNIDADE_TIPO_SINTETIZADA, unidades=unidades, tipologia=tipologia,
        modelo=conteiner if tem_edificacao else None)]


def migrar_esquema_e1(empreendimento: Empreendimento, dados: dict) -> None:
    """Move as ``edificacoes`` do esquema E1 para ``unidades_tipo`` (ADR-023).

    Cada item daquela chave era uma unidade tipo com o nome antigo — os quatro
    campos são os mesmos da ``UnidadeTipo`` (ADR-023) —, e volta com o **mesmo**
    ``id``: é a mesma entidade, e trocar-lhe a identidade invalidaria toda
    referência que um relatório guardasse. Lê do dicionário cru, e não do
    objeto, porque o domínio já não reconhece nesses itens uma unidade tipo.

    Como a E0: no lugar, sem mutador e sem a ``versao`` andar — reconstrução
    do que o arquivo dizia noutro vocabulário. A coleção antiga fica vazia
    depois de mover tudo: nenhuma ``Edificacao`` física é sintetizada de
    artefato antigo (ADR-023).
    """
    movidas = [u for u in (UnidadeTipo.from_dict(d)
                           for d in (dados.get("edificacoes") or []))
               if u is not None]
    empreendimento.unidades_tipo = movidas
    # O ``from_dict`` do domínio leu a mesma chave como edificações FÍSICAS
    # (só o contêiner sobreviveria): eram unidades tipo, e já foram movidas.
    empreendimento.edificacoes = []


def _unidades_declaradas(declaracoes: dict) -> int:
    """``num_uhs`` do esquema antigo como contagem de UH; 0 se ausente ou ilegível.

    Ilegível vira 0 em vez de levantar: um artefato com lixo num campo numérico
    ainda tem terreno, localização e declarações que valem — e perder o
    empreendimento inteiro por causa dele seria o oposto do que a leitura
    tolerante deste módulo promete.
    """
    try:
        return contagem_de_uh(declaracoes.get(CHAVE_NUM_UHS_LEGADA), "num_uhs")
    except ValueError:
        return 0


def migrar_terreno_legado(pasta_artefatos: str) -> Empreendimento | None:
    """Empreendimento em memória a partir do ``terreno.json``, ou ``None``."""
    terreno = legado_terreno.ler(pasta_artefatos)
    if terreno is None:
        return None
    declarado = (terreno.procedencia or {}).get("municipio_declarado") or {}
    try:
        localizacao = (Localizacao(codigo_ibge=declarado.get("ibge", ""),
                                   uf=declarado.get("uf", ""),
                                   municipio=declarado.get("nome", ""))
                       if declarado.get("ibge") else None)
    except ValueError:
        # Código inválido no arquivo antigo: o terreno vale, a localização não.
        # A tela pede o município de novo — melhor que inventar um.
        localizacao = None
    return Empreendimento(localizacao=localizacao, terreno=terreno)


def descartar(pasta_artefatos: str) -> None:
    """Remove o empreendimento gravado **e** o ``terreno.json`` legado.

    Os dois: descartar só o novo faria o terreno antigo reaparecer na próxima
    leitura, pela migração.
    """
    for origem in (caminho(pasta_artefatos),
                   legado_terreno.caminho(pasta_artefatos)):
        if os.path.exists(origem):
            os.unlink(origem)
