"""Inspetor de export do Catálogo de Escolas do INEP — **só lê e imprime**.

Existe por um motivo de método, não de comodidade: escrever o leitor do INEP
contra nomes de coluna **supostos** é a receita do erro silencioso. O bug de
detecção aproximada que quase transformou "Código do Município" na chave de
deduplicação (juntando escolas diferentes numa só) foi achado exatamente por
olhar o cabeçalho real antes de confiar nele.

Então este script não escreve nada, não converte nada e não decide nada. Ele
responde cinco perguntas sobre o arquivo que o analista baixou do portal:

1. **Como o arquivo é** — encoding, BOM, separador de campo, quantidade de
   linhas. O portal exporta em UTF-8 com BOM e vírgula, o que é o contrário da
   convenção brasileira que o resto do protótipo assume.
2. **Que colunas existem** — com índice, preenchimento e cardinalidade, porque
   é a cardinalidade que revela se a coluna é categórica (vocabulário fechado,
   mapeável) ou texto livre.
3. **O que a detecção automática casa** — roda o
   ``de_csv_equipamentos.detectar_colunas`` de verdade e mostra o que casou, o
   que faltou e **quais colunas ficaram sem dono**. É teste do leitor contra
   dado real, não simulação.
4. **Que valores aparecem** nos campos categóricos, com contagem, e quais
   deles o vocabulário canônico já traduz — a lista dos NÃO traduzidos é a
   especificação do que falta escrever no ``de_inep.py``.
5. **Cobertura de coordenada por município** — o número que decide se o
   ``insumo_suspeito`` vai disparar no estudo de caso. Coordenada ausente no
   export do Catálogo não vem vazia: vem como uma **cadeia de espaços**, que
   passa por qualquer teste de ``if not celula`` mal escrito.

Uso::

    python scripts/inspecionar_inep.py "entradas/gis/escolas_estrela.csv"
    python scripts/inspecionar_inep.py a.csv b.csv --valores 40
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.dominio import equipamentos as eq
from core.infra.gis import csv_equipamentos as leitor

LARGURA = 78
# Campos cujo vocabulário o leitor tenta traduzir. A ordem é a da avaliação.
VOCABULARIOS = {
    "rede": leitor.VOCAB_REDE,
    "situacao": leitor.VOCAB_SITUACAO,
    "ciclo": leitor.VOCAB_CICLO,
    "conveniada": leitor.VOCAB_BOOLEANO,
}
# Acima disso a coluna é tratada como texto livre e não se lista valor.
LIMITE_CATEGORICA = 30


def _titulo(texto: str) -> None:
    print()
    print("=" * LARGURA)
    print(texto)
    print("=" * LARGURA)


def _secao(texto: str) -> None:
    print()
    print(texto)
    print("-" * len(texto))


def _celulas(caminho: str) -> tuple[list[str], list[list[str]], dict]:
    """Cabeçalho, linhas e dialeto — pela mesma via que o leitor usa."""
    texto, encoding = leitor._ler_texto(caminho)
    dialeto = leitor._dialeto(texto[:8192])
    dialeto["encoding"] = encoding
    with open(caminho, "rb") as f:
        dialeto["bom"] = f.read(3) == b"\xef\xbb\xbf"
    dialeto["bytes"] = os.path.getsize(caminho)

    todas = list(csv.reader(io.StringIO(texto), delimiter=dialeto["separador"]))
    uteis = [l for l in todas if any((c or "").strip() for c in l)]
    dialeto["linhas_brutas"] = len(todas)
    dialeto["linhas_vazias"] = len(todas) - len(uteis)
    if not uteis:
        return [], [], dialeto
    return [c.strip() for c in uteis[0]], uteis[1:], dialeto


def _coordenada_valida(bruto: str) -> tuple[bool, float | None]:
    """Usa o mesmo ``_numero`` do leitor e a faixa do território brasileiro."""
    valor = leitor._numero(bruto)
    if valor is None:
        return False, None
    return -90.0 <= valor <= 90.0 or -180.0 <= valor <= 180.0, valor


def inspecionar(caminho: str, *, amostra: int, valores: int) -> None:
    _titulo(f"ARQUIVO: {os.path.basename(caminho)}")

    cabecalho, linhas, dialeto = _celulas(caminho)
    print(f"  bytes        : {dialeto['bytes']:,}".replace(",", "."))
    print(f"  encoding     : {dialeto['encoding']}"
          f"{'  (BOM presente)' if dialeto.get('bom') else ''}")
    print(f"  separador    : {dialeto['separador']!r}")
    print(f"  linhas       : {len(linhas)} de dados"
          f" (+1 de cabeçalho, {dialeto['linhas_vazias']} vazia(s) ignorada(s))")
    if not cabecalho:
        print("\n  ARQUIVO SEM CONTEÚDO UTILIZÁVEL.")
        return

    # ---- 2. colunas -------------------------------------------------------
    preenchimento: list[int] = []
    distintos: list[Counter] = []
    for i in range(len(cabecalho)):
        contagem: Counter = Counter()
        for linha in linhas:
            bruto = linha[i] if i < len(linha) else ""
            texto = (bruto or "").strip()
            if texto:
                contagem[texto] += 1
        preenchimento.append(sum(contagem.values()))
        distintos.append(contagem)

    _secao(f"COLUNAS ({len(cabecalho)})")
    for i, nome in enumerate(cabecalho):
        vazias = len(linhas) - preenchimento[i]
        marca = "  <- SEM PREENCHIMENTO" if preenchimento[i] == 0 else ""
        print(f"  [{i:>2}] {nome[:44]:<44} {len(distintos[i]):>4} distinto(s)"
              f"  {vazias:>4} vazia(s){marca}")
        print(f"       normalizado: {leitor.normalizar(nome)}")

    # ---- 3. detecção ------------------------------------------------------
    detectadas, faltando = leitor.detectar_colunas(cabecalho)
    _secao("DETECÇÃO AUTOMÁTICA (de_csv_equipamentos.detectar_colunas)")
    for campo in leitor.CAMPOS_OBRIGATORIOS + leitor.CAMPOS_OPCIONAIS:
        col = detectadas.get(campo)
        obrig = "obrigatório" if campo in leitor.CAMPOS_OBRIGATORIOS else "opcional  "
        estado = f"-> '{col}'" if col else "-> NÃO CASOU"
        print(f"  {campo:<12} ({obrig}) {estado}")
    if faltando:
        print(f"\n  FALTANDO (o leitor recusa o arquivo): {', '.join(faltando)}")
    sem_dono = [c for c in cabecalho if c not in detectadas.values()]
    if sem_dono:
        print(f"\n  Colunas sem dono ({len(sem_dono)}) — nenhuma é lida hoje:")
        for c in sem_dono:
            print(f"    · {c}")

    # ---- 4. valores dos campos categóricos --------------------------------
    _secao(f"VALORES DISTINTOS (colunas com até {LIMITE_CATEGORICA} valores)")
    inverso = {col: campo for campo, col in detectadas.items()}
    for i, nome in enumerate(cabecalho):
        contagem = distintos[i]
        if not contagem or len(contagem) > LIMITE_CATEGORICA:
            continue
        campo = inverso.get(nome)
        rotulo = f"[{i}] {nome}"
        if campo:
            rotulo += f"   (detectada como '{campo}')"
        print(f"\n  {rotulo}")
        vocab = VOCABULARIOS.get(campo or "")
        for valor, n in contagem.most_common(valores):
            traducao = ""
            if campo == "ciclo":
                alvos, indistinto = leitor._ciclos(valor, {})
                if alvos:
                    traducao = "  => " + ", ".join(alvos)
                    if indistinto:
                        traducao += " + FUNDAMENTAL SEM DISTINÇÃO DE CICLO"
                elif indistinto:
                    traducao = "  => FUNDAMENTAL SEM DISTINÇÃO DE CICLO"
                else:
                    traducao = "  => fora do recorte"
            elif campo == "situacao":
                situacao, atendimento = leitor._situacao_e_atendimento(valor, {})
                traducao = (f"  => {situacao or 'NÃO TRADUZIDO'}"
                            + (f" / {atendimento}"
                               if atendimento != eq.ATENDIMENTO_GERAL else ""))
            elif campo == "conveniada":
                traducao = f"  => {leitor._booleano(valor)}"
            elif vocab is not None:
                chave = leitor.normalizar(valor)
                if chave in vocab:
                    alvo = vocab[chave]
                    traducao = f"  => {alvo}" if alvo else "  => AMBÍGUO (vazio)"
                else:
                    traducao = "  => NÃO TRADUZIDO"
            print(f"      {n:>5}x  {valor[:52]:<52}{traducao}")
        if len(contagem) > valores:
            print(f"      ... e {len(contagem) - valores} outro(s)")

    # ---- 5. coordenadas ---------------------------------------------------
    col_lat, col_lon = detectadas.get("latitude"), detectadas.get("longitude")
    col_mun = next((c for c in cabecalho
                    if leitor.normalizar(c) in {"municipio", "nome_do_municipio",
                                                "no_municipio"}), None)
    _secao("COBERTURA DE COORDENADA")
    if not (col_lat and col_lon):
        print("  Sem colunas de latitude/longitude detectadas.")
    else:
        i_lat, i_lon = cabecalho.index(col_lat), cabecalho.index(col_lon)
        i_mun = cabecalho.index(col_mun) if col_mun else None
        por_municipio: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        sem_coordenada: list[tuple[int, str]] = []
        formas_de_vazio: Counter = Counter()
        i_nome = cabecalho.index(detectadas["nome"]) if "nome" in detectadas else 0

        for n, linha in enumerate(linhas, start=2):
            bruto_lat = linha[i_lat] if i_lat < len(linha) else ""
            bruto_lon = linha[i_lon] if i_lon < len(linha) else ""
            ok_lat, _ = _coordenada_valida(bruto_lat)
            ok_lon, _ = _coordenada_valida(bruto_lon)
            mun = (linha[i_mun].strip() if i_mun is not None and i_mun < len(linha)
                   else "(sem município)")
            par = por_municipio[mun]
            if ok_lat and ok_lon:
                par[0] += 1
            else:
                par[1] += 1
                nome_escola = (linha[i_nome].strip() if i_nome < len(linha) else "?")
                sem_coordenada.append((n, nome_escola))
                formas_de_vazio[f"lat={bruto_lat!r} lon={bruto_lon!r}"] += 1

        for mun in sorted(por_municipio):
            com, sem = por_municipio[mun]
            total = com + sem
            pct = 100.0 * com / total if total else 0.0
            alerta = "  <- COBERTURA PARCIAL" if sem else ""
            print(f"  {mun[:38]:<38} {com:>4}/{total:<4} com coordenada"
                  f"  ({pct:5.1f}%){alerta}")

        if sem_coordenada:
            print(f"\n  {len(sem_coordenada)} registro(s) sem coordenada utilizável:")
            for n, nome_escola in sem_coordenada[:amostra]:
                print(f"    linha {n:>4}: {nome_escola[:56]}")
            if len(sem_coordenada) > amostra:
                print(f"    ... e {len(sem_coordenada) - amostra} outro(s)")
            print("\n  Como o vazio se apresenta no arquivo:")
            for forma, n in formas_de_vazio.most_common(5):
                print(f"    {n:>4}x  {forma[:66]}")

    # ---- deduplicação -----------------------------------------------------
    col_cod = detectadas.get("codigo_inep")
    _secao("CHAVE DE DEDUPLICAÇÃO")
    if not col_cod:
        print("  Sem coluna de código INEP detectada — mesclar() não deduplica.")
    else:
        i_cod = cabecalho.index(col_cod)
        codigos = Counter((linha[i_cod] or "").strip() for linha in linhas
                          if i_cod < len(linha) and (linha[i_cod] or "").strip())
        repetidos = {c: n for c, n in codigos.items() if n > 1}
        print(f"  Coluna: '{col_cod}'")
        print(f"  {len(codigos)} código(s) distinto(s) em {len(linhas)} linha(s)"
              f" — {len(linhas) - sum(codigos.values())} sem código")
        if repetidos:
            print(f"  ATENÇÃO: {len(repetidos)} código(s) repetido(s) — "
                  "não serve como chave sozinho:")
            for c, n in list(repetidos.items())[:amostra]:
                print(f"    {c}: {n}x")
        else:
            print("  Nenhuma repetição — serve como chave de deduplicação.")

    # ---- leitura de verdade ----------------------------------------------
    _secao("LEITURA PELO de_csv_equipamentos.ler")
    resultado = leitor.ler(caminho, fonte=eq.FONTE_INEP,
                           precisao=eq.PRECISAO_DECLARADA)
    print(f"  equipamentos lidos : {len(resultado.equipamentos)}")
    print(f"  linhas rejeitadas  : {len(resultado.rejeitadas)}")
    for aviso in resultado.avisos:
        print(f"\n  AVISO: {aviso}")
    for n, motivo in resultado.rejeitadas[:amostra]:
        print(f"    linha {n:>4}: {motivo[:60]}")
    if len(resultado.rejeitadas) > amostra:
        print(f"    ... e {len(resultado.rejeitadas) - amostra} outra(s)")
    if resultado.valores_desconhecidos:
        print("\n  Valores que o vocabulário NÃO traduz (é isto que falta escrever):")
        for campo, vals in resultado.valores_desconhecidos.items():
            print(f"    {campo}: {len(vals)} valor(es)")
            for v in vals[:valores]:
                print(f"      · {v[:64]}")

    if resultado.equipamentos:
        for ciclo in (None,) + eq.CICLOS:
            filtragem = eq.filtrar(resultado.equipamentos, ciclo=ciclo)
            rotulo = eq.ROTULO_CICLO.get(ciclo, "qualquer ciclo")
            print(f"\n  Filtros normativos — {rotulo}:")
            print(f"    {filtragem.resumo()}")
            sens = eq.sensibilidade_conveniadas(resultado.equipamentos, ciclo=ciclo)
            if sens["conveniadas_excluidas"]:
                print(f"    Sensibilidade: {sens['considerados']} considerado(s) pela "
                      f"regra pública estrita; seriam "
                      f"{sens['considerados_se_incluisse']} se as "
                      f"{sens['conveniadas_excluidas']} conveniada(s) contassem.")

    # ---- amostra ----------------------------------------------------------
    _secao(f"AMOSTRA ({min(amostra, len(linhas))} primeira(s) linha(s))")
    for linha in linhas[:amostra]:
        print()
        for i, nome in enumerate(cabecalho):
            valor = (linha[i] if i < len(linha) else "") or ""
            print(f"    {nome[:34]:<34} = {valor.strip()[:40]}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspeciona export do Catálogo de Escolas do INEP (só leitura).")
    parser.add_argument("arquivos", nargs="+", help="CSV(s) a inspecionar")
    parser.add_argument("--amostra", type=int, default=3,
                        help="linhas de amostra e de listagem (padrão: 3)")
    parser.add_argument("--valores", type=int, default=25,
                        help="valores distintos por coluna (padrão: 25)")
    args = parser.parse_args(argv)

    for caminho in args.arquivos:
        if not os.path.exists(caminho):
            print(f"NÃO ENCONTRADO: {caminho}")
            continue
        inspecionar(caminho, amostra=args.amostra, valores=args.valores)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
