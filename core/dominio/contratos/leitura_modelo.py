"""A porta ``LeituraModelo`` (Protocol): o que as regras leem do modelo BIM.

Até o ADR-036 as regras BIM importavam os *helpers* de ``core/infra/ifc/``
diretamente — a exceção (a) do ADR-002. A porta inverte essa dependência do
mesmo modo que o ``Roteador`` e as ``FontesTerritoriais``: o contrato mora
aqui, a implementação sobre o IfcOpenShell mora em
``core/infra/ifc/leitura_ifc.py``, e quem a constrói e a injeta em
``Contexto.leitura_modelo`` é a composição (``core/composicao.py``).

O que ela NÃO é: uma camada anticorrupção completa. Os métodos devolvem o que
os leitores já devolvem — a triagem de ambientes (``Ambiente`` é do domínio),
a partição dos revestimentos, os próprios elementos IFC para as consultas de
propriedade —, e a regra continua sabendo que um revestimento tem property
set. A porta decide QUEM lê o arquivo; traduzir o modelo inteiro para
entidades do domínio segue fora do escopo (ADR-036).

A leitura é tardia: cada método roda quando a regra o chama, dentro do
``checar``, e uma exceção ali continua isolada por regra pelo executor.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LeituraModelo(Protocol):
    """O modelo aberto, pelas perguntas que as regras fazem a ele."""

    #: Como a largura de um ambiente é medida — vai para o detalhe das regras.
    metodo_ambientes: str
    #: Rótulo da partição quando o lado do revestimento veio do hospedeiro.
    origem_hospedeiro: str

    # -- ambientes (EDI-001/002, 004, 007/008/009, 011) ----------------------
    def triar_ambientes(self) -> Any:
        """A triagem da população de ambientes (``populacao``, ``fora``…)."""
        ...

    # -- revestimentos (absortância: ramos do EDI-019 e do EDI-024) ----------
    def classificar_revestimentos(self) -> Any:
        """A partição dos ``IfcCovering`` em parede, cobertura e não classificados."""
        ...

    def predefinido(self, elemento: Any) -> str | None:
        ...

    def propriedade_de_pset(self, elemento: Any, pset: str, *chaves: str
                            ) -> tuple[Any, str]:
        ...

    def materiais_do_elemento(self, elemento: Any) -> list:
        ...

    def propriedades_do_elemento(self, elemento: Any) -> dict:
        ...

    # -- georreferenciamento (EMP-001) ---------------------------------------
    def derivar_ancora(self) -> Any:
        """A âncora geográfica do modelo (``lat``, ``lon``, ``modo``…)."""
        ...

    def consistencia_localizacao(self) -> Any:
        """Endereço, lat/long do site e CRS cruzados (``to_dict()``)."""
        ...

    def procedencia_georreferenciamento(self) -> dict:
        ...
