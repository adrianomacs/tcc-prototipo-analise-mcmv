"""A porta Roteador (Protocol) e as constantes de provedor/metrica.

Duas implementacoes: a
de linha reta, sem I/O, no proprio dominio (core/dominio/euclidiana.py, o
piso do ADR-013), e a de rede em core/infra/rede/ors.py. Trocar de provedor nao toca em
regra nenhuma — a regra pergunta ao dado (Medicao.limite_inferior) se ele
conclui, nunca ao nome do provedor.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from core.dominio.mobilidade import Medicao

# --- Provedores -------------------------------------------------------------
PROVEDOR_EUCLIDIANA = "euclidiana"
PROVEDOR_ORS = "ors"
# Não há PROVEDOR_GOOGLE: o Google Routes está fora do escopo.

# --- Métricas ---------------------------------------------------------------
METRICA_LINHA_RETA = "linha_reta"
METRICA_REDE_PEDESTRE = "rede_pedestre"

ROTULO_METRICA = {
    METRICA_LINHA_RETA: "distância em linha reta (piso)",
    METRICA_REDE_PEDESTRE: "distância caminhável em rede",
}


@runtime_checkable
class Roteador(Protocol):
    """O que qualquer provedor precisa oferecer.

    ``limite_inferior`` é atributo do **provedor**, não de cada chamada: ele diz
    de que lado aquele provedor erra, e é o que o torna plugável sem que as
    regras saibam qual é.
    """

    provedor: str
    metrica: str
    limite_inferior: bool

    def medir(self, origem: tuple[float, float], destinos: list[Any],
              chaves: list[str] | None = None) -> list[Medicao]:
        """``origem`` é (lat, lon) em WGS 84; ``destinos`` são Equipamentos.

        ``chaves`` deixa o **chamador declarar a identidade** de cada destino.
        """
        ...
