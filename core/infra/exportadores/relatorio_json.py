"""Geração do relatório de conformidade em JSON.

O relatório é o artefato central do desacoplamento: relaciona cada elemento do
modelo (por GlobalId) aos seus resultados de verificação, permitindo que a
visualização destaque elementos sem conhecer o núcleo Python.

ORDEM DE EXIBIÇÃO × ORDEM DE EXECUÇÃO: o executor
(``core.aplicacao.executor``) devolve os resultados em ordem **topológica**
(pré-requisito antes de dependente — necessário para a corretude da
avaliação). Essa ordem não é, porém, a ordem "natural"/esperada de leitura do
relatório: como EDI-004.1/007/008/009/011 não dependem de EDI-004, a posição de
EDI-004 entre elas varia conforme a mecânica interna da pilha de dependências do executor, sem
relação com a ordem em que os requisitos aparecem declarados em
``config/grupos_requisitos.yaml``. Este módulo aceita um ``ordem_exibicao``
opcional (tipicamente os IDs pedidos pela interface, na ordem do grupo) só
para reordenar a EXIBIÇÃO — a ordem de execução do motor não é alterada.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime

from core.dominio.contratos.regra import Estado, Resultado
from core.dominio.vocabulario import tipos_diagnostico


def _ordenar_para_exibicao(resultados: Mapping[str, Resultado],
                           ordem_exibicao: list[str] | None) -> dict[str, Resultado]:
    """Reordena os resultados para EXIBIÇÃO, sem tocar a ordem topológica de
    execução (o motor continua garantindo pré-requisito antes de dependente
    internamente; isto é só a ordem em que o relatório lista os requisitos).

    ``ordem_exibicao`` é a ordem "natural" pedida pelo chamador — tipicamente
    a ordem declarada no grupo (``config/grupos_requisitos.yaml``), já
    filtrada pela aplicabilidade (ver ``app._checagem_comum.ids_executaveis``,
    que é o mesmo ``ids_selecionados`` passado ao executor). Sem isso (None
    ou vazio), preserva a ordem de execução recebida — comportamento anterior,
    usado por chamadores sem noção de grupo (ex.: o CLI do pipeline).

    IDs em ``ordem_exibicao`` ausentes de ``resultados`` são ignorados; IDs de
    ``resultados`` ausentes de ``ordem_exibicao`` (ex.: uma dependência
    puxada pelo executor que não fazia parte da seleção original) são
    anexados ao final, na ordem de execução — nenhum resultado é perdido.
    """
    if not ordem_exibicao:
        return dict(resultados)
    ordenado: dict[str, Resultado] = {}
    for rid in ordem_exibicao:
        if rid in resultados and rid not in ordenado:
            ordenado[rid] = resultados[rid]
    for rid, r in resultados.items():
        if rid not in ordenado:
            ordenado[rid] = r
    return ordenado


def montar(resultados: Mapping[str, Resultado], meta: dict | None = None,
          ordem_exibicao: list[str] | None = None) -> dict:
    """Monta a estrutura do relatório a partir dos resultados das regras.

    ``ordem_exibicao``: ver ``_ordenar_para_exibicao`` — reordena só a
    exibição (``por_requisito``), não a lógica de execução já concluída.
    """
    resultados = _ordenar_para_exibicao(resultados, ordem_exibicao)
    por_requisito = [r.to_dict() for r in resultados.values()]

    # Índice auxiliar GlobalId -> estados, conveniente para a visualização.
    por_elemento: dict[str, list[dict]] = {}
    for r in resultados.values():
        for gid in r.elementos:
            por_elemento.setdefault(gid, []).append(
                {"requisito": r.regra_id, "estado": r.estado.value}
            )

    resumo = _resumo(resultados)
    return {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "meta": meta or {},
        "resumo": resumo,
        "por_requisito": por_requisito,
        "por_elemento": por_elemento,
    }


def _resumo(resultados: Mapping[str, Resultado]) -> dict:
    """Contagens por estado das LINHAS executadas + os dois números normativos.

    As duas coisas têm universos diferentes e por isso convivem aqui com nomes
    diferentes:

    * ``total_requisitos``, ``avaliados`` e as contagens por estado descrevem as
      **linhas do relatório** — é o que a tabela da tela mostra, e tem de fechar
      com ela.
    * ``conformidade`` e ``cobertura`` são os dois números do relatório e
      contam **requisitos da Portaria**, não linhas. O bloco ``normativo`` mostra
      de onde eles saíram.

    Cuidado ao ler: ``cobertura`` NÃO é ``avaliados / total_requisitos``. Ver
    :func:`_normativo`.
    """
    cont = {e.value: 0 for e in Estado}
    for r in resultados.values():
        cont[r.estado.value] += 1
    total = len(resultados)
    avaliados = total - cont[Estado.NAO_AVALIAVEL.value]
    normativo = _normativo(resultados)
    return {
        "total_requisitos": total,
        "avaliados": avaliados,
        **cont,
        # Os dois números normativos, no nível normativo. Ficam no topo porque são a
        # saída do módulo; o bloco abaixo é a memória de cálculo deles.
        "conformidade": normativo["conformidade"],
        "cobertura": normativo["cobertura"],
        "normativo": normativo,
    }


def _membros_de_agregacao(resultados: Mapping[str, Resultado]) -> set[str]:
    """Ids que são MEMBROS de alguma agregação presente nos resultados.

    Sai do ``detalhe`` dos próprios resultados — nunca do registro de regras nem
    de arquivo de configuração. Duas consequências boas: o resumo não depende de
    o processo ter as mesmas regras registradas que produziram a análise, e tudo
    o que ele precisa já está dentro do ``relatorio.json`` (a informação viaja
    com o relatório, como no R5d).
    """
    membros: set[str] = set()
    for r in resultados.values():
        detalhe = r.detalhe or {}
        if detalhe.get("tipo") != tipos_diagnostico.AGREGACAO:
            continue
        for m in detalhe.get("membros") or []:
            if m.get("id"):
                membros.add(m["id"])
    return membros


def _normativo(resultados: Mapping[str, Resultado]) -> dict:
    """Os dois números do §3.1, contados sobre os requisitos da Portaria.

    * **conformidade** = conformes / (conformes + não conformes) — entre os que
      foi possível avaliar.
    * **cobertura** = avaliáveis / aplicáveis — quanto do enquadramento o insumo
      disponível alcançou.

    Por que o denominador exclui os membros de uma agregação
    -------------------------------------------------------

    Duas razões, e as duas apareceram medidas no R6a:

    1. **Contar pai e filho conta a mesma evidência duas vezes.** ENQ-010 é
       conforme *porque* ENQ-010.1 é; somar os dois transforma um resultado em
       dois e infla a conformidade.
    2. **As alternativas remetidas a parecer ficariam no denominador para
       sempre**, travando a cobertura em 5/7 mesmo num terreno em que a
       ferramenta dê veredito em todos os requisitos. O número passaria a
       descrever a ESTRUTURA DA NORMA — o "ou" existe justamente para que uma
       alternativa baste — em vez do alcance da ferramenta.

    Atenção ao critério, que **não** é "ter pai na planilha": é *ser membro de uma
    agregação*. EDI-004.1 tem `Grupo (pai)` = EDI-004 e não é agregado por
    ninguém — é requisito independente, com veredito próprio, desde a atomização
    do EDI-004. Ele conta. O que não conta é a alternativa cujo resultado o pai
    consome para decidir.

    Sem nenhuma agregação nos resultados, o nível normativo é o conjunto inteiro —
    então os grupos sem pai (Programa de necessidades, Georreferenciamento)
    ganham os dois números sem nenhuma configuração.
    """
    membros = _membros_de_agregacao(resultados)
    ids = [rid for rid in resultados if rid not in membros]

    cont = {e.value: 0 for e in Estado}
    for rid in ids:
        cont[resultados[rid].estado.value] += 1
    total = len(ids)
    # Com três estados, "avaliados" e "conformes + não conformes" são o mesmo
    # conjunto: é o denominador da conformidade e o numerador da cobertura.
    avaliados = total - cont[Estado.NAO_AVALIAVEL.value]
    return {
        "ids": ids,
        "membros": sorted(membros),
        "total": total,
        "avaliados": avaliados,
        **cont,
        # ``None``, e não 0.0, quando nada foi avaliado: 0% leria como "nenhum
        # conforme", que é afirmação sobre um conjunto vazio. A tela mostra "—".
        "conformidade": (round(cont[Estado.CONFORME.value] / avaliados, 4)
                         if avaliados else None),
        "cobertura": round(avaliados / total, 4) if total else 0.0,
    }


def agrupar(relatorio: Mapping) -> list[dict]:
    """Agrupa as linhas do relatório por **requisito da Portaria**.

    Devolve ``[{"requisito": <linha>, "membros": [<linha>, ...]}, ...]`` na ordem
    de exibição, com cada agregador trazendo suas alternativas e cada requisito
    sem pai aparecendo sozinho.

    É a mesma unidade do denominador de :func:`_normativo`, e não por acaso: se
    conformidade e cobertura contam requisitos, a tela tem de contar requisitos
    também — uma lista plana de sete verificações ao lado de um par de números
    calculado sobre três convida a somar as colunas erradas. Aqui a tela e o
    número passam a falar da mesma coisa.

    Opera sobre o **relatório montado** (dicionários), não sobre ``Resultado``:
    é o que a interface tem em mãos, e mantém o agrupamento derivável do
    ``relatorio.json`` salvo.
    """
    linhas = list(relatorio.get("por_requisito") or [])
    por_id = {linha.get("requisito"): linha for linha in linhas}

    membros_de: dict[str, list[str]] = {}
    for linha in linhas:
        detalhe = linha.get("detalhe") or {}
        if detalhe.get("tipo") != tipos_diagnostico.AGREGACAO:
            continue
        membros_de[linha.get("requisito")] = [
            m["id"] for m in (detalhe.get("membros") or []) if m.get("id")]

    de_alguem = {mid for ids in membros_de.values() for mid in ids}

    grupos: list[dict] = []
    for linha in linhas:
        rid = linha.get("requisito")
        if rid in de_alguem:
            continue          # aparece dentro do pai, não como linha própria
        grupos.append({
            "requisito": linha,
            "membros": [por_id[mid] for mid in membros_de.get(rid, [])
                        if mid in por_id],
        })
    return grupos


def gravar(resultados: Mapping[str, Resultado], caminho: str, meta: dict | None = None,
          ordem_exibicao: list[str] | None = None) -> dict:
    """Monta e grava o relatório em ``caminho`` (UTF-8).

    ``ordem_exibicao``: repassado a ``montar`` — ver ali."""
    relatorio = montar(resultados, meta, ordem_exibicao=ordem_exibicao)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(relatorio, f, ensure_ascii=False, indent=2)
    return relatorio
