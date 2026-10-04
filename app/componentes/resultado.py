"""Resultado final (card de síntese + métricas em requisitos) + tabela por requisito.

Extraído de `_checagem_comum.py`. ``origem_pagina`` é nó de `app.navegacao.arvore.Pagina` (ADR-010), e
`resultado_final` recebe o `Empreendimento` corrente para avisar quando o
relatório foi gerado para uma versão anterior dele (ADR-004).
"""

from __future__ import annotations

import streamlit as st

from app.componentes.card_verificacao import montar_card_grupo
from app.componentes.monitor_viz import _monitor_viz
from app.estado import chaves
from app.navegacao import arvore
from app.servicos import relatorios
from app.servicos.conversao_3d import estado_viz
from app.servicos.grupos import regras_registradas
from app.servicos.vereditos import (
    COR_ESTADO,
    ROTULO_ESTADO,
    _pct,
    _veredito_geral,
    contagens_em_requisitos,
    explicacao_do_resultado,
)


def _aviso_relatorio_desatualizado(relatorio: dict, empreendimento) -> None:
    """Regra 4 do §4.3: mudar o Empreendimento não limpa relatórios já
    rodados de OUTRAS checagens — mas eles precisam avisar que podem estar
    desatualizados. Compara a referência `{id, versao}` gravada em
    `meta.empreendimento` com o
    empreendimento corrente; sem `empreendimento` (chamador não o passou)
    ou sem a referência no relatório (relatório antigo), não há
    o que comparar — a ausência não é sinal de desatualização.
    """
    if empreendimento is None:
        return
    referencia = (relatorio.get("meta") or {}).get("empreendimento")
    if not referencia:
        return
    atual = empreendimento.referencia()
    if referencia == atual:
        return
    if referencia.get("id") != atual.get("id"):
        st.warning("Este relatório foi gerado para **outro empreendimento**. "
                   "Rode **Nova análise** para refletir o empreendimento "
                   "corrente.", icon=":material/history:")
    else:
        st.warning("Os dados do empreendimento mudaram desde esta análise "
                   "(versão "
                   f"{referencia.get('versao')} → {atual.get('versao')}). "
                   "Rode **Nova análise** para atualizar o relatório.",
                   icon=":material/history:")


def _metricas(resumo: dict) -> None:
    """As cinco métricas do grupo, **todas em requisitos da Portaria** (bloco
    ``normativo``), com uma legenda só (ADR-034, D1b.3b).

    Antes as contagens de cima vinham das linhas executadas e a legenda dizia
    que descreviam a tabela — mas a tabela lista requisitos, com as
    alternativas recolhidas, e os dois universos lado a lado convidavam a somar
    colunas erradas. Agora número e tabela falam da mesma unidade.
    """
    norm = resumo.get("normativo") or resumo
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Conformes", norm.get("conforme", 0))
    c2.metric("Não conformes", norm.get("nao_conforme", 0))
    c3.metric("Não avaliáveis", norm.get("nao_avaliavel", 0))
    c4.metric("Conformidade", _pct(norm.get("conformidade")),
              help="Conformes ÷ (conformes + não conformes), entre os requisitos "
                   "que foi possível avaliar.")
    c5.metric("Capacidade de conclusão", _pct(norm.get("cobertura")),
              help="Requisitos que foi possível avaliar (conformes e não "
                   "conformes) ÷ requisitos aplicáveis: quanto do grupo o "
                   "insumo entregue permitiu concluir.")
    st.caption(legenda_das_metricas(norm))


def legenda_das_metricas(norm: dict) -> str:
    """A legenda única das métricas — função pura, para teste."""
    total = norm.get("total", 0)
    frase = (f"Contados sobre {'o' if total == 1 else 'os'} **{total} "
             f"{'requisito' if total == 1 else 'requisitos'} da Portaria** deste grupo")
    if norm.get("membros"):
        frase += "; as alternativas de um mesmo requisito contam como um só"
    return frase + "."


def resultado_final(chave: str, relatorio: dict, origem_pagina, empreendimento=None,
                    com_metricas: bool = True) -> None:
    """Veredito + tabela por requisito, cada um com o botão do seu relatório
    (ADR-034: não há relatório consolidado de grupo)."""
    _aviso_relatorio_desatualizado(relatorio, empreendimento)

    resumo = relatorio.get("resumo", {})
    label, cor = _veredito_geral(resumo)
    norm = resumo.get("normativo") or resumo

    # O card de síntese (ADR-034, D1b.3b): o mesmo desenho do card do
    # Relatório de Checagem — veredito com a cor
    # do estado, contagens em requisitos e por que o grupo tem esse resultado.
    st.markdown(montar_card_grupo(
        "Resultado final", label, cor, contagens_em_requisitos(norm),
        explicacao_do_resultado(norm)), unsafe_allow_html=True)
    # Na Cobertura do Protótipo (2.4.1) as contagens de cada checagem já
    # estão no título do expander e na tabela; repeti-las aqui duplicaria os
    # indicadores do topo da página com números de uma checagem só.
    if com_metricas:
        _metricas(resumo)

    st.markdown("##### Requisitos verificados")
    requisitos = relatorio.get("por_requisito", [])
    if not requisitos:
        st.info("Nenhum requisito foi verificado.")
        return

    larguras_cols = [1, 2, 5, 2]
    cab = st.columns(larguras_cols)
    cab[0].markdown("**Estado**")
    cab[1].markdown("**Requisito**")
    cab[2].markdown("**Descrição**")
    cab[3].markdown("**Relatório**")

    com_visualizacao = _regras_com_visualizacao()
    # Uma linha por REQUISITO da Portaria, com as alternativas recolhidas dentro
    # dele. A mesma unidade do par conformidade × cobertura: uma lista
    # plana de sete verificações ao lado de números calculados sobre três convida
    # a somar as colunas erradas.
    for grupo in relatorios.agrupar(relatorio):
        r = grupo["requisito"]
        _linha_requisito(chave, r, larguras_cols, com_visualizacao, origem_pagina,
                         membros=grupo["membros"])
        if grupo["membros"]:
            _alternativas(r, grupo["membros"])

    # Enquanto a conversão 3D roda em segundo plano, reprocessa a página a cada
    # 2 s para atualizar os botões que exibem o modelo. Só se houve conversão
    # disparada nesta checagem: `estado_viz` responde "processando" também
    # quando não há job nenhum, e as checagens sem IFC (Enquadramento,
    # Qualificação) ficavam com o aviso de conversão para sempre.
    if (st.session_state.get(chaves.chave_viz_job_id(chave))
            and estado_viz(chave) == "processando"):
        _monitor_viz(chave)


def _linha_requisito(chave: str, r: dict, larguras_cols: list[int],
                     com_visualizacao: set[str], origem_pagina, *,
                     membros: list[dict]) -> None:
    """Uma linha da tabela de resultados, com o ponto de estado e o botão."""
    estado = r.get("estado", "")
    cor_e = COR_ESTADO.get(estado, "#888")
    col = st.columns(larguras_cols)
    col[0].markdown(
        f"<span style='color:{cor_e};font-size:22px;line-height:1'>●</span>"
        f"<br><span style='font-size:11px;color:{cor_e}'>"
        f"{ROTULO_ESTADO.get(estado, estado)}</span>",
        unsafe_allow_html=True,
    )
    col[1].write(r.get("requisito", ""))
    col[2].write(r.get("descricao", ""))
    _botao_relatorio(chave, col[3], r, com_visualizacao, origem_pagina,
                     membros=membros)


def _alternativas(r: dict, membros: list[dict]) -> None:
    """As alternativas do requisito, recolhidas sob ele.

    Elas não têm botão de relatório próprio: quem explica a alternativa é o
    relatório do requisito-pai, onde ela aparece como seção ao lado da medição e
    do intervalo. Aqui ficam só o estado e a causa, para o leitor entender a
    linha de cima sem sair da página.
    """
    from app.servicos import motivos

    rotulos = {m.get("requisito"): ROTULO_ESTADO.get(m.get("estado"),
                                                     m.get("estado") or "")
               for m in membros}
    resumo = " · ".join(f"{rid}: {rot}" for rid, rot in rotulos.items())
    with st.expander(f"Alternativas de {r.get('requisito','')} — {resumo}",
                     icon=":material/call_split:"):
        st.caption("A Portaria satisfaz este requisito por qualquer das "
                   "alternativas abaixo. O relatório do requisito explica as "
                   "duas em conjunto — elas não têm relatório separado.")
        for m in membros:
            estado = m.get("estado", "")
            cor_e = COR_ESTADO.get(estado, "#888")
            motivo = (m.get("detalhe") or {}).get(motivos.CHAVE, "")
            causa = f" · {motivos.rotulo(motivo)}" if motivo else ""
            st.markdown(
                f"<span style='color:{cor_e}'>●</span> "
                f"**{m.get('requisito','')}** — {m.get('descricao','')}<br>"
                f"<span style='font-size:12px;color:#5B6770'>"
                f"{ROTULO_ESTADO.get(estado, estado)}{causa}</span>",
                unsafe_allow_html=True)
            if m.get("mensagem"):
                st.caption(m["mensagem"])


def _regras_com_visualizacao() -> set[str]:
    """Ids das regras cujo relatório exibe o modelo 3D (metadado usa_visualizacao)."""
    return {rid for rid, cls in regras_registradas().items()
            if getattr(cls, "usa_visualizacao", False)}


def _abrir_relatorio(chave: str, r: dict, origem_pagina,
                     membros: list[dict] | None = None) -> None:
    """Abre o relatório de um requisito, levando as alternativas dele.

    Os membros viajam no ``session_state`` porque a página de relatório recebe
    **um** requisito e o relatório de um requisito agregado precisa das
    alternativas para se montar. São as próprias linhas do
    ``relatorio.json``, sem releitura de nada — a regra de ouro do R5d continua
    valendo: a tela se reproduz a partir do relatório gerado.

    ``origem_pagina`` é um nó `Pagina` — guardado
    como está, não como string, para o "Voltar" de `relatorio.py` usar
    `.caminho` sem depender de nenhum caminho hardcoded.
    """
    st.session_state[chaves.REQ_SELECIONADO] = r
    st.session_state[chaves.MEMBROS_SELECIONADOS] = list(membros or [])
    st.session_state[chaves.ORIGEM_RELATORIO] = origem_pagina
    # Viaja junto com REQ_SELECIONADO/ORIGEM_RELATORIO — é a chave que
    # a página de relatório usa para carregar a visualização 3D da MESMA
    # checagem que abriu este requisito, em vez da pasta/job globais de antes.
    st.session_state[chaves.CHAVE_SELECIONADA] = chave
    st.switch_page(arvore.PAGINA_RELATORIO.caminho)


def _botao_relatorio(chave: str, coluna, r: dict, com_visualizacao: set[str],
                     origem_pagina, *,
                     membros: list[dict] | None = None) -> None:
    """Botão 'Verificar relatório'.

    Regras que exibem o modelo 3D (``usa_visualizacao``) refletem o estado da
    conversão em segundo plano: ficam em 'Processando visualização…' até os
    artefatos ficarem prontos. As demais abrem o relatório na hora.
    """
    req = r.get("requisito", "")
    if req not in com_visualizacao:
        if coluna.button("Verificar relatório", key=f"ver_{req}"):
            _abrir_relatorio(chave, r, origem_pagina, membros)
        return

    if estado_viz(chave) == "processando":
        coluna.button("⏳ Processando visualização…", key=f"ver_{req}_proc",
                      disabled=True, help="A conversão do modelo para 3D está em "
                      "andamento em segundo plano.")
    else:  # 'pronto' ou 'erro' (no erro, a página cai no fallback do relatório)
        if coluna.button("Verificar relatório", key=f"ver_{req}"):
            _abrir_relatorio(chave, r, origem_pagina, membros)
