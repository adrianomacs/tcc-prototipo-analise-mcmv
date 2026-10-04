"""Relatório da absortância solar — EDI-019 (paredes externas) e EDI-024
(telhado), no padrão do ADR-034.

Cada requisito é um pai em seleção exclusiva: a zona bioclimática escolhe o
ramo (EDI-0xx.1 ≤ 0,6 ou EDI-0xx.2 ≤ 0,4). O ``detalhe`` de cada ramo traz o
limite, a faixa de zonas, a zona resolvida, a população de revestimentos
(``IfcCovering``) e a situação de cada um; o do pai, a seleção. Este módulo
traduz isso para a tela sem recalcular nada.

A cena 3D desenha cada revestimento avaliado como uma caixa na cor do seu
resultado, lido da ``situacao`` que o ramo gravou (ADR-034); a caixa vem do
``revestimentos.json`` da conversão (ADR-001).

As funções ``texto_*``/``criterio_*``/``avisos_*``/``linhas_*`` são puras e
são o que se testa; ``painel_*`` só desenha.
"""

from __future__ import annotations

from html import escape

import streamlit as st

from app.componentes.avisos import ALERTA, Aviso
from app.componentes.paineis import ROTULO_ESTADO
from app.componentes.paineis import (
    _tabela_com_destaque_dimensao as tabela_com_destaque,
)
from app.componentes.relatorio_ambientes import ATENDE, NAO_ATENDE, NEUTRO
from app.servicos.territorio import formatar_numero

RAMO_APLICAVEL = "aplicavel"
RAMO_INAPLICAVEL = "inaplicavel"
RAMO_INDETERMINADA = "indeterminada"

_ROTULO_RAMO = {
    RAMO_APLICAVEL: "aplicável à zona do município",
    RAMO_INAPLICAVEL: "não se aplica à zona do município",
    RAMO_INDETERMINADA: "considerado em qualquer zona",
}

# Frases de contexto (ADR-034 (e)): absortância e zona bioclimática não têm
# fonte na lista de referências — frases sem citação.
CONTEXTO_ABSORTANCIA = (
    "A absortância solar é a fração da radiação do sol que uma superfície "
    "absorve, de 0 a 1 — quanto mais escura a superfície, maior o valor. A "
    "Portaria limita a absortância das paredes externas e do telhado conforme "
    "a zona bioclimática do município: conforme a zona, o limite é 0,6 ou "
    "0,4. O valor é lido nos revestimentos do modelo — os "
    "acabamentos aplicados às paredes e ao telhado.")

CONTEXTO_TELHADO = (
    "No telhado, a Portaria escreve as zonas pela numeração antiga do "
    "zoneamento (1 a 8), que a edição vigente não publica e que não se traduz "
    "para a nova. Por isso os dois limites são considerados: até 0,4 atende "
    "em qualquer zona, acima de 0,6 não atende em nenhuma, e entre os dois o "
    "resultado fica em aberto. Telha de barro não vitrificada e cobertura "
    "verde estão dispensadas do limite.")


def _decimal(valor) -> str:
    return "—" if valor is None else formatar_numero(valor, 2)


def _limite(valor) -> str:
    """Limite sem zero à direita: 0,6 e 0,4, como a Portaria escreve."""
    return "—" if valor is None else f"{float(valor):g}".replace(".", ",")


def ramos(membros: list[dict]) -> list[dict]:
    """As linhas dos ramos (membros com diagnóstico de absortância)."""
    return [m for m in membros or []
            if (m.get("detalhe") or {}).get("tipo") == "absortancia"]


def eh_absortancia(membros: list[dict]) -> bool:
    return bool(ramos(membros))


def eh_telhado(ramos_: list[dict]) -> bool:
    """O telhado é o caso cujos ramos têm aplicabilidade indeterminada."""
    return any((r.get("detalhe") or {}).get("aplicabilidade_do_ramo")
               == RAMO_INDETERMINADA for r in ramos_)


def zona(ramos_: list[dict]) -> str:
    for r in ramos_:
        classe = ((r.get("detalhe") or {}).get("zona_resolvida") or {}).get("classe")
        if classe:
            return classe
    return ""


def criterio_absortancia(ramos_: list[dict], valor_encontrado=None) -> str:
    """O "Exige/Medido" do card: os limites por faixa de zona e a zona."""
    if not ramos_:
        return ""
    faixas = []
    for r in ramos_:
        d = r.get("detalhe") or {}
        faixas.append(f"≤ <b>{_limite(d.get('limite'))}</b> nas zonas "
                      f"{escape(d.get('zonas_texto') or '—')}")
    exige = "<b>Exige:</b> absortância " + " ou ".join(faixas)
    classe = zona(ramos_)
    aplicavel = [r for r in ramos_ if (r.get("detalhe") or {})
                 .get("aplicabilidade_do_ramo") == RAMO_APLICAVEL]
    if classe and aplicavel:
        lim = _limite((aplicavel[0].get("detalhe") or {}).get("limite"))
        exige += f"; zona do município: {escape(classe)}, limite {lim}"
    elif classe:
        exige += (f"; zona do município: {escape(classe)}, sem correspondência "
                  "na numeração da Portaria")
    medido = ""
    if valor_encontrado is not None:
        medido = (f" <b>Medido:</b> maior absortância "
                  f"{_decimal(valor_encontrado)}.")
    return f"{exige}.{medido}"


def maior_absortancia(ramos_: list[dict]):
    """A maior absortância comparada em qualquer ramo (o ``valor_encontrado``)."""
    valores = [r.get("valor_encontrado") for r in ramos_
               if isinstance(r.get("valor_encontrado"), (int, float))]
    return max(valores) if valores else None


def avisos_absortancia(ramos_: list[dict]) -> list[Aviso]:
    """Declarações do modelo que se contradizem bloqueiam o ramo (alerta)."""
    for r in ramos_:
        if (r.get("detalhe") or {}).get("motivo_nao_avaliavel") \
                == "inconsistencia_declaratoria":
            return [Aviso(
                ALERTA, "O modelo declara a mesma parede como externa e como "
                        "interna.",
                "O revestimento e a parede que ele cobre dizem coisas opostas, "
                "e a verificação não escolhe entre elas.",
                "Corrija a declaração no modelo autoral.",
                referencia=r.get("mensagem", ""))]
    return []


def texto_resultado(ramos_: list[dict]) -> str:
    """Uma frase: quantos revestimentos entraram e o que a zona decidiu."""
    if not ramos_:
        return ""
    d = ramos_[0].get("detalhe") or {}
    pop = d.get("populacao") or {}
    alvo = pop.get("alvo")
    n_alvo = len(alvo) if isinstance(alvo, list) else (alvo or 0)
    total = pop.get("total_coverings", 0)
    parte = "telhado" if eh_telhado(ramos_) else "paredes externas"
    if not n_alvo:
        return (f"Nenhum dos {total} revestimento(s) do modelo está declarado "
                f"como revestimento de {parte}: sem eles, a absortância não "
                "tem onde ser lida.")
    return (f"**{n_alvo}** de {total} revestimento(s) do modelo estão "
            f"declarados como revestimento de {parte} e entraram na "
            "verificação.")


def linhas_revestimentos(ramos_: list[dict]) -> list[dict]:
    """Uma linha por revestimento, com a situação sob o limite de cada ramo."""
    linhas: dict[str, dict] = {}
    for r in ramos_:
        d = r.get("detalhe") or {}
        coluna = f"Até {_limite(d.get('limite'))}"
        for c in d.get("coverings") or []:
            gid = c.get("global_id", "")
            linha = linhas.setdefault(gid, {
                "Revestimento": c.get("nome") or gid,
                "Material": ", ".join(c.get("materiais") or []) or "—",
                "Absortância": _decimal(c.get("absortancia")),
            })
            linha[coluna] = c.get("rotulo_situacao") or "—"
    return list(linhas.values())


# ---------------------------------------------------------------------------
# Blocos de tela
# ---------------------------------------------------------------------------

# As contagens da população em linguagem do usuário, na ordem de leitura.
ROTULO_POPULACAO = {
    "total_coverings": "Revestimentos no modelo",
    "alvo": "Entraram na verificação",
    "parede_pelo_hospedeiro": "De parede, identificados pela parede que revestem",
    "parede_pelo_predefinido": "De parede, identificados pelo tipo declarado "
                               "no revestimento (CLADDING)",
    "cobertura_pelo_hospedeiro": "De cobertura, identificados pelo elemento "
                                 "que revestem",
    "cobertura_pelo_predefinido": "De cobertura, identificados pelo tipo "
                                  "declarado no revestimento (ROOFING)",
    "cobertura_sem_roofing": "De cobertura sem o tipo ROOFING declarado",
    "declarada_interna": "De parede declarados internos",
    "sem_declaracao": "De parede sem declaração de externo ou interno",
    "divergente": "De parede com declaração contrária à da parede revestida",
    "cobertura": "De cobertura (fora desta verificação)",
    "parede": "De parede (fora desta verificação)",
    "nao_classificados": "Sem classificação (nem parede nem cobertura)",
}


def linhas_populacao(pop: dict) -> list[dict]:
    """As contagens da população, traduzidas; chave desconhecida mantém o nome."""
    ordem = list(ROTULO_POPULACAO) + [k for k in pop if k not in ROTULO_POPULACAO]
    linhas = []
    for chave in ordem:
        if chave not in pop or chave in ("criterio", "mensagem_vazia"):
            continue
        valor = pop[chave]
        linhas.append({"Revestimentos": ROTULO_POPULACAO.get(chave, chave),
                       "Quantidade": len(valor) if isinstance(valor, list) else valor})
    return linhas


def texto_acima_do_limite(ramos_: list[dict]) -> str:
    """A frase que explica a reprovação: quantos revestimentos passam do
    limite que decide. O limite que decide é o do ramo aplicável; sem ramo
    aplicável (telhado), o maior dos limites — acima dele, nenhuma zona
    aprova."""
    if not ramos_:
        return ""
    aplicaveis = [r for r in ramos_ if (r.get("detalhe") or {})
                  .get("aplicabilidade_do_ramo") == RAMO_APLICAVEL]
    if aplicaveis:
        ramo, qualificador = aplicaveis[0], "da zona do município"
    else:
        ramo = max(ramos_, key=lambda r: (r.get("detalhe") or {}).get("limite") or 0)
        qualificador = "o maior limite, que nenhuma zona ultrapassa"
    d = ramo.get("detalhe") or {}
    coverings = d.get("coverings") or []
    acima = [c for c in coverings if c.get("situacao") == "nao_atende"]
    if not acima:
        return ""
    parte = "telhado" if eh_telhado(ramos_) else "paredes externas"
    maior = max(c.get("absortancia") or 0 for c in acima)
    return (f"**{len(acima)} de {len(coverings)} revestimento(s) de {parte} "
            f"estão acima do limite de {_limite(d.get('limite'))}** "
            f"({qualificador}); o maior valor é {_decimal(maior)}. Basta um "
            "revestimento acima do limite para o requisito não ser atendido — "
            "eles estão em vermelho na tabela de \"Como este requisito foi "
            "decidido\".")


def destaques_revestimentos(linhas: list[dict]) -> dict[str, list[str | None]]:
    """Para cada coluna de limite, "ok" (atende), "falha" (acima) ou ``None``
    — o verde/vermelho por célula da tabela de revestimentos."""
    cor = {"atende ao limite": "ok", "acima do limite": "falha"}
    colunas = {c for linha in linhas for c in linha if c.startswith("Até ")}
    return {c: [cor.get(linha.get(c)) for linha in linhas] for c in sorted(colunas)}


def painel_resultado(ramos_: list[dict], municipio: dict | None = None) -> None:
    municipio = municipio or {}
    nome = municipio.get("nome") or "—"
    if municipio.get("nome") and municipio.get("uf"):
        nome = f"{municipio['nome']}/{municipio['uf']}"
    c1, c2, c3 = st.columns(3)
    c1.metric("Município", nome)
    c2.metric("Código IBGE", municipio.get("codigo_ibge") or "—")
    c3.metric("Zona bioclimática", zona(ramos_) or "—")
    st.markdown(texto_resultado(ramos_))
    acima = texto_acima_do_limite(ramos_)
    if acima:
        st.markdown(acima)
    for r in ramos_:
        d = r.get("detalhe") or {}
        rotulo = _ROTULO_RAMO.get(d.get("aplicabilidade_do_ramo"), "")
        st.markdown(f"**{r.get('requisito', '')}** — até {_limite(d.get('limite'))}"
                    f", zonas {d.get('zonas_texto', '—')} · {rotulo} · "
                    f"{ROTULO_ESTADO.get(r.get('estado'), r.get('estado') or '—')}")


def revestimentos_para_cena(ramos_: list[dict]) -> list[dict]:
    """Os revestimentos que entraram na verificação, com o resultado de cada
    um para a cor da cena, sem campo novo no relatório (ADR-034).

    Decide o ramo aplicável à zona do município, pela ``situacao`` que ele
    gravou. Sem ramo aplicável (o telhado, cujas zonas não se traduzem), um
    revestimento só atende se atende sob todos os limites e só não atende
    se passa de todos; entre os dois fica em aberto, como a frase de
    contexto do telhado explica. Exceção da Portaria, material não
    identificável e absortância não informada ficam neutros, porque não
    entraram na comparação.
    """
    aplicaveis = [r for r in ramos_ if (r.get("detalhe") or {})
                  .get("aplicabilidade_do_ramo") == RAMO_APLICAVEL]
    considerados = aplicaveis[:1] or list(ramos_)
    situacoes: dict[str, list[str]] = {}
    rotulos: dict[str, str] = {}
    nomes: dict[str, str] = {}
    absortancias: dict[str, object] = {}
    for r in considerados:
        for c in (r.get("detalhe") or {}).get("coverings") or []:
            gid = c.get("global_id")
            if not gid:
                continue
            situacoes.setdefault(gid, []).append(c.get("situacao") or "")
            rotulos.setdefault(gid, c.get("rotulo_situacao") or "")
            nomes.setdefault(gid, c.get("nome") or gid)
            absortancias.setdefault(gid, c.get("absortancia"))
    itens = []
    for gid, sits in situacoes.items():
        if all(s == "atende" for s in sits):
            resultado = ATENDE
        elif all(s == "nao_atende" for s in sits):
            resultado = NAO_ATENDE
        else:
            resultado = NEUTRO
        rotulo = rotulos[gid]
        if len(sits) > 1 and resultado == NEUTRO and set(sits) <= {"atende", "nao_atende"}:
            rotulo = "entre os dois limites, em aberto"
        itens.append({"global_id": gid, "nome": nomes[gid],
                      "resultado": resultado, "rotulo": rotulo,
                      "absortancia": absortancias.get(gid)})
    return itens


def legenda_cena(itens: list[dict], com_caixas: int) -> str:
    """A frase sob a cena, conforme o que ela conseguiu destacar."""
    if not itens:
        return ("Nenhum revestimento do modelo entrou nesta verificação, então "
                "a cena mostra o modelo sem nada a destacar.")
    if not com_caixas:
        return ("A conversão deste modelo não trouxe a posição dos "
                "revestimentos, então a cena mostra o modelo sem destaque. "
                "Analisar o modelo de novo refaz a conversão.")
    texto = ("A cena mostra o modelo com as cores dele. Clique num "
             "revestimento da lista para ver a caixa que o envolve, na cor do "
             "seu resultado, ou destaque todos de uma vez. A caixa segue os "
             "eixos do modelo e cobre também as aberturas da placa, como as "
             "janelas.")
    faltam = len(itens) - com_caixas
    if faltam > 0:
        texto += (f" {faltam} revestimento(s) sem geometria no modelo "
                  "convertido não aparecem na cena.")
    return texto


def painel_decisao(detalhe_pai: dict, ramos_: list[dict]) -> None:
    """A seleção pela zona e a tabela dos revestimentos, recolhidas; abre
    sozinho quando algum revestimento fica acima de um limite."""
    linhas = linhas_revestimentos(ramos_)
    destaques = destaques_revestimentos(linhas)
    problema = any(e == "falha" for lista in destaques.values() for e in lista)
    with st.expander("Como este requisito foi decidido", expanded=problema,
                     icon=":material/rule:"):
        st.caption(detalhe_pai.get("rotulo_modo") or "")
        st.dataframe(
            [{"Ramo": m.get("id", ""),
              "Aplicação": m.get("rotulo_aplicabilidade") or "—",
              "Situação": ROTULO_ESTADO.get(m.get("estado"), m.get("estado") or "—"),
              "Entra na conta como": m.get("rotulo_conta") or "—",
              "O que falta": m.get("rotulo_motivo") or "—"}
             for m in detalhe_pai.get("membros") or []],
            hide_index=True, use_container_width=True)
        if linhas:
            st.markdown(f"**Revestimentos avaliados ({len(linhas)})**")
            tabela_com_destaque(linhas, destaques)
            st.caption("Verde: atende ao limite da coluna. Vermelho: acima dele. "
                       "Sem cor: o valor não entrou na comparação (material não "
                       "identificável, absortância não informada ou exceção da "
                       "Portaria).")


def painel_populacao(ramos_: list[dict]) -> None:
    """Quais revestimentos entraram e por quê — abre sozinho se nenhum entrou."""
    if not ramos_:
        return
    d = ramos_[0].get("detalhe") or {}
    pop = d.get("populacao") or {}
    alvo = pop.get("alvo")
    vazio = not (alvo if isinstance(alvo, list) else alvo)
    with st.expander("Quais revestimentos entraram na verificação",
                     expanded=vazio, icon=":material/layers:"):
        if pop.get("criterio"):
            st.markdown(f"**Critério:** {pop['criterio']}.")
        st.dataframe(linhas_populacao(pop), hide_index=True,
                     use_container_width=True)
        if d.get("explicacao_aplicabilidade"):
            st.caption(d["explicacao_aplicabilidade"])
        fonte = (d.get("zona_resolvida") or {}).get("fonte")
        if fonte:
            st.caption(f"Zona bioclimática: {fonte.replace('_', ' ')}.")
