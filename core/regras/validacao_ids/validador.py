"""Execução de uma especificação IDS sobre o modelo com IfcTester.

Função única ``validar_ids`` usada pelo executor antes de checar uma regra que
declara ``ids_spec``. Devolve (ok, detalhe).
"""

from __future__ import annotations

import os
from typing import Any


def validar_ids(modelo: Any, caminho_ids: str) -> tuple[bool, str]:
    """Valida o modelo IFC contra uma especificação IDS.

    Retorna ``(True, "ok")`` quando todas as especificações são satisfeitas;
    caso contrário ``(False, motivo)``. Se a spec não existir ou o modelo não
    estiver carregado, retorna falha controlada (a regra vira NAO_AVALIAVEL).
    """
    if modelo is None:
        return False, "modelo IFC não carregado"
    if not os.path.exists(caminho_ids):
        return False, f"spec IDS não encontrada: {caminho_ids}"

    try:
        from ifctester import ids, reporter
    except ImportError:
        return False, "ifctester não instalado"

    try:
        spec = ids.open(caminho_ids)
        spec.validate(modelo)
        rel = reporter.Json(spec).report()
    except Exception as exc:
        return False, f"erro ao validar IDS: {exc!r}"

    status = rel.get("status", False)
    if status:
        return True, "ok"

    # Coleta uma mensagem sucinta das specificações reprovadas.
    falhas = [s.get("name", "spec") for s in rel.get("specifications", [])
              if not s.get("status", False)]
    return False, "; ".join(falhas) or "especificação não satisfeita"
