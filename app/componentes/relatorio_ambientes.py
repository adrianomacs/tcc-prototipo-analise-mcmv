"""Relatório de uma regra do Programa de necessidades — os textos puros
(ADR-034). Cada regra do grupo (EDI-004, EDI-004.1, EDI-001, EDI-002,
EDI-007, EDI-008, EDI-009, EDI-011) tem relatório próprio em
``app/paginas/relatorios/relatorio.py``; aqui ficam os textos e as tabelas
que todas elas compartilham, lidos do ``detalhe`` da própria regra."""

from __future__ import annotations

from app.componentes.avisos import ALERTA, Aviso

# Frase de contexto (ADR-034 (e)): ambiente/IfcSpace não tem fonte na lista
# de referências — frase sem citação.
CONTEXTO_AMBIENTES = (
    "Esta verificação lê os ambientes do modelo, os espaços que o projeto "
    "delimita e nomeia, como sala, cozinha e banheiro, e reconhece cada um "
    "pelo nome.")

TIPOS = ("ambientes", "areas_uh", "larguras")


def eh_ambientes(detalhe: dict) -> bool:
    """O relatório é de uma regra do Programa (lê os ambientes do modelo)."""
    return (detalhe or {}).get("tipo") in TIPOS


# Um aviso só na faixa (como na definição do terreno por IFC): várias caixas
# amarelas empurram o resultado para baixo e não dizem o que fazer. O porquê
# de cada ponto fica no expander "Por que este aviso" (ADR-034 (c)).
AVISO_GERAL = Aviso(
    ALERTA, "Há pontos de atenção sobre o alcance deste resultado.",
    "O modelo e as declarações trazem condições que limitam o que a "
    "verificação pode concluir.",
    "Leia os pontos abaixo antes de usar o resultado.")

SECAO_AMBIENTES_FORA = "Ambientes deixados de fora"


def ponto_normalizacao(num_uhs) -> str:
    """Mais de uma UH no modelo: as exigências são multiplicadas e comparadas
    ao total do modelo."""
    if not num_uhs or num_uhs <= 1:
        return ""
    return (f"**As exigências foram multiplicadas pelas {num_uhs} UHs que o "
            "modelo representa.** Cada cômodo e cada área mínima exigidos por "
            "UH são comparados ao total do modelo, supondo as unidades iguais: "
            "a verificação não separa uma UH da outra.")


def pontos_diagnosticos(meta: dict) -> list[str]:
    """Os diagnósticos marcados da análise (``meta.diagnosticos``), lidos do
    relatório gravado, sem recalcular."""
    return [f"**{d.get('rotulo', '')}.** {d.get('mensagem', '')}".strip()
            for d in (meta or {}).get("diagnosticos") or [] if d.get("marcado")]


def ambientes_fora(detalhe: dict) -> list[dict]:
    """Os ambientes que a triagem do extrator tirou da população (ADR-031),
    lidos do ``detalhe`` da própria regra — cada relatório mostra os seus."""
    return list((detalhe or {}).get("fora_da_populacao") or [])


def ponto_ambientes_fora(fora: list[dict]) -> str:
    if not fora:
        return ""
    return (f"**{len(fora)} ambiente(s) do modelo ficaram fora das "
            "verificações.** Eles parecem erro de exportação — caixas no "
            "tamanho padrão do exportador (6' × 8'), área incompatível com a "
            "planta ou vários ambientes no mesmo ponto — e contá-los "
            "distorceria o resultado. Para ver cada um "
            "(nome, GUID, motivo e dimensões) e retirá-los do modelo autoral, "
            f"consulte a seção \"{SECAO_AMBIENTES_FORA}\" no fim deste "
            "relatório.")


def pontos_de_atencao(detalhe: dict, meta: dict) -> list[str]:
    """Os pontos do expander "Por que este aviso", na ordem de leitura.

    A normalização por UH e os diagnósticos da análise só valem para as
    regras que consomem o número de UHs, as que gravam ``num_uhs`` no
    ``detalhe``; nas larguras eles não dizem nada sobre o resultado."""
    detalhe = detalhe or {}
    consome_uh = "num_uhs" in detalhe
    pontos = [ponto_normalizacao(detalhe.get("num_uhs")) if consome_uh else "",
              *(pontos_diagnosticos(meta) if consome_uh else []),
              ponto_ambientes_fora(ambientes_fora(detalhe))]
    return [p for p in pontos if p]


def _num(valor, casas=2):
    return round(float(valor), casas) if isinstance(valor, (int, float)) else None


def linhas_ambientes_fora(fora: list[dict]) -> list[dict]:
    """A tabela dos ambientes desconsiderados — para o proponente localizar
    cada um no modelo autoral pelo GUID."""
    linhas = []
    for a in fora or []:
        pav = ((a.get("valores") or {}).get("sobreposicao_no_pavimento") or {}) \
            .get("pavimento")
        causa = a.get("causa", "")
        linhas.append({
            "Ambiente": a.get("nome") or "—",
            "Pavimento": pav or "—",
            "GUID": a.get("global_id", ""),
            "Motivo": causa[:1].upper() + causa[1:],
            "Área declarada (m²)": _num(a.get("area_declarada_m2")),
            "Área da pegada (m²)": _num(a.get("area_footprint_m2")),
            "Largura (m)": _num(a.get("largura_m")),
            "Comprimento (m)": _num(a.get("comprimento_m")),
        })
    return linhas


def criterio(r: dict) -> str:
    """O "Exige" e o "Medido" do card, com os valores que a regra gravou."""
    from html import escape
    ve, vf = r.get("valor_esperado"), r.get("valor_encontrado")
    partes = []
    if ve:
        partes.append(f"<b>Exige:</b> {escape(str(ve))}")
    if vf:
        partes.append(f"<b>Medido:</b> {escape(str(vf))}")
    return ". ".join(partes) + ("." if partes else "")


# Resultado de cada elemento destacado na cena (a cor vem da cena3d). Três
# valores, como os três estados do ADR-006 vistos por elemento.
ATENDE, NAO_ATENDE, NEUTRO = "atende", "nao_atende", "neutro"

ROTULO_RESULTADO = {ATENDE: "atende", NAO_ATENDE: "não atende",
                    NEUTRO: "não avaliado"}


def resultado_por_ambiente(detalhe: dict, estado: str | None = None) -> dict[str, str]:
    """``{GlobalId: atende | nao_atende | neutro}`` lido do que a regra gravou.

    Nenhum campo novo no relatório (ADR-034): cada tipo de diagnóstico já
    diz, à sua maneira, como cada ambiente pesou no resultado.
    Nas larguras e na varanda, o ``atende`` de cada ambiente (``None`` é
    medida ausente). No programa, a categoria do ambiente atende ou não ao
    mínimo de quantidade, e o ambiente leva a cor dela; o que não pertence a
    nenhuma categoria da regra fica neutro. Na área útil a regra julga a
    soma e não cada ambiente, então todos os somados levam a cor do estado
    da regra, e o ambiente sem área, que não entrou na soma, fica neutro.
    """
    detalhe = detalhe or {}
    tipo = detalhe.get("tipo")
    ambientes_ = [a for a in detalhe.get("ambientes") or [] if a.get("global_id")]
    if tipo == "larguras":
        cor = {True: ATENDE, False: NAO_ATENDE}
        return {a["global_id"]: cor.get(a.get("atende"), NEUTRO) for a in ambientes_}
    if tipo == "ambientes":
        por_gid: dict[str, str] = {}
        for c in detalhe.get("categorias") or []:
            valor = ATENDE if c.get("atende") else NAO_ATENDE
            for gid in c.get("global_ids") or []:
                por_gid[gid] = valor
        return {a["global_id"]: por_gid.get(a["global_id"], NEUTRO) for a in ambientes_}
    if tipo == "areas_uh":
        conjunto = {"conforme": ATENDE, "nao_conforme": NAO_ATENDE}.get(estado, NEUTRO)
        return {a["global_id"]: (conjunto if _tem_area(a) else NEUTRO)
                for a in ambientes_}
    return {a["global_id"]: NEUTRO for a in ambientes_}


def _tem_area(ambiente: dict) -> bool:
    area = ambiente.get("area_m2")
    return isinstance(area, (int, float)) and not isinstance(area, bool)


def legenda_cena(detalhe: dict) -> str:
    """A frase sob a cena, conforme o que a regra carregou nela."""
    tipo = (detalhe or {}).get("tipo")
    if tipo == "larguras":
        rot = (detalhe.get("categoria_rotulo") or "da categoria").lower()
        return (f"A cena mostra só os ambientes de {rot} que esta regra mediu, "
                "cada um na cor do seu resultado. Clique num deles na lista "
                "para destacá-lo no modelo, ou destaque todos de uma vez.")
    if tipo == "areas_uh":
        return ("A cena mostra os ambientes cuja área entrou na soma. Como a "
                "regra julga a soma e não cada ambiente, todos levam a cor do "
                "resultado da regra. Clique num deles para destacá-lo, ou "
                "destaque todos de uma vez.")
    return ("A cena mostra os ambientes que esta regra conferiu contra o "
            "programa, cada um na cor da sua categoria, que atende ou não ao "
            "mínimo exigido. Clique num deles na lista para destacá-lo no "
            "modelo, ou destaque todos de uma vez.")
