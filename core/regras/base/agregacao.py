"""Avaliação por limites: decidir uma agregação sob informação incompleta.

Uma agregação pergunta *quantos dos meus membros atendem?* e compara com um
limiar ``k``. O problema é que parte dos membros costuma não ter sido avaliada —
e exigir todos avaliados para concluir jogaria fora justamente os casos em que a
falta **não é capaz** de mudar o resultado.

Daí os dois limites::

    n_conf = membros confirmados conformes
    n_pot  = n_conf + membros não avaliáveis       (o melhor cenário possível)

    n_conf >= k   ->  CONFORME       (nenhum dado novo reverte)
    n_pot  <  k   ->  NÃO CONFORME   (nem no melhor cenário alcança o limiar)
    senão         ->  NÃO AVALIÁVEL, reportando [n_conf, n_pot] contra k

A mesma assimetria de ``core/dominio/mobilidade.py``, uma camada acima: lá a
pergunta era o que uma MEDIÇÃO autoriza concluir; aqui é o que um CONJUNTO
INCOMPLETO de resultados autoriza. Nos dois casos quem responde é o dado, e em
nenhum dos dois se inventa valor para o que falta.

O intervalo não é consolo — ele diz **quanto falta**. "3 a 6 itens confirmados,
exigidos 4" é informação de trabalho; "não avaliável" seco não é.

Por que o membro não avaliável nunca conta contra
-------------------------------------------------

Contá-lo como não conforme seria reprovar por ignorância — o mesmo defeito que
``confrontar_conjunto`` evita ao exigir o conjunto inteiro medido antes de
reprovar, e o mesmo que a sanidade do insumo persegue: lacuna não pode produzir falso
não-conforme. Lá a lacuna era de cadastro; aqui é de resultado, e a regra é
idêntica.

O teto de reprovabilidade
-------------------------

Se um membro declara que **não é avaliável por concepção** (``remete_a``, ver
``core/regras/base/remessa.py``), ele fica permanentemente dentro de ``n_pot``. Quando
o número desses membros alcança ``k``, a condição ``n_pot < k`` passa a ser
inalcançável e o requisito **pode ser aprovado, nunca reprovado**. Não é defeito
a corrigir: é propriedade da norma somada ao insumo disponível, e por isso viaja
declarada no ``detalhe`` em vez de ficar implícita. É a segunda assimetria do
módulo — a primeira vem da métrica (o piso euclidiano reprova e não aprova),
esta vem da estrutura normativa (um "ou" com alternativa não pública aprova e
não reprova).

A seleção exclusiva (ADR-026)
-----------------------------

O quarto modo não conta membros: ele escolhe **um**. Um requisito condicionado
à zona bioclimática é escrito em ramos mutuamente exclusivos (ZB 1–3 → ≤ 0,6;
ZB 4–8 → ≤ 0,4), e o seletor pode ser **desconhecido** — a cláusula do telhado
está presa ao vocabulário de 2005 (DN-08). Seja ``S`` o conjunto de ramos que
*podem* aplicar:

    |S| = 1  ->  o pai HERDA o veredito do ramo
    |S| > 1  ->  decide a UNANIMIDADE entre os vereditos que cada ramo teria
                 sob o próprio limite; discordância é INDECISÃO, nunca
                 reprovação (NÃO AVALIÁVEL, ``analise_humana_documental``)

``todos`` não serve aqui: dois candidatos com um conforme e um não conforme
caem em ``n_pot < k`` e o pai **reprova** — reprovaria um projeto que a norma
talvez aprove, o erro exato que a DN-08 existe para impedir. O teste que
prende a diferença está em ``tests/core/regras/base/test_agregacao.py`` §7.

O ramo é quem sabe se aplica: ele declara no próprio ``detalhe``
(``CHAVE_APLICABILIDADE``) se é aplicável, inaplicável ou indeterminado, e o
veredito que teria sob o próprio limite (``CHAVE_VEREDITO_RAMO``). O pai lê
as duas chaves e nada mais — não conhece zona, insumo nem limite. Ramo sem
resultado é candidato de veredito desconhecido, como no modo por limites.
"""

from __future__ import annotations

from core.dominio.contratos.regra import Contexto, Estado, Regra, Resultado, Verbo
from core.dominio.vocabulario import motivos, tipos_diagnostico

# --- Modos de agregação -----------------------------------------------------
# O vocabulário dos modos. O limiar `k` de cada modo sai de `k_de`, e não de
# `if`s nas regras: um modo novo se acrescenta aqui, sem tocar em regra nenhuma.
MODO_QUALQUER = "qualquer"            # "ou" normativo — basta um membro
MODO_TODOS = "todos"                  # "e" normativo — todos os membros
MODO_CONTAGEM_MINIMA = "contagem_minima"  # ">= k itens", com k declarado
MODO_SELECAO_EXCLUSIVA = "selecao_exclusiva"  # ramos exclusivos; um só aplica (ADR-026)

ROTULO_MODO = {
    MODO_QUALQUER: "satisfeito por qualquer dos membros",
    MODO_TODOS: "exige todos os membros",
    MODO_CONTAGEM_MINIMA: "exige um número mínimo de membros",
    MODO_SELECAO_EXCLUSIVA: "um só ramo aplica — herda o ramo aplicável ou "
                            "conclui pela unanimidade dos candidatos",
}

# --- O que um RAMO declara ao pai na seleção exclusiva (ADR-026) ----------
# Chaves de ``Resultado.detalhe`` do ramo. É o único canal entre ramo e pai:
# o pai não lê zona, insumo nem limite — lê o que o ramo declarou sobre si.
CHAVE_APLICABILIDADE = "aplicabilidade_do_ramo"
RAMO_APLICAVEL = "aplicavel"          # a zona resolvida seleciona este ramo
RAMO_INAPLICAVEL = "inaplicavel"      # a zona resolvida exclui este ramo
RAMO_INDETERMINADA = "indeterminada"  # não se sabe (DN-08 ou zona não resolvida)
# O veredito que o ramo TERIA sob o próprio limite (``Estado.value``), mesmo
# quando o estado que ele emite é NÃO AVALIÁVEL por aplicabilidade em aberto.
CHAVE_VEREDITO_RAMO = "veredito_sob_o_proprio_limite"

ROTULO_APLICABILIDADE = {
    RAMO_APLICAVEL: "aplicável à zona resolvida",
    RAMO_INAPLICAVEL: "não aplicável à zona resolvida",
    RAMO_INDETERMINADA: "aplicabilidade indeterminada",
}

# Chave de despacho do relatório dedicado da agregação.
TIPO_DIAGNOSTICO = tipos_diagnostico.AGREGACAO

# --- Como cada membro entra na contagem -------------------------------------
# Três valores, não dois: "confirmado" e "potencial" são estados DIFERENTES, pelo
# mesmo motivo que `atende_provado` e `dentro_do_piso` são diferentes no
# roteamento. Pintá-los igual na tela diria que o requisito está atendido
# enquanto o veredito diz NÃO AVALIÁVEL.
CONTA_CONFIRMADO = "confirmado"   # entra em n_conf e em n_pot
CONTA_POTENCIAL = "potencial"     # entra só em n_pot (poderia atender)
CONTA_FORA = "fora"               # não entra em nenhum dos dois
CONTA_NAO_CANDIDATO = "nao_candidato"  # seleção exclusiva: o ramo não aplica

ROTULO_CONTA = {
    CONTA_CONFIRMADO: "confirmado — atende",
    CONTA_POTENCIAL: "em aberto — poderia atender",
    CONTA_FORA: "avaliado — não atende",
    CONTA_NAO_CANDIDATO: "fora da seleção — o ramo não aplica à zona",
}


def k_de(modo: str, total_membros: int, k_declarado: int | None = None) -> int:
    """Limiar de conformes exigido pelo modo de agregação."""
    if modo == MODO_QUALQUER:
        return 1
    if modo == MODO_TODOS:
        return total_membros
    if modo == MODO_CONTAGEM_MINIMA:
        if not k_declarado or int(k_declarado) < 1:
            raise ValueError(
                "O modo 'contagem_minima' exige 'k_minimo' declarado (>= 1); "
                f"recebido {k_declarado!r}.")
        return int(k_declarado)
    if modo == MODO_SELECAO_EXCLUSIVA:
        # Um ramo aplica. O limiar não decide o veredito neste modo (quem
        # decide é ``selecao_exclusiva``); fica declarado para o diagnóstico.
        return 1
    raise ValueError(f"Modo de agregação desconhecido: {modo!r}")


def por_limites(estados: list[Estado | None],
                k: int) -> tuple[Estado, int, int]:
    """``(estado, n_conf, n_pot)`` para os estados dos membros contra o limiar.

    ``None`` — membro sem resultado, porque não foi executado — conta como não
    avaliável. Tratá-lo como inexistente encolheria ``n_pot`` e poderia produzir
    reprovação a partir de um membro que ninguém avaliou.
    """
    if not estados:
        raise ValueError("Agregação sem membros: nada a agregar.")

    n_conf = sum(1 for e in estados if e is Estado.CONFORME)
    n_pot = n_conf + sum(1 for e in estados
                         if e is None or e is Estado.NAO_AVALIAVEL)

    if n_conf >= k:
        return Estado.CONFORME, n_conf, n_pot
    if n_pot < k:
        return Estado.NAO_CONFORME, n_conf, n_pot
    return Estado.NAO_AVALIAVEL, n_conf, n_pot


# Resultado da seleção exclusiva: além do estado, POR QUE ele saiu assim.
SELECAO_HERDADO = "herdado"            # |S| = 1
SELECAO_UNANIME = "unanime"            # |S| > 1, todos concordam
SELECAO_DISCORDANTE = "discordante"    # |S| > 1, conforme x não conforme
SELECAO_PENDENTE = "pendente"          # algum candidato sem veredito próprio
SELECAO_SEM_CANDIDATO = "sem_candidato"


def selecao_exclusiva(candidatos: list[Estado | None]) -> tuple[Estado, str]:
    """``(estado, como)`` do pai a partir dos vereditos dos ramos CANDIDATOS.

    Recebe só os ramos que podem aplicar (os inaplicáveis já ficaram de fora),
    cada um com o veredito que teria sob o próprio limite — ``None`` quando o
    ramo não o tem (não executado, ou sem informação para concluir).

    Um candidato: herda. Mais de um: unanimidade decide; um candidato sem
    veredito impede a unanimidade (qualquer que seja o outro, o par ainda pode
    concordar ou discordar); e conforme × não conforme é **discordância**, que
    é indecisão declarada — NÃO reprovação. Ver o cabeçalho do módulo.
    """
    if not candidatos:
        return Estado.NAO_AVALIAVEL, SELECAO_SEM_CANDIDATO
    decididos = {e for e in candidatos if e in (Estado.CONFORME, Estado.NAO_CONFORME)}
    if len(candidatos) == 1:
        unico = candidatos[0]
        if unico in (Estado.CONFORME, Estado.NAO_CONFORME):
            return unico, SELECAO_HERDADO
        return Estado.NAO_AVALIAVEL, SELECAO_HERDADO
    if any(e not in (Estado.CONFORME, Estado.NAO_CONFORME) for e in candidatos):
        return Estado.NAO_AVALIAVEL, SELECAO_PENDENTE
    if decididos == {Estado.CONFORME}:
        return Estado.CONFORME, SELECAO_UNANIME
    if decididos == {Estado.NAO_CONFORME}:
        return Estado.NAO_CONFORME, SELECAO_UNANIME
    return Estado.NAO_AVALIAVEL, SELECAO_DISCORDANTE


def _estado_ou_none(valor: str) -> Estado | None:
    """``Estado`` a partir do ``value`` gravado no detalhe; ``None`` se vazio
    ou não avaliável — o ramo não tem veredito próprio a oferecer."""
    try:
        estado = Estado(valor) if valor else None
    except ValueError:
        return None
    return estado if estado in (Estado.CONFORME, Estado.NAO_CONFORME) else None


class RegraAgregacao(Regra):
    """Base das regras que decidem a partir de ``ctx.resultados``.

    A regra-pai não tem insumo próprio: a "fonte de dados" dela é interna, o que
    é a única coisa que a distingue de qualquer outra regra. Uma
    subclasse declara ``agrega``, ``modo`` e — só no modo de contagem mínima —
    ``k_minimo``.
    """

    verbo = Verbo.AGREGACAO
    modo: str = MODO_QUALQUER
    k_minimo: int | None = None
    # Como os membros são chamados nas mensagens e na unidade do resultado
    # ("alternativa(s)" nos "ou" do Anexo I; "item(ns)" nas qualificações).
    rotulo_membro: str = "alternativa(s)"

    # Sem pré-requisito e sem gate de terreno: o pai não mede nada, e um gate
    # aqui trocaria a causa verdadeira (o que falta nos membros) por uma causa
    # da moldura. Quem exige terreno são os membros, cada um por conta própria.
    depende_de: list[str] = []
    exige_terreno = ""

    # -- checagem ----------------------------------------------------------

    def checar(self, ctx: Contexto) -> Resultado:
        if not self.agrega:
            raise ValueError(
                f"A regra de agregação {self.id} não declarou membros em 'agrega'.")

        pares = [(mid, (ctx.resultados or {}).get(mid)) for mid in self.agrega]
        k = k_de(self.modo, len(self.agrega), self.k_minimo)
        if self.modo == MODO_SELECAO_EXCLUSIVA:
            return self._checar_selecao_exclusiva(pares, k)
        estado, n_conf, n_pot = por_limites(
            [r.estado if r is not None else None for _, r in pares], k)

        membros = [self._membro(mid, r) for mid, r in pares]
        comuns = {
            "valor_esperado": k,
            "valor_encontrado": n_conf,
            "unidade": self.rotulo_membro,
            # Os elementos dos membros sobem para o pai: é o que liga o
            # requisito agregado à geometria na visualização, sem que o pai
            # precise conhecer insumo nenhum.
            "elementos": [gid for _, r in pares if r is not None
                          for gid in r.elementos],
            "detalhe": self._detalhe(membros, k, n_conf, n_pot),
        }

        if estado is Estado.CONFORME:
            return self.conforme(mensagem=self._msg_conforme(membros, k), **comuns)
        if estado is Estado.NAO_CONFORME:
            return self.nao_conforme(
                mensagem=self._msg_nao_conforme(membros, k, n_pot), **comuns)
        return self.nao_avaliavel(motivo=self._motivo(membros),
                                  mensagem=self._msg_indeciso(membros, k,
                                                              n_conf, n_pot),
                                  **comuns)

    # -- seleção exclusiva (ADR-026) -----------------------------------------

    def _checar_selecao_exclusiva(self, pares: list[tuple[str, Resultado | None]],
                                  k: int) -> Resultado:
        membros = [self._membro(mid, r) for mid, r in pares]
        candidatos = [m for m in membros if m["conta_para"] != CONTA_NAO_CANDIDATO]
        vereditos = [_estado_ou_none(m["veredito_ramo"]) for m in candidatos]
        estado, como = selecao_exclusiva(vereditos)

        n_conf = sum(1 for m in candidatos if m["conta_para"] == CONTA_CONFIRMADO)
        n_pot = n_conf + sum(1 for m in candidatos
                             if m["conta_para"] == CONTA_POTENCIAL)
        detalhe = self._detalhe(membros, k, n_conf, n_pot)
        detalhe["candidatos"] = [m["id"] for m in candidatos]
        detalhe["selecao"] = como
        comuns = {
            "valor_esperado": "um ramo aplicável",
            "valor_encontrado": len(candidatos),
            "unidade": self.rotulo_membro,
            "elementos": [gid for _, r in pares if r is not None
                          for gid in r.elementos],
            "detalhe": detalhe,
        }
        ids = self._lista([m["id"] for m in candidatos])

        if estado is Estado.CONFORME:
            return self.conforme(mensagem=self._msg_selecao(como, ids, "conforme"),
                                 **comuns)
        if estado is Estado.NAO_CONFORME:
            return self.nao_conforme(
                mensagem=self._msg_selecao(como, ids, "não conforme"), **comuns)

        if como == SELECAO_SEM_CANDIDATO:
            motivo = motivos.NAO_APLICAVEL
            msg = (f"Nenhum dos {len(membros)} {self.rotulo_membro} aplica à "
                   "zona resolvida: o requisito não se aplica a este território.")
        elif como == SELECAO_DISCORDANTE:
            # O caso que o modo existe para tratar: os ramos candidatos dariam
            # vereditos opostos e não se sabe qual aplica (DN-08). Indecisão
            # declarada, remetida ao parecer — nunca reprovação.
            motivo = motivos.ANALISE_HUMANA_DOCUMENTAL
            msg = (f"Os ramos candidatos discordam ({ids}) e a Portaria não "
                   "permite saber qual deles aplica: o veredito fica em aberto "
                   "e é remetido ao parecer do analista — não é reprovação.")
        else:
            # Herdado de um ramo sem veredito, ou candidato pendente: a causa
            # é a do(s) ramo(s), como no modo por limites.
            pendentes = [m for m in candidatos if m["conta_para"] == CONTA_POTENCIAL]
            motivo = self._motivo(pendentes)
            lista = "; ".join(
                f"{m['id']} — {m['rotulo_motivo'] or 'sem causa declarada'}"
                for m in pendentes)
            msg = (f"{len(candidatos)} ramo(s) candidato(s) e ao menos um sem "
                   f"veredito próprio; o pai não conclui. Em aberto: {lista}.")
        return self.nao_avaliavel(motivo=motivo, mensagem=msg, **comuns)

    def _msg_selecao(self, como: str, ids: str, veredito: str) -> str:
        if como == SELECAO_HERDADO:
            return (f"Um só ramo aplica ({ids}): o requisito herda o veredito "
                    f"dele — {veredito}.")
        return (f"Não se sabe qual dos ramos aplica ({ids}), mas todos dão o "
                f"mesmo veredito sob o próprio limite — {veredito} sob qualquer "
                "leitura da zona.")

    # -- membros -----------------------------------------------------------

    def _membro(self, mid: str, r: Resultado | None) -> dict:
        """Uma linha por membro, com o que ele contribuiu e o que falta nele.

        O ``automatizavel`` NÃO é deduzido aqui a partir de uma lista de ids: ele
        vem do ``detalhe`` do próprio membro, do mesmo modo que
        ``limite_inferior`` viaja dentro da ``Medicao`` em vez de a regra
        perguntar o nome do provedor. Membro que não declara nada é tratado como
        automatizável, que é o caso comum.
        """
        detalhe = (r.detalhe or {}) if r is not None else {}
        if r is None:
            estado, conta = "", CONTA_POTENCIAL
            motivo = motivos.MEMBRO_NAO_EXECUTADO
        else:
            estado = r.estado.value
            conta = {Estado.CONFORME: CONTA_CONFIRMADO,
                     Estado.NAO_CONFORME: CONTA_FORA}.get(r.estado,
                                                          CONTA_POTENCIAL)
            motivo = detalhe.get(motivos.CHAVE, "")
        # Seleção exclusiva (ADR-026): o que conta é o que o RAMO declarou
        # sobre si — se aplica, e o veredito sob o próprio limite —, não o
        # estado que ele emitiu (NÃO AVALIÁVEL por aplicabilidade em aberto).
        aplicabilidade = detalhe.get(CHAVE_APLICABILIDADE, "")
        veredito_ramo = detalhe.get(CHAVE_VEREDITO_RAMO, "") or estado
        if self.modo == MODO_SELECAO_EXCLUSIVA:
            if aplicabilidade == RAMO_INAPLICAVEL:
                conta = CONTA_NAO_CANDIDATO
            else:
                conta = {Estado.CONFORME.value: CONTA_CONFIRMADO,
                         Estado.NAO_CONFORME.value: CONTA_FORA}.get(
                             veredito_ramo, CONTA_POTENCIAL)
        membro = {
            "id": mid,
            "executado": r is not None,
            "descricao": r.descricao if r is not None else "",
            "mensagem": r.mensagem if r is not None else "",
            "estado": estado,
            "conta_para": conta,
            "rotulo_conta": ROTULO_CONTA[conta],
            "motivo": motivo,
            "rotulo_motivo": motivos.rotulo(motivo),
            "acao": motivos.ACAO.get(motivo, ""),
            "automatizavel": detalhe.get("automatizavel", True),
            "remetido_a": detalhe.get("remetido_a", ""),
        }
        # As chaves do ramo só existem na seleção exclusiva: nos outros modos
        # o relatório fica byte a byte o que era (o Enquadramento é linha de
        # base do Estrela I e não pode mudar por uma agregação que não é dele).
        if self.modo == MODO_SELECAO_EXCLUSIVA:
            membro.update({
                "aplicabilidade": aplicabilidade,
                "rotulo_aplicabilidade": ROTULO_APLICABILIDADE.get(aplicabilidade, ""),
                "veredito_ramo": veredito_ramo,
            })
        return membro

    def _motivo(self, membros: list[dict]) -> str:
        """Herda a causa dos membros pendentes quando ela é única.

        A taxonomia existe para que cada não avaliável aponte o que o destrava.
        Um `agregacao_indecisa` aplicado sempre trocaria "obtenha a declaração da
        Prefeitura" por "veja a lista de membros" mesmo quando há uma única
        pendência — perda gratuita de especificidade. Quando as causas divergem,
        porém, não há uma ação a nomear, e aí o motivo genérico é o honesto.
        """
        pendentes = {m["motivo"] for m in membros
                     if m["conta_para"] == CONTA_POTENCIAL and m["motivo"]}
        if len(pendentes) == 1:
            return pendentes.pop()
        return motivos.AGREGACAO_INDECISA

    # -- diagnóstico -------------------------------------------------------

    def _detalhe(self, membros: list[dict], k: int,
                 n_conf: int, n_pot: int) -> dict:
        irredutiveis = [m["id"] for m in membros if m["automatizavel"] is False]
        return {
            # Chave de despacho do relatório (``app/paginas/relatorio.py``).
            "tipo": TIPO_DIAGNOSTICO,
            "modo": self.modo,
            "rotulo_modo": ROTULO_MODO.get(self.modo, self.modo),
            "k": k,
            "n_conf": n_conf,
            "n_pot": n_pot,
            "total_membros": len(membros),
            "rotulo_membro": self.rotulo_membro,
            # A EVIDÊNCIA, não só a conclusão: o relatório do pai se reproduz
            # daqui sem reler resultado nenhum, como o das regras de distância.
            "membros": membros,
            # O teto declarado. Ver o cabeçalho deste módulo.
            "reprovabilidade": {
                "reprovavel": len(irredutiveis) < k,
                "membros_irredutiveis": irredutiveis,
                "explicacao": self._explicacao_teto(irredutiveis, k),
            },
        }

    def _explicacao_teto(self, irredutiveis: list[str], k: int) -> str:
        if not irredutiveis:
            return ("Todos os membros são avaliáveis pela ferramenta: o requisito "
                    "pode ser aprovado e reprovado.")
        if len(irredutiveis) < k:
            return (f"{self._lista(irredutiveis)} não é avaliável pela ferramenta, "
                    f"mas o mínimo de {k} ainda pode ser excluído pelos demais "
                    "membros — o requisito continua podendo ser reprovado.")
        return (f"{self._lista(irredutiveis)} não é avaliável pela ferramenta e "
                f"permanece em aberto, então o mínimo de {k} nunca pode ser "
                "excluído: este requisito pode ser APROVADO, nunca REPROVADO. "
                "É limitação da norma somada ao insumo disponível, não do motor.")

    # -- textos ------------------------------------------------------------

    @staticmethod
    def _lista(ids: list[str]) -> str:
        if len(ids) <= 1:
            return "".join(ids)
        return ", ".join(ids[:-1]) + " e " + ids[-1]

    def _msg_conforme(self, membros: list[dict], k: int) -> str:
        confirmados = [m["id"] for m in membros
                       if m["conta_para"] == CONTA_CONFIRMADO]
        if self.modo == MODO_QUALQUER:
            return (f"Critério satisfeito por {self._lista(confirmados)}: basta "
                    f"uma das {len(membros)} alternativas, e nenhum dado novo "
                    "reverte isso.")
        return (f"{len(confirmados)} de {len(membros)} {self.rotulo_membro} "
                f"confirmado(s) — exigido(s) {k}: {self._lista(confirmados)}.")

    def _msg_nao_conforme(self, membros: list[dict], k: int, n_pot: int) -> str:
        if self.modo == MODO_QUALQUER:
            return (f"Nenhuma das {len(membros)} alternativas atende, e todas "
                    "foram avaliadas — o requisito não é satisfeito por "
                    "nenhuma via.")
        return (f"Nem no melhor cenário o mínimo é alcançado: no máximo {n_pot} "
                f"de {len(membros)} {self.rotulo_membro}, exigido(s) {k}.")

    def _msg_indeciso(self, membros: list[dict], k: int,
                      n_conf: int, n_pot: int) -> str:
        pendentes = [m for m in membros if m["conta_para"] == CONTA_POTENCIAL]
        lista = "; ".join(f"{m['id']} — {m['rotulo_motivo'] or 'sem causa declarada'}"
                          for m in pendentes)
        return (f"Entre {n_conf} e {n_pot} de {len(membros)} "
                f"{self.rotulo_membro} atendem; o mínimo é {k}, e o intervalo "
                f"não decide. Em aberto: {lista}.")
