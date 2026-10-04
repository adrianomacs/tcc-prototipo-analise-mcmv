"""Checagem — Programa de necessidades (BIM only) — seleção por GRUPO.

Anatomia do ADR-034: explicação do grupo, card do empreendimento
(implantação e tipologia vêm de Informações Gerais, 2.1.1), faixa de avisos
(o que falta declarar lá) e as duas seções:
  1) **Informações de entrada** — de quem são as UHs deste arquivo, quantas
     ele representa e o upload do IFC; o aviso de arquivo misto fica junto da
     escolha, porque nasce dela;
  2) **Cobertura e análise** — métricas, a linha "Ao analisar…" com o botão e
     o resultado, com o relatório consolidado do grupo.

Os blocos compartilhados com as demais checagens (conversão 3D em segundo
plano, ação, resultados provisórios) vivem em ``app.componentes.acao`` e
``app.servicos``.

O EMP-001 (georreferenciamento) pertence à checagem própria
(paginas/checagens/checagem_georreferenciamento.py).

O nº de UHs do arquivo NORMALIZA a análise por UH (ambientes/UH, área/UH) —
ex.: casa geminada com 2 UHs duplica ambientes e áreas. Desde o ADR-021 ele
não é mais declaração: é `ModeloBIM.unidades_representadas`, propriedade da
entrega, e por isso sai desta tela como número, não como chave de
`declaracoes` — e continua sendo perguntado aqui: é o arquivo que chega
agora, e ninguém mais sabe quantas UHs ele representa.

De quem são as UHs deste arquivo (ADR-023)
-------------------------------------------

Como 2.1.1 declara a composição antes de qualquer upload, a pergunta desta
tela é dizer de QUEM são as UHs: de uma unidade tipo
(o caso normal, "um IFC = uma unidade tipo") ou de uma edificação física
(o pavimento tipo MISTO, que mistura tipos e por isso não pertence a nenhum
deles). A natureza é fixa em `edificacao_isolada`: o arquivo desta checagem
contém UH, não terreno. Só entram no seletor unidades tipo e edificações
**com composição** — uma edificação vazia não tem tipologia nem UH de que
falar (ADR-023).

Execução: via ponto de entrada ``streamlit run app/main.py``.
"""

from __future__ import annotations

import streamlit as st

from app.componentes import acao as acao_mod
from app.componentes import avisos
from app.componentes import explicacao_grupo as explicacao_mod
from app.componentes.cabecalho_empreendimento import cabecalho_empreendimento
from app.estado import chaves
from app.navegacao import arvore
from app.servicos import analise, grupos
from app.servicos import declaracoes as dec
from app.servicos import empreendimento as emp_mod

CHAVE = "programa"
GRUPO_ID = "programa_necessidades"
ORIGEM = arvore.PAGINA_CHECAGEM_PROGRAMA



def _empreendimento_corrente():
    guardado = st.session_state.get(chaves.EMPREENDIMENTO)
    if guardado is not None:
        return guardado
    carregado = emp_mod.carregar()
    st.session_state[chaves.EMPREENDIMENTO] = carregado
    return carregado


def main() -> None:
    grupo = grupos.carregar_grupo(GRUPO_ID)
    if grupo is None:
        st.error("Grupo 'programa_necessidades' não encontrado em "
                 "config/grupos_requisitos.yaml.")
        return

    explicacao_mod.explicacao_grupo(grupo, em_expander=True, mostrar_situacao=False)

    emp = _empreendimento_corrente()
    cabecalho_empreendimento(emp)
    # A faixa (ADR-034 (c)) depende do ALVO, que o formulário abaixo resolve —
    # e tem de aparecer ANTES dele. O contêiner reserva o lugar agora e é
    # preenchido depois.
    espaco_da_faixa = st.container()

    st.subheader("Informações de entrada")
    declaracoes_locais, unidades_representadas, alvo = _formulario_inputs(emp)
    _aviso_heterogeneidade(emp, alvo)
    arquivo_ifc = st.file_uploader("Modelo IFC", type=["ifc"])

    with espaco_da_faixa:
        avisos.faixa_de_avisos([_aviso_sem_unidade_tipo(emp),
                                _aviso_implantacao_tipologia_ausente(emp, alvo)])

    st.divider()
    st.subheader("Cobertura e análise")
    executaveis = grupos.ids_executaveis(
        grupo, analise.declaracoes_da_analise(emp, declaracoes_locais))
    explicacao_mod.cobertura(grupo, executaveis)
    acao_mod.acao(CHAVE, arquivo_ifc, grupo, declaracoes_locais, ORIGEM, emp,
                 unidades_representadas=unidades_representadas,
                 alvo=alvo,
                 resumo_execucao=explicacao_mod.resumo_da_execucao(
                     grupo, executaveis))


def _aviso_sem_unidade_tipo(emp) -> avisos.Aviso | None:
    """Pré-condição da faixa: sem unidade tipo declarada não há a quem anexar
    o arquivo (a análise sintetiza uma efêmera, mas o autor precisa saber)."""
    if _opcoes(emp):
        return None
    return avisos.Aviso(
        avisos.ALERTA, "Nenhuma unidade tipo declarada.",
        "O arquivo será analisado sem saber a que unidade tipo pertence.",
        "Declare ao menos uma em Informações Gerais antes de enviar o modelo.")


def _aviso_implantacao_tipologia_ausente(emp, alvo: str) -> avisos.Aviso | None:
    """Implantação e tipologia não são perguntadas nesta tela — quem as declara
    é "Informações Gerais" (2.1.1). Sem elas, as regras que as consultam
    simplesmente saem NÃO AVALIÁVEL por condição de contorno ausente (mesmo
    princípio de `informacoes_gerais._aviso_do_recorte`: avisa, não bloqueia
    nem inventa um valor padrão).

    A tipologia é a **do alvo escolhido** (ADR-023), não uma dedução sobre o
    empreendimento inteiro: com duas unidades tipo declaradas, cada uma com a
    sua tipologia, a dedução devolve `""` — e o aviso acusava falta de
    declaração onde havia duas."""
    faltando = [rotulo for rotulo, declarado in
               (("implantação", dec.ARRANJO in emp.declaracoes),
                ("tipologia", bool(analise.tipologia_do_alvo(emp, alvo))))
               if not declarado]
    if not faltando:
        return None
    return avisos.Aviso(
        avisos.ALERTA,
        f"{' e '.join(faltando).capitalize()} ainda não "
        f"{'declaradas' if len(faltando) > 1 else 'declarada'}.",
        "As verificações que dependem disso sairão como não avaliáveis.",
        "Declare em Informações Gerais.")


def _aviso_heterogeneidade(emp, alvo: str) -> None:
    """O arquivo misto avisa ANTES de analisar (exigência da validação da R2).

    Fica logo abaixo da escolha e acima do envio, porque é sobre a escolha que
    ele fala: o autor acabou de apontar uma edificação que reúne mais de uma
    unidade tipo, e o veredito que sair dali será agregado sobre todas elas.
    Avisar só depois, em `meta`, chegaria tarde — o usuário já teria lido o
    relatório como se falasse de uma planta só.

    Marca, não bloqueia (D-K): o arquivo misto é aceito de propósito, porque é
    o que as submissões de hoje permitem entregar. A frase vem de
    `analise.heterogeneidade_do_alvo`, a mesma que o relatório carrega.
    """
    aviso = analise.heterogeneidade_do_alvo(emp, alvo)
    if aviso:
        st.warning(aviso, icon=":material/layers:")


def _opcoes(emp) -> dict[str, str]:
    """Rótulo -> alvo (ADR-023): as unidades tipo e as edificações COM
    composição declaradas em 2.1.1.

    Uma edificação sem composição fica de fora: dela a raiz não deriva
    tipologia nem número de UH, e oferecê-la seria oferecer um dono do qual
    esta checagem não tem o que dizer."""
    opcoes: dict[str, str] = {}
    for unidade_tipo in emp.unidades_tipo:
        nome = unidade_tipo.nome or "(sem nome)"
        opcoes[f"{nome} (unidade tipo)"] = analise.alvo_de_unidade_tipo(
            unidade_tipo.id)
    for edificacao in emp.edificacoes:
        if not edificacao.composicao:
            continue
        nome = edificacao.nome or "(sem nome)"
        opcoes[f"{nome} (edificação — arquivo misto)"] = (
            analise.alvo_de_edificacao(edificacao.id))
    return opcoes


def _seletor_alvo(emp) -> str:
    """A quem o arquivo pertence — sem pergunta quando não há escolha a fazer.

    Zero alvos: avisa e não oferece seletor nenhum (o arquivo ainda pode ser
    analisado, e a análise sintetiza uma unidade tipo efêmera para ele, mas o
    autor precisa saber que nada disso foi declarado). Um só: é ele, dito em
    voz alta. Vários: escolha por nome."""
    opcoes = _opcoes(emp)
    if not opcoes:
        # O aviso mora na faixa (`_aviso_sem_unidade_tipo`).
        return analise.ALVO_DEDUZIDO
    if len(opcoes) == 1:
        (rotulo, alvo), = opcoes.items()
        st.caption(f"Este modelo será anexado a **{rotulo}**.")
        return alvo
    rotulo = st.selectbox("As UHs deste arquivo são de:", list(opcoes),
                          key=f"alvo__{CHAVE}")
    return opcoes[rotulo]


def _formulario_inputs(emp) -> tuple[dict, int, str]:
    """O que esta tela afirma sobre o arquivo enviado: de quem são as UHs
    (condição de contorno desta análise) e quantas UHs ele representa, que não
    é declaração (ADR-021) — daí os dois seguirem separados."""
    col_esq, col_dir = st.columns(2)
    with col_esq:
        alvo = _seletor_alvo(emp)
    with col_dir:
        unidades_representadas = st.number_input(
            "Quantas UHs o modelo enviado representa?", min_value=1, value=1,
            step=1,
            help="Propriedade do arquivo, não do empreendimento: é a "
                 "geometria entregue que representa 1, 2, 4 UHs. Normaliza a "
                 "análise por UH (ambientes/UH, área/UH) — uma casa geminada "
                 "de 2 UHs tem cozinhas e áreas duplicadas no modelo.")

    st.caption("A tipologia da unidade tipo escolhida define quais "
               "verificações se aplicam; o número de UHs do arquivo divide "
               "ambientes e áreas por UH.")

    return ({dec.TIPO_MODELO: dec.EDIFICACAO_ISOLADA},
            int(unidades_representadas), alvo)


main()
