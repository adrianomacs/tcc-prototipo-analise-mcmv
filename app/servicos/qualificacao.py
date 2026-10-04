"""Leitura do relatório da Qualificação urbanística — o território analisado.

O relatório do EMP-025 (``app/componentes/relatorio_porte.py``) mostra o
município de que o porte foi derivado; ele vem do ``meta`` gravado em
``artefatos/relatorios/<chave>.json`` e de nada mais (ADR-001). O quadro que a
tela da checagem montava a partir do mesmo relatório saiu: repetia o relatório
do requisito (ADR-034: o resultado mora no relatório).

Função pura sobre um ``dict``, sem Streamlit (ADR-003).
"""

from __future__ import annotations

def municipio(relatorio: dict | None) -> dict:
    """``{nome, uf, codigo_ibge}`` do território analisado, lidos de ``meta``."""
    meta = (relatorio or {}).get("meta") or {}
    decl = meta.get("declaracoes") or {}
    return {"nome": str(decl.get("municipio") or ""),
            "uf": str(decl.get("uf") or ""),
            "codigo_ibge": str(meta.get("municipio_ibge")
                               or decl.get("municipio_ibge") or "")}
