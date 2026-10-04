"""Card de verificação — a abertura do relatório de um requisito (ADR-034).

Generaliza o banner que o relatório das ENQ já usava: id e estado, a
descrição do requisito, o motivo quando não avaliável, o critério (o que a
norma exige e o que foi medido) e "o que destrava". É o **único** lugar da
tela onde o veredito tem cor (ADR-034 (c)): conforme e não conforme nunca
passam por ``st.success``/``st.error``, para o vermelho de "não conforme" não
se confundir com o vermelho de "a ferramenta falhou".

A margem inferior do card separa o veredito da frase de contexto que vem
logo abaixo em todo relatório — colados, os dois se liam como um bloco só.

``montar_card`` é pura (devolve o HTML) e é a que se testa; ``card_verificacao``
só a desenha.
"""

from __future__ import annotations

from html import escape

import streamlit as st

from app.componentes.paineis import COR_ESTADO, ROTULO_ESTADO
from app.servicos import motivos


def montar_card(r: dict, detalhe: dict | None = None,
                criterio: str = "") -> str:
    """HTML do card. ``criterio`` é HTML já montado pela página a partir dos
    campos que a regra gravou (nunca digitado na tela): o card não sabe o que
    cada regra exige, e não deve saber."""
    detalhe = detalhe or {}
    estado = r.get("estado", "")
    cor = COR_ESTADO.get(estado, "#888")
    legenda = escape(r.get("descricao", "") or "")
    motivo = detalhe.get(motivos.CHAVE)
    if motivo:
        legenda = f"{legenda} · {escape(motivos.rotulo(motivo))}"
    linha_criterio = (f"<br><span style='font-size:12.5px;color:#3C4A52'>"
                      f"{criterio}</span>" if criterio else "")
    return (
        f"<div style='padding:12px 18px;border-radius:8px;background:{cor}1a;"
        f"margin-bottom:1.1rem;"
        f"border:1px solid {cor}'><span style='font-size:20px;font-weight:700;"
        f"color:{cor}'>{escape(r.get('requisito', '') or '')} — "
        f"{ROTULO_ESTADO.get(estado, estado)}</span><br>"
        f"<span style='font-size:12px;color:#5B6770'>{legenda}</span>"
        f"{linha_criterio}</div>")


def card_verificacao(r: dict, detalhe: dict | None = None,
                     criterio: str = "") -> None:
    """Desenha o card e, se o requisito não foi avaliado, o que o destrava."""
    detalhe = detalhe or {}
    st.markdown(montar_card(r, detalhe, criterio), unsafe_allow_html=True)
    motivo = detalhe.get(motivos.CHAVE)
    if motivo and motivos.ACAO.get(motivo):
        st.caption(f"**O que destrava:** {motivos.ACAO[motivo]}")


def montar_card_grupo(titulo: str, rotulo: str, cor: str, legenda: str,
                      explicacao: str = "") -> str:
    """O card de síntese de um grupo (resultado final da checagem e 2.4.2):
    o veredito do grupo, as contagens na legenda e, abaixo, por que o grupo
    tem esse resultado. Mesmo desenho do card de requisito."""
    linha = (f"<br><span style='font-size:12.5px;color:#3C4A52'>"
             f"{escape(explicacao)}</span>" if explicacao else "")
    return (
        f"<div style='padding:12px 18px;border-radius:8px;background:{cor}1a;"
        f"border:1px solid {cor};margin-bottom:1.1rem'><span style='font-size:20px;"
        f"font-weight:700;color:{cor}'>{escape(titulo)} — {escape(rotulo)}</span>"
        f"<br><span style='font-size:12px;color:#5B6770'>{escape(legenda)}</span>"
        f"{linha}</div>")
