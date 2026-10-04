"""``contexto_bim`` — um ``Contexto`` com modelo, montado como a composição o
monta (ADR-036).

As regras BIM leem o modelo pela porta ``LeituraModelo`` e o EMP-001 julga o
LoGeoRef calculado na ingestão; um teste que chama a regra direto, sem passar
por ``core.composicao.montar_contexto``, precisa do mesmo preparo. É a mesma
função de produção (``composicao.leitura_do_modelo``), não uma imitação.
"""

from __future__ import annotations

from core import composicao
from core.dominio.contratos.regra import Contexto


def contexto_bim(modelo_ifc=None, **kwargs) -> Contexto:
    georref = dict(kwargs.pop("georref", None) or {})
    leitura = composicao.leitura_do_modelo(modelo_ifc, georref)
    kwargs.setdefault("fontes_territoriais", composicao.fontes_territoriais())
    return Contexto(modelo_ifc=modelo_ifc, georref=georref,
                    leitura_modelo=leitura, **kwargs)
