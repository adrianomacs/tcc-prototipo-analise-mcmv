"""Impressão digital (SHA-256) de um arquivo submetido.

O relatório de uma checagem cita o arquivo que consumiu pelo nome, e nome não
identifica conteúdo: o mesmo ``E1_georref.ifc`` reexportado é outro arquivo.
O SHA-256 do conteúdo, calculado por quem o consumiu e gravado no relatório,
é o que amarra o resultado ao insumo de forma inequívoca (ADR-035).

É I/O, por isso mora aqui e não no domínio (``ModeloBIM.digest`` só guarda o
valor). A leitura é em blocos: o custo é o de uma passada no arquivo, pequeno
perto de abri-lo com o IfcOpenShell.
"""

from __future__ import annotations

import hashlib
import os

_BLOCO = 1 << 20


def sha256(caminho: str | None) -> str:
    """SHA-256 do conteúdo em hexadecimal, ou ``""`` sem arquivo legível —
    ausência de impressão nunca derruba a análise; o relatório a declara."""
    if not caminho or not os.path.isfile(caminho):
        return ""
    h = hashlib.sha256()
    try:
        with open(caminho, "rb") as arquivo:
            for bloco in iter(lambda: arquivo.read(_BLOCO), b""):
                h.update(bloco)
    except OSError:
        return ""
    return h.hexdigest()
