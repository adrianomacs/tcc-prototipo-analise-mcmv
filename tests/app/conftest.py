"""Fixtures e configuração específicas de `tests/app/`.

O ajuste de `sys.path` que existia aqui (para permitir `from app.servicos
import ...`, `from core.dominio import ...` etc. sem instalar o pacote) saiu
daqui: a raiz do projeto agora
entra no `sys.path` pela própria configuração do pytest
(`[tool.pytest.ini_options]` em `pyproject.toml`, `pythonpath = ["."]`),
válida para toda a suíte — não só para esta pasta.
"""

from __future__ import annotations
