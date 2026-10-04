"""Vocabulário de ambientes e verificação do programa mínimo de necessidades.

Faz a **correspondência nominal** entre os ambientes nomeados do modelo (IfcSpace)
e as categorias do programa mínimo da Portaria (EDI-004 / EDI-004.1). Como a
nomenclatura de projeto é livre, cada categoria reúne **variações prováveis** via
expressões regulares sobre o nome **normalizado** (minúsculas, sem acento,
pontuação colapsada) — o mesmo espírito de um filtro por regex numa checagem IDS.

Exemplos de variações cobertas: "Banheiro", "banheiro", "Sanitário", "sanitario",
"W.C.", "WC", "Lavabo"; "Dormitório", "Quarto", "Suíte", "Qto"; "Área de Serviço",
"Lavanderia", "A.S."; "Varanda", "Sacada", "Terraço".

Transparência: a classificação devolve o **termo que casou** em cada ambiente, de
modo que o relatório possa explicitar qual critério fez a correspondência.

Decisão de granularidade (nominal): a distinção entre "dormitório de casal" e
"dormitório para 2 pessoas" NÃO é inferível só pelo nome — é dimensional
(EDI-005/006). Assim, ambos são detectados pela categoria única ``dormitorio``, e
o programa exige a **quantidade** correspondente (2 dormitórios), derivada da
lista de ambientes exigidos da própria regra.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from typing import Any

# Mapeia cada item do programa (chave declarada na regra) à categoria nominal.
# Dois itens de dormitório recaem na mesma categoria -> exige 2 ocorrências.
MAPA_PROGRAMA = {
    "sala": "sala",
    "dormitorio_casal": "dormitorio",
    "dormitorio_2p": "dormitorio",
    "cozinha": "cozinha",
    "area_servico": "area_servico",
    "banheiro": "banheiro",
    "varanda": "varanda",
}

# Categorias nominais: rótulo legível + padrões (regex sobre o nome normalizado).
# A ordem define a prioridade de classificação (mais específicas primeiro).
CATEGORIAS: dict[str, dict[str, Any]] = {
    "banheiro": {
        "rotulo": "Banheiro",
        "padroes": [r"banheir", r"sanitari", r"\bw\s*c\b", r"lavab", r"toalet", r"\bbwc\b"],
    },
    "cozinha": {
        "rotulo": "Cozinha",
        "padroes": [r"cozinh", r"copa", r"kitchen"],
    },
    "area_servico": {
        "rotulo": "Área de serviço",
        "padroes": [r"area de servic", r"\bservic", r"lavanderia", r"\ba\s*s\b"],
    },
    "varanda": {
        "rotulo": "Varanda",
        "padroes": [r"varand", r"sacad", r"terrac", r"balcao", r"balcon"],
    },
    "dormitorio": {
        "rotulo": "Dormitório",
        "padroes": [r"dormit", r"\bdorm\b", r"quart", r"suite", r"\bqto\b"],
    },
    "sala": {
        "rotulo": "Sala",
        "padroes": [r"\bsala", r"\bestar\b", r"living", r"refeic", r"jantar"],
    },
}

# Ordem de prioridade na classificação (chave -> primeira que casar vence).
_ORDEM = ("banheiro", "cozinha", "area_servico", "varanda", "dormitorio", "sala")

# Padrões pré-compilados.
_COMPILADOS = {
    chave: [re.compile(p) for p in CATEGORIAS[chave]["padroes"]] for chave in CATEGORIAS
}


def rotulo(categoria: str) -> str:
    return CATEGORIAS.get(categoria, {}).get("rotulo", categoria)


def normalizar(nome: str | None) -> str:
    """Minúsculas, sem acentos, pontuação/hífens vira espaço, espaços colapsados."""
    if not nome:
        return ""
    s = unicodedata.normalize("NFKD", str(nome))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[^\w\s]", " ", s)   # pontuação -> espaço (W.C. -> "w c")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def classificar(nome: str | None) -> tuple[str | None, str | None, str | None]:
    """Classifica um nome de ambiente.

    Devolve ``(categoria, rotulo, termo_casado)`` da primeira categoria (na ordem
    de prioridade) cujo padrão casa com o nome normalizado; ``(None, None, None)``
    se nenhuma casar. ``termo_casado`` é o trecho efetivamente reconhecido — usado
    no relatório para explicitar o critério.
    """
    alvo = normalizar(nome)
    if not alvo:
        return None, None, None
    for chave in _ORDEM:
        for padrao in _COMPILADOS[chave]:
            m = padrao.search(alvo)
            if m:
                return chave, CATEGORIAS[chave]["rotulo"], m.group(0).strip()
    return None, None, None


def avaliar_programa(ambientes: list[Any], exigidos: list[str],
                     unidades_representadas: int = 1) -> dict:
    """Verifica a presença do programa mínimo a partir dos ambientes extraídos.

    ``ambientes`` são objetos com ``.global_id``, ``.nome`` e ``.to_dict()``
    (ver ``core.infra.ifc.extrator_ambientes.Ambiente``). ``exigidos`` é a lista de
    itens do programa declarada pela regra (ex.: ``parametro['ambientes_minimos']``).
    ``unidades_representadas`` é quantas UHs o contêiner em análise representa
    (ADR-021, ``ModeloBIM.unidades_representadas``); cada exigência é
    multiplicada por esse valor. Era o ``num_uhs`` das declarações até o
    ADR-021 tirar de lá o número — a aritmética é a mesma, o dono do número é
    que mudou.

    Normalização por UH: o modelo não
    traz uma separação espacial confiável entre UHs (os IFC de teste não usam
    ``IfcZone``/``IfcSpatialZone``; só ``IfcBuildingStorey``, que não serve para
    UHs lado a lado no mesmo pavimento). Em vez de agrupar ambientes por UH, a
    exigência de cada categoria é multiplicada por ``unidades_representadas`` e comparada à
    contagem total do modelo (ex.: 4 UHs × 1 cozinha = exige 4 cozinhas no
    total). **Limitação assumida**: valida a distribuição em agregado/uniforme
    entre as UHs — não garante que CADA UH individualmente tenha seu programa
    completo (uma UH deficiente pode ser compensada por outra superavitária).

    Devolve um diagnóstico ``tipo='ambientes'`` pronto para o ``detalhe`` da regra
    e para o relatório (contagens por categoria, faltantes e a lista de ambientes
    enriquecida com categoria, termo casado e a fonte da área). Inclui o número
    aplicado, sob a chave ``num_uhs`` — nome que o relatório e o painel já
    consomem, e que se troca quando se trocar o contrato deles, não aqui.
    """
    num_uhs = max(1, int(unidades_representadas or 1))
    requeridos = Counter(MAPA_PROGRAMA.get(k, k) for k in (exigidos or []))
    requeridos = Counter({cat: qtd * num_uhs for cat, qtd in requeridos.items()})

    enriquecidos: list[dict] = []
    por_categoria: dict[str, list] = defaultdict(list)
    for a in ambientes:
        chave, rot, termo = classificar(getattr(a, "nome", None))
        linha = a.to_dict() if hasattr(a, "to_dict") else dict(a)
        linha.update({"categoria": chave, "categoria_rotulo": rot, "termo_casado": termo})
        enriquecidos.append(linha)
        if chave:
            por_categoria[chave].append(a)

    categorias_result: list[dict] = []
    faltantes: list[str] = []
    atende = True
    for cat, minimo in requeridos.items():
        achados = por_categoria.get(cat, [])
        ok = len(achados) >= minimo
        if not ok:
            atende = False
            falta = minimo - len(achados)
            faltantes.append(f"{rotulo(cat)}" + (f" (faltam {falta})" if minimo > 1 else ""))
        categorias_result.append({
            "chave": cat, "rotulo": rotulo(cat), "min": minimo,
            "qtd": len(achados), "atende": ok,
            "global_ids": [getattr(x, "global_id", "") for x in achados],
        })

    return {
        "tipo": "ambientes",
        "total_ambientes": len(ambientes),
        "categorias": categorias_result,
        "faltantes": faltantes,
        "atende_programa": atende,
        "ambientes": enriquecidos,
        "num_uhs": num_uhs,
    }


def consolidar_areas(ambientes: list[Any]) -> dict:
    """Consolida a área útil da UH somando TODOS os ambientes (IfcSpace).

    Decisão do usuário: a área útil é a soma de **todos** os ambientes do modelo
    (o cumprimento do programa mínimo é garantido à parte, pela dependência de
    EDI-004). Ainda assim classifica cada ambiente (categoria/termo casado) para
    o realce por cor no relatório e o destaque no modelo, e reporta a quebra por
    categoria e os ambientes **sem área** (transparência/robustez).

    Devolve um diagnóstico ``tipo='areas_uh'`` — sem o ``area_min``/``atende``,
    que ficam a cargo de cada regra (EDI-001 = 40 m²; EDI-002 = 41,5 m²).
    """
    enriquecidos: list[dict] = []
    por_categoria: dict[str, float] = defaultdict(float)
    sem_area: list[str] = []
    soma = 0.0
    for a in ambientes:
        chave, rot, termo = classificar(getattr(a, "nome", None))
        linha = a.to_dict() if hasattr(a, "to_dict") else dict(a)
        linha.update({"categoria": chave, "categoria_rotulo": rot, "termo_casado": termo})
        enriquecidos.append(linha)
        area = linha.get("area_m2")
        if isinstance(area, (int, float)) and not isinstance(area, bool):
            soma += float(area)
            por_categoria[rot or "Sem categoria"] += float(area)
        else:
            sem_area.append(linha.get("nome") or linha.get("global_id") or "(sem nome)")

    return {
        "tipo": "areas_uh",
        "area_util_total": round(soma, 2),
        "total_ambientes": len(ambientes),
        "ambientes_sem_area": sem_area,
        "area_por_categoria": [{"rotulo": k, "area_m2": round(v, 2)}
                               for k, v in sorted(por_categoria.items())],
        "ambientes": enriquecidos,
    }
