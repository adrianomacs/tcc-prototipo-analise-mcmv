"""Bloco de ação das telas de checagem: botão 'Analisar' (rótulo único em
todas as páginas, ADR-034) que se transforma em 'Nova análise' + resultado final.

Extraído de `_checagem_comum.py`. Recebe o `Empreendimento` da tela e o
repassa a `app.servicos.analise` — é o que dá ao relatório gravado uma
referência estável ao empreendimento (ADR-004). ``origem_pagina`` é um nó
de `app.navegacao.arvore.Pagina` (ADR-010), não mais uma string de caminho
solta.
"""

from __future__ import annotations

from contextlib import nullcontext

import streamlit as st

from app.componentes import avisos
from app.componentes.resultado import resultado_final
from app.estado import chaves
from app.servicos import analise, conversao_3d, grupos, provedores, uploads
from app.servicos.grupos import Grupo


def acao(chave: str, arquivo_ifc, grupo: Grupo, declaracoes: dict,
         origem_pagina, empreendimento,
         unidades_representadas: int = 0,
         alvo: str = analise.ALVO_DEDUZIDO, resumo_execucao: str = "") -> None:
    """Botão único 'Analisar': processa e libera os resultados na sequência.

    A análise (pipeline + eventual download da malha municipal) roda dentro do
    clique, sob o spinner; ao concluir, os resultados aparecem imediatamente —
    apenas a conversão 3D segue em segundo plano (os botões 'Verificar
    relatório' das regras com visualização refletem esse estado).

    ``unidades_representadas`` é quantas UHs o arquivo enviado representa
    (ADR-021). Vem da tela porque é afirmação sobre o arquivo, e viaja até o
    `ModeloBIM` que `app.servicos.analise` monta — deixou de ser declaração
    quando deixou de ser condição de contorno.

    ``alvo`` (ADR-023) é a quem este arquivo pertence — a unidade tipo ou a
    edificação física escolhida por nome na tela, entre as declaradas em
    2.1.1; repassado a `app.servicos.analise.analisar_modelo` sem ser
    interpretado aqui.

    ``resumo_execucao`` é a linha "Ao analisar, o protótipo verifica: …" ao
    lado do botão (ADR-034, seção 2), como em :func:`acao_sem_ifc`; vazio,
    o bloco fica como era (botão em largura total)."""
    relatorio = st.session_state.get(chaves.chave_relatorio(chave))
    col_botao = nullcontext()
    if resumo_execucao:
        col_texto, col_botao = st.columns([3, 1], vertical_alignment="center")
        col_texto.markdown(resumo_execucao)
    if relatorio is None:
        with col_botao:
            clicou = st.button("Analisar", type="primary",
                               use_container_width=True, key=f"analisar_{chave}")
        # Fora da coluna: erros e spinner da análise ocupam a largura toda.
        if clicou:
            _analisar(chave, arquivo_ifc, grupo, declaracoes, empreendimento,
                      unidades_representadas, alvo)
        return

    if resumo_execucao:
        with col_botao:
            nova = st.button("Nova análise", use_container_width=True,
                             key=f"nova_{chave}")
        st.caption("Resultado referente ao modelo e às declarações do momento "
                   "da análise.")
    else:
        col_info, col_nova = st.columns([3, 1], vertical_alignment="center")
        with col_info:
            st.caption("A análise refere-se ao modelo e às declarações do "
                       "momento do processamento. Para reprocessar com novos "
                       "dados, use **Nova análise**.")
        with col_nova:
            nova = st.button("Nova análise", use_container_width=True,
                             key=f"nova_{chave}")
    if nova:
        for k in (chaves.chave_relatorio(chave),
                  chaves.chave_mostrar_resultados(chave),
                  chaves.chave_caminho_ifc(chave), chaves.REQ_SELECIONADO,
                  chaves.ORIGEM_RELATORIO, chaves.CHAVE_SELECIONADA, "viz",
                  chaves.chave_viz_future(chave), chaves.chave_viz_job_id(chave)):
            st.session_state.pop(k, None)
        st.rerun()

    st.divider()
    resultado_final(chave, relatorio, origem_pagina, empreendimento)


def acao_sem_ifc(chave: str, grupo: Grupo, declaracoes: dict,
                 origem_pagina, empreendimento, *, com_rede: bool = True,
                 rotulo_botao: str = "Analisar",
                 espera: str = "Avaliando o enquadramento do terreno…",
                 referencia: str = "ao terreno",
                 avisar_rede: bool = True,
                 resumo_execucao: str = "") -> None:
    """Botão 'Analisar' para grupos que NÃO dependem de modelo IFC.

    O Enquadramento é o primeiro: o insumo dele é o terreno, que pode ter vindo
    do mapa, de coordenadas digitadas ou de um IFC já consumido na etapa
    anterior. Exigir um IFC aqui inutilizaria três dos quatro modos de entrada —
    a mesma razão pela qual as regras ENQ não dependem do EMP-001.

    A Qualificação urbanística é o segundo, e sem rede: ``com_rede=False`` não
    constrói provedor de rede nem avisa sobre a métrica, porque nenhuma regra
    dela mede distância. Os padrões mantêm o Enquadramento como era.

    ``avisar_rede=False`` é para a página que já pôs o aviso de rede na faixa
    do topo (ADR-034): o aviso é de pré-condição e não se repete aqui.

    ``resumo_execucao`` (ADR-034, seção "Cobertura e análise") põe numa linha só
    o que será executado e o botão — Analisar antes, Nova análise depois —,
    com a nota curta abaixo, em vez de empilhar texto, divisória e botão.
    """
    relatorio = st.session_state.get(chaves.chave_relatorio(chave))
    col_botao = nullcontext()
    if resumo_execucao:
        col_texto, col_botao = st.columns([3, 1], vertical_alignment="center")
        col_texto.markdown(resumo_execucao)
    if relatorio is None:
        ids = grupos.ids_executaveis(grupo, declaracoes)
        if com_rede and avisar_rede:
            avisos.aviso_de_metrica()
        with col_botao:
            clicou = st.button(rotulo_botao, type="primary",
                               use_container_width=True, key=f"analisar_{chave}")
        if clicou:
            with st.spinner(espera):
                st.session_state[chaves.chave_relatorio(chave)] = (
                    analise.analisar_enquadramento(
                        chave, empreendimento, ids,
                        provedores.roteador_de_rede())
                    if com_rede else
                    analise.analisar_sem_modelo(chave, empreendimento, ids))
            st.rerun()
        return

    if resumo_execucao:
        with col_botao:
            nova = st.button("Nova análise", use_container_width=True,
                             key=f"nova_{chave}")
        st.caption(f"Resultado referente {referencia} e às declarações do "
                   "momento da análise.")
    else:
        col_info, col_nova = st.columns([3, 1], vertical_alignment="center")
        with col_info:
            st.caption(f"A análise refere-se {referencia} e às declarações do "
                       "momento do processamento. Para reprocessar, use "
                       "**Nova análise**.")
        with col_nova:
            nova = st.button("Nova análise", use_container_width=True,
                             key=f"nova_{chave}")
    if nova:
        for k in (chaves.chave_relatorio(chave), chaves.REQ_SELECIONADO,
                  chaves.ORIGEM_RELATORIO, chaves.CHAVE_SELECIONADA):
            st.session_state.pop(k, None)
        st.rerun()

    st.divider()
    resultado_final(chave, relatorio, origem_pagina, empreendimento)


def _analisar(chave: str, arquivo_ifc, grupo: Grupo,
              declaracoes: dict, empreendimento,
              unidades_representadas: int = 0,
              alvo: str = analise.ALVO_DEDUZIDO) -> None:
    if arquivo_ifc is None:
        st.error("Envie um modelo IFC antes de analisar.")
        return
    # A aplicabilidade é decidida com as declarações do EMPREENDIMENTO
    # (implantação, de 2.1.1) e a tipologia da edificação (ADR-021) somadas às
    # locais da tela — só com as locais, regras da tipologia errada entravam
    # (EDI-001 num empreendimento de apartamento). Mesma fusão de `analise`.
    ids = grupos.ids_executaveis(
        grupo, analise.declaracoes_da_analise(empreendimento, declaracoes))
    if not ids:
        st.error("Nenhuma verificação do grupo é executável com as "
                 "declarações informadas.")
        return
    with st.spinner("Analisando o modelo IFC…"):
        caminho_ifc = uploads.salvar_upload(arquivo_ifc, "entradas/ifc",
                                            arquivo_ifc.name)
        relatorio = analise.analisar_modelo(chave, empreendimento, caminho_ifc,
                                            ids, declaracoes,
                                            unidades_representadas, alvo)

    # O IFC não abriu. Esta é a ÚNICA porta das duas telas
    # que analisam modelo — Georreferenciamento e Programa de necessidades —,
    # então tratar aqui cobre as duas e impede que divirjam.
    #
    # Não se guarda relatório nem se inicia a conversão 3D: sem relatório a tela
    # continua no estado "envie um modelo e analise", que é o estado verdadeiro;
    # e a conversão falharia de novo, em segundo plano, onde ninguém vê o erro.
    if relatorio.get("erro_ingestao"):
        st.error(relatorio["erro_ingestao"], icon=":material/error:")
        st.caption("**Nenhuma verificação foi executada.** O resultado acima é "
                   "sobre o arquivo, não sobre o projeto — por isso ele não "
                   "entra como requisito não conforme nem reduz a cobertura da "
                   "análise. Exporte o modelo num schema publicado e envie de "
                   "novo.")
        return

    st.session_state[chaves.chave_relatorio(chave)] = relatorio
    # Caminho do IFC analisado — permite reprocessar a visualização depois
    # (ex.: posicionamento aproximado na checagem de georreferenciamento).
    st.session_state[chaves.chave_caminho_ifc(chave)] = caminho_ifc

    # A visualização 3D (conversão IFC -> 3D Tiles) é desacoplada da análise:
    # roda em segundo plano e habilita os relatórios que exibem o modelo.
    conversao_3d.iniciar_conversao(chave, caminho_ifc)
    st.rerun()  # próximo ciclo já exibe os resultados
