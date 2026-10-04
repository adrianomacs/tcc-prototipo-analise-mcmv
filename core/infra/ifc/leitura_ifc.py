"""``LeituraIFC`` — a implementação da porta ``LeituraModelo`` sobre o modelo
aberto pelo IfcOpenShell (ADR-036).

Não lê nada por conta própria: cada método delega ao leitor que já é o dono
daquela leitura (``extrator_ambientes``, ``classificacao_covering``,
``leitor_modelo``, ``georref.ancora``, ``georref.consistencia``,
``georref.procedencia``), chamado **na hora** — de modo que a leitura continua
tardia, dentro do ``checar`` da regra, e um teste que troque a função do
leitor vê a troca. Quem a constrói é a composição (``core/composicao.py``).
"""

from __future__ import annotations

from typing import Any

from core.infra.ifc import classificacao_covering, extrator_ambientes, leitor_modelo
from core.infra.ifc.georref import ancora, consistencia, procedencia


class LeituraIFC:
    """O modelo IFC aberto, pelas perguntas que as regras fazem a ele."""

    metodo_ambientes = extrator_ambientes.METODO
    origem_hospedeiro = classificacao_covering.ORIGEM_HOSPEDEIRO

    def __init__(self, modelo: Any) -> None:
        self.modelo = modelo

    # -- ambientes -----------------------------------------------------------
    def triar_ambientes(self):
        return extrator_ambientes.triar(self.modelo)

    # -- revestimentos -------------------------------------------------------
    def classificar_revestimentos(self):
        return classificacao_covering.classificar_por_hospedeiro(self.modelo)

    def predefinido(self, elemento: Any) -> str | None:
        return classificacao_covering.predefinido(elemento)

    def propriedade_de_pset(self, elemento: Any, pset: str, *chaves: str):
        return leitor_modelo.propriedade_de_pset(elemento, pset, *chaves)

    def materiais_do_elemento(self, elemento: Any) -> list:
        return leitor_modelo.materiais_do_elemento(elemento)

    def propriedades_do_elemento(self, elemento: Any) -> dict:
        return leitor_modelo.propriedades_do_elemento(elemento)

    # -- georreferenciamento -------------------------------------------------
    def derivar_ancora(self):
        return ancora.derivar(self.modelo)

    def consistencia_localizacao(self):
        return consistencia.avaliar(self.modelo)

    def procedencia_georreferenciamento(self) -> dict:
        return procedencia.extrair(self.modelo)
