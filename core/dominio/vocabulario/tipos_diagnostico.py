"""Tipos de diagnóstico — as chaves que dizem que forma tem o ``detalhe``.

Algumas regras-base devolvem, no ``detalhe`` do ``Resultado``, um diagnóstico
com forma própria (os membros de uma agregação, as medições de distância, as
camadas de revestimento...), e o campo ``detalhe["tipo"]`` diz qual é. Quem
lê o relatório escolhe por ele o relatório dedicado; o resumo normativo o usa
para reconhecer o pai de agregação (ADR-015).

A chave é vocabulário do domínio, e não da regra que a emite: o exportador do
relatório (anel externo) precisa reconhecê-la sem importar o anel de regras, e
a regra da dependência para dentro vale sem exceção (ADR-002). As regras-base
continuam expondo o seu ``TIPO_DIAGNOSTICO``, igual à constante daqui.

Conjunto fechado: tipo novo nasce aqui, junto com a regra que o emite.
"""

from __future__ import annotations

AGREGACAO = "agregacao"
REMETIDA = "remetida"
ABSORTANCIA = "absortancia"
DISTANCIA_EQUIPAMENTO = "distancia_equipamento"
PORTE_EMPREENDIMENTO = "porte_empreendimento"
