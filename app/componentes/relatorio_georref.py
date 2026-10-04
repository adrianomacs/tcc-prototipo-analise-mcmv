"""Relatório do EMP-001 — os textos e os blocos da página (ADR-034).

O ``detalhe`` do EMP-001 carrega a escada da escala LoGeoRef, a procedência,
a consistência das fontes de localização e os dois confrontos de posição
(município e terreno). Este módulo traduz esse conteúdo para a tela na ordem do
ADR-034: aviso na faixa, critério no card, frase de contexto, o que o modelo
tem e, em expanders, o técnico. Nada aqui muda o ``detalhe`` nem o veredito —
é camada de apresentação.

As funções ``texto_*``/``avisos_*``/``criterio_*`` são puras e são o que se
testa; ``painel_*`` só desenha.
"""

from __future__ import annotations

from html import escape

import streamlit as st

from app.componentes.avisos import ALERTA, ORIENTACAO, Aviso
from app.componentes.paineis import painel_procedencia, render_localizacao
from app.servicos.territorio import formatar_numero

# Frase de contexto (ADR-034 (e)): a escala antes do resultado, com a
# referência da lista de referências.
CONTEXTO_LOGEOREF = (
    "O georreferenciamento do modelo é avaliado pela escala **LoGeoRef** "
    "(*Level of Georeferencing*), proposta por Clemen e Görne (2019), que "
    "classifica em níveis, de 10 a 60, onde e como o arquivo IFC registra a "
    "própria localização — do endereço postal (nível 10) ao sistema de "
    "coordenadas projetado com os parâmetros de conversão para ele (nível 50), "
    "recurso disponível só no IFC4. O requisito pede o modelo georreferenciado "
    "em UTM / SIRGAS 2000, o que corresponde ao nível 50. Atingido esse nível, "
    "a posição do modelo é ainda confrontada com os limites do município "
    "declarado (malha municipal do IBGE).")

# Cada degrau em linguagem do usuário (com artigo, para entrar numa frase) e a
# entidade IFC que o registra, que só aparece no expander.
NIVEIS_LOGEOREF = {
    10: ("o endereço postal", "IfcPostalAddress"),
    20: ("a latitude e a longitude do terreno",
         "IfcSite — RefLatitude / RefLongitude"),
    30: ("a posição e a rotação do terreno no modelo",
         "IfcSite — IfcLocalPlacement e norte verdadeiro"),
    40: ("o sistema de coordenadas do projeto com o norte verdadeiro",
         "IfcProject — WorldCoordinateSystem e TrueNorth"),
    50: ("o sistema de coordenadas projetado e a conversão para ele",
         "IfcProjectedCRS e IfcMapConversion"),
}


def _nome_do_degrau(degrau: dict) -> str:
    return NIVEIS_LOGEOREF.get(degrau.get("nivel"), (degrau.get("rotulo", ""),))[0]


def _enumerar(itens: list[str]) -> str:
    if len(itens) <= 1:
        return "".join(itens)
    return ", ".join(itens[:-1]) + " e " + itens[-1]


def lugar_declarado(declarada: dict) -> str:
    municipio, uf = declarada.get("municipio", ""), declarada.get("uf", "")
    return f"{municipio}/{uf}" if uf else municipio


def criterio_logeoref(detalhe: dict) -> str:
    """O "Exige/Medido" do card, montado dos campos que a regra gravou."""
    alvo = detalhe.get("alvo", 50)
    nivel = detalhe.get("nivel")
    declarada = detalhe.get("localizacao_declarada") or {}
    exige = f"<b>Exige:</b> nível {alvo} da escala LoGeoRef"
    if declarada.get("municipio"):
        exige += f" e posição dentro de {escape(lugar_declarado(declarada))}"
    if nivel is None:
        return exige + "."
    medido = f"<b>Medido:</b> nível {nivel}"
    if nivel >= alvo and declarada.get("avaliado"):
        onde = "dentro" if declarada.get("dentro") else "fora"
        medido += f", posição {onde} de {escape(lugar_declarado(declarada))}"
    return f"{exige}. {medido}."


def texto_resultado(detalhe: dict) -> str:
    """O que o modelo tem e o que falta, em uma ou duas frases."""
    nivel, alvo = detalhe.get("nivel", 0), detalhe.get("alvo", 50)
    degraus = detalhe.get("degraus") or []
    if nivel >= alvo:
        return (f"O modelo atinge o nível **{nivel}**: declara "
                f"{NIVEIS_LOGEOREF[50][0]}.")
    tem = [_nome_do_degrau(d) for d in degraus if d.get("presente")]
    falta = [_nome_do_degrau(d) for d in degraus if not d.get("presente")]
    if not tem:
        texto = (f"O modelo não registra a própria localização em nenhum "
                 f"nível da escala (alvo: {alvo}).")
    else:
        texto = (f"O modelo chega ao nível **{nivel}** de {alvo}: registra "
                 f"{_enumerar(tem)}")
        texto += "." if not falta else ""
    if falta:
        verbo = "falta" if len(falta) == 1 else "faltam"
        texto += (f"; {verbo} {_enumerar(falta)}." if tem
                  else f" Falta{'m' if len(falta) > 1 else ''} "
                       f"{_enumerar(falta)}.")
    return texto


def avisos_emp001(detalhe: dict) -> list[Aviso]:
    """Os avisos da faixa: o que a posição do modelo diz e o veredito não diz.

    * Âncora fora da poligonal do terreno → alerta. É aviso, nunca veredito
      (a regra calcula sem ler o veredito, e o veredito não o lê).
    * Posição no terreno não conferida, com o nível atingido → orientação.
      Abaixo do alvo não se avisa: a causa já está no card.
    * Posição aproximada (lat/long do terreno) fora do município, abaixo do
      alvo → alerta. Acima do alvo o confronto com o município é o próprio
      veredito e mora no card.
    """
    avisos: list[Aviso] = []
    nivel, alvo = detalhe.get("nivel", 0), detalhe.get("alvo", 50)
    pos = detalhe.get("posicionamento_terreno") or {}
    estado = pos.get("estado")
    if estado == "fora":
        dist = pos.get("distancia_m")
        tol = pos.get("tolerancia_m")
        medida = (f"Ela está a {formatar_numero(dist)} m da divisa, além da "
                  f"tolerância de {formatar_numero(tol, 0)} m. "
                  if dist is not None and tol is not None else "")
        avisos.append(Aviso(
            ALERTA, "A origem das coordenadas do modelo cai fora do terreno "
                    "declarado.",
            medida + "É um aviso: não altera o resultado do requisito.",
            "Confira no modelo autoral o ponto de referência das coordenadas "
            "compartilhadas."))
    elif estado == "nao_avaliado" and nivel >= alvo:
        avisos.append(Aviso(
            ORIENTACAO, "A posição do modelo no terreno não foi conferida.",
            "É uma conferência de apoio e não altera o resultado.",
            referencia=_frase(pos.get("motivo", ""))))

    declarada = detalhe.get("localizacao_declarada") or {}
    if (nivel < alvo and declarada.get("avaliado")
            and declarada.get("dentro") is False):
        avisos.append(Aviso(
            ALERTA, f"A localização gravada no modelo fica fora de "
                    f"{lugar_declarado(declarada)}.",
            "A latitude e a longitude do terreno no arquivo apontam para outro "
            "lugar. Não altera o resultado, que já decorre do nível atingido.",
            "Confira as coordenadas do terreno no modelo autoral."))
    return avisos


def _frase(texto: str) -> str:
    texto = (texto or "").strip()
    return texto[:1].upper() + texto[1:] if texto else ""


def texto_posicao_no_terreno(pos: dict) -> str:
    """O confronto âncora × poligonal, sem a palavra "tipologia" (ADR-034 (d))."""
    estado = pos.get("estado")
    tol = pos.get("tolerancia_m")
    tol_txt = f" (tolerância de {formatar_numero(tol, 0)} m)" if tol is not None else ""
    if estado == "dentro":
        dist = pos.get("distancia_m")
        onde = ("dentro do terreno ou sobre a divisa" if not dist
                else f"a {formatar_numero(dist)} m da divisa")
        return ("compatível com o terreno — a origem das coordenadas está "
                f"{onde}{tol_txt}.")
    if estado == "fora":
        dist = pos.get("distancia_m")
        return (f"fora do terreno declarado — a origem das coordenadas está a "
                f"{formatar_numero(dist)} m da divisa{tol_txt}.")
    if estado == "nao_aplicavel":
        texto = ("não se aplica — o modelo é de uma unidade tipo ou de uma "
                 "edificação isolada, que não tem posição própria no terreno; "
                 "a posição vem do modelo de implantação.")
        info = pos.get("distancia_informativa_m")
        if info is not None:
            texto += (f" Só para informação: a origem das coordenadas está a "
                      f"{formatar_numero(info)} m da divisa.")
        return texto
    motivo = pos.get("motivo", "")
    return "não conferida" + (f" — {motivo}" if motivo else ".")


def texto_posicao_no_municipio(declarada: dict) -> str:
    if not declarada:
        return "não conferida — município não declarado."
    lugar = lugar_declarado(declarada)
    if not declarada.get("avaliado"):
        motivo = declarada.get("motivo", "")
        return f"não conferida com {lugar}" + (f" — {motivo}" if motivo else ".")
    modo = (declarada.get("ancora") or {}).get("modo")
    qual = {"preciso": "a origem das coordenadas projetadas cai",
            "aproximado": "a latitude e a longitude do terreno caem"}.get(
                modo, "a posição do modelo cai")
    onde = "dentro" if declarada.get("dentro") else "fora"
    return f"{qual} {onde} de {lugar} (malha municipal do IBGE)."


# ---------------------------------------------------------------------------
# Blocos de tela
# ---------------------------------------------------------------------------

def painel_niveis(detalhe: dict) -> None:
    """A escada da escala, degrau a degrau, com a entidade IFC de cada um.
    Abre sozinho quando o nível fica abaixo do alvo (ADR-034 (c))."""
    nivel, alvo = detalhe.get("nivel", 0), detalhe.get("alvo", 50)
    schema = detalhe.get("schema") or "?"
    with st.expander(f"Níveis da escala LoGeoRef no modelo — {nivel} de {alvo} "
                     f"· {schema}", expanded=nivel < alvo,
                     icon=":material/stairs:"):
        for d in detalhe.get("degraus") or []:
            nome, entidade = NIVEIS_LOGEOREF.get(
                d.get("nivel"), (d.get("rotulo", ""), ""))
            marca = ":material/check:" if d.get("presente") else ":material/close:"
            linha = f"{marca} **Nível {d.get('nivel')}** — {nome}"
            if entidade:
                linha += f" · `{entidade}`"
            st.markdown(linha)
        lacunas = detalhe.get("lacunas") or []
        if lacunas:
            st.caption(f"Faltam para o nível {alvo}: "
                       + ", ".join(f"`{x}`" for x in lacunas) + ".")


def painel_posicao(detalhe: dict) -> None:
    """Os dois confrontos de posição — município e terreno — num só lugar."""
    pos = detalhe.get("posicionamento_terreno") or {}
    declarada = detalhe.get("localizacao_declarada") or {}
    if not (pos or declarada):
        return
    problema = pos.get("estado") == "fora" or declarada.get("dentro") is False
    with st.expander("Posição do modelo no município e no terreno",
                     expanded=problema, icon=":material/pin_drop:"):
        st.markdown(f"**No município:** {texto_posicao_no_municipio(declarada)}")
        if pos:
            st.markdown(f"**No terreno:** {texto_posicao_no_terreno(pos)}")
            if pos.get("crs"):
                st.caption(f"Medida no sistema de coordenadas do terreno "
                           f"({pos['crs']}).")
            if pos.get("justificativa"):
                st.caption(f"**Por que o terreno só avisa.** {pos['justificativa']}")


def painel_consistencia(detalhe: dict) -> None:
    loc = detalhe.get("localizacao") or {}
    if not loc:
        return
    with st.expander("Consistência entre as fontes de localização do modelo",
                     expanded=bool(loc.get("avisos")),
                     icon=":material/compare_arrows:"):
        render_localizacao(loc)


def painel_informacoes_extraidas(detalhe: dict) -> None:
    with st.expander("Informações extraídas do IFC", expanded=False,
                     icon=":material/table_view:"):
        st.caption("Origem de cada dado usado na verificação: classe IFC, "
                   "atributo e valor.")
        painel_procedencia(detalhe.get("procedencia") or {})
