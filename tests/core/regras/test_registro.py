"""Teste do utilitário de linha de comando de ``core/regras/registro.py``.

    pytest tests/core/regras/test_registro.py

Roda ``python -m core.regras.registro --listar`` via ``subprocess`` de
propósito: o defeito da execução como módulo só existe sob ``-m`` (o módulo passa a rodar
como ``__main__``, um objeto de módulo distinto de ``core.regras.registro``,
e ``descobrir()`` popula o registro do módulo canônico, não o do
``__main__``); chamar ``_cli()`` por import normal não teria reproduzido o
bug nem provaria a correção.

Forçamos ``PYTHONIOENCODING=utf-8`` no processo filho: as descrições das
regras trazem símbolos como “≥” (``EDI-001``: “≥ 40,00 m²”), que não cabem no
code page padrão do console do Windows (cp1252) — sem isso, o `print()` do
utilitário derruba o processo com `UnicodeEncodeError` antes mesmo de o teste
chegar a exercitar esse defeito.
"""

import os
import subprocess
import sys


def test_cli_lista_as_21_regras_registradas():
    # A contagem partiu de 19; os ramos e pais da absortância (ADR-026) levaram a
    # 24, e EMP-025/025.1/025.2 (ADR-015/028, DN-04) a 27; a saída de EDI-003 e
    # EDI-026, nunca ativas, a 25. O nome do teste ficou com o número antigo:
    # renomeá-lo não muda o que ele prende.
    ambiente = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    resultado = subprocess.run(
        [sys.executable, "-m", "core.regras.registro", "--listar"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=ambiente,
        check=True,
    )

    assert "Nenhuma regra registrada." not in resultado.stdout
    assert "25 regra(s) registrada(s):" in resultado.stdout
    assert "EDI-001" in resultado.stdout
    assert "ENQ-011.2" in resultado.stdout
