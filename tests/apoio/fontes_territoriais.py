"""Implementação em memória da porta ``FontesTerritoriais``.

Serve aos testes do resolvedor da aplicação (ADR-011): o que eles prendem é o
gate (terreno, município) e que falha de leitura não sobe — nada disso depende
de CSV. Registra as consultas, para que um teste possa provar que o resolvedor
nem perguntou.
"""

from __future__ import annotations

from core.dominio.equipamentos import RecorteMunicipal


class FontesEmMemoria:
    """Território fixo por código IBGE; ``erro`` faz toda consulta levantar."""

    def __init__(self, recortes=None, zonas=None, populacoes=None, erro=None):
        self.recortes = dict(recortes or {})
        self.zonas = dict(zonas or {})
        self.populacoes = dict(populacoes or {})
        self.erro = erro
        self.consultas: list[tuple[str, str]] = []

    def _consultar(self, qual, codigo):
        self.consultas.append((qual, codigo))
        if self.erro is not None:
            raise self.erro

    def recorte_equipamentos(self, codigo_ibge):
        self._consultar("recorte", codigo_ibge)
        return self.recortes.get(codigo_ibge, RecorteMunicipal(codigo_ibge=codigo_ibge))

    def procedencia_do_recorte(self, codigo_ibge):
        self._consultar("procedencia", codigo_ibge)
        recorte = self.recortes.get(codigo_ibge)
        return dict(recorte.procedencia) if recorte is not None else {}

    def zona_bioclimatica(self, codigo_ibge):
        self._consultar("zona", codigo_ibge)
        return self.zonas.get(codigo_ibge)

    def populacao_municipal(self, codigo_ibge):
        self._consultar("populacao", codigo_ibge)
        return self.populacoes.get(codigo_ibge)
