"""O que esta análise não consegue dizer — e que veredito nenhum diria por ela.

Os vereditos respondem "conforme?"; nenhum deles responde "sobre quanto do
empreendimento, e a partir de quanta geometria?". Essas perguntas são do
**recorte da submissão**, não do projeto, e por isso não cabem na taxonomia do
ADR-006: não falta insumo nem pré-requisito, e a medição que foi feita é
válida. O ADR-023 (D-K) decide que elas viajam como **diagnóstico**: marcam,
nunca reprovam, e cada uma tem rótulo próprio, distinto dos motivos de
``NAO_AVALIAVEL``.

Por análise, nunca por empreendimento
-------------------------------------

O contêiner é efêmero: nada aqui supõe contêiner
persistido. Os cinco diagnósticos são calculados sobre o **agregado como a
análise o viu** (o instantâneo) e sobre o **contêiner desta execução** — os
dois que ``pipeline.analisar`` já tem na mão quando monta o ``meta``.

Por que só nas análises que leem UH
-----------------------------------

A D-K restringe os diagnósticos às análises que consomem
``unidades_representadas`` — na prática, o Programa de necessidades. No
Georreferenciamento o EMP-001 não lê UH nenhuma: dizer ali que "o veredito fala
por 1 UH de 150 previstas" seria descrever uma extrapolação que não aconteceu,
porque a pergunta do EMP-001 é sobre a âncora do modelo, não sobre a UH. Quem
responde "esta análise lê UH?" é ``consome_unidades_representadas``, pela lista
de regras que chamam ``ancora.unidades_representadas`` — lista que
``tests/arquitetura/test_regras_que_consomem_uh.py`` confere contra o código
das regras, para não envelhecer em silêncio.

Todos marcam; nenhum reprova
----------------------------

Os cinco são sempre calculados e sempre aparecem, com ``marcado`` dizendo se
dispararam: um diagnóstico que só aparece quando dispara não tem como ser
conferido à mão quando não dispara. Os valores viajam junto, porque é deles que
a tela monta a frase — e é por eles que a conferência se faz.

Anel: aplicação. Nenhum I/O — só aritmética sobre o agregado e o contêiner.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.dominio import ancora

# --- Rótulos próprios (D-K) -------------------------------------------------
#
# Distintos dos motivos do ADR-006/022 de propósito: nenhum destes produz
# ``NAO_AVALIAVEL``, e reaproveitar a constante da taxonomia faria um
# diagnóstico parecer causa de não avaliação. O da inconsistência declaratória
# chama-se "números declarados não fecham" (D-L) justamente para não ser
# confundido com o motivo homônimo do ADR-022, que entrou no vocabulário com o
# primeiro emissor, EMP-025.1 (ADR-028).
EXTRAPOLACAO = "extrapolacao"
COBERTURA_DA_ANALISE = "cobertura_da_analise"
NUMEROS_NAO_FECHAM = "numeros_declarados_nao_fecham"
HETEROGENEIDADE = "heterogeneidade"
TIPOLOGIA_INDETERMINADA = "tipologia_indeterminada"

ROTULO = {
    EXTRAPOLACAO: "Resultado estendido a mais UHs do que o modelo contém",
    COBERTURA_DA_ANALISE: "Parte do empreendimento analisada",
    NUMEROS_NAO_FECHAM: "Números declarados não fecham",
    HETEROGENEIDADE: "Resultado reúne mais de uma unidade tipo",
    TIPOLOGIA_INDETERMINADA: "Casa ou apartamento não declarado",
}

# As regras que leem ``ancora.unidades_representadas``. Conferida contra o
# código em ``tests/arquitetura/test_regras_que_consomem_uh.py``: o critério é
# o MÓDULO da regra chamar a âncora, e não cada classe chamá-la — é o módulo
# que declara a dependência, e o teste mede exatamente isso.
REGRAS_QUE_CONSOMEM_UH = ("EDI-001", "EDI-002", "EDI-004", "EDI-004.1")


@dataclass(frozen=True)
class Diagnostico:
    """Uma frase que o relatório carrega sem que nenhum veredito mude.

    ``marcado`` diz se disparou; ``valores`` traz os números de que a frase foi
    feita, para que a tela não os recalcule e a conferência à mão seja possível.
    """

    chave: str
    marcado: bool
    mensagem: str = ""
    valores: dict = field(default_factory=dict)

    @property
    def rotulo(self) -> str:
        return ROTULO.get(self.chave, self.chave)

    def to_dict(self) -> dict:
        return {"chave": self.chave, "rotulo": self.rotulo,
                "marcado": self.marcado, "mensagem": self.mensagem,
                "valores": self.valores}


def consome_unidades_representadas(ids_executados) -> bool:
    """Esta análise lê UH? (D-K)

    ``True`` se alguma das regras executadas consome a âncora. Sem lista de ids
    — um chamador que não a tenha — a resposta é ``False``: o silêncio não
    autoriza diagnosticar, porque o diagnóstico afirma algo sobre o
    denominador de um veredito que talvez não exista.
    """
    return any(id_regra in REGRAS_QUE_CONSOMEM_UH
               for id_regra in (ids_executados or ()))


def _donos(empreendimento, conteiner):
    """Os donos do contêiner no nível que vence a precedência (ADR-023).

    Devolve ``(nivel, lista)`` com ``nivel`` em ``"unidades_tipo"``,
    ``"edificacoes"``, ``"terreno"`` ou ``""``. A precedência é a mesma de
    ``ancora.tipologia_em_analise``, e não uma segunda leitura: dois lugares
    respondendo "de quem é este arquivo?" com critérios diferentes seria o
    defeito que a âncora existe para evitar.
    """
    if conteiner is None:
        return "", []
    donos = ancora.donos_do_conteiner(empreendimento, conteiner)
    if donos["unidades_tipo"]:
        return "unidades_tipo", donos["unidades_tipo"]
    if donos["edificacoes"]:
        return "edificacoes", donos["edificacoes"]
    if donos["terreno"] is not None:
        return "terreno", [donos["terreno"]]
    return "", []


def unidades_do_dono(empreendimento, conteiner) -> int:
    """Por quantas UH o veredito desta análise fala.

    Do tipo, ``unidades``; da edificação física, a soma da composição (D-K). Com
    pares no mesmo nível — as quatro torres iguais do ADR-023 — os donos somam,
    e é o que mantém as duas formas equivalentes: quatro tipos de 16 UH sobre o
    mesmo contêiner falam pelas mesmas 64 UH que um tipo de 64.
    """
    nivel, donos = _donos(empreendimento, conteiner)
    if nivel == "unidades_tipo":
        return sum(u.unidades for u in donos)
    if nivel == "edificacoes":
        return sum(sum(e.composicao.values()) for e in donos)
    return 0


def _extrapolacao(empreendimento, conteiner) -> Diagnostico:
    """O veredito fala por mais UH do que a geometria lida representa.

    É a extrapolação que o ADR-021 tornou visível ao separar os três números:
    ``unidades_representadas`` é o que foi entregue; ``unidades`` do dono é por
    quantas o veredito fala. Legítima — um tipo de 150 UH com um IFC de 1 UH é
    a submissão normal —, e por isso marca sem reprovar.
    """
    do_dono = unidades_do_dono(empreendimento, conteiner)
    representadas = (conteiner.unidades_representadas
                     if conteiner is not None else 0)
    marcado = bool(do_dono and representadas and do_dono > representadas)
    return Diagnostico(
        EXTRAPOLACAO, marcado,
        (f"O resultado vale para {do_dono} UHs, a partir de um modelo que foi "
         f"declarado com {representadas} UHs." if marcado else ""),
        {"unidades_do_dono": do_dono, "unidades_representadas": representadas})


def _cobertura(empreendimento, conteiner) -> Diagnostico:
    """Que fatia do empreendimento previsto esta análise cobre.

    ``unidades`` do dono ÷ ``unidades_previstas`` (D-K). Sem previsão declarada
    não há denominador, e a cobertura é ``None`` — ausência de declaração não é
    cobertura zero. A cobertura do **parque**, somando as várias análises, é
    conta das telas 2.4.x, que leem todos os relatórios; aqui é só a desta.
    """
    do_dono = unidades_do_dono(empreendimento, conteiner)
    previstas = empreendimento.unidades_previstas
    fracao = (do_dono / previstas) if previstas else None
    marcado = bool(fracao is not None and fracao < 1)
    return Diagnostico(
        COBERTURA_DA_ANALISE, marcado,
        (f"Esta análise cobre {do_dono} das {previstas} UHs previstas."
         if marcado else ""),
        {"unidades_do_dono": do_dono, "unidades_previstas": previstas,
         "cobertura": fracao})


def _numeros_nao_fecham(empreendimento) -> Diagnostico:
    """As duas aritméticas declaratórias do ADR-022, sobre o agregado.

    Soma das unidades tipo × ``unidades_previstas``, e soma da composição das
    edificações × ``unidades`` de cada tipo. Rótulo próprio, em ``meta``, e
    **não** o motivo do ADR-022 (D-L): nas análises que leem UH a
    inconsistência não altera insumo — o denominador é
    ``unidades_representadas`` —, e derrubar EDI-004 a ``NAO_AVALIAVEL`` por
    ela jogaria fora uma medição válida. Quem consome os totais declarados é
    EMP-025.1 (ADR-028), e é ela que emite o motivo.
    """
    excedente = empreendimento.excedente_declarado
    compostos = {u.id: empreendimento.excedente_composto(u)
                 for u in empreendimento.unidades_tipo
                 if empreendimento.excedente_composto(u)}
    marcado = bool(excedente or compostos)
    partes = []
    if excedente:
        partes.append(
            f"as unidades tipo somam {empreendimento.unidades_declaradas} UH, "
            f"{excedente} a mais que as {empreendimento.unidades_previstas} "
            "previstas")
    if compostos:
        partes.append(
            "a composição das edificações passa das unidades declaradas em "
            + ", ".join(sorted(
                (empreendimento.unidade_tipo_por_id(i).nome or i)
                for i in compostos)))
    return Diagnostico(
        NUMEROS_NAO_FECHAM, marcado,
        ("Números declarados não fecham: " + "; ".join(partes) + "."
         if marcado else ""),
        {"excedente_declarado": excedente,
         "excedente_composto": compostos,
         "unidades_declaradas": empreendimento.unidades_declaradas,
         "unidades_previstas": empreendimento.unidades_previstas})


def _heterogeneidade(empreendimento, conteiner) -> Diagnostico:
    """O veredito é agregado sobre mais de uma unidade tipo.

    Duas formas (D-K): o dono é uma ``Edificacao`` com dois ou mais tipos na
    composição — o pavimento tipo misto do caso 3 —, ou ninguém é dono e o
    empreendimento declara dois ou mais tipos ("Terreno com as edificações" sem
    física declarada). Nas duas, UH de plantas diferentes podem compensar-se
    dentro do mesmo veredito e mascarar uma não conforme (limitação declarada
    do ADR-021). É a limitação ficando visível, não um defeito do projeto: um
    IFC por unidade tipo (o EIR) elimina o aviso.
    """
    nivel, donos = _donos(empreendimento, conteiner)
    tipos: set[str] = set()
    if nivel == "edificacoes":
        for edificacao in donos:
            if len(edificacao.composicao) > 1:
                tipos |= set(edificacao.composicao)
    elif nivel == "" and conteiner is not None:
        if len(empreendimento.unidades_tipo) > 1:
            tipos = {u.id for u in empreendimento.unidades_tipo}
    marcado = len(tipos) > 1
    return Diagnostico(
        HETEROGENEIDADE, marcado,
        mensagem_heterogeneidade(len(tipos)) if marcado else "",
        {"unidades_tipo_no_escopo": sorted(tipos)})


def mensagem_heterogeneidade(quantidade_de_tipos: int) -> str:
    """A frase da heterogeneidade, dita em dois lugares (exigência da R2).

    O diagnóstico tem **dois momentos**: o aviso preventivo, quando o usuário
    escolhe uma edificação como alvo e ainda não analisou nada, e o registro em ``meta``, depois de
    analisar. São o mesmo fato, e por isso a mesma frase sai daqui — duas
    redações divergindo sobre a mesma limitação seria a tela contradizendo o
    relatório que ela própria gerou.
    """
    return (f"O resultado reúne {quantidade_de_tipos} unidades tipo e pode "
            "esconder uma UH não conforme dentro do conjunto. Indica-se checar "
            "um modelo IFC por unidade tipo.")


def _tipologia_indeterminada(empreendimento, conteiner) -> Diagnostico:
    """Há dono, e dele não sai tipologia.

    O caso nomeado é a edificação física declarada **sem composição** que
    recebe arquivo: a raiz não tem de onde derivar a tipologia e devolve ``""``.
    ``""`` é ausência, e o guard não bloqueia — EDI-001 e EDI-002 rodam ambas,
    como quando ninguém declara. O que esta linha faz é dizer que rodaram assim.
    """
    nivel, _ = _donos(empreendimento, conteiner)
    tipologia = ancora.tipologia_em_analise(empreendimento, conteiner)
    marcado = bool(nivel in ("unidades_tipo", "edificacoes") and not tipologia)
    return Diagnostico(
        TIPOLOGIA_INDETERMINADA, marcado,
        ("O modelo não está ligado a uma unidade tipo com tipologia (casa ou "
         "apartamento): as verificações que dependem disso rodaram sem esse "
         "filtro." if marcado else ""),
        {"nivel_do_dono": nivel, "tipologia": tipologia})


def avaliar(empreendimento, conteiner=None) -> list[Diagnostico]:
    """Os cinco, na ordem em que o relatório os mostra."""
    return [_extrapolacao(empreendimento, conteiner),
            _cobertura(empreendimento, conteiner),
            _numeros_nao_fecham(empreendimento),
            _heterogeneidade(empreendimento, conteiner),
            _tipologia_indeterminada(empreendimento, conteiner)]


def para_meta(empreendimento, conteiner, ids_executados) -> list[dict]:
    """``meta.diagnosticos`` do relatório, ou ``[]`` se a análise não lê UH.

    Lista vazia e chave ausente são a mesma coisa para quem lê; ``pipeline``
    só acrescenta a chave quando há o que pôr nela, para que o relatório de
    uma análise que não diagnostica continue sendo o que sempre foi.
    """
    if not consome_unidades_representadas(ids_executados):
        return []
    return [d.to_dict() for d in avaliar(empreendimento, conteiner)]
