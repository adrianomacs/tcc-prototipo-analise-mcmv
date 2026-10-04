"""``UnidadeTipo`` — o grupo de UH que se repete (ADR-023).

Por que é a unidade tipo, e não o prédio
----------------------------------------

A ``Edificacao`` anterior ao ADR-023 — nome, número de unidades, tipologia, um
contêiner — fazia dois papéis que a base de requisitos separa: o prédio FÍSICO
(``IfcBuilding``, pavimentos) e o GRUPO DE UH QUE SE REPETE, que é o que
EDI-001/002/004 consomem e onde "140 casas padrão + 10 PCD" precisa ser
declarado. Os quatro campos descrevem o segundo papel. O ADR-023 dá a ele o
nome certo: **um IFC = uma unidade tipo**, a planta que se repete. A edificação
física é outra entidade, ``dominio/edificacao.py``, ligada a esta por
composição; nada de UH nem de tipologia mora nela.

*Tipologia* e *unidade tipo* são eixos diferentes: tipologia é o eixo normativo
da Portaria (casa × apartamento/casa sobreposta) e continua sendo a dimensão
declarativa do guard, com origem aqui; unidade tipo é a planta. "Padrão" e
"PCD" são duas unidades tipo da **mesma** tipologia.

Por que é magra (ADR-023)
-------------------------

Identidade, nome, número de unidades, tipologia e, no máximo, um ``ModeloBIM``.
Nada de ``UnidadeHabitacional``: sem ``IfcZone``/``IfcSpatialZone`` nos modelos
do acervo não haveria com o que preenchê-la. Quatro torres iguais se exprimem
como quatro unidades tipo apontando para o mesmo contêiner **ou** como uma de
64 unidades com um contêiner de ``unidades_representadas = 4`` — as duas formas
continuam equivalentes (ADR-023); a canônica é a segunda.

``unidades`` é o terceiro número de UH do ADR-021 — **por quantas UHs o veredito
fala**. Não é o denominador de regra dimensional nenhuma: esse é o
``unidades_representadas`` do contêiner efetivamente lido. A diferença entre os
dois é a extrapolação que o proponente faz ao afirmar que a planta se repete —
legítima, e visível agora que os dois números têm dono.

Limitação que **permanece** declarada (ADR-021): um arquivo que mistura tipos
anexado a uma unidade tipo é indetectável — é o EIR que o evita, não o motor.
Anexado a uma edificação física com composição, vira diagnóstico.

Anel: domínio. Nenhum I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.dominio.identidade import novo_id
from core.dominio.modelo_bim import ModeloBIM, contagem_de_uh


@dataclass(eq=False)
class UnidadeTipo:
    """Uma unidade tipo do empreendimento. Igualdade por identidade (``id``).

    Como o ``Empreendimento`` (ADR-004), é entidade: duas unidades tipo com os
    mesmos dados continuam sendo duas. Quem versiona é a raiz do agregado —
    mudar um campo daqui por fora de ``Empreendimento.atualizar_unidade_tipo``
    não faz a versão andar, pela mesma razão que mudar o ``dict`` de declarações
    por fora dos métodos não faz.
    """

    nome: str = ""
    unidades: int = 0
    tipologia: str = ""
    modelo: ModeloBIM | None = None
    id: str = field(default_factory=novo_id)

    def __post_init__(self):
        self.nome = str(self.nome or "").strip()
        self.tipologia = str(self.tipologia or "").strip()
        self.unidades = contagem_de_uh(self.unidades, "unidades")

    def __eq__(self, outro: object) -> bool:
        return isinstance(outro, UnidadeTipo) and outro.id == self.id

    def __hash__(self) -> int:
        return hash(self.id)

    # -- capacidade ---------------------------------------------------------

    @property
    def checavel_por_bim(self) -> bool:
        """Sem ``ModeloBIM`` anexado não há checagem BIM **nesta** unidade tipo.

        É a leitura honesta do que o ADR-023 permite exprimir: a submissão é
        fragmentária, e uma unidade tipo declarada sem contêiner não tem
        geometria a ler — o que não impede as demais de terem a sua.
        """
        return self.modelo is not None

    @property
    def unidades_representadas(self) -> int:
        """Quantas UHs o contêiner **desta** unidade tipo representa (ADR-021).

        Zero sem contêiner: não há entrega a cujo respeito perguntar.
        """
        return self.modelo.unidades_representadas if self.modelo is not None else 0

    # -- serialização (sem I/O) ---------------------------------------------

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "nome": self.nome,
            "unidades": self.unidades,
            "tipologia": self.tipologia,
            "modelo": self.modelo.to_dict() if self.modelo is not None else None,
        }

    @classmethod
    def from_dict(cls, dados: dict | None) -> UnidadeTipo | None:
        if not dados:
            return None
        return cls(
            id=dados.get("id") or novo_id(),
            nome=dados.get("nome", ""),
            unidades=dados.get("unidades", 0),
            tipologia=dados.get("tipologia", ""),
            modelo=ModeloBIM.from_dict(dados.get("modelo")),
        )
