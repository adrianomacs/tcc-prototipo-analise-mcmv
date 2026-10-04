"""Gera o recorte municipal de equipamentos a partir das bases nacionais do INEP.

Este script é a **fronteira** entre as bases nacionais e o aplicativo. Do lado
de cá ficam três arquivos de centenas de megabytes que não são versionáveis nem
citáveis; do lado de lá, um CSV de algumas dezenas de linhas por município, mais
um JSON de procedência. **O app nunca atravessa essa fronteira**: ele lê o
recorte e só. Se o município pedido não tiver recorte, isso é ``insumo_ausente``
— NÃO AVALIÁVEL, com o CSV do usuário oferecido como caminho complementar —, e
nunca uma consulta às bases nacionais.

Por que não deixar o app consultar direto
-----------------------------------------

Não é desempenho: a passada completa pelos três arquivos leva cerca de cinco
segundos, o que seria aceitável em tela. São outras três razões:

1. **Distribuição.** 327 MB fora do controle de versão contra ~30 linhas dentro
   dele. É a diferença entre um repositório que um terceiro clona e roda e um
   que só funciona na máquina de quem o gerou.
2. **Procedência.** O JSON registra URL, safra do Censo, data da geração,
   SHA-256 de cada fonte e as contagens por motivo de descarte. É isso que
   permite conferir um número sem ter o arquivo de 141 MB.
3. **Estabilidade.** Consultando a base viva, os números mudariam
   sozinhos quando o INEP publicasse a safra seguinte — debaixo de um trabalho
   já publicado. Congelado, o número publicado e o número do código são o mesmo
   número, permanentemente.

Comportamento preguiçoso
------------------------

Município já gerado é pulado. "Já gerado" não é "o arquivo existe": é "o arquivo
existe **e** o SHA-256 das três fontes bate com o que está na procedência". Se
alguma fonte mudou, o recorte é declarado **defasado** e o script diz isso em vez
de reusá-lo calado — reusar cache velho sem avisar seria a versão silenciosa do
mesmo erro que este módulo inteiro existe para não cometer.

Acrescentar um município novo
-----------------------------

Não exige download nenhum: as três bases já são **nacionais**, então todo
município do país já está nelas. São dois comandos::

    python scripts/gerar_equipamentos.py --procurar "bom jesus" --uf RS
    python scripts/gerar_equipamentos.py --municipio 4302303

O primeiro existe porque a extração é pelo **código IBGE** e ninguém o sabe de
cor — e exigir o código sem oferecer como descobri-lo empurraria o usuário a
buscá-lo fora da ferramenta, e a digitá-lo errado.

Uso::

    python scripts/gerar_equipamentos.py --municipio 4307807
    python scripts/gerar_equipamentos.py --municipio <codigo_ibge> --municipio <codigo_ibge>
    python scripts/gerar_equipamentos.py --municipio 4307807 --forcar
    python scripts/gerar_equipamentos.py --listar
    python scripts/gerar_equipamentos.py --procurar estrela --uf RS
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.dominio import equipamentos as eq
from core.infra.gis import inep as de_inep

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTES_PADRAO = os.path.join(RAIZ, "entradas", "inep")
SAIDA_PADRAO = os.path.join(RAIZ, "config")
VERSAO = "1.0"
URL_MICRODADO = ("https://www.gov.br/inep/pt-br/acesso-a-informacao/"
                 "dados-abertos/microdados/censo-escolar")
URL_CATALOGO = "https://www.gov.br/inep/pt-br/areas-de-atuacao/pesquisas-estatisticas-e-indicadores/censo-escolar"

# Como cada fonte é reconhecida na pasta de entrada. Prefixo, não nome exato:
# o INEP já mudou o nome do arquivo entre safras (``microdados_ed_basica_2024``
# virou ``Tabela_Escola_2025_V2``), e fixar o nome completo quebraria na próxima.
PADROES = {
    de_inep.PAPEL_ESCOLA: ("tabela_escola", "microdados_ed_basica"),
    de_inep.PAPEL_TURMA: ("tabela_turma",),
    de_inep.PAPEL_CATALOGO: ("analise - tabela da lista das escolas",
                             "tabela da lista das escolas", "catalogo"),
}

COLUNAS_SAIDA = ("codigo_inep", "nome", "latitude", "longitude", "ciclo",
                 "rede", "situacao", "atendimento", "conveniada", "endereco")


def localizar_fontes(pasta: str) -> tuple[dict[str, str], list[str]]:
    """Casa cada papel com um arquivo da pasta; devolve também o que não achou."""
    achados: dict[str, str] = {}
    if os.path.isdir(pasta):
        arquivos = sorted(f for f in os.listdir(pasta) if f.lower().endswith(".csv"))
        for papel, prefixos in PADROES.items():
            for nome in arquivos:
                baixo = nome.lower()
                if any(baixo.startswith(p) or p in baixo for p in prefixos):
                    achados[papel] = os.path.join(pasta, nome)
                    break
    faltando = [p for p in de_inep.PAPEIS if p not in achados]
    return achados, faltando


def caminhos(saida: str, codigo: str) -> tuple[str, str]:
    return (os.path.join(saida, f"equipamentos_{codigo}.csv"),
            os.path.join(saida, f"equipamentos_{codigo}.json"))


def estado(saida: str, codigo: str, fontes: dict[str, str]) -> tuple[str, dict | None]:
    """``('ausente' | 'atual' | 'defasado', procedencia)``.

    O SHA-256 é o que distingue "já gerado" de "gerado a partir de outro
    arquivo". Sem ele, o comportamento preguiçoso viraria cache mentiroso.
    """
    csv_path, json_path = caminhos(saida, codigo)
    if not (os.path.exists(csv_path) and os.path.exists(json_path)):
        return "ausente", None
    try:
        with open(json_path, encoding="utf-8") as f:
            proc = json.load(f)
    except (OSError, json.JSONDecodeError):
        return "defasado", None
    gravados = {f["papel"]: f.get("sha256") for f in proc.get("fontes", [])}
    for papel, caminho in fontes.items():
        if not gravados.get(papel):
            return "defasado", proc
        if gravados[papel] != de_inep.sha256(caminho):
            return "defasado", proc
    return "atual", proc


def gravar(extracao: de_inep.Extracao, saida: str, fontes: dict[str, str]) -> dict:
    """Escreve o CSV do recorte e o JSON de procedência; devolve o resumo."""
    os.makedirs(saida, exist_ok=True)
    csv_path, json_path = caminhos(saida, extracao.municipio)

    # Sem coordenada, o estabelecimento não pode ser usado por regra alguma de
    # distância. Ele fica FORA do CSV e DENTRO da procedência, contado pelo
    # nome do motivo — some do insumo, não do relato.
    com_coord = [e for e in extracao.equipamentos if e.lat is not None]
    sem_coord = [e for e in extracao.equipamentos if e.lat is None]

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";", lineterminator="\n")
        w.writerow(COLUNAS_SAIDA)
        for e in sorted(com_coord, key=lambda x: (x.nome or "", x.codigo_inep or "")):
            w.writerow([
                e.codigo_inep or "", e.nome, f"{e.lat:.8f}", f"{e.lon:.8f}",
                # '|' e não ';': o separador de campo é ';', e uma célula com
                # ';' não citada se parte em duas na primeira planilha que a
                # reabrir e salvar.
                "|".join(e.ciclos), e.rede, e.situacao, e.atendimento,
                "" if e.conveniada is None else ("sim" if e.conveniada else "nao"),
                e.endereco or "",
            ])

    filtragem = eq.filtrar(extracao.equipamentos)
    por_ciclo = {c: len(eq.filtrar(extracao.equipamentos, ciclo=c).aceitos)
                 for c in eq.CICLOS}
    sensibilidade = {c: eq.sensibilidade_conveniadas(extracao.equipamentos, ciclo=c)
                     for c in eq.CICLOS}

    procedencia = {
        "municipio": extracao.municipio,
        "nome_municipio": extracao.nome_municipio,
        "uf": extracao.uf,
        "ano_censo": extracao.ano_censo,
        "gerado_em": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "gerador": {"script": "scripts/gerar_equipamentos.py", "versao": VERSAO},
        "urls": {"microdado": URL_MICRODADO, "catalogo": URL_CATALOGO},
        "precedencia_por_campo": {
            "identidade": "microdado/Tabela_Escola",
            "rede": "microdado/Tabela_Escola",
            "situacao": "microdado/Tabela_Escola",
            "ciclos": "microdado/Tabela_Turma",
            "coordenada": "Catálogo de Escolas",
            "conveniada": "Catálogo de Escolas",
            "motivo": ("a divulgação pública do microdado 2025 não traz "
                       "coordenada nem oferta de etapa; a precedência por campo "
                       "é imposição da fonte, não escolha de projeto"),
        },
        "fontes": [f.to_dict() for f in extracao.fontes],
        "contagens": {
            "no_municipio": len(extracao.equipamentos),
            "gravados_no_csv": len(com_coord),
            "sem_coordenada": len(sem_coord),
            "considerados_apos_filtros": len(filtragem.aceitos),
            "por_motivo_de_descarte": filtragem.contagem_por_motivo,
            "aptos_por_ciclo": por_ciclo,
            "resumo": filtragem.resumo(),
        },
        "sensibilidade_conveniadas": sensibilidade,
        "divergencias_entre_fontes": extracao.divergencias.to_dict(),
        "avisos": extracao.avisos,
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(procedencia, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return procedencia


def _resumo(proc: dict) -> str:
    c = proc["contagens"]
    ciclos = "  ".join(f"{k}={v}" for k, v in c["aptos_por_ciclo"].items())
    return (f"{proc['nome_municipio']}/{proc['uf']} · censo {proc['ano_censo']} · "
            f"{c['no_municipio']} no município, {c['gravados_no_csv']} com "
            f"coordenada, {c['considerados_apos_filtros']} considerados · {ciclos}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--municipio", action="append", default=[], metavar="COD_IBGE",
                   help="código IBGE de 7 dígitos; pode repetir")
    p.add_argument("--fontes", default=FONTES_PADRAO,
                   help="pasta com as bases nacionais (padrão: entradas/inep)")
    p.add_argument("--saida", default=SAIDA_PADRAO,
                   help="pasta do recorte versionado (padrão: config)")
    p.add_argument("--forcar", action="store_true",
                   help="regera mesmo que o recorte esteja atual")
    p.add_argument("--listar", action="store_true",
                   help="lista os recortes já gerados e o estado de cada um")
    p.add_argument("--procurar", metavar="NOME",
                   help="descobre o código IBGE pelo nome do município")
    p.add_argument("--uf", metavar="SG", default=None,
                   help="restringe --procurar a uma UF (ex.: RS)")
    args = p.parse_args(argv)

    fontes, faltando = localizar_fontes(args.fontes)

    if args.procurar:
        if de_inep.PAPEL_ESCOLA in faltando:
            print(f"Base de escolas não encontrada em {args.fontes}.")
            return 1
        achados = de_inep.procurar_municipios(
            fontes[de_inep.PAPEL_ESCOLA], args.procurar, uf=args.uf)
        if not achados:
            print(f"Nenhum município casando com {args.procurar!r}"
                  + (f" em {args.uf.upper()}." if args.uf else "."))
            return 1
        print(f"{len(achados)} município(s) — use o código na coluna da esquerda:\n")
        for codigo, nome, sigla, n in achados:
            print(f"  {codigo}  {sigla}  {nome:<42} {n:>5} estabelecimento(s)")
        if len(achados) > 1:
            print("\n  Homônimos são comuns. A contagem de estabelecimentos ajuda a"
                  "\n  desempatar, mas quem decide qual é o município do"
                  "\n  empreendimento é você, não a contagem.")
        return 0

    if args.listar:
        existentes = sorted(f for f in os.listdir(args.saida)
                            if f.startswith("equipamentos_") and f.endswith(".json")
                            ) if os.path.isdir(args.saida) else []
        if not existentes:
            print(f"Nenhum recorte em {args.saida}.")
            return 0
        for nome in existentes:
            codigo = nome[len("equipamentos_"):-len(".json")]
            with open(os.path.join(args.saida, nome), encoding="utf-8") as f:
                proc = json.load(f)
            est = estado(args.saida, codigo, fontes)[0] if not faltando else "?"
            print(f"  [{est:<8}] {codigo}  {_resumo(proc)}")
        return 0

    if not args.municipio:
        p.error("informe ao menos um --municipio "
                "(ou use --listar, ou --procurar <nome> para achar o código)")
    if faltando:
        print("FONTES NÃO ENCONTRADAS em", args.fontes)
        for papel in faltando:
            print(f"  {papel}: nenhum CSV casando com {PADROES[papel]}")
        print("\nO recorte não pode ser gerado sem as três. Elas não são "
              "versionadas — veja docs/modulos/enquadramento/recorte_tcc.md §3.7.")
        return 1

    print("Fontes:")
    for papel in de_inep.PAPEIS:
        print(f"  {papel:<10} {os.path.basename(fontes[papel])}")

    houve_erro = False
    for codigo in args.municipio:
        codigo = codigo.strip()
        print(f"\n--- {codigo} " + "-" * 56)
        situacao, proc = estado(args.saida, codigo, fontes)
        if situacao == "atual" and not args.forcar:
            print("  já gerado e atual (SHA-256 das três fontes confere) — pulando.")
            print("  " + _resumo(proc))
            continue
        if situacao == "defasado":
            print("  recorte DEFASADO: alguma fonte mudou desde a geração. "
                  "Regerando." if not args.forcar else "  regerando (--forcar).")

        extracao = de_inep.extrair(codigo, escola=fontes[de_inep.PAPEL_ESCOLA],
                                   turma=fontes[de_inep.PAPEL_TURMA],
                                   catalogo=fontes[de_inep.PAPEL_CATALOGO])
        if extracao.faltando:
            print("  COLUNAS ESSENCIAIS AUSENTES:")
            for papel, cols in extracao.faltando.items():
                print(f"    {papel}: {', '.join(cols)}")
            houve_erro = True
            continue
        if not extracao.equipamentos:
            print(f"  nenhum estabelecimento com CO_MUNICIPIO = {codigo}.")
            for a in extracao.avisos:
                print(f"    {a}")
            houve_erro = True
            continue

        proc = gravar(extracao, args.saida, fontes)
        csv_path, json_path = caminhos(args.saida, codigo)
        print("  " + _resumo(proc))
        print(f"  gravado: {os.path.relpath(csv_path, RAIZ)}")
        print(f"           {os.path.relpath(json_path, RAIZ)}")
        div = {k: v for k, v in proc["divergencias_entre_fontes"].items()
               if k != "codigos" and v}
        if div:
            print(f"  divergências entre as duas fontes oficiais: {div}")
        for a in proc["avisos"]:
            print(f"  aviso: {a}")

    return 1 if houve_erro else 0


if __name__ == "__main__":
    raise SystemExit(main())
