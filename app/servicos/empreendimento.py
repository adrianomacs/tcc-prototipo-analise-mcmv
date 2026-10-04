"""Gateway do `Empreendimento` — único ponto de `app/` que toca
`core.dominio.empreendimento` e `core.infra.persistencia.empreendimento_json`
.

ADR-004: as telas
passam a ler e gravar o `Empreendimento` em vez do `terreno.json` isolado —
o repositório (`core/infra/persistencia/empreendimento_json.py`) já sabe
migrar um `terreno.json` legado na leitura; este módulo só
resolve a pasta de artefatos, do mesmo jeito que `app.servicos.territorio`
resolve o resolvedor de território.
"""

from __future__ import annotations

import os

from core.dominio import ancora
from core.dominio.empreendimento import (  # noqa: F401 (reexportado)
    Edificacao,
    Empreendimento,
    Localizacao,
    ModeloBIM,
    UnidadeTipo,
)
from core.dominio.vocabulario import declaracoes as dec
from core.infra.caminhos import ARTEFATOS
from core.infra.persistencia import empreendimento_json as _repo


def ler() -> Empreendimento | None:
    """O empreendimento gravado, o migrado do `terreno.json` legado, ou
    `None` quando nenhum dos dois existe."""
    return _repo.ler(ARTEFATOS)

def carregar() -> Empreendimento:
    """Como `ler()`, mas nunca `None` — um `Empreendimento` vazio na
    primeira visita, para a tela não ter que tratar dois casos."""
    return ler() or Empreendimento()


def gravar(empreendimento: Empreendimento) -> str:
    """Grava o empreendimento (atomicamente) e devolve o caminho do arquivo."""
    return _repo.gravar(empreendimento, ARTEFATOS)


def ja_gravado() -> bool:
    """Se o `empreendimento.json` já existe em disco.

    A 2.1.1 só grava quando algo mudou (a `versao` andou); a exceção é o
    primeiro gravar, para que um empreendimento migrado do `terreno.json`
    legado ganhe arquivo — e `id` — estável na primeira visita."""
    return os.path.exists(_repo.caminho(ARTEFATOS))


def descartar_declaracoes_fora_do_vocabulario(
        empreendimento: Empreendimento) -> list[str]:
    """Tira das `declaracoes` as chaves que o vocabulário não conhece e
    devolve quais saíram, para a tela avisar — nunca em silêncio.

    O vocabulário é o de `core.dominio.vocabulario.declaracoes`
    (`ROTULO_DIMENSAO`). O caso que motivou é o `num_uhs` que o ADR-021 tirou
    das declarações: nenhuma regra o lê, mas ele vazava para
    `meta.declaracoes` de todo relatório. A leitura do esquema antigo, que
    ainda o consome, roda antes disto, na persistência."""
    fora = sorted(k for k in empreendimento.declaracoes
                  if k not in dec.ROTULO_DIMENSAO)
    if fora:
        empreendimento.declarar({k: v for k, v in empreendimento.declaracoes.items()
                                 if k not in fora})
    return fora


def descartar() -> None:
    """Remove o empreendimento gravado e o `terreno.json` legado (ver o
    docstring de `empreendimento_json.descartar`)."""
    _repo.descartar(ARTEFATOS)


def tipologia(empreendimento: Empreendimento) -> str:
    """A tipologia da unidade tipo do empreendimento, ou `""`.

    Desde o ADR-021 a tipologia é da unidade tipo (`UnidadeTipo`, ADR-023), e
    não mais uma declaração do empreendimento; as telas leem por aqui para não
    voltarem a procurá-la em `declaracoes`."""
    return ancora.tipologia_em_analise(empreendimento)


def referencia_atual() -> dict:
    """`{"id": ..., "versao": ...}` do empreendimento corrente — o que um
    relatório grava em `meta.empreendimento` para uma tela poder
    dizer, sem reler o relatório inteiro, se ele está desatualizado."""
    return carregar().referencia()
