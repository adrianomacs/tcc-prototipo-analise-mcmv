"""Pacote de regras de checagem, organizado por domínio.

Subpacotes:

* ``gis``      — regras de natureza espacial (contexto territorial);
* ``bim``      — regras sobre atributos e medidas extraídos do modelo;
* ``gis_bim``  — regras que cruzam modelo e contexto territorial.

A organização por domínio espelha o roteamento do motor de regras (Passo 3).
Cada arquivo contém exatamente uma regra, decorada com ``@registrar``.
"""
