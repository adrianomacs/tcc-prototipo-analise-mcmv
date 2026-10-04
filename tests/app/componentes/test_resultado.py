"""Testes das regras (ADR-004, ADR-010) que não dependem de renderizar a página
inteira: a origem do relatório como nó da árvore (regra 6) e o aviso de
relatório desatualizado (regra 4). A regra 1 (trocar município com terreno
confirmado) tem `AppTest` dedicado em `test_informacoes_gerais.py`, porque
depende do formulário renderizado.

Estes testes chamam as funções privadas de `app.componentes.resultado`
diretamente, com `st.warning`/`st.switch_page`/`st.session_state`
monkeypatchados — mais rápido e mais preciso que dirigir os widgets via
`AppTest` para uma lógica que não depende de nenhum widget.
"""

from __future__ import annotations

import pytest

pytest.importorskip("streamlit", reason="sem Streamlit não há o que testar")

from app.componentes import resultado
from app.estado import chaves
from app.navegacao import arvore
from core.dominio.empreendimento import Empreendimento

# ---------------------------------------------------------------------------
# Regra 6 — origem_relatorio é um nó da árvore, não uma string solta.
# ---------------------------------------------------------------------------

def test_paginas_de_checagem_expoem_a_origem_como_no_da_arvore():
    """As três checagens declaram `ORIGEM` como o mesmo objeto `Pagina` da
    árvore (identidade, não string igual por acaso) — varredura de texto,
    sem importar as páginas (que rodam `main()` ao serem importadas)."""
    import re

    alvo = re.compile(r'^ORIGEM = (arvore\.PAGINA_\w+)', re.MULTILINE)
    esperado = {
        "app/paginas/checagens/checagem_enquadramento.py": "arvore.PAGINA_CHECAGEM_ENQUADRAMENTO",
        "app/paginas/checagens/checagem_georreferenciamento.py": "arvore.PAGINA_CHECAGEM_GEORREFERENCIAMENTO",
        "app/paginas/checagens/checagem_programa.py": "arvore.PAGINA_CHECAGEM_PROGRAMA",
    }
    for caminho, nome_esperado in esperado.items():
        with open(caminho, encoding="utf-8") as arquivo:
            conteudo = arquivo.read()
        m = alvo.search(conteudo)
        assert m, f"{caminho}: ORIGEM não encontrado ou não é um Pagina da árvore"
        assert m.group(1) == nome_esperado, (
            f"{caminho}: ORIGEM aponta para {m.group(1)!r}, esperado {nome_esperado!r}")
        # e o nome realmente existe em arvore.py, como o tipo certo
        pagina = getattr(arvore, nome_esperado.split(".", 1)[1])
        assert isinstance(pagina, arvore.Pagina)


def test_abrir_relatorio_guarda_o_no_da_arvore_como_origem(monkeypatch):
    sessao: dict = {}
    chamadas: dict = {}
    monkeypatch.setattr(resultado.st, "session_state", sessao)
    monkeypatch.setattr(resultado.st, "switch_page",
                        lambda p: chamadas.setdefault("switch_page", p))

    resultado._abrir_relatorio("enquadramento", {"requisito": "ENQ-009"},
                               arvore.PAGINA_CHECAGEM_ENQUADRAMENTO)

    assert sessao[chaves.ORIGEM_RELATORIO] is arvore.PAGINA_CHECAGEM_ENQUADRAMENTO
    assert chamadas["switch_page"] == arvore.PAGINA_RELATORIO.caminho
    # A chave da checagem viaja junto com a origem — é o que permite
    # à página de relatório carregar a visualização 3D da MESMA checagem.
    assert sessao[chaves.CHAVE_SELECIONADA] == "enquadramento"


# ---------------------------------------------------------------------------
# Regra 4 — mudar o Empreendimento não limpa relatórios de outras checagens,
# mas eles precisam avisar que podem estar desatualizados.
# ---------------------------------------------------------------------------

def test_sem_empreendimento_nenhum_aviso(monkeypatch):
    avisos = []
    monkeypatch.setattr(resultado.st, "warning", lambda *a, **kw: avisos.append(a))
    resultado._aviso_relatorio_desatualizado(
        {"meta": {"empreendimento": {"id": "x", "versao": 1}}}, None)
    assert avisos == []


def test_relatorio_sem_referencia_de_empreendimento_nao_avisa(monkeypatch):
    """Relatório antigo (sem `meta.empreendimento`) — a ausência
    não é sinal de desatualização, só de que o relatório é anterior ao campo."""
    avisos = []
    monkeypatch.setattr(resultado.st, "warning", lambda *a, **kw: avisos.append(a))
    resultado._aviso_relatorio_desatualizado({"meta": {}}, Empreendimento())
    assert avisos == []


def test_relatorio_em_dia_nao_avisa(monkeypatch):
    avisos = []
    monkeypatch.setattr(resultado.st, "warning", lambda *a, **kw: avisos.append(a))
    emp = Empreendimento()
    relatorio = {"meta": {"empreendimento": emp.referencia()}}
    resultado._aviso_relatorio_desatualizado(relatorio, emp)
    assert avisos == []


def test_relatorio_de_versao_anterior_avisa(monkeypatch):
    avisos = []
    monkeypatch.setattr(resultado.st, "warning",
                        lambda msg, **kw: avisos.append(msg))
    emp = Empreendimento()
    relatorio = {"meta": {"empreendimento": emp.referencia()}}  # versao 1
    emp.renomear("Estrela I")                                  # versao 2
    resultado._aviso_relatorio_desatualizado(relatorio, emp)
    assert len(avisos) == 1 and "1" in avisos[0] and "2" in avisos[0]


def test_relatorio_de_outro_empreendimento_avisa_diferente(monkeypatch):
    avisos = []
    monkeypatch.setattr(resultado.st, "warning",
                        lambda msg, **kw: avisos.append(msg))
    relatorio = {"meta": {"empreendimento": {"id": "outro-id", "versao": 1}}}
    resultado._aviso_relatorio_desatualizado(relatorio, Empreendimento())
    assert len(avisos) == 1 and "outro empreendimento" in avisos[0]


# ---------------------------------------------------------------------------
# Card de síntese e legenda única (ADR-034, D1b.3b): tudo em requisitos.
# ---------------------------------------------------------------------------

def test_legenda_unica_conta_requisitos_da_portaria():
    norm = {"total": 3, "membros": ["ENQ-010.1", "ENQ-010.2"]}
    assert resultado.legenda_das_metricas(norm) == (
        "Contados sobre os **3 requisitos da Portaria** deste grupo; as "
        "alternativas de um mesmo requisito contam como um só.")
    assert resultado.legenda_das_metricas({"total": 1}) == (
        "Contados sobre o **1 requisito da Portaria** deste grupo.")


def test_card_de_sintese_explica_o_resultado_em_requisitos():
    from app.servicos.vereditos import contagens_em_requisitos, explicacao_do_resultado

    norm = {"total": 3, "conforme": 0, "nao_conforme": 1, "nao_avaliavel": 2}
    assert contagens_em_requisitos(norm) == (
        "0 conformes · 1 não conforme · 2 não avaliáveis, em 3 requisitos da Portaria")
    assert explicacao_do_resultado(norm) == (
        "1 requisito não atende à Portaria; basta um para o conjunto não ser conforme.")
    assert explicacao_do_resultado({"nao_avaliavel": 2}) == (
        "Nenhum requisito avaliado reprova, mas 2 não puderam ser avaliados com "
        "o insumo entregue.")
    assert explicacao_do_resultado({"conforme": 2}) == (
        "Todos os requisitos avaliados atendem à Portaria.")
