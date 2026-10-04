"""Identidade das entidades do agregado do empreendimento (ADR-004, ADR-023).

Existe porque duas entidades do **mesmo** agregado geram identidade do mesmo
jeito — o ``Empreendimento``, que é a raiz (ADR-004), e a ``UnidadeTipo``
(ADR-023; a antiga ``Edificacao``) que ele contém — e a função não podia
ficar em nenhuma das duas: ``empreendimento`` importa ``unidade_tipo`` para
reconstruir a coleção, e o caminho de volta fecharia um ciclo de import.

Doze dígitos hexadecimais de um ``uuid4``: curto o bastante para caber num
rótulo de tela e num nome de arquivo, largo o bastante para que a colisão não
seja um problema prático em uso normal.

Anel: domínio. Nenhum I/O.
"""

from __future__ import annotations

import uuid


def novo_id() -> str:
    """Identificador curto e estável de uma entidade do agregado."""
    return uuid.uuid4().hex[:12]
