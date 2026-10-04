"""Qual unidade tipo — e qual contêiner — esta análise está lendo.

O ADR-021 dá dono a cada um dos três números de UH e decide que a regra
dimensional consome **um só**: o ``unidades_representadas`` do contêiner
efetivamente lido. Fica faltando responder *qual* é esse contêiner — e essa é
uma pergunta sobre o agregado, não uma regra normativa: a resposta sai só
do ``Empreendimento`` e do ``Contexto``, e por isso o módulo mora no domínio,
como serviço de domínio que as regras e a aplicação consultam. Se cada regra a
respondesse por conta própria, a mesma análise teria quatro respostas, e a
divergência apareceria como veredito, no lugar mais caro de investigar.

A âncora chega por argumento; a dedução é o que resta
-----------------------------------------------------

A âncora da execução é argumento nomeado de ``composicao.rodar`` (ADR-021):
quem conhece a submissão — a tela, por ``app/servicos/analise.py`` — resolve
**qual contêiner analisar** e o passa adiante; o pipeline o guarda em
``Contexto.conteiner`` e a regra o lê de lá, por ``conteiner_da_execucao``.
Com ``None`` (a CLI, os contextos montados à mão, a suíte) vale a dedução
daqui, que é o comportamento anterior: a unidade tipo em análise é a única
que pode ser, e o contêiner é o dela.

O campo legado ``Empreendimento.modelo`` **não existe mais** (ADR-023):
um contêiner que ninguém anexou a uma unidade tipo nem ao terreno já não tem
onde morar no agregado — e é exatamente por isso que a âncora explícita
precisou chegar antes de o campo sair.

O dono do contêiner (ADR-023)
-----------------------------

O mesmo ``ModeloBIM`` — objeto de valor — pode estar pendurado em mais de um
dono ao mesmo tempo: a migração do esquema antigo, com
``terreno_com_edificacoes``, anexa o **mesmo** contêiner ao ``Terreno`` e à
unidade tipo sintetizada. Por isso a tipologia de uma análise que recebeu
âncora não é lida de "a unidade tipo" e sim dos **donos** do contêiner, com
precedência **tipo > edificação física > terreno**: o terreno só é dono quando
ninguém mais é. É o que mantém o EDI falando da UH quando terreno e unidade
tipo coexistem. A edificação física não tem tipologia própria — a dela é
derivada da composição, pela raiz (``Empreendimento.tipologia_de``). Pares no
mesmo nível (quatro torres iguais sobre o mesmo VO; duas físicas em "todas")
não são recusados: se todos derivam a mesma tipologia, é ela; se divergem,
``""``. Recusar seria perder a tipologia justamente no caso que o ADR-023
trata como equivalente.

"Igual" aqui é igualdade do que foi **declarado** — caminho, natureza, UHs
representadas. ``schema`` é descoberto ao abrir o arquivo e carimbado no
contêiner da execução pelo pipeline; ``digest`` é calculado. Nenhum dos dois
faz de um contêiner outro contêiner.

Por que o terreno entra na dedução
----------------------------------

O ADR-023 anexa o contêiner pela natureza declarada, e ``terreno`` o pendura no
``Terreno``. Sem unidade tipo nem edificação com contêiner, é ele o único que
a submissão trouxe — e é ele que o pipeline abriu. A escada da dedução é a
mesma da precedência: tipo → edificação → terreno. Ler o terreno **depois**, e
não antes, é o que mantém o EDI falando da geometria da UH quando as duas
existem.

Ambiguidade não vira sorteio
----------------------------

Com mais de uma candidata não há resposta honesta, e o chamador recebe
``None`` — que as regras traduzem no piso de 1 UH, o mesmo comportamento
conservador de quando nada foi declarado. Escolher "a primeira" seria eleger um
denominador por ordem de lista e apresentá-lo como fato do projeto. Quem elimina
o caso de vez é a âncora explícita, não uma heurística melhor.

Anel: domínio (ADR-002). Nenhum I/O — só leitura do agregado e do contexto.
"""

from __future__ import annotations

from core.dominio.edificacao import Edificacao
from core.dominio.modelo_bim import ModeloBIM
from core.dominio.unidade_tipo import UnidadeTipo


def mesmo_conteiner(a: ModeloBIM | None, b: ModeloBIM | None) -> bool:
    """Os dois referem o mesmo contêiner DECLARADO (ADR-023).

    Compara o que a submissão diz — caminho, natureza, UHs representadas — e
    ignora o que a execução descobre (``schema``) ou calcula (``digest``): o
    pipeline carimba o schema lido no contêiner da execução antes de montar o
    instantâneo, e sem esta tolerância o contêiner nunca acharia o dono a que a
    própria tela o anexou.
    """
    if a is None or b is None:
        return False
    return ((a.caminho, a.natureza, a.unidades_representadas)
            == (b.caminho, b.natureza, b.unidades_representadas))


def unidade_tipo_em_analise(empreendimento) -> UnidadeTipo | None:
    """A unidade tipo cuja geometria esta análise lê, ou ``None`` se não há como saber.

    Uma só unidade tipo: é ela. Várias, e uma única com contêiner: é a única
    que tem geometria a ser lida. Várias com contêiner: ver a docstring do
    módulo.
    """
    unidades_tipo = list(getattr(empreendimento, "unidades_tipo", None) or [])
    if len(unidades_tipo) == 1:
        return unidades_tipo[0]
    com_conteiner = [u for u in unidades_tipo if u.modelo is not None]
    return com_conteiner[0] if len(com_conteiner) == 1 else None


def edificacao_em_analise(empreendimento) -> Edificacao | None:
    """A edificação física cuja geometria esta análise lê, ou ``None``.

    Mesma regra da unidade tipo, no nível seguinte da escada: uma só, é ela;
    várias e uma única com contêiner, é essa; várias com contêiner, recusa.
    """
    edificacoes = list(getattr(empreendimento, "edificacoes", None) or [])
    if len(edificacoes) == 1:
        return edificacoes[0]
    com_conteiner = [e for e in edificacoes if e.modelo is not None]
    return com_conteiner[0] if len(com_conteiner) == 1 else None


def conteiner_em_analise(empreendimento) -> ModeloBIM | None:
    """O contêiner DEDUZIDO do agregado — tipo → edificação → terreno.

    É a resposta de quem tem só o empreendimento na mão: a persistência, ao
    dizer o que o artefato declara, e o pipeline quando ninguém lhe passou
    âncora. Quem tem o ``Contexto`` pergunta a ``conteiner_da_execucao``, que
    respeita a âncora explícita antes de cair aqui.
    """
    unidade_tipo = unidade_tipo_em_analise(empreendimento)
    if unidade_tipo is not None and unidade_tipo.modelo is not None:
        return unidade_tipo.modelo
    edificacao = edificacao_em_analise(empreendimento)
    if edificacao is not None and edificacao.modelo is not None:
        return edificacao.modelo
    terreno = getattr(empreendimento, "terreno", None)
    return getattr(terreno, "modelo", None) if terreno is not None else None


def conteiner_da_execucao(ctx) -> ModeloBIM | None:
    """O contêiner que ESTA execução abriu: a âncora recebida, ou a dedução.

    Ponto único de resposta para as regras. ``Contexto.conteiner`` é preenchido
    por ``composicao.montar_contexto`` e corresponde, campo a campo, ao
    ``ctx.modelo_ifc`` aberto (o ``schema`` inclusive). Um contexto montado à
    mão não o traz, e aí vale o que o agregado permite deduzir — que é o que a
    suíte de regras exercita.
    """
    conteiner = getattr(ctx, "conteiner", None)
    if conteiner is not None:
        return conteiner
    return conteiner_em_analise(getattr(ctx, "empreendimento", None))


def unidades_representadas(ctx) -> int:
    """Quantas UHs o contêiner desta execução representa; 0 quando não há contêiner.

    É o **único** dos três números do ADR-021 que uma regra dimensional pode
    consumir. Zero aqui significa "não há entrega a cujo respeito perguntar" —
    e não "nenhuma UH": quem decide o que fazer com a ausência é a regra, que
    aplica o piso de 1 em vez de anular o parâmetro normativo.
    """
    conteiner = conteiner_da_execucao(ctx)
    return conteiner.unidades_representadas if conteiner is not None else 0


def donos_do_conteiner(empreendimento, conteiner: ModeloBIM | None) -> dict:
    """Quem, no agregado, carrega um contêiner igual ao dado — por nível (ADR-023).

    ``{"unidades_tipo": [...], "edificacoes": [...], "terreno": Terreno | None}``.
    Todos os donos de cada nível, sem escolher: a precedência entre níveis é
    de quem lê (``tipologia_em_analise``), e pares no mesmo nível são
    legítimos.
    """
    unidades_tipo = [u for u in (getattr(empreendimento, "unidades_tipo", None) or [])
                     if mesmo_conteiner(u.modelo, conteiner)]
    edificacoes = [e for e in (getattr(empreendimento, "edificacoes", None) or [])
                   if mesmo_conteiner(e.modelo, conteiner)]
    terreno = getattr(empreendimento, "terreno", None)
    if terreno is None or not mesmo_conteiner(getattr(terreno, "modelo", None),
                                              conteiner):
        terreno = None
    return {"unidades_tipo": unidades_tipo, "edificacoes": edificacoes,
            "terreno": terreno}


def _tipologia_unica(tipologias: set[str]) -> str:
    """A tipologia comum dos pares de um nível, ou ``""`` se divergem."""
    return next(iter(tipologias)) if len(tipologias) == 1 else ""


def tipologia_em_analise(empreendimento, conteiner: ModeloBIM | None = None) -> str:
    """A tipologia de que esta análise fala, ou ``""``.

    Desde o ADR-021 a tipologia é da unidade tipo, e não mais declaração única
    do empreendimento — é o que torna o empreendimento misto exprimível. O
    ``""`` é ausência, não um valor: quem monta as condições da análise não deve
    gravá-lo, sob pena de o guard de aplicabilidade ler "tipologia declarada e
    diferente de casa" onde ninguém declarou nada.

    **Com** contêiner (ADR-023), lê dos donos dele, por precedência: as unidades
    tipo que o carregam, se todas derivam a mesma tipologia — e ``""`` se
    divergem; senão as edificações físicas que o carregam, pela tipologia que
    a raiz deriva da composição de cada uma (``""`` se alguma está vazia ou se
    divergem); senão o terreno, que não tem tipologia. Um contêiner que
    ninguém carrega não diz de que tipo fala, e aí vale a dedução. **Sem**
    contêiner (contextos montados à mão, as fixtures das regras, a CLI), a
    dedução de sempre: a unidade tipo em análise.
    """
    if conteiner is not None:
        donos = donos_do_conteiner(empreendimento, conteiner)
        if donos["unidades_tipo"]:
            return _tipologia_unica({u.tipologia for u in donos["unidades_tipo"]})
        if donos["edificacoes"]:
            return _tipologia_unica({empreendimento.tipologia_de(e)
                                     for e in donos["edificacoes"]})
        if donos["terreno"] is not None:
            return ""
    unidade_tipo = unidade_tipo_em_analise(empreendimento)
    return unidade_tipo.tipologia if unidade_tipo is not None else ""
