"""Executor do motor de regras.

Percorre as regras registradas e as executa, respeitando:

* as **dependências assimétricas** descritas no Passo 3 — uma regra cuja lista
  ``depende_de`` aponta para um requisito não conforme (ou não avaliado) retorna
  ``NAO_AVALIAVEL``, sem ser de fato executada;
* a **validação de informações (IDS)** como filtro prévio: se a regra declara
  ``ids_spec`` e o modelo não satisfaz a specificação, a regra é marcada como
  ``NAO_AVALIAVEL`` (a propriedade exigida não existe ou tem tipo errado);
* o **modo de medição** da PoC: a execução nunca é abortada — todas as regras
  possíveis são processadas e as demais relatadas.

A ordem de execução é resolvida por uma ordenação topológica simples sobre o
grafo de dependências, garantindo que um pré-requisito seja avaliado antes de
quem depende dele — e, desde o R6, que os **membros de uma agregação** sejam
avaliados antes do requisito-pai que os agrega (``Regra.agrega``). São duas
relações distintas com a mesma exigência de ordem e efeitos opostos sobre o
veredito: ver :func:`_precedentes`.
"""

from __future__ import annotations

from core.dominio.contratos.regra import Contexto, Estado, Regra, Resultado
from core.dominio.vocabulario import motivos
from core.regras.registro import regras_registradas
from core.regras.validacao_ids.validador import validar_ids


def _precedentes(regra: type[Regra]) -> list[str]:
    """Requisitos que precisam ser avaliados ANTES de ``regra``.

    Duas listas com semânticas opostas e a mesma necessidade de ordem:
    ``depende_de`` é pré-requisito (não conforme ⇒ a regra nem roda) e ``agrega``
    é filiação (o pai roda **justamente** para julgar o que os membros deram).
    A distinção mora no passo 1 de :func:`_executar_uma`, que só consulta
    ``depende_de``; aqui, onde só importa quem vem primeiro, as duas se somam.

    Confundir as duas seria o defeito silencioso do R6: um pai de "ou" declarado
    com ``depende_de`` sairia NÃO AVALIÁVEL por `prerequisito_falho`, sem
    intervalo e com a causa errada, exatamente quando a alternativa A reprovasse.
    """
    return list(regra.depende_de) + list(regra.agrega)


def _com_dependencias(todas: dict[str, type[Regra]], selecionados: list[str]) -> dict[str, type[Regra]]:
    """Restringe ``todas`` aos selecionados, puxando dependências e membros.

    Uma dependência não implementada (ausente do registro) é simplesmente
    ignorada aqui; em tempo de execução a regra dependente resultará em
    NAO_AVALIAVEL por pré-requisito não satisfeito. Um **membro** de agregação
    ausente do registro também é ignorado aqui, e o agregador o conta como não
    avaliável — nunca como inexistente, que faria o limite superior encolher e o
    pai reprovar por ignorância.
    """
    escolhidas: dict[str, type[Regra]] = {}
    pilha = list(selecionados)
    while pilha:
        rid = pilha.pop()
        if rid in escolhidas or rid not in todas:
            continue
        escolhidas[rid] = todas[rid]
        pilha.extend(_precedentes(todas[rid]))
    return escolhidas


def _ordenar_por_dependencia(regras: dict[str, type[Regra]]) -> list[str]:
    """Ordenação topológica dos ids de regra a partir de :func:`_precedentes`.

    Regras com precedentes ainda não resolvidos são adiadas. Precedentes
    ausentes do registro são ignorados na ordenação (tratados como falhas em
    tempo de execução, resultando em NAO_AVALIAVEL).
    """
    pendentes = dict(regras)
    ordenadas: list[str] = []
    resolvidas: set[str] = set()

    while pendentes:
        progrediu = False
        for rid in list(pendentes):
            deps = [d for d in _precedentes(pendentes[rid]) if d in regras]
            if all(d in resolvidas for d in deps):
                ordenadas.append(rid)
                resolvidas.add(rid)
                del pendentes[rid]
                progrediu = True
        if not progrediu:
            # Ciclo ou dependência irresolúvel: anexa o restante como está.
            ordenadas.extend(pendentes)
            break
    return ordenadas


def executar(ctx: Contexto, ids_selecionados: list[str] | None = None) -> dict[str, Resultado]:
    """Executa as regras registradas sobre o contexto e devolve os resultados.

    Se ``ids_selecionados`` for informado (escolha feita na interface), apenas
    essas regras são executadas; caso contrário, todas as registradas. As
    dependências de uma regra selecionada continuam sendo avaliadas para que o
    pré-requisito seja conhecido (ex.: ENQ-009 depende de EMP-001).

    Os resultados também são acumulados em ``ctx.resultados`` ao longo da
    execução, de modo que regras dependentes consigam consultar o estado de
    seus pré-requisitos.
    """
    regras = regras_registradas()
    if ids_selecionados is not None:
        regras = _com_dependencias(regras, ids_selecionados)
    ordem = _ordenar_por_dependencia(regras)

    for rid in ordem:
        regra = regras[rid]()  # instancia a regra
        resultado = _executar_uma(regra, ctx)

        # ``checar`` pode devolver lista (requisito desdobrado em instâncias).
        if isinstance(resultado, list):
            # Consolida em um resultado-resumo, mantendo os elementos.
            ctx.resultados[rid] = _consolidar(rid, resultado)
        else:
            ctx.resultados[rid] = resultado

    return dict(ctx.resultados)


def _executar_uma(regra: Regra, ctx: Contexto) -> Resultado | list[Resultado]:
    """Aplica filtros (aplicabilidade, dependências, IDS) e executa a checagem."""

    # 0) Aplicabilidade às declarações do usuário (condições de contorno).
    #    Vale mesmo se a regra foi puxada por dependência, não só pela seleção.
    motivo = regra.motivo_inaplicavel(ctx.empreendimento.declaracoes)
    if motivo is not None:
        from core.dominio.vocabulario import declaracoes as dec
        return regra.nao_avaliavel(
            motivo=motivos.NAO_APLICAVEL,
            mensagem=f"Não aplicável à declaração ({dec.rotulo(*motivo)}).",
        )

    # 0.1) Capacidade do insumo territorial (Enquadramento). Gate por regra: a
    #      granularidade da entrada define o subconjunto avaliável, e a causa é
    #      declarada em vez de somada ao balde genérico de não avaliável.
    if regra.exige_terreno:
        if ctx.empreendimento.terreno is None:
            return regra.nao_avaliavel(
                motivo=motivos.TERRENO_AUSENTE,
                mensagem="Terreno do empreendimento não definido; "
                         "checagem não avaliável.",
            )
        if not ctx.empreendimento.terreno.atende(regra.exige_terreno):
            return regra.nao_avaliavel(
                motivo=motivos.TERRENO_INSUFICIENTE,
                mensagem=f"A checagem exige {regra.exige_terreno} do terreno; "
                         f"a entrada forneceu apenas {ctx.empreendimento.terreno.nivel}.",
            )

    # 1) Dependências (ex.: porta espacial do EMP-001).
    for dep in regra.depende_de:
        if not ctx.prerequisito_conforme(dep):
            return regra.nao_avaliavel(
                motivo=motivos.PREREQUISITO_FALHO,
                mensagem=f"Pré-requisito {dep} não satisfeito; checagem não avaliável.",
            )

    # 2) Validação de informações (IDS), quando aplicável.
    if regra.ids_spec:
        ok, detalhe = validar_ids(ctx.modelo_ifc, regra.ids_spec)
        if not ok:
            return regra.nao_avaliavel(
                motivo=motivos.INFORMACAO_AUSENTE,
                mensagem=f"Validação IDS falhou ({detalhe}); informação ausente/incompatível.",
            )

    # 3) Checagem da regra propriamente dita.
    try:
        return regra.checar(ctx)
    except Exception as exc:  # robustez: uma regra com erro não derruba o lote
        return regra.nao_avaliavel(
            motivo=motivos.ERRO_DE_EXECUCAO,
            mensagem=f"Erro ao executar a checagem: {exc!r}",
        )


def _consolidar(rid: str, resultados: list[Resultado]) -> Resultado:
    """Reduz uma lista de resultados de instâncias a um resultado-resumo.

    Regra de consolidação: se qualquer instância é não conforme, o requisito é
    não conforme; se todas conformes, conforme; caso contrário, não avaliável.
    """
    estados = {r.estado for r in resultados}
    elementos = [e for r in resultados for e in r.elementos]
    descricao = resultados[0].descricao if resultados else ""

    if Estado.NAO_CONFORME in estados:
        estado = Estado.NAO_CONFORME
    elif estados == {Estado.CONFORME}:
        estado = Estado.CONFORME
    else:
        estado = Estado.NAO_AVALIAVEL

    nao_conformes = [r for r in resultados if r.estado is Estado.NAO_CONFORME]
    msg = (
        f"{len(nao_conformes)} de {len(resultados)} instância(s) não conforme(s)."
        if nao_conformes else f"{len(resultados)} instância(s) avaliada(s)."
    )
    return Resultado(
        regra_id=rid, estado=estado, descricao=descricao,
        elementos=elementos, mensagem=msg,
    )
