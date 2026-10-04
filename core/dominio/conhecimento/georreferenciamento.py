"""O nível de georreferenciamento que o protótipo exige do modelo.

LoGeoRef 50 é a premissa de leitura da DN-03: o modelo tem de trazer
``IfcMapConversion`` e ``IfcProjectedCRS`` (IFC4) para que a âncora seja a
origem das coordenadas compartilhadas. O número é conhecimento de referência
do domínio — quem o consome é o EMP-001, pelo parâmetro normativo, e a
composição, ao calcular o diagnóstico na ingestão (ADR-036).
"""

from __future__ import annotations

LOGEOREF_ALVO = 50
