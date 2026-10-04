"""``ModeloBIM`` — o contêiner de informação apresentado, como objeto de valor.

Saiu de ``empreendimento.py`` porque **deixou de ser propriedade do
empreendimento** (ADR-023): passa a ser anexável à ``UnidadeTipo``
e ao ``Terreno``, 0..1 cada. Deixá-lo onde estava fecharia um ciclo de import assim
que o terreno o referenciasse, já que ``empreendimento`` importa ``terreno``.

Objeto de valor, não entidade
-----------------------------

Não tem identidade própria: dois contêineres com os mesmos campos são o mesmo
contêiner. O ADR-023 o classifica como objeto de valor, e não como entidade. Daí o
``frozen=True``: quem
precisa de uma variação usa ``dataclasses.replace``, como o pipeline já fazia
para carimbar o ``schema`` lido do arquivo aberto.

``unidades_representadas``
--------------------------

É o segundo dos três números de UH do ADR-021 — a **propriedade da entrega** —,
e o único que uma regra dimensional pode consumir: 1 para a casa isolada, 4 para
o pavimento tipo com quatro apartamentos, 0 para o modelo só do terreno. Não é
quantas UHs o empreendimento terá (``Empreendimento.unidades_previstas``) nem
por quantas o veredito fala (``UnidadeTipo.unidades``).

``natureza`` é o valor de ``vocabulario/declaracoes.py:TIPO_MODELO`` (terreno,
edificação isolada, terreno com edificações) — é por ela que o ADR-023 decide a
quem o contêiner enviado numa tela é anexado. ``digest`` é o SHA-256 do
conteúdo, calculado fora daqui (seria I/O): o pipeline o carimba no contêiner
da execução ao abrir o arquivo, e o relatório o registra (ADR-035). Declarado
pela tela, fica vazio.

Anel: domínio. Nenhum I/O — ``to_dict``/``from_dict`` produzem e consomem
dicionários; quem grava é ``infra/persistencia/``.
"""

from __future__ import annotations

from dataclasses import dataclass


def contagem_de_uh(valor, campo: str) -> int:
    """Valida uma das contagens de UH do ADR-021: inteiro, nunca negativo.

    Mora aqui, e não num módulo próprio, porque os três números do ADR-021 são a
    mesma grandeza contada em lugares diferentes, e os dois módulos que declaram
    os outros dois (``unidade_tipo`` e ``empreendimento``) já importam este.

    Zero é legítimo e frequente — o modelo só do terreno representa zero UH, e um
    empreendimento recém-criado ainda não previu nenhuma. Negativo não é.
    """
    try:
        numero = int(valor or 0)
    except (TypeError, ValueError):
        raise ValueError(
            f"{campo} deve ser um número inteiro de UHs; recebido {valor!r}."
        ) from None
    if numero < 0:
        raise ValueError(f"{campo} não pode ser negativo; recebido {numero}.")
    return numero


@dataclass(frozen=True)
class ModeloBIM:
    """Referência ao contêiner IFC apresentado — não o modelo aberto.

    O modelo aberto (o objeto do IfcOpenShell) é serviço de execução e vive no
    ``Contexto`` (ADR-004); aqui fica só a referência.
    """

    caminho: str = ""
    schema: str = ""
    natureza: str = ""
    digest: str = ""
    unidades_representadas: int = 0

    def __post_init__(self):
        object.__setattr__(
            self, "unidades_representadas",
            contagem_de_uh(self.unidades_representadas, "unidades_representadas"))

    def to_dict(self) -> dict:
        return {"caminho": self.caminho, "schema": self.schema,
                "natureza": self.natureza, "digest": self.digest,
                "unidades_representadas": self.unidades_representadas}

    @classmethod
    def from_dict(cls, dados: dict | None) -> ModeloBIM | None:
        if not dados:
            return None
        return cls(caminho=dados.get("caminho", ""), schema=dados.get("schema", ""),
                   natureza=dados.get("natureza", ""),
                   digest=dados.get("digest", ""),
                   unidades_representadas=dados.get("unidades_representadas", 0))
