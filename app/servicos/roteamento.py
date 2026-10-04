"""Vocabulário e contrato do roteamento (classificações, rótulos) —
reexportado de `core.dominio.mobilidade` e `core.dominio.contratos.roteador`
(gateway único do núcleo). O adaptador de rede em si
(`core.infra.rede.ors`) é assunto de `app/servicos/provedores.py` — é lá
que a chave de configuração é lida.
"""

from __future__ import annotations

from core.dominio.contratos.roteador import *
from core.dominio.mobilidade import *
