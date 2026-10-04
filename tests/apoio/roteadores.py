"""Provedor de rede falso, reutilizado pelos testes das regras ENQ e de
agregação.

Extraído de ``tests/test_regras_enq_rede.py`` — apoio compartilhado.
"""

from __future__ import annotations

from core.dominio import mobilidade as rot
from core.dominio.contratos import roteador as rot_rot


class RoteadorFalso:
    """Provedor de rede que devolve metros fixos. Registra o que recebeu."""

    provedor = rot_rot.PROVEDOR_ORS
    metrica = rot_rot.METRICA_REDE_PEDESTRE
    limite_inferior = False

    def __init__(self, metros=800.0, *, procedencia=True, erro=None):
        self.metros = metros
        self.procedencia = procedencia
        self.erro = erro
        self.chamadas: list[dict] = []

    def medir(self, origem, destinos, chaves=None):
        self.chamadas.append({"origem": origem, "destinos": list(destinos),
                              "chaves": list(chaves) if chaves else None})
        if self.erro is not None:
            raise self.erro
        detalhe = ({"graph_date": "2026-08-28T12:16:53Z",
                    "osm_date": "2026-08-17T00:00:02Z", "version": "9.10.0"}
                   if self.procedencia else {})
        saida = []
        for i, e in enumerate(destinos):
            chave = chaves[i] if chaves else str(i)
            saida.append(rot.Medicao(
                destino=chave, rotulo=getattr(e, "nome", ""),
                metros=self.metros, segundos=self.metros / 1.4,
                provedor=self.provedor, metrica=self.metrica,
                limite_inferior=False, snap_m=8.55, detalhe=dict(detalhe)))
        return saida

