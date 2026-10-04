"""Cobertura do Protótipo — 2.4.1: os números e o detalhe navegável.

Consolida os relatórios já gravados em disco por cada checagem
(`app.servicos.relatorios.relatorios_do_empreendimento_corrente`), sem
reprocessar nada: a tela se reproduz a partir do que está gravado (ADR-001).

Anatomia do ADR-034, como a de um relatório consolidado: título, "O que esta
página mostra", card do empreendimento, faixa de avisos (consolidado
parcial); os indicadores e o gráfico; a **análise por checagem** — um
expander por fase, com as contagens no título e a tabela de requisitos com
"Verificar relatório"; e, sob "Outras informações", a tabela por checagem e
os limites das análises. O texto descritivo (o parecer) é o papel do
Relatório de Checagem (2.4.2).
"""

import pandas as pd
import streamlit as st

from app.componentes import avisos
from app.componentes.cabecalho_empreendimento import cabecalho_empreendimento
from app.componentes.layout import ALTURA_TABELA, secao_outras_informacoes
from app.componentes.resultado import resultado_final
from app.navegacao.arvore import PAGINA_RESULTADOS
from app.servicos import empreendimento as emp_servico
from app.servicos import relatorios
from app.servicos.vereditos import _pct

# Mesmas chaves de `relatorios.CHECAGENS`, na mesma ordem (a da árvore de
# navegação) — o teste de 2.4.x prende a igualdade.
_ROTULOS = {
    "enquadramento": "Fase 1: Enquadramento",
    "qualificacao": "Qualificação Urbanística",
    "georref": "Georreferenciamento do Modelo",
    "programa": "Programa de Necessidades",
    "bim_gis": "Requisitos de Projeto (BIM + GIS)",
}


def _diagnosticos(encontrados: dict) -> None:
    """O que as análises não conseguiram dizer (ADR-023, D-K).

    Lidos dos relatórios GRAVADOS (`meta.diagnosticos`), sem recalcular nada —
    a mesma regra de ouro do resto da tela: ela se reproduz a partir do que
    está em disco. Só os que **marcaram**: os cinco são sempre calculados, mas
    uma lista com os cinco em toda checagem afogaria o que de fato aconteceu;
    quem quiser os não marcados os tem no relatório.

    Nenhum deles é veredito, e por isso ficam FORA das contagens acima — a
    separação visual é a decisão, não um detalhe de layout.

    A **cobertura do parque** (somar as várias análises para dizer que fatia do
    empreendimento já foi verificada) não entra aqui, e a D-K deixou a escolha
    para esta fase: somar coberturas de análises exige saber que elas falam de
    UH disjuntas, e nada no que está declarado hoje garante isso — duas
    análises da mesma unidade tipo somariam duas vezes. Enquanto a submissão
    não disser quais UH cada arquivo cobre, o número seria uma soma com
    aparência de medida. Fica para quando houver de onde tirá-lo.
    """
    marcados = [(chave, d) for chave in _ROTULOS
                for d in (encontrados.get(chave) or {}).get(
                    "meta", {}).get("diagnosticos", [])
                if d.get("marcado")]
    if not marcados:
        return

    # Em expander, sob "Outras informações" (ADR-034 (c)): não é veredito nem
    # contagem — é o alcance de cada resultado, material de consulta.
    with st.expander(f"Limites destas análises ({len(marcados)})",
                     icon=":material/info:"):
        st.caption("Não reprovam nenhum requisito nem entram nas contagens "
                   "acima: dizem por quantas UHs cada resultado fala e a "
                   "partir de quanto do modelo.")
        for chave, diagnostico in marcados:
            st.markdown(f"**{_ROTULOS[chave]}** — {diagnostico['rotulo']}  \n"
                        f"{diagnostico.get('mensagem') or ''}")


def _contagens(norm: dict) -> str:
    """ "1 conforme · 1 não conforme · 1 não avaliável" — só o que existe."""
    partes = [(norm.get("conforme", 0), "conforme"),
              (norm.get("nao_conforme", 0), "não conforme"),
              (norm.get("nao_avaliavel", 0), "não avaliável")]
    return " · ".join(f"{n} {rotulo}" for n, rotulo in partes if n) or "sem requisitos"


def _analise_por_checagem(encontrados: dict, emp) -> None:
    """Um expander por checagem executada, com as contagens no título para
    cruzar com os indicadores sem abrir; dentro, a tabela de requisitos com
    "Verificar relatório" (o mesmo componente das telas de checagem)."""
    st.markdown("##### Análise por checagem")
    for chave, rotulo in _ROTULOS.items():
        relatorio = encontrados.get(chave)
        if relatorio is None:
            continue
        norm = relatorio["resumo"]["normativo"]
        with st.expander(f"{rotulo} — {_contagens(norm)}",
                         icon=":material/fact_check:"):
            if not relatorio.get("por_requisito"):
                # Orientação discreta, e não caixa: a página já tem dados, e
                # uma caixa azul aqui leria como "nada foi executado".
                st.caption("Nenhum requisito registrado nesta análise.")
                continue
            resultado_final(chave, relatorio, PAGINA_RESULTADOS, emp,
                            com_metricas=False)


emp = emp_servico.carregar()

with st.expander("O que esta página mostra", icon=":material/info:"):
    st.write("Quanto dos requisitos da Portaria as checagens já executadas "
             "conseguiram avaliar para este empreendimento, e com que "
             "resultado: os indicadores somados, o gráfico por checagem e, "
             "abaixo, a análise de cada fase, com acesso ao relatório de cada "
             "requisito. **Capacidade de conclusão** é a parte dos requisitos aplicáveis que "
             "o insumo entregue permitiu avaliar; **conformidade**, a parte "
             "dos avaliados que atende à Portaria.")
cabecalho_empreendimento(emp)

encontrados = relatorios.relatorios_do_empreendimento_corrente()

if not encontrados:
    st.info(
        "Nenhuma checagem foi executada para este empreendimento ainda "
        "(ou os relatórios gravados são de uma versão anterior dele). Rode "
        "ao menos uma das checagens em “Checagens do Protótipo” "
        "para ver o índice aqui.",
        icon=":material/monitoring:")
else:
    consolidado = relatorios.consolidar(encontrados)
    faltantes = [rotulo for chave, rotulo in _ROTULOS.items()
                if chave not in encontrados]
    avisos.faixa_de_avisos([avisos.aviso_consolidado_parcial(faltantes)])

    c1, c2, c3 = st.columns(3)
    c1.metric("Capacidade de conclusão", _pct(consolidado["cobertura"]),
              help="Requisitos que foi possível avaliar (conformes e não "
                   "conformes) ÷ requisitos aplicáveis, somados sobre as "
                   "checagens executadas.")
    c2.metric("Conformidade", _pct(consolidado["conformidade"]),
              help="Conformes ÷ (conformes + não conformes), entre os "
                   "requisitos avaliados.")
    c3.metric("Requisitos avaliados",
              f"{consolidado['avaliados']}/{consolidado['total']}")

    linhas, indices = [], []
    for chave, rotulo in _ROTULOS.items():
        relatorio = encontrados.get(chave)
        if relatorio is None:
            continue
        norm = relatorio["resumo"]["normativo"]
        linhas.append({
            "Checagem": rotulo,
            "Conforme": norm.get("conforme", 0),
            "Não conforme": norm.get("nao_conforme", 0),
            "Não avaliável": norm.get("nao_avaliavel", 0),
        })
        indices.append({"Capacidade de conclusão": _pct(norm.get("cobertura")),
                        "Conformidade": _pct(norm.get("conformidade"))})

    df = pd.DataFrame(linhas).set_index("Checagem")
    st.markdown("##### Requisitos por checagem")
    st.bar_chart(df, color=["#34a853", "#ea4335", "#fbbc04"],
                horizontal=True)

    _analise_por_checagem(encontrados, emp)

    secao_outras_informacoes()
    with st.expander("Contagens e indicadores por checagem",
                     icon=":material/table_chart:"):
        st.dataframe(
            df.assign(Total=df.sum(axis=1),
                      **{"Capacidade de conclusão":
                         [i["Capacidade de conclusão"] for i in indices]},
                      Conformidade=[i["Conformidade"] for i in indices]),
            use_container_width=True,
            height=min(ALTURA_TABELA, 40 + 36 * len(df)))

    _diagnosticos(encontrados)
