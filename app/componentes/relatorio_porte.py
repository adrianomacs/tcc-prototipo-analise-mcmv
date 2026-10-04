"""Relatório do EMP-025 — o porte do empreendimento (ADR-034).

O EMP-025 é um requisito-pai que exige **os dois** limites de UH do item 4.I.a
(por empreendimento, EMP-025.1; do grupo de contíguos, EMP-025.2). O
``detalhe`` do pai traz a agregação; o do EMP-025.1 traz a população, a faixa
e os dois limites; o do EMP-025.2, a remessa ao parecer. Este módulo traduz
isso para a tela na ordem do ADR-034 — sem recalcular nada: o que a regra
gravou é o que a tela diz.

As funções ``texto_*``/``criterio_*``/``avisos_*`` são puras e são o que se
testa; ``painel_*`` só desenha.
"""

from __future__ import annotations

from html import escape

import streamlit as st

from app.componentes.avisos import ALERTA, Aviso
from app.componentes.paineis import ROTULO_ESTADO
from app.servicos.territorio import formatar_numero

ID_INDIVIDUAL = "EMP-025.1"
ID_CONTIGUOS = "EMP-025.2"

# Frase de contexto (ADR-034 (e)): porte não tem fonte na lista de referências — a
# frase vai sem citação; a Portaria é o próprio objeto da verificação.
CONTEXTO_PORTE = (
    "Para fins de avaliação deste requisito, o porte do município é definido "
    "pela sua população indicada no Censo Demográfico 2022 (IBGE). "
    "A faixa em que ela cai define dois limites de unidades habitacionais (UH) "
    "no item 4.I.a do Anexo II da Portaria MCID nº 725/2023: um para o "
    "empreendimento e outro para o grupo de empreendimentos contíguos — os "
    "que distam até 1 km entre si (art. 4º, II). O requisito só é atendido "
    "quando os dois limites são respeitados.")


def _inteiro(valor) -> str:
    return "—" if valor is None or valor == "" else formatar_numero(valor, 0)


def membro(membros: list[dict], rid: str) -> dict:
    """A linha do relatório do membro ``rid``, ou ``{}``."""
    return next((m for m in membros or [] if m.get("requisito") == rid), {})


def eh_porte(membros: list[dict]) -> bool:
    """O requisito agregado é o do porte (despacho da página de relatório)."""
    return ((membro(membros, ID_INDIVIDUAL).get("detalhe") or {}).get("tipo")
            == "porte_empreendimento")


def criterio_porte(det_individual: dict) -> str:
    """O "Exige/Medido" do card, dos campos que o EMP-025.1 gravou."""
    limite = det_individual.get("limite")
    grupo = det_individual.get("limite_grupo_contiguos")
    if limite is None:
        return ""
    exige = (f"<b>Exige:</b> até <b>{_inteiro(limite)} UH</b> no empreendimento "
             f"e até <b>{_inteiro(grupo)} UH</b> no grupo de contíguos")
    faixa = det_individual.get("faixa")
    if faixa:
        exige += f" (municípios {escape(faixa)})"
    previstas = det_individual.get("unidades_previstas")
    medido = (f" <b>Medido:</b> {_inteiro(previstas)} UHs previstas; grupo de "
              "contíguos não avaliado." if previstas else "")
    return f"{exige}.{medido}"


def texto_decisao(det_pai: dict) -> str:
    """Como o "e" da norma decidiu, sem cor de veredito (ADR-034 (c))."""
    k = det_pai.get("k", 2)
    n_conf, n_pot = det_pai.get("n_conf", 0), det_pai.get("n_pot", 0)
    total = det_pai.get("total_membros", k)
    if n_conf >= k:
        return f"Os {total} limites foram confirmados."
    if n_pot < k:
        return (f"Confirmados {n_conf} de {total}; mesmo que o limite em aberto "
                f"fosse atendido, seriam no máximo {n_pot} — por isso o "
                "requisito não é atendido.")
    return (f"Confirmados {n_conf} de {total}; o limite em aberto decide. Como "
            "ele depende de parecer, a ferramenta pode reprovar o requisito, "
            "nunca aprová-lo.")


def avisos_porte(det_individual: dict) -> list[Aviso]:
    """Números de Informações Gerais que não fecham entre si."""
    inconsistencias = det_individual.get("inconsistencias") or []
    if not inconsistencias:
        return []
    return [Aviso(ALERTA, "Os números declarados em Informações Gerais não "
                          "fecham entre si.",
                  "; ".join(inconsistencias) + ".",
                  "A correção é do proponente, em Informações Gerais.")]


# ---------------------------------------------------------------------------
# Blocos de tela
# ---------------------------------------------------------------------------

def nome_municipio(municipio: dict) -> str:
    """ "Estrela/RS", ou "—" sem município."""
    nome = (municipio or {}).get("nome") or ""
    uf = (municipio or {}).get("uf") or ""
    return f"{nome}/{uf}" if nome and uf else (nome or "—")


def painel_resultado(det_individual: dict, individual: dict,
                     contiguos: dict, municipio: dict | None = None) -> None:
    """Métricas do cruzamento, a tabela dos dois limites e o que cada um diz."""
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Município", nome_municipio(municipio or {}))
    c2.metric("População (Censo 2022)", _inteiro(det_individual.get("populacao")))
    c3.metric("Limite por empreendimento",
              f"{_inteiro(det_individual.get('limite'))} UH")
    c4.metric("UHs previstas", _inteiro(det_individual.get("unidades_previstas")))

    st.dataframe(
        [{"Limite": "Por empreendimento",
          "Requisito": ID_INDIVIDUAL,
          "Máximo (UH)": _inteiro(det_individual.get("limite")),
          "Declarado (UH)": _inteiro(det_individual.get("unidades_previstas")),
          "Situação": ROTULO_ESTADO.get(individual.get("estado"), "—")},
         {"Limite": "Grupo de empreendimentos contíguos",
          "Requisito": ID_CONTIGUOS,
          "Máximo (UH)": _inteiro(det_individual.get("limite_grupo_contiguos")),
          "Declarado (UH)": "—",
          "Situação": ROTULO_ESTADO.get(contiguos.get("estado"), "—")}],
        hide_index=True, use_container_width=True)

    if individual.get("mensagem"):
        st.markdown(f"**Por empreendimento.** {individual['mensagem']}")
    det_c = contiguos.get("detalhe") or {}
    if contiguos:
        texto = ("**Grupo de contíguos.** Não é avaliado por esta ferramenta: "
                 f"{det_c.get('porque') or contiguos.get('mensagem', '')}")
        st.markdown(texto)
        if det_c.get("acao"):
            st.caption(f"**O que destrava:** {det_c['acao']}")


def painel_decisao(det_pai: dict, membros: list[dict]) -> None:
    """A mecânica do "e", recolhida; abre sozinha se o requisito não decide."""
    k = det_pai.get("k", 2)
    indeciso = det_pai.get("n_conf", 0) < k <= det_pai.get("n_pot", 0)
    with st.expander("Como este requisito foi decidido", expanded=indeciso,
                     icon=":material/rule:"):
        st.markdown(texto_decisao(det_pai))
        st.dataframe(
            [{"Limite": m.get("id", ""),
              "Situação": ROTULO_ESTADO.get(m.get("estado"), m.get("estado") or "—"),
              "Entra na conta como": m.get("rotulo_conta") or "—",
              "O que falta": m.get("rotulo_motivo") or "—"}
             for m in det_pai.get("membros") or []],
            hide_index=True, use_container_width=True)
        repro = det_pai.get("reprovabilidade") or {}
        if repro.get("explicacao"):
            st.caption(repro["explicacao"])


def painel_consulta(det_individual: dict, contiguos: dict) -> None:
    """Procedência da população e fundamento de cada limite."""
    partes = []
    if det_individual.get("fonte_populacao"):
        partes.append(f"**População:** {det_individual['fonte_populacao']}, "
                      f"referência {det_individual.get('referencia_populacao', '')}"
                      " — derivada do município, nunca declarada pelo proponente.")
    if det_individual.get("ref_portaria"):
        partes.append(f"**Limites:** Portaria MCID nº 725/2023, "
                      f"{det_individual['ref_portaria']}.")
    fundamento = (contiguos.get("detalhe") or {}).get("fundamento")
    if fundamento:
        partes.append(f"**Contiguidade:** {fundamento}.")
    if partes:
        st.caption("  \n".join(partes))
