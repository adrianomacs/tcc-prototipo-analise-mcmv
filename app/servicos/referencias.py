"""Serviço de leitura da lista de referências do trabalho.

Fonte da verdade: `docs/tcc/referencias.yaml`, a lista de referências do
trabalho, no formato USP/ESALQ. A página 1.2.9
(`app/paginas/pesquisa/referencias.py`) só exibe o que este serviço devolve,
para que a página e o texto nunca divirjam.

A ordem é alfabética pelo texto da referência, sem distinguir maiúsculas nem
acentos (o "buildingSMART" minúsculo e o "Associação" acentuado entram no
lugar certo); a ordem em que as entradas aparecem no arquivo não importa.
Obra marcada com ``citada: false`` fica registrada no arquivo, mas fora da
lista, porque o texto vigente não a cita.
"""

from __future__ import annotations

import os
import unicodedata
from dataclasses import dataclass

import yaml

from core.infra.caminhos import RAIZ

ARQUIVO = os.path.join(RAIZ, "docs", "tcc", "referencias.yaml")


@dataclass(frozen=True)
class Referencia:
    chave: str
    texto: str
    validar: bool = False
    nota: str = ""
    citada: bool = True


def chave_de_ordem(texto: str) -> str:
    """Texto sem acentos e em minúsculas, para a ordem alfabética."""
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return sem_acento.casefold()


def carimbo_das_referencias() -> float:
    """Data de modificação do arquivo, para a chave do cache da página."""
    return os.path.getmtime(ARQUIVO)


def carregar_referencias(caminho: str = ARQUIVO,
                         so_citadas: bool = True) -> list[Referencia]:
    """Lê o arquivo e devolve as referências em ordem alfabética; por padrão,
    só as que o texto vigente cita, como uma lista de referências."""
    with open(caminho, encoding="utf-8") as f:
        dados = yaml.safe_load(f) or []
    refs = [
        Referencia(
            chave=str(d["chave"]),
            texto=str(d["texto"]).strip(),
            validar=bool(d.get("validar", False)),
            nota=str(d.get("nota", "") or ""),
            citada=bool(d.get("citada", True)),
        )
        for d in dados
    ]
    if so_citadas:
        refs = [r for r in refs if r.citada]
    return sorted(refs, key=lambda r: chave_de_ordem(r.texto))
