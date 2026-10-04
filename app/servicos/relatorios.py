"""Relatórios das checagens — leitura, agrupamento e consolidação.

Agrupamento de linhas do relatório por requisito-pai, reexportado de
`core.infra.exportadores.relatorio_json` (gateway único do núcleo).

ADR-001: cada checagem
grava o SEU relatório em `artefatos/relatorios/<chave>.json` (`caminho`,
usado por `app.servicos.analise` como `destino_rel` de `composicao.rodar`),
em vez de todas sobrescreverem `artefatos/relatorio.json`. As funções
abaixo são o que as telas de resultados consolidados (2.4.1 "Cobertura do
Protótipo", 2.4.2 "Relatório de Checagem") usam para reunir os relatórios
das checagens já executadas, filtrados pelo empreendimento corrente —
mesma regra de invalidação por `{id, versao}` que `app.componentes.
resultado._aviso_relatorio_desatualizado` já aplica por checagem
individual (regra 4 do §4.3), aqui aplicada ao CONJUNTO: um relatório de
uma versão anterior do empreendimento simplesmente não entra no
consolidado, em vez de entrar com aviso — não há como avisar sobre uma
linha que a tela nunca mostrou.
"""

from __future__ import annotations

import json
import os

from core.infra.caminhos import ARTEFATOS
from core.infra.exportadores.relatorio_json import agrupar  # noqa: F401 (reexportado)

# As checagens somadas pelo consolidado (2.4.1/2.4.2), na ordem da árvore de
# navegação: todas as que gravam relatório por chave (ADR-001). As páginas de
# resultados têm cada uma o seu dicionário de rótulos com EXATAMENTE estas
# chaves — um teste de 2.4.x prende a igualdade, para que a checagem nova não
# volte a gravar relatório sem entrar na soma. `informacoes_gerais.py`
# (`CHAVE = "geral"`) não roda `composicao.rodar` — grava o `Empreendimento`,
# não um relatório.
CHECAGENS = ("enquadramento", "qualificacao", "georref", "programa", "bim_gis")

PASTA_RELATORIOS = os.path.join(ARTEFATOS, "relatorios")


def caminho(chave: str) -> str:
    """Onde o relatório dessa checagem é gravado
    (`artefatos/relatorios/<chave>.json`) — usado como `destino_rel` de
    `composicao.rodar` e para reler o relatório depois."""
    return os.path.join(PASTA_RELATORIOS, f"{chave}.json")


def ler(chave: str) -> dict | None:
    """O relatório gravado em disco para essa checagem, ou `None` se ela
    nunca rodou (ou o arquivo foi apagado)."""
    arquivo = caminho(chave)
    if not os.path.isfile(arquivo):
        return None
    with open(arquivo, encoding="utf-8") as f:
        return json.load(f)


def _pertence_ao_empreendimento(relatorio: dict, referencia: dict) -> bool:
    """Mesma comparação de `resultado._aviso_relatorio_desatualizado`, sem o
    aviso: aqui a resposta é só sim/não — entra ou não no consolidado."""
    meta_emp = (relatorio.get("meta") or {}).get("empreendimento")
    return bool(meta_emp) and meta_emp == referencia


def relatorios_do_empreendimento_corrente() -> dict[str, dict]:
    """`{chave: relatório}` de cada checagem cujo relatório em disco bate
    com o `{id, versao}` do `Empreendimento` corrente da sessão — as
    checagens nunca executadas, ou executadas para uma versão anterior do
    empreendimento, ficam de fora."""
    from app.servicos import (
        empreendimento as emp_servico,  # evita ciclo no import do módulo
    )

    referencia = emp_servico.referencia_atual()
    encontrados: dict[str, dict] = {}
    for chave in CHECAGENS:
        relatorio = ler(chave)
        if relatorio is not None and _pertence_ao_empreendimento(relatorio, referencia):
            encontrados[chave] = relatorio
    return encontrados


def consolidar(relatorios: dict[str, dict]) -> dict:
    """Soma o bloco `resumo.normativo` de cada relatório recebido num único
    `{total, avaliados, conforme, nao_conforme, nao_avaliavel,
    conformidade, cobertura}` — a MESMA fórmula de
    `core.infra.exportadores.relatorio_json._normativo`, aplicada ao
    conjunto agregado das checagens em vez de aos requisitos de uma só.

    Somar é seguro aqui porque os `ids` normativos de cada checagem são
    disjuntos entre si (ENQ-* do Enquadramento, EMP-025 da Qualificação,
    EMP-001 do Georreferenciamento, EDI-* do Programa e EDI-019/EDI-024 da
    BIM + GIS: um grupo de `config/grupos_requisitos.yaml` por checagem) —
    nenhum requisito aparece em mais de uma checagem, então não há dupla
    contagem a evitar; um teste de 2.4.x prende a disjunção sobre o YAML (ao contrário da agregação DENTRO de um
    relatório, que `_normativo` já resolve antes de chegar aqui).

    `relatorios` vazio devolve um consolidado zerado (`total=0`,
    `conformidade=None`, `cobertura=0.0`) — mesma convenção de
    `_normativo` para "nada para avaliar".
    """
    total = avaliados = conforme = nao_conforme = nao_avaliavel = 0
    for relatorio in relatorios.values():
        norm = (relatorio.get("resumo") or {}).get("normativo") or {}
        total += norm.get("total", 0)
        avaliados += norm.get("avaliados", 0)
        conforme += norm.get("conforme", 0)
        nao_conforme += norm.get("nao_conforme", 0)
        nao_avaliavel += norm.get("nao_avaliavel", 0)
    return {
        "total": total,
        "avaliados": avaliados,
        "conforme": conforme,
        "nao_conforme": nao_conforme,
        "nao_avaliavel": nao_avaliavel,
        "conformidade": round(conforme / avaliados, 4) if avaliados else None,
        "cobertura": round(avaliados / total, 4) if total else 0.0,
    }
