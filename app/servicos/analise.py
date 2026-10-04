"""Execução da análise (`core.composicao.rodar`) — a única parte de
`_analisar`/`acao_sem_ifc` que toca o núcleo (`app/servicos`
é o único importador de `core/`). A parte visual (spinner, `st.error`,
`st.rerun`) fica em `app/componentes/acao.py`.

ADR-004: as duas funções passam a
receber o `Empreendimento` da sessão e chamam `composicao.rodar(empreendimento
=...)` — o caminho novo — em vez da assinatura antiga de
argumentos soltos. É o que dá a cada relatório uma referência ESTÁVEL
(`meta.empreendimento.id`) ao empreendimento que o gerou, necessária para
uma tela detectar relatório desatualizado (regra 4 do §4.3) comparando com
`app.servicos.empreendimento.referencia_atual()`.

ADR-001: as duas funções também recebem
a `chave` da checagem (``"enquadramento"``, ``"georref"``, ``"programa"``)
e repassam a `composicao.rodar(destino_rel=...)` o caminho por checagem que
`app.servicos.relatorios.caminho(chave)` resolve
(``artefatos/relatorios/<chave>.json``) — cada checagem passa a gravar o
seu próprio relatório em vez de todas sobrescreverem
``artefatos/relatorio.json``, o que permite às telas de resultados
consolidados (2.4.1/2.4.2) lerem os relatórios das várias checagens ao
mesmo tempo.

``declaracoes_locais`` são as condições de contorno que continuam sendo
declaradas NA PRÓPRIA TELA (hoje só a natureza do modelo): entram por cima
de `empreendimento.declaracoes` num INSTANTÂNEO da análise — o objeto
persistido do chamador não é alterado (mesmo princípio de
`core.aplicacao.pipeline._instantaneo`, que faz o mesmo com o schema lido
do IFC).

ADR-021: o nº de UHs deixou de ser declaração. O número que a tela informa
sobre o arquivo enviado é `unidades_representadas`, e viaja como propriedade
do `ModeloBIM` que este módulo monta — não mais como uma chave de
`declaracoes`. A tipologia, também por força do ADR-021, é lida da
unidade tipo em análise (`UnidadeTipo`, ADR-023) e entregue ao guard de
aplicabilidade junto das declarações: `declaracoes_da_analise` é o ponto onde as duas origens se
encontram, e é a MESMA fusão que decide `grupos.ids_executaveis` e que roda
a análise — separá-las já produziu veredito divergente.

ADR-021: é ESTE módulo quem resolve **qual contêiner** a análise lê, e o entrega a `composicao.rodar(conteiner=...)`. O
núcleo deixou de procurá-lo num campo fixo do empreendimento: a tela
conhece a submissão — o arquivo que acabou de ser enviado, a natureza declarada
nela, quantas UHs ele representa — e o núcleo, não. É o que permite analisar um
contêiner de terreno sem ter de pendurá-lo em alguma entidade só para o
pipeline achá-lo.

ADR-023: e é este módulo quem resolve **a quem o arquivo pertence**. Com as
duas coleções do ADR-023 — unidades tipo e edificações físicas —, "a natureza
do modelo" deixou de bastar como resposta: ela diz o que o arquivo contém
(pré-condição das regras EDI), não de quem ele é. O ``alvo`` diz de quem, por
id, e as constantes abaixo são o vocabulário dessa resposta.
"""

from __future__ import annotations

import dataclasses

from app.servicos import relatorios
from core import composicao
from core.aplicacao import diagnosticos as diag
from core.dominio import ancora
from core.dominio.empreendimento import Empreendimento, ModeloBIM
from core.dominio.unidade_tipo import UnidadeTipo
from core.dominio.vocabulario import declaracoes as dec

# --- O alvo da análise (ADR-023) -------------------------------------------
#
# A tela sabe a quem o arquivo enviado pertence; o núcleo, não. Antes de haver
# duas coleções, essa resposta cabia numa categoria abstrata ("a natureza do modelo") porque
# só existia uma entidade a que pendurar o contêiner. Com as duas coleções do
# ADR-023 a resposta passa a ter endereço, e é isto que estas constantes
# nomeiam. O formato é texto — e não um par (tipo, id) — porque atravessa
# `st.selectbox` e `st.session_state`, que guardam valores simples.
ALVO_DEDUZIDO = ""          # a CLI, a suíte, quem não conhece a composição
ALVO_TERRENO = "terreno"    # só o terreno
ALVO_TODAS = "todas"        # terreno com as edificações
PREFIXO_UNIDADE_TIPO = "unidade_tipo:"
PREFIXO_EDIFICACAO = "edificacao:"


def alvo_de_unidade_tipo(id_unidade_tipo: str) -> str:
    """O alvo que nomeia uma unidade tipo pelo id."""
    return f"{PREFIXO_UNIDADE_TIPO}{id_unidade_tipo}"


def alvo_de_edificacao(id_edificacao: str) -> str:
    """O alvo que nomeia uma edificação física pelo id."""
    return f"{PREFIXO_EDIFICACAO}{id_edificacao}"


def tipologia_do_alvo(empreendimento, alvo: str) -> str:
    """A tipologia de que a análise vai falar, dado o alvo escolhido na tela.

    É a mesma resposta que `_instantaneo_da_analise` vai produzir, só que
    ANTES de haver arquivo — a tela precisa dela para avisar, ou não avisar,
    que a tipologia está por declarar. Sem isto o aviso caía na dedução sobre
    o agregado inteiro e acusava "tipologia não declarada" num empreendimento
    com duas unidades tipo, cada uma com a sua: a dedução recusa escolher entre duas, com razão — mas a tela
    já sabe qual é, porque o autor apontou.

    Com o alvo em `todas`, `terreno` ou sem alvo, cai na dedução de sempre,
    que é exatamente o que essas três significam: ninguém apontou uma.
    """
    if alvo.startswith(PREFIXO_UNIDADE_TIPO):
        unidade_tipo = empreendimento.unidade_tipo_por_id(
            alvo[len(PREFIXO_UNIDADE_TIPO):])
        return unidade_tipo.tipologia if unidade_tipo is not None else ""
    if alvo.startswith(PREFIXO_EDIFICACAO):
        id_alvo = alvo[len(PREFIXO_EDIFICACAO):]
        edificacao = next((e for e in empreendimento.edificacoes
                           if e.id == id_alvo), None)
        return (empreendimento.tipologia_de(edificacao)
                if edificacao is not None else "")
    return ancora.tipologia_em_analise(empreendimento)


def heterogeneidade_do_alvo(empreendimento, alvo: str) -> str:
    """O aviso de heterogeneidade ANTES de analisar, ou ``""`` se não cabe.

    Analisar UH mistas em agregado pode levar a veredito enganoso, e o usuário
    precisa do aviso antes de rodar — não só em ``meta``, depois de a análise
    já ter rodado. O diagnóstico tem dois momentos (marca, não reprova, com
    rótulo próprio), e este é o primeiro.

    A pergunta aqui é a mesma de ``core.aplicacao.diagnosticos``, feita sem
    arquivo: lá o escopo vem dos DONOS do contêiner, aqui do alvo que o autor
    apontou — é a única coisa que se sabe antes de haver submissão. A frase é a
    de lá, para tela e relatório não divergirem.
    """
    if not alvo.startswith(PREFIXO_EDIFICACAO):
        return ""
    id_alvo = alvo[len(PREFIXO_EDIFICACAO):]
    edificacao = next((e for e in empreendimento.edificacoes
                       if e.id == id_alvo), None)
    if edificacao is None or len(edificacao.composicao) < 2:
        return ""
    return diag.mensagem_heterogeneidade(len(edificacao.composicao))


def declaracoes_da_analise(empreendimento: Empreendimento | None,
                           declaracoes_locais: dict | None,
                           conteiner: ModeloBIM | None = None) -> dict:
    """As condições desta análise: declarações do empreendimento (2.1.1), a
    tipologia de que a análise fala e as declarações locais da tela.

    A tipologia entra por cima das declarações e por baixo das locais. Por cima
    porque a unidade tipo é a dona dela (ADR-021) e uma tipologia sobrevivente
    nas declarações de um artefato antigo não pode vencer a da entidade; por
    baixo porque a tela continua sendo o último a falar sobre o modelo que
    acabou de ser enviado. Mesma precedência de `pipeline._instantaneo`, e de
    propósito: é a mesma pergunta respondida nos dois lugares.

    ``conteiner`` (ADR-023) é a âncora desta análise, quando já se sabe qual é:
    aí a tipologia vem dos DONOS dele, por precedência (tipo > edificação >
    terreno), e não de uma dedução sobre o agregado inteiro. Quem chama antes
    de haver arquivo — a lista de ids executáveis que a tela mostra ao abrir —
    não o tem, e segue pela dedução de sempre. O empreendimento passado precisa
    ser aquele em que o contêiner JÁ está pendurado (o instantâneo), porque é
    por ele que os donos são achados."""
    base = dict(empreendimento.declaracoes) if empreendimento is not None else {}
    tipologia = ancora.tipologia_em_analise(empreendimento, conteiner)
    if tipologia:
        base[dec.TIPOLOGIA] = tipologia
    base.update(declaracoes_locais or {})
    return base


def _instantaneo_da_analise(empreendimento: Empreendimento,
                            declaracoes_locais: dict,
                            caminho_ifc: str = "",
                            unidades_representadas: int = 0,
                            alvo: str = ALVO_DEDUZIDO
                            ) -> tuple[Empreendimento, ModeloBIM | None]:
    """O empreendimento e o CONTÊINER desta análise: as condições da tela
    fundidas e, havendo IFC, o `ModeloBIM` do arquivo enviado.
    Mesmo `id`/`versao` do original — `dataclasses.replace` não os toca.

    Devolve os dois porque são duas perguntas: o empreendimento diz o que está
    declarado, e o contêiner diz o que esta execução vai ler. O segundo é a
    âncora que `composicao.rodar` recebe (D2) — e é por ele existir como
    argumento que o campo legado `Empreendimento.modelo` pôde sair.

    **A ordem é contêiner → dono → declarações** (ADR-023), e não a inversa de
    antes: a tipologia da análise é lida dos donos do contêiner, e só existe
    dono depois de o contêiner ter sido pendurado. Montar as declarações
    primeiro devolvia a tipologia de uma dedução sobre o agregado inteiro — que
    é a resposta certa só quando ninguém disse qual é o alvo.

    Nada do objeto do chamador é alterado: quem ganha contêiner é RECRIADO por
    `dataclasses.replace` (preservando o `id`, então continua sendo o mesmo),
    nunca mutado no lugar — o empreendimento da sessão não foi editado por ter
    sido analisado."""
    if not caminho_ifc:
        return (dataclasses.replace(
            empreendimento,
            declaracoes=declaracoes_da_analise(empreendimento,
                                               declaracoes_locais)), None)

    natureza = (declaracoes_locais or {}).get(dec.TIPO_MODELO, "")
    conteiner = ModeloBIM(caminho=caminho_ifc, natureza=natureza,
                          unidades_representadas=unidades_representadas)
    anexado = _com_conteiner(empreendimento, conteiner, natureza, alvo)
    return dataclasses.replace(
        anexado,
        declaracoes=declaracoes_da_analise(anexado, declaracoes_locais,
                                           conteiner)), conteiner


def _com_conteiner(empreendimento: Empreendimento, conteiner: ModeloBIM,
                   natureza: str, alvo: str) -> Empreendimento:
    """O empreendimento com o contêiner pendurado em quem a tela apontou.

    O mesmo objeto de valor pode ficar pendurado em mais de um dono ao mesmo
    tempo (ADR-023) — é o caso de "Terreno com as edificações" —, e quem
    desempata na leitura é a precedência de `core.dominio.ancora`, não uma
    escolha feita aqui.

    **Terreno** : com natureza ``terreno`` ou
    ``terreno_com_edificacoes`` o contêiner vai TAMBÉM para `Terreno.modelo`
    **do instantâneo** — efêmero, como tudo nesta análise. É o arquivo
    submetido descrevendo também o terreno; o efeito visível é
    `meta.terreno.modelo` do relatório de Georreferenciamento deixar de ser
    `null`. Não é veredito: nenhuma regra lê esse campo, e o EMP-001 continua
    lendo o contêiner pela âncora. Sem terreno declarado não há onde
    pendurá-lo, e a análise corre igual — a âncora é argumento.

    **Alvo**: `terreno` não pendura em mais ninguém; `unidade_tipo:<id>` e
    `edificacao:<id>` penduram exatamente naquele, e um id que não corresponde
    a nada (tela desatualizada, entidade removida entre o formulário e o
    clique) não inventa entidade nenhuma — a coleção volta intacta, mesma
    postura de quando a dedução falha; `todas` pendura em todas as edificações
    físicas e, não havendo nenhuma, no único tipo (com dois ou mais tipos e
    nenhuma física, em nenhum: a tipologia sai `""` e a heterogeneidade é
    diagnóstico da fase seguinte).

    Sem alvo (`ALVO_DEDUZIDO` — a CLI, a suíte, quem chama sem conhecer a
    composição) vale o comportamento anterior: com natureza que contém
    edificação, o contêiner vai para a unidade tipo em análise; sem nenhuma
    declarada, uma é sintetizada PARA ESTA ANÁLISE e não é gravada (o arquivo
    enviado é uma unidade tipo — "um IFC = uma unidade tipo" —, e sem ela não
    haveria onde pendurar as UHs que a tela informou; gravá-la seria a
    interface inventando composição que ninguém declarou, e quem declara
    composição é 2.1.1).
    """
    mudancas: dict = {}

    terreno = empreendimento.terreno
    if terreno is not None and natureza in (dec.TERRENO,
                                            dec.TERRENO_COM_EDIFICACOES):
        mudancas["terreno"] = dataclasses.replace(terreno, modelo=conteiner)

    unidades_tipo, edificacoes = _donos_do_alvo(empreendimento, conteiner,
                                                natureza, alvo)
    if unidades_tipo is not None:
        mudancas["unidades_tipo"] = unidades_tipo
    if edificacoes is not None:
        mudancas["edificacoes"] = edificacoes
    return dataclasses.replace(empreendimento, **mudancas)


def _donos_do_alvo(empreendimento: Empreendimento, conteiner: ModeloBIM,
                   natureza: str, alvo: str):
    """As duas coleções com o contêiner anexado, ou ``None`` onde nada muda."""
    if alvo == ALVO_TERRENO:
        return None, None

    if alvo.startswith(PREFIXO_UNIDADE_TIPO):
        id_alvo = alvo[len(PREFIXO_UNIDADE_TIPO):]
        return _anexado_a(empreendimento.unidades_tipo, id_alvo, conteiner), None

    if alvo.startswith(PREFIXO_EDIFICACAO):
        id_alvo = alvo[len(PREFIXO_EDIFICACAO):]
        return None, _anexado_a(empreendimento.edificacoes, id_alvo, conteiner)

    if alvo == ALVO_TODAS:
        if empreendimento.edificacoes:
            return None, [dataclasses.replace(e, modelo=conteiner)
                          for e in empreendimento.edificacoes]
        if not empreendimento.unidades_tipo:
            return [UnidadeTipo(modelo=conteiner)], None
        if len(empreendimento.unidades_tipo) == 1:
            return [dataclasses.replace(empreendimento.unidades_tipo[0],
                                        modelo=conteiner)], None
        return None, None

    if natureza in dec.COM_EDIFICACAO:
        return _por_deducao(empreendimento, conteiner), None
    return None, None


def _anexado_a(colecao: list, id_alvo: str, conteiner: ModeloBIM) -> list:
    """A coleção com o contêiner em quem tem este ``id``; intacta se não há."""
    if not any(item.id == id_alvo for item in colecao):
        return list(colecao)
    return [dataclasses.replace(item, modelo=conteiner)
            if item.id == id_alvo else item for item in colecao]


def _por_deducao(empreendimento: Empreendimento, conteiner: ModeloBIM) -> list:
    """A coleção de unidades tipo pela dedução da âncora — o comportamento de
    quem chama sem alvo, preservado."""
    unidades_tipo = empreendimento.unidades_tipo
    if not unidades_tipo:
        return [UnidadeTipo(modelo=conteiner)]
    alvo = ancora.unidade_tipo_em_analise(empreendimento)
    if alvo is None:
        return unidades_tipo
    return [dataclasses.replace(u, modelo=conteiner) if u.id == alvo.id else u
            for u in unidades_tipo]


def analisar_modelo(chave: str, empreendimento: Empreendimento, caminho_ifc: str,
                    ids: list[str], declaracoes_locais: dict,
                    unidades_representadas: int = 0,
                    alvo: str = ALVO_DEDUZIDO) -> dict:
    """Roda o pipeline sobre um modelo IFC enviado.

    Devolve o relatório cru — que pode conter ``erro_ingestao``; cabe
    ao chamador tratar esse caso, que é comum às duas telas que analisam
    modelo (Georreferenciamento e Programa de necessidades). ``chave``
    é a checagem que está rodando — decide onde o relatório é
    gravado em disco (``app.servicos.relatorios.caminho``). ``alvo`` (ADR-023)
    é a quem o arquivo enviado pertence, escolhido por NOME na tela entre o que
    2.1.1 declarou; ver `_com_conteiner`.
    """
    instantaneo, conteiner = _instantaneo_da_analise(
        empreendimento, declaracoes_locais, caminho_ifc, unidades_representadas,
        alvo)
    return composicao.rodar(empreendimento=instantaneo, conteiner=conteiner,
                          ids_selecionados=ids,
                          destino_rel=relatorios.caminho(chave))


def analisar_sem_modelo(chave: str, empreendimento: Empreendimento,
                        ids: list[str]) -> dict:
    """Roda o pipeline sem modelo IFC e sem provedor de rede — o insumo é só o
    que o `Empreendimento` declara e o que o território resolve a partir do
    município (a Qualificação urbanística, ADR-028/030). ``chave``: ver
    `analisar_modelo`."""
    return composicao.rodar(empreendimento=empreendimento, ids_selecionados=ids,
                          destino_rel=relatorios.caminho(chave))


def analisar_enquadramento(chave: str, empreendimento: Empreendimento,
                           ids: list[str], roteador_rede) -> dict:
    """Roda o pipeline sem modelo IFC — o insumo do Enquadramento é o
    terreno e a localização já declarados no `Empreendimento` (2.1.1 e a
    própria tela de Enquadramento). ``chave``: ver `analisar_modelo`."""
    return composicao.rodar(empreendimento=empreendimento, ids_selecionados=ids,
                          roteador_rede=roteador_rede,
                          destino_rel=relatorios.caminho(chave))
