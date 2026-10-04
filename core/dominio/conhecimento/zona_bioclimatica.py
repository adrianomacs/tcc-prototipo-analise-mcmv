"""Zona bioclimática — o valor resolvido e as doze classes da norma vigente.

A zona condiciona uma família de requisitos do Anexo III da Portaria MCID 725
(absortância de parede e de telhado, ático, ventilação, esquadrias). Ela **não
é declarada pelo usuário**: é atributo do território, derivado do município
(ADR-030) e resolvido pela aplicação antes do motor (ADR-011).

Este módulo é o anel de domínio: define **o que** uma zona é e não sabe de onde
ela vem. A leitura do arquivo mora em ``core/infra/gis/csv_zonas_bioclimaticas``
— o ``dominio/`` não faz I/O (ADR-002), como a do snapshot de municípios, em
``core/infra/gis/csv_municipios``.

Doze classes, não oito
----------------------

A edição vigente, ABNT TR 15220-3-1:2024, tem doze classes e **não tem zona 7
nem 8**; a numeração tampouco se preserva ante a NBR 15220-3:2005 (São Paulo
era Z3 e é 2M). Cláusula da Portaria ainda escrita no vocabulário de 2005 não é
traduzida para cá — ver a DN-08.
"""

from __future__ import annotations

from dataclasses import dataclass

# As doze classes da ABNT TR 15220-3-1:2024, na ordem da norma. É vocabulário
# fechado: classe fora daqui é erro de base, não zona desconhecida.
CLASSES: tuple[str, ...] = ("1M", "1R", "2M", "2R", "3A", "3B",
                            "4A", "4B", "5A", "5B", "6A", "6B")

# Valores da coluna ``fonte`` do snapshot que produzem zona.
FONTE_NORMA = "ABNT_TR_15220-3-1_2024"
FONTE_HERANCA = "HERANCA_MUNICIPIO_DE_ORIGEM"


@dataclass(frozen=True)
class ZonaBioclimatica:
    """A zona de um município, com a procedência junto — nunca a classe solta.

    A procedência viaja com o valor porque o ADR-030 proíbe **herança
    silenciosa**: município instalado depois da base de localidades da norma
    herda a zona dos municípios de origem quando eles concordam, e quem consome
    a zona tem de poder dizer isso no relatório. ``fonte`` e ``origens`` são o
    que torna a herança visível.
    """

    classe: str
    codigo_ibge: str
    fonte: str = FONTE_NORMA
    origens: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.classe not in CLASSES:
            raise ValueError(
                f"Zona bioclimática {self.classe!r} fora do vocabulário da "
                f"ABNT TR 15220-3-1:2024 ({', '.join(CLASSES)}).")

    @property
    def herdada(self) -> bool:
        """A zona veio do município de origem, não de uma linha da norma."""
        return self.fonte == FONTE_HERANCA

    def __str__(self) -> str:
        return self.classe
