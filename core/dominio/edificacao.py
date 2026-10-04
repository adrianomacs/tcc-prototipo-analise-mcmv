"""A ``Edificacao`` FÍSICA do empreendimento (ADR-023) e o ``Ambiente``.

Dois papéis que se pareciam e não são a mesma coisa
----------------------------------------------------

A ``Edificacao`` anterior ao ADR-023 (nome, nº de unidades, tipologia, um contêiner)
descrevia o **grupo de UH que se repete** — o que EDI-001/002/004 consomem —
e por isso passou a chamar-se ``UnidadeTipo`` (``dominio/unidade_tipo.py``).
O que mora aqui é o outro papel: o **prédio**, a torre, a casa como objeto
físico — o ``IfcBuilding`` a que EMP-032 e EDI-013 vão um dia se referir, e a
que o pavimento tipo MISTO de hoje precisa ser anexado sem mentir sobre a quem
pertence.

Por que é magra, e opcional
---------------------------

``nome``, um ``ModeloBIM`` opcional e a **composição**: quantas UH de cada
unidade tipo ela contém (``{id da UnidadeTipo → quantidade}``). Nada de nº de
UH próprio nem de tipologia: os dois são derivados da composição, **na raiz**
(``Empreendimento.tipologia_de``, ``unidades_compostas``), porque a edificação
só conhece ids e quem sabe o que eles significam é o agregado. Um loteamento
de 150 casas não precisa enumerar 150 prédios — a ``Edificacao`` é 0..n, e o
caso mais simples não a declara. Campos que NÃO entram enquanto nenhuma regra
ativa os consome (ADR-023): ``pavimentos``, ``adaptada``, o ``IfcBuilding``
correspondente, ``Quadra``/``Lote``.

A composição é dado da edificação; os **invariantes** são da raiz (ADR-004):
só cita unidades tipo do agregado, e todas de uma mesma tipologia — um prédio
casa + apartamento não existe na Portaria. Aqui só se normaliza a forma:
quantidade por ``contagem_de_uh``, e entrada com zero é **removida**, não
guardada — "zero desta" e "nenhuma desta" são a mesma coisa.

``unidades_representadas`` do contêiner anexado continua sendo o **único**
número que uma regra dimensional consome (ADR-021). Um arquivo que mistura
tipos anexa-se aqui e é analisado em agregado, com diagnóstico — nunca
recusado, nunca ``NAO_AVALIAVEL`` (ADR-023).

Anel: domínio. Nenhum I/O — a extração do ``Ambiente`` a partir do IfcOpenShell
fica em ``core/infra/ifc/extrator_ambientes.py``; aqui é só o dado.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.dominio.identidade import novo_id
from core.dominio.modelo_bim import ModeloBIM, contagem_de_uh


@dataclass(eq=False)
class Edificacao:
    """Um prédio do empreendimento. Igualdade por identidade (``id``).

    Entidade, como a ``UnidadeTipo`` e o ``Empreendimento`` (ADR-004): duas
    edificações com os mesmos dados continuam sendo duas. Quem versiona é a
    raiz — mudar um campo daqui por fora de
    ``Empreendimento.atualizar_edificacao`` não faz a versão andar.
    """

    nome: str = ""
    modelo: ModeloBIM | None = None
    composicao: dict[str, int] = field(default_factory=dict)
    id: str = field(default_factory=novo_id)

    def __post_init__(self):
        self.nome = str(self.nome or "").strip()
        self.composicao = self._normalizar_composicao(self.composicao)

    @staticmethod
    def _normalizar_composicao(composicao) -> dict[str, int]:
        """``{id: quantidade}`` com quantidades válidas e sem entradas de zero."""
        normalizada: dict[str, int] = {}
        for id_unidade_tipo, quantidade in dict(composicao or {}).items():
            chave = str(id_unidade_tipo or "").strip()
            numero = contagem_de_uh(quantidade, f"composicao[{chave}]")
            if chave and numero:
                normalizada[chave] = numero
        return normalizada

    def __eq__(self, outro: object) -> bool:
        return isinstance(outro, Edificacao) and outro.id == self.id

    def __hash__(self) -> int:
        return hash(self.id)

    # -- capacidade ---------------------------------------------------------

    @property
    def checavel_por_bim(self) -> bool:
        """Sem ``ModeloBIM`` anexado não há checagem BIM **nesta** edificação."""
        return self.modelo is not None

    @property
    def unidades_representadas(self) -> int:
        """Quantas UHs o contêiner **desta** edificação representa (ADR-021).

        Zero sem contêiner: não há entrega a cujo respeito perguntar.
        """
        return self.modelo.unidades_representadas if self.modelo is not None else 0

    @property
    def unidades_compostas(self) -> int:
        """Total de UH declarado na composição — por quantas UHs um veredito
        sobre esta edificação fala. Zero quando a composição está vazia."""
        return sum(self.composicao.values())

    @property
    def ids_unidades_tipo(self) -> tuple[str, ...]:
        """Os ids das unidades tipo citadas, na ordem em que foram declaradas."""
        return tuple(self.composicao)

    # -- serialização (sem I/O) ---------------------------------------------

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "nome": self.nome,
            "modelo": self.modelo.to_dict() if self.modelo is not None else None,
            "composicao": dict(self.composicao),
        }

    @classmethod
    def from_dict(cls, dados: dict | None) -> Edificacao | None:
        if not dados:
            return None
        return cls(
            id=dados.get("id") or novo_id(),
            nome=dados.get("nome", ""),
            modelo=ModeloBIM.from_dict(dados.get("modelo")),
            composicao=dados.get("composicao") or {},
        )


@dataclass
class Ambiente:
    """Um ambiente do modelo (IfcSpace) com suas propriedades principais."""

    global_id: str
    nome: str                       # LongName > Name > GlobalId
    name: str | None = None         # IfcSpace.Name (bruto)
    long_name: str | None = None    # IfcSpace.LongName (bruto)
    descricao: str | None = None    # IfcSpace.Description
    area_m2: float | None = None
    fonte_area: str | None = None   # de qual quantidade a área foi lida
    classe_ifc: str | None = None   # classe IFC do elemento (ex.: "IfcSpace")

    def to_dict(self) -> dict:
        return {
            "global_id": self.global_id,
            "nome": self.nome,
            "name": self.name,
            "long_name": self.long_name,
            "descricao": self.descricao,
            "area_m2": self.area_m2,
            "fonte_area": self.fonte_area,
            "classe_ifc": self.classe_ifc,
        }
