"""Gera o perfil por requisito e degrau, as degradações, as variações e os dados do gráfico.

Uso, da raiz do repositório (ou de qualquer lugar)::

    python scripts/gerar_tabelas_cenarios.py              # artefatos/cenarios/tabelas/
    python scripts/gerar_tabelas_cenarios.py --saida <pasta>

Lê as saídas por cenário que ``scripts/rodar_cenario.py`` grava em
``artefatos/cenarios/<id>/<chave>.json`` (os cinco relatórios por checagem —
o mesmo contrato do ``relatorio.json`` das telas, ADR-001) e roda **com os
cenários que existirem**: uma coluna some quando o cenário ainda não foi
produzido, e nada é inventado no lugar. A forma é esta:

* **Perfil por requisito × degrau.** 14 linhas agrupadas por
  checagem, uma coluna por enriquecimento (E0 · E1 · E2 · E3); célula =
  ``C`` / ``NC`` / ``NA(motivo)``. Rodapé com **cobertura**
  (concluídos/14) e **conformidade** (conformes/concluídos) por coluna — os
  dois eixos, nunca um índice só.
* **Degradações contra o teto.** Uma coluna por degradação
  (D1…D5, DD1, DD2), só as células que mudaram em relação ao E3, com o
  motivo produzido. Exige o E3; sem ele a tabela sai vazia, com a razão.
* **Variações legítimas.** Uma linha por V1…V5: o pai, "veredito
  mantido: sim/não" pelo critério de estado e motivo iguais nos 14
  requisitos e, quando não, o achado — a lista do que mudou. Nas variantes
  com ``numeros_comparaveis`` (mesma geometria), os ``valor_encontrado``
  também são conferidos, com tolerância relativa 1e-9.
* **Ganho de conclusão por decisão de informação (dados do gráfico).** Os dados
  das barras empilhadas (C / NC / NA) por degrau E0→E3, com a linha do teto
  (concluídos do E3) e a faixa dos requisitos estruturalmente não avaliáveis
  (ENQ-010/011, DN-04).

Cada tabela sai em Markdown (para ler) e em CSV (para uso em texto — sem
formatação). A unidade é sempre o **requisito da
Portaria**, lida do ``resumo.normativo.ids`` de cada relatório, pelo
mesmo ``perfil`` do comando por cenário — este script importa aquele, para
que os dois não possam divergir sobre o que é uma linha.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import os
import sys

_AQUI = os.path.dirname(os.path.abspath(__file__))


def _carregar_rodar_cenario():
    """``scripts/`` não é pacote: o irmão é carregado pelo caminho, como
    ``tests/scripts/`` faz com os inspetores."""
    spec = importlib.util.spec_from_file_location(
        "rodar_cenario", os.path.join(_AQUI, "rodar_cenario.py"))
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["rodar_cenario"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


rc = _carregar_rodar_cenario()      # muda o cwd para a raiz do projeto

# Abreviaturas dos motivos nas células ("NA(motivo abreviado)"). O CSV
# leva o motivo por extenso; o Markdown, a abreviatura.
ABREVIATURA_MOTIVO = {
    "informacao_ausente": "info. ausente",
    "prerequisito_falho": "pré-req.",
    "analise_humana_documental": "parecer",
    "agregacao_indecisa": "agreg. indecisa",
    "metrica_insuficiente": "métrica",
    "porte_indeterminado": "porte",
    "insumo_ausente": "insumo",
    "insumo_suspeito": "insumo susp.",
    "inconsistencia_declaratoria": "declar. inconsist.",
    "insumo_do_proponente_ausente": "insumo prop.",
    "nao_aplicavel": "n/a",
    "terreno_ausente": "terreno",
    "terreno_insuficiente": "terreno insuf.",
    "membro_nao_executado": "membro",
    "mapeamento_pendente": "mapeamento",
    "verificacao_em_campo": "campo",
    "erro_de_execucao": "erro",
}

# Os requisitos que nenhum nível de informação do proponente destrava
# (alternativa B remetida a parecer, DN-04) — a faixa da Figura 4.
ESTRUTURALMENTE_NAO_AVALIAVEIS = ("ENQ-010", "ENQ-011")


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------

def perfis_existentes(config: dict) -> dict[str, list[dict]]:
    """``{id: perfil}`` dos cenários com os cinco relatórios em disco."""
    perfis: dict[str, list[dict]] = {}
    for c in config["cenarios"]:
        linhas = rc.ler_perfil(config, c["id"])
        if linhas:
            perfis[c["id"]] = linhas
    return perfis


def por_familia(config: dict, familia: str) -> list[dict]:
    return [c for c in config["cenarios"] if c["familia"] == familia]


def rotulo_checagem(config: dict, chave: str) -> str:
    return next((ch["rotulo"] for ch in config["checagens"] if ch["chave"] == chave),
                chave)


def celula_md(linha: dict | None) -> str:
    if linha is None:
        return "—"
    if linha["estado"] == "nao_avaliavel":
        return f"NA({ABREVIATURA_MOTIVO.get(linha['motivo'], linha['motivo'] or '?')})"
    return rc.ABREVIATURA_ESTADO[linha["estado"]]


def contagens(perfil: list[dict]) -> dict:
    c = {"C": 0, "NC": 0, "NA": 0}
    for linha in perfil:
        c[rc.ABREVIATURA_ESTADO[linha["estado"]]] += 1
    total = len(perfil)
    concluidos = c["C"] + c["NC"]
    return {**c, "total": total, "concluidos": concluidos,
            "cobertura": f"{concluidos}/{total}",
            "conformidade": (f"{c['C']}/{concluidos}" if concluidos else "—")}


# ---------------------------------------------------------------------------
# Tabela 3 — perfil por requisito × degrau
# ---------------------------------------------------------------------------

def tabela_3(config: dict, perfis: dict[str, list[dict]]) -> tuple[list[str], list[list[str]], list[str]]:
    degraus = [c["id"] for c in por_familia(config, "enriquecimento") if c["id"] in perfis]
    if not degraus:
        return [], [], ["nenhum enriquecimento (E0…E3) em artefatos/cenarios/ — "
                        "rode scripts/rodar_cenario.py E0"]
    referencia = perfis[degraus[0]]
    cabecalho = ["checagem", "requisito", *degraus]
    linhas: list[list[str]] = []
    for base in referencia:
        rid = base["requisito"]
        linha = [rotulo_checagem(config, base["checagem"]), rid]
        for d in degraus:
            linha.append(next((x for x in perfis[d] if x["requisito"] == rid), None))
        linhas.append(linha)
    rodape = []
    for eixo in ("cobertura", "conformidade"):
        rodape.append([eixo, ""] + [contagens(perfis[d])[eixo] for d in degraus])
    return cabecalho, linhas, rodape


# ---------------------------------------------------------------------------
# Tabela 4 — degradações contra o teto
# ---------------------------------------------------------------------------

def tabela_4(config: dict, perfis: dict[str, list[dict]]):
    teto = perfis.get("E3")
    degradacoes = [c["id"] for c in por_familia(config, "degradacao") if c["id"] in perfis]
    if teto is None:
        return [], [], ["o teto (E3) não está em artefatos/cenarios/ — a Tabela 4 "
                        "compara contra ele (§15.7)"]
    if not degradacoes:
        return [], [], ["nenhuma degradação (D1…D5, DD1, DD2) em artefatos/cenarios/"]
    cabecalho = ["checagem", "requisito", "E3 (teto)", *degradacoes]
    linhas, iguais = [], 0
    for base in teto:
        rid = base["requisito"]
        celulas = []
        for d in degradacoes:
            atual = next((x for x in perfis[d] if x["requisito"] == rid), None)
            celulas.append(atual if atual is not None and not rc.mesmo_veredito(base, atual)
                           else None)
        if any(c is not None for c in celulas):
            linhas.append([rotulo_checagem(config, base["checagem"]), rid, base, *celulas])
        else:
            iguais += 1
    notas = [f"{iguais} requisito(s) sem nenhuma mudança contra o teto (omitidos); "
             "célula vazia = veredito igual ao E3"]
    return cabecalho, linhas, notas


# ---------------------------------------------------------------------------
# Tabela 5 — variações legítimas
# ---------------------------------------------------------------------------

def comparar_variacao(config: dict, perfis: dict[str, list[dict]], c: dict) -> dict:
    """Uma linha da Tabela 5: mantido? e o achado, se não."""
    pai = c.get("pai")
    atual, base = perfis.get(c["id"]), perfis.get(pai)
    if atual is None:
        return {"id": c["id"], "pai": pai, "situacao": "não produzida", "mantido": "",
                "achado": rc.faltando(config, c["id"])}
    if base is None:
        return {"id": c["id"], "pai": pai, "situacao": "sem o pai", "mantido": "",
                "achado": f"o pai {pai} não está em artefatos/cenarios/"}
    por_id = {x["requisito"]: x for x in base}
    mudaram, numeros = [], []
    for linha in atual:
        ref = por_id.get(linha["requisito"])
        if ref is None:
            mudaram.append(f"{linha['requisito']}: só na variação")
            continue
        if not rc.mesmo_veredito(ref, linha):
            mudaram.append(f"{linha['requisito']}: {rc.celula(ref)} → {rc.celula(linha)}")
        elif c.get("numeros_comparaveis") and not rc.numeros_iguais(
                ref["valor_encontrado"], linha["valor_encontrado"]):
            numeros.append(f"{linha['requisito']}: {ref['valor_encontrado']!r} → "
                           f"{linha['valor_encontrado']!r}")
    faltam = [rid for rid in por_id if rid not in {x["requisito"] for x in atual}]
    mudaram += [f"{rid}: só no pai" for rid in faltam]
    mantido = not mudaram and not numeros
    achado = "; ".join(mudaram + [f"números: {n}" for n in numeros])
    return {"id": c["id"], "pai": pai, "situacao": "comparada",
            "mantido": "sim" if mantido else "não", "achado": achado}


def tabela_5(config: dict, perfis: dict[str, list[dict]]):
    variacoes = por_familia(config, "variacao")
    cabecalho = ["variação", "sobre", "pai", "situação", "veredito mantido", "achado"]
    linhas = []
    for c in variacoes:
        r = comparar_variacao(config, perfis, c)
        linhas.append([c["id"], c["rotulo"], r["pai"] or "—", r["situacao"],
                       r["mantido"] or "—", r["achado"]])
    return cabecalho, linhas, []


# ---------------------------------------------------------------------------
# Figura 4 — dados
# ---------------------------------------------------------------------------

def figura_4(config: dict, perfis: dict[str, list[dict]]):
    degraus = [c["id"] for c in por_familia(config, "enriquecimento") if c["id"] in perfis]
    cabecalho = ["degrau", "C", "NC", "NA", "concluidos", "total",
                 "teto", "estruturalmente_NA"]
    teto = contagens(perfis["E3"])["concluidos"] if "E3" in perfis else ""
    linhas = []
    for d in degraus:
        cont = contagens(perfis[d])
        estruturais = sum(1 for x in perfis[d]
                          if x["requisito"] in ESTRUTURALMENTE_NAO_AVALIAVEIS
                          and x["estado"] == "nao_avaliavel")
        linhas.append([d, cont["C"], cont["NC"], cont["NA"], cont["concluidos"],
                       cont["total"], teto, estruturais])
    notas = ([] if teto != "" else
             ["teto em branco: o E3 não está em artefatos/cenarios/"])
    return cabecalho, linhas, notas


# ---------------------------------------------------------------------------
# Escrita
# ---------------------------------------------------------------------------

def _texto(valor, md: bool) -> str:
    if isinstance(valor, dict):          # uma linha de perfil
        return celula_md(valor) if md else rc.celula(valor)
    if valor is None:
        return ""
    return str(valor)


def escrever(pasta: str, nome: str, titulo: str, cabecalho: list[str],
             linhas: list[list], rodape: list[list] | None = None,
             notas: list[str] | None = None) -> None:
    os.makedirs(pasta, exist_ok=True)
    with open(os.path.join(pasta, f"{nome}.csv"), "w", encoding="utf-8",
              newline="") as f:
        w = csv.writer(f, delimiter=";")
        if cabecalho:
            w.writerow(cabecalho)
        for linha in linhas:
            w.writerow([_texto(v, md=False) for v in linha])
        for linha in rodape or []:
            w.writerow([_texto(v, md=False) for v in linha])
    with open(os.path.join(pasta, f"{nome}.md"), "w", encoding="utf-8") as f:
        f.write(f"# {titulo}\n\n")
        if cabecalho:
            f.write("| " + " | ".join(cabecalho) + " |\n")
            f.write("|" + "---|" * len(cabecalho) + "\n")
            for linha in linhas:
                f.write("| " + " | ".join(_texto(v, md=True) for v in linha) + " |\n")
            for linha in rodape or []:
                f.write("| " + " | ".join(f"**{_texto(v, md=True)}**" if v != "" else ""
                                          for v in linha) + " |\n")
        for nota in notas or []:
            f.write(f"\n> {nota}\n")


def gerar(config: dict, pasta: str) -> dict[str, list[dict]]:
    perfis = perfis_existentes(config)
    cab, linhas, rodape = tabela_3(config, perfis)
    escrever(pasta, "tabela_3", "Tabela 3 — Perfil por requisito × degrau de informação",
             cab, linhas, rodape if cab else None, None if cab else rodape)
    cab, linhas, notas = tabela_4(config, perfis)
    escrever(pasta, "tabela_4", "Tabela 4 — Degradações contra o teto (E3)",
             cab, linhas, notas=notas)
    cab, linhas, notas = tabela_5(config, perfis)
    escrever(pasta, "tabela_5", "Tabela 5 — Variações legítimas: o veredito se mantém?",
             cab, linhas, notas=notas)
    cab, linhas, notas = figura_4(config, perfis)
    escrever(pasta, "figura_4", "Figura 4 — Ganho de conclusão por decisão de informação (dados)",
             cab, linhas, notas=notas)
    return perfis


def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="Gera as Tabelas 3, 4 e 5 e os dados da Figura 4 (§15.7).")
    parser.add_argument("--saida", default=None,
                        help="Pasta de saída (padrão: artefatos/cenarios/tabelas/).")
    args = parser.parse_args()
    config = rc.carregar_config()
    pasta = args.saida or os.path.join(config["pastas"]["saida"], "tabelas")
    perfis = gerar(config, pasta)
    print(f"cenários encontrados: {', '.join(perfis) or 'nenhum'}")
    for nome in ("tabela_3", "tabela_4", "tabela_5", "figura_4"):
        print(f"  {os.path.join(pasta, nome)}.md / .csv")
    for nome in ("tabela_3", "tabela_4", "tabela_5", "figura_4"):
        print()
        with open(os.path.join(pasta, f"{nome}.md"), encoding="utf-8") as f:
            print(f.read().rstrip())


if __name__ == "__main__":
    _cli()
