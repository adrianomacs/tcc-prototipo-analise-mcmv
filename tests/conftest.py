"""Configuração e apoio compartilhados por toda a suíte de `tests/`.

``RAIZ`` (raiz do projeto) e ``FIXTURES`` (``tests/fixtures/``) substituem os
cálculos ad-hoc a partir de ``__file__`` que existiam em vários arquivos de
teste — cada um contando "quantos `dirname`/`parent` até a raiz", número que
dependia da profundidade do próprio arquivo e quebrava silenciosamente a cada
movimento. Centralizados aqui, mover arquivos entre pastas
não exige recalcular nada: os arquivos passam a importar
``RAIZ``/``FIXTURES`` daqui.

``RAIZ`` é ``str`` (mantém compatível o uso existente com ``os.path.join`` /
``os.path.dirname``); ``FIXTURES`` é ``Path`` (usado com o operador ``/``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

RAIZ = str(Path(__file__).resolve().parent.parent)
FIXTURES = Path(__file__).resolve().parent / "fixtures"



@pytest.fixture(autouse=True)
def _isolar_artefatos_de_testes_de_interface(request, tmp_path, monkeypatch):
    """Sem isto, todo teste marcado ``interface`` grava por cima do
    `artefatos/empreendimento.json` e dos relatórios reais de quem roda a
    suíte: o Estrela I já mudou de versão e de tipologia só por se
    ter rodado `pytest`.

    A causa tinha duas metades: a tela grava a cada render (não só quando
    algo muda) e os testes que a rendem não isolavam o repositório. Esta
    fixture fecha a segunda metade para toda a suíte de uma vez, em vez de
    depender de cada teste lembrar de se isolar — ``test_casco.py`` e
    ``test_paginas_renderizam.py`` não se isolavam sozinhos; os que já o
    faziam (``test_informacoes_gerais.py``,
    ``test_checagem_georreferenciamento.py``,
    ``test_checagem_programa.py``, ``test_resultados_consolidados.py``)
    ficam redundantes, não quebrados — apontar duas vezes para o mesmo
    ``tmp_path`` é inofensivo.

    A outra metade — a tela só gravar quando algo de fato mudou — está em
    `app/paginas/checagens/informacoes_gerais.py`; esta
    fixture continua valendo para toda página que grave.
    """
    if not request.node.get_closest_marker("interface"):
        return

    from app.servicos import empreendimento as _emp_mod
    from app.servicos import relatorios as _rel_mod

    monkeypatch.setattr(_emp_mod, "ARTEFATOS", str(tmp_path))
    monkeypatch.setattr(_rel_mod, "PASTA_RELATORIOS", str(tmp_path / "relatorios"))
