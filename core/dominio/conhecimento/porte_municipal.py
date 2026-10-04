"""Porte populacional do município — o valor resolvido e as faixas de cada item.

O porte condiciona requisitos da Portaria MCID 725 (limite de UH por
empreendimento no Anexo II, item 4.I.a; equipamentos de assistência social no
Anexo I). Ele **não é declarado pelo usuário**: é fato censitário do
território, derivado do município (ADR-030) e resolvido pela aplicação antes
do motor, no mesmo caminho da zona bioclimática (ADR-011).

Este módulo é o anel de domínio: define **o que** a população resolvida é e
como uma população cai numa faixa. A leitura do snapshot mora em
``core/infra/gis/csv_municipios`` — o ``dominio/`` não faz I/O.

Por que a população viaja, e não um token de porte
--------------------------------------------------

A Portaria não tem **uma** tabela de porte: cada item traz a sua. O item
4.I.a do Anexo II corta em 20, 50, 100 e 500 mil habitantes; o Anexo I corta
em 100 e 250 mil. Um token único (``ate_100k``…) serviria a um item e mentiria
para o outro. Por isso o que chega ao ``Contexto`` é a população do Censo,
com a procedência junto, e cada regra a classifica pela tabela **do próprio
item** (ADR-030).
"""

from __future__ import annotations

from dataclasses import dataclass

# Procedência fixa: o Censo Demográfico 2022, nunca a estimativa anual (ADR-030).
FONTE_CENSO_2022 = "IBGE — Censo Demográfico 2022, SIDRA tabela 4714"
REFERENCIA_CENSO_2022 = "2022-07-31"


@dataclass(frozen=True)
class PopulacaoMunicipal:
    """A população de um município, com a procedência — nunca o número solto.

    ``densidade`` (hab/km²) viaja junto porque sai da mesma consulta e é o
    insumo do ENQ-001.1; é opcional porque nenhuma regra ativa a consome.
    """

    codigo_ibge: str
    populacao: int
    densidade: float | None = None
    fonte: str = FONTE_CENSO_2022
    referencia: str = REFERENCIA_CENSO_2022

    def __post_init__(self) -> None:
        if isinstance(self.populacao, bool) or not isinstance(self.populacao, int):
            raise TypeError(f"População deve ser inteiro; recebido {self.populacao!r}.")
        if self.populacao < 1:
            raise ValueError(f"População deve ser positiva; recebido {self.populacao}.")


@dataclass(frozen=True)
class FaixaDePorte:
    """Uma linha de uma tabela de porte: até quantos habitantes, e o que vale ali.

    ``ate`` é o limite superior **inclusive** ("até 20.000 habitantes"); a
    última faixa de uma tabela tem ``ate=None`` ("acima de 500.000"). Os
    limites da Portaria são inteiros e contíguos (20.000 / 20.001), então
    inclusivo em cima não deixa buraco nem sobreposição.
    """

    rotulo: str
    ate: int | None
    valores: tuple[int, ...]


def faixa(populacao: int, tabela: tuple[FaixaDePorte, ...]) -> FaixaDePorte:
    """A faixa da tabela em que a população cai."""
    for linha in tabela:
        if linha.ate is None or populacao <= linha.ate:
            return linha
    raise ValueError("Tabela de porte sem faixa aberta no topo.")


# --- Anexo II, item 4.I.a — porte do empreendimento --------------------------
# (limite por empreendimento, limite do grupo de contíguos), em UH.
PORTE_EMPREENDIMENTO_4_I_A: tuple[FaixaDePorte, ...] = (
    FaixaDePorte("até 20.000 habitantes", 20_000, (50, 200)),
    FaixaDePorte("de 20.001 a 50.000 habitantes", 50_000, (100, 300)),
    FaixaDePorte("de 50.001 a 100.000 habitantes", 100_000, (150, 400)),
    FaixaDePorte("de 100.001 a 500.000 habitantes", 500_000, (250, 500)),
    FaixaDePorte("acima de 500.000 habitantes", None, (300, 750)),
)
