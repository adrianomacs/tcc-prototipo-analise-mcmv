"""A porta ``FontesTerritoriais`` (Protocol): o que a aplicação pergunta ao
território antes de executar.

O ADR-011 tirou da regra a leitura do recorte de equipamentos e a entregou à
aplicação (``core/aplicacao/resolver_territorio.py``). Faltava o último passo
da inversão: a aplicação também não deve saber que o território mora em CSV.
Ela pergunta por esta porta — os equipamentos de educação do município, a
procedência do recorte, a zona bioclimática, a população do Censo; e o EMP-001,
se a âncora do modelo cai dentro dos limites do município — e quem
responde é a implementação injetada pela composição (``core/composicao.py``),
hoje ``core/infra/gis/fontes_csv.py``. É o mesmo desenho do ``Roteador``
(``contratos/roteador.py``): contrato no domínio, implementação no anel
externo, injeção pela borda (ADR-002, ADR-011).

Os métodos respondem por código IBGE de 7 dígitos. Ausência é resposta, não
erro: recorte ausente volta como ``RecorteMunicipal`` sem leitura (a mensagem
da regra mostra de onde ele deveria vir); zona e população ausentes voltam
``None``. Falha de leitura pode levantar — quem decide que ela não sobe é o
resolvedor da aplicação.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from core.dominio.conhecimento.porte_municipal import PopulacaoMunicipal
from core.dominio.conhecimento.zona_bioclimatica import ZonaBioclimatica
from core.dominio.equipamentos import RecorteMunicipal


@runtime_checkable
class FontesTerritoriais(Protocol):
    """O território de um município, pelo código IBGE."""

    def recorte_equipamentos(self, codigo_ibge: str) -> RecorteMunicipal:
        """Os equipamentos de educação do município, presente ou ausente."""
        ...

    def procedencia_do_recorte(self, codigo_ibge: str) -> dict:
        """Safra e data do recorte, sem ler o conjunto inteiro."""
        ...

    def zona_bioclimatica(self, codigo_ibge: str) -> ZonaBioclimatica | None:
        """A zona bioclimática do município (ADR-030), ou ``None``."""
        ...

    def populacao_municipal(self, codigo_ibge: str) -> PopulacaoMunicipal | None:
        """A população do Censo do município (ADR-030), ou ``None``."""
        ...

    def conferir_ponto_no_municipio(self, codigo_ibge: str, lat: float,
                                    lon: float) -> Any:
        """O ponto (WGS 84) contra os limites do município: ``dentro``
        (``True``/``False``, ou ``None`` sem malha), ``fonte`` e ``mensagem``."""
        ...
