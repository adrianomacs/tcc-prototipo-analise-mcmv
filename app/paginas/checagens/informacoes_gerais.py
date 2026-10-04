"""Informações Gerais — 2.1.1 (ADR-004).

Centraliza os dados estruturantes do empreendimento — nome, UF/Município,
implantação e a composição — num só lugar. As três checagens (Enquadramento,
Georreferenciamento, Programa de necessidades) pararam de ter cada uma o
seu formulário de localização: agora só LEEM o `Empreendimento` gravado
aqui e mostram, no topo, o cabeçalho
(`app.componentes.cabecalho_empreendimento`) com um link de volta para esta
página.

Regras (ADR-004) implementadas nesta
página:

0. **A composição é declarada aqui (ADR-021, ADR-023).** Dois
   sub-formulários, na ordem em que a Portaria pergunta: **Unidades tipo**
   (nome, unidades, tipologia) — o grupo de UH que se repete, que é o que
   EDI-001/002/004 consomem — e **Edificações** (nome e composição por
   unidade tipo), retraído e opcional, porque um loteamento de 150 casas não
   precisa enumerar 150 prédios. `unidades_previstas` fecha o primeiro dos
   três números do ADR-021. O **contêiner** (o arquivo IFC) continua sendo
   anexado só quando enviado numa checagem: a linha "Contêiner" é resumo de
   leitura do que já foi anexado, nunca um campo de upload.
1. **O município vem do `Empreendimento`, e não do terreno confirmado.**
   Quem manda é o `Empreendimento`, e ele é editado
   só aqui. Trocar o município com um terreno já confirmado não bloqueia a
   troca (mesma política "avisa, não corrige" do resto do projeto) — avisa,
   e oferece **Redefinir terreno** (função :func:`_aviso_terreno_desatualizado`).
2. **Os avisos de proveniência migram para cá:** o de snapshot de
   municípios ausente (dentro de `seletor_municipio`) e o do recorte de
   equipamentos de educação (:func:`_aviso_do_recorte`, portado de
   `checagem_enquadramento.py` sem mudança de lógica).

A quem um modelo enviado se refere **não** entra aqui — é declaração sobre o
*arquivo*, afirmada na hora do envio, nas telas de Georreferenciamento e
Programa de necessidades (ADR-023). Natureza do modelo e nº de UHs
representadas, pela mesma razão, continuam locais àquelas telas.
"""

from __future__ import annotations

import dataclasses
import os

import streamlit as st

from app.componentes import avisos
from app.componentes import seletor_municipio as seletor_mod
from app.componentes.cabecalho_empreendimento import card_do_empreendimento
from app.estado import chaves
from app.servicos import declaracoes as dec
from app.servicos import empreendimento as emp_mod
from app.servicos import territorio
from app.servicos.empreendimento import Edificacao, Localizacao, UnidadeTipo

CHAVE = "geral"

ARRANJO_OPCOES = {
    "Condomínio": dec.CONDOMINIO,
    "Loteamento": dec.LOTEAMENTO,
}
TIPOLOGIA_OPCOES = {
    "Casa": dec.CASA,
    "Apartamento / casa sobreposta": dec.APARTAMENTO,
}


def _empreendimento_corrente():
    """O `Empreendimento` da sessão: da sessão, ou — na primeira carga —
    de `artefatos/empreendimento.json` (migrando `terreno.json`, se for o
    caso). Mesmo padrão de `_terreno_corrente()` em
    `checagem_enquadramento.py`."""
    guardado = st.session_state.get(chaves.EMPREENDIMENTO)
    if guardado is not None:
        return guardado
    carregado = emp_mod.carregar()
    st.session_state[chaves.EMPREENDIMENTO] = carregado
    return carregado


def main() -> None:
    # Topo igual ao das demais páginas da seção (ADR-034): o que a página
    # faz num expander sob o título, e o card logo abaixo.
    with st.expander("O que esta página faz", icon=":material/info:"):
        st.write("Aqui se declaram os dados que caracterizam o empreendimento: "
                 "nome, município, implantação, UHs previstas, unidades tipo "
                 "e edificações. Todas as checagens leem estes dados — "
                 "nenhuma pergunta de novo o município ou a composição —, e o "
                 "card abaixo mostra como a declaração ficou.")

    emp = _empreendimento_corrente()
    versao_lida = emp.versao
    # O card mostra o que o formulário abaixo acabou de aplicar (ADR-034 (d)):
    # o lugar é reservado agora, no topo, e preenchido depois de gravar.
    espaco_do_card = st.container()
    # Faixa de avisos logo sob o card (ADR-034 (c)): só o que nasce do
    # artefato lido, não do que o usuário preenche — esses ficam no campo.
    espaco_da_faixa = st.container()

    st.subheader("Identificação do empreendimento")
    nome = st.text_input("Nome do empreendimento", value=emp.nome,
                         placeholder="ex.: Estrela I", key=f"nome__{CHAVE}")

    localizacao_anterior = emp.localizacao
    pre = ({"uf": localizacao_anterior.uf, "ibge": localizacao_anterior.codigo_ibge}
          if localizacao_anterior else None)
    declaracoes_loc = seletor_mod.seletor_municipio(CHAVE, preselecao=pre)
    nova_localizacao = Localizacao.de_declaracoes(declaracoes_loc)

    _aviso_terreno_desatualizado(emp, nova_localizacao)
    # Logo abaixo do município, para o usuário ver a falta de recorte no
    # mesmo instante em que escolhe um município não coberto.
    _aviso_do_recorte(nova_localizacao)

    idx_arr = list(ARRANJO_OPCOES.values()).index(
        emp.declaracoes.get(dec.ARRANJO)) if emp.declaracoes.get(
            dec.ARRANJO) in ARRANJO_OPCOES.values() else 0
    rotulo_arr = st.selectbox("A implantação do empreendimento é em:",
                              list(ARRANJO_OPCOES), index=idx_arr,
                              key=f"arranjo__{CHAVE}")

    previstas = st.number_input(
        "Quantidade de UHs previstas para o empreendimento", min_value=0,
        value=emp.unidades_previstas, step=1, key=f"previstas__{CHAVE}",
        help="O total de UHs da proposta.")

    st.markdown("**Unidades tipo**")
    novas_unidades_tipo, mexeu_nos_tipos = _formulario_unidades_tipo(
        emp.unidades_tipo)
    if st.button("Adicionar unidade tipo", icon=":material/add_home:",
                 key=f"add_unidade_tipo__{CHAVE}"):
        novas_unidades_tipo.append(
            UnidadeTipo(nome=f"Unidade tipo {len(novas_unidades_tipo) + 1}"))
        mexeu_nos_tipos = True

    novas_edificacoes, mexeu_nas_edificacoes = _formulario_edificacoes(
        emp.edificacoes, novas_unidades_tipo)

    # -- aplica e grava -------------------------------------------------
    novas_declaracoes = dict(emp.declaracoes)
    novas_declaracoes[dec.ARRANJO] = ARRANJO_OPCOES[rotulo_arr]

    emp.renomear(nome)
    emp.localizar(nova_localizacao)
    emp.declarar(novas_declaracoes)
    emp.prever_unidades(previstas)
    _aplicar_composicao(emp, novas_unidades_tipo, novas_edificacoes)
    _limpar_tipologia_legada(emp)
    descartadas = emp_mod.descartar_declaracoes_fora_do_vocabulario(emp)
    if descartadas:
        with espaco_da_faixa:
            avisos.mostrar_aviso(_aviso_declaracoes_descartadas(descartadas))
    # Grava só quando algo mudou: todo mutador da raiz faz a `versao` andar
    # só com mudança de conteúdo (ADR-004), e gravar a cada reexecução do
    # script tornava cada render um efeito colateral no artefato.
    if emp.versao != versao_lida or not emp_mod.ja_gravado():
        emp_mod.gravar(emp)
    st.session_state[chaves.EMPREENDIMENTO] = emp
    with espaco_do_card:
        card_do_empreendimento(emp, com_link=False)

    # Acrescentar e remover mudam a LISTA de cartões, e os cartões foram
    # desenhados antes — sem redesenhar, o que o clique fez só apareceria na
    # próxima interação: o cartão novo não aparece, o removido continua na
    # tela, e clicar de novo cria um segundo. Vale só para os botões: editar um campo já redesenha
    # sozinho, e um `rerun` ali faria a tela piscar a cada tecla.
    if mexeu_nos_tipos or mexeu_nas_edificacoes:
        st.rerun()


def _aviso_declaracoes_descartadas(descartadas) -> avisos.Aviso:
    """Aviso da faixa: o artefato gravado trazia declarações fora do
    vocabulário, descartadas ao gravar (ADR-021). É ALERTA, e não orientação,
    porque o dado gravado mudou sem ação do usuário (ADR-034 (c))."""
    campos = ", ".join(f"`{k}`" for k in descartadas)
    return avisos.Aviso(
        avisos.ALERTA, "Dados antigos removidos do empreendimento.",
        f"A declaração gravada trazia campos que o protótipo não usa mais "
        f"({campos}); foram descartados e não afetam as checagens.")


def _formulario_unidades_tipo(unidades_tipo: list) -> tuple[list, bool]:
    """O sub-formulário das unidades tipo (ADR-021, ADR-023): nome, unidades,
    tipologia e um resumo de leitura do contêiner. Devolve a coleção
    atualizada — sem as removidas nesta execução — e se algum **botão** foi
    clicado, que é o que obriga `main()` a redesenhar a tela.

    O contêiner é só mostrado, nunca editado aqui: quem o anexa é a tela que
    recebe o upload (Georreferenciamento ou Programa de necessidades). Uma
    unidade tipo sem contêiner ainda não tem nada a exibir além do aviso — a
    linha existe desde já para o autor ver, ao voltar aqui, se o que enviou
    ficou de fato anexado.
    """
    restantes = []
    removeu = False
    for unidade_tipo in unidades_tipo:
        sufixo = unidade_tipo.id
        with st.container(border=True):
            col_nome, col_uh, col_tip, col_rem = st.columns([3, 1.4, 2.6, 1.2])
            with col_nome:
                nome = st.text_input("Nome", value=unidade_tipo.nome,
                                     key=f"tipo_nome__{sufixo}")
            with col_uh:
                unidades = st.number_input(
                    "Unidades", min_value=0, value=unidade_tipo.unidades,
                    step=1, key=f"tipo_unidades__{sufixo}",
                    help="Quantas UHs do empreendimento seguem esta unidade tipo.")
            with col_tip:
                tip_atual = unidade_tipo.tipologia
                idx_tip = (list(TIPOLOGIA_OPCOES.values()).index(tip_atual)
                          if tip_atual in TIPOLOGIA_OPCOES.values() else 0)
                rotulo_tip = st.selectbox(
                    "Tipologia", list(TIPOLOGIA_OPCOES), index=idx_tip,
                    key=f"tipo_tipologia__{sufixo}")
            with col_rem:
                st.write("")  # alinha o botão com os demais campos
                remover = st.button("Remover", icon=":material/delete:",
                                    key=f"tipo_remover__{sufixo}",
                                    use_container_width=True)
            st.caption(_resumo_conteiner(unidade_tipo))
        removeu = removeu or remover
        if not remover:
            restantes.append(dataclasses.replace(
                unidade_tipo, nome=nome, unidades=int(unidades),
                tipologia=TIPOLOGIA_OPCOES[rotulo_tip]))
    if not restantes:
        st.caption("Nenhuma unidade tipo declarada ainda.")
    return restantes, removeu


def _formulario_edificacoes(edificacoes: list,
                            unidades_tipo: list) -> tuple[list, bool]:
    """O sub-formulário das edificações físicas (ADR-023), opcional: nome,
    composição por unidade tipo e o resumo do contêiner. Devolve a coleção e
    se algum **botão** foi clicado, como `_formulario_unidades_tipo`.

    Opcional porque a edificação física é 0..n e o caso mais simples não a
    declara — ela existe para o prédio, a torre, o pavimento tipo MISTO: o
    arquivo que mistura unidades tipo e precisa de um dono que não minta sobre
    a quem pertence. A composição só oferece as unidades tipo que existem
    AGORA (as desta mesma execução do formulário, não as gravadas): remover um
    tipo tem de limpar as composições que o citavam na mesma passada, que é o
    cascade que a raiz faz.

    **Fica aberto quando há edificação declarada.** O Streamlit não guarda o
    estado do expander entre execuções, e cada campo editado é uma execução:
    com `expanded` fixo em `False`, o sub-formulário se fechava a cada tecla e
    o autor tinha de reabri-lo para continuar. Vazio, continua retraído — que é o caso que a decisão de
    interface queria discreto: o loteamento que não declara prédio nenhum.
    """
    with st.expander(f"Edificações (opcional) — {len(edificacoes)} declarada(s)",
                     icon=":material/apartment:", expanded=bool(edificacoes)):
        st.caption("Os prédios do empreendimento e quantas UHs de cada unidade "
                   "tipo cada um contém.")
        restantes = []
        mexeu = False
        for edificacao in edificacoes:
            sufixo = edificacao.id
            with st.container(border=True):
                col_nome, col_rem = st.columns([4.6, 1.2])
                with col_nome:
                    nome = st.text_input("Nome", value=edificacao.nome,
                                         key=f"edif_nome__{sufixo}")
                with col_rem:
                    st.write("")  # alinha o botão com o campo de nome
                    remover = st.button("Remover", icon=":material/delete:",
                                        key=f"edif_remover__{sufixo}",
                                        use_container_width=True)
                composicao = _composicao_da_edificacao(edificacao, unidades_tipo)
                st.caption(_resumo_conteiner(edificacao))
            mexeu = mexeu or remover
            if not remover:
                restantes.append(dataclasses.replace(
                    edificacao, nome=nome, composicao=composicao))
        if not restantes:
            st.caption("Nenhuma edificação declarada.")
        if st.button("Adicionar edificação", icon=":material/add_home_work:",
                     key=f"add_edificacao__{CHAVE}"):
            restantes.append(
                Edificacao(nome=f"Edificação {len(restantes) + 1}"))
            mexeu = True
    return restantes, mexeu


def _composicao_da_edificacao(edificacao, unidades_tipo: list) -> dict:
    """Quantas UH de cada unidade tipo esta edificação contém.

    Um campo por unidade tipo declarada; zero é ausência (a entidade descarta
    a entrada, ADR-023). Sem nenhuma unidade tipo não há o que compor — e é o
    aviso, não um formulário vazio, que diz por quê."""
    if not unidades_tipo:
        st.caption("Declare ao menos uma unidade tipo acima para compor esta "
                   "edificação.")
        return {}
    composicao = {}
    for inicio in range(0, len(unidades_tipo), 3):
        faixa = unidades_tipo[inicio:inicio + 3]
        for coluna, unidade_tipo in zip(st.columns(3), faixa):
            with coluna:
                quantidade = st.number_input(
                    f"UHs de {unidade_tipo.nome or '(sem nome)'}", min_value=0,
                    value=edificacao.composicao.get(unidade_tipo.id, 0), step=1,
                    key=f"edif_comp__{edificacao.id}__{unidade_tipo.id}")
            if quantidade:
                composicao[unidade_tipo.id] = int(quantidade)
    return composicao


def _aplicar_composicao(emp, unidades_tipo: list, edificacoes: list) -> bool:
    """Aplica as duas coleções, traduzindo o invariante da raiz em mensagem de
    tela. Devolve se passou.

    A raiz recusa (`ValueError`) uma composição que misture tipologias — um
    prédio casa + apartamento não existe na Portaria (ADR-023). Recusar é o
    comportamento certo; o que não pode é a tela morrer por isso.

    As **duas** chamadas precisam do guarda, e é isto que se viu em tela:
    trocar a tipologia de uma unidade tipo já composta
    torna mista a composição de quem a cita, e quem recusa aí é
    `definir_unidades_tipo` — não `definir_edificacoes`, que era o único
    protegido. A tela quebrava antes de chegar à mensagem.

    Quando a raiz recusa, nada é aplicado: a tela continua mostrando o valor
    que o autor escolheu, mas a entidade fica como estava — daí a mensagem
    dizer, com todas as letras, que a mudança não foi aplicada e o que fazer
    para aplicá-la."""
    try:
        emp.definir_unidades_tipo(unidades_tipo)
        emp.definir_edificacoes(edificacoes)
        return True
    except ValueError as erro:
        avisos.mostrar_aviso(avisos.Aviso(
            avisos.ERRO, "A mudança não foi aplicada.", str(erro),
            "Tire essa unidade tipo da composição da edificação (ou deixe as "
            "duas com a mesma tipologia) e tente de novo."))
        return False


def _resumo_conteiner(entidade) -> str:
    """O contêiner GRAVADO nesta entidade, se houver.

    Na ausência, a linha não promete que enviar um modelo numa checagem vai
    preenchê-la: o contêiner de uma análise é **efêmero** por decisão (a
    submissão é dita a cada análise, e o `empreendimento.json` não a guarda),
    e a versão anterior desta frase dizia "nenhum enviado ainda", o que fez o
    autor procurar na tela, depois de analisar, uma mudança que nunca vem.
    Quem chega aqui com contêiner
    gravado é o artefato migrado do esquema antigo, que trazia o modelo na
    raiz."""
    modelo = entidade.modelo
    if modelo is None or not modelo.caminho:
        return ("Contêiner: o arquivo IFC é informado a cada análise, na tela "
                "da checagem — não fica gravado aqui.")
    natureza = dec.ROTULO_VALOR.get(modelo.natureza, modelo.natureza or "—")
    return (f"Contêiner: `{os.path.basename(modelo.caminho)}` — {natureza}, "
           f"{modelo.unidades_representadas} UH(s) representada(s).")


def _limpar_tipologia_legada(emp) -> None:
    """A chave `dec.TIPOLOGIA` sobrevivente nas declarações de um artefato
    do esquema E0 (ADR-021/023) — enquanto ela existir, o artefato afirma em dois
    lugares um dado que agora tem um dono só (a unidade tipo), e a coleção
    inteira é editada pelo sub-formulário."""
    if dec.TIPOLOGIA in emp.declaracoes:
        restantes = dict(emp.declaracoes)
        restantes.pop(dec.TIPOLOGIA)
        emp.declarar(restantes)


def _aviso_terreno_desatualizado(emp, nova_localizacao) -> None:
    """Regra 1 do §4.3: trocar o município com terreno confirmado não é
    bloqueado — avisa, e oferece **Redefinir terreno**.

    Compara contra o município gravado em `terreno.procedencia
    ["municipio_declarado"]` (o mesmo campo que `checagem_enquadramento.
    _confirmar` grava) — NÃO contra `emp.localizacao` capturado no início
    desta execução: essa comparação ficaria obsoleta sozinha na primeira
    reexecução do script, porque o bloco de baixo desta função já aplica a
    localização nova ao empreendimento (a política é "avisa, não corrige",
    não "trava até decidir") — e o aviso desapareceria antes de o usuário
    conseguir clicar em "Redefinir terreno". O campo do terreno, gravado só
    na confirmação, não se move sozinho.
    """
    terreno = emp.terreno
    if terreno is None or nova_localizacao is None:
        return
    do_terreno = dict((terreno.procedencia or {}).get("municipio_declarado") or {})
    codigo_terreno = str(do_terreno.get("ibge") or "")
    if not codigo_terreno or codigo_terreno == nova_localizacao.codigo_ibge:
        return

    avisos.mostrar_aviso(avisos.Aviso(
        avisos.ALERTA,
        f"O terreno do Enquadramento foi confirmado em "
        f"{do_terreno.get('nome', '?')}/{do_terreno.get('uf', '?')}, e o "
        f"município agora é {nova_localizacao.municipio}/{nova_localizacao.uf}.",
        "O Enquadramento mediria as distâncias aos equipamentos do município "
        "novo a partir de um terreno do município anterior.",
        "Redefina o terreno ou, se a troca foi engano, volte ao município "
        "anterior."))
    if st.button("Redefinir terreno", key=f"redefinir_terreno__{CHAVE}"):
        emp.definir_terreno(None)
        emp_mod.gravar(emp)
        st.session_state[chaves.EMPREENDIMENTO] = emp
        for k in (chaves.chave_relatorio("enquadramento"),
                  chaves.chave_mostrar_resultados("enquadramento")):
            st.session_state.pop(k, None)
        st.rerun()


def _aviso_do_recorte(localizacao) -> None:
    """Aviso do recorte de equipamentos — portado de
    `checagem_enquadramento._aviso_do_recorte` sem mudança de lógica (só de
    lugar: regra 2 do §4.3, "migram para cá")."""
    codigo = localizacao.codigo_ibge if localizacao else ""
    if not codigo:
        return
    if territorio.carregar_recorte(codigo) is not None:
        proc = territorio.procedencia_do_recorte(codigo)
        safra = proc.get("ano_censo")
        st.caption("Recorte de equipamentos disponível para este município"
                   + (f" — Censo Escolar {safra}." if safra else "."))
        return
    avisos.mostrar_aviso(avisos.Aviso(
        avisos.ALERTA,
        "Não há recorte de equipamentos de educação para este município.",
        "As verificações de distância do Enquadramento sairão como não "
        "avaliáveis."))


main()
