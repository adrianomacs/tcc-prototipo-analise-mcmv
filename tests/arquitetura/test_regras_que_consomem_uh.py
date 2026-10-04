"""A lista de regras que leem UH não pode envelhecer em silêncio (ADR-023, D-K).

``core.aplicacao.diagnosticos`` só emite os cinco diagnósticos nas análises que
consomem ``unidades_representadas``, e responde isso por uma **lista de ids** —
``REGRAS_QUE_CONSOMEM_UH``. Uma lista é conhecimento duplicado: o outro lado
dela é o código das regras, e nada obriga os dois a andarem juntos. Sem este
teste, uma regra nova que lesse a âncora ficaria fora dos diagnósticos sem
ninguém notar, e o Programa de necessidades passaria a diagnosticar menos do
que analisa — exatamente o tipo de defeito que só aparece no resultado final.

O critério é o **módulo** da regra chamar ``ancora.unidades_representadas``, e
não cada classe chamá-la: é o módulo que declara a dependência (as duas regras
de área útil a consomem pela mesma função), e é isso que este teste mede. A
alternativa — um atributo novo em ``Regra`` — mudaria o contrato de ``Regra``,
que não deve mudar sem decisão explícita do desenvolvedor.
"""

from __future__ import annotations

import inspect

from core.aplicacao import diagnosticos as diag
from core.regras import registro

CHAMADA = "ancora.unidades_representadas"


def _ids_por_leitura_do_codigo() -> set[str]:
    """Os ids cujas regras moram num módulo que chama a âncora."""
    achados = set()
    for id_regra, classe in registro.descobrir().items():
        try:
            fonte = inspect.getsource(inspect.getmodule(classe))
        except (OSError, TypeError):       # pragma: no cover - módulo sem fonte
            continue
        if CHAMADA in fonte:
            achados.add(id_regra)
    return achados


def test_a_lista_declarada_e_a_que_o_codigo_das_regras_mostra():
    assert _ids_por_leitura_do_codigo() == set(diag.REGRAS_QUE_CONSOMEM_UH)


def test_a_lista_nao_e_vazia():
    """Uma lista vazia passaria no teste acima se a âncora sumisse do código —
    e desligaria os diagnósticos em toda parte, em silêncio."""
    assert diag.REGRAS_QUE_CONSOMEM_UH
