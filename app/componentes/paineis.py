"""Componentes de UI compartilhados entre a página principal e as dedicadas."""

from __future__ import annotations

import streamlit as st

from app.servicos.vereditos import CONTA_CONFIRMADO

COR_ESTADO = {"conforme": "#34a853", "nao_conforme": "#ea4335", "nao_avaliavel": "#fbbc04"}
ROTULO_ESTADO = {"conforme": "Conforme", "nao_conforme": "Não conforme", "nao_avaliavel": "Não avaliável"}


def _render_logeoref(detalhe: dict, incluir_localizacao: bool = True) -> None:
    nivel, alvo = detalhe.get("nivel", 0), detalhe.get("alvo", 50)
    schema = detalhe.get("schema") or "?"
    st.markdown(f"**Diagnóstico de georreferenciamento** — LoGeoRef {nivel}/{alvo} · schema {schema}")
    for d in detalhe.get("degraus", []):
        marca = "[x]" if d.get("presente") else "[ ]"
        st.markdown(f"`{marca}` **{d.get('nivel')}** — {d.get('rotulo','')}")
    lacunas = detalhe.get("lacunas") or []
    if lacunas:
        st.markdown("**Faltam para o nível 50:**")
        for l in lacunas:
            st.markdown(f"- {l}")
    render_posicionamento_terreno(detalhe.get("posicionamento_terreno") or {})
    if incluir_localizacao:
        render_localizacao(detalhe.get("localizacao") or {})


def render_posicionamento_terreno(pos: dict) -> None:
    """Aviso âncora do modelo × poligonal do terreno (ADR-032).

    Exibido sempre que o relatório o traz — inclusive "não avaliado" e "não
    aplicável" —, com a tolerância e a justificativa à vista: é aviso, e o
    rótulo diz isso para que ninguém o leia como veredito.
    """
    if not pos:
        return
    estado = pos.get("estado")
    tol = pos.get("tolerancia_m")
    tol_txt = f"{tol:.0f} m" if tol is not None else "—"
    st.markdown("**Posicionamento no terreno** (âncora do modelo × poligonal "
                f"declarada · aviso, não altera o veredito · tolerância {tol_txt})")
    rotulo = pos.get("rotulo") or estado
    texto = pos.get("mensagem") or pos.get("motivo") or ""
    linha = f"{rotulo[:1].upper()}{rotulo[1:]}" + (f" — {texto}" if texto else "")
    if estado == "fora":
        st.warning(linha)
    elif estado == "dentro":
        st.success(linha)
    else:
        st.caption(linha)
    if pos.get("crs"):
        st.caption(f"Medida no CRS da poligonal: {pos['crs']}.")
    with st.expander("Por que a poligonal só avisa"):
        st.write(pos.get("justificativa") or "")


def render_localizacao(loc: dict) -> None:
    """Cruzamento endereço × IfcSite × CRS (consistência de localização)."""
    if not loc:
        return
    st.markdown("**Consistência de localização** (endereço × IfcSite × CRS)")

    end = loc.get("endereco") or {}
    partes = [", ".join(end.get("address_lines") or []), end.get("town"),
              end.get("postal_code"), end.get("country")]
    endereco_txt = " — ".join([p for p in partes if p])
    if endereco_txt:
        st.markdown(f"- **Endereço (IFC):** {endereco_txt}")
    site = loc.get("site_latlon")
    if site:
        st.markdown(f"- **IfcSite (lat/long):** {site[0]:.5f}, {site[1]:.5f}")
    crs = loc.get("crs_latlon")
    if crs:
        st.markdown(f"- **CRS (lat/long):** {crs[0]:.5f}, {crs[1]:.5f}")
    dist = loc.get("distancia_site_crs_km")
    if dist is not None:
        st.markdown(f"- **Distância IfcSite ↔ CRS:** {dist:.1f} km")
    sa, ca = loc.get("site_altura"), loc.get("crs_altura")
    if sa is not None or ca is not None:
        sa_txt = f"{sa:.2f} m" if sa is not None else "—"
        ca_txt = f"{ca:.2f} m" if ca is not None else "—"
        st.markdown(f"- **Altura (IfcSite / CRS):** {sa_txt} / {ca_txt}")
    dz = loc.get("divergencia_altura_m")
    if dz is not None:
        st.markdown(f"- **Divergência de altura:** {dz:.2f} m")
    for aviso in (loc.get("avisos") or []):
        st.warning(aviso)
    if loc.get("consistente") is True:
        st.caption("Fontes de localização consistentes entre si.")


def painel_procedencia(proc: dict) -> None:
    """Tabela de rastreabilidade: de qual classe/atributo IFC veio cada valor."""
    linhas = (proc or {}).get("linhas") or []
    if not linhas:
        st.caption("Sem informações de georreferenciamento extraíveis deste modelo.")
        return
    dados = [{"Classe IFC": l.get("classe", ""), "Propriedade": l.get("propriedade", ""),
              "Valor": l.get("valor", ""), "Fonte": l.get("fonte", "")} for l in linhas]
    st.dataframe(dados, hide_index=True, use_container_width=True,
                 column_config={"Fonte": st.column_config.TextColumn(width="small")})
    unidade = (proc or {}).get("unidade_projeto")
    if unidade:
        st.caption(f"Unidade de comprimento do projeto: {unidade}. "
                   "Valores marcados como *derivado* são calculados a partir dos atributos brutos.")


def _fmt_area(v) -> str:
    return f"{v:.2f}" if isinstance(v, (int, float)) and not isinstance(v, bool) else "—"


# Cor de realce das linhas de ambientes que tiveram correspondência no programa.
_COR_MATCH = "#d9f0d9"
# Par verde/vermelho claro p/ destaque POR CÉLULA de valores que atendem/reprovam
# um critério dimensional (mesmo peso visual do _COR_MATCH, legível com texto escuro).
_COR_OK = "#d9f0d9"
_COR_FALHA = "#fbdad9"


def _tabela_ambientes(dados: list[dict], matches: list[bool]) -> None:
    """Tabela interativa (``st.dataframe``) realçando as linhas com correspondência.

    Mantém ordenação/filtro nativos do ``st.dataframe``. O realce por cor usa o
    ``Styler`` do pandas (que requer jinja2); se o jinja2 não estiver disponível,
    exibe a tabela interativa sem cor (degradação graciosa, sem quebrar).
    """
    if not dados:
        return
    try:
        import pandas as pd
        df = pd.DataFrame(dados)
        try:
            def _realce(row):
                cor = f"background-color: {_COR_MATCH}" if matches[row.name] else ""
                return [cor] * len(row)
            objeto = df.style.apply(_realce, axis=1)   # requer jinja2
        except Exception:
            objeto = df                                # sem jinja2: interativa, sem cor
        st.dataframe(objeto, hide_index=True, use_container_width=True)
    except Exception:
        st.dataframe(dados, hide_index=True, use_container_width=True)


def _tabela_com_destaque_dimensao(dados: list[dict],
                                  destaques: dict[str, list[str | None]]) -> None:
    """Tabela interativa com destaque POR CÉLULA nas colunas de dimensão avaliada.

    Diferente de ``_tabela_ambientes`` (que realça a LINHA inteira por
    correspondência nominal), aqui o destaque fica só no VALOR da(s) coluna(s)
    de medida — verde quando o valor atende ao mínimo exigido daquele critério
    específico, vermelho quando reprova. ``destaques`` mapeia nome da coluna a
    uma lista (uma entrada por linha, mesma ordem de ``dados``) com "ok" /
    "falha" / ``None`` (sem medida — sem destaque). Necessário porque um
    ambiente pode reprovar em um critério (ex.: largura) e atender a outro
    (ex.: área) na mesma linha — destacar a linha inteira esconderia qual dos
    dois valores é o problema.
    """
    if not dados:
        return
    try:
        import pandas as pd
        df = pd.DataFrame(dados)
        try:
            def _cor_serie(serie, estados):
                cores = {"ok": f"background-color: {_COR_OK}",
                         "falha": f"background-color: {_COR_FALHA}"}
                return [cores.get(e, "") for e in estados]

            objeto = df.style
            for coluna, estados in destaques.items():
                if coluna not in df.columns:
                    continue
                objeto = objeto.apply(
                    lambda serie, estados=estados: _cor_serie(serie, estados),
                    subset=[coluna],
                )
        except Exception:
            objeto = df
        st.dataframe(objeto, hide_index=True, use_container_width=True)
    except Exception:
        st.dataframe(dados, hide_index=True, use_container_width=True)


def painel_ambientes_resumo(detalhe: dict) -> None:
    """Resumo da análise de ambientes: contagem, cobertura do programa e tabela."""
    amb = (detalhe or {}).get("ambientes") or []
    total = (detalhe or {}).get("total_ambientes", len(amb))
    st.metric("Ambientes encontrados", total)

    # Veredito sem caixa de cor (ADR-034 (c)): o estado já está no card; aqui
    # só o que falta, em texto. A normalização por UH vai para a faixa.
    if not detalhe.get("atende_programa"):
        faltantes = detalhe.get("faltantes") or []
        st.markdown("**Faltam no programa:** " + (", ".join(faltantes) or "—"))

    categorias = detalhe.get("categorias") or []
    if categorias:
        nome_por_gid = {a.get("global_id"): a.get("nome", "") for a in amb}
        st.markdown("**Cobertura do programa**")
        st.dataframe(
            [{"Categoria": c.get("rotulo", ""), "Exigido": c.get("min", 1),
              "Encontrados": c.get("qtd", 0), "Atende": "sim" if c.get("atende") else "não",
              "Ambiente(s) correspondente(s)":
                  ", ".join(nome_por_gid.get(g, g) for g in (c.get("global_ids") or [])) or "—"}
             for c in categorias],
            hide_index=True, use_container_width=True,
        )

    st.markdown("**Ambientes do modelo**")
    dados = [{"Ambiente": a.get("nome", ""), "Categoria": a.get("categoria_rotulo") or "—",
              "Área (m²)": _fmt_area(a.get("area_m2"))} for a in amb]
    matches = [bool(a.get("categoria")) for a in amb]
    _tabela_ambientes(dados, matches)
    if any(matches):
        st.caption("🟩 Linhas destacadas: ambiente com correspondência no programa "
                   "de necessidades (revise a classificação nos casos duvidosos).")


def painel_ambientes_atributos(detalhe: dict) -> None:
    """Atributos IFC extraídos por ambiente — inclui a FONTE da área (transparência)."""
    amb = (detalhe or {}).get("ambientes") or []
    if not amb:
        st.caption("Nenhum ambiente extraído do modelo.")
        return
    dados = [{"GlobalId": a.get("global_id", ""), "Classe IFC": a.get("classe_ifc") or "—",
              "Name": a.get("name") or "—",
              "LongName": a.get("long_name") or "—", "Descrição": a.get("descricao") or "—",
              "Área (m²)": _fmt_area(a.get("area_m2")), "Fonte da área": a.get("fonte_area") or "—",
              "Termo casado": a.get("termo_casado") or "—"} for a in amb]
    matches = [bool(a.get("categoria")) for a in amb]
    _tabela_ambientes(dados, matches)
    st.caption("🟩 Linhas destacadas: ambiente com correspondência no programa. "
               "*Classe IFC*: classe do elemento do modelo do qual os atributos foram "
               "extraídos (ex.: IfcSpace). *Fonte da área*: qual quantidade IFC forneceu "
               "a área (ex.: NetFloorArea, GrossFloorArea). *Termo casado*: trecho do "
               "nome que classificou o ambiente.")


def painel_areas_uh(detalhe: dict) -> None:
    """Resumo da consolidação de área útil da UH (EDI-001/002)."""
    total = detalhe.get("area_util_total", 0.0)
    minimo = detalhe.get("area_min")
    sem = detalhe.get("ambientes_sem_area") or []

    num_uhs = detalhe.get("num_uhs", 1)
    principal_min = detalhe.get("area_principal_min")
    dois_limites = minimo is not None and principal_min is not None
    if minimo is not None:
        st.metric("Área útil com varanda" if dois_limites else "Área útil consolidada",
                  f"{total:.2f} m²", delta=f"{total - minimo:+.2f} m² vs. mínimo")
        if dois_limites:
            # Dois limites no mesmo dispositivo (Anexo III, 2.I.a.ii): cada
            # legenda diz o que soma e qual é o seu mínimo.
            st.caption(f"O **mínimo exigido** é de {minimo:.2f} m²"
                       + (f" ({num_uhs} UH × {minimo / num_uhs:.2f} m²)"
                          if num_uhs and num_uhs > 1 else "")
                       + ", somando todos os ambientes, varanda incluída."
                       + (" O valor é normalizado pelo número de UHs declarado e a "
                          "soma é validada em agregado, sem separar cada UH."
                          if num_uhs and num_uhs > 1 else ""))
        elif num_uhs and num_uhs > 1:
            st.caption(f"Mínimo exigido: {minimo:.2f} m² ({num_uhs} UH × "
                       f"{minimo / num_uhs:.2f} m² — normalizado pelo nº de UHs "
                       "declarado; valida em agregado, não separa cada UH).")
        else:
            st.caption(f"Mínimo exigido: {minimo:.2f} m².")
        # Sem caixa de cor (ADR-034 (c)): o veredito está no card.
        if total >= minimo:
            st.markdown(f"Área útil {total:.2f} m² ≥ {minimo:.2f} m²." +
                        (f" ({len(sem)} ambiente(s) sem área, não somados.)"
                         if sem else ""))
        elif sem:
            st.markdown(f"{total:.2f} m² < {minimo:.2f} m², mas {len(sem)} "
                        "ambiente(s) sem área declarada — a soma pode estar "
                        "subestimada.")
        else:
            st.markdown(f"Área útil {total:.2f} m² < {minimo:.2f} m².")
    else:
        st.metric("Área útil consolidada", f"{total:.2f} m²")

    if dois_limites:
        # Segundo limite do mesmo dispositivo (Anexo III, 2.I.a.ii).
        principal = detalhe.get("area_principal", 0.0)
        varanda = detalhe.get("area_varanda", 0.0)
        st.metric("Área principal, sem varanda", f"{principal:.2f} m²",
                  delta=f"{principal - principal_min:+.2f} m² vs. mínimo")
        st.caption(f"O **mínimo exigido** é de {principal_min:.2f} m²"
                   + (f" ({num_uhs} UH × {principal_min / num_uhs:.2f} m²)"
                      if num_uhs and num_uhs > 1 else "")
                   + ", somando os ambientes que não são varanda. A varanda, com "
                   f"{varanda:.2f} m², fica de fora desta soma. Os dois limites "
                   "valem juntos, e a regra só é atendida quando os dois são.")
        if principal >= principal_min:
            st.markdown(f"Área principal {principal:.2f} m² ≥ {principal_min:.2f} m².")
        elif sem:
            st.markdown(f"Área principal {principal:.2f} m² < {principal_min:.2f} m², "
                        "mas há ambiente(s) sem área declarada, então a soma pode "
                        "estar subestimada.")
        else:
            st.markdown(f"Área principal {principal:.2f} m² < {principal_min:.2f} m².")

    if sem:
        st.caption("Sem área declarada (" + str(len(sem)) + "): " +
                   ", ".join(sem[:8]) + (" …" if len(sem) > 8 else ""))

    cats = detalhe.get("area_por_categoria") or []
    if cats:
        st.markdown("**Área por categoria**")
        st.dataframe(
            [{"Categoria": c.get("rotulo", ""), "Área (m²)": _fmt_area(c.get("area_m2"))}
             for c in cats],
            hide_index=True, use_container_width=True,
        )


def painel_larguras(detalhe: dict, incluir_localizacao: bool = True) -> None:
    """Larguras mínimas (EDI-007/008/009/011): tabela por ambiente + método.

    Destaque POR VALOR (não por linha inteira): a célula da dimensão medida
    fica verde quando atende ao mínimo daquele critério específico e vermelha
    quando reprova — necessário porque a varanda (EDI-011) tem DOIS critérios
    (largura e área) e um ambiente pode reprovar em só um deles.
    """
    amb = (detalhe or {}).get("ambientes") or []
    minimo = detalhe.get("largura_min_m")
    area_min = detalhe.get("area_min_m2")  # presente só na varanda (EDI-011)
    if not amb:
        st.caption("Nenhum ambiente da categoria identificado no modelo.")
        return

    def _fmt(v, casas=2):
        return f"{v:.{casas}f}" if isinstance(v, (int, float)) and not isinstance(v, bool) else "—"

    def _estado(v, limite):
        """"ok"/"falha" comparando o valor medido ao mínimo; None se sem medida."""
        if limite is None or not isinstance(v, (int, float)) or isinstance(v, bool):
            return None
        return "ok" if v >= limite else "falha"

    dados: list[dict] = []
    destaque_largura: list[str | None] = []
    destaque_area: list[str | None] = []
    for a in amb:
        linha = {
            "Ambiente": a.get("nome", ""),
            "Largura (m)": _fmt(a.get("largura_m")),
            "Comprimento (m)": _fmt(a.get("comprimento_m")),
        }
        destaque_largura.append(_estado(a.get("largura_m"), minimo))
        if area_min is not None:
            linha["Área avaliada (m²)"] = _fmt(a.get("area_avaliada_m2"))
            linha["Fonte da área"] = a.get("fonte_area_avaliada") or "—"
            destaque_area.append(_estado(a.get("area_avaliada_m2"), area_min))
        atende = a.get("atende")
        linha["Atende"] = "sim" if atende else ("não" if atende is False else "sem medida")
        if a.get("erro"):
            linha["Observação"] = a["erro"]
        dados.append(linha)

    destaques = {"Largura (m)": destaque_largura}
    if area_min is not None:
        destaques["Área avaliada (m²)"] = destaque_area
    _tabela_com_destaque_dimensao(dados, destaques)
    st.caption("Verde: o valor atende ao mínimo daquele critério. Vermelho: "
               "abaixo do mínimo. O destaque fica na dimensão, não na linha.")

    exigido = f"largura ≥ {minimo:.2f} m" if minimo is not None else ""
    if area_min is not None:
        exigido += f" e área ≥ {area_min:.2f} m²"
    if exigido:
        st.caption(f"Exigido por ambiente: {exigido}.")
    if detalhe.get("metodo"):
        st.caption(f"Método de medição: {detalhe['metodo']}. Em plantas não "
                   "retangulares (ex.: em 'L'), o envelope pode superestimar a largura.")


# ---------------------------------------------------------------------------
# Regras de distância a equipamento (ENQ-009, ENQ-010.1, ENQ-011.1)
# ---------------------------------------------------------------------------

# Tons claros para fundo de célula (par dos saturados de ``app.componentes.mapa``): a
# tabela é texto sobre cor, o mapa é cor sobre mapa — o mesmo código nos dois
# lugares tornaria um dos dois ilegível.
_COR_CLASSIF_CELULA = {
    "atende_provado": "#d9f0d9",
    "dentro_do_piso": "#fdecc8",
    "fora_provado": "#fbdad9",
    "nao_medida": "#eceff1",
}


def _fmt_metros(v) -> str:
    return f"{v:,.0f}".replace(",", ".") if isinstance(v, (int, float)) else "—"


def _frase_descartes(filtragem: dict) -> str:
    """Motivos de descarte por extenso, do mais frequente ao menos."""
    from app.servicos.territorio import equipamentos as eq

    por_motivo = (filtragem or {}).get("por_motivo") or {}
    if not por_motivo:
        return ""
    return ", ".join(f"{n} por {eq.ROTULO_DESCARTE.get(m, m)}"
                     for m, n in sorted(por_motivo.items(), key=lambda kv: -kv[1]))


def painel_enq_resumo(detalhe: dict, r: dict | None = None) -> None:
    """Resumo indicativo da análise de distância a equipamento.

    Descreve o MÉTODO que foi de fato executado, e não uma paráfrase dele. A
    distinção importa e não é preciosismo: dizer "foram buscadas escolas num
    raio de X m" descreveria o pré-filtro do roteamento como se fosse o conjunto
    avaliado — foi exatamente esse mal-entendido que produziu o defeito do R5a
    (terreno rural saindo "inconclusivo" quando todos estavam demonstravelmente
    além do limiar). O conjunto inteiro é medido; o raio só escolhe quem iria à
    rede.
    """
    from app.servicos import roteamento as rot

    detalhe = detalhe or {}
    filtragem = detalhe.get("filtragem") or {}
    municipio = detalhe.get("municipio") or {}
    linhas = detalhe.get("equipamentos") or []
    limiar = detalhe.get("limiar_m") or 0.0
    raio = detalhe.get("raio_de_busca_m") or 0.0

    # Mínimo calculado, NÃO o primeiro da lista: a tabela é
    # ordenada pela linha reta, e o menor em linha reta pode não ser o menor em
    # rede. Depender da ordem aqui faria a frase "o mais próximo é X" apontar para
    # outro equipamento que o do veredito, em silêncio.
    medidos = [linha for linha in linhas if linha.get("metros") is not None]
    mais_proxima = min(medidos, key=lambda linha: linha["metros"]) if medidos else None

    c1, c2, c3 = st.columns(3)
    c1.metric("Considerados", filtragem.get("aceitos", len(linhas)))
    c2.metric("Mais próximo",
              f"{_fmt_metros(mais_proxima['metros'])} m" if mais_proxima else "—")
    c3.metric("Limiar do requisito", f"{_fmt_metros(limiar)} m")

    onde = "/".join(x for x in (municipio.get("nome"), municipio.get("uf")) if x)
    descartes = _frase_descartes(filtragem)
    st.markdown(
        f"O recorte de **{onde or 'município'}** traz "
        f"**{filtragem.get('total', 0)}** estabelecimento(s) de educação. Para "
        f"**{detalhe.get('rotulo_ciclo', '')}**, "
        f"**{filtragem.get('aceitos', 0)}** foi(ram) considerado(s) — "
        f"{detalhe.get('criterio_aceite', '')} — e "
        f"**{filtragem.get('descartados', 0)}** descartado(s)"
        + (f": {descartes}." if descartes else "."))

    metrica = rot.ROTULO_METRICA.get(
        (mais_proxima or {}).get("metrica"), "distância em linha reta (piso)")
    st.markdown(
        f"Todos os **{filtragem.get('aceitos', 0)}** considerados foram medidos "
        f"a partir do **centro do terreno** — {metrica}. "
        + _frase_do_raio(raio, detalhe.get("candidatos_para_roteamento", 0))
        + (f" O mais próximo é **{mais_proxima.get('nome', '')}**, a "
           f"**{_fmt_metros(mais_proxima['metros'])} m**." if mais_proxima else ""))

    if r and r.get("mensagem"):
        st.info(r["mensagem"], icon=":material/gavel:")

    _suspeitas_do_insumo(detalhe)


def _frase_do_raio(raio: float, quantos: int) -> str:
    """O raio de pré-seleção em linguagem do usuário (ADR-034, U3): quantos
    seguem para a distância caminhável e por que o raio não é critério."""
    r = _fmt_metros(raio)
    if quantos == 1:
        abertura = (f"Nesta análise, **1** equipamento está a até **{r} m** do "
                    "terreno e segue")
    elif quantos:
        abertura = (f"Nesta análise, **{quantos}** equipamentos estão a até "
                    f"**{r} m** do terreno e seguem")
    else:
        abertura = (f"Nesta análise, nenhum equipamento está a até **{r} m** do "
                    "terreno para seguir")
    return (abertura + " para a verificação da distância caminhável. A "
            f"distância de {r} m não vem do requisito da Portaria: é apenas uma "
            "forma de restringir o conjunto de equipamentos cuja distância "
            "caminhável é verificada.")


def painel_enq_consulta(detalhe: dict) -> None:
    """Informação de segundo plano, junto da legenda (ADR-034): de onde as
    medidas partiram, a procedência do recorte e as verificações da base que
    não puderam ser feitas. Material de auditoria, lido quando o olho volta
    com uma dúvida — não na primeira passada."""
    _origem_da_medida(detalhe)
    _procedencia_do_recorte(detalhe)
    _sinais_nao_verificados(detalhe)


def _origem_da_medida(detalhe: dict) -> None:
    """A coordenada de onde toda medida da tela partiu.

    Ela já viajava no ``detalhe`` desde o R5d e não aparecia em lugar nenhum. É a
    origem de todas as distâncias exibidas: sem ela, quem audita não tem como
    refazer um número por fora da ferramenta — e refazer por fora é exatamente o
    que um analista faz quando desconfia do resultado.
    """
    terreno = (detalhe or {}).get("terreno") or {}
    centro = terreno.get("centro_wgs84") or {}
    lat, lon = centro.get("lat"), centro.get("lon")
    if lat is None or lon is None:
        return

    origem = terreno.get("origem") or "—"
    nivel = terreno.get("nivel") or "—"
    area = terreno.get("area_m2")
    partes = [f"**Origem das medidas:** `{lat:.6f}, {lon:.6f}`",
              f"terreno por *{origem}*, nível *{nivel}*"]
    if area:
        partes.append(f"área {area:,.0f} m²".replace(",", "."))
    if terreno.get("crs_metrico"):
        partes.append(f"CRS métrico {terreno['crs_metrico']}")
    st.caption(" · ".join(partes)
               + ". Copie a coordenada para conferir qualquer distância por fora.")


def _suspeitas_do_insumo(detalhe: dict) -> None:
    """Suspeitas sobre a base de equipamentos: afetam a leitura do resultado,
    então ficam junto dele."""
    from app.servicos.territorio import equipamentos as eq

    for s in detalhe.get("suspeitas") or []:
        classe = eq.ROTULO_CLASSE_SUSPEITA.get(s.get("classe"), "")
        st.warning(f"**{classe or 'Suspeita do insumo'}** — {s.get('mensagem','')}",
                   icon=":material/warning:")


def _sinais_nao_verificados(detalhe: dict) -> None:
    """Verificações de qualidade da base que não puderam ser feitas.

    Declaradas porque *não verificado* não é o mesmo que *não disparou* —
    confundir os dois transforma ausência de checagem em aparência de
    aprovação. Não mudam o veredito; por isso moram na consulta."""
    nao_verificados = detalhe.get("sinais_nao_verificados") or {}
    if not nao_verificados:
        return
    with st.expander(f"Verificações da base de equipamentos não realizadas "
                     f"({len(nao_verificados)})", icon=":material/help:"):
        st.caption("Conferências automáticas da qualidade do cadastro que não "
                   "puderam rodar nesta análise. Não alteram o resultado, mas "
                   "também não atestam que o cadastro esteja correto.")
        for codigo, razao in nao_verificados.items():
            st.markdown(f"- {razao} (`{codigo}`)")


def _procedencia_do_recorte(detalhe: dict) -> None:
    proc = detalhe.get("procedencia_recorte") or {}
    if proc:
        fontes = ", ".join(f for f in (proc.get("fontes") or []) if f)
        st.caption(
            f"Recorte de equipamentos: Censo Escolar {proc.get('ano_censo', '—')}"
            + (f", gerado em {proc.get('gerado_em')}" if proc.get("gerado_em") else "")
            + (f" · fontes: {fontes}" if fontes else ""))


def painel_enq_equipamentos(detalhe: dict) -> None:
    """Tabela dos equipamentos avaliados + os descartados dentro do raio."""
    from app.servicos import roteamento as rot

    linhas = (detalhe or {}).get("equipamentos") or []
    if not linhas:
        st.info("Nenhum equipamento do ciclo exigido restou para medir — o "
                "resultado se explica pelo insumo, não pela distância.",
                icon=":material/inbox:")
        _tabela_descartados(detalhe)
        return

    dados, estados = [], []
    for linha in linhas:
        classificacao = linha.get("classificacao") or rot.CLASSIF_NAO_MEDIDA
        estados.append(classificacao)
        dados.append({
            "Equipamento": ("★ " if linha.get("determinante") else "")
                           + (linha.get("nome") or ""),
            "INEP": linha.get("codigo_inep") or "—",
            "Rede": linha.get("rede") or "—",
            # As DUAS leituras do mesmo par: é a comparação que deixa o desvio da
            # malha viária visível, e é o que o analista olha primeiro ao
            # desconfiar de um número. A coluna "Distância (m)" segue sendo a que
            # DECIDE — as outras duas são leitura, não veredito.
            "Linha reta (m)": (round(linha["metros_linha_reta"])
                               if linha.get("metros_linha_reta") is not None
                               else None),
            "Em rede (m)": (round(linha["metros_rede"])
                            if linha.get("metros_rede") is not None else None),
            "Distância (m)": (round(linha["metros"])
                              if linha.get("metros") is not None else None),
            "Frente ao limiar": rot.ROTULO_CLASSIFICACAO.get(classificacao,
                                                             classificacao),
            # Já viajava no `detalhe` e a tela não usava. É o que
            # falta na mão de quem desconfia de um número e vai conferir a escola
            # por fora — e só cabe porque a tabela passou à largura inteira.
            "Endereço": linha.get("endereco") or "—",
            "Fonte": linha.get("fonte") or "—",
        })

    _tabela_por_classificacao(dados, estados)
    st.caption(
        "★ marca o equipamento determinante — aquele cuja medida sustenta o "
        "veredito. **Linha reta** é o piso geodésico, medido para todos; **em "
        "rede** é a distância caminhável, medida só para quem entrou no raio de "
        "pré-seleção. **Distância** é a que decidiu: a de rede quando existe, o "
        "piso quando não. Ordenação e filtro por coluna são nativos da tabela.")
    _tabela_descartados(detalhe)


def _formato_inteiro(*colunas: str) -> dict:
    """``column_config`` que exibe metros como inteiro, sem casas decimais.

    Uma coluna de metros que tenha ``None`` — quem não foi ao roteamento em rede —
    vira ``float64`` no pandas, e o Streamlit a renderiza com a precisão do tipo:
    seis casas decimais de precisão espúria num número que a regra já arredondou.

    Degrada para ``{}`` se a versão do Streamlit não tiver ``column_config``: a
    tabela sai sem o formato, em vez de o painel inteiro estourar.
    """
    try:
        return {coluna: st.column_config.NumberColumn(coluna, format="%d")
                for coluna in colunas}
    except Exception:                                    # noqa: BLE001
        return {}


def _tabela_por_classificacao(dados: list[dict], estados: list[str]) -> None:
    """Tabela interativa com a célula de distância colorida pela classificação.

    Destaque POR CÉLULA (mesmo princípio de ``_tabela_com_destaque_dimensao``):
    o que está sendo julgado é a DISTÂNCIA, não o estabelecimento. Pintar a
    linha inteira sugeriria um juízo sobre a escola.
    """
    colunas = ["Distância (m)", "Frente ao limiar"]
    formato_metros = _formato_inteiro("Linha reta (m)", "Em rede (m)",
                                      "Distância (m)")
    try:
        import pandas as pd
        df = pd.DataFrame(dados)
        try:
            def _cor_serie(serie, estados=estados):
                return [f"background-color: {_COR_CLASSIF_CELULA[e]}"
                        if e in _COR_CLASSIF_CELULA else "" for e in estados]

            objeto = df.style
            for coluna in colunas:
                if coluna in df.columns:
                    objeto = objeto.apply(_cor_serie, subset=[coluna])
        except Exception:
            objeto = df                       # sem jinja2: interativa, sem cor
        st.dataframe(objeto, hide_index=True, use_container_width=True,
                     column_config=formato_metros, **_altura_de_tabela(len(dados)))
    except Exception:
        st.dataframe(dados, hide_index=True, use_container_width=True,
                     column_config=formato_metros, **_altura_de_tabela(len(dados)))


def _altura_de_tabela(linhas: int) -> dict:
    """Tabela longa ganha altura fixa (ADR-034 (b)); curta fica no tamanho do
    conteúdo, sem área vazia embaixo."""
    from app.componentes.layout import ALTURA_TABELA
    return {"height": ALTURA_TABELA} if linhas > LINHAS_TABELA_CURTA else {}


LINHAS_TABELA_CURTA = 8


def _tabela_descartados(detalhe: dict) -> None:
    """Descartados dentro do raio: a resposta a *"e aquela escola ali?"*."""
    descartados = (detalhe or {}).get("descartados_no_raio") or []
    if not descartados:
        return
    raio = (detalhe or {}).get("raio_de_busca_m") or 0.0
    with st.expander(f"Equipamentos descartados dentro do raio "
                     f"({len(descartados)})", icon=":material/filter_alt_off:"):
        st.caption(
            f"Estão a menos de {_fmt_metros(raio)} m do terreno, mas não entram "
            "na avaliação. O descarte é contabilizado e nomeado, nunca "
            "silencioso: um não-conforme cuja escola mais próxima foi excluída "
            "precisa ser auditável.")
        st.dataframe(
            [{"Equipamento": linha.get("nome") or "",
              "INEP": linha.get("codigo_inep") or "—",
              "Distância (m)": round(linha.get("metros") or 0),
              "Motivo do descarte": linha.get("rotulo_motivo") or linha.get("motivo"),
              "Rede": linha.get("rede") or "—",
              "Situação": linha.get("situacao") or "—"}
             for linha in descartados],
            hide_index=True, use_container_width=True)


def painel_enq_completo(detalhe: dict, r: dict | None = None) -> None:
    """Resumo + tabela — usado pelo relatório e pelo painel genérico."""
    painel_enq_resumo(detalhe, r)
    st.markdown("##### Equipamentos avaliados")
    painel_enq_equipamentos(detalhe)
    painel_enq_consulta(detalhe)


# ---------------------------------------------------------------------------
# Agregação (requisito-pai) e remessa (alternativa não automatizável)
# ---------------------------------------------------------------------------

def painel_agregacao(detalhe: dict) -> None:
    """Como o requisito-pai decidiu: o intervalo, os membros e o teto.

    Tudo vem do ``detalhe`` produzido por ``core/motor/agregacao.py`` — nada é
    recalculado aqui. Recalcular abriria a porta para a tela discordar da regra,
    que é o defeito que a classificação de quatro valores do R5d existe para não
    cometer.
    """
    detalhe = detalhe or {}
    membros = detalhe.get("membros") or []
    k = detalhe.get("k", 1)
    n_conf = detalhe.get("n_conf", 0)
    n_pot = detalhe.get("n_pot", 0)
    total = detalhe.get("total_membros", len(membros))
    rotulo = detalhe.get("rotulo_membro", "alternativa(s)")

    c1, c2, c3 = st.columns(3)
    c1.metric("Confirmadas", f"{n_conf} de {total}",
              help="Alternativas avaliadas e conformes.")
    c2.metric("No melhor cenário", f"{n_pot} de {total}",
              help="Confirmadas somadas às que ainda podem atender — o limite "
                   "superior do que o insumo disponível permite.")
    c3.metric("Mínimo exigido", k, help=detalhe.get("rotulo_modo", ""))

    if n_conf >= k:
        st.success(f"O critério da Portaria é satisfeito por **qualquer** das "
                   f"{total} {rotulo}, e {n_conf} foi(ram) confirmada(s).",
                   icon=":material/check_circle:")
    elif n_pot < k:
        st.error(f"Nem no melhor cenário o mínimo de {k} é alcançado.",
                 icon=":material/cancel:")
    else:
        st.warning(
            f"O intervalo vai de **{n_conf} a {n_pot}** de {total} {rotulo}, "
            f"contra o mínimo de **{k}** — e não decide. O que falta está na "
            "tabela abaixo, alternativa por alternativa.",
            icon=":material/help:")

    st.markdown("##### Alternativas do requisito")
    st.dataframe(
        [{"Alternativa": m.get("id", ""),
          "Situação": ROTULO_ESTADO.get(m.get("estado"), m.get("estado") or "—"),
          "Entra na conta como": m.get("rotulo_conta") or "—",
          "O que falta": m.get("rotulo_motivo") or "—",
          "Descrição": m.get("descricao") or ""}
         for m in membros],
        hide_index=True, use_container_width=True)

    # As ações só aparecem quando ainda há o que destravar. Num requisito já
    # conforme, "encaminhar ao parecer do analista" sugeriria trabalho pendente
    # que a Portaria não pede: uma alternativa basta, e ela foi confirmada.
    if n_conf < k:
        for acao in sorted({m.get("acao") for m in membros if m.get("acao")
                            and m.get("conta_para") != CONTA_CONFIRMADO}):
            st.caption(f"**O que destrava:** {acao}")

    _teto_de_reprovabilidade(detalhe)


def _teto_de_reprovabilidade(detalhe: dict) -> None:
    """A frase do §7.1 do recorte, quando o requisito não pode ser reprovado.

    Aparece **sempre** que o teto existe, inclusive num requisito conforme: o
    leitor precisa saber que a aprovação é legítima e que a reprovação não estava
    disponível — são coisas diferentes, e omitir a segunda faria a primeira
    parecer mais forte do que é.
    """
    repro = (detalhe or {}).get("reprovabilidade") or {}
    if repro.get("reprovavel", True):
        return
    irredutiveis = ", ".join(repro.get("membros_irredutiveis") or [])
    st.info(
        f"**Limite declarado desta verificação.** {repro.get('explicacao', '')}"
        + (f" Alternativa(s) permanentemente em aberto: {irredutiveis}."
           if irredutiveis else ""),
        icon=":material/info:")


def painel_remetida(detalhe: dict) -> None:
    """A alternativa que o protótipo não avalia — dita sem rodeio.

    O vocabulário é deliberado: **remetida a parecer**, nunca "pendente" nem "em
    implementação". As duas palavras prometem uma versão futura que não vem, e o
    insumo desta alternativa não é dado público.
    """
    detalhe = detalhe or {}
    st.warning("**Esta alternativa não é avaliada por este protótipo.** "
               + (detalhe.get("porque") or ""),
               icon=":material/gavel:")
    linhas = [("Insumo que a avaliação exigiria", detalhe.get("insumo")),
              ("Encaminhamento", detalhe.get("rotulo_remessa")),
              ("O que fazer", detalhe.get("acao")),
              ("Fundamento normativo", detalhe.get("fundamento"))]
    st.markdown("\n".join(f"- **{titulo}:** {valor}"
                          for titulo, valor in linhas if valor))


def _render_distancia_equipamento(detalhe: dict,
                                  incluir_localizacao: bool = True) -> None:
    painel_enq_completo(detalhe)


RENDERIZADORES = {"logeoref": _render_logeoref, "larguras": painel_larguras,
                  "distancia_equipamento": _render_distancia_equipamento}


def render_detalhe(detalhe: dict, incluir_localizacao: bool = True) -> None:
    fn = RENDERIZADORES.get((detalhe or {}).get("tipo"))
    if fn:
        fn(detalhe, incluir_localizacao)


def par_esperado_encontrado(r: dict) -> None:
    """Confronto 'Esperado × Encontrado' em fonte de leitura (não st.metric).

    O ``st.metric`` usa fonte grande e trunca textos longos (ex.: "menor
    largura medida: 2.62 m"); aqui o valor quebra linha normalmente. Uso
    uniforme em todos os requisitos (painel genérico e relatório consolidado).
    """
    ve, vf = r.get("valor_esperado"), r.get("valor_encontrado")
    if ve is None and vf is None:
        return
    c1, c2 = st.columns(2)
    for coluna, rotulo_col, valor in ((c1, "Esperado", ve), (c2, "Encontrado", vf)):
        coluna.markdown(
            f"<div style='font-size:.78rem;color:#5B6770'>{rotulo_col}</div>"
            f"<div style='font-size:1.02rem;font-weight:600;line-height:1.35'>"
            f"{valor if valor is not None else '—'}</div>",
            unsafe_allow_html=True,
        )


def painel_requisito(r: dict, incluir_localizacao: bool = True) -> None:
    """Painel reutilizável com o resultado de checagem de um requisito."""
    estado = r.get("estado", "")
    cor = COR_ESTADO.get(estado, "#888")
    st.markdown(
        f"### {r.get('requisito','')} "
        f"<span style='color:{cor}'>· {ROTULO_ESTADO.get(estado, estado)}</span>",
        unsafe_allow_html=True,
    )
    if r.get("descricao"):
        st.caption(r["descricao"])
    if r.get("mensagem"):
        st.write(r["mensagem"])
    par_esperado_encontrado(r)
    render_detalhe(r.get("detalhe") or {}, incluir_localizacao)
    with st.expander("Dados brutos (JSON)"):
        st.json(r)
