"""Localização → território: o recorte de equipamentos, a zona bioclimática e a
população do Censo.

Fecha o defeito D1 do ADR-011 (território resolvido pela aplicação): a regra de
distância abria ``config/equipamentos_<ibge>.csv`` por conta própria, com caminho
relativo ao CWD, **dentro** de uma regra. A pergunta certa da regra é *"quais são
os equipamentos de educação deste município?"*, e quem responde é a aplicação,
antes de executar — é o que este módulo faz.

A aplicação pergunta pela porta ``FontesTerritoriais``
(``core/dominio/contratos/fontes_territoriais.py``) e não sabe que o
território mora em CSV: a implementação é injetada pela composição
(``core/composicao.py``), como o ``Roteador`` (ADR-011). Por isso este módulo
não importa o anel externo (ADR-002).

Quando resolver
---------------

Só quando há **terreno**. Não é economia, é a condição exata: os únicos
consumidores do recorte são as regras com ``exige_terreno``, e sem terreno o
executor as gateia antes do ``checar``. Resolver sem terreno faria as telas de
Georreferenciamento e de Programa de necessidades — que também declaram município
— lerem um CSV que nenhuma regra delas usa, e passarem a depender dele estar
legível.

Falha ao ler não sobe daqui
---------------------------

Se a leitura levantar, o recorte fica ``None`` e a causa vai para o log; a
regra de distância, sem recorte resolvido, sai NÃO AVALIÁVEL por erro de
execução — o mesmo estado e o mesmo motivo de quando ela relia o arquivo dentro
do ``checar`` e o executor isolava a exceção. Um CSV corrompido derruba as
regras de distância, com a causa registrada, e não a análise inteira.
"""

from __future__ import annotations

import logging

from core.dominio.conhecimento.porte_municipal import PopulacaoMunicipal
from core.dominio.conhecimento.zona_bioclimatica import ZonaBioclimatica
from core.dominio.contratos.fontes_territoriais import FontesTerritoriais
from core.dominio.equipamentos import RecorteMunicipal

_log = logging.getLogger(__name__)


def recorte(codigo_ibge: str, fontes: FontesTerritoriais
            ) -> RecorteMunicipal | None:
    """O recorte do município, presente ou ausente; ``None`` sem código."""
    codigo = str(codigo_ibge or "").strip()
    if not codigo:
        return None
    return fontes.recorte_equipamentos(codigo)


def para_empreendimento(empreendimento, fontes: FontesTerritoriais
                        ) -> RecorteMunicipal | None:
    """O recorte que a análise deste empreendimento precisa, ou ``None``.

    ``None`` quando não há terreno ou não há município declarado, e quando a
    leitura falhou (ver o cabeçalho: a causa vai para o log, e a regra sai NÃO
    AVALIÁVEL por erro de execução).
    """
    if empreendimento is None or empreendimento.terreno is None:
        return None
    try:
        return recorte(empreendimento.codigo_ibge, fontes)
    except Exception as exc:                            # noqa: BLE001
        _log.warning("[território] recorte de %s não lido: %r",
                     empreendimento.codigo_ibge, exc)
        return None


def procedencia(codigo_ibge: str, fontes: FontesTerritoriais) -> dict:
    """Safra e data do recorte, para o aviso da tela (sem ler o CSV inteiro)."""
    return fontes.procedencia_do_recorte(codigo_ibge)


# ---------------------------------------------------------------------------
# Zona bioclimática (ADR-030)
# ---------------------------------------------------------------------------
#
# Mesma cadeia do recorte — a aplicação resolve, o motor recebe (ADR-011) —, com
# UMA diferença que não é detalhe: a zona **não** se gateia por terreno. Os
# consumidores do recorte são as regras com ``exige_terreno``; os da zona são
# regras EDI, que avaliam a unidade habitacional e rodam com um modelo isolado,
# sem terreno nenhum. Gateá-la por terreno as deixaria sem parâmetro justo nos
# fluxos em que elas são o assunto. O gate certo é o município declarado, e ele
# está no próprio ``codigo_ibge``.


def zona_bioclimatica(codigo_ibge: str, fontes: FontesTerritoriais
                      ) -> ZonaBioclimatica | None:
    """A zona do município, ou ``None`` sem código e sem linha na base."""
    return fontes.zona_bioclimatica(codigo_ibge)


def zona_para_empreendimento(empreendimento, fontes: FontesTerritoriais
                             ) -> ZonaBioclimatica | None:
    """A zona da análise deste empreendimento, ou ``None``.

    ``None`` quando não há município declarado e quando a leitura falhou — a
    falha não sobe daqui, pelo mesmo motivo do recorte (ver o cabeçalho): a
    regra que precisar da zona a reencontra ausente e sai NÃO AVALIÁVEL com a
    causa registrada, em vez de derrubar a análise inteira.
    """
    if empreendimento is None:
        return None
    try:
        return zona_bioclimatica(empreendimento.codigo_ibge, fontes)
    except Exception:                                   # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# População do Censo 2022 — de onde sai o porte (ADR-030)
# ---------------------------------------------------------------------------
#
# A cadeia da zona, sem tirar nem pôr: gate pelo município declarado, nunca por
# terreno (a regra de porte não mede nada no terreno), e falha de leitura não
# sobe daqui. O que chega ao motor é a POPULAÇÃO, não um token de porte: cada
# item da Portaria tem a sua tabela de faixas, e quem classifica é a regra
# (``core/dominio/conhecimento/porte_municipal.py``).


def populacao_municipal(codigo_ibge: str, fontes: FontesTerritoriais
                        ) -> PopulacaoMunicipal | None:
    """A população do Censo 2022 do município, ou ``None``."""
    return fontes.populacao_municipal(codigo_ibge)


def populacao_para_empreendimento(empreendimento, fontes: FontesTerritoriais
                                  ) -> PopulacaoMunicipal | None:
    """A população da análise deste empreendimento, ou ``None`` (ver a zona)."""
    if empreendimento is None:
        return None
    try:
        return populacao_municipal(empreendimento.codigo_ibge, fontes)
    except Exception:                                   # noqa: BLE001
        return None
